"""data_dictionary.py — Honest Mistake, Layer 2.

Factual reference for what each column holds and when it receives its
value. Descriptions state definitions and lifecycle timing only; they
carry no assessment of whether a field is appropriate to model with.
Any such conclusion is for the caller to derive.

Entries cover every column of X_test plus every column removed during
dataset construction, so any field can be looked up.

Schema:
    FEATURE_DOCS[column] = {
        "description": what the field holds,
        "populated":   when it receives its value,
        "source":      'borrower application' | 'credit bureau'
                       | 'Lending Club internal' | 'engineered',
    }

`search()` has two tiers: exact substring matching over feature names,
then semantic retrieval over descriptions via agent.retrieval. Only the
description text is embedded — see agent/retrieval.py for why `populated`
is deliberately kept out of the vector.

Run the coverage self-check:
    .venv/bin/python -m agent.data_dictionary
"""

APPLICATION = "borrower application"
BUREAU = "credit bureau"
INTERNAL = "Lending Club internal"
ENGINEERED = "engineered"

AT_APPLICATION = "at application, before the loan is approved"
AT_ORIGINATION = "at origination, when the loan is issued"
DURING_TERM = "updated during the loan term"
MONTHLY = "updated monthly during the loan term"
AT_PREP = "derived during feature preparation"

