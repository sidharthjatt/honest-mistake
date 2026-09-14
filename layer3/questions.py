"""Known-answer questions K1 to K6, as frozen in PREREGISTRATION_PHASE3.md.

Each question does three things: writes the files a tool is given, reads
the right answer, and decides whether a tool's output matches it.

Answers are read from the artefacts the document names, every time, and
checked against the values the document froze. If an artefact no longer
says what the document says, the question raises AnswerSourceError and no
verdict is given. Validating against a moved target would be worse than
not validating.

Inputs that are part of an artefact are copied as text, row for row, with
the csv module. Reading them into pandas and writing them back would
re-serialise every float, and pandas' default parser is not round-trip
exact (K6 in the document), so a tool would be handed different digits
from the ones on disk.
"""

from __future__ import annotations

import csv
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUTS = ROOT / "outputs"
CACHE = OUTPUTS / "agent_cache"

COVERAGE_CSV = CACHE / "coverage_profile.csv"
ABLATION_CSV = CACHE / "ablation_cache.csv"
SHAP_VALUES = CACHE / "shap_values.parquet"
SHAP_GLOBAL_CSV = CACHE / "shap_global.csv"
OPTUNA_CSV = OUTPUTS / "optuna_trials.csv"
BEST_PARAMS = OUTPUTS / "models" / "best_params.json"
SPLIT_NOTES = OUTPUTS / "split_notes.txt"
BASELINE_NOTES = OUTPUTS / "baseline_notes.txt"

VINTAGES = ("2014", "2015", "2016")


class AnswerSourceError(RuntimeError):
    """An answer source is missing or no longer says what the document froze."""


class BadShape(ValueError):
    """The tool's output is not the object the question asks for."""


# ---------------------------------------------------------------- helpers

def _rows(path: Path) -> list[dict]:
    if not path.exists():
        raise AnswerSourceError(f"{path.name} is missing.")
    with path.open(newline="") as fh:
        return list(csv.DictReader(fh))


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row[k] for k in fields})


def _copy(src: Path, dest_dir: Path) -> None:
    if not src.exists():
        raise AnswerSourceError(f"{src.name} is missing.")
    shutil.copyfile(src, dest_dir / src.name)


def _search(path: Path, pattern: str) -> str:
    if not path.exists():
        raise AnswerSourceError(f"{path.name} is missing.")
    match = re.search(pattern, path.read_text())
    if not match:
        raise AnswerSourceError(f"{path.name} no longer contains the line "
                                f"the answer is read from.")
    return match.group(1)


def _frozen(what: str, found, frozen) -> None:
    if found != frozen:
        raise AnswerSourceError(f"{what}: the artefact says {found!r}, the "
                                f"document froze {frozen!r}.")


def _is_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _keys(obj, expected, where: str) -> None:
    if not isinstance(obj, dict):
        raise BadShape(f"{where} is not an object.")
    missing = sorted(set(expected) - set(obj))
    extra = sorted(set(obj) - set(expected))
    if missing or extra:
        raise BadShape(f"{where} has {len(missing)} missing and {len(extra)} "
                       f"unexpected keys (missing {missing[:3]}, unexpected "
                       f"{extra[:3]}).")


def _numeric_misses(returned: dict, expected: dict, tol: float,
                    label: str) -> list[str]:
    """One summary line if any item is outside an absolute tolerance."""
    misses = [(abs(float(returned[k]) - v), k) for k, v in expected.items()]
    over = [m for m in misses if m[0] > tol]
    if not over:
        return []
    size, key = max(over)
    return [f"{len(over)} of {len(expected)} {label} differ by more than "
            f"{tol:g}; largest miss {size:.6g} on {key} (returned "
            f"{returned[key]!r}, expected {expected[key]!r})"]


# ---------------------------------------------------------------- questions

class Question:
    qid = ""

    def prepare(self, dest: Path) -> None:
        raise NotImplementedError

    def answer(self):
        raise NotImplementedError

    def check_shape(self, output: dict, answer) -> None:
        raise NotImplementedError

    def compare(self, output: dict, answer) -> list[str]:
        """Descriptions of every failed match rule. Empty means a pass."""
        raise NotImplementedError


