"""Phase 5, step 2: build the long-format SHAP artefact, then verify it.

The layout is the one frozen in PREREGISTRATION_PHASE5.md, Decision 1:
columns row_id (int64), feature (string, dictionary-encoded) and shap_value
(float32, copied exactly); one row group per feature, 180 in all; features
in shap_values.parquet's column order; rows within each group in that file's
row order. Everything else pyarrow writes is left at its defaults, and the
settings it used are printed from the file's own metadata.

Verification reads the written file back from disk, not the arrays used to
build it. The round trip does not use the row groups: it pivots on the
decoded feature value, keeping file order within each feature, so a file
whose groups were right but whose feature labels were wrong would fail it.
Values are compared bit for bit as float32, which is stricter than equality:
it would also tell 0.0 from -0.0 and would not treat NaN as unequal to
itself.

Nothing is adjusted when a check fails. The script reports and exits 1.

    .venv/bin/python -m scripts.build_phase5_artefact
"""

import hashlib
import sys
from pathlib import Path

import numpy as np
import pyarrow as pa
import pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "outputs" / "agent_cache" / "shap_values.parquet"
TARGET = ROOT / "outputs" / "layer3" / "phase5" / "shap_values_long.parquet"

N_ROWS = 30_000
N_FEATURES = 180


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bits(values: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(values, dtype=np.float32).view(np.uint32)


def build(source: pa.Table) -> None:
    features = [n for n in source.column_names if n != "row_id"]
    row_id = source.column("row_id").combine_chunks()
    names = pa.array(features, type=pa.string())
    schema = pa.schema([
        ("row_id", pa.int64()),
        ("feature", pa.dictionary(pa.int32(), pa.string())),
        ("shap_value", pa.float32()),
    ])
    TARGET.parent.mkdir(parents=True, exist_ok=True)
    with pq.ParquetWriter(TARGET, schema, use_dictionary=["feature"]) as writer:
        for i, name in enumerate(features):
            codes = pa.array(np.full(len(row_id), i, dtype=np.int32))
            group = pa.table({
                "row_id": row_id,
                "feature": pa.DictionaryArray.from_arrays(codes, names),
                "shap_value": source.column(name).combine_chunks(),
            }, schema=schema)
            writer.write_table(group, row_group_size=len(row_id))


def verify(source: pa.Table) -> list[str]:
    problems = []
    features = [n for n in source.column_names if n != "row_id"]
    src_row_id = source.column("row_id").to_numpy()

    meta = pq.ParquetFile(TARGET).metadata
    print(f"written by: {meta.created_by}; format {meta.format_version}; "
          f"{meta.num_rows:,} rows; {meta.num_row_groups} row groups; "
          f"{TARGET.stat().st_size:,} bytes")
    if meta.num_rows != N_ROWS * N_FEATURES:
        problems.append(f"{meta.num_rows:,} rows, expected "
                        f"{N_ROWS * N_FEATURES:,}")
    if meta.num_row_groups != N_FEATURES:
        problems.append(f"{meta.num_row_groups} row groups, expected "
                        f"{N_FEATURES}")

    encodings, compressions, physical = {}, set(), {}
    sizes = set()
    for g in range(meta.num_row_groups):
        rg = meta.row_group(g)
        sizes.add(rg.num_rows)
        for c in range(rg.num_columns):
            col = rg.column(c)
            encodings.setdefault(col.path_in_schema, set()).update(col.encodings)
            physical[col.path_in_schema] = col.physical_type
            compressions.add(col.compression)
    print(f"row-group sizes: {sorted(sizes)}")
    print(f"physical types: {physical}")
    print(f"encodings: { {k: sorted(v) for k, v in encodings.items()} }")
    print(f"compression: {sorted(compressions)}")
    if sizes != {N_ROWS}:
        problems.append(f"row-group sizes {sorted(sizes)}, expected {N_ROWS}")
    if "RLE_DICTIONARY" not in encodings.get("feature", set()):
        problems.append("feature is not dictionary-encoded")

    long = pq.read_table(TARGET)
    print(f"arrow schema read back: {long.schema.types}")
    if long.column_names != ["row_id", "feature", "shap_value"]:
        problems.append(f"columns {long.column_names}")
    if long.schema.field("row_id").type != pa.int64():
        problems.append("row_id is not int64")
    if long.schema.field("shap_value").type != pa.float32():
        problems.append("shap_value is not float32")
    if any(c.null_count for c in long.columns):
        problems.append("the long file holds nulls")

    # Row groups: each holds one feature, in the source's column order.
    pf = pq.ParquetFile(TARGET)
    for g in range(pf.num_row_groups):
        labels = pf.read_row_group(g, columns=["feature"]).column("feature")
        values = set(labels.combine_chunks().dictionary_decode().to_pylist())
        if values != {features[g]}:
            problems.append(f"row group {g} holds {sorted(values)[:3]}, "
                            f"expected {features[g]}")
            break

    # Round trip: pivot on the decoded feature value, keeping file order.
    decoded = long.column("feature").combine_chunks().dictionary_decode()
    labels = np.asarray(decoded.to_pylist(), dtype=object)
    row_id = long.column("row_id").to_numpy()
    shap = long.column("shap_value").to_numpy()
    order_seen = list(dict.fromkeys(labels.tolist()))
    if order_seen != features:
        problems.append("features in the long file, in order of first "
                        "appearance, are not the source's column order")
    wide_names, wide_values, rows_ok, values_ok = [], [], 0, 0
    for name in order_seen:
        mask = labels == name
        ids, vals = row_id[mask], shap[mask]
        wide_names.append(name)
        wide_values.append(vals)
        if len(ids) == len(src_row_id) and np.array_equal(ids, src_row_id):
            rows_ok += 1
        if len(vals) == len(src_row_id) and np.array_equal(
                _bits(vals), _bits(source.column(name).to_numpy())):
            values_ok += 1
    print(f"round trip: {len(wide_names)} features rebuilt; row_id sequence "
          f"identical to the source's for {rows_ok}; float32 bits identical "
          f"to the source column for {values_ok}")
    if wide_names != features:
        problems.append("rebuilt column names or order differ from the source")
    if rows_ok != N_FEATURES:
        problems.append(f"row order matches for {rows_ok} of {N_FEATURES}")
    if values_ok != N_FEATURES:
        problems.append(f"values match for {values_ok} of {N_FEATURES}")
    if rows_ok == N_FEATURES and values_ok == N_FEATURES:
        wide = np.column_stack(wide_values)
        src_wide = np.column_stack([source.column(n).to_numpy()
                                    for n in features])
        same = np.array_equal(_bits(wide), _bits(src_wide))
        print(f"rebuilt wide matrix {wide.shape}, {wide.dtype}: bit-identical "
              f"to the source's 180 feature columns: {same}")
        if not same:
            problems.append("the rebuilt wide matrix differs from the source")
    return problems


def main() -> int:
    if TARGET.exists():
        print(f"{TARGET.name} already exists; it is not overwritten.")
        return 1
    print(f"pyarrow {pa.__version__}, numpy {np.__version__}")
    print(f"source sha256 {_sha256(SOURCE)}")
    source = pq.read_table(SOURCE)
    shape = (source.num_rows, source.num_columns)
    print(f"source: {shape[0]:,} rows, {shape[1]} columns, row_id "
          f"{source.schema.field('row_id').type}")
    if shape != (N_ROWS, N_FEATURES + 1) or source.column_names[0] != "row_id":
        print("the source is not 30,000 rows of row_id plus 180 features.")
        return 1

    build(source)
    problems = verify(source)
    print(f"artefact sha256 {_sha256(TARGET)}")
    for p in problems:
        print(f"PROBLEM: {p}")
    print(f"{len(problems)} problem(s).")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
