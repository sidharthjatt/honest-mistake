# Evaluation notes: the populated-suppression ablation

A record of a negative result, written while building the Layer 2
evaluation and before any agent had been run.

## What the ablation was meant to test

The agent is given a data dictionary describing all 221 columns. Each
entry has three fields: `description` (what the column holds),
`populated` (when it receives its value), and `source`.

The `populated` field was written to a uniform template. Application-time
columns read "at application, before the loan is approved"; columns that
receive their value later read variants of "updated during the loan
term" or "set when the borrower enters a hardship plan, which happens
after the loan is issued". Because the template is uniform, the field is
close to machine-readable: a cross-tabulation of `populated` phrasing
against whether a column survived into the model separates 39 of the 41
removed columns from all 180 kept ones, with the two exceptions being
columns removed for emptiness rather than for timing.

That separability is convenient for analysis and dangerous for
evaluation. An agent could reach the right answer by matching on the
phrasing of one field without engaging with what any column means. The
ablation was intended to distinguish those two possibilities: run the
agent once with the full dictionary, run it again with `populated`
suppressed, and read the drop in performance as the portion of the
agent's success that depended on timing information rather than
reasoning.

The tool layer was built with the switch as a first-class constructor
argument for exactly this purpose.

## What the description scan found

Before running anything, the 39 lifecycle-removed columns were scanned
for timing language in the `description` field alone — that is, in what
the agent still sees when `populated` is suppressed. Thirty-six of the
thirty-nine carry it. Grouped by how explicit the signal is:

| Tier | Character | Count |
|---|---|---|
| A | explicit post-outcome event | 3 |
| B | explicit in-life accumulation | 10 |
| C | names a post-origination programme | 23 |

Tier A is the most direct: `recoveries` is described as "Gross amount
recovered on the loan after it was charged off." Tier B conveys
accumulation without naming a period: `total_pymnt` is "Total payment
received to date on the loan", and `out_prncp` is "Remaining outstanding
principal on the loan." Tier C names a programme that only exists after
origination: `hardship_amount` is "Interest payment owed each month
while the hardship plan is in effect."

The three that matched nothing are `last_credit_pull_d`,
`last_fico_range_high`, and `last_fico_range_low`. These are recorded as
`CLEAN_UNDER_SUPPRESSION`, but the label overstates the case. Each is
described in terms of the borrower's "most recent" credit pull or FICO
band, and "most recent" implies a value that is refreshed over time. A
careful reader can infer timing from these too. They are the residue of
one particular pattern list, not a demonstrated absence of signal.

## Why this cannot be fixed by rewording

The obvious response is to rewrite the descriptions so they carry no
timing information, and then the ablation works as designed. This is not
available, because the timing is not decoration on these definitions.
It is what the fields are.

A description of `hardship_amount` that does not mention a hardship plan
does not describe `hardship_amount`. A description of `total_pymnt` that
does not convey accumulation to date does not distinguish it from
`installment` or `funded_amnt`. A description of `recoveries` that omits
charge-off does not say what was recovered or from what. In each case the
sentence that would pass the scan is not a neutral version of the
original — it is a false one.

The dictionary was therefore left accurate. No description was weakened,
shortened, or made deliberately vague to raise the difficulty of the
task. Making the evaluation harder by making the reference material
wrong would produce a score that measures nothing about leakage
detection and would quietly corrupt every other use of the dictionary.

## What the ablation measures now

With `populated` suppressed, the agent loses one uniform, templated,
machine-readable field. It does not lose access to timing information,
which survives in the descriptions of at least 36 of the 39 true
positives.

The ablation should accordingly be reported as measuring dependence on
the convenience of a single structured timing field, not as measuring
dependence on timing information as such. A small performance drop
between the two runs would indicate that the agent was reading meaning
rather than matching one field's phrasing. It would not license the
stronger claim that the agent identifies leakage without timing
information, because that condition was never achieved.

To keep this readable in the results rather than buried here, the
answer key carries the tier assignment for every residual entry along
with the specific phrase that placed it there, and the scorer reports
how many of an agent's correct flags fall in each tier. A run whose
correct flags sit overwhelmingly in tier A and tier C — the tiers where
the giveaway is most explicit — is a different result from one spread
evenly, even at identical precision and recall.

