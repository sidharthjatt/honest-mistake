"""07_audit.py — Honest Mistake project.

Self-audit of the tuned XGBoost model:
  1. SHAP global explanations (beeswarm + bar, top 20)
  2. Sanity check: do the expected credit variables dominate, or is the
     model leaning on artifacts (missing-flags, dummies)? -> AUDIT FINDINGS
  3. Local waterfalls: confident-correct / confident-wrong / borderline
  4. Slice AUCs: 2017 quarters, grade, bureau was-missing cohort

Run:  .venv/bin/python src/07_audit.py
"""

from datetime import datetime
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import roc_auc_score

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "data" / "processed"
FIGURES = PROJECT_ROOT / "outputs" / "figures"
NOTES_TXT = PROJECT_ROOT / "outputs" / "audit_notes.txt"
MODEL_PATH = PROJECT_ROOT / "outputs" / "models" / "xgb_tuned.joblib"

SHAP_SAMPLE = 30_000
RANDOM_STATE = 42
SLICE_AUC_DROP = 0.03   # flag slices this far below overall AUC
MIN_SLICE_N = 1_000     # below this, report but don't AUC-flag

ONE_HOT_PREFIXES = (
    "home_ownership_", "verification_status_", "purpose_",
    "initial_list_status_", "application_type_", "disbursement_method_",
    "addr_state_",
)


class Tee:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("w", encoding="utf-8")

    def line(self, text: str = "") -> None:
        print(text, flush=True)
        self._fh.write(text + "\n")
        self._fh.flush()

    def close(self) -> None:
        self._fh.close()


def header(tee: Tee, title: str) -> None:
    tee.line()
    tee.line("=" * 70)
    tee.line(title)
    tee.line("=" * 70)


def is_artifact(col: str) -> str | None:
    """Return artifact type if the feature is a flag/dummy, else None."""
    if col.endswith("_was_missing"):
        return "was_missing flag"
    if col.startswith(ONE_HOT_PREFIXES):
        return "one-hot dummy"
    return None


def save_shap_fig(path: Path, title: str) -> None:
    plt.gcf().suptitle(title, fontsize=10)
    plt.savefig(path, dpi=150, bbox_inches="tight")
    plt.close("all")


def slice_auc(tee: Tee, label: str, y: np.ndarray, proba: np.ndarray,
              mask: np.ndarray, overall: float, exempt: bool = False) -> None:
    n = int(mask.sum())
    if n == 0:
        tee.line(f"  {label:<28} n=0 — empty slice")
        return
    ys, ps = y[mask], proba[mask]
    rate = ys.mean() * 100
    if ys.min() == ys.max():
        tee.line(f"  {label:<28} n={n:>7,}  default {rate:5.2f}%  AUC n/a (single class)")
        return
    auc = roc_auc_score(ys, ps)
    line = f"  {label:<28} n={n:>7,}  default {rate:5.2f}%  AUC {auc:.4f}"
    if n < MIN_SLICE_N:
        line += "  (small slice — not flagged)"
    elif not exempt and auc < overall - SLICE_AUC_DROP:
        line += f"  ** AUDIT FINDING: {overall - auc:.3f} below overall **"
    tee.line(line)


