# Layer 3, Phase 4: gap detection and tool-spec generation

Written 2026-09-14, before any detector, generator or prompt existed, and before any API call for this phase. This file fixes the scope, the question set, the accept rules, the near-misses, the exclusions and the cost position. Changes after that point go in dated amendments at the end, the same way as in `PREREGISTRATION_PHASE3.md`.

Every question below is grounded either in a tool schema in `agent/tools.py`, as surveyed in Phase 4 step 0, or in an artefact fact checked on disk in steps 0b and 1. Where an item rests on the schema alone rather than a disk check, the text says so.

## 1. Scope

### What Phase 4 builds

**A gap detector.** It is given one question in plain English and the eight Layer 2 tools, and it labels the question as answerable by the existing tools, answerable with a stated difference, or not answerable. Where it says answerable, it names the tool calls and the field that carry the answer. Where it says not answerable, it names the closest call and what is missing.

**A tool-spec generator.** For a question the detector labels not answerable, it writes a specification for a tool that would answer it, or declines and says why no tool could.

### What Phase 4 does not build

- **No tool is implemented or run.** A generated spec is text. Nothing in Phase 4 turns a spec into code, and nothing runs in the Phase 3 sandbox.
- **No registry.** Specs are recorded in the run record and admitted nowhere.
- **No human-in-the-loop checkpoint** in front of admission. There is nothing to admit.
- **No Agent-as-a-Judge and no separate verifier.** Where scoring needs judgement, a person adjudicates against the rubric in this file.
- **No change to the eight tools,** their schemas, the two suppression switches, or any artefact.
- **No new artefact is computed.** A spec may say that a new precomputed artefact would be needed. It is not built.
- **No Layer 2 audit run,** no model retraining, and no use of the canary cache.

### The detection protocol

Fixed now, so the accept rules below have something definite to apply to.

- **Model and settings:** `claude-sonnet-5`, the thinking setting in `agent/llm.py`, the moving cache breakpoint from `PREREGISTRATION_PHASE2.md`, and 12,400 max tokens per turn.
- **Tools:** the eight schemas unchanged, served by `ToolLayer` on the honest cache (`outputs/agent_cache/`) with both suppression switches on. The pgvector index must be up: a run whose preflight reports degraded retrieval is not started.
- **One episode per question.** Each episode is independent, with no history carried between questions.
- **Limits per episode:** 8 turns and 16 tool calls. An episode that reaches either limit is scored incorrect for that item. It is not retried.
- **Output:** the episode ends with one JSON object: `{"label": "answerable" | "answerable_with_difference" | "not_answerable", "calls": [{"tool", "arguments", "field"}], "difference_or_missing": string or null}`. Output that does not parse, or has the wrong shape, is scored incorrect.
- **The system prompt** does not exist yet. It is recorded in a dated amendment, with its SHA-256, before the first call. It may not contain any question from section 2, any label, any item's answer, or any of the words "declared", "silent" or "near-miss".
- **Runs:** three complete runs over the question set.
- **Spec generation:** one separate request per item labelled `not_answerable` in parts b and c. It receives the question, the detector's output and the eight schemas, and has no tool access. It returns either `{"spec": {...}}` or `{"decline": string}`.

## 2. The question set

All names and figures come from the honest cache (section 5). All items assume both suppression switches are on.

### 2a. Non-gaps: 9 items

Each is answerable now. For each, the calls listed are the accepted ones. A detector citing a different call is scored incorrect, unless the call is listed here as an accepted alternative.

| # | Question | Accepted calls and field | Grounding |
|---|---|---|---|
| A1 | How many features does the model read, and what are they? | `get_shap_ranking(top_n ≥ 180)`: `total_features` and `ranking[].feature` | Schema: "Values above the total are clamped to it." 180 features, verified. |
| A2 | Is `purpose_wedding` constant on the test set? | `get_feature_target_association(feature="purpose_wedding")`: `is_constant_test` | `purpose_wedding` is in the verified set of 14 test-constant features |
| A3 | What is `all_util`'s standalone ROC-AUC within 2014? | `get_feature_target_association(feature="all_util")`: `auc_2014` together with `undefined_note` | The answer is **null: undefined in that scope**. `all_util` is in the verified set of 35 features with a null `auc_2014`. |
| A4 | Is `all_util` documented in the data dictionary? | `lookup_feature(feature="all_util")`: `found` | No model feature lacks an entry, verified |
| A5 | Where does `max_bal_bc_was_missing` rank by mean absolute SHAP? | `get_feature_shap_detail(feature="max_bal_bc_was_missing")`: `rank_by_mean_abs_shap`; or `get_shap_ranking(top_n ≥ 166)`: `ranking[].rank` | Rank 166. Ranks agree between the two tools for all 180 features, verified. |
| A6 | How many 2014 rows does `all_util`'s coverage profile cover? | `get_feature_coverage(feature="all_util")`: `scopes[scope="2014"].n_rows` | 223,102, verified through the tool |
| A7 | Which 15 features are most correlated with `all_util` on the test set? | `get_correlated_features(feature="all_util", top_k ≥ 15)`: `neighbours` | Returned 15, verified. `all_util` is not test-constant. |
| A8 | How does held-out ROC-AUC change when the model is retrained without its highest-ranked feature? | `get_shap_ranking(top_n ≥ 1)`: `ranking[0].feature`, then `get_ablation_result(feature="term")`: `delta_roc_auc` | Rank 1 is `term`, its ablation is `available=true`, and the ablation set equals the top 20, verified |
| A9 | Is `addr_state` one of the model's inputs? | `get_feature_shap_detail`, `get_feature_coverage` or `get_feature_target_association` with `feature="addr_state"`: `found`; or `get_correlated_features(feature="addr_state")`: `available`; or `get_shap_ranking(top_n ≥ 180)`: absence from `ranking` | The answer is **no, from a false flag**. `addr_state` is documented but not a model input: all five data tools return false for it, verified. `lookup_feature` alone does not answer this (schema: "a name may be documented here and still not be one of the model's inputs"). |