## The finding

On this dataset, leakage detection cannot be cleanly separated from
reading definitions. The columns that leak do so because of what they
record, and any honest description of what they record conveys when they
come into existence. There is no version of this dictionary that is both
truthful and timing-blind.

This limits what the evaluation can establish. It can measure whether an
agent reads and reasons about definitions rather than pattern-matching a
single field, and it can measure whether an agent distinguishes genuine
lifecycle columns from the fourteen application-time bureau fields whose
`populated` string carries an unrelated clause about collection
coverage. It cannot establish that an agent would detect leakage from
column names and statistical behaviour alone. Testing that would require
a different instrument: a dictionary withheld entirely, or a dataset
whose leaking columns are not self-describing.

## Correction

An earlier note in this project put the residual at three columns. That
figure came from a single-phrase probe — a search for "charged off",
which returns exactly `loan_status`, `recoveries`, and
`collection_recovery_fee`. It was reported as the residual when it was
only the residual for that one query. The full scan across all 39
descriptions gives 36. The specification for `RESIDUAL_TIMING_LEAK` was
drafted against the smaller figure and has been revised to the tiered
set.

## Results register

Only completed runs are results. A run that ended as `truncated`,
`call_limit` or `turn_limit` was stopped by the harness before the agent
signalled it was done, and its answer is not an answer; those runs are
listed under Runs not entered below, with the reason.

Harness at the time of the entries below: model `claude-sonnet-5`, no
sampling parameters sent, `max_tokens` 12,400 per exchange, adaptive
thinking with summaries returned. Ceilings vary per run and are given in
the table.

`MAX_TOKENS` was raised from 2,000 to 12,400 after two runs were cut off
mid-investigation, sized from the observed reasoning volume in run1.
Thinking summaries were enabled at the same point. Runs before and after
that change are not comparable on turn or call counts: under the 2,000
ceiling an exchange could be truncated mid-tool-call, which ends a run
without an answer regardless of how much budget remained.

Scores are as produced by the corrected scorer, which resolves an
engineered derivative to its parent column. Figures published before
that correction understate hard negatives; see the section below.

| run | config_id | matrix | term. | turns | calls | flags | TP | FP | HN raw | HN deriv | recall | A | B | C |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| run3 | toolsv1.0-populated-included | 180 | completed | 16/20 | 52/70 | 2 | 0 | 2 | 0 | 2 | 0.00 | 0/3 | 0/10 | 0/23 |
| run4 | toolsv1.0-populated-suppressed | 180 | completed | 16/20 | 50/70 | 3 | 0 | 3 | 0 | 2 | 0.00 | 0/3 | 0/10 | 0/23 |
| run5 | toolsv1.0-populated-included-canary | 181 | completed | 6/20 | 13/70 | 1 | 1 | 0 | 0 | 0 | 0.03 | 1/3 | 0/10 | 0/23 |

**run5 is not comparable to run3 and run4 on recall.** It audits a
different feature matrix: one removed column, `recoveries`, was
reintroduced, and the model was refitted with it. The recall denominator
is the same 39 true positives in all three rows, but in run3 and run4
none of the 39 is present in the matrix, and in run5 exactly one is. A
run cannot flag a column the model does not read, so recall on the
180-column rows measures something different from recall on the
181-column row. Read run5's recall of 0.03 as one find out of one
findable, not as 2.6 percent of a reachable target.

Precision is comparable across all three; tier counts are comparable
only within the same matrix.

Directories: run3
`20260825T050726__REAL__toolsv1.0-populated-included__run3`
(precision 0.00; input 362,621, output 23,275); run4
`20260825T133738__REAL__toolsv1.0-populated-suppressed__run4-ablated`
(precision 0.00; input 313,078, output 29,288); run5
`20260825T141400__REAL__toolsv1.0-populated-included-canary__run5-canary`
(precision 1.00; input 31,935, output 4,692).

The `config_id` format gained a variant segment when the canary was
built, so run3 and run4 carry ids without a trailing `-layer1` while an
equivalent run made today would have one. The ids in this table are as
recorded in each run's manifest and have not been rewritten.

