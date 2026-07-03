# Honest Mistake

A credit-default model built the honest way — where the hard part isn't the score, it's proving the score is real.

Most public models on the Lending Club data report AUCs above 0.90. Almost all of them are wrong: they train on columns that only exist *after* a loan's outcome is known, so the model is quietly reading the answer off the back of the page. This project does the opposite. It strips out every post-outcome column, keeps only information a lender would actually have at the moment of decision, and lands at an AUC of **0.73** on a true future-year holdout. That lower number is the point. It's what an honest model on this data looks like.

The name is deliberate. *Mistake* is the hidden leakage and blind spots a model carries. *Honest* is the discipline of surfacing them instead of hiding behind a flattering metric.

---

## The data

Lending Club accepted loans, 2007–2018 (the public `accepted_2007_to_2018Q4.csv`, ~1.68 GB, kept read-only).

From 2.26M raw rows I filter down to a clean modeling set:

| Step | Rows |
|---|---|
| Raw | 2,260,701 |
| Resolved loans only (Fully Paid / Charged Off) | 1,345,310 |
| Issued 2014–2017 | 1,061,042 |

`Current` and other in-progress statuses are dropped — an unresolved loan has no label to learn from. The final set is **1,061,042 loans with a 21.1% default rate**. The 2014–2017 window is chosen on purpose: earlier vintages sit in the 2008 crisis, and by the data's Dec-2018 cutoff these years have largely matured.

Target: `is_default` — 1 for Charged Off, 0 for Fully Paid.

## The leakage problem

This is the core of the project, so it gets the most attention.

A feature leaks if it wouldn't exist at the moment you make the prediction. `total_pymnt` (how much the borrower has repaid) is really the outcome wearing a disguise — high for paid loans, low for defaults. Train on it and you get a beautiful, useless model.

I removed **41 columns** in three passes, and it took all three to catch everything:

- **Pattern matching (33 columns).** Payment totals, recoveries, refreshed FICO scores, the whole hardship and settlement family — anything matching a known post-loan naming pattern.
- **Reading the data dictionary (4 columns).** `last_credit_pull_d`, `payment_plan_start_date`, `deferral_term`, and `pymnt_plan` are all post-origination, but their names don't match any obvious pattern. Automation misses these; a human reading each column's meaning does not.
- **Missingness analysis (1 column).** `orig_projected_additional_accrued_interest` survived both earlier passes. It's 99.6% missing because it only exists for borrowers already on a hardship plan — a leak that only shows itself once you look at *why* a column is empty.

Every dropped column is logged with a one-line reason in `outputs/leakage_drop_log.txt`. The lesson baked into that log — no single check is enough — is exactly what the later agentic layers of this project automate.

## Evaluation, and why it's set up this way

The split is **temporal, never random**: train on 2014–2016, test on 2017. A random split would let the model train on 2017 loans and test on 2014 ones — learning from the future to predict the past, which never happens in deployment and quietly inflates every metric.

Default rates rise across vintages (18.5% → 20.2% → 23.3% → 23.1%), so the 2017 test set is genuinely harder than training — the same drift a deployed model actually faces.

The 2017 test set is scored **exactly once**, at the very end. Hyperparameter tuning runs against a 2016 validation year carved out of training data, so the test set stays untouched until the final number.

Accuracy is never used as a metric. At a 21% default rate, a model that predicts "no default" for everyone scores 79% accuracy while catching zero defaulters. I report **ROC-AUC** (ranking quality) and **PR-AUC** (performance on the minority class that actually matters).

## Results

Everything below is on the 2017 temporal test set.

| Model | ROC-AUC | PR-AUC |
|---|---|---|
| Logistic Regression (reference) | 0.7136 | 0.4105 |
| XGBoost (baseline) | 0.7181 | 0.4275 |
| XGBoost (tuned) | **0.7296** | **0.4404** |

PR-AUC against a prevalence floor of 0.231 — the tuned model roughly doubles what random ranking gives you on the class that counts.

Two things I'd point to over the headline number:

- **The tuned model generalizes cleanly.** Validation AUC on 2016 was 0.7273; test AUC on 2017 was 0.7296 — a gap of −0.002. The tuning didn't memorize the validation year.
- **0.73 is the honest ceiling here.** Origination-only information on this data tops out in the low 0.70s. If I'd seen 0.85+, my first move would have been to hunt for the leak that survived — not celebrate.

