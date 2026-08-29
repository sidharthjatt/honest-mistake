"""build_agent_cache_v2.py — Honest Mistake project.

Precompute three artefacts for the Layer 2 agent cache:

    coverage_profile.csv    per-feature descriptive profile, by scope
    univariate_assoc.csv    per-feature single-variable association with the target
    correlation_topk.csv    per-feature 15 nearest neighbours by |Pearson r| on test

Nothing here fits a model, resamples, or recomputes SHAP. Everything is a
descriptive statistic over the finished feature matrices, so the agent can
read a file instead of touching data/.

Run:
    .venv/bin/python scripts/build_agent_cache_v2.py --variant honest
    .venv/bin/python scripts/build_agent_cache_v2.py --variant canary
"""

import argparse
import sys
import time
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import pearsonr, rankdata

PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "data" / "processed"
OUTPUTS = PROJECT_ROOT / "outputs"

TARGET = "is_default"
VINTAGE_COL = "issue_year"
SENTINEL = 999
TOP_K = 15
FLAG_SUFFIX = "_was_missing"

VARIANTS = {
    "honest": {
        "x_train": "X_train.parquet",
        "x_test": "X_test.parquet",
        "out_dir": OUTPUTS / "agent_cache",
    },
    "canary": {
        "x_train": "X_train_canary.parquet",
        "x_test": "X_test_canary.parquet",
        "out_dir": OUTPUTS / "agent_cache_canary",
    },
}

# Preferred alignment probes. Each is checked for eligibility before use;
# 04_features.py applies no scaling, but it does median-impute, and an
# imputed column no longer matches the pre-FE table row for row.
PREFERRED_PROBES = ["loan_amnt", "annual_inc", "dti", "revol_bal"]
MIN_PROBES = 4
N_PROBES = 6


class GateFailure(Exception):
    """Raised when the positional alignment between X_* and the pre-FE table
    cannot be demonstrated. Never repaired, never worked around."""