A3 and A9 are traps. Their correct answer is a null and a false flag. A detector that treats every null or false flag as a gap gets both wrong.

### 2b. Declared gaps: 6 items

In each, a tool returns an explicit false flag, and the question cannot be answered.

| # | Question | Declaring call and field | Grounding |
|---|---|---|---|
| B1 | How does held-out ROC-AUC change when the model is retrained without `percent_bc_gt_75`? | `get_ablation_result(feature="percent_bc_gt_75")`: `available=false` | Rank 21. All 160 features ranked 21–180 return `available=false`, verified. |
| B2 | Which features are most correlated with `purpose_wedding` on the test set? | `get_correlated_features(feature="purpose_wedding")`: `available=false` | Test-constant, verified. The tool's message says correlations are undefined for it. |
| B3 | What does `addr_state`'s SHAP distribution look like? | `get_feature_shap_detail(feature="addr_state")`: `found=false` | Not a model input, verified |
| B4 | What share of `addr_state`'s rows hold exactly zero, in each year? | `get_feature_coverage(feature="addr_state")`: `found=false` | Not a model input, verified |
| B5 | What is `addr_state`'s standalone ROC-AUC on the test set? | `get_feature_target_association(feature="addr_state")`: `found=false` | Not a model input, verified |
| B6 | Which features are most correlated with `addr_state` on the test set? | `get_correlated_features(feature="addr_state")`: `available=false` | Not a model input, verified |

Six items, but three distinct causes: B1 falls outside the precomputed set, B2 asks for a quantity that is undefined, and B3 to B6 share one cause, a column the model does not read. B3 to B6 are kept as four items because each is a different tool and a different flag, and a detector can read one tool's flag correctly and misread another's. A seventh item, `get_ablation_result(feature="addr_state")`, was left out: it repeats B1's tool and flag.

### 2c. Silent gaps: 7 items

In each, every relevant tool call succeeds, and the question still cannot be answered from the outputs.

| # | Question | Calls that succeed | Why the outputs do not compose into an answer |
|---|---|---|---|
| C1 | How does held-out ROC-AUC change when `term` and `sub_grade` are removed together? | `get_ablation_result` for `term` and for `sub_grade`, both `available=true` | The schema takes one `feature`, and each figure is one retrain without one column. Two single-column deltas are not a joint retrain, and nothing returns one. |
| C2 | What is `all_util`'s 99th percentile value on the training split? | `get_feature_coverage(feature="all_util")`, `found=true` | Each scope returns `mean`, `std` and `p50`, and no other percentile |
| C3 | When `all_util` is high, does its SHAP contribution push predictions up? | `get_feature_shap_detail(feature="all_util")` and `get_feature_coverage(feature="all_util")`, both `found=true` | One returns a summary of SHAP values, the other a summary of feature values. Neither has rows, so there is nothing to pair a value with its contribution. |
| C4 | Which test rows carry `all_util`'s largest SHAP attributions? | `get_feature_shap_detail(feature="all_util")`, `found=true` | It returns summary statistics only, with no row identifiers and no per-row values |
| C5 | What is `all_util`'s point-biserial correlation with the outcome on the training split? | `get_feature_target_association(feature="all_util")`, `found=true` | Only `point_biserial_test` is returned. The training-split figures are AUCs, not correlations. |
| C6 | Which features are most correlated with `all_util` on the training split? | `get_correlated_features(feature="all_util")`, `available=true` | Schema: correlations are "over the full held-out test set". No training-split figure exists in any tool. |
| C7 | What is the model's ROC-AUC on the 2016 vintage? | `get_ablation_result(feature="term")`, `available=true`; `get_feature_target_association(feature="all_util")`, `found=true` | Ablation reports held-out 2017 scores only, and does not return the full model's score itself. The yearly AUCs are for one feature, not the model. No tool returns a model metric for any year. |

Dropped from this part: correlation for a pair outside each other's 15 neighbours, because no specific pair was checked on disk; and the missing rate of an unflagged feature, which is near-miss 4.

## 3. Accept rules

Frozen before any generation. They apply to each of the three runs separately. The detector is accepted only if every rule below holds on every run. Parts are never pooled into one score.

### Per part

