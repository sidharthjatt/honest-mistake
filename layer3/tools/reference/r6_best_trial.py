"""R6, reference tool for K6: the Optuna trial with the highest value."""

import csv
import json
import os
from pathlib import Path

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def _number(text):
    try:
        return int(text)
    except ValueError:
        return float(text)


def main():
    with (INPUTS / "optuna_trials.csv").open(newline="") as fh:
        trials = [r for r in csv.DictReader(fh) if r["state"] == "COMPLETE"]
    best_value = max(float(r["value"]) for r in trials)
    best = [r for r in trials if float(r["value"]) == best_value]
    if len(best) != 1:
        raise ValueError("more than one trial holds the best value")
    row = best[0]
    params = {k[len("params_"):]: _number(v)
              for k, v in row.items() if k.startswith("params_")}
    print(json.dumps({"best_trial": int(row["number"]),
                      "val_roc_auc": float(row["value"]),
                      "params": params}))


if __name__ == "__main__":
    main()
