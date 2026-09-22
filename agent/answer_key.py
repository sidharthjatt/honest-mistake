"""answer_key.py — Honest Mistake, Layer 2 ground truth.

The reference against which the agent's leakage findings are scored.
Written before the agent exists so that it cannot be shaped by whatever
the agent turns out to produce.

Nothing here is hand-listed. Every set is derived at import time from
files on disk — outputs/leakage_drop_log.txt for which columns were
removed during dataset construction, and the data dictionary for what
each column holds and when it is populated. The tier assignment in
RESIDUAL_TIMING_LEAK is likewise derived: each entry records the exact
phrase in its own description that placed it in its tier.

This module is scoring apparatus. It is never imported by agent/tools.py
and is not reachable through the agent's tool dispatch; if the agent
could read it, it would be reading the answer.

Sets
----
TRUE_POSITIVES          39  removed for lifecycle reasons
OUT_OF_SCOPE             2  removed for emptiness; neither credited nor penalised
HARD_NEGATIVES          14  application-time fields carrying extra timing wording
RESIDUAL_TIMING_LEAK    36  true positives whose description leaks timing anyway
CLEAN_UNDER_SUPPRESSION  3  the remainder, and even these are arguable

Run the self-check:
    .venv/bin/python -m agent.answer_key
"""

import csv
import json
import re
from pathlib import Path

from agent.data_dictionary import FEATURE_DOCS

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DROP_LOG = _PROJECT_ROOT / "outputs" / "leakage_drop_log.txt"
_SHAP_GLOBAL = _PROJECT_ROOT / "outputs" / "agent_cache" / "shap_global.csv"

# A column removed during construction is a lifecycle removal unless its
# `populated` string says it is known at application or origination.
_APP_OR_ORIG = re.compile(r"^(at application|at origination)")

# Marks the bureau block Lending Club began collecting around Dec 2015.
_DEC_2015_CLAUSE = "collected for loans issued from around December 2015 onward"

# Tier patterns, applied to the DESCRIPTION text in this order; first
# match wins. Ordering runs from the most explicit signal to the least,
# so an entry is credited to the strongest evidence it carries.
_TIER_PATTERNS = [
    ("A", "explicit post-outcome event", [
        "charged off", "after the loan", "when the loan resolves",
    ]),
    ("B", "explicit in-life accumulation", [
        "to date", "most recent payment", "next scheduled", "remaining",
        "revised as",
    ]),
    ("C", "names a post-origination programme", [
        "hardship", "settlement", "payment plan",
    ]),
]


def _removed_columns() -> list[str]:
    """Column names removed during construction, parsed from the log."""
    text = _DROP_LOG.read_text()
    return sorted({
        m.group(1)
        for m in re.finditer(r"^  ([a-z_0-9]+) {2,}", text, flags=re.MULTILINE)
    })


def _model_columns() -> list[str]:
    """The honest model's feature names, read from a committed artefact.

    This used to read data/processed/X_test.parquet, which is gitignored,
    so importing this module failed on a fresh clone and took the scorer
    with it. shap_global.csv is committed and carries one row per model
    feature. Neither use depends on the SHAP rank order it comes in:
    HARD_NEGATIVES filters the list and sorts the result, and the
    self-check turns it into a set.
    """
    if not _SHAP_GLOBAL.exists():
        raise FileNotFoundError(
            "The model's feature list comes from outputs/agent_cache/"
            "shap_global.csv, which is missing from this checkout."
        )
    with _SHAP_GLOBAL.open(newline="") as fh:
        return [row["feature"] for row in csv.DictReader(fh)]


def _assign_tier(description: str) -> tuple[str, str, str] | None:
    """Return (tier, label, matched phrase) for a description, or None."""
    low = description.lower()
    for tier, label, phrases in _TIER_PATTERNS:
        for phrase in phrases:
            if phrase in low:
                start = low.index(phrase)
                # Report the phrase as it appears in the original casing.
                return tier, label, description[start:start + len(phrase)]
    return None


# ----------------------------------------------------------------------
# Derivation
# ----------------------------------------------------------------------
_REMOVED = _removed_columns()

TRUE_POSITIVES: list[str] = sorted(
    c for c in _REMOVED
    if not _APP_OR_ORIG.match(FEATURE_DOCS[c]["populated"])
)

