# Precomputed agent cache — v2 artefacts (honest variant)

Three files, written by `scripts/build_agent_cache_v2.py --variant honest`.
They exist so the audit agent can read finished measurements instead of
reaching for `data/`. Everything below is descriptive: no model was fitted,
nothing was resampled, no SHAP value was recomputed.

The feature matrix for this variant has 180 columns, 891,742 training
rows and 169,300 test rows. Train covers 2014 (223,102 rows), 2015 (375,545 rows), 2016 (293,095 rows); test is 2017 in full.

## coverage_profile.csv

One row per feature per scope, six scopes: `train`, `test`, and the four
vintages `2014`, `2015`, `2016`, `2017`. The vintage scopes come from
`issue_year`, which lives in `train.parquet` / `test.parquet` and not in the
feature matrix, so the script attaches it by row position and refuses to run
unless that alignment is demonstrated first — full-length row-for-row equality
on 6 untransformed numeric columns (loan_amnt, annual_inc, revol_bal, tot_hi_cred_lim, tot_cur_bal, total_bal_ex_mort). There is
no join, no sort, no merge on a key anywhere in this script.

`pct_flagged_missing` is the mean of the feature's `_was_missing` companion
within the scope. It is left empty, not zero, for features that have no such
companion: zero would read as "nothing was missing" when the truth is "the
question does not apply". `pct_zero` and `pct_at_999` count exact values, 999
being the sentinel that `04_features.py` writes into the `mths_since_*` family.
`mean`, `std` and `p50` are the ordinary sample statistics, `std` with ddof=1.

The `_was_missing` columns are profiled as features in their own right, since
that is what they are to the model.

## univariate_assoc.csv

One row per feature: how much of the target that feature accounts for on its
own. `auc_train` and `auc_test` are ROC-AUC computed from the Mann-Whitney U
statistic over `scipy.stats.rankdata`, using the raw feature value as the
score. `auc_2014` through `auc_2016` are the same statistic computed inside
each training vintage.

The AUCs are not folded to `max(auc, 1 - auc)`. A feature whose high values go
with non-default lands below 0.5 and is left there, because the direction is
part of what the number tells you. A feature that is constant within a scope
gets an empty AUC for that scope rather than 0.5. `point_biserial_test` is the
Pearson correlation between the feature and `is_default` on test.

## correlation_topk.csv

Long format: for each feature, its 15 nearest neighbours by absolute
Pearson correlation, ranked 1 to 15, signed `pearson_r` kept alongside
`abs_pearson_r`. Computed on the full test matrix, no sampling, so it sits on
the same footing as the ablation numbers in `ablation_cache.csv`, which were
also measured on test. Self-pairs are skipped. Ties are broken on neighbour
name so a rerun gives byte-identical output. A feature that is constant on test
has no defined correlations and gets one row with rank 1 and empty neighbour
and `pearson_r`, so that it still appears in the file rather than vanishing.

## What these files cannot tell you

The big one is coverage. The feature matrices contain no NaN at all — zero, in
both splits. `04_features.py` imputed as it built them: sentinel 999 for the
`mths_since_*` family, train medians for the Dec-2015 bureau block and for
`emp_length`, train medians again for everything else that had gaps. Of the
180 columns, 22 kept a `_was_missing` companion recording what was
filled. The other 158 did not, and for those `coverage_profile.csv`
will report complete data in every scope. That is an artefact of construction
and carries no information — it is not evidence that those columns were
complete in the source. Where a column was imputed without a flag, the fill is
now indistinguishable from a real observation in these statistics.

Two smaller ones. The vintage scopes are unbalanced by design, 2014 through
2016 being train slices of quite different sizes and 2017 being the whole test
split, so a per-vintage number moves partly with sample size. And every
statistic here is univariate or pairwise; nothing in these three files sees an
interaction between three or more columns.
