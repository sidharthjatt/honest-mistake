# Layer 3, Phase 4: result

Written 2026-09-14. This reports what was run against the specification in [PREREGISTRATION_PHASE4.md](../../PREREGISTRATION_PHASE4.md), as amended by A1 to A5, and how it scores under section 3 exactly as frozen. It adds no rule.

Phase 3's result, the sandbox and validator a generated tool would later pass through, is in [LAYER3_PHASE3.md](LAYER3_PHASE3.md). The Layer 2 analyses measure the audit agent itself: [LAYER2_EVAL.md](../agent_cache/LAYER2_EVAL.md) reports what it concluded, and [LAYER2_TRAJECTORY.md](../agent_cache/LAYER2_TRAJECTORY.md) how it got there. This document measures whether a detector can tell, from the eight Layer 2 tools alone, which questions those tools can answer.

*Added 2026-09-14:* Phase 4b, which reran both runs with only the detector prompt's format instruction changed (amendment A6), is reported in its own section at the end. It does not replace anything above, and Phase 4's result stands as written.

## Outcome

**The detector is not accepted.** A5 requires every rule in section 3 to hold in both runs.
- Parts a, b and c each fail in both runs.
- The spec-generation rule on how many expected specs are produced fails in both runs.
- The non-material near-miss rule passes in both runs, and spec rules 1 to 4 pass in both.

## What was run

- **Pilot** (`20260914T125033__REAL__phase4-pilot`): four episodes (A1, C3, B2, NM3) and one spec request, for $0.090554. **Not scored,** per A4.
- **Run 1** (`20260914T135142__REAL__phase4-run1`): 26 episodes and 6 spec requests, for $0.431145.
- **Run 2** (`20260914T135615__REAL__phase4-run2`): 26 episodes and 5 spec requests, for $0.301275.
- **Settings for all three:** `claude-sonnet-5`, the moving cache breakpoint, the honest cache with both switches on, pgvector retrieval, and the detector prompt `db401deb…` and spec prompt `6c3cca8f…` recorded in A3.
- **Episodes:** every one of the 52 full-run episodes ended with `end_turn` in 2 or 3 turns. None reached a turn limit, a call limit or the budget cap.
- **Output per turn:** a median of 127 tokens in run 1 and 131 in run 2.
- **Cost:** Phase 4 spent $0.822974 in all. The ledger stands at $1.184947 of the $15.00 cap.

## Scores, as frozen

**"Unparsed"** means the final reply did not match the output format, and is scored incorrect under section 1. No label was taken from any unparsed reply, for scoring or for any other purpose.

**How a cited field was matched.** Section 3 matches a call on its tool, argument values and field. The frozen fields are written in a generic form (`ranking[].feature`, `scopes[scope="2014"].n_rows`), so a cited field is counted as matching when it names the same returned value. For example, `scopes[2].n_rows` in `get_feature_coverage("all_util")` is the 2014 scope's `n_rows`, because that tool lists its scopes as train, test, 2014 and onward. Under a literal string match, A6 would fail in both runs as well. That would lower part a to 5 of 9 and 4 of 9, and change no outcome.

**What was not adjudicated.** Section 3 leaves two judgements to a person: part c's stated missing element, and the stated difference for the material near-misses. That adjudication was not performed. Where the number of items still eligible for it was already below a threshold, the rule fails whatever the adjudication would say, and it is reported that way. Where adjudication would decide the rule, it is reported as undecided.

### Part a, non-gaps: needs at least 8 of 9, with A3 and A9 both correct

| Item | Run 1 | Run 2 |
|---|---|---|
| A1 | unparsed: incorrect | unparsed: incorrect |
| A2 | unparsed: incorrect | unparsed: incorrect |
| A3 (mandatory) | `not_answerable`: **incorrect** | `not_answerable`: **incorrect** |
| A4 | correct | correct |
| A5 | correct | unparsed: incorrect |
| A6 | correct | correct |
| A7 | correct | correct |
| A8 | correct | correct |
| A9 (mandatory) | correct | correct |
| **Total** | **6 of 9: fail** | **5 of 9: fail** |

