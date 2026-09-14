"""R2, reference tool for K2: number of features in the SHAP matrix."""

import json
import os
from pathlib import Path

import pyarrow.parquet as pq

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    names = pq.read_schema(INPUTS / "shap_values.parquet").names
    features = [n for n in names if n != "row_id"]
    print(json.dumps({"n_features": len(features)}))


if __name__ == "__main__":
    main()