- **Part a, non-gaps.** An item is correct if the label is `answerable` and the cited calls match an accepted call in 2a: tool, argument values and field. **At least 8 of 9 correct, and A3 and A9 both correct.** One miss is allowed on the seven ordinary items. The two traps are mandatory, because they are the items a flag-reading detector fails.
- **Part b, declared gaps.** An item is correct if the label is `not_answerable` and the calls include the declaring call and flag field listed in 2b. **6 of 6.** Reading an explicit flag is mechanical, and any miss means the detector did not read the tool's output.
- **Part c, silent gaps.** An item is correct if all three hold:
  1. the label is `not_answerable`;
  2. the calls include at least one call listed as succeeding in 2c;
  3. `difference_or_missing` states the missing element in that row's last column.

  The third condition is adjudicated by a person, against that column, before any score is computed, with the adjudication recorded per item. **At least 5 of 7.** This is the loosest threshold. It is set this way because judging a stated missing element is less exact than matching a call, and it is stated as looser, not presented as equivalent.

### Why declared and silent gaps are scored apart

A detector that calls every tool and reads the false flags would score well on declared gaps without understanding the tool surface at all, and understanding the tool surface is the capability being claimed. Part b shows only that flags are read. Part c is the evidence that the detector knows what the tools return, and pooling the two would let flag-reading carry a claim it cannot support.

### Why part a makes parts b and c mean anything

The failure also runs the other way. A detector that calls every question a gap scores 100% on parts b and c and 0% on part a. Parts b and c reward saying "not answerable", and part a is the only place that saying it is punished. Without part a, the other two measure nothing.

### Near-misses

Scored separately from all three parts, under the rules in section 4. 2 of 2 on the material items, and 2 of 2 on the weaker criterion for the others.

### Spec generation

Applied per run to every spec or decline produced for parts b and c.

1. **Shape: 100%.** Every spec parses as a tool definition: `name` matching `^[a-z][a-z0-9_]{0,63}$`, a non-empty `description`, and `input_schema` of type `object` with `properties`, where every `required` name is in `properties`.
2. **No escape surface: 0 specs.** No parameter may be named `path`, `file`, `filename`, `filepath`, `dir`, `directory`, `folder`, `sql`, `url`, `uri`, `command`, `cmd`, `code`, `expression` or `script`.
3. **No forbidden source: 0 specs.** No spec may name any file listed in section 5, `data/`, the canary cache, or `recoveries`.
4. **A stated source: 100%.** Every spec has a `data_source` that names one of the six honest-cache artefacts in `agent/tools.py`, or says `new precomputed artefact` and lists its columns. A spec may never require reading data when the tool runs.
5. **Spec or decline, where it is decidable.**
   - A spec is expected for B1 and C1 to C7.
   - A decline is expected for B2, because the quantity is undefined for a constant feature.
   - B3 to B6 are not scored for spec or decline. Whether a tool about a column the model does not read is meaningful is not settled by any schema, so either output is accepted and recorded.

   **7 of the 8 expected specs are produced, and B2 is declined.**

Whether a produced spec would actually answer its question is recorded per item but not scored in Phase 4. No spec is implemented, so nothing could confirm it.

## 4. Near-misses: 4 items

In each, a tool succeeds and returns something that differs, subtly, from what was asked.

### Verified on disk, and standing on schema alone

For the record: the request that set this section asked for "the four that survived step 0b". The step 0b table named only two. The four chosen here merge two kinds of item, and they are kept apart below so the distinction is not lost again.

- **Verified on disk in step 0b:**
  - near-miss 1, which differences were measured through the tools;
  - near-miss 4, the no-null matrices and the flag structure. Its caveat is D9.
- **Standing on schema and code alone, never disk-dependent:**
  - near-miss 3, the search description against the two-tier search in `agent/data_dictionary.py`;
  - near-miss 6, the threshold at `agent/tools.py:80`.

### Material: the tool's answer must not be taken as the question's answer

Correct behaviour: the label is `answerable_with_difference` or `not_answerable`, and `difference_or_missing` states the difference below, adjudicated by a person. The label `answerable` with the tool's value given as the answer is incorrect.

- **NM3. "How many dictionary entries contain the literal text 'balance' in their name or definition?"** `search_data_dictionary(query="balance")` succeeds.
  - **The difference:** `match_count` counts column names containing the text, plus up to 10 further entries matched by meaning within cosine distance 0.45. Those need not contain the text at all. The tool's own no-match message speaks of containing the term, which is how a substring search would behave.
  - **Why material:** a count taken from `match_count` can include entries that fail the condition asked about, so the number answers a different question.
  - The query is the schema's own example. The item depends on the index being up, which was verified with 224 rows.
- **NM4. "What share of `loan_amnt`'s values were missing in the source data, in each year?"** `get_feature_coverage(feature="loan_amnt")` succeeds.
  - **The difference:** `loan_amnt` has no missingness flag, verified, so no missing percentage is returned. Every scope's `n_rows` is complete, and the matrices hold no nulls. That completeness is a property of the matrices, not evidence about the source.
  - **Why material:** reading complete row counts as "0% missing" would be a false statement about the data, and it is exactly the kind of statement an audit rests on.

### Not material: the difference is real, but below any threshold that changes an audit conclusion

The weaker criterion: the label is `answerable` or `answerable_with_difference`, and the cited call and field match the one listed. Whether the detector mentions the difference is recorded, but not scored. A `not_answerable` label is incorrect, because the tool does answer the question, to a precision no audit conclusion depends on.