run3 and run4 are the ablation pair: same ceilings, same model, same
harness, differing only in whether the dictionary's `populated` field was
returned. Both flagged `all_util_was_missing` and
`open_acc_6m_was_missing`; run4 added `term` at low confidence. Every
scored figure is identical across the pair.

### Runs not entered

| run | termination | turns | calls | max_tokens | reason |
|---|---|---|---|---|---|
| firstlight | call_limit | 3/3 | 5/8 | 2,000 | ceilings set low for a first live check |
| run1 | truncated | 4/12 | 10/40 | 2,000 | cut off mid-tool-call on an intermediate exchange |
| run2 | call_limit | 12/12 | 37/40 | 12,400 | exhausted both ceilings still investigating; no answer written |

## A scoring gap in the hard negatives, found by run3

The fourteen hard negatives are bureau columns whose `populated` string
carries a clause about Lending Club beginning to collect them around
December 2015. Feature preparation also produced a `_was_missing` flag
for each one, recording whether the parent had a value. Both the column
and its flag are inputs to the model, so the trap is twenty-eight
columns wide. The answer key listed only the fourteen parents, and the
scorer matched flags by exact name, so a flag on a derivative fell
through to the plain false-positive bucket and the hard-negative count
reported zero.

The gap was found by an agent walking into it. Run3 flagged
`all_util_was_missing` and `open_acc_6m_was_missing`, and the report
showed two false positives and "hard negatives flagged: 0" — which read
as an agent making two unremarkable errors rather than an agent hitting
the discriminating case twice. The stated reasons named the
December-2015 clause explicitly, which is what made the mis-scoring
visible; a reader checking only the numbers would not have caught it.

The gap was one-directional and could not have inflated any result in
the agent's favour. True positives were removed from the dataset during
construction, before feature preparation ran, so none of them has a
derivative in the feature matrix and none ever could. Derivatives
therefore exist only for columns the model kept, which means the failure
mode was always to under-count false positives, never to over-count true
ones. Every figure in run3's report other than the false-positive and
hard-negative lines was unaffected by the fix.

The scorer now resolves an engineered derivative to its parent and
scores it against whichever set the parent belongs to. Set membership is
unchanged: derivatives are resolved at scoring time and never added to a
set, and the self-check asserts both that every derivative of a graded
column resolves to its parent and that no derivative has joined a set.
Raw and derivative flags are reported separately rather than summed, so
"hard negatives flagged: 2 (2 via `_was_missing` derivatives)" cannot be
mistaken for two columns named outright. Recall counts distinct parents,
so flagging both a column and its derivative registers as one find
against the ground truth and two claims against precision.

The one-hot columns carry the same parent relationship. No categorical
parent currently sits in a graded set, so nothing scores differently
today; the mapping covers them anyway, so the gap cannot reopen quietly
if a future feature set changes that.

## What run3 produced

Run3 completed of its own accord — `end_turn`, sixteen of twenty
allowed exchanges, fifty-two of seventy allowed tool calls, no ceiling
reached. It was the first run to reserve budget and write a final answer
rather than being cut off.

It reported two flags, `all_util_was_missing` and
`open_acc_6m_was_missing`. Both are hard negatives reached through their
derivatives. Recall was 0.0 and precision 0.0; no true positive was
found, and all three residual tiers scored zero.

Its stated reason for both was the same. The underlying bureau field was
only collected from around December 2015, so the missingness flag stands
in for loan vintage rather than for borrower behaviour; the flag is
near-constant across the evaluation windows, with 99.98 and 99.99
percent of test rows receiving an identical contribution; and because
both the 2016 validation year and the 2017 test year fall entirely after
the collection cutoff, agreement between validation and test performance
cannot demonstrate that the model's behaviour on this feature
generalises.

That is an argument about vintage coverage. It is not an argument about
target leakage, and the answer key scores only target leakage. The
argument is also not a string match on the timing clause: it reasons
from the SHAP distribution to a claim about what the two evaluation
periods can and cannot establish. Whether it is correct is a separate
question from whether it is the question being graded.

## The ablation result

Suppressing the `populated` field changed nothing.