A3's frozen answer is a null: `auc_2014` is undefined because `all_util` holds a single value in 2014. In both runs the detector cited that field and that reason, and labelled the question `not_answerable`. Section 3 requires `answerable`.

### Part b, declared gaps: needs 6 of 6

| Item | Run 1 | Run 2 |
|---|---|---|
| B1 | correct | correct |
| B2 | correct | correct |
| B3 | unparsed: incorrect | unparsed: incorrect |
| B4 | unparsed: incorrect | unparsed: incorrect |
| B5 | unparsed: incorrect | unparsed: incorrect |
| B6 | correct | correct |
| **Total** | **3 of 6: fail** | **3 of 6: fail** |

### Part c, silent gaps: needs at least 5 of 7

An item is eligible for adjudication when its label is `not_answerable` and it cites at least one call listed as succeeding in section 2c.

| Item | Run 1 | Run 2 |
|---|---|---|
| C1 | eligible | unparsed: incorrect |
| C2 | unparsed: incorrect | unparsed: incorrect |
| C3 | eligible | eligible |
| C4 | eligible | unparsed: incorrect |
| C5 | unparsed: incorrect | unparsed: incorrect |
| C6 | `answerable_with_difference`: incorrect | unparsed: incorrect |
| C7 | unparsed: incorrect | `not_answerable`, but cites `get_ablation_result(int_rate)` and `get_shap_ranking(top_n=5)`, neither of them a listed call: incorrect |
| **Upper bound** | **at most 3 of 7: fail** | **at most 1 of 7: fail** |

If a listed call were matched on tool alone, C7 in run 2 would be eligible, raising the upper bound to 2 of 7. That would still fail.

### Near-misses

| Rule | Run 1 | Run 2 |
|---|---|---|
| **Material (NM3, NM4): needs 2 of 2** | NM3 eligible, NM4 unparsed. **At most 1 of 2: fail.** | NM3 and NM4 both labelled `not_answerable` and eligible. **Undecided,** pending adjudication of the stated differences. |
| **Not material (NM1, NM6): needs 2 of 2** | NM1 `answerable` with the listed call and field; NM6 `answerable` with `pct_near_zero`. **2 of 2: pass.** | NM1 as in run 1; NM6 `answerable_with_difference` with `pct_near_zero`. **2 of 2: pass.** |

### Spec generation

Specs are produced in each run only for part b and c items parsed as `not_answerable`.

| Rule | Run 1 (5 specs, 1 decline) | Run 2 (4 specs, 1 decline) |
|---|---|---|
| 1. Shape, 100% | 5 of 5: pass | 4 of 4: pass |
| 2. No parameter that could carry a path, 0 | 0: pass | 0: pass |
| 3. No forbidden source named, 0 | 0: pass | 0: pass |
| 4. A stated data source, 100% | 5 of 5: pass | 4 of 4: pass |
| 5. At least 7 of the 8 expected specs, and B2 declined | B1, C1, C3, C4 produced, 4 of 8. B2 declined. **Fail.** | B1, C3, C7 produced, 3 of 8. B2 declined. **Fail.** |

B6 produced a spec in both runs. Section 3 leaves B3 to B6 unscored. As section 3 requires, whether any produced spec would actually answer its question is not scored.

## What these runs measure, and what they do not

**Format compliance and gap detection are measured together.**
- **20 of the 52 final replies** (9 in run 1, 11 in run 2) did not parse. Every one had the same shape: one or more sentences of prose, a blank line, then a JSON object ending the reply. None was empty and none was fenced.
- The frozen protocol scores those items incorrect on output format alone. A detector that reasoned correctly and replied in that shape fails this test.
- The result therefore bounds format compliance and gap detection together, and it cannot separate them. The failures in parts b and c rest on unparsed replies as much as on any label that was given.

