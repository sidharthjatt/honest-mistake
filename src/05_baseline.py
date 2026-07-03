"""05_baseline.py — Honest Mistake project.

Baseline bar before any tuning: logistic regression + default-ish XGBoost,
evaluated on the temporal (2017) test set. No tuning, no feature selection,
no threshold optimization.

Run:  .venv/bin/python src/05_baseline.py
"""

import time
import warnings
from datetime import datetime
from pathlib import Path

import joblib
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_curve,
    precision_recall_fscore_support,
    roc_auc_score,
    roc_curve,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "data" / "processed"
NOTES_TXT = PROJECT_ROOT / "outputs" / "baseline_notes.txt"
FIG_PNG = PROJECT_ROOT / "outputs" / "figures" / "roc_pr_curves.png"
MODELS_DIR = PROJECT_ROOT / "outputs" / "models"

RANDOM_STATE = 42
THRESHOLD = 0.5  # default threshold — will tune later


class Tee:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("w", encoding="utf-8")

    def line(self, text: str = "") -> None:
        print(text)
        self._fh.write(text + "\n")

    def close(self) -> None:
        self._fh.close()


def header(tee: Tee, title: str) -> None:
    tee.line()
    tee.line("=" * 70)
    tee.line(title)
    tee.line("=" * 70)


def evaluate(tee: Tee, name: str, y_true, proba) -> dict:
    """Print + return honest metrics for one model."""
    roc = roc_auc_score(y_true, proba)
    pr = average_precision_score(y_true, proba)
    brier = brier_score_loss(y_true, proba)

    pred = (proba >= THRESHOLD).astype(int)
    cm = confusion_matrix(y_true, pred)
    prec, rec, f1, _ = precision_recall_fscore_support(
        y_true, pred, average="binary", zero_division=0
    )

    header(tee, f"METRICS — {name} (temporal 2017 test set)")
    tee.line(f"  ROC-AUC:      {roc:.4f}")
    tee.line(f"  PR-AUC (AP):  {pr:.4f}   (prevalence baseline: {y_true.mean():.4f})")
    tee.line(f"  Brier score:  {brier:.4f}   (inflated by class weighting — see caveat)")
    tee.line()
    tee.line(f"  At threshold {THRESHOLD} (default threshold — will tune later):")
    tee.line(f"    confusion matrix [rows=actual 0/1, cols=predicted 0/1]:")
    tee.line(f"      TN {cm[0, 0]:>8,}   FP {cm[0, 1]:>8,}")
    tee.line(f"      FN {cm[1, 0]:>8,}   TP {cm[1, 1]:>8,}")
    tee.line(f"    precision: {prec:.4f}   recall: {rec:.4f}   F1: {f1:.4f}")
    return {"roc": roc, "pr": pr}


