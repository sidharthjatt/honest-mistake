"""R4, reference tool for K4: ablation ROC-AUC minus the tuned test ROC-AUC."""

import csv
import json
import os
from pathlib import Path

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    baseline = json.loads((INPUTS / "best_params.json").read_text())["test_roc_auc"]
    with (INPUTS / "ablation_cache.csv").open(newline="") as fh:
        deltas = {r["feature"]: float(r["roc_auc"]) - baseline
                  for r in csv.DictReader(fh)}
    print(json.dumps({"delta_roc_auc": deltas}))


if __name__ == "__main__":
    main()