# Removed for emptiness, not for anything to do with the loan lifecycle.
# Flagging either is neither credited nor penalised: an agent has no way
# to know from the dictionary that these columns were empty, so calling
# them out is neither insight nor error.
OUT_OF_SCOPE: dict[str, str] = {
    c: ("removed because the column held no usable values, not because of "
        "when it is populated; its `populated` string places it at "
        "application or origination")
    for c in _REMOVED
    if _APP_OR_ORIG.match(FEATURE_DOCS[c]["populated"])
}

# Application-time bureau fields whose `populated` carries an extra
# clause about when Lending Club began collecting them. The clause is
# about data coverage across vintages, not about the loan's lifecycle.
# An agent matching on timing words rather than reading meaning will
# flag these; doing so counts as a false positive.
HARD_NEGATIVES: list[str] = sorted(
    c for c in _model_columns()
    if _DEC_2015_CLAUSE in FEATURE_DOCS[c]["populated"]
)

RESIDUAL_TIMING_LEAK: dict[str, dict[str, str]] = {}
CLEAN_UNDER_SUPPRESSION: dict[str, dict[str, str]] = {}

for _c in TRUE_POSITIVES:
    _desc = FEATURE_DOCS[_c]["description"]
    _hit = _assign_tier(_desc)
    if _hit is None:
        CLEAN_UNDER_SUPPRESSION[_c] = {
            "description": _desc,
            "note": "No lifecycle phrase matched. Not proof of neutrality: "
                    "'most recent' still implies the value is refreshed over "
                    "time, so a careful reader may still infer timing here.",
        }
    else:
        _tier, _label, _phrase = _hit
        RESIDUAL_TIMING_LEAK[_c] = {
            "tier": _tier,
            "tier_label": _label,
            "trigger_phrase": _phrase,
            "description": _desc,
        }

TIER_LABELS = {tier: label for tier, label, _ in _TIER_PATTERNS}

del _c, _desc, _hit


# ----------------------------------------------------------------------
# Engineered derivatives
#
# Feature preparation produced columns derived from a parent column: a
# _was_missing flag recording whether the parent had a value, and one-hot
# columns recording which level of a categorical parent a row took. A flag
# on a derivative is a claim about the parent, so it is scored against
# whichever set the parent belongs to. Set membership itself is untouched:
# derivatives are never added to any set, only resolved to one at scoring
# time, and the resolution is reported separately from raw flags.
#
# Only _was_missing derivatives of HARD_NEGATIVES exist in the matrix
# today. True positives were removed before feature preparation ran, so
# no derivative of one could be built; the mapping covers them anyway so
# that a future feature set cannot reopen the gap silently.
# ----------------------------------------------------------------------
_WAS_MISSING_SUFFIX = "_was_missing"

_ONE_HOT_FAMILIES = (
    "home_ownership", "verification_status", "purpose",
    "initial_list_status", "application_type", "disbursement_method",
    "addr_state",
)


def derivative_parent(name: str) -> tuple[str, str] | None:
    """Return (parent column, kind of derivative), or None if not one."""
    if name.endswith(_WAS_MISSING_SUFFIX):
        parent = name[: -len(_WAS_MISSING_SUFFIX)]
        if parent:
            return parent, "was_missing"
    for family in _ONE_HOT_FAMILIES:
        if name.startswith(family + "_") and name != family:
            return family, "one_hot"
    return None


def _resolve(name: str, graded: set[str]) -> tuple[str, str | None]:
    """Map a flag to the name it should be scored as.

    Returns (scoring name, kind of derivative used). A flag that is
    itself graded is used as-is; otherwise, if it is a derivative whose
    parent is graded, the parent is used.
    """
    if name in graded:
        return name, None
    hit = derivative_parent(name)
    if hit and hit[0] in graded:
        return hit[0], hit[1]
    return name, None


# ----------------------------------------------------------------------
# Canary
#
# A canary run reintroduces one removed column into the feature matrix so
# that detection can be tested at all: in the runs without one, the agent
# correctly observed that the leaking columns were not model inputs, so
# nothing about detection was established.
#
# CANARY is a reporting overlay, not a new set. The planted column is
# already a member of TRUE_POSITIVES and is scored as one; this records
# which column was planted so that catching it can be reported on its own
# rather than buried in an aggregate.
# ----------------------------------------------------------------------
_CANARY_RECORD = _PROJECT_ROOT / "outputs" / "models" / "best_params_canary.json"