class K1TrainRows(Question):
    qid = "K1"
    FROZEN = 891_742

    def prepare(self, dest):
        rows = [r for r in _rows(COVERAGE_CSV) if r["scope"] in VINTAGES]
        _write(dest / COVERAGE_CSV.name, ["feature", "scope", "n_rows"], rows)

    def answer(self):
        split = _search(SPLIT_NOTES, r"train \(2014-2016\):\s+([\d,]+) rows")
        _frozen("split_notes.txt train rows", int(split.replace(",", "")),
                self.FROZEN)
        base = _search(BASELINE_NOTES, r"X_train \((\d+), \d+\)")
        _frozen("baseline_notes.txt X_train rows", int(base), self.FROZEN)
        train = {int(r["n_rows"]) for r in _rows(COVERAGE_CSV)
                 if r["scope"] == "train"}
        _frozen("coverage_profile.csv train n_rows", train, {self.FROZEN})
        return self.FROZEN

    def check_shape(self, output, answer):
        _keys(output, ["train_rows"], "output")
        if not _is_int(output["train_rows"]):
            raise BadShape("train_rows is not an integer.")

    def compare(self, output, answer):
        if output["train_rows"] == answer:
            return []
        return [f"train_rows is {output['train_rows']:,}, expected {answer:,}"]


class K2FeatureCount(Question):
    qid = "K2"
    FROZEN = 180

    def prepare(self, dest):
        _copy(SHAP_VALUES, dest)

    def answer(self):
        test = _search(BASELINE_NOTES, r"X_test \(\d+, (\d+)\)")
        _frozen("baseline_notes.txt X_test columns", int(test), self.FROZEN)
        return self.FROZEN

    def check_shape(self, output, answer):
        _keys(output, ["n_features"], "output")
        if not _is_int(output["n_features"]):
            raise BadShape("n_features is not an integer.")

    def compare(self, output, answer):
        if output["n_features"] == answer:
            return []
        return [f"n_features is {output['n_features']}, expected {answer}"]


class K3TrainMean(Question):
    qid = "K3"
    TOL = 1e-6
    N_FEATURES = 180

    def prepare(self, dest):
        rows = [r for r in _rows(COVERAGE_CSV) if r["scope"] in VINTAGES]
        _write(dest / COVERAGE_CSV.name,
               ["feature", "scope", "n_rows", "mean"], rows)

    def answer(self):
        train = [r for r in _rows(COVERAGE_CSV) if r["scope"] == "train"]
        if any(r["mean"] == "" for r in train):
            raise AnswerSourceError("coverage_profile.csv has a train row "
                                    "with no mean.")
        _frozen("coverage_profile.csv train features", len(train),
                self.N_FEATURES)
        return {r["feature"]: float(r["mean"]) for r in train}

    def check_shape(self, output, answer):
        _keys(output, ["train_mean"], "output")
        _keys(output["train_mean"], answer, "train_mean")
        if not all(_is_number(v) for v in output["train_mean"].values()):
            raise BadShape("train_mean holds a value that is not a number.")

    def compare(self, output, answer):
        return _numeric_misses(output["train_mean"], answer, self.TOL,
                               "features")


class K4AblationDelta(Question):
    qid = "K4"
    TOL = 1e-12
    N_FEATURES = 20

    def prepare(self, dest):
        _write(dest / ABLATION_CSV.name, ["feature", "roc_auc"],
               _rows(ABLATION_CSV))
        _copy(BEST_PARAMS, dest)

    def answer(self):
        rows = _rows(ABLATION_CSV)
        _frozen("ablation_cache.csv rows", len(rows), self.N_FEATURES)
        return {r["feature"]: float(r["delta_roc_auc"]) for r in rows}

    def check_shape(self, output, answer):
        _keys(output, ["delta_roc_auc"], "output")
        _keys(output["delta_roc_auc"], answer, "delta_roc_auc")
        if not all(_is_number(v) for v in output["delta_roc_auc"].values()):
            raise BadShape("delta_roc_auc holds a value that is not a number.")

    def compare(self, output, answer):
        return _numeric_misses(output["delta_roc_auc"], answer, self.TOL,
                               "features")


