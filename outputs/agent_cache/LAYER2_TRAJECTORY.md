# Layer 2 trajectory metrics

## What this is

A retrospective measurement of the existing Layer 2 run records against the specification in [PREREGISTRATION.md](../../PREREGISTRATION.md), frozen before any of these numbers were computed and amended nine times since, each amendment dated and recorded in that file. It measures the agent's mechanics: how runs ended, how long they were, which tools were called and how, whether calls were rejected or repeated, whether cited evidence names tools that were called and figures that tools returned, and how soon the planted column was examined after it first appeared. It does not measure whether the agent's findings were correct. This document reports how the agent got to its conclusions. What it concluded, and whether that was right, is reported in [LAYER2_EVAL.md](LAYER2_EVAL.md). The Layer 3 machinery that will validate a tool before an agent may use it is reported separately, in [LAYER3_PHASE3.md](../layer3/LAYER3_PHASE3.md).

## Scope

Seventeen run directories were passed through the validity precondition and then the scope rule for each metric. Scope is decided by manifest field, never by directory name.

| run | mode | canary | canary_source | outcome |
|---|---|---|---|---|
| firstlight | REAL | False | derived | M1, M14 computed; all other metrics `scope_not_usable` |
| run1 | REAL | False | derived | M1, M14 computed; all other metrics `scope_not_usable` |
| run2 | REAL | False | derived | M1, M14 computed; all other metrics `scope_not_usable` |
| run3 | REAL | False | derived | 13 metrics computed; M18 `scope_not_canary` |
| run4-ablated | REAL | False | derived | 13 metrics computed; M18 `scope_not_canary` |
| run5-canary | REAL | True | field | all 14 computed |
| run6-canary-v2 | REAL | True | field | all 14 computed |
| run7-honest-v2 | REAL | False | field | 13 metrics computed; M18 `scope_not_canary` |
| run8-canary-splitonly | REAL | True | field | all 14 computed |
| run9-honest-nopop | REAL | False | field | M1, M14 computed; all other metrics `scope_not_usable` |
| run10-honest-nopop-30turns | REAL | False | field | 13 metrics computed; M18 `scope_not_canary` |
| mock-down | MOCK | True | field | all 14 `validity_precondition_failed` (retrieval segment `keyword-fallback`) |
| mock-up, mock-splitonly, mock-scopesall, mock-splitonly-v2, mock-scopesall-v2 | MOCK | True | field | all 14 `scope_not_real` |

The sample is 7 usable real runs across 2 tool surfaces, the five-tool keyword surface (version 1.0) and the eight-tool pgvector surface (version 2.0). Every configuration cell holds one usable run. Every figure below is descriptive, and no comparison between configurations is made anywhere in this document.

The A2 seq-mapping assertion, which M18 depends on, passed in all three canary runs. No value was withheld.

## Results

`canary_source` is `derived` where the manifest lacks a `canary` field and canary status was read from the `config_id` suffix, and `field` otherwise.

### M1 termination

The run's termination value, reported beside the ceilings that were in force.

| run | surface | canary | canary_source | termination | max_turns | max_tool_calls | max_tokens_per_turn |
|---|---|---|---|---|---|---|---|
| firstlight | 1.0 | False | derived | call_limit | 3 | 8 | 2000 |
| run1 | 1.0 | False | derived | truncated | 12 | 40 | 2000 |
| run2 | 1.0 | False | derived | call_limit | 12 | 40 | 12400 |
| run3 | 1.0 | False | derived | completed | 20 | 70 | 12400 |
| run4-ablated | 1.0 | False | derived | completed | 20 | 70 | 12400 |
| run5-canary | 1.0 | True | field | completed | 20 | 70 | 12400 |
| run6-canary-v2 | 2.0 | True | field | completed | 20 | 70 | 12400 |
| run7-honest-v2 | 2.0 | False | field | completed | 20 | 70 | 12400 |
| run8-canary-splitonly | 2.0 | True | field | completed | 20 | 70 | 12400 |
| run9-honest-nopop | 2.0 | False | field | turn_limit | 20 | 70 | 12400 |
| run10-honest-nopop-30turns | 2.0 | False | field | completed | 30 | 70 | 12400 |