Tuning was 50 Optuna trials. The best configuration is a "many small careful trees" setup — depth 8, learning rate 0.019, 900 trees, 50% row subsampling — where the regularization work is done by sampling rather than explicit penalties.

## The audit

The script the project is named for. After the model is trained, `07_audit.py` interrogates it with SHAP and a set of rule-based honesty checks.

**What carries the model.** The top features are `term`, `sub_grade`, `grade`, `dti`, and `int_rate` — eight of the top ten are core credit variables, and every direction makes sense (longer terms, worse grades, higher DTI, higher rates, lower FICO all push risk up). No leakage signature survived into the trained model.

**Three flags, three different verdicts.** The audit rule flags anything unexpected with high attribution; the judgment call is mine:

- `home_ownership_RENT` (rank 7) — flagged, but benign. Renters defaulting more often is real borrower economics, not an artifact.
- `emp_length_was_missing` (rank 14) — a genuine finding, and one I followed up on. Applicants who don't state their employment length are measurably riskier, so the model uses "declined to answer" as a risk signal — which raises a fairness question. I tested it directly: dropping the feature and retraining costs 0.0003 AUC (see `08_fairness_ablation.py`). The model doesn't depend on it and it can be removed for fairness at essentially no cost. Worth noting too that this is a case where SHAP attribution overstates importance — the feature ranks 14th yet is almost fully substitutable by correlated signals.
- The 21 bureau `was_missing` flags — dead weight at test time. Lending Club collected those fields for everyone by 2017, so the flagged cohort is empty in the test set. They only helped stratify older vintages during training.

**No slice failures.** AUC holds at 0.727–0.733 across all four 2017 quarters. Within-grade AUC is lower (0.63–0.71), which is expected — grade already does much of the ranking, so the residual signal inside a single grade is naturally smaller.

**The most confident mistake is instructive.** The model's most confident false positive was a G5, 60-month, 31%-interest small-business loan from a renter with a 13-month credit file — scored 0.96, and it paid off. The model wasn't wrong to call that risky; loans like it default roughly half the time. That's irreducible uncertainty, not a bug — and separating the two is exactly what the audit exists to do.

## Pipeline

Each script writes its own plain-text notes file to `outputs/`, so the full reasoning trail exists on disk, not just in my head.

| Script | Does |
|---|---|
| `01_data_exploration.py` | First look; flags leakage suspects |
| `02_build_dataset.py` | Filters to 2014–2017 resolved loans, drops 41 leakage/dead columns |
| `03_split.py` | Temporal train/test split by issue year |
| `04_features.py` | Feature prep — all transforms fit on train only |
| `05_baseline.py` | Logistic Regression + untuned XGBoost, to set the bar |
| `06_tune.py` | Optuna tuning against a 2016 validation year |
| `07_audit.py` | SHAP explanations + rule-based honesty checks |
| `08_fairness_ablation.py` | Measures the cost of dropping a fairness-sensitive feature |

## Known limitations

Stated plainly, because hiding them would defeat the purpose.

- **Resolution / survivorship bias in the 2017 test set.** The data ends Dec 2018, so a 36-month loan issued in mid-2017 could only resolve that early by prepaying or defaulting fast. The 2017 resolved subset therefore over-represents early payoffs and early defaults, and its 23.1% default rate isn't the true vintage rate. 2014–2015 are fully matured and unaffected; 2016 is mildly affected.
- **Probabilities are not calibrated.** Class weighting shifts predicted probabilities upward to favor recall, which inflates the Brier score by construction. Ranking metrics are unaffected; calibration is deferred to the confidence-flagging layer.
- **This is a research pipeline, not a service.** Single scripts, no packaging or tests yet. Productionizing — API, modular code, deployment — is a later stage of the project, not an oversight.

## Reproducing

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

The dataset is gitignored (too large, and it's public). Download the file `accepted_2007_to_2018Q4.csv.gz` from the ["All Lending Club loan data" dataset on Kaggle](https://www.kaggle.com/datasets/wordsforthewise/lending-club/data?select=accepted_2007_to_2018Q4.csv.gz), unzip it, and place `accepted_2007_to_2018Q4.csv` at `data/raw/`. Then run the scripts in order, `01` through `08`.

Built with Python 3.11, pandas, scikit-learn, XGBoost, SHAP, and Optuna.
