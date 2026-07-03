"""01_data_exploration.py — Honest Mistake project.

Read-only exploration of the Lending Club accepted-loans CSV (1.68 GB).
Never loads the full file: a 5,000-row sample for dtypes/missingness,
and a single chunked pass (2 columns only) for full-file stats.

Run:  .venv/bin/python src/01_data_exploration.py
"""

import re
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "accepted_2007_to_2018Q4.csv"
OUT_TXT = PROJECT_ROOT / "outputs" / "exploration_notes.txt"

SAMPLE_ROWS = 5_000
CHUNKSIZE = 100_000

# Pattern -> one-line reason why it leaks post-origination information.
LEAKAGE_PATTERNS = [
    (r"^total_pymnt",            "cumulative payments received over the loan's life; unknowable at decision time"),
    (r"^total_rec_",             "totals received (principal/interest/fees) after origination"),
    (r"^recoveries$",            "money recovered after charge-off — implies the default already happened"),
    (r"^collection_recovery_fee$", "fee charged on post-charge-off collections"),
    (r"^last_pymnt_",            "describes the most recent payment made during the loan"),
    (r"^next_pymnt_",            "scheduled future payment — only exists for loans already in repayment"),
    (r"^last_fico_",             "FICO score refreshed during the loan, not the score at application"),
    (r"^out_prncp",              "outstanding principal is the loan's current state, not origination info"),
    (r"^settlement",             "debt-settlement details — recorded only after the borrower is in distress"),
    (r"^hardship",               "hardship-plan fields — recorded only after the borrower is in distress"),
    (r"^debt_settlement",        "settlement flag/date — recorded only after the borrower is in distress"),
]


class Tee:
    """Write every line to stdout and to the notes file."""

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
    if not RAW_CSV.exists():
        sys.exit(f"ERROR: dataset not found at {RAW_CSV}")

    tee = Tee(OUT_TXT)
    tee.line(f"Honest Mistake — data exploration notes")
    tee.line(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    tee.line(f"Source: {RAW_CSV.name} ({RAW_CSV.stat().st_size / 1e9:.2f} GB, read-only)")

    # ------------------------------------------------------------------
    # 1. Columns & dtypes (from 5,000-row sample)
    # ------------------------------------------------------------------
    sample = pd.read_csv(RAW_CSV, nrows=SAMPLE_ROWS, low_memory=False)
    header(tee, f"1. COLUMNS & DTYPES (from first {SAMPLE_ROWS:,} rows)")
    tee.line(f"Total columns: {len(sample.columns)}")
    tee.line()
    width = max(len(c) for c in sample.columns)
    for col in sample.columns:
        tee.line(f"  {col:<{width}}  {sample[col].dtype}")

    # ------------------------------------------------------------------
    # 2-4. Single chunked pass over the full file (2 columns only):
    #      loan_status counts, issue_d min/max, total row count
    # ------------------------------------------------------------------
    status_counts: Counter = Counter()
    issue_min = None
    issue_max = None
    n_rows = 0

    reader = pd.read_csv(
        RAW_CSV,
        usecols=["loan_status", "issue_d"],
        chunksize=CHUNKSIZE,
    )
    for chunk in reader:
        n_rows += len(chunk)
        status_counts.update(chunk["loan_status"].fillna("<missing>"))
        dates = pd.to_datetime(chunk["issue_d"], format="%b-%Y", errors="coerce")
        cmin, cmax = dates.min(), dates.max()
        if pd.notna(cmin) and (issue_min is None or cmin < issue_min):
            issue_min = cmin
        if pd.notna(cmax) and (issue_max is None or cmax > issue_max):
            issue_max = cmax

    header(tee, "2. loan_status VALUE COUNTS (full file, chunked)")
    for status, count in status_counts.most_common():
        tee.line(f"  {count:>10,}  ({count / n_rows * 100:5.2f}%)  {status}")

    header(tee, "3. issue_d RANGE (full file, chunked)")
    tee.line(f"  min: {issue_min:%b %Y}" if issue_min is not None else "  min: n/a")
    tee.line(f"  max: {issue_max:%b %Y}" if issue_max is not None else "  max: n/a")
    tee.line("  (planned modeling window: 2014-2017)")

    header(tee, "4. TOTAL ROW COUNT (full file, chunked)")
    tee.line(f"  {n_rows:,} rows")

    # ------------------------------------------------------------------
    # 5. Missing-value % — top 20 (sample-based estimate)
    # ------------------------------------------------------------------
    header(tee, f"5. TOP 20 MOST-MISSING COLUMNS (estimate from {SAMPLE_ROWS:,}-row sample)")
    missing = sample.isna().mean().sort_values(ascending=False).head(20)
    for col, frac in missing.items():
        tee.line(f"  {frac * 100:6.2f}%  {col}")

    # ------------------------------------------------------------------
    # 6. Leakage suspects
    # ------------------------------------------------------------------
    header(tee, "6. LEAKAGE SUSPECTS (post-loan info)")
    tee.line("Columns that describe what happened AFTER origination — they must")
    tee.line("be excluded from any model that predicts default at decision time.")
    tee.line()
    flagged = set()
    for pattern, reason in LEAKAGE_PATTERNS:
        rx = re.compile(pattern)
        for col in sample.columns:
            if col in flagged or not rx.match(col):
                continue
            flagged.add(col)
            tee.line(f"  {col:<{width}}  {reason}")
    tee.line()
    tee.line(f"Total flagged: {len(flagged)} of {len(sample.columns)} columns")

    tee.line()
    tee.line(f"Notes saved to {OUT_TXT.relative_to(PROJECT_ROOT)}")
    tee.close()


if __name__ == "__main__":
    main()