- **NM1. "What is `max_bal_bc_was_missing`'s mean absolute SHAP value?"**
  - **Accepted calls:** `get_feature_shap_detail(feature="max_bal_bc_was_missing")`, field `mean_abs_shap`; or `get_shap_ranking(top_n ≥ 166)`, field `ranking[].mean_abs_shap`.
  - **The difference:** the two tools return different values. Across 180 features, 173 differ, by at most 3.73e-5 relative and 3.57e-7 absolute. This feature has the largest relative difference.
  - **Why not material:** ranks agree for all 180 features, and a difference in the fifth significant figure of a value of about 5e-5 changes no rank-based or magnitude-based conclusion.
- **NM6. "In what percentage of test rows does `all_util` contribute exactly zero to the prediction?"**
  - **Accepted call:** `get_feature_shap_detail(feature="all_util")`, field `pct_near_zero`.
  - **The difference:** `pct_near_zero` counts rows with an absolute SHAP value of at most 1e-3, not exactly zero. Neither the schema nor the payload states that threshold.
  - **Why not material:** a shift of 1e-3 in log-odds moves a predicted probability by at most 0.025 percentage points, because the slope of the logistic function never exceeds 1/4. No audit conclusion turns on a contribution that small.

## 5. Exclusions and provenance

- **The canary cache and `recoveries` are never used** in any Phase 4 question, answer, prompt, spec rule or scoring step. `recoveries` is the answer the Layer 2 agent is tested on.
- **The provenance rule.** Every name and every figure in the question set comes from the honest cache (`outputs/agent_cache/`) or the honest dictionary. No item may use a name learned from comparing the honest and canary caches. Names that were first seen in that comparison during step 0b were set aside, and every name used here was re-derived from the honest cache alone in step 1.
- **The documented columns that are not model inputs are not listed.** Step 1 found 44. This file names only the one it uses, `addr_state`. The full list overlaps with the columns Layer 1 removed and includes `recoveries`, so reproducing it would put Layer 2's answer into a document the Phase 4 prompts could later be written from.
- **Files that stay out of reach,** as the repo rules require, and are named nowhere in any prompt or spec: `outputs/leakage_drop_log.txt`, `outputs/audit_notes.txt`, `outputs/fairness_ablation_notes.txt`, `outputs/features_notes.txt`, `outputs/build_dataset_notes.txt` and `agent/data_dictionary.py`.
- **No raw or processed data.** Nothing in Phase 4 reads `data/`.

## 6. API cost

**What costs money.** Only requests to `claude-sonnet-5`: detection episodes and spec-generation requests. Token counting is free. Scoring, adjudication and every disk check cost nothing.

**Rough size.** This is an estimate for planning, not a projection.
- **Detection:** 26 items (9 + 6 + 7 + 4) × 3 runs = 78 episodes. At the limit of 8 turns, that is at most 624 requests. Most questions need a few calls, so something nearer 250 to 350 is expected.
- **Spec generation:** at most 13 items per run × 3 runs = 39 requests.
- **Cost:** run11 averaged about $0.032 per request, but those requests carried a history of up to 40,000 tokens. Short detection episodes should cost less. A rough total is $5 to $10.
- **The worst case is far higher.** 624 requests at the full 12,400 output tokens would alone pass the cap, and the ledger refuses any request that could.

**The position.** The Layer 3 ledger stands at $0.361965 of the $15.00 cap, leaving $14.638035.

**The rule.** No Phase 4 request is made until:
1. the first request of each kind has been counted with the free endpoint;
2. a projection has been reported with the expected and worst-case totals against the remaining budget;
3. that projection has been approved.

If the projection does not fit, the number of runs or items is reduced by a dated amendment before any request, never during a run. A run ended by `budget_cap` is reported as ended that way, and its partial results are not scored.

## Amendments

### A1. 2026-09-14. One run instead of three

Written before any prompt existed and before any Phase 4 request.

**The change.** Phase 4 makes one complete run over the question set, not three. Everything in this file that refers to three runs now refers to the one run:
- the protocol's "three complete runs";
- the accept rules applying "to each of the three runs separately";
- the spec-generation rules applying "per run";
- section 6's counts, which fall from 78 detection episodes and 39 spec requests to 26 and 13.

**Why.** Layer 3 does not fit under its $15.00 cap at three runs once Phases 5 to 7 are costed (A2). The cap is not being raised. The plan changed instead.

**What was not reduced.** The question set (9 non-gaps, 6 declared gaps, 7 silent gaps, 4 near-misses), the accept rules, and every threshold stand exactly as frozen. The run count was cut rather than any of them, because a cheaper test must not become an easier one.

**What is lost.** The accept rules were meant to hold on each of three runs, which is a 3-of-3 consistency requirement. That requirement is gone.
- **Why it matters here in particular:** Phase 4 is the first phase in Layer 3 whose subject is non-deterministic. Every Phase 3 tool gave the same output on every run. A detector does not. One run cannot separate a detector that reliably gets an item right from one that got it right once, and it gives no measure of how often the detector's labels change between runs.
- **What a pass on the one run shows:** that the detector met the thresholds once. It does not show that it would meet them again. Any result from Phase 4 is reported with that limitation attached.

### A2. 2026-09-14. The Layer 3 budget, and the Phase 6 design

Written before any prompt existed and before any Phase 4 request. These are the first cost estimates for Phases 5 to 7. No earlier per-phase estimate existed in the repository or in any session.