class K5ShapRanks(Question):
    qid = "K5"
    N_NONZERO = 173
    N_ZERO = 7

    def prepare(self, dest):
        _copy(SHAP_VALUES, dest)

    def answer(self):
        rows = sorted(_rows(SHAP_GLOBAL_CSV), key=lambda r: int(r["rank"]))
        _frozen("shap_global.csv ranks",
                [int(r["rank"]) for r in rows], list(range(1, 181)))
        nonzero = [r["feature"] for r in rows if float(r["mean_abs_shap"]) > 0]
        zero = {r["feature"] for r in rows if float(r["mean_abs_shap"]) == 0}
        _frozen("shap_global.csv nonzero features", len(nonzero),
                self.N_NONZERO)
        _frozen("shap_global.csv zero features", len(zero), self.N_ZERO)
        _frozen("nonzero features hold the top ranks",
                [r["feature"] for r in rows[:self.N_NONZERO]], nonzero)
        return nonzero, zero

    def check_shape(self, output, answer):
        _keys(output, ["ranked"], "output")
        ranked = output["ranked"]
        nonzero, zero = answer
        if not isinstance(ranked, list) or \
                not all(isinstance(f, str) for f in ranked):
            raise BadShape("ranked is not a list of feature names.")
        if len(ranked) != len(set(ranked)):
            raise BadShape("ranked names a feature more than once.")
        if set(ranked) != set(nonzero) | zero:
            raise BadShape(f"ranked holds {len(ranked)} names that are not "
                           f"the 180 features.")

    def compare(self, output, answer):
        ranked = output["ranked"]
        nonzero, zero = answer
        misses = []
        wrong = [i for i in range(self.N_NONZERO) if ranked[i] != nonzero[i]]
        if wrong:
            i = wrong[0]
            misses.append(f"{len(wrong)} of positions 1-{self.N_NONZERO} "
                          f"differ; first at position {i + 1} (returned "
                          f"{ranked[i]}, expected {nonzero[i]})")
        tail = set(ranked[self.N_NONZERO:])
        if tail != zero:
            misses.append(f"positions {self.N_NONZERO + 1}-180 hold "
                          f"{len(tail - zero)} features outside the zero set")
        return misses


class K6BestTrial(Question):
    qid = "K6"
    FROZEN_TRIAL = 21
    VAL_TOL = 1e-12
    PARAM_REL_TOL = 1e-12
    INT_PARAMS = ("max_depth", "n_estimators", "min_child_weight")

    def prepare(self, dest):
        _copy(OPTUNA_CSV, dest)

    def answer(self):
        if not BEST_PARAMS.exists():
            raise AnswerSourceError(f"{BEST_PARAMS.name} is missing.")
        bp = json.loads(BEST_PARAMS.read_text())
        _frozen("best_params.json best_trial", bp["best_trial"],
                self.FROZEN_TRIAL)
        _frozen("best_params.json parameter count", len(bp["best_params"]), 9)
        return {"best_trial": bp["best_trial"],
                "val_roc_auc": bp["val_roc_auc"],
                "params": bp["best_params"]}

    def check_shape(self, output, answer):
        _keys(output, ["best_trial", "val_roc_auc", "params"], "output")
        if not _is_int(output["best_trial"]):
            raise BadShape("best_trial is not an integer.")
        if not _is_number(output["val_roc_auc"]):
            raise BadShape("val_roc_auc is not a number.")
        _keys(output["params"], answer["params"], "params")
        for name, value in output["params"].items():
            if name in self.INT_PARAMS and not _is_int(value):
                raise BadShape(f"params.{name} is not an integer.")
            if not _is_number(value):
                raise BadShape(f"params.{name} is not a number.")

    def compare(self, output, answer):
        misses = []
        if output["best_trial"] != answer["best_trial"]:
            misses.append(f"best_trial is {output['best_trial']}, expected "
                          f"{answer['best_trial']}")
        val_miss = abs(output["val_roc_auc"] - answer["val_roc_auc"])
        if val_miss > self.VAL_TOL:
            misses.append(f"val_roc_auc off by {val_miss:.6g} (returned "
                          f"{output['val_roc_auc']!r}, expected "
                          f"{answer['val_roc_auc']!r})")
        for name, expected in answer["params"].items():
            got = output["params"][name]
            if name in self.INT_PARAMS:
                if got != expected:
                    misses.append(f"params.{name} is {got}, expected {expected}")
            elif abs(got - expected) > self.PARAM_REL_TOL * abs(expected):
                misses.append(f"params.{name} is {got!r}, expected "
                              f"{expected!r}")
        return misses


QUESTIONS: dict[str, Question] = {q.qid: q for q in (
    K1TrainRows(), K2FeatureCount(), K3TrainMean(),
    K4AblationDelta(), K5ShapRanks(), K6BestTrial(),
)}
