"""N17, broken tool: treats a column name as a feature (V4).

Checks the requested name against the file's column names before the
feature column. row_id is a column of the file, so for row_id it ranks that
column's own values and returns found=true with rows, where the name is not
one of the model's features. Any other name is handled as R7 handles it.

Expected outcome on V4: wrong_answer.
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
    if feature in table.column_names:
        ids = table.column("row_id").to_numpy()
        values = table.column(feature).to_numpy()
    else:
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
