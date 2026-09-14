"""N1, broken tool for K3: averages the vintage means without weighting by n_rows.

Expected outcome: wrong_answer.
"""

import csv
import json
import os
from pathlib import Path

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    means = {}
    with (INPUTS / "coverage_profile.csv").open(newline="") as fh:
        for row in csv.DictReader(fh):
            means.setdefault(row["feature"], []).append(float(row["mean"]))
    print(json.dumps({"train_mean": {f: sum(v) / len(v) for f, v in means.items()}}))


if __name__ == "__main__":
    main()
