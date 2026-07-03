"""04_features.py — Honest Mistake project.

Build the feature matrices from train.parquet / test.parquet.
EVERYTHING IS FIT ON TRAIN ONLY (medians, category lists, ordinal maps),
then applied identically to both splits.

Decisions (agreed 2026-07-02):
  - joint/sec_app columns: dropped (100% null in train — no signal to fit)
  - earliest_cr_line: engineered into credit_history_months, raw dropped
  - addr_state: one-hot despite 51 categories
  - Dec-2015+ bureau block: train-median impute + was_missing flag
  - mths_since_* ("event never happened"): sentinel 999 + was_missing flag
  - no scaling (tree models first)

Run:  .venv/bin/python src/04_features.py
"""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
PROCESSED = PROJECT_ROOT / "data" / "processed"
NOTES_TXT = PROJECT_ROOT / "outputs" / "features_notes.txt"

TARGET = "is_default"
SENTINEL = 999

# Row identifiers / free text — no generalizable signal, some near-unique.
ID_TEXT_DROPS = {
    "id":        "row identifier, unique per row",
    "url":       "row identifier (loan URL), unique per row",
    "emp_title": "free text, ~217k uniques",
    "title":     "free text, ~2k uniques — redundant with `purpose`",
    "zip_code":  "masked to 3 digits (e.g. 190xx), 937 uniques",
}

# Split bookkeeping — kept in train/test.parquet but never features.
BOOKKEEPING = ["issue_d", "issue_year"]

# LC only collected these from ~Dec 2015 → ~65% missing in train, missing
# means "not collected for this vintage", not borrower behavior.
BUREAU_2015_BLOCK = [
    "open_acc_6m", "open_act_il", "open_il_12m", "open_il_24m",
    "total_bal_il", "il_util", "open_rv_12m", "open_rv_24m",
    "max_bal_bc", "all_util", "inq_fi", "total_cu_tl", "inq_last_12m",
]

# "Months since <derogatory event>" — missing = event never happened.
# Selected by regex so nothing in the family slips through.
MTHS_SINCE_RX = re.compile(r"^mths_since_")

ONE_HOT_COLS = [
    "home_ownership", "verification_status", "purpose",
    "initial_list_status", "application_type", "disbursement_method",
    "addr_state",  # 51 categories — agreed exception to the <=15 rule
]

GRADE_MAP = {g: i + 1 for i, g in enumerate("ABCDEFG")}  # A=1 ... G=7

EMP_LENGTH_MAP = {
    "< 1 year": 0, "1 year": 1, "2 years": 2, "3 years": 3, "4 years": 4,
    "5 years": 5, "6 years": 6, "7 years": 7, "8 years": 8, "9 years": 9,
    "10+ years": 10,
}


class Tee:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._fh = path.open("w", encoding="utf-8")

    def line(self, text: str = "") -> None:
        print(text)
        self._fh.write(text + "\n")

    def close(self) -> None:
        self._fh.close()


def header(tee: Tee, title: str) -> None:
    tee.line()
    tee.line("=" * 70)
    tee.line(title)
    tee.line("=" * 70)


def sub_grade_to_int(s: pd.Series) -> pd.Series:
    """A1=1 ... G5=35 (letter*5 + digit, ordered by risk)."""
    letter = s.str[0].map(GRADE_MAP)
    digit = s.str[1].astype("int64")
    return ((letter - 1) * 5 + digit).astype("int16")


def credit_history_months(frame: pd.DataFrame) -> pd.Series:
    issue = pd.to_datetime(frame["issue_d"], format="%b-%Y", errors="coerce")
    earliest = pd.to_datetime(frame["earliest_cr_line"], format="%b-%Y", errors="coerce")
    return ((issue.dt.year - earliest.dt.year) * 12
            + (issue.dt.month - earliest.dt.month)).astype("float64")