def rule(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


# ----------------------------------------------------------------------
# Step 0 — alignment gate
# ----------------------------------------------------------------------
def pick_probes(X, pre, split_name):
    """Choose columns that are safe to compare row for row: present in both
    frames, numeric in both, and never imputed (no NaN in the pre-FE table,
    so nothing was filled in on the way into X). Preferred names first, then
    the highest-cardinality survivors, so the choice is deterministic."""
    shared = [c for c in X.columns if c in pre.columns]
    eligible, rejected = [], []
    for c in shared:
        if not (pd.api.types.is_numeric_dtype(X[c]) and pd.api.types.is_numeric_dtype(pre[c])):
            rejected.append((c, "not numeric in both frames"))
            continue
        n_na = int(pre[c].isna().sum())
        if n_na:
            rejected.append((c, f"{n_na} NaN in pre-FE table — median-imputed into X"))
            continue
        eligible.append(c)

    rejected_map = dict(rejected)
    for c in PREFERRED_PROBES:
        if c not in shared:
            print(f"  probe {c!r} not usable on {split_name}: absent from one of the two frames")
        elif c in rejected_map:
            print(f"  probe {c!r} not usable on {split_name}: {rejected_map[c]}")

    ranked = sorted(eligible, key=lambda c: (-int(pre[c].nunique()), c))
    chosen = [c for c in PREFERRED_PROBES if c in eligible]
    for c in ranked:
        if len(chosen) >= N_PROBES:
            break
        if c not in chosen:
            chosen.append(c)
    return chosen


def check_split(X, pre, y, split_name):
    """Assert positional alignment for one split. Full column, every row."""
    print(f"\n{split_name}:")

    if len(X) != len(pre):
        raise GateFailure(
            f"row-count check ({split_name}): X has {len(X)} rows, pre-FE table has {len(pre)}"
        )
    if len(X) != len(y):
        raise GateFailure(
            f"target row-count check ({split_name}): X has {len(X)} rows, y has {len(y)}"
        )
    print(f"  row counts match: {len(X)} rows in X, pre-FE table, and y")

    probes = pick_probes(X, pre, split_name)
    if len(probes) < MIN_PROBES:
        raise GateFailure(
            f"probe-selection check ({split_name}): only {len(probes)} usable probe "
            f"columns found, need at least {MIN_PROBES}"
        )

    for c in probes:
        a = X[c].to_numpy()
        b = pre[c].to_numpy()
        if np.issubdtype(a.dtype, np.integer) and np.issubdtype(b.dtype, np.integer):
            same = a == b
            how = "exact"
        else:
            same = np.isclose(a.astype("float64"), b.astype("float64"),
                              rtol=0, atol=1e-9, equal_nan=True)
            how = "np.isclose"
        n_bad = int((~same).sum())
        if n_bad:
            first = int(np.flatnonzero(~same)[0])
            raise GateFailure(
                f"row-for-row equality check ({split_name}, column {c!r}): "
                f"{n_bad} of {len(same)} rows differ, first at position {first} "
                f"(X={a[first]!r}, pre-FE={b[first]!r})"
            )
        print(f"  {c:<28s} {len(same):>7d} rows equal ({how}, {int(pre[c].nunique())} distinct values)")

    return probes


def alignment_gate(X_train, X_test, pre_train, pre_test, y_train, y_test):
    rule("STEP 0 — ALIGNMENT GATE")
    print("Establishing that X_* is positionally aligned with train/test.parquet,")
    print("so issue_year can be attached to feature rows by position alone.")
    probes_tr = check_split(X_train, pre_train, y_train, "train")
    probes_te = check_split(X_test, pre_test, y_test, "test")

    years_tr = sorted(pre_train[VINTAGE_COL].unique().tolist())
    years_te = sorted(pre_test[VINTAGE_COL].unique().tolist())
    print(f"\n  issue_year present in train: {years_tr}")
    print(f"  issue_year present in test:  {years_te}")
    print("\nGATE PASSED — alignment demonstrated on "
          f"{len(probes_tr)} train columns and {len(probes_te)} test columns, full length, no sampling.")
    return probes_tr, probes_te


# ----------------------------------------------------------------------
# Artefact 1 — coverage_profile.csv
# ----------------------------------------------------------------------
def build_coverage(X_train, X_test, year_train, features, flag_of):
    scopes = [("train", X_train, None), ("test", X_test, None)]
    for yr in (2014, 2015, 2016):
        scopes.append((str(yr), X_train, (year_train == yr).to_numpy()))
    scopes.append(("2017", X_test, None))

    rows = []
    for scope_name, frame, mask in scopes:
        sub = frame if mask is None else frame.loc[mask]
        n_rows = len(sub)
        for feat in features:
            v = sub[feat].to_numpy(dtype="float64", copy=False)
            flag = flag_of.get(feat)
            if flag is None:
                pct_flagged = None
            else:
                pct_flagged = round(float(sub[flag].mean()) * 100.0, 4)
            rows.append({
                "feature": feat,
                "scope": scope_name,
                "n_rows": n_rows,
                "has_missingness_flag": flag is not None,
                "pct_flagged_missing": pct_flagged,
                "pct_zero": round(float((v == 0).mean()) * 100.0, 4),
                "pct_at_999": round(float((v == SENTINEL).mean()) * 100.0, 4),
                "n_unique": int(np.unique(v).size),
                "mean": round(float(v.mean()), 6),
                "std": round(float(v.std(ddof=1)), 6) if n_rows > 1 else None,
                "p50": round(float(np.median(v)), 6),
            })
    return pd.DataFrame(rows, columns=[
        "feature", "scope", "n_rows", "has_missingness_flag", "pct_flagged_missing",
        "pct_zero", "pct_at_999", "n_unique", "mean", "std", "p50",
    ])


# ----------------------------------------------------------------------
# Artefact 2 — univariate_assoc.csv
# ----------------------------------------------------------------------
def auc_from_ranks(values, y):
    """Mann-Whitney U expressed as ROC-AUC, using the raw feature as the
    score. No direction correction: a feature that runs the other way lands
    below 0.5 and stays there."""
    n_pos = int(y.sum())
    n_neg = int(y.size - n_pos)
    if n_pos == 0 or n_neg == 0:
        return None
    if np.unique(values).size < 2:
        return None
    r = rankdata(values)
    u = r[y == 1].sum() - n_pos * (n_pos + 1) / 2.0
    return round(float(u / (n_pos * n_neg)), 6)


def build_univariate(X_train, X_test, y_train, y_test, year_train, features):
    y_tr = y_train.to_numpy(dtype="int8")
    y_te = y_test.to_numpy(dtype="int8")
    year_masks = {yr: (year_train == yr).to_numpy() for yr in (2014, 2015, 2016)}

    rows = []
    for feat in features:
        v_tr = X_train[feat].to_numpy(dtype="float64", copy=False)
        v_te = X_test[feat].to_numpy(dtype="float64", copy=False)
        n_uniq_te = int(np.unique(v_te).size)
        constant_te = n_uniq_te < 2

        if constant_te:
            r_te = None
        else:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                r_te = round(float(pearsonr(v_te, y_te.astype("float64"))[0]), 6)

        row = {
            "feature": feat,
            "auc_train": auc_from_ranks(v_tr, y_tr),
            "auc_test": auc_from_ranks(v_te, y_te),
        }
        for yr in (2014, 2015, 2016):
            m = year_masks[yr]
            row[f"auc_{yr}"] = auc_from_ranks(v_tr[m], y_tr[m])
        row["point_biserial_test"] = r_te
        row["n_unique_test"] = n_uniq_te
        row["is_constant_test"] = constant_te
        rows.append(row)

    return pd.DataFrame(rows, columns=[
        "feature", "auc_train", "auc_test", "auc_2014", "auc_2015", "auc_2016",
        "point_biserial_test", "n_unique_test", "is_constant_test",
    ])


# ----------------------------------------------------------------------
# Artefact 3 — correlation_topk.csv
# ----------------------------------------------------------------------
def build_correlation(X_test, features):
    mat = X_test[features].to_numpy(dtype="float64", copy=True)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        corr = np.corrcoef(mat, rowvar=False)
    del mat

    rows = []
    for i, feat in enumerate(features):
        series = pd.Series(corr[i], index=features).drop(labels=[feat])
        series = series.dropna()
        if series.empty:
            rows.append({"feature": feat, "rank": 1, "neighbour": None,
                         "pearson_r": None, "abs_pearson_r": None})
            continue
        ordered = pd.DataFrame({"neighbour": series.index, "pearson_r": series.to_numpy()})
        ordered["abs_pearson_r"] = ordered["pearson_r"].abs()
        # name as tiebreak so repeated runs give the same order
        ordered = ordered.sort_values(["abs_pearson_r", "neighbour"],
                                      ascending=[False, True], kind="stable")
        for rank, rec in enumerate(ordered.head(TOP_K).itertuples(index=False), start=1):
            rows.append({
                "feature": feat,
                "rank": rank,
                "neighbour": rec.neighbour,
                "pearson_r": round(float(rec.pearson_r), 6),
                "abs_pearson_r": round(float(rec.abs_pearson_r), 6),
            })
    return pd.DataFrame(rows, columns=[
        "feature", "rank", "neighbour", "pearson_r", "abs_pearson_r",
    ])


# ----------------------------------------------------------------------
# Notes
# ----------------------------------------------------------------------
def write_notes(path, variant, features, flag_of, n_train, n_test, probes, year_counts):
    n_feat = len(features)
    n_flagged = len(flag_of)
    n_unflagged = n_feat - n_flagged
    vintages = ", ".join(f"{yr} ({n:,} rows)" for yr, n in year_counts.items())

    text = f"""# Precomputed agent cache — v2 artefacts ({variant} variant)

Three files, written by `scripts/build_agent_cache_v2.py --variant {variant}`.
They exist so the audit agent can read finished measurements instead of
reaching for `data/`. Everything below is descriptive: no model was fitted,
nothing was resampled, no SHAP value was recomputed.

The feature matrix for this variant has {n_feat} columns, {n_train:,} training
rows and {n_test:,} test rows. Train covers {vintages}; test is 2017 in full.

## coverage_profile.csv

One row per feature per scope, six scopes: `train`, `test`, and the four
vintages `2014`, `2015`, `2016`, `2017`. The vintage scopes come from
`issue_year`, which lives in `train.parquet` / `test.parquet` and not in the
feature matrix, so the script attaches it by row position and refuses to run
unless that alignment is demonstrated first — full-length row-for-row equality
on {len(probes)} untransformed numeric columns ({", ".join(probes)}). There is
no join, no sort, no merge on a key anywhere in this script.

`pct_flagged_missing` is the mean of the feature's `_was_missing` companion
within the scope. It is left empty, not zero, for features that have no such
companion: zero would read as "nothing was missing" when the truth is "the
question does not apply". `pct_zero` and `pct_at_999` count exact values, 999
being the sentinel that `04_features.py` writes into the `mths_since_*` family.
`mean`, `std` and `p50` are the ordinary sample statistics, `std` with ddof=1.

The `_was_missing` columns are profiled as features in their own right, since
that is what they are to the model.

## univariate_assoc.csv

One row per feature: how much of the target that feature accounts for on its
own. `auc_train` and `auc_test` are ROC-AUC computed from the Mann-Whitney U
statistic over `scipy.stats.rankdata`, using the raw feature value as the
score. `auc_2014` through `auc_2016` are the same statistic computed inside
each training vintage.

The AUCs are not folded to `max(auc, 1 - auc)`. A feature whose high values go
with non-default lands below 0.5 and is left there, because the direction is
part of what the number tells you. A feature that is constant within a scope
gets an empty AUC for that scope rather than 0.5. `point_biserial_test` is the
Pearson correlation between the feature and `is_default` on test.

## correlation_topk.csv

Long format: for each feature, its {TOP_K} nearest neighbours by absolute
Pearson correlation, ranked 1 to {TOP_K}, signed `pearson_r` kept alongside
`abs_pearson_r`. Computed on the full test matrix, no sampling, so it sits on
the same footing as the ablation numbers in `ablation_cache.csv`, which were
also measured on test. Self-pairs are skipped. Ties are broken on neighbour
name so a rerun gives byte-identical output. A feature that is constant on test
has no defined correlations and gets one row with rank 1 and empty neighbour
and `pearson_r`, so that it still appears in the file rather than vanishing.

## What these files cannot tell you

The big one is coverage. The feature matrices contain no NaN at all — zero, in
both splits. `04_features.py` imputed as it built them: sentinel 999 for the
`mths_since_*` family, train medians for the Dec-2015 bureau block and for
`emp_length`, train medians again for everything else that had gaps. Of the
{n_feat} columns, {n_flagged} kept a `_was_missing` companion recording what was
filled. The other {n_unflagged} did not, and for those `coverage_profile.csv`
will report complete data in every scope. That is an artefact of construction
and carries no information — it is not evidence that those columns were
complete in the source. Where a column was imputed without a flag, the fill is
now indistinguishable from a real observation in these statistics.

Two smaller ones. The vintage scopes are unbalanced by design, 2014 through
2016 being train slices of quite different sizes and 2017 being the whole test
split, so a per-vintage number moves partly with sample size. And every
statistic here is univariate or pairwise; nothing in these three files sees an
interaction between three or more columns.
"""
    path.write_text(text, encoding="utf-8")


# ----------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Build v2 artefacts for the Layer 2 agent cache.")
    ap.add_argument("--variant", choices=sorted(VARIANTS), required=True)
    args = ap.parse_args()

    cfg = VARIANTS[args.variant]
    out_dir = cfg["out_dir"]
    t0 = time.perf_counter()

    rule(f"build_agent_cache_v2 — variant: {args.variant}")
    print(f"  features from : {cfg['x_train']} / {cfg['x_test']}")
    print(f"  target from   : y_train.parquet / y_test.parquet")
    print(f"  writing into  : {out_dir.relative_to(PROJECT_ROOT)}/")

    X_train = pd.read_parquet(PROCESSED / cfg["x_train"])
    X_test = pd.read_parquet(PROCESSED / cfg["x_test"])
    y_train = pd.read_parquet(PROCESSED / "y_train.parquet")[TARGET]
    y_test = pd.read_parquet(PROCESSED / "y_test.parquet")[TARGET]
    pre_train = pd.read_parquet(PROCESSED / "train.parquet")
    pre_test = pd.read_parquet(PROCESSED / "test.parquet")

    try:
        probes_tr, _ = alignment_gate(X_train, X_test, pre_train, pre_test, y_train, y_test)
    except GateFailure as exc:
        print()
        print(f"GATE FAILED — {exc}")
        print("No output files written. Alignment is not repaired here; fix it upstream.")
        return 1

    year_train = pre_train[VINTAGE_COL].reset_index(drop=True)
    features = list(X_train.columns)
    flag_of = {f: f + FLAG_SUFFIX for f in features if f + FLAG_SUFFIX in X_train.columns}
    year_counts = {int(yr): int(n) for yr, n in year_train.value_counts().sort_index().items()}

    out_dir.mkdir(parents=True, exist_ok=True)
    written = []

    rule("ARTEFACTS")

    t = time.perf_counter()
    cov = build_coverage(X_train, X_test, year_train, features, flag_of)
    p = out_dir / "coverage_profile.csv"
    cov.to_csv(p, index=False, na_rep="")
    written.append((p, len(cov), time.perf_counter() - t))
    print(f"  coverage_profile.csv   {len(cov):>6d} rows  ({time.perf_counter() - t:5.1f}s)")

    t = time.perf_counter()
    uni = build_univariate(X_train, X_test, y_train, y_test, year_train, features)
    p = out_dir / "univariate_assoc.csv"
    uni.to_csv(p, index=False, na_rep="")
    written.append((p, len(uni), time.perf_counter() - t))
    print(f"  univariate_assoc.csv   {len(uni):>6d} rows  ({time.perf_counter() - t:5.1f}s)")

    t = time.perf_counter()
    cor = build_correlation(X_test, features)
    p = out_dir / "correlation_topk.csv"
    cor.to_csv(p, index=False, na_rep="")
    written.append((p, len(cor), time.perf_counter() - t))
    print(f"  correlation_topk.csv   {len(cor):>6d} rows  ({time.perf_counter() - t:5.1f}s)")

    notes = out_dir / "PRECOMPUTE_NOTES.md"
    write_notes(notes, args.variant, features, flag_of, len(X_train), len(X_test),
                probes_tr, year_counts)
    print(f"  PRECOMPUTE_NOTES.md           -  prose")

    rule("SUMMARY")
    for p, n, secs in written:
        print(f"  {p.relative_to(PROJECT_ROOT)}  —  {n} rows")
    print(f"  {notes.relative_to(PROJECT_ROOT)}")
    print(f"\n  features profiled : {len(features)}")
    print(f"  with a _was_missing companion : {len(flag_of)}")
    print(f"  wall time : {time.perf_counter() - t0:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