**Measured numbers the estimates rest on:**
- The eight tool schemas count 1,979 tokens (`PREREGISTRATION_PHASE2.md`, step 2A). `agent/tools.py` has not changed since commit `97a339c`, which predates that count.
- run11, from the ledger and its `messages.json`:
  - 0.3003 tokens per character added between turns;
  - 1,096 tokens added per tool call;
  - 1,785 tokens of echoed assistant turn per turn;
  - output per non-final turn with a median of 880, a mean of 1,121 and a maximum of 3,107;
  - a recorded cost of $0.352383.
- Across Layer 2's 12 real runs, output per turn has a median of 1,213 and a maximum of 2,152.
- The tool results the question set would trigger, dispatched locally and converted at run11's ratio, are 53 to 778 tokens each, except `get_shap_ranking(top_n=180)` at 4,139.
- Rates are those in `PREREGISTRATION_PHASE2.md`.

**Estimates.** Each row says what is arithmetic on the measured numbers and what is a guess.

| Phase | What it runs | Requests | Estimate | Measured | Guessed |
|---|---|---|---|---|---|
| 4, one run | 26 detection episodes and 13 spec requests | 52–108 | $1.00–$4.63 | tool schemas, tool result sizes, run11's output and echo per turn, rates | detector prompt size (1,000–2,000), final output (800–3,000), extra calls (0–2), how calls are grouped into turns, spec prompt and output sizes |
| 5 | code generated from the 8 expected specs, run through the Phase 3 sandbox and validator, with retries | 8–24 | $0.22–$1.49 | rates only | scope (taken from the README roadmap), attempts (1–3), prompt (4,000–6,000), output (2,000–5,000) |
| 6 | two tool-less judges and one verifier over every Phase 4 detection episode | 78 | $2.50 (judges $1.56, verifier $0.94) | rates only | scope, transcript size (6,000), judge prompt (1,500), output per request (1,500) |
| 7 | four end-to-end audit runs | 4 runs | $2.82–$4.23 | run11's $0.352383 | scope, and a cost multiplier of 2–3 over run11 |
| **Total** | | | **$6.54–$12.85** | | |

Against the $14.638035 remaining, this leaves $1.79 to $8.10. The Phase 4 figure is replaced by a projection from counted tokens (the next amendment after the prompts are written) before any request is made.

The counted projection (A4) landed close to this character-ratio estimate, but for offsetting reasons. The prompts are smaller than guessed, and the tool results are larger: A1's tool result counts 7,459 tokens against the ratio's 4,139. The agreement was coincidental, so the character ratio must not be cited later as validated.

**The Phase 6 design decision.** Judges are tool-less and cover every Phase 4 detection episode.
- **Why coverage beats capability:** Phase 6's claim is agreement measured against a chance floor, and judging a third of the sample would weaken that floor. A judge that needs tools to reach its verdict is a second auditor, not a judge.
- **How 78 became 26:** the coverage argument was first made for 78 episodes, priced at $7.49. Once A1 cut Phase 4 to one run, those 78 no longer exist. The substance of the argument still holds: no episode that exists gets left out. Phase 6 therefore judges all 26, which costs $2.50 at the same per-episode rates.
- **The sample size is not incidental.** The chance floor can still be computed at 26 episodes. But the agreement estimate carries a wider uncertainty band at 26 than it would at 78, and that widening is a direct consequence of cutting Phase 4 to one run. Any agreement figure Phase 6 reports must be presented with its sample size and its uncertainty band, and never as if 26 were a free choice.
- **What it gives up:** at full design, tool-using judges over 78 episodes would have cost $23.08, more than the whole remaining budget.

**Phase 6 options that were rejected.**
- **Judging the 26 episodes three times,** $7.49. Repeated passes over the same material measure one judge's consistency with itself, not agreement between independent judges. That is a legitimate metric, but it is not Phase 6's claim, and it would cost $7.49 for the same material that $2.50 covers.
- **Keeping Phase 4 at three runs so 78 episodes exist,** $13.53–$27.11 for Layer 3. It reverses the Phase 4 decision in A1, and breaches the cap at the high end.

**Phase 4 at two runs is reopened, not decided.** The $1.79–$8.10 headroom reopens whether Phase 4 could afford two runs. That will be decided after the pilot, on measured cost per episode, not now on estimates. Until then Phase 4 stays frozen at one run.

**Rejected, with reasons.**
- **A second cache breakpoint on the system prompt,** to share the prefix across episodes, would save $0.55–$0.72. It would reinstate a design `PREREGISTRATION_PHASE2.md` rejected on its own merits, and the saving is not worth that precedent.
- **Cutting Phase 7 from four runs to two** would save up to $1.41. The end-to-end runs are that phase's evidence.

**How firm these numbers are.** Only the Phase 4 row rests substantially on measured numbers. Phases 5 to 7 have no document defining their scope, so their rows are planning figures and not commitments. Each phase will get its own projection from counted tokens before it spends.

### A3. 2026-09-14. The two prompts, recorded by hash

Written after both prompts existed and before any Phase 4 request, as section 1 requires.

| Prompt | File | SHA-256 | Size |
|---|---|---|---|
| Detector system prompt | `layer3/prompts/phase4_detector_system.txt` | `db401deb03318893e45b7b2fbad804ac7560233b5c4f9d26e25afd0af281e0d8` | 1,665 bytes, 18 lines |
| Spec-generation system prompt | `layer3/prompts/phase4_spec_system.txt` | `6c3cca8f5fca3df3e463f71bdd83a4c6463e6d0280521808bea9475a4db950ca` | 1,386 bytes, 16 lines |

