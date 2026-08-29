"""tools.py — Honest Mistake, Layer 2 tool layer.

The agent's entire view of the model and dataset passes through the eight
tools defined here. Nothing else is observable to it.

WHAT THIS LAYER DELIBERATELY WITHHOLDS
--------------------------------------
The agent is being evaluated on whether it can identify target leakage on
its own. Several artefacts on disk already contain that conclusion, drawn
by a human during Layer 1. If the agent could read any of them it would be
reciting an answer rather than deriving one, and the evaluation would
measure nothing.

The following are therefore unreachable through every tool here, directly
or indirectly:

    outputs/leakage_drop_log.txt          the verdict, per column, with reasons
    outputs/audit_notes.txt               the SHAP audit and its findings
    outputs/fairness_ablation_notes.txt   the fairness experiment's conclusion
    outputs/features_notes.txt            which columns were removed and why
    outputs/build_dataset_notes.txt       the construction-time removal counts
    agent/data_dictionary.py (source)     the templates and grouping that
                                          reveal which families were removed

The dictionary module is imported and called through its two public
functions; its source text, its FEATURE_DOCS mapping, and its generation
templates are never returned. No tool accepts a path, lists a directory,
runs a shell command, or evaluates code, so there is no indirect route to
any of the files above.

Errors are returned as plain sentences. Filesystem paths, module names,
and tracebacks are never exposed to the agent, since those would leak the
project's structure and hint at what else exists.

Filesystem paths this module reads (the complete list):
    outputs/agent_cache/shap_global.csv
    outputs/agent_cache/shap_values.parquet
    outputs/agent_cache/ablation_cache.csv
    outputs/agent_cache/coverage_profile.csv
    outputs/agent_cache/univariate_assoc.csv
    outputs/agent_cache/correlation_topk.csv

Each is a fixed filename joined to the cache directory chosen once at
construction. No filename, directory, or path fragment is ever taken from a
tool argument.
"""

from pathlib import Path

import pandas as pd

from agent import data_dictionary as _dict
from agent.data_dictionary import lookup as _dict_lookup
from agent.data_dictionary import search as _dict_search

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CACHE = _PROJECT_ROOT / "outputs" / "agent_cache"
_SHAP_GLOBAL_CSV = _CACHE / "shap_global.csv"
_SHAP_VALUES_PARQUET = _CACHE / "shap_values.parquet"
_ABLATION_CSV = _CACHE / "ablation_cache.csv"
_COVERAGE_CSV = _CACHE / "coverage_profile.csv"
_UNIVARIATE_CSV = _CACHE / "univariate_assoc.csv"
_CORRELATION_CSV = _CACHE / "correlation_topk.csv"

# 2.0: eight tools rather than five, a second suppression switch, and
# dictionary search backed by a vector index rather than substring
# matching. A 1.0 run and a 2.0 run gave the agent materially different
# evidence, so they must not share a version string.
TOOL_LAYER_VERSION = "2.0"

# What run_config reports when the vector index served every dictionary
# search. Mirrors agent.retrieval.RETRIEVAL_BACKEND, restated here so the
# stamp does not depend on the retrieval module importing cleanly.
RETRIEVAL_BACKEND = "pgvector-bge-small-en-v1.5"

# search() can otherwise be used to dump the whole dictionary in one call.
_SEARCH_LIMIT = 25

# |SHAP| below this counts as "no contribution" for this row.
_NEAR_ZERO = 1e-3

# ----------------------------------------------------------------------
# WHAT include_vintage_scopes GOVERNS — read this before adding a tool.
#
# The switch removes every per-vintage *measurement* from what the agent
# can see. It is not a filter on one tool; it is a statement about a class
# of number, and it has to be applied at every site that reports one.
# Twice now the switch's reach has been described as wider than its
# implementation, because a tool was added carrying an annual field and
# the switch was not extended to it. If you add a third, extend this list.
#
# Governed today, when include_vintage_scopes is False:
#     get_feature_coverage             the 2014/2015/2016/2017 scope
#                                      entries are dropped from `scopes`
#     get_feature_target_association   the auc_2014 / auc_2015 / auc_2016
#                                      keys are dropped, and any scope
#                                      note stops naming them
#
# In both cases the fields are absent, not blanked: no placeholder, no
# null, and nothing anywhere in the payload saying that something was
# withheld. A note explaining the gap would tell the agent the figures
# exist, which is the one thing the ablation cannot afford.
#
# Deliberately NOT governed:
#     get_ablation_result's note      names 2017 because that is what the
#                                     held-out split *is*. Naming a split
#                                     is not reporting a per-vintage
#                                     measurement, and the agent is told
#                                     the split either way.
#     the dictionary's own text       entries such as il_util say their
#                                     field was collected from around
#                                     December 2015. That is documentation
#                                     of the column, and it falls under
#                                     include_populated, which is a
#                                     separate switch with its own arm of
#                                     the experiment.
# ----------------------------------------------------------------------
_SPLIT_SCOPES = ("train", "test")
_VINTAGE_SCOPES = ("2014", "2015", "2016", "2017")