run3 and run4 differ only in whether that field was returned by
`lookup_feature` and `search_data_dictionary`. Both completed on their
own signal at sixteen exchanges. Both flagged `all_util_was_missing` and
`open_acc_6m_was_missing`. Both scored recall 0.0, precision 0.0, and
zero in every residual tier. Call counts were fifty-two and fifty. run4
added a third flag, `term`, at low confidence. The two hard negatives
were reached identically with and without the field.

This is the direct confirmation of the description scan recorded above.
That scan found timing language in the descriptions of thirty-six of the
thirty-nine true positives, and predicted that removing the one uniform
timing field would remove nothing an agent was relying on. The paired
runs show exactly that: the agent did not lose the ability to reason
about when a column is populated, because the descriptions still said
so, and in the event it reached the same conclusions by the same route.

The ablation, as designed, cannot answer the question it was built for.
It was meant to separate an agent reading meaning from an agent matching
one field's phrasing. It cannot, because the suppressed condition is not
a timing-blind condition. Nothing here is a surprise: the limitation was
established by scanning the descriptions before either run was made, and
is recorded above under what the ablation measures now. The paired runs
confirm a known defect in the instrument rather than discovering one.

Two things the result does not establish. It does not show the agent is
insensitive to the dictionary, only that this particular removal left
the relevant information intact. And with recall at zero in both arms,
the comparison has no dynamic range: two runs that both find nothing
would look identical whether or not the ablation worked.

## What the agent actually audited

Across both runs there are five flags carrying three distinct arguments.
None of the three is about target leakage.

The first is that a feature is near-constant in the holdout:
`all_util_was_missing` contributes in one direction on 99.98 percent of
sampled test rows, so the branch of model behaviour learned from the
more heterogeneous training population is barely exercised in the test
set. The second is a train/test mismatch in data completeness, argued
from the same distributional evidence for `open_acc_6m_was_missing`. The
third is outcome maturity: 60-month loans issued in 2017 may not have
revealed their final state by the end of the data, so the held-out score
may not survive those loans maturing.

All three are arguments about whether the held-out figure is a valid
estimate. The answer key scores whether a column carries information
unavailable at application. These are different properties, and an
argument of the first kind scores zero however sound it is.

The sharpest single observation is in run4's third flag. Arguing that
`term` may be distorted by differential outcome maturity, the agent
reasoned from `loan_status` — naming it as the presumed source of the
default label and citing that its values include a non-terminal
"Current" alongside "Fully Paid" and "Charged Off". `loan_status` is a
tier A true positive, the most explicit post-outcome column in the set.
The agent read it, understood what it records, used it as a premise, and
did not flag it.

The tool log shows the encounter was deliberate rather than incidental.
It searched for `loan_status` at call 13, looked it up at call 21, and
at call 22 called `get_feature_shap_detail` on it, which returned
`found=false` — so the agent also established that `loan_status` is
documented but is not one of the 180 columns the model reads.

What this suggests is that the agent was answering a different question.
It treated the label's definition as context for reasoning about the
evaluation rather than as a candidate finding, which is consistent with
every other flag it produced. What it does not show is failure to
notice. The column was retrieved three times and its contents were used
correctly. A reader should also weigh the call-22 result: having
established that `loan_status` is not a model input, the agent had a
coherent reason not to flag it, since a column the model does not read
cannot be a route by which the model sees the answer. That reading is
available from the transcript, and it is not the same as the agent
having missed the column.

## The canary

Runs 3 and 4 left the detection question open. In both, the agent
correctly observed that the leaking columns are not model inputs, so
neither run tested whether it detects leakage that is actually reachable
by the model. run5 tested that by reintroducing one removed column.

`recoveries` was chosen and the choice was measured rather than assumed.
A nonzero value implies default with probability 1.000000 and no false
positives, but it fires on only two thirds of defaults, so the model
cannot become trivially perfect. Held-out ROC-AUC moved from 0.7296 to
0.8730. Two candidates that look like obvious leaks on paper,
`out_prncp` and `hardship_flag`, were rejected on measurement: both are
constant in the resolved 2014-2017 subset and would have leaked nothing.

