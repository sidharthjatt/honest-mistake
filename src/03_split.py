"""03_split.py — Honest Mistake project.

Temporal train/test split of the clean modeling dataset.
    train = issue years 2014-2016
    test  = issue year  2017

No feature engineering, imputation, or scaling here — those must be
fit on train only, in a later script. Only added column: issue_year.

Run:  .venv/bin/python src/03_split.py
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
IN_PARQUET = PROJECT_ROOT / "data" / "processed" / "loans_2014_2017.parquet"
TRAIN_PARQUET = PROJECT_ROOT / "data" / "processed" / "train.parquet"
TEST_PARQUET = PROJECT_ROOT / "data" / "processed" / "test.parquet"
NOTES_TXT = PROJECT_ROOT / "outputs" / "split_notes.txt"

TRAIN_YEARS = {2014, 2015, 2016}
TEST_YEAR = 2017


class Tee:
    """Write every line to stdout and to a notes file."""

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


def main() -> None:
    if not IN_PARQUET.exists():
        raise SystemExit(f"ERROR: input not found at {IN_PARQUET} — run 02_build_dataset.py first")

    tee = Tee(NOTES_TXT)
    tee.line("Honest Mistake — temporal split notes")
    tee.line(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    tee.line(f"Source: {IN_PARQUET.relative_to(PROJECT_ROOT)}")

    df = pd.read_parquet(IN_PARQUET)

    issue_dt = pd.to_datetime(df["issue_d"], format="%b-%Y", errors="coerce")
    if issue_dt.isna().any():
        raise SystemExit(f"ERROR: {issue_dt.isna().sum()} rows failed issue_d parsing")
    df["issue_year"] = issue_dt.dt.year.astype("int16")

    expected_years = TRAIN_YEARS | {TEST_YEAR}
    actual_years = set(df["issue_year"].unique())
    if actual_years != expected_years:
        raise SystemExit(f"ERROR: unexpected issue years {actual_years - expected_years}")

    train = df[df["issue_year"].isin(TRAIN_YEARS)]
    test = df[df["issue_year"] == TEST_YEAR]
    assert len(train) + len(test) == len(df)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    header(tee, "SPLIT (temporal — no shuffling)")
    tee.line(f"  train (2014-2016):  {len(train):>10,} rows  ({len(train) / len(df) * 100:5.2f}%)")
    tee.line(f"  test  (2017):       {len(test):>10,} rows  ({len(test) / len(df) * 100:5.2f}%)")

    header(tee, "DEFAULT RATE — train vs test")
    tr_rate = train["is_default"].mean() * 100
    te_rate = test["is_default"].mean() * 100
    tee.line(f"  train:  {tr_rate:5.2f}%")
    tee.line(f"  test:   {te_rate:5.2f}%")
    tee.line(f"  delta:  {te_rate - tr_rate:+5.2f} pp")
    tee.line("  Note: a gap here is expected — vintage mix and borrower composition")
    tee.line("  shift over time. This is realistic deployment drift, not a data bug.")

    header(tee, "ISSUE-YEAR DISTRIBUTION (count / share / default rate)")
    for name, part in (("train", train), ("test", test)):
        tee.line(f"  {name}:")
        by_year = part.groupby("issue_year")["is_default"].agg(["size", "mean"])
        for year, row in by_year.iterrows():
            tee.line(f"    {year}:  {int(row['size']):>9,}  "
                     f"({row['size'] / len(part) * 100:5.2f}% of {name})  "
                     f"default rate {row['mean'] * 100:5.2f}%")

    # ------------------------------------------------------------------
    # Save
    # ------------------------------------------------------------------
    train.to_parquet(TRAIN_PARQUET, index=False)
    test.to_parquet(TEST_PARQUET, index=False)

    header(tee, "OUTPUT")
    tee.line(f"  {TRAIN_PARQUET.relative_to(PROJECT_ROOT)}  ({TRAIN_PARQUET.stat().st_size / 1e6:.1f} MB)")
    tee.line(f"  {TEST_PARQUET.relative_to(PROJECT_ROOT)}  ({TEST_PARQUET.stat().st_size / 1e6:.1f} MB)")
    tee.line()
    tee.line("No feature engineering / imputation / scaling performed — fit on train only, later.")

    header(tee, "KNOWN LIMITATION — resolution/survivorship bias in the 2017 test set")
    tee.line("  The dataset ends Dec 2018, but 2017 vintages had not matured by then:")
    tee.line("  a 36-month loan issued mid-2017 could only be resolved that early by")
    tee.line("  prepaying in full or defaulting fast. Keeping only resolved loans")
    tee.line("  (Fully Paid / Charged Off) therefore overrepresents early payoffs and")
    tee.line("  early defaults in the 2017 test set. 2014-2015 vintages are fully")
    tee.line("  matured and unaffected; 2016 is mildly affected.")
    tee.line(f"  Consequence: the {te_rate:.2f}% test default rate is not the true 2017 vintage")
    tee.line("  rate, and test metrics should be read with this bias in mind.")
    tee.line("  TODO: carry this into the README limitations section.")

    tee.line()
    tee.line(f"Notes saved to {NOTES_TXT.relative_to(PROJECT_ROOT)}")
    tee.close()


if __name__ == "__main__":
    main()