### M3 raw length

Turns and logged tool calls.

| run | surface | canary | canary_source | turns | tool calls |
|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 16 | 52 |
| run4-ablated | 1.0 | False | derived | 16 | 50 |
| run5-canary | 1.0 | True | field | 6 | 13 |
| run6-canary-v2 | 2.0 | True | field | 6 | 17 |
| run7-honest-v2 | 2.0 | False | field | 14 | 33 |
| run8-canary-splitonly | 2.0 | True | field | 13 | 31 |
| run10-honest-nopop-30turns | 2.0 | False | field | 12 | 29 |

### M4 calls per tool-bearing turn

The number of tool calls in each assistant turn that made at least one.

| run | surface | canary | canary_source | tool-bearing turns | mean | distribution |
|---|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 15 | 3.4667 | 1, 4, 10, 1, 3, 4, 5, 5, 4, 4, 3, 3, 2, 2, 1 |
| run4-ablated | 1.0 | False | derived | 15 | 3.3333 | 1, 3, 6, 1, 3, 2, 3, 2, 1, 3, 3, 6, 5, 3, 8 |
| run5-canary | 1.0 | True | field | 5 | 2.6000 | 1, 2, 1, 3, 6 |
| run6-canary-v2 | 2.0 | True | field | 5 | 3.4000 | 1, 4, 3, 6, 3 |
| run7-honest-v2 | 2.0 | False | field | 13 | 2.5385 | 1, 4, 5, 4, 2, 3, 3, 2, 3, 2, 2, 1, 1 |
| run8-canary-splitonly | 2.0 | True | field | 12 | 2.5833 | 1, 2, 2, 2, 2, 2, 6, 4, 3, 2, 3, 2 |
| run10-honest-nopop-30turns | 2.0 | False | field | 11 | 2.6364 | 1, 3, 4, 1, 4, 3, 3, 3, 1, 3, 3 |

The first turn of every usable run made one call, to `get_shap_ranking` with `top_n` 20.

### M5 tool mix

Calls per tool, with each count's share of the run's logged calls. Shares are read within a surface only. "n/a" marks a tool that does not exist on that surface; "none" marks a tool that exists and was not called.

| run | surface | canary | canary_source | lookup_feature | search_data_dictionary | get_shap_ranking | get_feature_shap_detail | get_ablation_result | get_feature_coverage | get_feature_target_association | get_correlated_features |
|---|---|---|---|---|---|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 21 (0.4038) | 9 (0.1731) | 2 (0.0385) | 14 (0.2692) | 6 (0.1154) | n/a | n/a | n/a |
| run4-ablated | 1.0 | False | derived | 5 (0.1000) | 11 (0.2200) | 2 (0.0400) | 23 (0.4600) | 9 (0.1800) | n/a | n/a | n/a |
| run5-canary | 1.0 | True | field | 1 (0.0769) | 3 (0.2308) | 1 (0.0769) | 7 (0.5385) | 1 (0.0769) | n/a | n/a | n/a |
| run6-canary-v2 | 2.0 | True | field | 3 (0.1765) | 3 (0.1765) | 1 (0.0588) | none | 1 (0.0588) | 7 (0.4118) | 1 (0.0588) | 1 (0.0588) |
| run7-honest-v2 | 2.0 | False | field | none | 7 (0.2121) | 2 (0.0606) | 6 (0.1818) | 3 (0.0909) | 5 (0.1515) | 9 (0.2727) | 1 (0.0303) |
| run8-canary-splitonly | 2.0 | True | field | 1 (0.0323) | 3 (0.0968) | 1 (0.0323) | 12 (0.3871) | 4 (0.1290) | 6 (0.1935) | 3 (0.0968) | 1 (0.0323) |
| run10-honest-nopop-30turns | 2.0 | False | field | none | 5 (0.1724) | 2 (0.0690) | none | 2 (0.0690) | 12 (0.4138) | 7 (0.2414) | 1 (0.0345) |

