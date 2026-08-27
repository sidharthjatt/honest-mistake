"""precompute.py — Honest Mistake, Layer 2.

Layer 1 saved notes and PNGs, not the numbers behind them. This script
computes machine-readable artifacts ONCE so the agent never recomputes
at runtime.

Loading, sampling, and retraining logic is copied from src/07_audit.py
and src/08_fairness_ablation.py so the numbers reproduce Layer 1 exactly.

Artifacts (outputs/agent_cache/):
  shap_values.parquet   full SHAP matrix, 30k sampled test rows + row_id
  shap_global.csv       feature, mean_abs_shap, rank (all 180 features)
  ablation_cache.csv    per-feature drop-one-retrain results (top 20)

Run:  .venv/bin/python -m agent.precompute --quick   (2 ablations)
      .venv/bin/python -m agent.precompute           (full, top 20)
"""

import argparse
import json
import time
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import shap
from sklearn.metrics import average_precision_score, roc_auc_score
from xgboost import XGBClassifier

# ----------------------------------------------------------------------
# Config — mirrors 07_audit.py / 08_fairness_ablation.py
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "data" / "processed"
CACHE = PROJECT_ROOT / "outputs" / "agent_cache"
MODEL_PATH = PROJECT_ROOT / "outputs" / "models" / "xgb_tuned.joblib"
PARAMS_JSON = PROJECT_ROOT / "outputs" / "models" / "best_params.json"

SHAP_VALUES_PARQUET = CACHE / "shap_values.parquet"
SHAP_GLOBAL_CSV = CACHE / "shap_global.csv"
ABLATION_CSV = CACHE / "ablation_cache.csv"

# From 07_audit.py — must match exactly for the numbers to reproduce.
SHAP_SAMPLE = 30_000
RANDOM_STATE = 42

# From 08_fairness_ablation.py — must match exactly.
FIXED_PARAMS = dict(
    tree_method="hist",
    eval_metric="auc",
    random_state=42,
    n_jobs=-1,
)

N_ABLATIONS = 20
QUICK_ABLATIONS = 2

# The canary variant writes to a parallel cache so Layer 1's artefacts,
# which take 13 minutes to regenerate, are never overwritten.
CACHE_CANARY = PROJECT_ROOT / "outputs" / "agent_cache_canary"
MODEL_CANARY = PROJECT_ROOT / "outputs" / "models" / "xgb_canary.joblib"
PARAMS_CANARY = PROJECT_ROOT / "outputs" / "models" / "best_params_canary.json"


def paths(canary: bool) -> dict:
    """Every path this script reads or writes, for one variant."""
    cache = CACHE_CANARY if canary else CACHE
    suffix = "_canary" if canary else ""
    return {
        "cache": cache,
        "model": MODEL_CANARY if canary else MODEL_PATH,
        "params": PARAMS_CANARY if canary else PARAMS_JSON,
        "X_train": PROCESSED / f"X_train{suffix}.parquet",
        "X_test": PROCESSED / f"X_test{suffix}.parquet",
        "shap_values": cache / "shap_values.parquet",
        "shap_global": cache / "shap_global.csv",
        "ablation": cache / "ablation_cache.csv",
    }


def load_test_side(p: dict):
    """Load model + test matrices exactly as 07_audit.py does."""
    model = joblib.load(p["model"])
    X_test = pd.read_parquet(p["X_test"])
    y_test = pd.read_parquet(PROCESSED / "y_test.parquet")["is_default"]
    meta = pd.read_parquet(PROCESSED / "test.parquet",
                           columns=["issue_d", "is_default"])
    assert len(meta) == len(X_test)
    assert (meta["is_default"].to_numpy() == y_test.to_numpy()).all(), \
        "row order mismatch between X_test and test.parquet"
    return model, X_test, y_test


def compute_shap(model, X_test):
    """TreeExplainer on 30k sampled rows, seed 42 — same as 07_audit.py."""
    rng = np.random.default_rng(RANDOM_STATE)
    idx = rng.choice(len(X_test), size=SHAP_SAMPLE, replace=False)
    X_s = X_test.iloc[idx]

    explainer = shap.TreeExplainer(model)
    exp = explainer(X_s)

    values = np.asarray(exp.values)
    assert values.shape == X_s.shape, \
        f"unexpected SHAP shape {values.shape}, expected {X_s.shape}"
    assert not np.isnan(values).any(), "NaNs in the SHAP matrix"

    shap_df = pd.DataFrame(values, columns=X_s.columns)
    # X_test.parquet was written with index=False, so positional indices
    # from rng.choice are also the row labels of the original frame.
    shap_df.insert(0, "row_id", idx)

    mean_abs = pd.Series(np.abs(values).mean(axis=0), index=X_s.columns)
    ranking = mean_abs.sort_values(ascending=False)
    global_df = pd.DataFrame({
        "feature": ranking.index,
        "mean_abs_shap": ranking.to_numpy(),
        "rank": np.arange(1, len(ranking) + 1),
    })
    return shap_df, global_df