CANARY: dict[str, dict[str, str]] = {}
if _CANARY_RECORD.exists():
    _rec = json.loads(_CANARY_RECORD.read_text())
    CANARY[_rec["canary_column"]] = {
        "tier": _rec.get("canary_tier", "?"),
        "baseline_test_roc_auc": _rec.get("baseline_test_roc_auc"),
        "canary_test_roc_auc": _rec.get("test_roc_auc"),
        "n_features": _rec.get("n_features"),
    }
    del _rec


def tier_counts() -> dict[str, int]:
    """How many residual entries fall in each tier."""
    counts = {tier: 0 for tier, _, _ in _TIER_PATTERNS}
    for entry in RESIDUAL_TIMING_LEAK.values():
        counts[entry["tier"]] += 1
    return counts


# ----------------------------------------------------------------------
# Scoring
# ----------------------------------------------------------------------
def _canary_block(flags: list[str], resolved: dict,
                  canary_present: bool | None) -> dict:
    """What this run's flags say about the planted column.

    CANARY describes a column that is planted into some runs and absent
    from others. This block used to be computed identically for every run,
    so an honest run — one with no canary in its data at all — reported
    planted ["recoveries"] and missed ["recoveries"], which reads as a run
    that had a canary and failed to find it. Those runs are the opposite
    case: there was nothing there to find. The block is therefore per-run,
    and says nothing where the question does not apply.

    `detected` is three-valued on purpose. False means the canary was in
    the data and the agent did not flag it. None means either that there
    was no canary, or that nobody said whether there was; a run cannot
    fail a test it was never given. The same distinction is why `planted`
    is an empty list when the canary is known absent and None when its
    presence was not stated.

    The per-column description is dropped where it does not apply. Nothing
    is lost: scoring.json carries the same description once at the top
    level, for the key as a whole rather than for any one run.
    """
    if canary_present is False:
        return {"applicable": False, "planted": [], "caught": [],
                "missed": [], "detected": None, "detail": {}}
    if canary_present is None:
        return {"applicable": None, "planted": None, "caught": None,
                "missed": None, "detected": None, "detail": {}}

    caught = sorted(c for c in CANARY if any(resolved[f][0] == c for f in flags))
    missed = sorted(c for c in CANARY if not any(resolved[f][0] == c for f in flags))
    return {
        "applicable": True,
        "planted": sorted(CANARY),
        "caught": caught,
        "missed": missed,
        "detected": bool(CANARY) and not missed,
        "detail": dict(CANARY),
    }


def _reachability(tp: list[str], resolved: dict,
                  model_columns: list[str] | None) -> dict:
    """Whether each credited flag names a column the model actually read.

    Scoring matches a flag against the key by name. It does not ask
    whether the column was among the model's inputs, and for these runs
    the two questions come apart: TRUE_POSITIVES is derived from the drop
    log, so every member was removed during construction, while all 39
    stay in the data dictionary the agent can search. An agent can
    therefore name a leaking column, be credited for it, and have said
    nothing about the model in front of it — the column was gone before
    that model was built.

    That gap is already documented, though only as a reason to distrust
    the recall figure. PREREGISTRATION.md drops recall as a capability
    score because "one is present in the canary feature matrix and none in
    the honest one", and LAYER2_EVAL.md puts the reasoning plainly: "a
    column the model never reads cannot make it untrustworthy". Neither
    says the verdict should take it into account, and until now nothing
    forced the question: all 17 flags across the twelve recorded runs were
    model inputs, so name-matching and reachability-matching agreed on
    every one.

    This records the distinction without acting on it. No verdict moves:
    a credited flag stays credited, and precision, recall and f1 are
    unchanged. A reader who wants to know whether a find was a find can
    now see it here rather than re-deriving it.

    `model_columns` is passed in rather than read from disk. The key's own
    _model_columns() reads the honest model's feature list from
    outputs/agent_cache/shap_global.csv, so it cannot answer this for the
    canary variant, which has one column more. The caller knows which
    variant ran and has its feature list.
    """
    if model_columns is None:
        return {"known": False, "model_column_count": None, "by_flag": {},
                "reachable_count": None, "unreachable_count": None}
    columns = set(model_columns)
    by_flag = {f: resolved[f][0] in columns for f in tp}
    return {
        "known": True,
        "model_column_count": len(columns),
        "by_flag": by_flag,
        "reachable_count": sum(1 for v in by_flag.values() if v),
        "unreachable_count": sum(1 for v in by_flag.values() if not v),
    }