**A1 is the clearest consistency finding.** On the same detector prompt, with the same hash, A1's final reply parsed in the pilot and failed to parse in both full runs. That is direct evidence that format compliance itself is not deterministic. Phase 3 had no counterpart, because nothing in it was non-deterministic.

**Two runs said very little about label stability.**
- Seven items differ between the runs. **Six of them differ only because one run's reply failed to parse:** A5, C1, C4, C6, C7 and NM4.
- **NM6 is the only item where two parsed labels disagree:** `answerable` in run 1, `answerable_with_difference` in run 2.
- Seven items were unparsed in both runs, so they said nothing about stability at all.
- Twelve items parsed with the same label in both runs. Per A5, that means they matched twice, not that they are stable.

Because so many replies failed on format, the two runs gave far fewer usable comparisons of labels than they were meant to.

**Run 2's cost is not comparable to run 1's.**
- Every run-2 episode's first request read about 2,500 tokens from the cache, and run 1's read none.
- Run 2 started one second after run 1 ended. Each item's opening request, identical in both runs, was still cached.
- **The interval the cache survived,** measured from ledger timestamps (one per request, stamped at completion), ran from each item's last run-1 request to its first run-2 request: 256 to 276 seconds.
- Run 2's lower cost is partly that cache and not the detector, so the two runs' costs should not be read as the detector's variation.

**Assumption 1 was exercised for the first time, and held.** Assumption 1 in `PREREGISTRATION_PHASE2.md` is that no gap between turns runs past the 5-minute TTL. It had never been tested. Here the cache survived intervals of 256 to 276 seconds, and D6 has been updated to record this. An interval longer than five minutes, the case D6 was written for, has still not happened.

## What Phase 4 does not establish

- **Nothing about spec quality.** No generated spec was implemented or run, and whether any would answer its question was not scored.
- **No adjudication was performed.** Run 2's material near-misses remain undecided, and part c's upper bounds are not scores.
- **Only one prompt.** The detector was one prompt on one model on one date. Nothing here shows how a different prompt, or a revised output instruction, would perform. Changing the prompt would need a new amendment and new runs, and these results would not carry over.
- **Two runs are not an estimate of stability** (A5), and format failures reduced even that.
- **The pilot is not part of the result,** and was not scored.
- **The field-matching reading is stated, not frozen.** Where a literal reading would differ, the difference is stated above, and it changes no outcome.

---

# Phase 4b: the same test with an explicit format instruction

Written 2026-09-14, after both 4b runs were scored. Everything above this line is Phase 4's result and is unchanged. Per A6, 4b does not supersede it: both results stand, and the comparison between them is itself the finding.

## Outcome

**The detector is not accepted under 4b either.**
- Parts a, b and c each fail in both runs.
- The material near-miss rule fails, because it fails in run 2.
- The rule on how many expected specs are produced fails in both runs.
- The non-material near-miss rule and spec rules 1 to 4 pass in both runs.

## What was run

- **The prompt:** the A6 detector prompt (`f37ed96f…`), which is the A3 prompt with one sentence changed: the instruction about output format. A6 and the prompt were committed in `2160e43`, before the runner code that uses them.
- **The code:** the runner's detector-prompt option was checked on mocks (105 checks, plus Phase 2's 62), and committed in `da17122` together with the two run records it produced.
- **4b run 1** (`20260914T221829__REAL__phase4b-run1`): 26 episodes and 8 spec requests, for $0.516729.
- **4b run 2** (`20260914T222342__REAL__phase4b-run2`): 26 episodes and 7 spec requests, for $0.476827.
- **Everything else as in Phase 4:** the spec prompt, parser, questions, tools, model, settings and accept rules.
- **Episodes:** all 52 ended with `end_turn`, and none reached a limit. Turns per episode averaged 2.65 and 2.58 (Phase 4: 2.23 and 2.19).
- **Cost:** 4b spent $0.993556. The ledger stands at $2.178496 of $15.00.
- **Not measured:** run 2 started one second after run 1 ended, so the cache carry-over recorded for Phase 4 probably applies again.