**How they are sent.** Each file's UTF-8 text is sent exactly as it is, with nothing stripped or added.
- **A detection episode:** the detector prompt is the system prompt, the question is the only content of the first user message, and the eight schemas in `agent/tools.py` are passed as tools.
- **A spec request:** the spec prompt is the system prompt, and one user message holds the question, the detector's JSON output and the eight tool definitions as JSON. No tools are passed.

**What they do not contain.** Neither prompt contains:
- any question from section 2, any item ID, or any part name;
- any answer, any feature name used in the question set, any feature count or year;
- the word `recoveries`, or the name of any file listed in section 5.

This was checked by searching both files for `declared`, `silent`, `near-miss`, `non-gap`, every feature name used in the question set, `balance`, `recoveries`, `180`, the years 2014 to 2017, and the protected file names. There were no matches. The spec prompt names the six honest-cache files, because spec rule 4 requires a tool's data source to be one of them.

**How "any label" is read.** Section 1 says the system prompt may not contain "any label". In that rule, "label" means an item's part assignment (non-gap, declared gap, silent gap, near-miss) and item IDs. The three output values `answerable`, `answerable_with_difference` and `not_answerable` appear in the detector prompt because the frozen output format in section 1 requires the detector to emit one of them.

This is a reading of the rule, not a change to it. No rule text changes. The rule exists to stop the prompt revealing which items are gaps, and the three output values reveal nothing about any item.

**Changes.** Any change to either file after this amendment needs a new dated amendment recording the new hash before any request uses it.

### A4. 2026-09-14. The counted projection, two request details, and the pilot

Written before any Phase 4 generation request. The token counts below were made with the free counting endpoint and spent nothing: the ledger stood at $0.361965 over 13 lines both before and after.

**Two request details left open by A3, fixed here.**
- **The question text sent** is the item's question as written in section 2, with Markdown code formatting removed. `` `all_util` `` is sent as `all_util`. Nothing else in the question changes.
- **The spec request's single user message** is exactly: `Question: {question}`, a blank line, `Check output:`, a newline, the detector's JSON output, a blank line, `Tool definitions:`, a newline, and the eight tool definitions from `agent/tools.py` serialised with `json.dumps` and default settings.

**The counted projection for one run.**
- **Counted:**
  - the first detection request for each of the 26 questions, as sent with the moving breakpoint and the thinking setting: 2,497 to 2,516 tokens;
  - the tokens added by each item's accepted tool calls and their real results, counted without the thinking setting on both sides: 126 to 1,256 tokens, and 7,459 for A1;
  - each of the 13 spec requests' prompts, with a placeholder standing in for the detector's output: 2,228 to 2,243 tokens.
- **Not countable before a response exists:**
  - output per turn, taken from run11's median of 880 and maximum of 3,107;
  - final output, guessed at 800 to 3,000;
  - echoed thinking per turn, taken from run11's 1,785;
  - the number of turns and extra calls, guessed.
- **Result:** detection $0.78 to $4.07 over 52 to 108 requests, plus spec generation $0.20 to $0.46, for **$0.98 to $4.54**. Output is 60–80% of that. Layer 3 with this figure: $6.52 to $12.76, leaving $1.88 to $8.12.

**The pilot.** It was approved as proposed, before any pilot request.
- **What it runs:** detection episodes for A1, C3, B2 and NM3, and one spec request for C3.
  - A1 is the most expensive episode by counted tokens.
  - C3 is the largest exchange among the others.
  - B2 is the cheapest.
  - NM3 is the only one that goes through the pgvector index.
  - Between them they span one non-gap, one silent gap, one declared gap and one near-miss.
  - The traps A3 and A9 are left out on purpose.
- **Projected cost:** $0.152 to $0.731.
- **Its rules:**
  1. Pilot episodes are not scored, and they are not part of the Phase 4 run, which runs all 26 items afresh.
  2. Pilot labels are not used to change either prompt. If a prompt changes anyway, the change needs a new amendment and hash, and the pilot's figures no longer apply to the new prompt.
  3. Pilot requests are recorded in the ledger under their own label.
  4. The pilot's purpose is measurement for the two-run decision reopened in A2.
- **What it measures, as first-class results and not only as cost:**
  - **turns per episode,** and **output tokens per turn** for each request;
  - its cost per episode is reported alongside those.

  Output is 60–80% of the spend and the only part no count can predict, so the two-run decision rests on those two numbers more than on the dollar figure.
- **When it runs:** only after the runner and the spec-request path have been built, checked on mock replies with no API request, the mock results reported, and the pilot approved.

### A5. 2026-09-14. Two runs instead of one

Written after the pilot and before either full run.

**The measured basis.** The pilot (`outputs/layer3/phase4_runs/20260914T125033__REAL__phase4-pilot/`) ran its four episodes and one spec request for $0.090554, against a projected $0.152 to $0.731 for the same work.
- All four episodes completed, in 2 to 3 turns.
- Output ran 58 to 742 tokens per turn, every figure below run11's median of 880.
- **Split by kind:** detection cost $0.080216 for four episodes, $0.020054 each, and the spec request cost $0.010337.
- **Scaled to a full run of 26 episodes and 13 spec requests:** $0.656, and two runs $1.31.
- **The conservative figures:** dividing the whole $0.090554 by four gives $0.0227 per episode. Scaling that and then adding the spec requests gives about $0.72 for one run and $1.44 for two. Those figures count the spec request twice, so they overstate the cost.
- **The limit on this basis:** it rests on four episodes, and a full run may differ.