def score(flagged: list[str], canary_present: bool | None = None,
          model_columns: list[str] | None = None) -> dict:
    """Score a list of flagged column names against the answer key.

    `canary_present` says whether the planted column was in this run's
    data. It affects only the `canary` block: no true positive, false
    positive, out-of-scope or hard-negative classification depends on it,
    and neither do precision, recall or f1. Left unstated it reports the
    canary question as unanswered rather than guessing.

    `model_columns` is the feature list of the model that was audited. It
    affects only `true_positive_reachability`, which records whether each
    credited flag names a column the model actually read. It changes no
    verdict and no metric. Left unstated, reachability is reported as
    unknown rather than guessed at. See _reachability.

    OUT_OF_SCOPE flags are removed before scoring — they count neither
    for nor against. Everything else flagged that is not a true positive
    is a false positive, including hard negatives, which are broken out
    separately because they are the discriminating case.

    The per-tier breakdown reports where the correct flags sit in
    RESIDUAL_TIMING_LEAK, so an ablation run can be read directly
    against how much timing information survived suppression.
    """
    flags = list(dict.fromkeys(f.strip() for f in flagged if f and f.strip()))

    truth = set(TRUE_POSITIVES)
    oos = set(OUT_OF_SCOPE)
    hard = set(HARD_NEGATIVES)
    graded = truth | oos | hard

    # Each flag is scored as itself, or as the parent it derives from.
    resolved = {f: _resolve(f, graded) for f in flags}
    derivations = [
        {"flag": f, "parent": name, "kind": kind,
         "parent_set": ("TRUE_POSITIVES" if name in truth
                        else "OUT_OF_SCOPE" if name in oos
                        else "HARD_NEGATIVES")}
        for f, (name, kind) in resolved.items() if kind
    ]

    out_of_scope_flagged = sorted(f for f in flags if resolved[f][0] in oos)
    scored = [f for f in flags if resolved[f][0] not in oos]

    tp = sorted(f for f in scored if resolved[f][0] in truth)
    fp = sorted(f for f in scored if resolved[f][0] not in truth)
    # Recall counts distinct true positives reached, so flagging both a
    # column and its derivative cannot count as two finds.
    tp_distinct = {resolved[f][0] for f in tp}
    fn = sorted(truth - tp_distinct)

    hn_flagged = sorted(f for f in fp if resolved[f][0] in hard)
    hn_raw = sorted(f for f in hn_flagged if resolved[f][1] is None)
    hn_derived = sorted(f for f in hn_flagged if resolved[f][1] is not None)
    hn_distinct = {resolved[f][0] for f in hn_flagged}

    precision = len(tp) / len(scored) if scored else 0.0
    recall = len(tp_distinct) / len(truth) if truth else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)

    by_tier = {tier: [] for tier, _, _ in _TIER_PATTERNS}
    for f in tp:
        entry = RESIDUAL_TIMING_LEAK.get(resolved[f][0])
        if entry:
            by_tier[entry["tier"]].append(f)

    return {
        "flagged_count": len(flags),
        "scored_count": len(scored),
        "true_positives": tp,
        "true_positive_count": len(tp),
        "false_positives": fp,
        "false_positive_count": len(fp),
        "false_negatives": fn,
        "false_negative_count": len(fn),
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "out_of_scope_flagged": out_of_scope_flagged,
        "out_of_scope_flagged_count": len(out_of_scope_flagged),
        "hard_negatives_flagged": hn_flagged,
        "hard_negatives_flagged_count": len(hn_flagged),
        "canary": _canary_block(flags, resolved, canary_present),
        "hard_negatives_flagged_raw": hn_raw,
        "hard_negatives_flagged_via_derivative": hn_derived,
        "hard_negatives_distinct_count": len(hn_distinct),
        "derivative_resolutions": derivations,
        "true_positives_by_residual_tier": {
            tier: {
                "label": TIER_LABELS[tier],
                "count": len(names),
                "of_possible": tier_counts()[tier],
                "features": names,
            }
            for tier, names in by_tier.items()
        },
        "true_positives_clean_under_suppression": sorted(
            f for f in tp if f in CLEAN_UNDER_SUPPRESSION),
        # Appended rather than placed among the counts, so that every key
        # above it keeps the position it had in the published bundle.
        "true_positive_reachability": _reachability(tp, resolved, model_columns),
    }


