"""02_build_dataset.py — Honest Mistake project.

Build the clean modeling dataset from the raw Lending Club CSV.
The raw CSV is read-only; output goes to data/processed/.

Filters: loan_status in {Fully Paid, Charged Off}, issue year 2014-2017.
Target:  is_default = 1 for Charged Off, 0 for Fully Paid.
Drops:   37 leakage columns, member_id/desc, loan_status (label source),
         and anything 100% null in the filtered data.

Run:  .venv/bin/python src/02_build_dataset.py
"""

from datetime import datetime
from pathlib import Path

import pandas as pd

# ----------------------------------------------------------------------
# Config
# ----------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_CSV = PROJECT_ROOT / "data" / "raw" / "accepted_2007_to_2018Q4.csv"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUT_PARQUET = PROCESSED_DIR / "loans_2014_2017.parquet"
NOTES_TXT = PROJECT_ROOT / "outputs" / "build_dataset_notes.txt"
DROP_LOG_TXT = PROJECT_ROOT / "outputs" / "leakage_drop_log.txt"

CHUNKSIZE = 100_000
KEEP_STATUSES = {"Fully Paid", "Charged Off"}
KEEP_YEARS = {2014, 2015, 2016, 2017}

# The 33 leakage suspects flagged by 01_data_exploration.py, with reasons.
LEAKAGE_DROPS = {
    "total_pymnt":              "cumulative payments received over the loan's life; unknowable at decision time",
    "total_pymnt_inv":          "cumulative payments received over the loan's life; unknowable at decision time",
    "total_rec_prncp":          "totals received (principal/interest/fees) after origination",
    "total_rec_int":            "totals received (principal/interest/fees) after origination",
    "total_rec_late_fee":       "totals received (principal/interest/fees) after origination",
    "recoveries":               "money recovered after charge-off — implies the default already happened",
    "collection_recovery_fee":  "fee charged on post-charge-off collections",
    "last_pymnt_d":             "describes the most recent payment made during the loan",
    "last_pymnt_amnt":          "describes the most recent payment made during the loan",
    "next_pymnt_d":             "scheduled future payment — only exists for loans already in repayment",
    "last_fico_range_high":     "FICO score refreshed during the loan, not the score at application",
    "last_fico_range_low":      "FICO score refreshed during the loan, not the score at application",
    "out_prncp":                "outstanding principal is the loan's current state, not origination info",
    "out_prncp_inv":            "outstanding principal is the loan's current state, not origination info",
    "settlement_status":        "debt-settlement details — recorded only after the borrower is in distress",
    "settlement_date":          "debt-settlement details — recorded only after the borrower is in distress",
    "settlement_amount":        "debt-settlement details — recorded only after the borrower is in distress",
    "settlement_percentage":    "debt-settlement details — recorded only after the borrower is in distress",
    "settlement_term":          "debt-settlement details — recorded only after the borrower is in distress",
    "hardship_flag":            "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_type":            "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_reason":          "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_status":          "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_amount":          "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_start_date":      "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_end_date":        "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_length":          "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_dpd":             "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_loan_status":     "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_payoff_balance_amount":  "hardship-plan fields — recorded only after the borrower is in distress",
    "hardship_last_payment_amount":    "hardship-plan fields — recorded only after the borrower is in distress",
    "debt_settlement_flag":     "settlement flag/date — recorded only after the borrower is in distress",
    "debt_settlement_flag_date": "settlement flag/date — recorded only after the borrower is in distress",
    # 4 additions spotted during review of 01's output:
    "last_credit_pull_d":       "date of the most recent credit pull during the loan — post-origination",
    "payment_plan_start_date":  "hardship-family field that doesn't match the hardship_* prefix",
    "deferral_term":            "hardship-plan field — recorded only after the borrower is in distress",
    "pymnt_plan":               "payment-plan flag set during the loan — post-origination",
    "orig_projected_additional_accrued_interest": "hardship-family, projected interest under a payment plan — post-origination info",
}