**Why the run count moved.** A1 cut three runs to one under a budget projection that no longer binds: detection episodes are now measured as far cheaper than audit runs. The question set, the accept rules and every threshold are still exactly as frozen. The cut is being partly reversed, not the test relaxed.

**What two runs give, and what they do not.**
- **Disagreement identifies an unstable item.** If an item gets a different label in each run, it is unstable.
- **Two runs cannot estimate how often an item is unstable.** Two matching labels mean the item matched twice, not that it is stable.
- **2-of-2 is not 3-of-3,** and must not be read as one.

**How the accept rules apply across two runs, fixed now.** This is fixed before either run, not after seeing which items disagree.
- Every rule in section 3 is applied to each run separately, as section 3 was written.
- **The detector is accepted only if every rule holds in both runs.** An item counts toward a part's threshold only within its own run.
- **Runs are never pooled,** and a pass in either run is never enough.
- This applies to parts a, b and c, the near-miss rules, and the spec-generation rules alike.

**Spec requests per run.** Section 1 makes a spec request only for an item in parts b or c that the detector labels `not_answerable` in that run. A run may therefore make fewer than 13. The number made in each run is reported, and an item not labelled `not_answerable` has no spec request in that run.

**The pilot.** Per A4, the pilot's four episodes are not scored. A1, C3, B2 and NM3 are re-run afresh as part of each full run, like every other item.

### A6. 2026-09-14. Phase 4b: a change to the detector prompt's format instruction only

Written after Phase 4 was scored, and before the new prompt existed.

**Why 4b runs.** Phase 4's result (`outputs/layer3/LAYER3_PHASE4.md`) binds output-format compliance and gap detection together and cannot separate them: 20 of 52 final replies were prose followed by a JSON object, and each was scored incorrect on format alone. Phase 4b changes only the detector prompt's instruction about output format and runs again. The difference between the two results isolates how much of Phase 4's failure was format.

**The permitted change, exactly.** One instruction about output format.
- **It may not contain:**
  - a hint;
  - an example answer;
  - any question from section 2, any item, or any label assignment;
  - anything that bears on whether a particular question can be answered.
- **In particular, it may not mention null values, undefined figures, or absent fields.** A3's frozen answer turns on exactly that, and a line about it would defeat the trap.
- **Everything else stays the same:** every other line of the detector prompt is unchanged, and so are the spec-generation prompt (`6c3cca8f…`), the parser, the tools, the question set, the model and every setting in section 1.

**How the change is made.** The new prompt is a new file, `layer3/prompts/phase4b_detector_system.txt`. The A3 file `layer3/prompts/phase4_detector_system.txt` is not edited, because Phase 4's run records carry its hash and must go on referring to a file that matches them. The runner loads the 4b prompt from its own file and refuses it unless it matches the hash recorded at the end of this amendment.

**Phase 4 is not superseded.** Phase 4's result stands as scored. 4b's result will stand beside it. The comparison between the two is itself the finding. If 4b passes, what that shows is that the detector passes with an explicit format instruction. It does not show that Phase 4's detector passed.

**Nothing frozen is touched.** The question set, the accept rules and every threshold are exactly as frozen, and as applied in A5. The detector has now failed against them once, and relaxing them after a failure is the failure mode this project exists to avoid.

**The protocol for 4b.**
- Two full runs back to back, labelled `phase4b-run1` and `phase4b-run2`, with 26 episodes each, and spec requests made under the same rule as Phase 4.
- No pilot.
- Before any request, the Phase 4 mock suite is re-run against the new prompt, to confirm that the hash refusal works and that the parser is unchanged.
- Results are scored under section 3 exactly as Phase 4 was: each run separately, both runs required, and unparsed output incorrect.
- Each run's parse-failure count is reported against Phase 4's 9 and 11.
- Phase 4's two runs cost $0.732420 together. The ledger stands at $1.184947.

**Prediction for A3, written before any 4b run. This is a prediction, not a result.**
- **The expectation:** A3 is labelled `not_answerable` again in both runs, with a reply that parses, so it is scored incorrect again.
- **Why:** in both Phase 4 runs A3's reply parsed. The detector read `auc_2014` as null, gave the right reason, and still labelled the question not answerable. That is a labelling judgement, not a format failure, and a format-only change should not move it.
- **What that would mean:** part a would fail again on the mandatory A3, whatever happens to the parse failures.
- **The rest of the prediction:** parse failures should fall, but not necessarily to zero, because A1 already showed format compliance varying on an unchanged prompt.

**The new prompt's hash.** Recorded once the file existed, and before any request used it.

| Prompt | File | SHA-256 | Size |
|---|---|---|---|
| Phase 4b detector system prompt | `layer3/prompts/phase4b_detector_system.txt` | `f37ed96ff07a0497e3e4aacba73872e95febf3559dd3306e2e880e89fb4769c1` | 1,753 bytes, 18 lines |