def main() -> None:
    tee = Tee(NOTES_TXT)
    tee.line("Honest Mistake — audit notes (tuned XGBoost)")
    tee.line(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")

    model = joblib.load(MODEL_PATH)
    X_test = pd.read_parquet(PROCESSED / "X_test.parquet")
    y_test = pd.read_parquet(PROCESSED / "y_test.parquet")["is_default"]
    meta = pd.read_parquet(PROCESSED / "test.parquet",
                           columns=["issue_d", "is_default"])
    assert len(meta) == len(X_test)
    assert (meta["is_default"].to_numpy() == y_test.to_numpy()).all(), \
        "row order mismatch between X_test and test.parquet"

    proba_full = model.predict_proba(X_test)[:, 1]
    y_arr = y_test.to_numpy()
    overall_auc = roc_auc_score(y_arr, proba_full)
    tee.line(f"Test set: {len(X_test):,} rows, overall ROC-AUC {overall_auc:.4f}")

    # ------------------------------------------------------------------
    # SHAP on a sample
    # ------------------------------------------------------------------
    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(len(X_test), size=SHAP_SAMPLE, replace=False)
    X_s = X_test.iloc[idx]
    y_s = y_arr[idx]
    proba_s = proba_full[idx]

    header(tee, f"SHAP — TreeExplainer on {SHAP_SAMPLE:,} sampled test rows (seed {RANDOM_STATE})")
    tee.line("  SHAP values are in log-odds space (XGBoost margin output).")
    explainer = shap.TreeExplainer(model)
    exp = explainer(X_s)

    FIGURES.mkdir(parents=True, exist_ok=True)
    shap.plots.beeswarm(exp, max_display=20, show=False)
    save_shap_fig(FIGURES / "shap_beeswarm_top20.png",
                  f"SHAP beeswarm — tuned XGB, {SHAP_SAMPLE:,} test rows")
    shap.plots.bar(exp, max_display=20, show=False)
    save_shap_fig(FIGURES / "shap_bar_top20.png",
                  f"mean |SHAP| — tuned XGB, {SHAP_SAMPLE:,} test rows")
    tee.line("  figures: shap_beeswarm_top20.png, shap_bar_top20.png")

    mean_abs = pd.Series(np.abs(exp.values).mean(axis=0), index=X_s.columns)
    ranking = mean_abs.sort_values(ascending=False)

    tee.line()
    tee.line("  Top 20 by mean |SHAP|:")
    for rank, (col, val) in enumerate(ranking.head(20).items(), 1):
        kind = is_artifact(col)
        tag = f"   <-- {kind}" if kind else ""
        tee.line(f"    {rank:>2}. {col:<35} {val:.4f}{tag}")

    # ------------------------------------------------------------------
    # Sanity check — audit findings
    # ------------------------------------------------------------------
    header(tee, "SANITY CHECK — who is carrying the model?")
    core = ["grade", "sub_grade", "int_rate", "term", "dti",
            "credit_history_months", "fico_range_low", "fico_range_high",
            "annual_inc", "loan_amnt", "installment"]
    top10 = list(ranking.head(10).index)
    core_in_top10 = [c for c in core if c in top10]
    tee.line(f"  Expected core features in top 10: {len(core_in_top10)}/10 slots")
    tee.line(f"    present: {core_in_top10}")

    findings: list[str] = []
    for rank, col in enumerate(top10, 1):
        kind = is_artifact(col)
        if kind:
            findings.append(
                f"rank {rank}: '{col}' is a {kind} (mean |SHAP| {ranking[col]:.4f}) "
                f"— the model is leaning on a data-collection artifact, not borrower behavior")
    for rank, col in enumerate(ranking.head(20).index, 1):
        if rank > 10 and is_artifact(col):
            findings.append(
                f"rank {rank}: '{col}' ({is_artifact(col)}) in top 20 "
                f"(mean |SHAP| {ranking[col]:.4f}) — worth watching, below top-10 severity")

    if findings:
        tee.line()
        tee.line("  " + "*" * 64)
        tee.line("  ** AUDIT FINDINGS — unexpected features with high attribution **")
        tee.line("  " + "*" * 64)
        for f in findings:
            tee.line(f"    - {f}")
    else:
        tee.line("  No missing-flags or dummies in the top 20 — attribution mass sits")
        tee.line("  on real application/bureau variables. No findings here.")

    # ------------------------------------------------------------------
    # Local waterfalls — 3 cases from the SHAP sample
    # ------------------------------------------------------------------
    header(tee, "LOCAL EXPLANATIONS — 3 cases (probas inflated by class weighting;")
    tee.line("'borderline' means score space, not calibrated risk)")

    cases = {
        "confident_correct": int(np.argmax(np.where(y_s == 1, proba_s, -1))),
        "confident_wrong":   int(np.argmax(np.where(y_s == 0, proba_s, -1))),
        "borderline":        int(np.argmin(np.abs(proba_s - 0.5))),
    }
    for name, i in cases.items():
        shap.plots.waterfall(exp[i], max_display=15, show=False)
        fname = f"shap_waterfall_{name}.png"
        save_shap_fig(FIGURES / fname, f"{name} — proba {proba_s[i]:.3f}, actual {y_s[i]}")
        row_contrib = pd.Series(exp.values[i], index=X_s.columns)
        top3 = row_contrib.abs().sort_values(ascending=False).head(3)
        tee.line(f"  {name}: proba {proba_s[i]:.3f}, actual is_default={y_s[i]}  -> {fname}")
        for col in top3.index:
            tee.line(f"      {col:<35} shap {row_contrib[col]:+.3f}  (value {X_s.iloc[i][col]:g})")

    # ------------------------------------------------------------------
    # Slice analysis — full test set
    # ------------------------------------------------------------------
    header(tee, f"SLICE AUCs (overall {overall_auc:.4f}; flag if > {SLICE_AUC_DROP} below)")

    tee.line("  By 2017 quarter (later quarters = less time to resolve —")
    tee.line("  survivorship bias from split_notes.txt applies most there):")
    quarter = pd.to_datetime(meta["issue_d"], format="%b-%Y").dt.quarter.to_numpy()
    for q in (1, 2, 3, 4):
        slice_auc(tee, f"2017 Q{q}", y_arr, proba_full, quarter == q, overall_auc)

    tee.line()
    tee.line("  By grade (NOTE: within-grade AUC is expected to be far below overall —")
    tee.line("  grade itself does much of the ranking; compare grades to each other):")
    grades = X_test["grade"].to_numpy()
    for g, letter in enumerate("ABCDEFG", start=1):
        slice_auc(tee, f"grade {letter}", y_arr, proba_full, grades == g,
                  overall_auc, exempt=True)

    tee.line()
    tee.line("  Bureau was-missing cohort (open_acc_6m_was_missing):")
    miss_mask = X_test["open_acc_6m_was_missing"].to_numpy() == 1
    slice_auc(tee, "bureau fields missing", y_arr, proba_full, miss_mask, overall_auc)
    slice_auc(tee, "bureau fields present", y_arr, proba_full, ~miss_mask, overall_auc)
    if miss_mask.sum() == 0:
        tee.line("    -> cohort is EMPTY in 2017: LC collected these fields for all test-era")
        tee.line("       loans. The 21 was_missing flag columns can never fire at test time —")
        tee.line("       they are train-era artifacts. Noted as an audit observation.")

    header(tee, "OUTPUT")
    tee.line("  figures: shap_beeswarm_top20.png, shap_bar_top20.png,")
    tee.line("           shap_waterfall_{confident_correct,confident_wrong,borderline}.png")
    tee.line(f"Notes saved to {NOTES_TXT.relative_to(PROJECT_ROOT)}")
    tee.close()


if __name__ == "__main__":
    main()
