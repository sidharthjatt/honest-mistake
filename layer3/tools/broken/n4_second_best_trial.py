"""N4, broken tool for K6: returns the second-best trial.

Expected outcome: wrong_answer.
"""

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
    row = sorted(trials, key=lambda r: float(r["value"]), reverse=True)[1]
    params = {k[len("params_"):]: _number(v)
              for k, v in row.items() if k.startswith("params_")}
    print(json.dumps({"best_trial": int(row["number"]),
                      "val_roc_auc": float(row["value"]),
                      "params": params}))


if __name__ == "__main__":
    main()
