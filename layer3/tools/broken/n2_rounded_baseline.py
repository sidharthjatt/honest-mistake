"""N2, broken tool for K4: subtracts the rounded 0.7296 from tuning_notes.txt.

Expected outcome: wrong_answer.
"""

import csv
import json
import os
from pathlib import Path

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))

BASELINE_AS_PRINTED = 0.7296


def main():
    with (INPUTS / "ablation_cache.csv").open(newline="") as fh:
        deltas = {r["feature"]: float(r["roc_auc"]) - BASELINE_AS_PRINTED
                  for r in csv.DictReader(fh)}
    print(json.dumps({"delta_roc_auc": deltas}))


if __name__ == "__main__":
    main()
