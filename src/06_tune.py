"""06_tune.py — Honest Mistake project.

Optuna tuning of XGBoost with a temporal validation split INSIDE train:
    fit  = issue years 2014-2015
    val  = issue year  2016   (objective: maximize val ROC-AUC)
The 2017 test set is not loaded until the study is finished, then the
best params are retrained on full train (2014-2016) and evaluated ONCE.

Run:  .venv/bin/python src/06_tune.py
"""

import json
import time
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import optuna
import pandas as pd
from sklearn.metrics import (
    average_precision_score,
    brier_score_loss,
    confusion_matrix,
    precision_recall_fscore_support,
    roc_auc_score,
)
from xgboost import XGBClassifier

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "data" / "processed"
NOTES_TXT = PROJECT_ROOT / "outputs" / "tuning_notes.txt"
TRIALS_CSV = PROJECT_ROOT / "outputs" / "optuna_trials.csv"
PARAMS_JSON = PROJECT_ROOT / "outputs" / "models" / "best_params.json"
MODEL_PATH = PROJECT_ROOT / "outputs" / "models" / "xgb_tuned.joblib"
MODELS_DIR = PROJECT_ROOT / "outputs" / "models"

RANDOM_STATE = 42
N_TRIALS = 50
FIT_YEARS = {2014, 2015}
VAL_YEAR = 2016
THRESHOLD = 0.5