# correlation_topk.csv holds 15 neighbours per feature and no more, so a
# larger request cannot be served by reading further.
_DEFAULT_TOP_K = 5
_MAX_TOP_K = 15


class ToolLayer:
    """The eight tools, bound to one fixed configuration.

    The two suppression switches, `include_populated` and
    `include_vintage_scopes`, are constructor arguments, so they are fixed
    for the lifetime of the object and are not parameters of any tool. The
    agent calls tools only through `dispatch`, which forwards only the
    arguments declared in the published schemas — neither switch appears
    there. The agent therefore cannot read, set, or vary either one.

    Chosen over a module-level global or a runtime patch because the
    binding is explicit and per-instance: two configurations can exist
    side by side in one process (useful when running the A/B comparison),
    and `run_config()` stamps every run with the setting that produced it.
    """

    def __init__(self, include_populated: bool = True,
                 include_vintage_scopes: bool = True,
                 cache_dir: Path | None = None):
        self.include_populated = bool(include_populated)
        # When false, get_feature_coverage reports the train and test
        # scopes only. The vintage scopes are dropped, not blanked: no
        # placeholder row and no note that anything was left out, since
        # either would tell the agent that per-vintage figures exist.
        self.include_vintage_scopes = bool(include_vintage_scopes)
        # A parallel cache lets a canary variant be audited without
        # overwriting Layer 1's artefacts. The directory is part of the
        # run's identity, so it is stamped into config_id.
        self.cache_dir = Path(cache_dir) if cache_dir else _CACHE
        self._shap_global_csv = self.cache_dir / "shap_global.csv"
        self._shap_values_parquet = self.cache_dir / "shap_values.parquet"
        self._ablation_csv = self.cache_dir / "ablation_cache.csv"
        self._coverage_csv = self.cache_dir / "coverage_profile.csv"
        self._univariate_csv = self.cache_dir / "univariate_assoc.csv"
        self._correlation_csv = self.cache_dir / "correlation_topk.csv"
        self._shap_global: pd.DataFrame | None = None
        self._shap_values: pd.DataFrame | None = None
        self._ablation: pd.DataFrame | None = None
        self._coverage: pd.DataFrame | None = None
        self._univariate: pd.DataFrame | None = None
        self._correlation: pd.DataFrame | None = None
        self._calls: list[dict] = []

    # ------------------------------------------------------------------
    # Run identification
    # ------------------------------------------------------------------
    def run_config(self) -> dict:
        """Configuration stamp for logging. Not exposed as a tool."""
        state = "included" if self.include_populated else "suppressed"
        scopes = "all" if self.include_vintage_scopes else "splitonly"
        variant = "canary" if self.cache_dir != _CACHE else "layer1"
        retrieval = self._retrieval_served()
        return {
            "tool_layer_version": TOOL_LAYER_VERSION,
            "dictionary_populated_field": state,
            "coverage_scopes": scopes,
            "retrieval": retrieval,
            "artefact_variant": variant,
            "cache_dir": self.cache_dir.name,
            "config_id": (f"toolsv{TOOL_LAYER_VERSION}-populated-{state}"
                          f"-scopes-{scopes}-retrieval-{retrieval}"
                          f"-{variant}"),
        }

    @staticmethod
    def _retrieval_served() -> str:
        """Which backend actually served dictionary search in this process.

        Reports what happened, not what was configured. A run that fell
        back to substring matching because the index was unreachable is a
        different experiment from one the index served, and the stamp has
        to say so without anyone having to remember.
        """
        used = _dict.retrieval_paths_used()
        if not used:
            # No dictionary search was made, so nothing served one. Saying
            # "pgvector" here would claim a backend the run never used.
            return "unused"
        if used == {"pgvector"}:
            return RETRIEVAL_BACKEND
        if used == {"keyword-fallback"}:
            return "keyword-fallback"
        return "mixed"

    # ------------------------------------------------------------------
    # Call log — for analysing behaviour after a run.
    #
    # Records what was asked and how it turned out, never the payload:
    # a log that carried full returns could be used to reconstruct the
    # findings without rerunning, and would defeat its own purpose as an
    # independent record of what the agent actually did.
    #
    # These methods are not tools. `dispatch` resolves names against the
    # five tools only, so the agent can neither read nor clear the log.
    # ------------------------------------------------------------------
    def get_call_log(self) -> dict:
        """Full log plus its configuration stamp, ready to serialise."""
        return {
            "config": self.run_config(),
            "call_count": len(self._calls),
            "calls": [dict(c) for c in self._calls],
        }

    def reset_call_log(self) -> None:
        """Clear the log between runs. Configuration is unaffected."""
        self._calls = []

    @staticmethod
    def _outcome(name: str, result: dict) -> str:
        """One-line summary of how a call turned out."""
        if name in ("lookup_feature", "get_feature_shap_detail",
                    "get_feature_coverage",
                    "get_feature_target_association"):
            if "found" not in result:
                return "error"
            return "found" if result["found"] else "not_found"
        if name == "search_data_dictionary":
            if "match_count" not in result:
                return "error"
            return f"match_count={result['match_count']}"
        if name == "get_shap_ranking":
            if "returned" not in result:
                return "error"
            return f"returned={result['returned']}"
        if name == "get_ablation_result":
            if "available" not in result:
                return "error"
            return "available" if result["available"] else "not_precomputed"
        if name == "get_correlated_features":
            if "available" not in result:
                return "error"
            return "available" if result["available"] else "not_available"
        return "error"

    def _record(self, name: str, arguments: dict, ok: bool,
                outcome: str) -> None:
        self._calls.append({
            "seq": len(self._calls) + 1,
            "tool": name,
            "arguments": dict(arguments) if isinstance(arguments, dict)
                         else {"<non-object>": repr(arguments)[:80]},
            "ok": ok,
            "outcome": outcome,
        })

    # ------------------------------------------------------------------
    # Cached artefact loaders — each reads one known file, nothing else
    # ------------------------------------------------------------------
    def _load_shap_global(self) -> pd.DataFrame | None:
        if self._shap_global is None:
            try:
                self._shap_global = pd.read_csv(self._shap_global_csv)
            except Exception:
                return None
        return self._shap_global

    def _load_shap_values(self) -> pd.DataFrame | None:
        if self._shap_values is None:
            try:
                self._shap_values = pd.read_parquet(self._shap_values_parquet)
            except Exception:
                return None
        return self._shap_values

    def _load_ablation(self) -> pd.DataFrame | None:
        if self._ablation is None:
            try:
                self._ablation = pd.read_csv(self._ablation_csv)
            except Exception:
                return None
        return self._ablation

    def _load_coverage(self) -> pd.DataFrame | None:
        if self._coverage is None:
            try:
                self._coverage = pd.read_csv(self._coverage_csv)
            except Exception:
                return None
        return self._coverage

    def _load_univariate(self) -> pd.DataFrame | None:
        if self._univariate is None:
            try:
                self._univariate = pd.read_csv(self._univariate_csv)
            except Exception:
                return None
        return self._univariate

    def _load_correlation(self) -> pd.DataFrame | None:
        if self._correlation is None:
            try:
                self._correlation = pd.read_csv(self._correlation_csv)
            except Exception:
                return None
        return self._correlation

    # ------------------------------------------------------------------
    # Dictionary entry shaping
    # ------------------------------------------------------------------
    def _shape_entry(self, entry: dict) -> dict:
        """Drop `populated` entirely when suppressed; touch nothing else."""
        if self.include_populated:
            return dict(entry)
        return {k: v for k, v in entry.items() if k != "populated"}

    # ------------------------------------------------------------------
    # Tool 1 — lookup_feature
    # ------------------------------------------------------------------
    def lookup_feature(self, feature: str) -> dict:
        """Definition of one column. Unknown names are a normal outcome."""
        if not isinstance(feature, str) or not feature.strip():
            return {"found": False,
                    "message": "Provide a feature name as a non-empty string."}
        entry = _dict_lookup(feature.strip())
        if entry is None:
            return {
                "found": False,
                "feature": feature.strip(),
                "message": f"No dictionary entry exists for '{feature.strip()}'. "
                           f"Check the spelling, or use search_data_dictionary "
                           f"to find related columns.",
            }
        return {"found": True, **self._shape_entry(entry)}

    # ------------------------------------------------------------------
    # Tool 2 — search_data_dictionary
    # ------------------------------------------------------------------
    def search_data_dictionary(self, query: str) -> dict:
        """Substring search over column names and definitions."""
        if not isinstance(query, str) or not query.strip():
            return {"query": "", "match_count": 0, "returned": 0,
                    "results": [],
                    "message": "Provide a search term as a non-empty string."}
        q = query.strip()
        hits = _dict_search(q)
        shown = [self._shape_entry(h) for h in hits[:_SEARCH_LIMIT]]
        out = {
            "query": q,
            "match_count": len(hits),
            "returned": len(shown),
            "results": shown,
        }
        if len(hits) > _SEARCH_LIMIT:
            out["message"] = (
                f"{len(hits)} columns matched; the first {_SEARCH_LIMIT} are "
                f"shown. Narrow the search term to see the rest.")
        elif not hits:
            out["message"] = (
                f"No column name or definition contains '{q}'.")
        return out

    # ------------------------------------------------------------------
    # Tool 3 — get_shap_ranking
    # ------------------------------------------------------------------
    def get_shap_ranking(self, top_n: int = 20) -> dict:
        """Features ordered by mean absolute SHAP value."""
        df = self._load_shap_global()
        if df is None:
            return {"message": "The global SHAP ranking is not available."}
        try:
            n = int(top_n)
        except (TypeError, ValueError):
            return {"message": "top_n must be a whole number."}
        n = max(1, min(n, len(df)))
        rows = df.head(n)
        return {
            "total_features": int(len(df)),
            "returned": int(n),
            "note": "mean_abs_shap is in log-odds units, averaged over "
                    "30,000 sampled test rows.",
            "ranking": [
                {"rank": int(r["rank"]),
                 "feature": str(r["feature"]),
                 "mean_abs_shap": float(r["mean_abs_shap"])}
                for _, r in rows.iterrows()
            ],
        }

    # ------------------------------------------------------------------
    # Tool 4 — get_feature_shap_detail
    # ------------------------------------------------------------------
    def get_feature_shap_detail(self, feature: str) -> dict:
        """Summary statistics of one feature's SHAP distribution.

        Returns a distribution summary rather than 30,000 raw values.
        The statistics chosen describe the *shape* of a feature's
        influence, not just its size:

          centre and spread   mean, std, and percentiles from p1 to p99
                              show whether the effect is broad or extreme.
          direction           pct_positive / pct_negative / pct_near_zero
                              show whether the feature pushes both ways or
                              only one, and how often it does nothing.
          concentration       top1pct_abs_share is the fraction of this
                              feature's total absolute attribution carried
                              by its 1% most-attributed rows. A feature
                              acting on nearly every applicant spreads its
                              mass evenly; one that is inert for most rows
                              and decisive for a few concentrates it.
          relative size       share_of_total_abs_shap places the feature
                              against every column combined.
        """
        if not isinstance(feature, str) or not feature.strip():
            return {"found": False,
                    "message": "Provide a feature name as a non-empty string."}
        name = feature.strip()

        df = self._load_shap_values()
        if df is None:
            return {"found": False,
                    "message": "The per-row SHAP values are not available."}
        if name not in df.columns or name == "row_id":
            return {
                "found": False,
                "feature": name,
                "message": f"'{name}' is not one of the model's features, so "
                           f"it has no SHAP values. Use get_shap_ranking to "
                           f"see the feature names.",
            }

        s = df[name].astype("float64")
        a = s.abs()
        total_abs = float(a.sum())
        k = max(1, int(round(len(a) * 0.01)))
        top1 = float(a.nlargest(k).sum())

        gdf = self._load_shap_global()
        rank = None
        if gdf is not None:
            hit = gdf.loc[gdf["feature"] == name, "rank"]
            if len(hit):
                rank = int(hit.iloc[0])

        all_abs_total = None
        if gdf is not None:
            all_abs_total = float(gdf["mean_abs_shap"].sum())

        return {
            "found": True,
            "feature": name,
            "rows": int(len(s)),
            "rank_by_mean_abs_shap": rank,
            "units": "log-odds contribution per row",
            "mean_abs_shap": float(a.mean()),
            "share_of_total_abs_shap": (
                float(a.mean() / all_abs_total) if all_abs_total else None),
            "mean_signed_shap": float(s.mean()),
            "std": float(s.std()),
            "min": float(s.min()),
            "p1": float(s.quantile(0.01)),
            "p5": float(s.quantile(0.05)),
            "q25": float(s.quantile(0.25)),
            "median": float(s.median()),
            "q75": float(s.quantile(0.75)),
            "p95": float(s.quantile(0.95)),
            "p99": float(s.quantile(0.99)),
            "max": float(s.max()),
            "pct_positive": float((s > _NEAR_ZERO).mean() * 100),
            "pct_negative": float((s < -_NEAR_ZERO).mean() * 100),
            "pct_near_zero": float((a <= _NEAR_ZERO).mean() * 100),
            "top1pct_abs_share": (
                float(top1 / total_abs) if total_abs > 0 else 0.0),
        }

    # ------------------------------------------------------------------
    # Tool 5 — get_ablation_result
    # ------------------------------------------------------------------
    def get_ablation_result(self, feature: str) -> dict:
        """Effect of retraining without one feature, where precomputed."""
        if not isinstance(feature, str) or not feature.strip():
            return {"available": False,
                    "message": "Provide a feature name as a non-empty string."}
        name = feature.strip()

        df = self._load_ablation()
        if df is None:
            return {"available": False,
                    "message": "The ablation results are not available."}

        hit = df.loc[df["feature"] == name]
        if not len(hit):
            n_covered = int(len(df))
            gdf = self._load_shap_global()
            known = gdf is not None and (gdf["feature"] == name).any()
            if known:
                # The covered set is exactly the SHAP top-N, so naming its
                # members here would hand over that ranking in one call.
                why = (f"Ablation was precomputed only for the {n_covered} "
                       f"highest-ranked features by mean absolute SHAP, and "
                       f"'{name}' is not among them. Use get_shap_ranking to "
                       f"see which features rank where.")
            else:
                why = (f"'{name}' is not one of the model's features, and "
                       f"ablation was precomputed only for the {n_covered} "
                       f"highest-ranked of those.")
            return {
                "available": False,
                "feature": name,
                "precomputed_count": n_covered,
                "message": why + " No ablation figure can be given for it.",
            }

        r = hit.iloc[0]
        return {
            "available": True,
            "feature": name,
            "note": "Model retrained without this column, then scored on the "
                    "held-out 2017 test set. Deltas are relative to the same "
                    "model trained with every feature.",
            "roc_auc_without_feature": float(r["roc_auc"]),
            "pr_auc_without_feature": float(r["pr_auc"]),
            "delta_roc_auc": float(r["delta_roc_auc"]),
            "delta_pr_auc": float(r["delta_pr_auc"]),
        }

    # ------------------------------------------------------------------
    # Shared helper for the precomputed CSVs, which leave a cell empty
    # wherever a statistic was undefined rather than writing a stand-in.
    # ------------------------------------------------------------------
    @staticmethod
    def _opt_float(value) -> float | None:
        """Empty cell -> None. Never a substituted default."""
        return None if pd.isna(value) else float(value)

    # ------------------------------------------------------------------
    # Tool 6 — get_feature_coverage
    # ------------------------------------------------------------------
    def get_feature_coverage(self, feature: str) -> dict:
        """How populated and how distributed one feature is, per scope."""
        if not isinstance(feature, str) or not feature.strip():
            return {"found": False,
                    "message": "Provide a feature name as a non-empty string."}
        name = feature.strip()

        df = self._load_coverage()
        if df is None:
            return {"found": False,
                    "message": "The coverage profile is not available."}

        rows = df.loc[df["feature"] == name]
        if not len(rows):
            return {
                "found": False,
                "feature": name,
                "message": f"'{name}' is not one of the columns in the "
                           f"model's feature matrix, so it has no coverage "
                           f"profile. Use get_shap_ranking to see the "
                           f"feature names.",
            }

        wanted = list(_SPLIT_SCOPES)
        if self.include_vintage_scopes:
            wanted += list(_VINTAGE_SCOPES)

        by_scope = {str(r["scope"]): r for _, r in rows.iterrows()}
        has_flag = bool(rows.iloc[0]["has_missingness_flag"])

        scopes = []
        for scope in wanted:
            r = by_scope.get(scope)
            if r is None:
                continue
            entry = {
                "scope": scope,
                "n_rows": int(r["n_rows"]),
                "has_missingness_flag": has_flag,
            }
            if has_flag:
                entry["pct_flagged_missing"] = self._opt_float(
                    r["pct_flagged_missing"])
            entry.update({
                "pct_zero": self._opt_float(r["pct_zero"]),
                "pct_at_999": self._opt_float(r["pct_at_999"]),
                "n_unique": int(r["n_unique"]),
                "mean": self._opt_float(r["mean"]),
                "std": self._opt_float(r["std"]),
                "p50": self._opt_float(r["p50"]),
            })
            scopes.append(entry)

        out = {
            "found": True,
            "feature": name,
            "has_missingness_flag": has_flag,
            "note": "pct_zero and pct_at_999 count rows holding exactly that "
                    "value. std is the sample standard deviation and p50 the "
                    "median, both within the scope.",
            "scopes": scopes,
        }
        if not has_flag:
            out["missingness_flag_note"] = (
                f"'{name}' has no companion _was_missing column, so no "
                f"flagged-missing percentage exists for it and none is "
                f"reported.")
        return out

    # ------------------------------------------------------------------
    # Tool 7 — get_feature_target_association
    # ------------------------------------------------------------------
    def get_feature_target_association(self, feature: str) -> dict:
        """One feature's standalone association with the outcome.

        Every figure here comes from that one column and the outcome, with
        no other column involved and no model fitted.
        """
        if not isinstance(feature, str) or not feature.strip():
            return {"found": False,
                    "message": "Provide a feature name as a non-empty string."}
        name = feature.strip()

        df = self._load_univariate()
        if df is None:
            return {"found": False,
                    "message": "The univariate association figures are not "
                               "available."}

        hit = df.loc[df["feature"] == name]
        if not len(hit):
            return {
                "found": False,
                "feature": name,
                "message": f"'{name}' is not one of the columns in the "
                           f"model's feature matrix, so it has no univariate "
                           f"association figures. Use get_shap_ranking to see "
                           f"the feature names.",
            }

        r = hit.iloc[0]
        # Governed by include_vintage_scopes — see the block above
        # _SPLIT_SCOPES for what the switch covers and what it does not.
        auc_fields = ["auc_train", "auc_test"]
        if self.include_vintage_scopes:
            auc_fields += ["auc_2014", "auc_2015", "auc_2016"]
        scope_of = {"auc_train": "the training split",
                    "auc_test": "the test split",
                    "auc_2014": "2014", "auc_2015": "2015",
                    "auc_2016": "2016"}

        out = {
            "found": True,
            "feature": name,
            "reading": "Each AUC is rank-based, computed from the "
                       "Mann-Whitney U statistic using the raw feature value "
                       "as the score. It is not corrected for direction: 0.5 "
                       "means the feature does not order the outcome, above "
                       "0.5 means it orders it in the same direction, and "
                       "below 0.5 means it orders it in reverse.",
        }
        for f in auc_fields:
            out[f] = self._opt_float(r[f])
        out["point_biserial_test"] = self._opt_float(r["point_biserial_test"])
        out["n_unique_test"] = int(r["n_unique_test"])
        out["is_constant_test"] = bool(r["is_constant_test"])

        # Only over the fields actually reported, so the note cannot name
        # a vintage the caller was not given.
        empty = [scope_of[f] for f in auc_fields if out[f] is None]
        if empty:
            out["undefined_note"] = (
                f"'{name}' takes a single value within "
                f"{', '.join(empty)}, so no association could be computed "
                f"there and those figures are null rather than substituted.")
        return out

    # ------------------------------------------------------------------
    # Tool 8 — get_correlated_features
    # ------------------------------------------------------------------
    def get_correlated_features(self, feature: str,
                                top_k: int = _DEFAULT_TOP_K) -> dict:
        """The features most linearly related to one feature, on test."""
        if not isinstance(feature, str) or not feature.strip():
            return {"available": False,
                    "message": "Provide a feature name as a non-empty string."}
        name = feature.strip()

        try:
            k = int(top_k)
        except (TypeError, ValueError):
            return {"available": False,
                    "message": "top_k must be a whole number."}

        clamp_note = None
        if k > _MAX_TOP_K:
            clamp_note = (f"{k} neighbours were requested; only "
                          f"{_MAX_TOP_K} were precomputed per feature, so "
                          f"{_MAX_TOP_K} are returned.")
        k = max(1, min(k, _MAX_TOP_K))

        df = self._load_correlation()
        if df is None:
            return {"available": False,
                    "message": "The correlation neighbours are not available."}

        rows = df.loc[df["feature"] == name].sort_values("rank")
        if not len(rows):
            return {
                "available": False,
                "feature": name,
                "message": f"'{name}' is not one of the columns in the "
                           f"model's feature matrix, so it has no correlation "
                           f"neighbours. Use get_shap_ranking to see the "
                           f"feature names.",
            }

        if rows["neighbour"].isna().all():
            return {
                "available": False,
                "feature": name,
                "message": f"Correlations are undefined for '{name}': it "
                           f"holds a single value throughout the evaluation "
                           f"split, so it has no variation to relate to any "
                           f"other column. No neighbours can be reported.",
            }

        rows = rows.loc[rows["neighbour"].notna()].head(k)
        out = {
            "available": True,
            "feature": name,
            "returned": int(len(rows)),
            "precomputed_count": _MAX_TOP_K,
            "note": "Pearson correlation between the two columns over the "
                    "full held-out test set, ordered by absolute value. "
                    "pearson_r keeps its sign.",
            "neighbours": [
                {"rank": int(r["rank"]),
                 "neighbour": str(r["neighbour"]),
                 "pearson_r": float(r["pearson_r"]),
                 "abs_pearson_r": float(r["abs_pearson_r"])}
                for _, r in rows.iterrows()
            ],
        }
        if clamp_note:
            out["message"] = clamp_note
        return out

    # ------------------------------------------------------------------
    # Dispatch — the agent's only entry point
    # ------------------------------------------------------------------
    def dispatch(self, name: str, arguments: dict | None = None) -> dict:
        """Run one tool by name. Never raises; never leaks internals."""
        handlers = {
            "lookup_feature": self.lookup_feature,
            "search_data_dictionary": self.search_data_dictionary,
            "get_shap_ranking": self.get_shap_ranking,
            "get_feature_shap_detail": self.get_feature_shap_detail,
            "get_ablation_result": self.get_ablation_result,
            "get_feature_coverage": self.get_feature_coverage,
            "get_feature_target_association":
                self.get_feature_target_association,
            "get_correlated_features": self.get_correlated_features,
        }
        fn = handlers.get(name)
        if fn is None:
            self._record(name, arguments or {}, False, "unknown_tool")
            return {"message": f"There is no tool called '{name}'. Available "
                               f"tools: {', '.join(sorted(handlers))}."}
        args = arguments or {}
        if not isinstance(args, dict):
            self._record(name, args, False, "bad_arguments")
            return {"message": "Tool arguments must be supplied as an object."}
        allowed = _SCHEMA_ARGS[name]
        unexpected = [k for k in args if k not in allowed]
        if unexpected:
            self._record(name, args, False, "unexpected_argument")
            return {"message": f"'{name}' does not accept "
                               f"{', '.join(sorted(unexpected))}. It accepts: "
                               f"{', '.join(allowed)}."}
        try:
            result = fn(**args)
        except TypeError:
            self._record(name, args, False, "bad_arguments")
            return {"message": f"'{name}' was called with the wrong arguments. "
                               f"It accepts: {', '.join(allowed)}."}
        except Exception:
            # Deliberately opaque: no traceback, no path, no module name.
            self._record(name, args, False, "failed")
            return {"message": f"'{name}' could not be completed."}
        self._record(name, args, True, self._outcome(name, result))
        return result