The canary was caught, at high confidence, with precision 1.0 and no
false positives. The agent's stated reason was that the column is only
populated after a loan has already been charged off, so it encodes
post-default outcome information that would not exist when a real
prediction must be made. Its evidence cited three independent routes:
the dictionary entry, the SHAP ranking, and the ablation.

Two differences from the earlier pair are worth recording. run5 finished
in six exchanges and thirteen tool calls, against sixteen exchanges and
around fifty calls in each of run3 and run4. And it flagged nothing
else: the two `_was_missing` hard negatives that both earlier runs
flagged did not appear. Neither difference is cleanly attributable. run5
audited a different matrix and a different model, and stopped much
earlier, so the absence of the hard-negative flags is confounded with
both.

What the catch establishes is bounded, and the bound was set in the
design before the run rather than after it. Tier A is the weakest
positive this experiment could produce. `recoveries` is signalled three
ways at once: its description states the outcome, its SHAP attribution
is 8.6 times the next feature and 44.6 percent of the total, and its
ablation moves held-out AUC by 0.1434. A catch under those conditions
establishes that detection works when the leak is a model input and
loudly signalled. It says nothing about tier C, where a description
names a post-origination programme without stating an outcome, and
nothing about a leak carrying no descriptive giveaway. A tier A miss
would have been the informative result; a tier A catch is the floor.

## What the five runs jointly establish

Known:

The agent completes and produces a well-formed answer when it is told
its budget. The three runs that stated the ceilings in the prompt all
ended on the agent's own signal; the two that did not were cut off, one
by an output limit and one by exhausting both ceilings.

Detection works in the loudest case. Given a leaking column the model
actually reads, with a description stating the outcome, dominant SHAP
attribution, and a large ablation delta, the agent flagged it, flagged
nothing else, and cited all three routes.

With no leaking column in the matrix, the agent flags none. In run3 and
run4 it returned no true positives and instead argued about distribution
and validity: a near-constant feature in the holdout, a train/test
mismatch in data completeness, and outcome maturity under a non-terminal
loan status.

Suppressing the `populated` field changed nothing measurable. The same
two hard negatives were reached with and without it, and every scored
figure was identical.

Not known:

Whether detection extends to tier B or tier C, or to a leak with no
descriptive giveaway. No run has presented the agent with one.

Whether the two hard-negative flags in run3 and run4 indicate a
systematic weakness. They did not recur in run5, but run5 differed in
matrix, model, and length, so the comparison establishes nothing.

Whether the distribution and validity arguments are correct. They remain
ungraded; the scorer cannot settle them and no one has yet.

Whether the ablation would show anything if it could be run under a
genuinely timing-blind condition. That condition was never achieved and,
on this dictionary, cannot be.

## An unresolved mismatch between the prompt and the ground truth

The system prompt asks the agent to decide whether the held-out figure
is a trustworthy estimate of performance on new loans, and to report
anything it finds that would make that reading misleading. It does not
say what kind of problem to look for, deliberately: naming one would
hand over the answer.

The answer key scores one kind of problem. Its true positives are the
thirty-nine columns removed for carrying post-application information,
and nothing else counts as a find.

These two are not the same question. A vintage artifact of the sort
run3 described would, if the argument holds, make the held-out figure
misleading in exactly the way the prompt asks about, while scoring zero
against the key. An agent can satisfy the instruction it was given and
record precision 0.0 and recall 0.0.

Run3's result is therefore not straightforwardly a miss. The agent
investigated for sixteen exchanges, declined to flag any of the columns
the key rewards, and returned two findings of a different kind with
reasoning that does not reduce to pattern matching. Whether that
represents failure to detect leakage, a decision that no leakage was
present, or success at answering a question the key does not ask, cannot
be settled by the numbers in the report.

The mismatch is recorded here rather than resolved. Narrowing the prompt
to name leakage would make the evaluation circular, which is the thing
the prompt was written to avoid. Broadening the key to credit other
categories of finding would require deciding, in advance and without
reference to any run, what counts as a legitimate threat to the held-out
figure — a specification that does not currently exist. Both directions
change what is being measured, and neither should be taken on the
evidence of a single run.