**The change, line for line.** The file is byte-for-byte the A3 prompt with one sentence replaced, and nothing else differs.
- **Removed:** `When you have decided, reply with one JSON object and nothing else, in this form:`
- **Added:** `When you have decided, your final reply must be the JSON object alone, beginning with { and ending with }, with no words or blank lines before or after it, in this form:`
- **Checked after writing:** the A3 file still hashes to `db401deb03318893e45b7b2fbad804ac7560233b5c4f9d26e25afd0af281e0d8`.

**The forbidden-content check.** The added line was searched, case-insensitively, for:
- `null`, `undefined`, `absent`, `missing`, `empty`, `none`, `not returned`;
- `example`, `e.g`, `hint`, `trap`;
- `declared`, `silent`, `near-miss`, `non-gap`;
- the three output label values;
- every feature name used in the question set, and `balance`, `recoveries`, `180`, the years 2014 to 2017, `leakage` and `canary`;
- item IDs.

None occurs in it.

Four of those terms occur elsewhere in the prompt, with exactly the same counts as in the A3 prompt, because they come from lines that were not changed:
- `null` (once), in the description of `difference_or_missing`;
- `missing` (twice), in the field name `difference_or_missing`;
- `example` (once), in the field-path example `items[2].value`;
- the three label values, in the definition of the output format.

## Defect register

Numbering continues from D8 in `PREREGISTRATION_PHASE3.md`.

**D9. 2026-09-14.** The no-NaN finding from step 0b rests on parquet `null_count` statistics read from the metadata of `X_train.parquet` and `X_test.parquet`: 0 nulls, with statistics present for every column. `null_count` counts nulls. It does not count NaN stored as a floating-point value, so NaN in the 77 float columns was not ruled out; the 103 integer columns cannot hold NaN. Imputation itself was not verified from any artefact: that the matrices were filled in during feature preparation is a statement about how they were built, and checking it would take the source data, which step 0b did not read. Near-miss 4 depends only on what the tool returns and on the flag structure, both verified. Any claim that the source values were imputed stands on this defect entry, not on a check.

**D10. 2026-09-14.** Phase 5's real risk is scope, not cost. Specs for C2, C3, C5, C6 and C7, if produced as section 3 expects, can only name `new precomputed artefact` as their data source. Each needs something built from `data/` that no current artefact holds: training-split percentiles, value paired with SHAP row by row, training-split point-biserial correlations, training-split correlations, and model scores by year. No known answer exists for any of them, so the Phase 3 validator has nothing to check such a tool against. Phase 5 could therefore turn into building artefacts and new known answers rather than implementing tools. This is recorded now so that scope decision is taken deliberately when Phase 5 starts, and not discovered in the middle of building.

**D11. 2026-09-14.** `run_items` in `layer3/phase4.py` words the reason for a spec request not made wrongly when an episode's reply did not parse. With no parsed output, it prints the termination value (`completed`) where a label belongs, as in "the detector's result was completed, not not_answerable". The decision is correct: with no parsed `not_answerable`, no spec request is made. But the recorded reason is misleading. It is not fixed, because the runner produced the results reported in `LAYER3_PHASE4.md`, and changing it now would separate the code from the record it generated.

**D18. 2026-09-15.** The adjudication section 3 requires is performed late, after the scores were computed and published.

Numbered D18 because numbering continues across the Layer 3 files, and `PREREGISTRATION_PHASE5.md` already holds D12 to D17. Written before any judgement is made.

- **The rule and its timing condition.** Section 3 says part c's third condition "is adjudicated by a person, against that column, before any score is computed". Section 4 leaves the stated difference for the material near-misses to a person in the same way.
- **The condition was not met.** The scores were computed and published in `LAYER3_PHASE4.md` on 2026-09-14 with no adjudication performed. The person now adjudicating has seen those scores.
- **What is done, and how it is labelled.** The adjudication goes ahead as a **late adjudication**. It is labelled late wherever it appears.
  - It is not a deferral, and it is not an exception to the rule.
  - The rule was written with a timing condition, the condition was not met, and the label says so.
- **Its one purpose:** to produce a reference made by a person, not a model, for the judge in the next phase to be compared against.
- **What it does not do.**
  - **It does not complete section 3's pending rule.** That rule's timing condition can no longer be met, so the late adjudication cannot satisfy it.
  - **It changes no Phase 4 or 4b outcome.** Both rules these judgements feed already fail in at least one run whatever the judgements say:
    - part c's upper bound is below 5 of 7 in all four scored runs;
    - the material near-miss rule already fails in Phase 4 run 1 and 4b run 2.
  - **It closes nothing.**
- **Scope: all 16 judgements, not the 8 distinct items.**
  - **The judgements:**
    - 10 for part c: C1 twice, C2 twice, C3 three times, C4, C5 and C7;
    - 6 for the material near-misses: NM3 four times, NM4 twice.
  - **The same item appears with different wording in different runs.**
  - **Why not per item:** the judge will see the same 16 replies, so a reference made per item could not be compared against it. Collapsing the runs into items would also discard the differences in wording.

This is recorded because a rule with a timing condition that was missed cannot be quietly satisfied later. The late judgements are useful for a different purpose, and they are labelled so that they are never read as the adjudication section 3 asked for.

## Result

What was run against this specification, and how it scored under section 3 as frozen, is reported in [LAYER3_PHASE4.md](outputs/layer3/LAYER3_PHASE4.md). That document adds no rule. This file remains the specification.