OTHER_DROPS = {
    "member_id": "fully null in the raw file",
    "desc":      "free-text description discontinued by Lending Club (~100% null)",
    "loan_status": "source of the is_default label — keeping it among features would be trivially leaky",
}


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
    if not RAW_CSV.exists():
        raise SystemExit(f"ERROR: dataset not found at {RAW_CSV}")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    tee = Tee(NOTES_TXT)
    tee.line("Honest Mistake — build_dataset notes")
    tee.line(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")
    tee.line(f"Source: {RAW_CSV.name} (read-only)")

    # ------------------------------------------------------------------
    # Chunked filter pass
    # ------------------------------------------------------------------
    n_raw = 0
    n_after_status = 0
    n_after_year = 0
    kept_chunks = []

    reader = pd.read_csv(RAW_CSV, chunksize=CHUNKSIZE, low_memory=False)
    for chunk in reader:
        n_raw += len(chunk)

        chunk = chunk[chunk["loan_status"].isin(KEEP_STATUSES)]
        n_after_status += len(chunk)

        years = pd.to_datetime(
            chunk["issue_d"], format="%b-%Y", errors="coerce"
        ).dt.year
        chunk = chunk[years.isin(KEEP_YEARS)]
        n_after_year += len(chunk)

        if len(chunk):
            kept_chunks.append(chunk)

    df = pd.concat(kept_chunks, ignore_index=True)
    del kept_chunks

    header(tee, "ROW FUNNEL")
    tee.line(f"  raw rows:                      {n_raw:>10,}")
    tee.line(f"  after status filter:           {n_after_status:>10,}  (Fully Paid / Charged Off)")
    tee.line(f"  after issue-year filter:       {n_after_year:>10,}  (2014-2017)")

    # ------------------------------------------------------------------
    # Target
    # ------------------------------------------------------------------
    df["is_default"] = (df["loan_status"] == "Charged Off").astype("int8")

    # ------------------------------------------------------------------
    # Column drops (logged to leakage_drop_log.txt)
    # ------------------------------------------------------------------
    log = Tee(DROP_LOG_TXT)
    log.line("Honest Mistake — dropped-column log")
    log.line(f"Generated: {datetime.now():%Y-%m-%d %H:%M:%S}")

    width = max(len(c) for c in df.columns)

    header(log, f"LEAKAGE DROPS ({len(LEAKAGE_DROPS)} columns — post-loan info)")
    leak_present = [c for c in LEAKAGE_DROPS if c in df.columns]
    for col in leak_present:
        log.line(f"  {col:<{width}}  {LEAKAGE_DROPS[col]}")
    df = df.drop(columns=leak_present)

    header(log, f"OTHER DROPS ({len(OTHER_DROPS)} columns)")
    other_present = [c for c in OTHER_DROPS if c in df.columns]
    for col in other_present:
        log.line(f"  {col:<{width}}  {OTHER_DROPS[col]}")
    df = df.drop(columns=other_present)

    # Columns 100% null in the filtered (2014-2017, resolved) data
    all_null = [c for c in df.columns if df[c].isna().all()]
    header(log, f"100%-NULL IN FILTERED DATA ({len(all_null)} columns)")
    for col in all_null:
        log.line(f"  {col:<{width}}  100.00% null across all {len(df):,} filtered rows")
    df = df.drop(columns=all_null)

    log.line()
    n_dropped = len(leak_present) + len(other_present) + len(all_null)
    log.line(f"Total dropped: {n_dropped} columns "
             f"({len(leak_present)} leakage, {len(other_present)} other, {len(all_null)} all-null)")
    log.close()

    # ------------------------------------------------------------------
    # Write parquet (guard against chunk-wise dtype drift on text cols)
    # ------------------------------------------------------------------
    for col in df.columns:
        if df[col].dtype == object:
            df[col] = df[col].astype("str")
    df.to_parquet(OUT_PARQUET, index=False)

    # ------------------------------------------------------------------
    # Summary
    # ------------------------------------------------------------------
    header(tee, "FINAL DATASET")
    tee.line(f"  shape:         {df.shape[0]:,} rows x {df.shape[1]} columns")
    tee.line(f"  default rate:  {df['is_default'].mean() * 100:.2f}%  "
             f"({int(df['is_default'].sum()):,} defaults)")
    tee.line(f"  dropped:       {n_dropped} columns "
             f"({len(leak_present)} leakage, {len(other_present)} other, {len(all_null)} all-null)")
    tee.line(f"  output:        {OUT_PARQUET.relative_to(PROJECT_ROOT)} "
             f"({OUT_PARQUET.stat().st_size / 1e6:.1f} MB)")
    tee.line(f"  drop log:      {DROP_LOG_TXT.relative_to(PROJECT_ROOT)}")

    header(tee, "TOP 20 MOST-MISSING COLUMNS (recomputed on filtered data)")
    missing = df.isna().mean().sort_values(ascending=False).head(20)
    for col, frac in missing.items():
        tee.line(f"  {frac * 100:6.2f}%  {col}")

    tee.line()
    tee.line(f"Notes saved to {NOTES_TXT.relative_to(PROJECT_ROOT)}")
    tee.close()


if __name__ == "__main__":
    main()
