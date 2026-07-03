"""08_fairness_ablation.py — Honest Mistake project.

Fairness experiment: how much predictive value does the model extract
from emp_length_was_missing (the "declined to state employment" marker
flagged in the audit)? Retrain the tuned config WITHOUT that column and
measure the cost on the 2017 test set.

The ablated model is an experiment, not a candidate — it is not saved.

Run:  .venv/bin/python src/08_fairness_ablation.py
"""

import json
import time
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score
from xgboost import XGBClassifier

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "data" / "processed"
NOTES_TXT = PROJECT_ROOT / "outputs" / "fairness_ablation_notes.txt"
PARAMS_JSON = PROJECT_ROOT / "outputs" / "models" / "best_params.json"
TUNED_MODEL = PROJECT_ROOT / "outputs" / "models" / "xgb_tuned.joblib"

ABLATED_COL = "emp_length_was_missing"

FIXED_PARAMS = dict(
    tree_method="hist",
    eval_metric="auc",
    random_state=42,
    n_jobs=-1,
)


class Tee:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("w", encoding="utf-8")

    def line(self, text: str = "") -> None:
        print(text, flush=True)
        self._fh.write(text + "\n")

    def close(self) -> None:
        self._fh.close()


def header(tee: Tee, title: str) -> None:
    tee.line()
    tee.line("=" * 70)
    tee.line(title)
    tee.line("=" * 70)


def main() -> None:
    tee = Tee(NOTES_TXT)
    tee.line("Honest Mistake — fairness ablation notes")
    tee.line(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    tee.line(f"Question: how much does the model rely on '{ABLATED_COL}'")
    tee.line("(the 'declined to state employment' marker) for its performance?")

    payload = json.loads(PARAMS_JSON.read_text())
    best_params = payload["best_params"]
    spw_full = payload["scale_pos_weight_full"]

    X_train = pd.read_parquet(PROCESSED / "X_train.parquet")
    X_test = pd.read_parquet(PROCESSED / "X_test.parquet")
    y_train = pd.read_parquet(PROCESSED / "y_train.parquet")["is_default"]
    y_test = pd.read_parquet(PROCESSED / "y_test.parquet")["is_default"]

    header(tee, "SETUP")
    tee.line(f"  params: best_params.json (trial #{payload['best_trial']}), "
             f"scale_pos_weight {spw_full:.3f} — identical to xgb_tuned")
    tee.line(f"  only difference: '{ABLATED_COL}' dropped "
             f"({X_train.shape[1]} -> {X_train.shape[1] - 1} features)")
    flag_rate = X_train[ABLATED_COL].mean() * 100
    tee.line(f"  cohort size: flag=1 on {flag_rate:.2f}% of train rows")

    X_train_abl = X_train.drop(columns=[ABLATED_COL])
    X_test_abl = X_test.drop(columns=[ABLATED_COL])

    # ------------------------------------------------------------------
    # Retrain without the flag
    # ------------------------------------------------------------------
    model = XGBClassifier(**best_params, **FIXED_PARAMS, scale_pos_weight=spw_full)
    t0 = time.perf_counter()
    model.fit(X_train_abl, y_train)
    tee.line(f"  retrain time: {time.perf_counter() - t0:.1f}s")

    proba_abl = model.predict_proba(X_test_abl)[:, 1]
    roc_abl = roc_auc_score(y_test, proba_abl)
    pr_abl = average_precision_score(y_test, proba_abl)

    # Re-score the saved tuned model so the delta is exact, not quoted.
    tuned = joblib.load(TUNED_MODEL)
    proba_tuned = tuned.predict_proba(X_test)[:, 1]
    roc_tuned = roc_auc_score(y_test, proba_tuned)
    pr_tuned = average_precision_score(y_test, proba_tuned)

    # ------------------------------------------------------------------
    # Comparison
    # ------------------------------------------------------------------
    header(tee, "RESULTS — temporal 2017 test set")
    tee.line(f"  {'model':<30} {'ROC-AUC':>8} {'PR-AUC':>8}")
    tee.line(f"  {'tuned (with flag)':<30} {roc_tuned:>8.4f} {pr_tuned:>8.4f}")
    tee.line(f"  {'ablated (flag dropped)':<30} {roc_abl:>8.4f} {pr_abl:>8.4f}")
    tee.line(f"  {'delta (ablated - tuned)':<30} {roc_abl - roc_tuned:>+8.4f} {pr_abl - pr_tuned:>+8.4f}")

    header(tee, "CAVEAT")
    tee.line("  This removes the EXPLICIT 'declined to state employment' marker only.")
    tee.line("  Rows that had missing emp_length keep their median-imputed value (6),")
    tee.line("  and correlated features may let the model partially reconstruct the")
    tee.line("  cohort. This is a remove-the-explicit-signal test, not full")
    tee.line("  information removal.")

    header(tee, "SUMMARY")
    droc = roc_tuned - roc_abl
    tee.line(f"  Dropping the flag costs {droc:+.4f} ROC-AUC and "
             f"{pr_tuned - pr_abl:+.4f} PR-AUC on the 2017 test set.")
    if abs(droc) < 0.002:
        tee.line("  The cost is negligible: the model's performance does not depend on")
        tee.line("  penalizing applicants for not stating employment length. Removing")
        tee.line("  the marker on fairness grounds would be essentially free.")
    elif abs(droc) < 0.005:
        tee.line("  The cost is small but real. Removing the marker on fairness grounds")
        tee.line("  is affordable; document the trade-off.")
    else:
        tee.line("  The cost is material — the model extracts real ranking power from")
        tee.line("  the 'declined to answer' signal. A fairness-driven removal needs an")
        tee.line("  explicit decision weighing that loss.")
    tee.line("  (Ablated model not saved — experiment only.)")

    tee.line()
    tee.line(f"Notes saved to {NOTES_TXT.relative_to(PROJECT_ROOT)}")
    tee.close()


if __name__ == "__main__":
    main()