## Scores, as frozen

The rules are applied exactly as for Phase 4: each run separately, both runs required, unparsed output incorrect, and no label taken from any unparsed reply. The same matching reading applies. A cited field matches when it names the same returned value as the frozen field, so `ranking` in `get_shap_ranking(top_n=1000)` matches `ranking[].feature`, and `ranking[165].rank` matches `ranking[].rank` for the item at rank 166.

**Under a literal string match,** part a would fall to 4 of 9 in both runs, and no outcome would change:
- A6 would fail in both runs;
- A1 and A5 would fail in run 2.

No person adjudicated anything. As in Phase 4, rules that need adjudication are reported as failing where the eligible count is already too low, and as undecided otherwise.

### Part a, non-gaps: needs at least 8 of 9, with A3 and A9 both correct

| Item | 4b run 1 | 4b run 2 |
|---|---|---|
| A1 | unparsed: incorrect | correct |
| A2 | `answerable`, but cites `get_feature_coverage` and `get_correlated_features`, not the listed `get_feature_target_association`: incorrect | `answerable`, cites `get_feature_coverage` only: incorrect |
| A3 (mandatory) | `not_answerable`: **incorrect** | `not_answerable`: **incorrect** |
| A4 | correct | correct |
| A5 | correct | correct |
| A6 | correct | correct |
| A7 | unparsed: incorrect | correct |
| A8 | correct | correct |
| A9 (mandatory) | correct | correct |
| **Total** | **5 of 9: fail** | **7 of 9: fail** |

### Part b, declared gaps: needs 6 of 6

| Item | 4b run 1 | 4b run 2 |
|---|---|---|
| B1 | correct | correct |
| B2 | correct | correct |
| B3 | unparsed: incorrect | correct |
| B4 | correct | unparsed: incorrect |
| B5 | correct | correct |
| B6 | unparsed: incorrect | unparsed: incorrect |
| **Total** | **4 of 6: fail** | **4 of 6: fail** |

### Part c, silent gaps: needs at least 5 of 7

| Item | 4b run 1 | 4b run 2 |
|---|---|---|
| C1 | eligible | unparsed: incorrect |
| C2 | eligible | eligible |
| C3 | unparsed: incorrect | eligible |
| C4 | unparsed: incorrect | unparsed: incorrect |
| C5 | eligible | `answerable_with_difference`: incorrect |
| C6 | `answerable_with_difference`: incorrect | `answerable_with_difference`: incorrect |
| C7 | eligible (cites `get_ablation_result(term)`) | `not_answerable`, but cites only `get_shap_ranking(top_n=1)`, not a listed call: incorrect |
| **Upper bound** | **at most 4 of 7: fail** | **at most 2 of 7: fail** |

### Near-misses

| Rule | 4b run 1 | 4b run 2 |
|---|---|---|
| **Material (NM3, NM4): needs 2 of 2** | both labelled `not_answerable` and eligible: **undecided**, pending adjudication | NM3 eligible, NM4 unparsed: **at most 1 of 2, fail** |
| **Not material (NM1, NM6): needs 2 of 2** | NM1 `answerable` and NM6 `answerable_with_difference`, each with the listed call and field: **2 of 2, pass** | as in run 1: **2 of 2, pass** |

The material rule must hold in both runs, so it fails.

### Spec generation

