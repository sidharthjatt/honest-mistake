"""N15, broken tool: ranks by absolute SHAP value (V1).

Identical to R7 except that rows are ranked by magnitude, reading "largest
SHAP attribution" the other way. It returns the signed values of the rows it
picks. For all_util, 9 of the 10 largest magnitudes are negative, so the
rows it returns are not the 10 largest signed values.

Expected outcome on V1: wrong_answer.
"""

import json
import os
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.compute as pc
import pyarrow.parquet as pq

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    args = json.loads((INPUTS / "arguments.json").read_text())
    feature, top_n = args["feature"], args["top_n"]

    table = pq.read_table(INPUTS / "shap_values_long.parquet")
    labels = pc.cast(table.column("feature"), pa.string())
    rows = table.filter(pc.equal(labels, pa.scalar(feature, pa.string())))
    if rows.num_rows == 0:
        print(json.dumps({"found": False}))
        return

    ids = rows.column("row_id").to_numpy()
    values = rows.column("shap_value").to_numpy()
    order = np.argsort(-np.abs(values), kind="stable")[:max(0, min(top_n, len(values)))]
    print(json.dumps({"found": True, "rows": [
        {"row_id": int(ids[i]), "shap_value": float(values[i])} for i in order
    ]}))


if __name__ == "__main__":
    main()
