"""retrieval_probes.py — probe set for the dictionary retrieval eval.

Kept separate from the scorer so the probes can be argued with on their
own. Nothing here computes anything.

Each probe is a question phrased the way an auditor would actually ask
it, not a rearrangement of a description. Where a probe does share words
with its target that is noted as the point of the probe, not an accident:
the `lexical` family exists precisely to check that substring matching
keeps winning where substring matching should win.

`expected` is my judgement about which entries answer the question. It is
not ground truth handed down from anywhere. `why` records the reasoning
in one sentence so the judgement can be checked; `uncertain` marks probes
where I would not defend the expected set strongly, and the scorer
reports those separately.

Families:
    lexical      the query word appears verbatim in the target description
    paraphrase   same concept, different vocabulary
    conceptual   a property or a lifecycle position, not a named thing
    identifier   a name fragment; keyword matching must not regress
    none         nothing in the dictionary should answer this
"""

# A probe: (id, family, query, expected set, why, uncertain)
PROBES = [
    # ------------------------------------------------------------------
    # lexical — the word is in the description; keyword should win or tie
    # ------------------------------------------------------------------
    {
        "id": "lex-bankruptcy",
        "family": "lexical",
        "query": "bankruptcies",
        "expected": {"pub_rec_bankruptcies"},
        "why": "Only one column counts bankruptcies, and the word appears "
               "in its description, so both backends should find it.",
        "uncertain": False,
    },
    {
        "id": "lex-mortgage",
        "family": "lexical",
        "query": "mortgage",
        "expected": {"mort_acc", "total_bal_ex_mort", "home_ownership_MORTGAGE",
                     "dti"},
        "why": "Mortgage is named directly in the mortgage-account count, in "
               "the balance measure that excludes mortgages, in the "
               "MORTGAGE level of home ownership, and in the debt-to-income "
               "definition which excludes mortgage payments.",
        "uncertain": False,
    },
    {
        "id": "lex-hardship",
        "family": "lexical",
        "query": "hardship",
        "expected": {"hardship_flag", "hardship_type", "hardship_reason",
                     "hardship_status", "hardship_amount", "hardship_length",
                     "hardship_dpd", "hardship_start_date", "hardship_end_date",
                     "hardship_loan_status", "hardship_payoff_balance_amount",
                     "hardship_last_payment_amount", "deferral_term",
                     "payment_plan_start_date"},
        "why": "The hardship family is a coherent block; the word is in every "
               "member's name and most descriptions.",
        "uncertain": False,
    },
    {
        "id": "lex-fico",
        "family": "lexical",
        "query": "FICO score",
        "expected": {"fico_range_low", "fico_range_high", "last_fico_range_low",
                     "last_fico_range_high"},
        "why": "Four columns carry FICO bands, two at application and two at "
               "the most recent pull.",
        "uncertain": False,
    },
    {
        "id": "lex-interest-rate",
        "family": "lexical",
        "query": "interest rate on the loan",
        "expected": {"int_rate"},
        "why": "One column holds the rate; total_rec_int is interest received, "
               "not a rate, so it is not expected.",
        "uncertain": False,
    },

    # ------------------------------------------------------------------
    # paraphrase — same concept, different words
    # ------------------------------------------------------------------
    {
        "id": "par-utilisation",
        "family": "paraphrase",
        "query": "how much of their available credit is the borrower using",
        "expected": {"revol_util", "bc_util", "all_util", "il_util",
                     "percent_bc_gt_75", "bc_open_to_buy"},
        "why": "This is the utilisation family; the question uses none of the "
               "words those descriptions use, which is the point.",
        "uncertain": False,
    },
    {
        "id": "par-job-tenure",
        "family": "paraphrase",
        "query": "how long has the applicant been in their job",
        "expected": {"emp_length", "emp_length_was_missing"},
        "why": "Employment length is the only tenure field; its missingness "
               "flag is a reasonable second hit.",
        "uncertain": False,
    },
    {
        "id": "par-missed-payments",
        "family": "paraphrase",
        "query": "has this borrower missed payments before",
        "expected": {"delinq_2yrs", "acc_now_delinq", "num_tl_30dpd",
                     "num_tl_90g_dpd_24m", "num_accts_ever_120_pd",
                     "mths_since_last_delinq", "pct_tl_nvr_dlq",
                     "delinq_amnt", "num_tl_120dpd_2m"},
        "why": "Delinquency is expressed across many columns and none of them "
               "uses the phrase 'missed payments'.",
        "uncertain": False,
    },
    {
        "id": "par-where-they-live",
        "family": "paraphrase",
        "query": "where in the country does the applicant live",
        "expected": {"addr_state"} | {f"addr_state_{s}" for s in [
            "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA",
            "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME",
            "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM",
            "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX",
            "UT", "VA", "VT", "WA", "WI", "WV", "WY"]},
        "why": "Geography is the state field and its 51 one-hot columns; the "
               "query says neither 'state' nor 'address'.",
        "uncertain": False,
    },
    {
        "id": "par-own-or-rent",
        "family": "paraphrase",
        "query": "does the applicant own their home or pay rent",
        "expected": {"home_ownership_ANY", "home_ownership_MORTGAGE",
                     "home_ownership_OWN", "home_ownership_RENT", "mort_acc"},
        "why": "The home-ownership one-hots are the direct answer; the "
               "mortgage-account count is a defensible near miss.",
        "uncertain": False,
    },
    {
        "id": "par-earnings",
        "family": "paraphrase",
        "query": "what does the borrower earn",
        "expected": {"annual_inc", "dti"},
        "why": "Income is the direct answer and debt-to-income is defined "
               "against it; neither description says 'earn'.",
        "uncertain": False,
    },
    {
        "id": "par-money-back",
        "family": "paraphrase",
        "query": "how much did the lender get back after giving up on the loan",
        "expected": {"recoveries", "collection_recovery_fee", "tot_coll_amt"},
        "why": "Post-charge-off recovery is the concept; the query avoids "
               "'recovered' and 'charged off'.",
        "uncertain": True,
    },

    # ------------------------------------------------------------------
    # conceptual — a property or a lifecycle position, not a named thing
    # ------------------------------------------------------------------
    {
        "id": "con-after-outcome",
        "family": "conceptual",
        "query": "which fields are only filled in once the loan has finished",
        "expected": {"total_pymnt", "total_pymnt_inv", "total_rec_prncp",
                     "total_rec_int", "total_rec_late_fee", "recoveries",
                     "collection_recovery_fee", "last_pymnt_d",
                     "last_pymnt_amnt", "loan_status", "out_prncp",
                     "out_prncp_inv", "settlement_amount", "settlement_status"},
        "why": "Lifecycle position, not a topic; the repayment and settlement "
               "fields are the ones that only exist after the fact.",
        "uncertain": True,
    },
    {
        "id": "con-known-at-application",
        "family": "conceptual",
        "query": "what does the lender know before deciding whether to approve",
        "expected": {"annual_inc", "emp_length", "dti", "fico_range_low",
                     "fico_range_high", "inq_last_6mths", "delinq_2yrs",
                     "open_acc", "pub_rec", "revol_bal", "revol_util",
                     "total_acc", "loan_amnt", "addr_state"},
        "why": "The application-time fields; this asks about a lifecycle "
               "position rather than any subject matter.",
        "uncertain": True,
    },
    {
        "id": "con-derived",
        "family": "conceptual",
        "query": "which columns were computed by us rather than collected",
        "expected": {"credit_history_months"} | {
            f"{b}_was_missing" for b in [
                "mths_since_last_delinq", "mths_since_last_major_derog",
                "mths_since_last_record", "mths_since_rcnt_il",
                "mths_since_recent_bc", "mths_since_recent_bc_dlq",
                "mths_since_recent_inq", "mths_since_recent_revol_delinq",
                "open_acc_6m", "open_act_il", "open_il_12m", "open_il_24m",
                "total_bal_il", "il_util", "open_rv_12m", "open_rv_24m",
                "max_bal_bc", "all_util", "inq_fi", "total_cu_tl",
                "inq_last_12m", "emp_length"]},
        "why": "The engineered columns: the derived credit-history length and "
               "every missingness flag.",
        "uncertain": True,
    },
    {
        "id": "con-flag-absence",
        "family": "conceptual",
        "query": "how do we record that a value was absent in the source",
        "expected": {f"{b}_was_missing" for b in [
            "mths_since_last_delinq", "mths_since_last_major_derog",
            "mths_since_last_record", "mths_since_rcnt_il",
            "mths_since_recent_bc", "mths_since_recent_bc_dlq",
            "mths_since_recent_inq", "mths_since_recent_revol_delinq",
            "open_acc_6m", "open_act_il", "open_il_12m", "open_il_24m",
            "total_bal_il", "il_util", "open_rv_12m", "open_rv_24m",
            "max_bal_bc", "all_util", "inq_fi", "total_cu_tl",
            "inq_last_12m", "emp_length"]},
        "why": "The 22 missingness flags are exactly the mechanism the "
               "question describes.",
        "uncertain": False,
    },
    {
        "id": "con-still-owed",
        "family": "conceptual",
        "query": "is there anything left to pay on this loan",
        "expected": {"out_prncp", "out_prncp_inv", "next_pymnt_d",
                     "loan_status", "pymnt_plan"},
        "why": "Outstanding principal and the forward payment date describe a "
               "live balance without the query naming either.",
        "uncertain": False,
    },
    {
        "id": "con-time-anchor",
        "family": "conceptual",
        "query": "which columns tell you when something happened",
        "expected": {"issue_d", "earliest_cr_line", "last_pymnt_d",
                     "next_pymnt_d", "last_credit_pull_d",
                     "hardship_start_date", "hardship_end_date",
                     "payment_plan_start_date", "settlement_date",
                     "debt_settlement_flag_date", "credit_history_months"},
        "why": "The date-valued columns; the question describes a property of "
               "the column rather than its subject.",
        "uncertain": True,
    },
    {
        "id": "con-identifies-person",
        "family": "conceptual",
        "query": "could any of these identify an individual borrower",
        "expected": {"member_id", "desc", "addr_state"},
        "why": "The member identifier and the free-text field are the "
               "person-level columns; state is the only other locator.",
        "uncertain": True,
    },

    # ------------------------------------------------------------------
    # identifier — name fragments; keyword must not regress
    # ------------------------------------------------------------------
    {
        "id": "id-mths-since",
        "family": "identifier",
        "query": "mths_since",
        "expected": {"mths_since_last_delinq", "mths_since_last_record",
                     "mths_since_last_major_derog", "mths_since_rcnt_il",
                     "mths_since_recent_bc", "mths_since_recent_bc_dlq",
                     "mths_since_recent_inq", "mths_since_recent_revol_delinq"}
                    | {f"mths_since_{b}_was_missing" for b in [
                        "last_delinq", "last_major_derog", "last_record",
                        "rcnt_il", "recent_bc", "recent_bc_dlq", "recent_inq",
                        "recent_revol_delinq"]},
        "why": "A literal name fragment: the 16 columns whose names start with "
               "it, and nothing else.",
        "uncertain": False,
    },
    {
        "id": "id-addr-state",
        "family": "identifier",
        "query": "addr_state",
        "expected": {"addr_state"} | {f"addr_state_{s}" for s in [
            "AK", "AL", "AR", "AZ", "CA", "CO", "CT", "DC", "DE", "FL", "GA",
            "HI", "IA", "ID", "IL", "IN", "KS", "KY", "LA", "MA", "MD", "ME",
            "MI", "MN", "MO", "MS", "MT", "NC", "ND", "NE", "NH", "NJ", "NM",
            "NV", "NY", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX",
            "UT", "VA", "VT", "WA", "WI", "WV", "WY"]},
        "why": "Name fragment matching the base column and all 51 one-hots.",
        "uncertain": False,
    },
    {
        "id": "id-num-tl",
        "family": "identifier",
        "query": "num_tl",
        "expected": {"num_tl_120dpd_2m", "num_tl_30dpd", "num_tl_90g_dpd_24m",
                     "num_tl_op_past_12m"},
        "why": "Four columns carry this prefix; nothing else should match on "
               "the literal string.",
        "uncertain": False,
    },
    {
        "id": "id-settlement",
        "family": "identifier",
        "query": "settlement",
        "expected": {"settlement_status", "settlement_date",
                     "settlement_amount", "settlement_percentage",
                     "settlement_term", "debt_settlement_flag",
                     "debt_settlement_flag_date"},
        "why": "The settlement block, matched by name.",
        "uncertain": False,
    },
    {
        "id": "id-revol",
        "family": "identifier",
        "query": "revol",
        "expected": {"revol_bal", "revol_util", "num_op_rev_tl",
                     "mths_since_recent_revol_delinq",
                     "mths_since_recent_revol_delinq_was_missing"},
        "why": "Columns whose names contain the fragment; the rev_tl family "
               "spells it differently and is a partial match at best.",
        "uncertain": True,
    },

    # ------------------------------------------------------------------
    # none — nothing in the dictionary answers these
    # ------------------------------------------------------------------
    {
        "id": "none-weather",
        "family": "none",
        "query": "what was the weather like on the day the loan was issued",
        "expected": set(),
        "why": "The dictionary holds no environmental data of any kind.",
        "uncertain": False,
    },
    {
        "id": "none-branch-staff",
        "family": "none",
        "query": "which loan officer approved this application",
        "expected": set(),
        "why": "Nothing records who at the lender handled a loan.",
        "uncertain": False,
    },
    {
        "id": "none-vehicle",
        "family": "none",
        "query": "what make and model of car does the borrower drive",
        "expected": set(),
        "why": "purpose_car records a loan purpose, not a vehicle; no column "
               "describes a car.",
        "uncertain": False,
    },
    {
        "id": "none-social",
        "family": "none",
        "query": "how many children does the applicant have",
        "expected": set(),
        "why": "No household or dependant information exists anywhere in the "
               "dictionary.",
        "uncertain": False,
    },
]

FAMILIES = ["lexical", "paraphrase", "conceptual", "identifier", "none"]