### M6 tool coverage

Distinct tools called that exist on the run's surface, over the number that exist.

| run | surface | canary | canary_source | distinct tools called | tools available | coverage |
|---|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 5 | 5 | 1.0000 |
| run4-ablated | 1.0 | False | derived | 5 | 5 | 1.0000 |
| run5-canary | 1.0 | True | field | 5 | 5 | 1.0000 |
| run6-canary-v2 | 2.0 | True | field | 7 | 8 | 0.8750 |
| run7-honest-v2 | 2.0 | False | field | 7 | 8 | 0.8750 |
| run8-canary-splitonly | 2.0 | True | field | 8 | 8 | 1.0000 |
| run10-honest-nopop-30turns | 2.0 | False | field | 6 | 8 | 0.7500 |

No run called a tool name outside its surface.

### M8 rejected-call rate and M10 repeat calls

M8 counts logged calls with `ok == false`. M10 counts logged calls whose canonical form repeats an earlier call in the same run.

No logged call was rejected in any of the seven usable runs. Across all 225 logged calls, the count of `unknown_tool`, `unexpected_argument`, `bad_arguments` and `failed` outcomes is zero.

No logged call repeated an earlier call in any of the seven usable runs. This was confirmed by an independent read of `tool_call_log.json` that paired each call's tool with its raw arguments, with no canonicalisation: in every run, each logged call forms a distinct pair, 225 distinct pairs from 225 calls, so canonicalisation had no effect on the result.

| run | surface | canary | canary_source | logged calls | rejected | repeated |
|---|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 52 | 0 | 0 |
| run4-ablated | 1.0 | False | derived | 50 | 0 | 0 |
| run5-canary | 1.0 | True | field | 13 | 0 | 0 |
| run6-canary-v2 | 2.0 | True | field | 17 | 0 | 0 |
| run7-honest-v2 | 2.0 | False | field | 33 | 0 | 0 |
| run8-canary-splitonly | 2.0 | True | field | 31 | 0 | 0 |
| run10-honest-nopop-30turns | 2.0 | False | field | 29 | 0 | 0 |

### M9 empty-result rate

Calls returning no data: outcomes `not_found`, `not_precomputed`, `not_available` or `match_count=0`.

| run | surface | canary | canary_source | logged calls | calls returning no data | rate |
|---|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 52 | 11 | 0.2115 |
| run4-ablated | 1.0 | False | derived | 50 | 13 | 0.2600 |
| run5-canary | 1.0 | True | field | 13 | 6 | 0.4615 |
| run6-canary-v2 | 2.0 | True | field | 17 | 6 | 0.3529 |
| run7-honest-v2 | 2.0 | False | field | 33 | 6 | 0.1818 |
| run8-canary-splitonly | 2.0 | True | field | 31 | 11 | 0.3548 |
| run10-honest-nopop-30turns | 2.0 | False | field | 29 | 4 | 0.1379 |

### M11 feature breadth

Distinct columns named in a `feature` argument, split by whether a matrix tool (`get_feature_shap_detail`, `get_feature_coverage`, `get_feature_target_association`) found them.

| run | surface | canary | canary_source | distinct | in matrix | out of matrix | unclassified |
|---|---|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 36 | 4 | 10 | 22 |
| run4-ablated | 1.0 | False | derived | 31 | 12 | 11 | 8 |
| run5-canary | 1.0 | True | field | 7 | 1 | 6 | 0 |
| run6-canary-v2 | 2.0 | True | field | 9 | 1 | 6 | 2 |
| run7-honest-v2 | 2.0 | False | field | 17 | 11 | 6 | 0 |
| run8-canary-splitonly | 2.0 | True | field | 17 | 6 | 11 | 0 |
| run10-honest-nopop-30turns | 2.0 | False | field | 17 | 13 | 4 | 0 |