def main() -> None:
    tee = Tee(NOTES_TXT)
    tee.line("Honest Mistake — feature-prep notes")
    tee.line(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    tee.line("All statistics fit on TRAIN ONLY, applied to both splits.")

    train = pd.read_parquet(PROCESSED / "train.parquet")
    test = pd.read_parquet(PROCESSED / "test.parquet")
    tee.line(f"Loaded train {train.shape}, test {test.shape}")

    y_train = train[TARGET].astype("int8")
    y_test = test[TARGET].astype("int8")

    # ------------------------------------------------------------------
    # Engineered feature (before dropping issue_d / earliest_cr_line)
    # ------------------------------------------------------------------
    header(tee, "ENGINEERED")
    for frame in (train, test):
        frame["credit_history_months"] = credit_history_months(frame)
    n_neg = int((train["credit_history_months"] < 0).sum() + (test["credit_history_months"] < 0).sum())
    n_nan = int(train["credit_history_months"].isna().sum() + test["credit_history_months"].isna().sum())
    tee.line("  credit_history_months = issue_d - earliest_cr_line (months)")
    tee.line(f"    negative values: {n_neg}, unparseable: {n_nan} (raw earliest_cr_line dropped)")

    # ------------------------------------------------------------------
    # Column drops
    # ------------------------------------------------------------------
    header(tee, "DROPPED FROM X")
    drops: dict[str, str] = {}
    drops[TARGET] = "target -> y_train / y_test"
    for c in BOOKKEEPING:
        drops[c] = "split bookkeeping (kept in train/test.parquet, not a feature)"
    drops.update(ID_TEXT_DROPS)
    drops["earliest_cr_line"] = "replaced by engineered credit_history_months"

    joint_cols = [c for c in train.columns
                  if c.startswith("sec_app_") or c.endswith("_joint")]
    for c in joint_cols:
        drops[c] = "joint/secondary-app field — 100% null in train (2014-2016), nothing to fit"

    X_train = train.drop(columns=list(drops))
    X_test = test.drop(columns=list(drops))

    # Zero-variance columns (constant incl. NaN pattern) — fit on train.
    zero_var = [c for c in X_train.columns if X_train[c].nunique(dropna=False) <= 1]
    for c in zero_var:
        drops[c] = "zero variance in train (constant)"
    X_train = X_train.drop(columns=zero_var)
    X_test = X_test.drop(columns=zero_var)

    width = max(len(c) for c in drops)
    for c, reason in drops.items():
        tee.line(f"  {c:<{width}}  {reason}")
    tee.line(f"  ({len(drops)} columns dropped, incl. target/bookkeeping)")

    # ------------------------------------------------------------------
    # Parse string-numeric columns
    # ------------------------------------------------------------------
    header(tee, "PARSED TO NUMERIC")
    for frame in (X_train, X_test):
        frame["term"] = frame["term"].str.strip().str.split(" ").str[0].astype("int16")
        frame["emp_length"] = frame["emp_length"].map(EMP_LENGTH_MAP)  # NaN stays NaN
    tee.line("  term        ' 36 months' -> 36 / 60")
    tee.line("  emp_length  '< 1 year' -> 0 ... '10+ years' -> 10 (missing -> flag + train median)")

    # int_rate / revol_util: spec said strip '%' if strings — they are
    # already float in the parquet, so assert instead of convert.
    for col in ("int_rate", "revol_util"):
        assert pd.api.types.is_numeric_dtype(X_train[col]), f"{col} is not numeric"
    tee.line("  int_rate, revol_util: already numeric in parquet — verified, no conversion needed")

    # ------------------------------------------------------------------
    # Ordinal encoding
    # ------------------------------------------------------------------
    header(tee, "ORDINAL ENCODING")
    for frame in (X_train, X_test):
        frame["grade"] = frame["grade"].map(GRADE_MAP).astype("int8")
        frame["sub_grade"] = sub_grade_to_int(frame["sub_grade"])
    tee.line("  grade      A..G -> 1..7")
    tee.line("  sub_grade  A1..G5 -> 1..35 (both kept; redundancy is harmless for trees)")

    # ------------------------------------------------------------------
    # Missing values — three numeric policies + categorical 'missing'
    # ------------------------------------------------------------------
    header(tee, "MISSING VALUES (numeric)")

    mths_since_cols = sorted(c for c in X_train.columns if MTHS_SINCE_RX.match(c))
    tee.line(f"  A) sentinel {SENTINEL} + was_missing flag — missing = event never happened:")
    for c in mths_since_cols:
        frac = X_train[c].isna().mean() * 100
        tee.line(f"       {c}  ({frac:.1f}% missing in train)")
        for frame in (X_train, X_test):
            frame[c + "_was_missing"] = frame[c].isna().astype("int8")
            frame[c] = frame[c].fillna(SENTINEL)

    bureau_cols = [c for c in BUREAU_2015_BLOCK if c in X_train.columns]
    tee.line("  B) train-median + was_missing flag — bureau fields LC collected only from ~Dec 2015")
    tee.line("     (missing = vintage, not borrower behavior; flag mildly encodes time — accepted):")
    for c in bureau_cols:
        med = X_train[c].median()
        frac = X_train[c].isna().mean() * 100
        tee.line(f"       {c}  ({frac:.1f}% missing in train, median {med:g})")
        for frame in (X_train, X_test):
            frame[c + "_was_missing"] = frame[c].isna().astype("int8")
            frame[c] = frame[c].fillna(med)

    # emp_length: missing is plausibly informative (not stated / unemployed)
    emp_med = X_train["emp_length"].median()
    for frame in (X_train, X_test):
        frame["emp_length_was_missing"] = frame["emp_length"].isna().astype("int8")
        frame["emp_length"] = frame["emp_length"].fillna(emp_med)
    tee.line(f"  C) emp_length: flag + train median ({emp_med:g})")

    tee.line("  D) all other numerics: train median, no flag:")
    other_numeric = [c for c in X_train.columns
                     if pd.api.types.is_numeric_dtype(X_train[c])
                     and X_train[c].isna().any()
                     and not c.endswith("_was_missing")]
    for c in other_numeric:
        med = X_train[c].median()
        frac = X_train[c].isna().mean() * 100
        tee.line(f"       {c}  ({frac:.2f}% missing in train, median {med:g})")
        for frame in (X_train, X_test):
            frame[c] = frame[c].fillna(med)

    # Any test-only missingness left in numeric columns -> train medians.
    test_only = [c for c in X_test.columns
                 if pd.api.types.is_numeric_dtype(X_test[c]) and X_test[c].isna().any()]
    if test_only:
        tee.line("  E) missing in TEST only (imputed with train median):")
        for c in test_only:
            med = X_train[c].median()
            tee.line(f"       {c}  ({X_test[c].isna().mean() * 100:.2f}% missing in test, median {med:g})")
            X_test[c] = X_test[c].fillna(med)

    # ------------------------------------------------------------------
    # One-hot encoding (categories learned from train)
    # ------------------------------------------------------------------
    header(tee, "ONE-HOT ENCODING (train categories; unseen test values -> all-zeros)")
    for col in ONE_HOT_COLS:
        for frame in (X_train, X_test):
            frame[col] = frame[col].fillna("missing")
        train_cats = sorted(X_train[col].unique())
        unseen = sorted(set(X_test[col].unique()) - set(train_cats))
        note = f"  {col}: {len(train_cats)} train categories"
        if unseen:
            note += f"  ** UNSEEN IN TEST -> all-zero rows: {unseen}"
        tee.line(note)
        for frame in (X_train, X_test):
            # mask unseen values to NaN explicitly -> all-zero dummy rows
            vals = frame[col].where(frame[col].isin(train_cats))
            frame[col] = pd.Categorical(vals, categories=train_cats)

    X_train = pd.get_dummies(X_train, columns=ONE_HOT_COLS, dtype="int8")
    X_test = pd.get_dummies(X_test, columns=ONE_HOT_COLS, dtype="int8")
    X_test = X_test[X_train.columns]  # identical column order

    # ------------------------------------------------------------------
    # Final checks + save
    # ------------------------------------------------------------------
    assert list(X_train.columns) == list(X_test.columns)
    assert not X_train.isna().any().any(), "NaNs left in X_train"
    assert not X_test.isna().any().any(), "NaNs left in X_test"
    non_numeric = [c for c in X_train.columns
                   if not pd.api.types.is_numeric_dtype(X_train[c])]
    assert not non_numeric, f"non-numeric columns left: {non_numeric}"

    X_train.to_parquet(PROCESSED / "X_train.parquet", index=False)
    X_test.to_parquet(PROCESSED / "X_test.parquet", index=False)
    y_train.to_frame().to_parquet(PROCESSED / "y_train.parquet", index=False)
    y_test.to_frame().to_parquet(PROCESSED / "y_test.parquet", index=False)

    header(tee, "OUTPUT")
    tee.line(f"  X_train: {X_train.shape[0]:,} x {X_train.shape[1]}")
    tee.line(f"  X_test:  {X_test.shape[0]:,} x {X_test.shape[1]}")
    tee.line(f"  y_train: {len(y_train):,}  (default rate {y_train.mean() * 100:.2f}%)")
    tee.line(f"  y_test:  {len(y_test):,}  (default rate {y_test.mean() * 100:.2f}%)")
    tee.line()
    tee.line("NO SCALING applied — first models are tree-based (XGBoost) and don't")
    tee.line("need it. If a linear/NN baseline is added later, fit a scaler on train.")
    tee.line(f"Notes saved to {NOTES_TXT.relative_to(PROJECT_ROOT)}")
    tee.close()


if __name__ == "__main__":
    main()