def run_ablations(features, X_test, y_test, baseline_roc, baseline_pr,
                  p: dict):
    """Drop-one-column retrain, exactly as 08_fairness_ablation.py does."""
    payload = json.loads(p["params"].read_text())
    best_params = payload["best_params"]
    spw_full = payload["scale_pos_weight_full"]

    X_train = pd.read_parquet(p["X_train"])
    y_train = pd.read_parquet(PROCESSED / "y_train.parquet")["is_default"]

    rows = []
    for i, col in enumerate(features, 1):
        t0 = time.perf_counter()
        model = XGBClassifier(**best_params, **FIXED_PARAMS,
                              scale_pos_weight=spw_full)
        model.fit(X_train.drop(columns=[col]), y_train)
        proba = model.predict_proba(X_test.drop(columns=[col]))[:, 1]
        roc = roc_auc_score(y_test, proba)
        pr = average_precision_score(y_test, proba)
        rows.append({
            "feature": col,
            "roc_auc": roc,
            "pr_auc": pr,
            "delta_roc_auc": roc - baseline_roc,
            "delta_pr_auc": pr - baseline_pr,
        })
        print(f"  [{i}/{len(features)}] {col:<32} "
              f"ROC {roc:.4f} ({roc - baseline_roc:+.4f})  "
              f"PR {pr:.4f} ({pr - baseline_pr:+.4f})  "
              f"[{time.perf_counter() - t0:.0f}s]", flush=True)
    return pd.DataFrame(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--quick", action="store_true",
                        help=f"run only {QUICK_ABLATIONS} ablations")
    parser.add_argument("--canary", action="store_true",
                        help="build the parallel cache for the canary model")
    args = parser.parse_args()

    t_start = time.perf_counter()
    p = paths(args.canary)
    p["cache"].mkdir(parents=True, exist_ok=True)
    if args.canary:
        print("CANARY VARIANT - writing to "
              f"{p['cache'].relative_to(PROJECT_ROOT)}", flush=True)

    print("Loading model and test data...", flush=True)
    model, X_test, y_test = load_test_side(p)

    # Baseline read from the tuned model itself — never hardcoded.
    proba_tuned = model.predict_proba(X_test)[:, 1]
    baseline_roc = roc_auc_score(y_test, proba_tuned)
    baseline_pr = average_precision_score(y_test, proba_tuned)
    print(f"Tuned baseline (from model): ROC-AUC {baseline_roc:.4f}, "
          f"PR-AUC {baseline_pr:.4f}", flush=True)

    print(f"Computing SHAP on {SHAP_SAMPLE:,} sampled rows (seed "
          f"{RANDOM_STATE})...", flush=True)
    t0 = time.perf_counter()
    shap_df, global_df = compute_shap(model, X_test)
    print(f"  done in {time.perf_counter() - t0:.0f}s — "
          f"matrix {shap_df.shape[0]:,} x {shap_df.shape[1] - 1} "
          f"(+ row_id), no NaNs", flush=True)

    shap_df.to_parquet(p["shap_values"], index=False)
    global_df.to_csv(p["shap_global"], index=False)
    print(f"  saved {p['shap_values'].relative_to(PROJECT_ROOT)} "
          f"({p['shap_values'].stat().st_size / 1e6:.1f} MB)")
    print(f"  saved {p['shap_global'].relative_to(PROJECT_ROOT)}")

    print("\nTop 20 by mean |SHAP| (verify against Layer 1 audit_notes.txt):")
    for _, r in global_df.head(20).iterrows():
        print(f"  {int(r['rank']):>2}. {r['feature']:<35} {r['mean_abs_shap']:.4f}")

    n = QUICK_ABLATIONS if args.quick else N_ABLATIONS
    features = global_df.head(n)["feature"].tolist()
    print(f"\nAblations: retraining without each of the top {n} features"
          f"{' (--quick)' if args.quick else ''}...", flush=True)
    abl_df = run_ablations(features, X_test, y_test, baseline_roc,
                           baseline_pr, p)
    abl_df.to_csv(p["ablation"], index=False)
    print(f"  saved {p['ablation'].relative_to(PROJECT_ROOT)}"
          f"{' (PARTIAL — quick run)' if args.quick else ''}")

    print(f"\nTotal wall-clock: {(time.perf_counter() - t_start) / 60:.1f} min")


if __name__ == "__main__":
    main()
