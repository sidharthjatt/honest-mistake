"""N5, broken tool for K2: counts correctly but prints a bare number.

Expected outcome: bad_output.
"""

import os
from pathlib import Path

import pyarrow.parquet as pq

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    names = pq.read_schema(INPUTS / "shap_values.parquet").names
    print(len([n for n in names if n != "row_id"]))


if __name__ == "__main__":
    main()
