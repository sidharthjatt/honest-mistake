"""R1, reference tool for K1: training row count from the vintage rows."""

import csv
import json
import os
from pathlib import Path

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    totals = {}
    with (INPUTS / "coverage_profile.csv").open(newline="") as fh:
        for row in csv.DictReader(fh):
            totals[row["feature"]] = totals.get(row["feature"], 0) + int(row["n_rows"])
    counts = set(totals.values())
    if len(counts) != 1:
        raise ValueError("features disagree on the training row count")
    print(json.dumps({"train_rows": counts.pop()}))


if __name__ == "__main__":
    main()