# ----------------------------------------------------------------------
# Loan terms and application fields
# ----------------------------------------------------------------------
FEATURE_DOCS: dict[str, dict[str, str]] = {
    "loan_amnt": {
        "description": "Amount of money the borrower requested.",
        "populated": AT_APPLICATION,
        "source": APPLICATION,
    },
    "funded_amnt": {
        "description": "Amount Lending Club committed to fund for this loan.",
        "populated": AT_ORIGINATION,
        "source": INTERNAL,
    },
    "funded_amnt_inv": {
        "description": "Portion of the loan amount funded by investors.",
        "populated": AT_ORIGINATION,
        "source": INTERNAL,
    },
    "term": {
        "description": "Number of monthly payments scheduled for the loan, "
                       "either 36 or 60; stored as an integer count of months.",
        "populated": AT_ORIGINATION,
        "source": INTERNAL,
    },
    "int_rate": {
        "description": "Annual interest rate assigned to the loan, in percent.",
        "populated": AT_ORIGINATION,
        "source": INTERNAL,
    },
    "installment": {
        "description": "Scheduled monthly payment amount implied by the loan "
                       "amount, rate, and term.",
        "populated": AT_ORIGINATION,
        "source": INTERNAL,
    },
    "grade": {
        "description": "Lending Club risk grade A through G, encoded A=1 "
                       "through G=7.",
        "populated": AT_ORIGINATION,
        "source": INTERNAL,
    },
    "sub_grade": {
        "description": "Lending Club risk sub-grade A1 through G5, a finer "
                       "division of grade, encoded A1=1 through G5=35.",
        "populated": AT_ORIGINATION,
        "source": INTERNAL,
    },
    "emp_length": {
        "description": "Years of employment the borrower reported, encoded 0 "
                       "for under one year through 10 for ten or more years.",
        "populated": AT_APPLICATION,
        "source": APPLICATION,
    },
    "annual_inc": {
        "description": "Annual income the borrower reported.",
        "populated": AT_APPLICATION,
        "source": APPLICATION,
    },
    "dti": {
        "description": "Debt-to-income ratio: monthly debt payments other than "
                       "mortgage and this loan, divided by monthly income.",
        "populated": AT_APPLICATION,
        "source": APPLICATION,
    },

    # ------------------------------------------------------------------
    # Credit bureau — delinquency and public records
    # ------------------------------------------------------------------
    "delinq_2yrs": {
        "description": "Number of times the borrower was 30 or more days past "
                       "due in the previous two years.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "fico_range_low": {
        "description": "Lower bound of the borrower's FICO score band at the "
                       "credit pull made for this application.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "fico_range_high": {
        "description": "Upper bound of the borrower's FICO score band at the "
                       "credit pull made for this application.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "inq_last_6mths": {
        "description": "Number of credit inquiries in the previous six months, "
                       "other than auto and mortgage inquiries.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mths_since_last_delinq": {
        "description": "Months since the borrower's most recent delinquency.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mths_since_last_record": {
        "description": "Months since the borrower's most recent public record.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "open_acc": {
        "description": "Number of open credit lines in the borrower's file.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "pub_rec": {
        "description": "Number of derogatory public records.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "revol_bal": {
        "description": "Total revolving balance across the borrower's accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "revol_util": {
        "description": "Revolving line utilisation: percent of available "
                       "revolving credit the borrower is using.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "total_acc": {
        "description": "Total number of credit lines in the borrower's file, "
                       "open and closed.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "collections_12_mths_ex_med": {
        "description": "Number of collections in the previous 12 months, "
                       "counting everything other than medical collections.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mths_since_last_major_derog": {
        "description": "Months since the most recent 90-day or worse rating.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "acc_now_delinq": {
        "description": "Number of accounts on which the borrower is currently "
                       "delinquent.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "tot_coll_amt": {
        "description": "Total collection amounts ever owed by the borrower.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "tot_cur_bal": {
        "description": "Total current balance across all of the borrower's "
                       "accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },

    # ------------------------------------------------------------------
    # Credit bureau — trade line detail (collected from around Dec 2015)
    # ------------------------------------------------------------------
    "open_acc_6m": {
        "description": "Number of trades opened in the previous six months.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "open_act_il": {
        "description": "Number of currently active instalment trades.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "open_il_12m": {
        "description": "Number of instalment accounts opened in the previous "
                       "12 months.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "open_il_24m": {
        "description": "Number of instalment accounts opened in the previous "
                       "24 months.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "mths_since_rcnt_il": {
        "description": "Months since the borrower's most recently opened "
                       "instalment account.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "total_bal_il": {
        "description": "Total current balance across all instalment accounts.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "il_util": {
        "description": "Ratio of current balance to credit limit across the "
                       "borrower's instalment accounts.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "open_rv_12m": {
        "description": "Number of revolving trades opened in the previous "
                       "12 months.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "open_rv_24m": {
        "description": "Number of revolving trades opened in the previous "
                       "24 months.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "max_bal_bc": {
        "description": "Highest current balance on any revolving bankcard "
                       "account.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "all_util": {
        "description": "Balance to credit limit ratio across all of the "
                       "borrower's trades.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "total_rev_hi_lim": {
        "description": "Total revolving high credit limit across the "
                       "borrower's accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "inq_fi": {
        "description": "Number of personal finance inquiries.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "total_cu_tl": {
        "description": "Number of finance trades on the borrower's file.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },
    "inq_last_12m": {
        "description": "Number of credit inquiries in the previous 12 months.",
        "populated": AT_APPLICATION + "; collected for loans issued from "
                     "around December 2015 onward",
        "source": BUREAU,
    },

    # ------------------------------------------------------------------
    # Credit bureau — account age, mix, and counts
    # ------------------------------------------------------------------
    "acc_open_past_24mths": {
        "description": "Number of trades opened in the previous 24 months.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "avg_cur_bal": {
        "description": "Average current balance across all of the borrower's "
                       "accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "bc_open_to_buy": {
        "description": "Total unused credit available on revolving bankcards.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "bc_util": {
        "description": "Ratio of current balance to credit limit across all "
                       "bankcard accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "chargeoff_within_12_mths": {
        "description": "Number of charge-offs on the borrower's other accounts "
                       "within the previous 12 months.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "delinq_amnt": {
        "description": "Past-due amount owed on the accounts on which the "
                       "borrower is currently delinquent.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mo_sin_old_il_acct": {
        "description": "Months since the borrower's oldest instalment account "
                       "was opened.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mo_sin_old_rev_tl_op": {
        "description": "Months since the borrower's oldest revolving account "
                       "was opened.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mo_sin_rcnt_rev_tl_op": {
        "description": "Months since the borrower's most recent revolving "
                       "account was opened.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mo_sin_rcnt_tl": {
        "description": "Months since the borrower's most recent account of any "
                       "kind was opened.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mort_acc": {
        "description": "Number of mortgage accounts in the borrower's file.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mths_since_recent_bc": {
        "description": "Months since the borrower's most recent bankcard "
                       "account was opened.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mths_since_recent_bc_dlq": {
        "description": "Months since the borrower's most recent bankcard "
                       "delinquency.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mths_since_recent_inq": {
        "description": "Months since the borrower's most recent credit "
                       "inquiry.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "mths_since_recent_revol_delinq": {
        "description": "Months since the borrower's most recent delinquency on "
                       "a revolving account.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_accts_ever_120_pd": {
        "description": "Number of accounts ever 120 or more days past due.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_actv_bc_tl": {
        "description": "Number of currently active bankcard accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_actv_rev_tl": {
        "description": "Number of currently active revolving trades.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_bc_sats": {
        "description": "Number of satisfactory bankcard accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_bc_tl": {
        "description": "Total number of bankcard accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_il_tl": {
        "description": "Total number of instalment accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_op_rev_tl": {
        "description": "Number of open revolving accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_rev_accts": {
        "description": "Total number of revolving accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_rev_tl_bal_gt_0": {
        "description": "Number of revolving trades carrying a balance greater "
                       "than zero.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_sats": {
        "description": "Number of satisfactory accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_tl_120dpd_2m": {
        "description": "Number of accounts currently 120 days past due, "
                       "measured in the previous two months.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_tl_30dpd": {
        "description": "Number of accounts currently 30 days past due.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_tl_90g_dpd_24m": {
        "description": "Number of accounts 90 or more days past due in the "
                       "previous 24 months.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "num_tl_op_past_12m": {
        "description": "Number of accounts opened in the previous 12 months.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "pct_tl_nvr_dlq": {
        "description": "Percent of the borrower's trades that have never been "
                       "delinquent.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "percent_bc_gt_75": {
        "description": "Percent of bankcard accounts with a balance above 75 "
                       "percent of their limit.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "pub_rec_bankruptcies": {
        "description": "Number of public record bankruptcies.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "tax_liens": {
        "description": "Number of tax liens in the borrower's file.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "tot_hi_cred_lim": {
        "description": "Total high credit limit across all of the borrower's "
                       "accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "total_bal_ex_mort": {
        "description": "Total current balance across all accounts other than "
                       "mortgages.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "total_bc_limit": {
        "description": "Total credit limit across the borrower's bankcard "
                       "accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },
    "total_il_high_credit_limit": {
        "description": "Total high credit limit across the borrower's "
                       "instalment accounts.",
        "populated": AT_APPLICATION,
        "source": BUREAU,
    },

    # ------------------------------------------------------------------
    # Engineered
    # ------------------------------------------------------------------
    "credit_history_months": {
        "description": "Length of the borrower's credit history in months, "
                       "computed as the gap between earliest_cr_line and the "
                       "loan's issue date.",
        "populated": AT_PREP + " from earliest_cr_line and the issue date",
        "source": ENGINEERED,
    },

    # ------------------------------------------------------------------
    # Columns removed during dataset construction
    # ------------------------------------------------------------------
    "loan_status": {
        "description": "Current status of the loan, such as Fully Paid, "
                       "Charged Off, or Current.",
        "populated": "set once the loan is issued and revised as the loan "
                     "progresses; reaches its final value when the loan "
                     "resolves",
        "source": INTERNAL,
    },
    "member_id": {
        "description": "Identifier for the borrower's Lending Club account.",
        "populated": AT_APPLICATION + "; not present in the public file",
        "source": INTERNAL,
    },
    "desc": {
        "description": "Free-text description of the loan written by the "
                       "borrower; the field was discontinued.",
        "populated": AT_APPLICATION,
        "source": APPLICATION,
    },
    "pymnt_plan": {
        "description": "Indicator of whether a payment plan is in place for "
                       "the loan.",
        "populated": "set when a payment plan is arranged, which happens after "
                     "the loan is issued",
        "source": INTERNAL,
    },
    "out_prncp": {
        "description": "Remaining outstanding principal on the loan.",
        "populated": MONTHLY + " as payments reduce the balance",
        "source": INTERNAL,
    },
    "out_prncp_inv": {
        "description": "Remaining outstanding principal on the investor-funded "
                       "portion of the loan.",
        "populated": MONTHLY + " as payments reduce the balance",
        "source": INTERNAL,
    },
    "total_pymnt": {
        "description": "Total payment received to date on the loan.",
        "populated": MONTHLY + " as the borrower makes payments",
        "source": INTERNAL,
    },
    "total_pymnt_inv": {
        "description": "Total payment received to date on the investor-funded "
                       "portion of the loan.",
        "populated": MONTHLY + " as the borrower makes payments",
        "source": INTERNAL,
    },
    "total_rec_prncp": {
        "description": "Principal received to date on the loan.",
        "populated": MONTHLY + " as the borrower makes payments",
        "source": INTERNAL,
    },
    "total_rec_int": {
        "description": "Interest received to date on the loan.",
        "populated": MONTHLY + " as the borrower makes payments",
        "source": INTERNAL,
    },
    "total_rec_late_fee": {
        "description": "Late fees received to date on the loan.",
        "populated": DURING_TERM + " whenever a late fee is charged and paid",
        "source": INTERNAL,
    },
    "recoveries": {
        "description": "Gross amount recovered on the loan after it was "
                       "charged off.",
        "populated": "set once the loan has been charged off and recovery "
                     "activity begins",
        "source": INTERNAL,
    },
    "collection_recovery_fee": {
        "description": "Fee charged on amounts recovered after the loan was "
                       "charged off.",
        "populated": "set once the loan has been charged off and recovery "
                     "activity begins",
        "source": INTERNAL,
    },
    "last_pymnt_d": {
        "description": "Month of the most recent payment received on the loan.",
        "populated": MONTHLY + " as payments arrive",
        "source": INTERNAL,
    },
    "last_pymnt_amnt": {
        "description": "Amount of the most recent payment received on the loan.",
        "populated": MONTHLY + " as payments arrive",
        "source": INTERNAL,
    },
    "next_pymnt_d": {
        "description": "Month in which the next scheduled payment is due.",
        "populated": MONTHLY + " while the loan is in repayment",
        "source": INTERNAL,
    },
    "last_credit_pull_d": {
        "description": "Month of the most recent credit pull Lending Club made "
                       "on this borrower.",
        "populated": DURING_TERM + " each time a further credit pull is made",
        "source": INTERNAL,
    },
    "last_fico_range_low": {
        "description": "Lower bound of the borrower's most recent FICO score "
                       "band.",
        "populated": "refreshed periodically during the loan term",
        "source": BUREAU,
    },
    "last_fico_range_high": {
        "description": "Upper bound of the borrower's most recent FICO score "
                       "band.",
        "populated": "refreshed periodically during the loan term",
        "source": BUREAU,
    },
    "hardship_flag": {
        "description": "Indicator of whether a hardship plan applies to the "
                       "loan.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_type": {
        "description": "Type of hardship plan applied to the loan.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_reason": {
        "description": "Reason the borrower gave for requesting a hardship "
                       "plan.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_status": {
        "description": "Status of the hardship plan, such as active, completed, "
                       "or broken.",
        "populated": "set when the borrower enters a hardship plan and revised "
                     "as the plan progresses",
        "source": INTERNAL,
    },
    "deferral_term": {
        "description": "Number of months the borrower's payments are reduced "
                       "under a hardship plan.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_amount": {
        "description": "Interest payment owed each month while the hardship "
                       "plan is in effect.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_start_date": {
        "description": "Date the hardship plan began.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_end_date": {
        "description": "Date the hardship plan ended or is scheduled to end.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "payment_plan_start_date": {
        "description": "Date the borrower's revised payment schedule begins "
                       "under a hardship plan.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_length": {
        "description": "Number of months of the hardship plan.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_dpd": {
        "description": "Days the borrower was past due as of the hardship plan "
                       "start date.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_loan_status": {
        "description": "Status the loan held as of the hardship plan start "
                       "date.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "orig_projected_additional_accrued_interest": {
        "description": "Interest projected to accrue over the course of the "
                       "hardship plan, as estimated when the plan begins.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_payoff_balance_amount": {
        "description": "Payoff balance on the loan as of the hardship plan "
                       "start date.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "hardship_last_payment_amount": {
        "description": "Amount of the last payment received as of the hardship "
                       "plan start date.",
        "populated": "set when the borrower enters a hardship plan, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "debt_settlement_flag": {
        "description": "Indicator of whether the borrower is working with a "
                       "debt settlement company on this loan.",
        "populated": "set when a settlement arrangement is recorded, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "debt_settlement_flag_date": {
        "description": "Date the debt settlement indicator was most recently "
                       "set.",
        "populated": "set when a settlement arrangement is recorded, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "settlement_status": {
        "description": "Status of the borrower's settlement plan.",
        "populated": "set when a settlement arrangement is recorded, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "settlement_date": {
        "description": "Date the borrower agreed to the settlement plan.",
        "populated": "set when a settlement arrangement is recorded, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "settlement_amount": {
        "description": "Loan amount the borrower agreed to pay under the "
                       "settlement plan.",
        "populated": "set when a settlement arrangement is recorded, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "settlement_percentage": {
        "description": "Settlement amount as a percentage of the outstanding "
                       "balance at the time of settlement.",
        "populated": "set when a settlement arrangement is recorded, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
    "settlement_term": {
        "description": "Number of months the borrower is scheduled to pay under "
                       "the settlement plan.",
        "populated": "set when a settlement arrangement is recorded, which "
                     "happens after the loan is issued",
        "source": INTERNAL,
    },
}


# ----------------------------------------------------------------------
# Generated families — templates applied to every member so that wording
# is uniform and no member is described differently from its siblings.
# ----------------------------------------------------------------------
_WAS_MISSING_FIELDS = [
    "mths_since_last_delinq", "mths_since_last_major_derog",
    "mths_since_last_record", "mths_since_rcnt_il", "mths_since_recent_bc",
    "mths_since_recent_bc_dlq", "mths_since_recent_inq",
    "mths_since_recent_revol_delinq", "open_acc_6m", "open_act_il",
    "open_il_12m", "open_il_24m", "total_bal_il", "il_util", "open_rv_12m",
    "open_rv_24m", "max_bal_bc", "all_util", "inq_fi", "total_cu_tl",
    "inq_last_12m", "emp_length",
]

for _field in _WAS_MISSING_FIELDS:
    FEATURE_DOCS[f"{_field}_was_missing"] = {
        "description": f"Takes the value 1 when {_field} had no value in the "
                       f"source data for this loan, and 0 when {_field} had a "
                       f"value.",
        "populated": AT_PREP + f" from the presence or absence of {_field}",
        "source": ENGINEERED,
    }

_ONE_HOT_FAMILIES = {
    "home_ownership": (
        "home ownership status the borrower reported",
        AT_APPLICATION, APPLICATION,
        {"ANY": "ANY", "MORTGAGE": "MORTGAGE", "OWN": "OWN", "RENT": "RENT"},
    ),
    "verification_status": (
        "whether the borrower's income was verified by Lending Club",
        AT_APPLICATION, INTERNAL,
        {"Not Verified": "Not Verified",
         "Source Verified": "Source Verified",
         "Verified": "Verified"},
    ),
    "purpose": (
        "category the borrower selected for the loan's purpose",
        AT_APPLICATION, APPLICATION,
        {k: k for k in [
            "car", "credit_card", "debt_consolidation", "educational",
            "home_improvement", "house", "major_purchase", "medical",
            "moving", "other", "renewable_energy", "small_business",
            "vacation", "wedding"]},
    ),
    "initial_list_status": (
        "initial listing status of the loan, whole or fractional",
        AT_ORIGINATION, INTERNAL,
        {"f": "f", "w": "w"},
    ),
    "application_type": (
        "whether the loan is an individual application or a joint "
        "application with a co-borrower",
        AT_APPLICATION, APPLICATION,
        {"Individual": "Individual", "Joint App": "Joint App"},
    ),
    "disbursement_method": (
        "method by which the loan proceeds were disbursed",
        AT_ORIGINATION, INTERNAL,
        {"Cash": "Cash", "DirectPay": "DirectPay"},
    ),
}

for _base, (_what, _when, _src, _levels) in _ONE_HOT_FAMILIES.items():
    for _suffix, _level in _levels.items():
        FEATURE_DOCS[f"{_base}_{_suffix}"] = {
            "description": f"One-hot column for {_base}, the {_what}. Takes "
                           f"the value 1 when {_base} is '{_level}', and 0 "
                           f"otherwise.",
            "populated": AT_PREP + f" from {_base}, which is recorded "
                         f"{_when}",
            "source": ENGINEERED,
        }

_STATES = [
    "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA", "HI",
    "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME", "MI", "MN",
    "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM", "NV", "NY", "OH",
    "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VA", "VT", "WA",
    "WI", "WV", "WY",
]

for _state in _STATES:
    FEATURE_DOCS[f"addr_state_{_state}"] = {
        "description": f"One-hot column for addr_state, the US state the "
                       f"borrower gave in their address. Takes the value 1 "
                       f"when addr_state is '{_state}', and 0 otherwise.",
        "populated": AT_PREP + " from addr_state, which is recorded "
                     + AT_APPLICATION,
        "source": ENGINEERED,
    }

# Underlying categoricals and dates that the engineered columns replace.
FEATURE_DOCS["addr_state"] = {
    "description": "US state the borrower gave in their address.",
    "populated": AT_APPLICATION,
    "source": APPLICATION,
}
FEATURE_DOCS["earliest_cr_line"] = {
    "description": "Month the borrower's earliest reported credit line was "
                   "opened.",
    "populated": AT_APPLICATION,
    "source": BUREAU,
}
FEATURE_DOCS["issue_d"] = {
    "description": "Month the loan was issued.",
    "populated": AT_ORIGINATION,
    "source": INTERNAL,
}

del _field, _base, _what, _when, _src, _levels, _suffix, _level, _state


# ----------------------------------------------------------------------
# Lookup helpers
# ----------------------------------------------------------------------
def lookup(feature: str) -> dict | None:
    """Return the entry for `feature`, or None if it is not documented."""
    entry = FEATURE_DOCS.get(feature)
    if entry is None:
        return None
    return {"feature": feature, **entry}


# ----------------------------------------------------------------------
# Retrieval path recording.
#
# Which backend actually served a search is part of a run's identity: a
# run served by the semantic index and a run served by the substring
# fallback are not the same experiment. The tool layer reads this when it
# stamps run_config().
#
# The agent is never told. Nothing here reaches a tool payload — no field,
# no message, no ordering difference beyond the results themselves.
# ----------------------------------------------------------------------
_PGVECTOR = "pgvector"
_FALLBACK = "keyword-fallback"
_retrieval_paths_used: set[str] = set()


def retrieval_paths_used() -> set[str]:
    """Which retrieval backends have served a search in this process."""
    return set(_retrieval_paths_used)


def reset_retrieval_paths() -> None:
    """Clear the record. For tests and between runs."""
    _retrieval_paths_used.clear()


def mark_retrieval_unavailable() -> None:
    """Record that the index is known to be unreachable for this run.

    Called by the runner's preflight when warming the retrieval stack
    fails. Without it a run that never happened to make a dictionary
    search would stamp itself 'unused', which is true but hides that the
    backend was down the whole time.
    """
    _retrieval_paths_used.add(_FALLBACK)


# Semantic tier bounds.
#
#   _MAX_DISTANCE   an absolute ceiling. Nothing beyond it is a match at
#                   all. Note what this does and does not catch: a
#                   gibberish string lands past it and is cut, but a
#                   fluent English question about something the dictionary
#                   does not hold embeds much closer than gibberish and
#                   sits well inside it. See
#                   outputs/agent_cache/RETRIEVAL_EVAL.md, `none` family.
#   _TOP_K          how many neighbours tier 2 may return at most.
#
# This replaced a relative band that kept everything within 0.05 of the
# closest hit. Two things killed it, both visible in the same eval run.
#
# One: a single global band could not serve two probes at once. For a
# query of "FICO score" the band closed at 0.285, after the two most
# recent FICO columns and before the two application-time ones at 0.325
# and 0.339 — too narrow, and it returned half of a set that obviously
# belongs together. For "which columns were computed rather than
# collected" the same band let through 87 entries — too wide. Moving the
# constant fixes one and worsens the other.
#
# Two, and the reason for a fixed cap rather than a better band: a
# semantic retriever over 224 one-sentence entries should never report 87
# matches, whatever the distances say. Bounding the tier is a structural
# statement about how large a useful answer can be in a corpus this size,
# not a per-query judgement about relevance. A relative band is the
# latter dressed as the former.
_MAX_DISTANCE = 0.45
_TOP_K = 10


def _semantic_description_hits(query: str, exclude: set[str]) -> list[dict]:
    """Tier 2 via the vector index. Raises if the index is unreachable."""
    from agent import retrieval

    hits = retrieval.search_descriptions(query, len(FEATURE_DOCS))
    if not hits:
        return []
    out = []
    for h in hits:
        if h["distance"] > _MAX_DISTANCE:
            break
        if h["feature"] in exclude:
            continue
        # The contract is four keys. distance is working state, not output.
        out.append({"feature": h["feature"],
                    "description": h["description"],
                    "populated": h["populated"],
                    "source": h["source"]})
        if len(out) == _TOP_K:
            break
    return out


def _substring_description_hits(q_lower: str, exclude: set[str]) -> list[dict]:
    """Tier 2 as it worked before the index existed, used as the fallback.

    Case-insensitive substring over descriptions, in FEATURE_DOCS
    insertion order.
    """
    return [
        {"feature": feature, **entry}
        for feature, entry in FEATURE_DOCS.items()
        if feature not in exclude and q_lower in entry["description"].lower()
    ]


def search(query: str) -> list[dict]:
    """Two-tier search over the dictionary, uncapped, in relevance order.

    Tier 1 is unchanged from the substring implementation: entries whose
    *name* contains the query, case-insensitively, in FEATURE_DOCS
    insertion order.

    Tier 2 is semantic retrieval over description embeddings, nearest
    first, excluding anything tier 1 already returned. If the index cannot
    be reached, tier 2 falls back to the substring matching over
    descriptions that this function used to do. The fallback is recorded
    for the run stamp and is invisible to the caller.

    Every record has exactly the keys feature, description, populated and
    source. Callers apply their own presentation limits.
    """
    q_raw = query.strip()
    if not q_raw:
        return []
    q = q_raw.lower()

    name_hits = [
        {"feature": feature, **entry}
        for feature, entry in FEATURE_DOCS.items()
        if q in feature.lower()
    ]
    seen = {h["feature"] for h in name_hits}

    try:
        from agent.retrieval import RetrievalUnavailable
    except Exception:  # retrieval deps absent — treat as unreachable
        _retrieval_paths_used.add(_FALLBACK)
        return name_hits + _substring_description_hits(q, seen)

    try:
        desc_hits = _semantic_description_hits(q_raw, seen)
        _retrieval_paths_used.add(_PGVECTOR)
    except RetrievalUnavailable:
        _retrieval_paths_used.add(_FALLBACK)
        desc_hits = _substring_description_hits(q, seen)

    return name_hits + desc_hits


# ----------------------------------------------------------------------
# Coverage self-check
# ----------------------------------------------------------------------
def _self_check() -> None:
    from pathlib import Path
    import re

    import pandas as pd

    root = Path(__file__).resolve().parent.parent
    x_cols = pd.read_parquet(
        root / "data" / "processed" / "X_test.parquet").columns.tolist()

    log = (root / "outputs" / "leakage_drop_log.txt").read_text()
    removed_cols = sorted({
        m.group(1) for m in re.finditer(r"^  ([a-z_0-9]+) {2,}", log,
                                        flags=re.MULTILINE)
    })

    missing_x = [c for c in x_cols if c not in FEATURE_DOCS]
    missing_d = [c for c in removed_cols if c not in FEATURE_DOCS]

    assert not missing_x, f"X_test columns not documented: {missing_x}"
    assert not missing_d, f"removed columns not documented: {missing_d}"

    print(f"FEATURE_DOCS entries:            {len(FEATURE_DOCS)}")
    print(f"X_test columns:                  {len(x_cols)} — all covered "
          f"(assert passed)")
    print(f"Columns removed in construction: {len(removed_cols)} — all covered "
          f"(assert passed)")
    extra = sorted(set(FEATURE_DOCS) - set(x_cols) - set(removed_cols))
    print(f"Additional entries documented:   {len(extra)} — {extra}")


if __name__ == "__main__":
    _self_check()
