"""Validation cases V1, V3 and V4, as frozen in PREREGISTRATION_PHASE5.md.

Each is a question in the Phase 3 sense, so the same runners and the same
classify() serve them. Importing this module adds them to QUESTIONS.

Every case mounts the long-format artefact recorded in amendment A2. The
expected answers are not read from that artefact. They are read from
shap_values.parquet at validation time, after the four confirmations the
document requires; if any fails, AnswerSourceError is raised and no verdict
is given.

The output contract checked in check_shape() is Decision 2's, which is ours,
not the spec's. A breach of it is bad_output. Everything else in a case's
pass rule is compare(), and a breach there is wrong_answer.
"""

from __future__ import annotations

import math

import numpy as np
import pyarrow.parquet as pq

from layer3.questions import (OUTPUTS, QUESTIONS, SHAP_VALUES,
                              AnswerSourceError, BadShape, Question, _copy,
                              _is_int, _is_number)

ARTEFACT = OUTPUTS / "layer3" / "phase5" / "shap_values_long.parquet"
ARTEFACT_SHA256 = "07ff508bba87ec97ee4fe46f5577ce065076de865279dc6a6cce9e2bf864cc0d"
N_ROWS = 30_000


def _confirm_source():
    """The document's four confirmations, before any verdict."""
    if not SHAP_VALUES.exists():
        raise AnswerSourceError(f"{SHAP_VALUES.name} is missing.")
    meta = pq.ParquetFile(SHAP_VALUES)
    names = meta.schema_arrow.names
    if meta.metadata.num_rows != N_ROWS:
        raise AnswerSourceError(f"{SHAP_VALUES.name} holds "
                                f"{meta.metadata.num_rows} rows, not {N_ROWS}.")
    if "all_util" not in names:
        raise AnswerSourceError("all_util is not a column of the source.")
    if "addr_state" in names:
        raise AnswerSourceError("addr_state is a column of the source.")
    if "row_id" not in names:
        raise AnswerSourceError("row_id is not a column of the source.")


def _f32(value) -> np.float32:
    with np.errstate(over="ignore"):
        return np.float32(float(value))


class _Phase5Question(Question):
    ARGUMENTS: dict = {}

    def prepare(self, dest):
        _copy(ARTEFACT, dest)

    def check_shape(self, output, answer):
        if "found" not in output:
            raise BadShape("output has no found key.")
        if not isinstance(output["found"], bool):
            raise BadShape("found is not a boolean.")
        rows = output.get("rows")
        if not output["found"]:
            if "rows" in output and rows != []:
                raise BadShape("found is false and rows is present but not "
                               "an empty list.")
            return
        if "rows" not in output:
            raise BadShape("found is true and rows is missing.")
        if not isinstance(rows, list):
            raise BadShape("rows is not a list.")
        for i, row in enumerate(rows):
            if not isinstance(row, dict):
                raise BadShape(f"rows[{i}] is not an object.")
            if "row_id" not in row or not _is_int(row["row_id"]):
                raise BadShape(f"rows[{i}].row_id is missing or not an "
                               f"integer.")
            value = row.get("shap_value")
            if not _is_number(value):
                raise BadShape(f"rows[{i}].shap_value is missing or not a "
                               f"number.")
            try:
                finite = math.isfinite(float(value))
            except OverflowError:
                finite = False
            if not finite:
                raise BadShape(f"rows[{i}].shap_value is not finite.")


class V1TopRows(_Phase5Question):
    qid = "V1"
    ARGUMENTS = {"feature": "all_util", "top_n": 10}
    N = 10

    def answer(self):
        _confirm_source()
        table = pq.read_table(SHAP_VALUES, columns=["row_id", "all_util"])
        ids = table.column("row_id").to_numpy()
        values = table.column("all_util").to_numpy().astype(np.float32)
        by_row = dict(zip(ids.tolist(), values))
        largest = sorted(values, reverse=True)[:self.N]
        return by_row, largest

    def compare(self, output, answer):
        by_row, largest = answer
        if not output["found"]:
            return ["found is false, expected true"]
        rows = output["rows"]
        misses = []
        if len(rows) != self.N:
            misses.append(f"rows has {len(rows)} entries, expected {self.N}")
        ids = [r["row_id"] for r in rows]
        if len(ids) != len(set(ids)):
            misses.append("a row_id appears more than once")
        returned = [_f32(r["shap_value"]) for r in rows]
        unknown = [i for i in ids if i not in by_row]
        if unknown:
            misses.append(f"{len(unknown)} row_id(s) are not rows of the "
                          f"source, first {unknown[0]}")
        wrong = [(i, v) for i, v in zip(ids, returned)
                 if i in by_row and v != by_row[i]]
        if wrong:
            i, v = wrong[0]
            misses.append(f"{len(wrong)} returned value(s) differ from the "
                          f"row's all_util value, first row_id {i} (returned "
                          f"{float(v)!r}, source {float(by_row[i])!r})")
        if any(a < b for a, b in zip(returned, returned[1:])):
            misses.append("returned values are not in non-increasing order")
        if sorted(returned) != sorted(largest):
            misses.append("returned values are not, as a multiset, the "
                          f"{self.N} largest signed all_util values")
        return misses


class _NotFound(_Phase5Question):
    def answer(self):
        _confirm_source()
        return None

    def compare(self, output, answer):
        if output["found"]:
            return [f"found is true for {self.ARGUMENTS['feature']}, "
                    f"expected false"]
        return []


class V3NotAFeature(_NotFound):
    qid = "V3"
    ARGUMENTS = {"feature": "addr_state", "top_n": 10}


class V4Identifier(_NotFound):
    qid = "V4"
    ARGUMENTS = {"feature": "row_id", "top_n": 10}


# Added to the shared registry so the Phase 3 runners and classify() serve
# these cases unchanged. K1 to K6 are untouched.
QUESTIONS.update({q.qid: q for q in (V1TopRows(), V3NotAFeature(),
                                     V4Identifier())})
