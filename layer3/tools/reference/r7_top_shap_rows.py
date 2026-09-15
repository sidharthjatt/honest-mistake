"""R7, reference tool for get_top_shap_rows (V1, V3, V4).

Uses only what the code-generation prompt tells the model: the arguments
file, the artefact's name and its three columns. It reads the whole file
and relies on nothing about its layout, so it meets the memory limit under
the same conditions as the generated tool.

Ranks by signed SHAP value, highest first (Decision 3). A name with no rows
in the feature column returns found=false.
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
    order = np.argsort(-values, kind="stable")[:max(0, min(top_n, len(values)))]
    print(json.dumps({"found": True, "rows": [
        {"row_id": int(ids[i]), "shap_value": float(values[i])} for i in order
    ]}))


if __name__ == "__main__":
    main()