The member lists are in `outputs/agent_cache/trajectory_metrics.json`.

### M14 input and cost

Input and output tokens, the primary quantity. Cost is withheld on every row: A3 requires the rate to be verified against the Anthropic Console billing record or Anthropic's first-party pricing page before any cost figure is published, and neither has been consulted. The assumed rates, carried with every row, are $2.00 per million input tokens and $10.00 per million output tokens for `claude-sonnet-5`, from the claude-api reference cached 2026-06-24. Cache tokens are zero in every run.

| run | surface | canary | canary_source | input tokens | output tokens | cost |
|---|---|---|---|---|---|---|
| firstlight | 1.0 | False | derived | 12,679 | 1,163 | withheld |
| run1 | 1.0 | False | derived | 36,087 | 3,667 | withheld |
| run2 | 1.0 | False | derived | 241,559 | 25,825 | withheld |
| run3 | 1.0 | False | derived | 362,621 | 23,275 | withheld |
| run4-ablated | 1.0 | False | derived | 313,078 | 29,288 | withheld |
| run5-canary | 1.0 | True | field | 31,935 | 4,692 | withheld |
| run6-canary-v2 | 2.0 | True | field | 40,764 | 2,845 | withheld |
| run7-honest-v2 | 2.0 | False | field | 303,979 | 18,754 | withheld |
| run8-canary-splitonly | 2.0 | True | field | 167,323 | 13,299 | withheld |
| run9-honest-nopop | 2.0 | False | field | 502,004 | 21,744 | withheld |
| run10-honest-nopop-30turns | 2.0 | False | field | 274,562 | 23,260 | withheld |

### M16 answer shape

Parsed findings records and their confidence values.

| run | surface | canary | canary_source | records | high | medium | low | explicit no findings | parser warnings |
|---|---|---|---|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 2 | 0 | 2 | 0 | False | 0 |
| run4-ablated | 1.0 | False | derived | 3 | 0 | 2 | 1 | False | 0 |
| run5-canary | 1.0 | True | field | 1 | 1 | 0 | 0 | False | 0 |
| run6-canary-v2 | 2.0 | True | field | 1 | 1 | 0 | 0 | False | 0 |
| run7-honest-v2 | 2.0 | False | field | 1 | 0 | 1 | 0 | False | 0 |
| run8-canary-splitonly | 2.0 | True | field | 3 | 1 | 1 | 1 | False | 0 |
| run10-honest-nopop-30turns | 2.0 | False | field | 3 | 0 | 2 | 1 | False | 0 |

### M17a evidence-tool grounding

Whether each record's evidence names at least one tool, and whether every tool it names was called in that run.

| run | surface | canary | canary_source | record | flag | tools named | grounded |
|---|---|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 1 | all_util_was_missing | lookup_feature, get_feature_shap_detail | True |
| run3 | 1.0 | False | derived | 2 | open_acc_6m_was_missing | lookup_feature, get_feature_shap_detail | True |
| run4-ablated | 1.0 | False | derived | 1 | all_util_was_missing | get_feature_shap_detail | True |
| run4-ablated | 1.0 | False | derived | 2 | open_acc_6m_was_missing | get_feature_shap_detail | True |
| run4-ablated | 1.0 | False | derived | 3 | term | lookup_feature, get_shap_ranking | True |
| run5-canary | 1.0 | True | field | 1 | recoveries | none | False (no tool named) |
| run6-canary-v2 | 2.0 | True | field | 1 | recoveries | lookup_feature, get_ablation_result, get_feature_target_association | True |
| run7-honest-v2 | 2.0 | False | field | 1 | term | get_feature_target_association | True |
| run8-canary-splitonly | 2.0 | True | field | 1 | recoveries | lookup_feature, get_ablation_result | True |
| run8-canary-splitonly | 2.0 | True | field | 2 | open_acc_6m_was_missing | get_feature_coverage, get_feature_target_association | True |
| run8-canary-splitonly | 2.0 | True | field | 3 | all_util_was_missing | get_shap_ranking, get_feature_coverage | True |
| run10-honest-nopop-30turns | 2.0 | False | field | 1 | all_util_was_missing | get_shap_ranking, get_feature_coverage | True |
| run10-honest-nopop-30turns | 2.0 | False | field | 2 | open_acc_6m_was_missing | get_feature_coverage | True |
| run10-honest-nopop-30turns | 2.0 | False | field | 3 | acc_open_past_24mths | get_ablation_result, get_feature_target_association | True |