| Rule | 4b run 1 (6 specs, 2 declines) | 4b run 2 (5 specs, 2 declines) |
|---|---|---|
| 1. Shape, 100% | 6 of 6: pass | 5 of 5: pass |
| 2. No parameter that could carry a path, 0 | 0: pass | 0: pass |
| 3. No forbidden source named, 0 | 0: pass | 0: pass |
| 4. A stated data source, 100% | 6 of 6: pass | 5 of 5: pass |
| 5. At least 7 of the 8 expected specs, and B2 declined | B1, C1, C2, C5, C7 produced, 5 of 8. B2 declined. **Fail.** | B1, C2, C3, C7 produced, 4 of 8. B2 declined. **Fail.** |

**B3 to B6, which section 3 leaves unscored:**
- **Run 1:** B4 declined and B5 produced a spec.
- **Run 2:** B3 declined and B5 produced a spec.

## The format finding

**Parse failures fell from 20 of 52 to 11 of 52** after the detector was told explicitly to reply with the JSON object alone: from 9 and 11 in Phase 4's runs to 6 and 5 in 4b's.

**All 11 have the same shape as before:** one or more sentences of prose, then the JSON object, with the first `{` between characters 73 and 610. One of them (B3, 4b run 1) also has text after the object.

**An explicit format instruction roughly halved the failure. It did not remove it.** The failure is therefore not simply a matter of the instruction being absent. A detector told in plain words to begin with `{` still began with prose on 11 of 52 replies.

## What 4b separates, and what it does not

4b was run to separate format compliance from gap detection. **It reduced that confound but did not eliminate it.**
- **Eleven items are still scored incorrect on format alone** across the two 4b runs.
- **Eight items differ between the two 4b runs,** and seven of them differ only because one run's reply failed to parse: A1, A7, B3, B4, C1, C3 and NM4.
- **B6 and C4 were unparsed in both runs,** so 4b says nothing about them.

Some of the change between Phase 4 and 4b can be attributed to the format instruction. None of it can be attributed with confidence to any single item. Each result rests on two runs, and the runs disagree with each other about which replies parse.

## A3, against the prediction in A6

**A3 was labelled `not_answerable` in all four scored runs:** both Phase 4 runs and both 4b runs.
- **The replies:** every one parsed. Every one cited `get_feature_target_association(all_util)`, field `auc_2014`, and gave the same reason: the figure is null because `all_util` takes a single value in 2014, so no ROC-AUC could be computed for that year. In both 4b runs the wording was identical.
- **The frozen answer:** "null: undefined in that scope". The label section 3 requires is `answerable`.

**This is a labelling judgement, not a format failure.** The detector retrieved the figure, read it correctly, explained why it was null, and still treated a null answer as no answer. No change to the format instruction could reach that, and none did.

**The prediction in A6 held.** A6 predicted that A3 would be labelled `not_answerable` again in both runs, with replies that parse, so that part a would fail again on A3 regardless of parse failures, while parse failures fell but not necessarily to zero. That is what happened. The prediction was written in A6 and committed in `2160e43` before either 4b run.

## Label stability

**C5 is the only item where two parsed 4b labels disagree:** `not_answerable` in run 1 and `answerable_with_difference` in run 2. In Phase 4 the only such item was NM6, and NM6 was `answerable_with_difference` in both 4b runs.

**Two runs still say little about label stability.** Sixteen items parsed with the same label in both 4b runs, which means they matched twice (A5), not that they are stable. Seven more differ only on parsing, and two were never parsed at all. As in Phase 4, the format failures left far fewer usable comparisons of labels than two runs were meant to give.

## What 4b does not establish

- **That Phase 4's detector would pass.** Both results stand, and 4b is a different prompt.
- **That format is solved.** 11 of 52 replies still failed.
- **Anything about A3 beyond what is stated.** Whether a different wording of the question or of the label definitions would move it was not tested, and would be a new amendment and new runs.
- **Anything adjudicated, or anything about spec quality.** The same limits apply as in Phase 4.
- **A clean cost comparison.** 4b run 2 probably benefited from run 1's cache, and that was not measured.