def main() -> None:
    tee = Tee(NOTES_TXT)
    tee.line("Honest Mistake — baseline notes")
    tee.line(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    tee.line("No tuning, no feature selection, no threshold optimization — this is the bar.")

    X_train = pd.read_parquet(PROCESSED / "X_train.parquet")
    X_test = pd.read_parquet(PROCESSED / "X_test.parquet")
    y_train = pd.read_parquet(PROCESSED / "y_train.parquet")["is_default"]
    y_test = pd.read_parquet(PROCESSED / "y_test.parquet")["is_default"]

    n_neg, n_pos = int((y_train == 0).sum()), int((y_train == 1).sum())
    spw = n_neg / n_pos
    tee.line(f"Loaded X_train {X_train.shape}, X_test {X_test.shape}")
    tee.line(f"scale_pos_weight (train neg/pos): {n_neg:,}/{n_pos:,} = {spw:.3f}")

    MODELS_DIR.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Model A — logistic regression (scaler inside pipeline: fit on train only)
    # ------------------------------------------------------------------
    logreg = Pipeline([
        ("scaler", StandardScaler()),
        ("clf", LogisticRegression(max_iter=2000, class_weight="balanced")),
    ])

    header(tee, "MODEL A — LogisticRegression (scaled, class_weight='balanced')")
    tee.line("  StandardScaler lives INSIDE the pipeline -> fit on train only.")
    tee.line("  (Trees below get no scaler — they don't need one.)")
    t0 = time.perf_counter()
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        logreg.fit(X_train, y_train)
    t_logreg = time.perf_counter() - t0
    tee.line(f"  train time: {t_logreg:.1f}s")
    conv = [w for w in caught if "onverge" in str(w.message)]
    if conv:
        tee.line(f"  ** CONVERGENCE WARNING ({len(conv)}): {conv[0].message}")
    else:
        tee.line("  converged: yes (no convergence warnings)")

    proba_logreg = logreg.predict_proba(X_test)[:, 1]
    m_logreg = evaluate(tee, "LogisticRegression", y_test, proba_logreg)

    # ------------------------------------------------------------------
    # Model B — XGBoost, defaults except the agreed handful
    # ------------------------------------------------------------------
    xgb = XGBClassifier(
        n_estimators=300,
        tree_method="hist",
        eval_metric="auc",
        scale_pos_weight=spw,
        random_state=RANDOM_STATE,
        n_jobs=-1,
    )

    header(tee, "MODEL B — XGBClassifier (defaults + agreed overrides)")
    tee.line(f"  n_estimators=300, tree_method='hist', eval_metric='auc',")
    tee.line(f"  scale_pos_weight={spw:.3f}, random_state={RANDOM_STATE}, n_jobs=-1")
    t0 = time.perf_counter()
    xgb.fit(X_train, y_train)
    t_xgb = time.perf_counter() - t0
    tee.line(f"  train time: {t_xgb:.1f}s")

    proba_xgb = xgb.predict_proba(X_test)[:, 1]
    m_xgb = evaluate(tee, "XGBoost", y_test, proba_xgb)

    # ------------------------------------------------------------------
    # Caveat
    # ------------------------------------------------------------------
    header(tee, "CAVEAT — Brier scores are inflated by construction")
    tee.line("  Both models use class weighting (class_weight='balanced' /")
    tee.line("  scale_pos_weight), which deliberately shifts predicted probabilities")
    tee.line("  upward to favor recall on the minority class. Brier score punishes")
    tee.line("  that distortion. Do NOT compare these Brier values against future")
    tee.line("  unweighted or calibrated models without re-reading this note.")
    tee.line("  Ranking metrics (ROC-AUC, PR-AUC) are unaffected by the weighting.")

    # ------------------------------------------------------------------
    # Figure — ROC + PR, both models
    # ------------------------------------------------------------------
    fig, (ax_roc, ax_pr) = plt.subplots(1, 2, figsize=(12, 5))

    for name, proba, m in (
        ("LogReg", proba_logreg, m_logreg),
        ("XGBoost", proba_xgb, m_xgb),
    ):
        fpr, tpr, _ = roc_curve(y_test, proba)
        ax_roc.plot(fpr, tpr, label=f"{name} (AUC = {m['roc']:.4f})")
        prec, rec, _ = precision_recall_curve(y_test, proba)
        ax_pr.plot(rec, prec, label=f"{name} (AP = {m['pr']:.4f})")

    ax_roc.plot([0, 1], [0, 1], "k--", lw=1, label="chance")
    ax_roc.set_xlabel("False positive rate")
    ax_roc.set_ylabel("True positive rate")
    ax_roc.set_title("ROC — temporal 2017 test set")
    ax_roc.legend()

    ax_pr.axhline(y_test.mean(), color="k", ls="--", lw=1,
                  label=f"prevalence ({y_test.mean():.3f})")
    ax_pr.set_xlabel("Recall")
    ax_pr.set_ylabel("Precision")
    ax_pr.set_title("Precision-Recall — temporal 2017 test set")
    ax_pr.legend()

    fig.suptitle("Honest Mistake — baseline models (untuned)")
    fig.tight_layout()
    FIG_PNG.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG_PNG, dpi=150)
    plt.close(fig)

    # ------------------------------------------------------------------
    # Save models
    # ------------------------------------------------------------------
    logreg_path = MODELS_DIR / "baseline_logreg.joblib"
    xgb_path = MODELS_DIR / "baseline_xgb.joblib"
    joblib.dump(logreg, logreg_path)
    joblib.dump(xgb, xgb_path)

    header(tee, "OUTPUT")
    tee.line(f"  figure:  {FIG_PNG.relative_to(PROJECT_ROOT)}")
    tee.line(f"  models:  {logreg_path.relative_to(PROJECT_ROOT)}")
    tee.line(f"           {xgb_path.relative_to(PROJECT_ROOT)}")
    tee.line(f"Notes saved to {NOTES_TXT.relative_to(PROJECT_ROOT)}")
    tee.close()


if __name__ == "__main__":
    main()
