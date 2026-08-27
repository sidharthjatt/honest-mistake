"""tools.py — Honest Mistake, Layer 2 tool layer.

The agent's entire view of the model and dataset passes through the five
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
"""

from pathlib import Path

import pandas as pd

from agent.data_dictionary import lookup as _dict_lookup
from agent.data_dictionary import search as _dict_search

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_CACHE = _PROJECT_ROOT / "outputs" / "agent_cache"
_SHAP_GLOBAL_CSV = _CACHE / "shap_global.csv"
_SHAP_VALUES_PARQUET = _CACHE / "shap_values.parquet"
_ABLATION_CSV = _CACHE / "ablation_cache.csv"

TOOL_LAYER_VERSION = "1.0"

# search() can otherwise be used to dump the whole dictionary in one call.
_SEARCH_LIMIT = 25

# |SHAP| below this counts as "no contribution" for this row.
_NEAR_ZERO = 1e-3


class ToolLayer:
    """The five tools, bound to one fixed configuration.

    The `populated` suppression switch is a constructor argument, so it is
    fixed for the lifetime of the object and is not a parameter of any
    tool. The agent calls tools only through `dispatch`, which forwards
    only the arguments declared in the published schemas — none of which
    include the switch. The agent therefore cannot read, set, or vary it.

    Chosen over a module-level global or a runtime patch because the
    binding is explicit and per-instance: two configurations can exist
    side by side in one process (useful when running the A/B comparison),
    and `run_config()` stamps every run with the setting that produced it.
    """

    def __init__(self, include_populated: bool = True,
                 cache_dir: Path | None = None):
        self.include_populated = bool(include_populated)
        # A parallel cache lets a canary variant be audited without
        # overwriting Layer 1's artefacts. The directory is part of the
        # run's identity, so it is stamped into config_id.
        self.cache_dir = Path(cache_dir) if cache_dir else _CACHE
        self._shap_global_csv = self.cache_dir / "shap_global.csv"
        self._shap_values_parquet = self.cache_dir / "shap_values.parquet"
        self._ablation_csv = self.cache_dir / "ablation_cache.csv"
        self._shap_global: pd.DataFrame | None = None
        self._shap_values: pd.DataFrame | None = None
        self._ablation: pd.DataFrame | None = None
        self._calls: list[dict] = []

    # ------------------------------------------------------------------
    # Run identification
    # ------------------------------------------------------------------
    def run_config(self) -> dict:
        """Configuration stamp for logging. Not exposed as a tool."""
        state = "included" if self.include_populated else "suppressed"
        variant = "canary" if self.cache_dir != _CACHE else "layer1"
        return {
            "tool_layer_version": TOOL_LAYER_VERSION,
            "dictionary_populated_field": state,
            "artefact_variant": variant,
            "cache_dir": self.cache_dir.name,
            "config_id": (f"toolsv{TOOL_LAYER_VERSION}-populated-{state}"
                          f"-{variant}"),
        }

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
        if name in ("lookup_feature", "get_feature_shap_detail"):
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
            "Find columns whose name or definition contains a search term. "
            "Matching is plain case-insensitive substring matching against "
            "those two fields only; other fields of an entry are returned "
            "but not searched. Covers the whole dictionary, which documents "
            "more columns than the model reads. Use it to explore related "
            "columns when the exact name is not known. At most "
            f"{_SEARCH_LIMIT} matches are returned per call."
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
]

_SCHEMA_ARGS = {
    s["name"]: tuple(s["input_schema"]["properties"].keys())
    for s in TOOL_SCHEMAS
}