# ----------------------------------------------------------------------
# Anthropic tool definitions — pass straight to call_llm(tools=...)
# ----------------------------------------------------------------------
TOOL_SCHEMAS = [
    {
        "name": "lookup_feature",
        "description": (
            "Look up one column by its exact name. Returns what the column "
            "holds and where its value comes from. The dictionary documents "
            "more columns than the model reads, so a name may be documented "
            "here and still not be one of the model's inputs. Returns "
            "found=false if the name is not documented at all."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature": {
                    "type": "string",
                    "description": "Exact column name, e.g. 'revol_util'.",
                },
            },
            "required": ["feature"],
        },
    },
    {
        "name": "search_data_dictionary",
        "description": (
            "Find columns related to a search term. Names are matched "
            "literally; beyond that, results are the entries closest to the "
            "term by meaning, so a result may be unrelated to what was asked "
            "and its presence in the list is not on its own evidence that "
            "the dictionary holds an answer. Covers the whole dictionary, "
            "which documents more columns than the model reads. Use it to "
            "explore related columns when the exact name is not known. At "
            f"most {_SEARCH_LIMIT} matches are returned per call."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Substring to search for, e.g. 'balance'.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_shap_ranking",
        "description": (
            "List the model's features ordered by mean absolute SHAP value "
            "over 30,000 sampled test rows, highest first. The result "
            "reports how many features there are in total."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "top_n": {
                    "type": "integer",
                    "description": "How many features to return. Values above the total are clamped to it.",
                },
            },
            "required": ["top_n"],
        },
    },
    {
        "name": "get_feature_shap_detail",
        "description": (
            "Summary statistics for one feature's SHAP distribution across "
            "30,000 sampled test rows: mean, spread, percentiles, how often "
            "the feature pushes the prediction up, down, or not at all, and "
            "how concentrated its attribution is across rows. Covers exactly "
            "the columns the model reads and nothing else: a column the "
            "dictionary documents but the model does not read has no SHAP "
            "values, and returns found=false. get_shap_ranking lists the "
            "names this tool accepts."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature": {
                    "type": "string",
                    "description": "Exact name of one of the model's features.",
                },
            },
            "required": ["feature"],
        },
    },
    {
        "name": "get_ablation_result",
        "description": (
            "Report how the model scores on the held-out test set when it is "
            "retrained without one feature. Retraining is expensive, so this "
            "was precomputed only for the 20 features with the highest mean "
            "absolute SHAP value; every other column, whether or not the "
            "model reads it, returns available=false. get_shap_ranking shows "
            "which features those 20 are."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature": {
                    "type": "string",
                    "description": "Exact name of one of the model's features.",
                },
            },
            "required": ["feature"],
        },
    },
    {
        "name": "get_feature_coverage",
        "description": (
            "Report how populated and how distributed one feature is, as a "
            "list of scopes. Each scope gives the row count, the percentage "
            "of rows holding exactly zero and exactly 999, the number of "
            "distinct values, and the mean, standard deviation and median. "
            "Where the feature has a companion _was_missing column, the "
            "percentage of rows it marks is included; where it has none, no "
            "such percentage is reported. Covers exactly the columns the "
            "model reads; any other name returns found=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature": {
                    "type": "string",
                    "description": "Exact name of one of the model's features.",
                },
            },
            "required": ["feature"],
        },
    },
    {
        "name": "get_feature_target_association",
        "description": (
            "Report how well one feature on its own orders the outcome, with "
            "no other column involved and no model fitted. Returns rank-based "
            "ROC-AUC on the training split, on the test split, and within "
            "each year of the training period, plus the Pearson correlation "
            "with the outcome on test. A figure is null where the feature "
            "holds a single value in that scope. Covers exactly the columns "
            "the model reads; any other name returns found=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature": {
                    "type": "string",
                    "description": "Exact name of one of the model's features.",
                },
            },
            "required": ["feature"],
        },
    },
    {
        "name": "get_correlated_features",
        "description": (
            "List the features most strongly correlated with one feature, "
            "measured by Pearson correlation over the full held-out test set "
            "and ordered by absolute value, sign retained. Neighbours were "
            f"precomputed {_MAX_TOP_K} deep per feature, so top_k above "
            f"{_MAX_TOP_K} returns {_MAX_TOP_K} with a note rather than an "
            "error. A feature that holds a single value on the test set has "
            "no correlations and returns available=false."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "feature": {
                    "type": "string",
                    "description": "Exact name of one of the model's features.",
                },
                "top_k": {
                    "type": "integer",
                    "description": (
                        f"How many neighbours to return. Defaults to "
                        f"{_DEFAULT_TOP_K}, maximum {_MAX_TOP_K}."),
                },
            },
            "required": ["feature"],
        },
    },
]

_SCHEMA_ARGS = {
    s["name"]: tuple(s["input_schema"]["properties"].keys())
    for s in TOOL_SCHEMAS
}