### M17b numeric grounding

Each numeric token in a record's evidence, classified automatically as matched or unmatched against the run's payload numbers, with unmatched tokens then adjudicated by hand into derived, quoted, prompt or multiply sourced under A9. The adjudications are in `outputs/agent_cache/m17b_adjudications.json`. No adjudication was rejected by the script's evidence checks.

| run | surface | canary | canary_source | record | flag | matched | unmatched | derived | quoted | prompt | multiply sourced |
|---|---|---|---|---|---|---|---|---|---|---|---|
| run3 | 1.0 | False | derived | 1 | all_util_was_missing | 1 | 0 | 0 | 1 | 2 | 0 |
| run3 | 1.0 | False | derived | 2 | open_acc_6m_was_missing | 1 | 0 | 0 | 1 | 0 | 0 |
| run4-ablated | 1.0 | False | derived | 1 | all_util_was_missing | 4 | 0 | 0 | 0 | 0 | 0 |
| run4-ablated | 1.0 | False | derived | 2 | open_acc_6m_was_missing | 5 | 0 | 0 | 0 | 0 | 0 |
| run4-ablated | 1.0 | False | derived | 3 | term | 4 | 0 | 0 | 0 | 0 | 0 |
| run5-canary | 1.0 | True | field | 1 | recoveries | 4 | 0 | 1 | 0 | 0 | 1 |
| run6-canary-v2 | 2.0 | True | field | 1 | recoveries | 5 | 0 | 0 | 0 | 0 | 1 |
| run7-honest-v2 | 2.0 | False | field | 1 | term | 12 | 0 | 0 | 0 | 0 | 0 |
| run8-canary-splitonly | 2.0 | True | field | 1 | recoveries | 3 | 0 | 1 | 0 | 0 | 2 |
| run8-canary-splitonly | 2.0 | True | field | 2 | open_acc_6m_was_missing | 3 | 0 | 0 | 0 | 0 | 0 |
| run8-canary-splitonly | 2.0 | True | field | 3 | all_util_was_missing | 3 | 0 | 0 | 0 | 0 | 0 |
| run10-honest-nopop-30turns | 2.0 | False | field | 1 | all_util_was_missing | 8 | 1 | 0 | 0 | 0 | 0 |
| run10-honest-nopop-30turns | 2.0 | False | field | 2 | open_acc_6m_was_missing | 11 | 0 | 1 | 0 | 0 | 0 |
| run10-honest-nopop-30turns | 2.0 | False | field | 3 | acc_open_past_24mths | 7 | 0 | 0 | 0 | 0 | 0 |

Multiply sourced tokens and the sources recorded for each:

| run | canary_source | record | token | sources |
|---|---|---|---|---|
| run5-canary | field | 1 | 0.8730 | derived, prompt |
| run6-canary-v2 | field | 1 | 0.8730 | derived, prompt |
| run8-canary-splitonly | field | 1 | 2017 | quoted, prompt |
| run8-canary-splitonly | field | 1 | 0.8730 | derived, prompt |

No token was flagged as having its classification turn on a rounding tie, and no evidence contained scientific notation.