FIXED_PARAMS = dict(
    tree_method="hist",
    eval_metric="auc",
    random_state=RANDOM_STATE,
    n_jobs=-1,
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


def evaluate(tee: Tee, name: str, y_true, proba) -> dict:
    """Same metric block as 05_baseline.py, for comparability."""
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
    tee.line(f"  PR-AUC (AP):  {pr:.4f}")
    tee.line(f"  Brier score:  {brier:.4f}   (class weighting caveat still applies)")
    tee.line(f"  At threshold {THRESHOLD} (default threshold — untuned):")
    tee.line(f"      TN {cm[0, 0]:>8,}   FP {cm[0, 1]:>8,}")
    tee.line(f"      FN {cm[1, 0]:>8,}   TP {cm[1, 1]:>8,}")
    tee.line(f"    precision: {prec:.4f}   recall: {rec:.4f}   F1: {f1:.4f}")
    return {"roc": roc, "pr": pr, "brier": brier, "f1": f1}


def main() -> None:
    tee = Tee(NOTES_TXT)
    tee.line("Honest Mistake — tuning notes")
    tee.line(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")

    # ------------------------------------------------------------------
    # Load train side only — 2017 test stays untouched during tuning
    # ------------------------------------------------------------------
    X_train = pd.read_parquet(PROCESSED / "X_train.parquet")
    y_train = pd.read_parquet(PROCESSED / "y_train.parquet")["is_default"]
    meta = pd.read_parquet(PROCESSED / "train.parquet",
                           columns=["issue_year", "is_default"])

    # X_train has no issue_year (by design) — align positionally with
    # train.parquet and PROVE the alignment via the target column.
    assert len(meta) == len(X_train), "row count mismatch vs train.parquet"
    assert (meta["is_default"].to_numpy() == y_train.to_numpy()).all(), \
        "row order mismatch between X_train and train.parquet"
    issue_year = meta["issue_year"]

    fit_mask = issue_year.isin(FIT_YEARS).to_numpy()
    val_mask = (issue_year == VAL_YEAR).to_numpy()
    assert (fit_mask | val_mask).all()

    X_fit, y_fit = X_train[fit_mask], y_train[fit_mask]
    X_val, y_val = X_train[val_mask], y_train[val_mask]

    spw_fit = float((y_fit == 0).sum() / (y_fit == 1).sum())
    spw_full = float((y_train == 0).sum() / (y_train == 1).sum())

    header(tee, "TEMPORAL VALIDATION SPLIT (inside train — 2017 never touched)")
    tee.line(f"  fit  (2014-2015): {len(X_fit):>8,} rows, default rate {y_fit.mean() * 100:.2f}%")
    tee.line(f"  val  (2016):      {len(X_val):>8,} rows, default rate {y_val.mean() * 100:.2f}%")
    tee.line(f"  scale_pos_weight fixed for all trials (fit-years ratio): {spw_fit:.3f}")

    # ------------------------------------------------------------------
    # Optuna study
    # ------------------------------------------------------------------
    def objective(trial: optuna.Trial) -> float:
        params = dict(
            max_depth=trial.suggest_int("max_depth", 3, 10),
            learning_rate=trial.suggest_float("learning_rate", 0.01, 0.3, log=True),
            n_estimators=trial.suggest_int("n_estimators", 100, 1000, step=50),
            min_child_weight=trial.suggest_int("min_child_weight", 1, 20),
            subsample=trial.suggest_float("subsample", 0.5, 1.0),
            colsample_bytree=trial.suggest_float("colsample_bytree", 0.5, 1.0),
            reg_alpha=trial.suggest_float("reg_alpha", 1e-8, 10.0, log=True),
            reg_lambda=trial.suggest_float("reg_lambda", 1e-8, 10.0, log=True),
            gamma=trial.suggest_float("gamma", 1e-8, 10.0, log=True),
        )
        model = XGBClassifier(**params, **FIXED_PARAMS, scale_pos_weight=spw_fit)
        model.fit(X_fit, y_fit)
        proba = model.predict_proba(X_val)[:, 1]
        return roc_auc_score(y_val, proba)

    optuna.logging.set_verbosity(optuna.logging.WARNING)
    study = optuna.create_study(
        direction="maximize",
        sampler=optuna.samplers.TPESampler(seed=RANDOM_STATE),
        study_name="xgb_temporal_2016val",
    )

    def progress(study: optuna.Study, trial: optuna.trial.FrozenTrial) -> None:
        print(f"  trial {trial.number + 1:>3}/{N_TRIALS}  "
              f"val AUC {trial.value:.5f}  best {study.best_value:.5f}", flush=True)

    header(tee, f"OPTUNA STUDY — {N_TRIALS} trials, TPE(seed={RANDOM_STATE}), maximize val ROC-AUC")
    t0 = time.perf_counter()
    study.optimize(objective, n_trials=N_TRIALS, callbacks=[progress])
    study_time = time.perf_counter() - t0

    trials_df = study.trials_dataframe()
    trials_df.to_csv(TRIALS_CSV, index=False)

    tee.line(f"  total study time: {study_time / 60:.1f} min "
             f"({study_time / N_TRIALS:.1f}s / trial avg)")
    tee.line(f"  best trial: #{study.best_trial.number}  val ROC-AUC {study.best_value:.5f}")
    tee.line("  best params:")
    for k, v in study.best_params.items():
        tee.line(f"    {k:<18} {v}")
    tee.line(f"  full trial log: {TRIALS_CSV.relative_to(PROJECT_ROOT)}")

    # ------------------------------------------------------------------
    # Retrain best params on FULL train (2014-2016)
    # ------------------------------------------------------------------
    header(tee, "FINAL RETRAIN on full train (2014-2016)")
    tee.line(f"  scale_pos_weight recomputed on full train: {spw_full:.3f} "
             f"(tuning used fit-years {spw_fit:.3f})")
    final = XGBClassifier(**study.best_params, **FIXED_PARAMS,
                          scale_pos_weight=spw_full)
    t0 = time.perf_counter()
    final.fit(X_train, y_train)
    tee.line(f"  train time: {time.perf_counter() - t0:.1f}s")

    # ------------------------------------------------------------------
    # Single evaluation on 2017 test + baseline comparison
    # ------------------------------------------------------------------
    X_test = pd.read_parquet(PROCESSED / "X_test.parquet")
    y_test = pd.read_parquet(PROCESSED / "y_test.parquet")["is_default"]

    proba_tuned = final.predict_proba(X_test)[:, 1]
    m_tuned = evaluate(tee, "XGBoost TUNED", y_test, proba_tuned)

    # Re-score the saved baselines (predict only — no retraining).
    baselines = {}
    for name, fname in (("LogReg (reference)", "baseline_logreg.joblib"),
                        ("XGBoost baseline", "baseline_xgb.joblib")):
        model = joblib.load(MODELS_DIR / fname)
        proba = model.predict_proba(X_test)[:, 1]
        baselines[name] = {
            "roc": roc_auc_score(y_test, proba),
            "pr": average_precision_score(y_test, proba),
            "brier": brier_score_loss(y_test, proba),
        }

    header(tee, "COMPARISON — temporal 2017 test set")
    tee.line(f"  {'model':<22} {'ROC-AUC':>8} {'PR-AUC':>8} {'Brier':>8}")
    for name, m in baselines.items():
        tee.line(f"  {name:<22} {m['roc']:>8.4f} {m['pr']:>8.4f} {m['brier']:>8.4f}")
    tee.line(f"  {'XGBoost TUNED':<22} {m_tuned['roc']:>8.4f} {m_tuned['pr']:>8.4f} {m_tuned['brier']:>8.4f}")
    tee.line()
    gap = study.best_value - m_tuned["roc"]
    tee.line(f"  Generalization check: val(2016) AUC {study.best_value:.4f} -> "
             f"test(2017) AUC {m_tuned['roc']:.4f}  (gap {gap:+.4f})")
    tee.line("  A positive gap is expected drift; a large one would suggest the")
    tee.line("  tuning overfit the 2016 vintage.")

    # ------------------------------------------------------------------
    # Save artifacts
    # ------------------------------------------------------------------
    payload = {
        "generated": datetime.now().isoformat(timespec="seconds"),
        "objective": "maximize val(2016) ROC-AUC",
        "n_trials": N_TRIALS,
        "best_trial": study.best_trial.number,
        "val_roc_auc": study.best_value,
        "test_roc_auc": m_tuned["roc"],
        "scale_pos_weight_fit": spw_fit,
        "scale_pos_weight_full": spw_full,
        "fixed_params": {k: str(v) for k, v in FIXED_PARAMS.items()},
        "best_params": study.best_params,
    }
    PARAMS_JSON.parent.mkdir(parents=True, exist_ok=True)
    PARAMS_JSON.write_text(json.dumps(payload, indent=2))
    joblib.dump(final, MODEL_PATH)

    header(tee, "OUTPUT")
    tee.line(f"  trials:      {TRIALS_CSV.relative_to(PROJECT_ROOT)}")
    tee.line(f"  best params: {PARAMS_JSON.relative_to(PROJECT_ROOT)}")
    tee.line(f"  model:       {MODEL_PATH.relative_to(PROJECT_ROOT)}")
    tee.line(f"Notes saved to {NOTES_TXT.relative_to(PROJECT_ROOT)}")
    tee.close()


if __name__ == "__main__":
    main()
