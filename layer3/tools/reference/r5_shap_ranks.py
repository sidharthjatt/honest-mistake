"""R5, reference tool for K5: features ordered by mean absolute SHAP value."""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    shap = pd.read_parquet(INPUTS / "shap_values.parquet").drop(columns="row_id")
    mean_abs = np.abs(shap.to_numpy(dtype="float64")).mean(axis=0)
    order = np.argsort(-mean_abs, kind="stable")
    print(json.dumps({"ranked": [shap.columns[i] for i in order]}))


if __name__ == "__main__":
    main()