### M18 exposure-to-investigation latency

For canary runs: the seq of the first tool result naming the planted column, the seq of the first call whose `feature` argument is that column, and the difference.

| run | surface | canary | canary_source | planted | exposure seq | investigation seq | gap |
|---|---|---|---|---|---|---|---|
| run5-canary | 1.0 | True | field | recoveries | 1 | 2 | 1 |
| run6-canary-v2 | 2.0 | True | field | recoveries | 1 | 2 | 1 |
| run8-canary-splitonly | 2.0 | True | field | recoveries | 1 | 2 | 1 |

Exposure seq 1, investigation seq 2 and a gap of 1 are identical in all three canary runs, across two tool surfaces and both settings of `include_vintage_scopes`.

## Four findings

### 1. The 0.8730 figure in every canary run is multiply sourced

Each canary run's evidence cites a held-out ROC-AUC of 0.8730 for the model with `recoveries` included. That figure has two sources in each run, and the records cannot say which the agent used.

It is stated verbatim in the system prompt: "Its score on the held-back 2017 loans is a ROC-AUC of 0.8730; on the 2016 loans used while selecting settings it scored 0.9020." That sentence was rendered from `agent/prompts.py` at `eb89b98` for run5-canary and at HEAD for run6 and run8, using the canary tuning record. Each render's length matches the run's recorded `system_prompt_chars`: 4,268 characters for run5-canary and 4,624 for run6 and run8.

It is also recoverable from `get_ablation_result` for `recoveries`, which the agent called in each run: at seq 4 in run5-canary, seq 3 in run6-canary-v2 and seq 4 in run8-canary-splitonly. That tool returns no baseline field. It returns `roc_auc_without_feature` 0.7295752764137673 and `delta_roc_auc` −0.1434433443801116, and

0.7295752764137673 − (−0.1434433443801116) = 0.8730186207938789,

which is 0.8730 at four decimal places.

M17a marks each of these records grounded, run5-canary's excepted because it names no tool at all. That is correct under M17a's definition. M17a asks whether a tool cited in the evidence was called. M17b asks whether a figure cited in the evidence appears in what the tools returned. The two metrics describe the same sentence and answer different questions.

### 2. One label, two different quantities

In run10-honest-nopop-30turns record 2, the agent's evidence reads, in one sentence: "get_feature_coverage returns pct_zero/mean = 100%/1.0 (2014), 94.95%/0.9496 (2015), then a hard drop to 99.98%/0.0002 (2016) and 100%/0.0 (2017/test)". The figures before each slash are presented as pct_zero. The payload is `get_feature_coverage` for `open_acc_6m_was_missing` at seq 12.

| scope | stated as pct_zero | payload pct_zero | payload mean × 100 | stated figure equals |
|---|---|---|---|---|
| 2014 | 100 | 0.0 | 100.0 | mean × 100 |
| 2015 | 94.95 | 5.0447 | 94.9553 | mean × 100 |
| 2016 | 99.98 | 99.9816 | 0.0184 | pct_zero |
| 2017 | 100 | 100.0 | 0.0 | pct_zero |
| test | 100 | 100.0 | 0.0 | pct_zero |

For 2016 and 2017/test the stated figure is the payload's pct_zero. For 2014 and 2015 it is mean × 100, which for a 0/1 flag is exactly the complement of pct_zero. The column is a missingness flag, so pct_zero plus mean × 100 is 100 in every scope by construction; the two quantities are complements and never coincide. The agent used one label for two different quantities within a single sentence, and the two scopes it got right are not the ones where the quantities are close, because there are no such scopes.

M17b classified the 2015 figure, 94.95, as derived, under the adjudicated computation mean × 100. It matched the 2014 figure, 100, because 100.0 appears in the same payload as the pct_zero of the test and 2017 scopes. Every other token in the record matched. M17b raised no flag on any of it.

