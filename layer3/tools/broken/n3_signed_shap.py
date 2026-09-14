"""N3, broken tool for K5: ranks by the mean of signed SHAP values.

Expected outcome: wrong_answer.
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    shap = pd.read_parquet(INPUTS / "shap_values.parquet").drop(columns="row_id")
    mean_signed = shap.to_numpy(dtype="float64").mean(axis=0)
    order = np.argsort(-mean_signed, kind="stable")
    print(json.dumps({"ranked": [shap.columns[i] for i in order]}))


if __name__ == "__main__":
    main()