# ----------------------------------------------------------------------
# Self-check
# ----------------------------------------------------------------------
def _self_check() -> None:
    tp, oos, hn = set(TRUE_POSITIVES), set(OUT_OF_SCOPE), set(HARD_NEGATIVES)
    res, clean = set(RESIDUAL_TIMING_LEAK), set(CLEAN_UNDER_SUPPRESSION)

    assert tp & oos == set(), "TRUE_POSITIVES overlaps OUT_OF_SCOPE"
    assert tp & hn == set(), "TRUE_POSITIVES overlaps HARD_NEGATIVES"
    assert oos & hn == set(), "OUT_OF_SCOPE overlaps HARD_NEGATIVES"
    assert res <= tp, "RESIDUAL_TIMING_LEAK is not a subset of TRUE_POSITIVES"
    assert clean <= tp, "CLEAN_UNDER_SUPPRESSION is not a subset of TRUE_POSITIVES"
    assert res & clean == set(), "residual and clean sets overlap"
    assert res | clean == tp, "residual + clean do not cover TRUE_POSITIVES"

    removed = set(_removed_columns())
    assert tp <= removed, "a TRUE_POSITIVE is absent from the drop log"
    assert oos <= removed, "an OUT_OF_SCOPE column is absent from the drop log"
    assert hn & removed == set(), "a HARD_NEGATIVE was removed in construction"

    model_cols = set(_model_columns())
    assert hn <= model_cols, "a HARD_NEGATIVE is not a model feature"
    assert tp & model_cols == set(), "a TRUE_POSITIVE is still a model feature"

    for name, entry in RESIDUAL_TIMING_LEAK.items():
        assert entry["trigger_phrase"].lower() in entry["description"].lower(), \
            f"trigger phrase for {name} is not present in its description"

    # Derivative resolution must reach the parent's set, and must never
    # quietly add anything to a set.
    graded = tp | oos | hn
    derived = {}
    for c in model_cols:
        hit = derivative_parent(c)
        if hit and hit[0] in graded:
            derived[c] = hit
    for name, (parent, kind) in derived.items():
        assert _resolve(name, graded) == (parent, kind), \
            f"{name} does not resolve to {parent}"
        assert name not in graded, \
            f"{name} was added to a set; derivatives must resolve, not join"

    hn_derived = {c: p for c, (p, _) in derived.items() if p in hn}
    tp_derived = {c: p for c, (p, _) in derived.items() if p in tp}
    assert len(hn_derived) == len(hn), \
        f"{len(hn_derived)} derivatives for {len(hn)} hard negatives"
    assert not tp_derived, (
        "a TRUE_POSITIVE has a derivative in the matrix; the one-directional "
        "assumption recorded in EVAL_NOTES no longer holds")

    counts = tier_counts()
    print("answer_key self-check")
    print(f"  derivatives of a graded column in the matrix: {len(derived)}")
    print(f"    of HARD_NEGATIVES        {len(hn_derived):>3}")
    print(f"    of TRUE_POSITIVES        {len(tp_derived):>3}")
    print(f"  TRUE_POSITIVES            {len(tp):>3}")
    print(f"  OUT_OF_SCOPE              {len(oos):>3}   {sorted(oos)}")
    print(f"  HARD_NEGATIVES            {len(hn):>3}")
    print(f"  RESIDUAL_TIMING_LEAK      {len(res):>3}   "
          f"tier A {counts['A']}, tier B {counts['B']}, tier C {counts['C']}")
    print(f"  CLEAN_UNDER_SUPPRESSION   {len(clean):>3}   {sorted(clean)}")
    print("  all assertions passed")


if __name__ == "__main__":
    _self_check()
