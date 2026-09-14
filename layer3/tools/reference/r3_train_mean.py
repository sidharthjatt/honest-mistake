"""R3, reference tool for K3: train mean as the row-weighted vintage mean."""

import csv
import json
import os
from pathlib import Path

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    weighted, rows = {}, {}
    with (INPUTS / "coverage_profile.csv").open(newline="") as fh:
        for row in csv.DictReader(fh):
            n = int(row["n_rows"])
            f = row["feature"]
            weighted[f] = weighted.get(f, 0.0) + n * float(row["mean"])
            rows[f] = rows.get(f, 0) + n
    print(json.dumps({"train_mean": {f: weighted[f] / rows[f] for f in weighted}}))


if __name__ == "__main__":
    main()