That is the behaviour M17b's specification warns of. The warning was written into [PREREGISTRATION.md](../../PREREGISTRATION.md) before any number was computed: "Matched is equally misleading when read as correct use: a number can appear in a payload and still be cited for the wrong column or in the wrong claim."

The claim the sentence supports, a cliff between vintages, is not evaluated here.

### 3. One figure could not be traced

Of the 83 numeric tokens in the evidence of the 14 records, drawn from runs that made 225 logged calls, one could not be traced to a payload number, a payload string or the system prompt: 0.0299, in run10-honest-nopop-30turns record 1, cited as the mean absolute SHAP of `all_util_was_missing`.

The payload at seq 9, `get_shap_ranking` with `top_n` 180, gives `all_util_was_missing` at rank 27 with `mean_abs_shap` 0.029952029. That value is 0.0300 at four decimal places. The agent wrote 0.0299, which is the value truncated rather than rounded. The discrepancy between the stated figure and the payload value is 0.000052029. The token remains unmatched.

### 4. Mechanics against judgement

Across the seven usable runs: no logged call was rejected, and no logged call repeated an earlier one. Thirteen of the 14 findings records name at least one tool, and every tool they name was called. In all three canary runs the planted column was examined in the call immediately after the one that first returned it.

Correctness is reported in [LAYER2_EVAL.md](LAYER2_EVAL.md), in its Results table and Findings section: the planted column was caught in every canary configuration, and every scored run on the honest cache scored 0.000 on precision, recall and f1 and produced at least one false positive.

## Limitations

**The analysis is contaminated by construction.** As recorded in the preregistration's scope and honesty statement, the metrics were defined by people who had already seen run-level results for every real run. No blind reviewer was available.

**One run per cell.** Every configuration cell holds one usable run, so no figure here can separate the effect of a configuration from run-to-run variance.

**M17a checks citation, not correctness.** A record is grounded when the tools it names were called. It says nothing about whether their output was read correctly or supports the claim.

**The prompt class cannot be verified from any run record.** No run record stores the prompt text; each stores only `system_prompt_chars`. Evidence for the prompt class comes from re-rendering the code at the commit that produced each run. Matching render length to `system_prompt_chars` is a check on the render, not a record of what was sent.

**The derived class rests on arithmetic the script does not verify.** It checks that each source value appears in the run's payloads, not that the recorded computation produces the token. The 2015 adjudication in run10 record 2 records mean × 100, which is 94.9553, against a token of 94.95. Every derived and multiply sourced classification therefore rests on hand arithmetic by an adjudicator who had already seen the results.

**Hand adjudication was not blind.** The derived, quoted and prompt classes were all assigned by hand, by someone who had already seen the results.

**Tie behaviour is representation-dependent.** Under A8, whether a figure written at an exact decimal tie matches its payload number depends on how the payload value is stored as a float. No token in these records was flagged as turning on a tie, but the detection itself uses a relative tolerance chosen in the implementation, not in the specification.

**A test assertion was weakened.** The suite's assertion that the default output file is not written was replaced, during the A9 implementation and before step 1G, by an assertion that the suite's own run does not create or modify it. The original assertion had begun failing once a real run legitimately wrote that file.

**The amendment record carries imprecisions.** Under A6's rule these are recorded here rather than as new amendments:
- A6 announces two smaller corrections to A5 and gives one.
- A7's heading says three definitions were corrected; it makes five corrections across two metrics, as A8 records.
- A8 describes 460 values as diverging from round-half-even. The search counted (payload, written) pairs across half-up, half-even and half-down rounding, compared against Python's `round`, which rounds the stored float rather than applying half-even to the decimal text.

## What this does not measure

Whether any finding was correct is outside this document and covered by [LAYER2_EVAL.md](LAYER2_EVAL.md). What was considered and rejected as not measurable on these records is listed in the Not definable section of [PREREGISTRATION.md](../../PREREGISTRATION.md).
