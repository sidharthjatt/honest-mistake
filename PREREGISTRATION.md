# Preregistration: trajectory metrics over the Layer 2 run records

Frozen on 2026-09-13, before any metric below was computed. Nothing in this file is a result. As corrected by A5: any change to a definition, scope rule or classification procedure is always written first as an amendment in the Amendments section at the end of this file, with its date and reason. The text above may then be edited, but only to reflect a recorded amendment, and only in the places that amendment requires. No change is made to the text above that does not appear in the Amendments section.

## Scope and honesty statement

This is a retrospective analysis, and it is contaminated by construction.

Both the author and the assistant that proposed these metrics had already seen run-level results for every real run before any metric was defined: turns, tool calls, token usage and cost, the columns flagged, and the scores. Those results are published in `outputs/agent_cache/LAYER2_EVAL.md` and were discussed at length in an earlier session in this repo. The assistant also saw per-tool call counts, which bear directly on at least two metrics below, tool mix (M5) and empty-result rate (M9). A metric set chosen after seeing outcomes can be shaped by them, whether or not anyone intends it.

No blind reviewer was available to check or trim this list. Saying the metrics were chosen blind would be false, so this file does not say it.

One fact limits the damage. The run records were enumerated field by field before this file was written, and every configuration cell holds at most one usable run. With no replication inside any cell, no comparison between configurations can separate a configuration effect from run-to-run variance. Every metric here is therefore descriptive. Nothing in the analysis claims that one configuration outperforms another, and a contaminated metric choice can do less harm to a descriptive report than to an inferential one.

The commitment to define metrics blind applies to Layer 3, whose runs do not yet exist. For Layer 3 the metric set is frozen before the first run is made, and nobody who defines or amends it sees any result first.

## Validity precondition

Before any metric is computed, each candidate run's `manifest.json` is checked against the following rule, as amended by A1. If the run's `config_id` carries a retrieval segment, meaning it contains `-retrieval-`, that segment must read `pgvector-bge-small-en-v1.5`, or, as amended by A4, `unused`. A `config_id` with no retrieval segment passes. A segment reading `unused` passes because it records that no dictionary search was made during the run, which is agent behaviour, not a degraded backend. A segment naming `keyword-fallback` or `mixed` fails. A run that fails is out of scope for every metric, whatever its results.

`mock-down` is stamped `retrieval-keyword-fallback` because it was the verification run made with the database container stopped. This rule excludes it. That is the rule doing its job, not an exception to it.

The rule admits the six v1.0 records (`firstlight`, `run1`, `run2`, `run3`, `run4-ablated`, `run5-canary`). Retrieval was stamped into `config_id` only from tool-layer version 2.0, and at 1.0 keyword search was the documented design rather than a fallback, so those records carry no retrieval segment. Three of them ended usable. The in-scope set therefore spans both tool surfaces, the five-tool keyword surface and the eight-tool pgvector surface, and any metric that cannot be compared across surfaces is read within a surface only.

This is a limitation of the amended rule. For the six v1.0 records the retrieval backend is not recorded in the run at all, so the rule cannot verify it from the record. It is known only from the code: pgvector retrieval was introduced in `97a339c`, after those records were written, so no version of the code that could have produced them had it.

## Scope rules

Scope is decided by manifest field, never by directory name or label. Each rule is applied to runs that have already passed the validity precondition.

- **All real runs:** `mode == "REAL"`.
- **Usable real runs:** `mode == "REAL"` and `is_usable == true`.
- **Usable real canary runs:** `mode == "REAL"`, `is_usable == true`, and canary true, with canary attributed as described in the next section.

Each metric family applies to exactly one scope.

| scope | metrics |
|---|---|
| all real runs | M1 termination, M14 input and cost |
| usable real runs | M3, M4, M5, M6, M8, M9, M10, M11, M16, M17a, M17b |
| usable real canary runs | M18 |

Termination and cost are reported for unusable runs because those runs are informative about exactly those things. Every trajectory metric is restricted to usable runs. A run stopped by a ceiling is a partial trajectory cut short by the harness, and including one would pull every shape metric toward that ceiling.

MOCK runs are never reported as results, in any table or figure. They replay fixed fixtures, so any metric computed on them measures the fixtures, not the model. Their one use in this analysis is as deterministic inputs for unit-testing the analysis code: a known trajectory with known structure against which each metric implementation is checked before it is run on real records.

## Canary attribution

The `canary` field is absent from five of the six v1.0 manifests: `firstlight`, `run1`, `run2`, `run3` and `run4-ablated`. It is present in `run5-canary` and in every v2.0 manifest.

The rule is as follows. Where `canary` is present, its value is used and the row is marked `canary_source: field`. Where it is absent, canary is derived from `config_id`: true if `config_id` ends with `-canary`, false otherwise, and the row is marked `canary_source: derived`. Derived rows are visibly marked in every output that reports canary status or depends on it, including every table, figure and log line.

This section's closing sentences, which said the rule applied to no in-scope run, were removed under A1, and the removal is recorded in A5.

## Metrics

Fourteen metrics, retained from the step 1A proposal. For each: the exact definition in terms of fields on disk, the question it answers, what would make it misleading, and whether it measures agent behaviour or harness configuration.

Terms used below:
- **Logged call:** an entry in `tool_call_log.json` `calls[]`. A batch refused at the call ceiling is never dispatched and never logged.
- **Surface:** the `tool_layer_version`.
- **Tools available on a surface:** the entries in `TOOL_SCHEMAS` at that version, five at 1.0 and eight at 2.0.

### M1 termination

**Definition.** The value of `manifest.termination`, always reported beside `limits.max_turns`, `limits.max_tool_calls` and `max_tokens_per_turn` for the same run.

**Question.** Did the model end the run itself, or did something else end it?

**Misleading when.** Read without the ceilings beside it. The ceiling decides the point at which a long trajectory is labelled a failure, so the same behaviour can end as `completed` under one ceiling and `turn_limit` under another.

**Measures.** Both. It is the agent's behaviour cut off at a threshold the harness sets.

### M3 raw length

**Definition.** `manifest.turns` and `manifest.tool_calls`.

**Question.** How long was the investigation?

**Misleading when.** Averaged across runs that ended differently. The scope rule limits M3 to usable runs for this reason, since a limit-terminated run's length is censored at its ceiling.

**Measures.** Agent behaviour, within usable runs.

### M4 calls per tool-bearing turn

**Definition.** From `messages.json`, for each message with `role == "assistant"` whose `content` contains at least one block with `type == "tool_use"`, the number of such blocks. Reported as the distribution over those messages and its mean. Assistant messages with no `tool_use` block are excluded.

**Question.** Does the agent issue calls in parallel batches or one at a time?

**Misleading when.** Zero-call turns are counted. The closing turn of every completed run carries no calls, and including it would pull the mean down by an amount that depends only on run length. The definition excludes such turns for that reason.

**Measures.** Agent behaviour.

### M5 tool mix

**Definition.** For each tool name, the number of logged calls with that `tool` value, and that number divided by all logged calls in the run.

**Question.** Where did the investigation's effort go?

**Misleading when.** Compared across surfaces. A tool that does not exist on a surface has a share of zero by construction, so M5 is reported and read within a single surface only and never pooled across `tool_layer_version`. A share also moves with total call count, so it is reported beside the raw count.

**Measures.** Agent behaviour, bounded by the harness, which fixes which tools exist.

### M6 tool coverage

**Definition.** As amended by A7, the number of distinct `tool` values among logged calls that are among the tools available on the run's surface, divided by the number of tools available on that surface. Calls to names outside that set are excluded from M6 and remain counted in M8.

**Question.** How many of the available instruments did the agent use at least once?

**Misleading when.** Compared across surfaces, since the denominators differ. It is also misleading when read as quality: using a tool once is not evidence it was used well.

**Measures.** Agent behaviour, bounded by the harness.

### M8 rejected-call rate

**Definition.** Logged calls with `ok == false`, divided by all logged calls. Reported with its breakdown by `outcome` among `unknown_tool`, `unexpected_argument`, `bad_arguments` and `failed`.

**Question.** How well does the agent adhere to the published tool schemas?

**Misleading when.** Treated as a rate at all when the counts are tiny. A rate of zero in every run carries no information about differences between runs, and is reported as a universal statement rather than a comparison.

**Measures.** Agent behaviour.

### M9 empty-result rate

**Definition.** Logged calls whose `outcome` is one of `not_found`, `not_precomputed`, `not_available` or `match_count=0`, divided by all logged calls.

**Question.** How often did the agent ask for something the tool surface could not answer?

**Misleading when.** Read as waste or error. Asking whether the model reads a given column is a legitimate probe, and a `not_found` can be the answer the agent was looking for. The data dictionary documents more columns than the feature matrix contains, so part of this rate is set by the harness. It is reported as "calls returning no data", never as "failed" or "wasted" calls.

**Measures.** Both.

### M10 repeat calls

**Definition.** The number of logged calls whose canonical form equals the canonical form of an earlier logged call in the same run, computed over all logged calls, including rejected ones.

The canonical form of a call is the pair of its `tool` and its canonical arguments, built as follows:
1. Start from the call's `arguments`.
2. Fill in schema defaults for any argument the call omitted. The defaults are those of the tool method's signature in `agent/tools.py`: `top_n = 20` for `get_shap_ranking`, identical at tool-layer versions 1.0 and 2.0, and `top_k = 5` for `get_correlated_features`. So `get_shap_ranking` with `{}` and `get_shap_ranking` with `{"top_n": 20}` are the same call.
3. Strip leading and trailing whitespace from every string value. Case is preserved.
4. Sort keys.

Arguments outside a tool's schema are kept as they were written, so a rejected call cannot collide with a valid one.

**Question.** How much of the trajectory repeats a request already made?

**Misleading when.** A repeat is read as redundancy. A repeat made after the context has grown may be a deliberate re-check, and nothing on disk distinguishes the two.

**Measures.** Agent behaviour.

### M11 feature breadth

**Definition.** The set of distinct values of `arguments.feature`, whitespace-stripped, across all logged calls that carry that argument. Each feature is classified as follows:
- **In matrix** if at least one call on it to `get_feature_shap_detail`, `get_feature_coverage` or `get_feature_target_association` has outcome `found`.
- **Out of matrix** if it has at least one `not_found` from one of those three tools and no `found` from any of them.
- **Unclassified** otherwise.

`lookup_feature` does not classify matrix membership, because its `found` means the column is documented in the dictionary, and the dictionary documents columns the model does not read. `get_correlated_features` does not classify it either, because its `not_available` is returned both for a column absent from the matrix and for a column that is constant on the test split. `get_ablation_result` does not classify it, because `not_precomputed` is returned for model features outside the precomputed set.

**Question.** How many columns did the agent examine, and how many of them lay outside the model's inputs?

**Misleading when.** Read as quality. Breadth is not thoroughness, and examining many columns is not evidence of examining the right ones.

**Measures.** Agent behaviour.

### M14 input and cost

**Definition.** `manifest.usage.input` and `manifest.usage.output`. Cost is `usage.input × input_rate + usage.output × output_rate`, using the first-party list rates for the model named in `manifest.model`, as recorded in the claude-api reference cached on 2026-06-24: $2.00 per million input tokens and $10.00 per million output tokens for `claude-sonnet-5`. Prompt caching was not enabled in any run. The rates are an input assumption, stated beside every cost figure.

As amended by A3, token counts are the primary reported quantity for M14, because they are recorded facts. Cost is a derived figure, reported only beside the rates used and the date those rates were taken, and never without them. The rates are not verifiable from anything on disk. Before any cost figure is published, the rate is verified outside this repo against one of two sources: the Anthropic Console's billing record for 25 and 29 August 2026, or Anthropic's first-party pricing page read at the date of reporting. Whichever source is used is named in the report with its date. If neither is available, cost figures are withheld and only token counts are reported.

**Question.** What did the run consume and cost?

**Misleading when.** Input is read as behaviour. The full history is resent on every turn, so input grows faster than linearly with turn count and is mostly a function of M3 and of payload sizes. Cost is also misleading when read as a current price, since the rates are fixed at the date above.

**Measures.** Mostly harness configuration.

### M16 answer shape

**Definition.** From `agent.eval_canary.parse_final_answer` applied to `final_answer.txt`:
- the number of parsed records;
- the count of `CONFIDENCE` values over `high`, `medium` and `low`;
- whether `explicit_no_findings` is set;
- the parser's `warnings`, reported both as a count and as text.

**Question.** What kind of answer did the agent commit to?

**Misleading when.** Read as quality. The number of findings and the confidence attached to them say nothing about whether the findings are correct.

**Measures.** Agent behaviour.

### M17a evidence-tool grounding

**Definition.** For each parsed record, the tool names mentioned in its `EVIDENCE` text are the names of tools available on the run's surface that appear there as whole words. A record is grounded if it names at least one tool and every tool it names appears among that run's logged `tool` values. A record that names no tool is ungrounded, and is reported with the sub-reason "no tool named". Reported per record, and as the number grounded out of the number of records in the run.

**Question.** Does the evidence the agent cites correspond to calls it actually made?

**Misleading when.** Read as correctness. The check confirms a named tool was called. It does not confirm the tool's output was read correctly or supports the claim. Evidence that paraphrases a tool's output without naming the tool is counted ungrounded even when the output supports it.

**Measures.** Agent behaviour.

### M17b numeric grounding

**Definition.** Each numeric token in a parsed record's `EVIDENCE` text is classified as matched, unmatched or derived.

A **numeric token** is a maximal match of an optional sign, digits with optional thousands separators, an optional decimal part and an optional trailing percent sign, not adjacent to a letter or underscore. As amended by A7, a leading sign is read as a sign only where it is not preceded by a digit, a decimal point or a closing bracket. As amended by A8, a hyphen preceded by a letter is also not read as a sign. Where a sign is not read as a sign, it is a separator, so a range written `0.614-0.624` yields `0.614` and `0.624`, and `top-6` yields `6`. As amended by A7, scientific notation in the form `1e-3` is not parsed, and any `EVIDENCE` text containing it is reported so it can be handled by hand. The adjacency rule keeps digits inside identifiers such as `auc_2014` from being read as numbers. Separators and the percent sign are removed, and the number of decimal places written, `d`, is recorded.

The **payload numbers** of a run are every numeric leaf, excluding booleans, of every `tool_result` payload in that run's `messages.json`, where each payload's `content` is parsed as JSON. As amended by A7, a string leaf counts as a payload number only if it matches the same numeric token form used for `EVIDENCE` text, so scope labels such as `"2014"` are included, and values such as `nan`, `inf`, underscore-separated digits and strings with surrounding whitespace are not.

1. **Matched:** as amended by A7, at least one payload number `x` in the same run satisfies `abs(x - v) < 0.5 * 10**(-d)`, where `v` is the token's value written to `d` decimal places. As amended by A8, what this rule provides is stated here. A token is matched when it lies strictly inside the half-interval around a payload number at the precision written. At an exact decimal tie the outcome depends on how the payload value is stored as a float, and the token is usually rejected. A rejected token joins the unmatched set, which is adjudicated by hand, so the error runs toward more manual review rather than toward a false match. A non-strict inequality was considered and rejected, because it would match both `0.12` and `0.13` against `0.125` and replace a conservative rejection with an ambiguity. Any figure whose classification turned on a tie is named in the report.
2. **Unmatched:** every token that is not matched.
3. **Derived:** a figure the agent computed itself, such as a ratio, a delta or a percentage converted from a fraction, which cannot appear verbatim in any payload.
4. **Quoted:** as amended by A9, the figure appears verbatim inside a payload string rather than as a numeric leaf, typically a data dictionary description or a tool's note field. The adjudicator records the payload string and the seq that returned it.
5. **Prompt:** as amended by A9, the figure appears in the system prompt. The adjudicator records the prompt text. The figure is not written in `agent/prompts.py`: the prompt reads the held-out ROC-AUC from `outputs/models/best_params_canary.json` for canary runs and `best_params.json` otherwise. The prompt text is not stored in any run record, only `system_prompt_chars`, so evidence for this class comes from re-rendering the code at the commit that produced the run, and for the v1.0 records that means the earliest committed code.
6. **Multiply sourced** (`multiply_sourced`): as amended by A9, more than one of derived, quoted and prompt applies and the record cannot say which the agent used. The adjudicator records every source that applies. No precedence rule is defined.

As amended by A9, derived, quoted, prompt and multiply sourced are assigned only by hand, and only to tokens first classified unmatched, under the same evidence requirement. A matched token is never reclassified. A token that cannot be traced to a payload number, a payload string or the prompt stays unmatched.

The flagged records across all in-scope runs are few enough to adjudicate every unmatched token by hand, and their exact count is reported with the results. That is the procedure. This sentence was reworded under A1, which widened the scope the original estimate assumed, and the edit is recorded in A5. Adjudication reintroduces human judgement, and the adjudicator is not blind to the results, so for every token moved to derived the adjudicator records the computation believed to have produced it and the payload values it was computed from. A token that cannot be traced to payload values stays unmatched.

As amended by A9, reported per record as six counts: matched, unmatched, derived, quoted, prompt and multiply sourced, with the adjudication notes attached and the source list attached to every multiply sourced token.

**Question.** Are the figures the agent cites present in what the tools returned, or computed from it?

**Misleading when.** Unmatched is read as fabricated. A figure can be unmatched because of rounding the agent chose, or because it was derived in a way the adjudicator did not recognise. Matched is equally misleading when read as correct use: a number can appear in a payload and still be cited for the wrong column or in the wrong claim.

**Measures.** Agent behaviour.

### M18 exposure-to-investigation latency

**Definition.** For a usable real canary run, the planted column is the column named in `CANARY` in `agent/answer_key.py`, read from `outputs/models/best_params_canary.json`. The k-th `tool_result` block in message order corresponds to logged call `seq` k, because calls are dispatched and logged in the order their `tool_use` blocks appear. Two values are reported:
- **Exposure seq:** the smallest `seq` whose `tool_result` payload contains the planted column's name as a whole word.
- **Investigation seq:** the smallest `seq` whose whitespace-stripped `arguments.feature` equals that name.

Both are reported, together with the investigation seq minus the exposure seq. If either never occurs, it is reported as absent rather than given a value.

The mapping between `tool_result` blocks and logged calls is asserted per run before M18 is computed, as added by A2. The number of `tool_result` blocks in the run's `messages.json` must equal the number of logged calls. At each position k, the `name` of the `tool_use` block whose `id` matches the k-th `tool_result` block's `tool_use_id` must equal the `tool` of logged call `seq` k. A run that fails the assertion is reported as failing it, and its M18 values are withheld, not estimated.

**Question.** How long after the planted column first appeared in a tool result did the agent examine it directly?

**Misleading when.** The gap is read as attention or hesitation. A name can appear in a long payload, such as a ranking of twenty features, without being noticed at that step. The gap measures ordering, not what the agent registered.

**Measures.** Agent behaviour.

## Dropped metrics

Five metrics from the step 1A proposal are not computed. They are recorded here rather than deleted so that the set of candidates considered stays visible.

**M2 budget utilisation** (turns and calls as fractions of their ceilings). Dropped because it mostly reflects the harness. The ceilings are stated to the agent in the system prompt, so the agent may pace itself to them. `ceilings_stated_in_prompt` is also absent from three manifests, so that condition cannot be confirmed for every run. M1 read beside its ceilings, together with M3, carries the behavioural content without implying the ratio is a behaviour.

**M7 opening sequence** (the first three tools called, and the first seq for each tool). Dropped because each cell holds a single run. A three-tool opening per run is an anecdote, and giving it a metric name would present it as more than that. If the openings are discussed at all, it is by reading the traces.

**M12 visible reasoning volume** (characters of thinking and text blocks per assistant message). Dropped because thinking is returned with summarized display, so its length measures a summary of the reasoning, not the reasoning. Whether the thinking text is non-empty in every record was deliberately not checked at enumeration, because it is a value rather than a key. The metric is also too easily read as reasoning effort.

**M13 output per turn** (`usage.output / turns`). Dropped because usage is recorded only cumulatively, so the per-turn figure is a mean that hides the distribution it purports to describe. It also includes thinking tokens and adds nothing M14 does not already report.

**M15 wall_seconds.** Dropped because elapsed time is dominated by network latency, API response time and embedding model load. It measures the harness and its environment, not the agent.

## Not definable

These were considered and rejected because they cannot be measured on this repo. Constructing any of them now would mean inventing a standard after seeing the runs it would be applied to.

**Per-step tool-selection accuracy.** There is no labelled correct tool for any step. The task is open-ended and has no unique correct sequence of calls. The answer key labels columns, not steps. Writing step labels now, with every trajectory already seen, would record the labeller's judgement rather than measure the agent. What is definable instead is recorded above: tool mix and coverage (M5, M6), schema-level validity (M8), whether cited evidence corresponds to calls and payloads (M17a, M17b), and exposure-to-investigation latency on the planted column (M18). M18 uses the answer key, which was written before the agent existed.

**"Wasted" or "efficient" calls.** Both require a notion of which calls were necessary, and none exists. M9 and M10 describe calls that returned no data and calls that repeated an earlier request, without calling either wasteful.

**Reasoning effort or reasoning quality.** Thinking is summarized, so its length is not effort. Reasons are deliberately ungraded by `eval_canary`, and no grading standard exists.

**Anything per turn from tokens or latency.** Usage is recorded only as run totals. There are no per-turn timestamps. The retrieval backend is recorded per run, not per call.

**Recall as a capability score.** Recall on these records has a structural ceiling. Of the 39 columns in the scoring set, one is present in the canary feature matrix and none in the honest one, as documented in `outputs/agent_cache/LAYER2_EVAL.md`. A recall figure therefore reports whether the planted column was found and nothing more, and presenting it as a capability score would misrepresent it.

## Defect register

### D1. 2026-09-13. MOCK fixture tool calls do not match the structure of real ones

Real `tool_use` content blocks in `messages.json` carry a `caller` key. The `tool_use` blocks built by the mock fixtures in `agent/mock_replies.py` do not. Enumeration of all seventeen run directories found the five-key form (`caller`, `id`, `input`, `name`, `type`) in every real record and in no mock record, and the four-key form (`id`, `input`, `name`, `type`) in every mock record and in no real one.

The mock path exists to stand in structurally for the real path, so that the loop can be exercised without an API call. On this field it does not. Nothing is known to be broken by it: the loop reads only `id`, `name` and `input` from `tool_use` blocks, and scoring reads the call log rather than the message history.

It is recorded because a structural divergence between the path that is tested and the path that runs in production is the class of defect that surfaces late. The first code to read `caller` will pass its tests on mock records and meet the key only on real ones.

### D2. 2026-09-13. Early manifests lack fields added after they were written

The `canary`, `cache_dir`, `artefact_variant` and `n_features_stated_in_prompt` keys are absent from five v1.0 manifests: `firstlight`, `run1`, `run2`, `run3` and `run4-ablated`. The `ceilings_stated_in_prompt` key is absent from three: `firstlight`, `run1` and `run2`. The fields were added to the runner after those runs were written, and the records were never rewritten.

The keys are absent, not null. No key in any manifest holds null. Code that reads a missing field with a default in place of an absent value will silently treat the absence as a real value.

This register entry is why the canary attribution rule above exists. The absence of `cache_dir` and `artefact_variant` from the same five records is why neither can stand in for `canary`.

## Amendments

### A1. 2026-09-13. Validity precondition narrowed

**Original rule.** A run is in scope only if its `config_id` contains `retrieval-pgvector-bge-small-en-v1.5`.

**Why it was wrong.** The precondition exists to exclude runs where retrieval degraded silently, since `_warm_retrieval()` falls back to substring matching without stopping the run. The v1.0 records did not degrade. Retrieval was stamped into `config_id` only at tool-layer version 2.0, and at 1.0 keyword search was the documented design, not a fallback. The original rule therefore excluded six records for lacking a field that did not exist when they were written, which is not what it was meant to test.

**Amended rule.** If a run's `config_id` carries a retrieval segment, that segment must name pgvector. A `config_id` with no retrieval segment passes.

**Consequence.** `mock-down` remains excluded, stamped `retrieval-keyword-fallback`. The six v1.0 records are admitted, of which `run3`, `run4-ablated` and `run5-canary` are usable. The canary attribution rule now has subjects.

**Honesty note.** This amendment was made before any metric was computed, but not in ignorance. The consequence of the original rule, that it dropped three usable runs and left the canary attribution rule with no subject, was known when the amendment was decided, and the results of those three runs were already known from `LAYER2_EVAL.md`. It is recorded here rather than made by editing the original text.

**Residual limitation.** For the six v1.0 records the retrieval backend is not recorded in the run at all, so it cannot be verified from the record. It is known from the code: pgvector retrieval was introduced in `97a339c`, after those records were written, so no version of the code that could have produced them had it. This limitation is stated in the Validity precondition section.

### A2. 2026-09-13. Two checks added to the computation step, before it runs

**M18 seq mapping.** The specification assumes the k-th `tool_result` block corresponds to logged call `seq` k. This was taken from dispatch order in the code and never checked against the records. The computation step asserts it per run: the count of `tool_result` blocks equals the count of logged calls, and the tool named at each position matches. A run failing the assertion is reported as such and its M18 value withheld, not estimated.

**M14 rate assumption.** The input and output rates are an assumption carried from an external reference. The computation step recomputes cost for the five runs whose cost is published in `LAYER2_EVAL.md` and compares. A disagreement means the rate assumption is wrong, and it is resolved and recorded before any cost figure is reported.

### A3. 2026-09-13. A2's cost cross-check withdrawn and replaced

**What A2 specified.** Recompute cost for the runs whose cost is published in `LAYER2_EVAL.md`, at the rates in M14, and compare.

**Why it was wrong.** Those published figures were themselves computed from the same token counts at the same rates. The comparison agrees by construction. It can catch an arithmetic or transcription error and nothing else, and it was written as though it could catch a wrong rate. A2 also said five runs have published costs. There are seven: five in the results table and two in the paragraph after it.

**Replacement.** The rate is not verifiable from anything on disk, and this file stops claiming it is. Two changes follow.

First, token counts become the primary reported quantity for M14. They are recorded facts. Cost is a derived figure, reported beside the rates and the date they were taken, and never without them.

Second, the rate is verified outside this repo before any cost figure is published, by one of: the Anthropic Console's billing record for 25 and 29 August 2026, or Anthropic's first-party pricing page read at the date of reporting. Whichever is used is named in the report with its date. If neither is available, the cost figures are withheld and only token counts are reported.

**Note recorded 2026-09-13.** Anthropic's pricing documentation states that Sonnet 5's $2 and $10 per million rates, announced as introductory pricing through 31 August 2026, are now the standard price, and that the increase to $3 and $15 scheduled for 1 September 2026 did not occur. This was read from a search result, not from the Console, so it does not by itself satisfy the verification above. Several third-party pricing pages state the opposite.

### A4. 2026-09-13. The validity precondition does not reject "unused"

A1's wording, that a retrieval segment must name pgvector, rejects any other value including `unused`. That is wrong for `unused`, which records that no dictionary search was made during the run. That is agent behaviour, not a degraded backend, and the precondition exists to catch degradation. A run stamped `unused` passes. A segment naming a fallback or a mixed backend still fails. No record currently carries `unused`, so no scope changes.

### A5. 2026-09-13. How this file is amended, corrected

The opening line said changes are not made by editing the text above. A1 and A2 were then reflected into the frozen text by direct edits, so that line was false as soon as it was applied. The actual rule, stated correctly here: an amendment is always written in this section first, with its date and reason. The frozen text above may then be edited, but only to reflect a recorded amendment, and only in the places that amendment requires. No change is made to the frozen text that does not appear here.

Two edits made under A1 and A2 carry no marker in the frozen text: the removal of the canary paragraph's closing sentences, and the rewording of M17b's record-count estimate. Both are named here so the record is complete.

### A6. 2026-09-13. A1's honesty note contained a claim A5 contradicts

A1's honesty note ends "It is recorded here rather than made by editing the original text." A1 was then reflected into the frozen text by direct edits, which is the same thing A5 identifies as false in the opening line. The sentence was wrong when it was written. A1's text is not edited, because under A5 amendment text is the record and is never changed in place. This entry is the correction.

Two smaller corrections to A5 while the subject is open. A5 says the two unmarked frozen-text edits were made under A1 and A2. Both were made under A1: widening the scope left the canary paragraph without a subject and made M17b's record-count estimate no longer fit. A2 required neither.

This is the last amendment about how this file is amended. Any further imprecision in the amendment mechanism is recorded in the report's limitations rather than as a new amendment, because the mechanism has now consumed six entries and produced no measurement.

### A7. 2026-09-13. Three definitions corrected after implementation exposed them

Found while testing on MOCK and synthetic records. No REAL record had been read when these were decided.

**M6 numerator.** The definition counted distinct tool values among logged calls, which admits names that do not exist on the surface, so coverage could exceed 1. A rejected unknown-tool probe is not coverage of an instrument. Corrected: the numerator counts distinct tool values that are among the tools available on the run's surface. Calls to names outside that set are excluded from M6 and remain counted in M8.

**M17b sign rule.** A numeric token's leading sign is read as a sign only where it is not preceded by a digit, a decimal point or a closing bracket. In a range written 0.614-0.624 the hyphen is a separator, and the second value is 0.624, not -0.624. Figures in that form occur in this project's own prose, so the original wording would have silently misread real values.

**M17b scientific notation is out of scope.** A token in the form 1e-3 is not parsed. Any `EVIDENCE` text containing one is reported so it can be handled by hand rather than mis-tokenised.

**M17b matching tolerance.** The original rule compared `round(x, d)` to the token's value, which leaves the rounding mode unspecified and makes the result depend on binary float representation. Corrected: a token with value v written to d decimal places matches a payload number x when `abs(x - v) < 0.5 * 10**(-d)`. This accepts any figure that is a correct rounding of x under any standard mode, and removes the mode from the specification entirely.

**Payload numbers, narrowed.** A string leaf counts as a payload number only if it matches the same numeric token form used for `EVIDENCE` text. Values that `float()` would accept but that form would not, including `nan`, `inf`, underscore-separated digits and surrounding whitespace, do not count.

**Frozen-text edits required.** M6's definition, and M17b's tokeniser, matching rule and payload-number definition. Each is marked "as amended by A7".

### A8. 2026-09-13. A7's matching-tolerance justification withdrawn; sign rule extended to letters

**Tolerance justification.** A7 stated that the tolerance rule "accepts any figure that is a correct rounding of x under any standard mode" and removes binary float representation from the specification. Both claims are false. The rule uses a strict inequality, so an exact decimal tie is rejected under every rounding mode, and whether a written figure is an exact tie depends on how the payload value is stored as a float. Testing found 460 values where the behaviour diverges from round-half-even; payload 0.125 written as either 0.12 or 0.13 is rejected, and payload 7.55 written as 7.6 is accepted.

The rule is not changed. Its justification is. What the rule actually provides: a token is matched when it lies strictly inside the half-interval around a payload number at the precision written. At exact decimal ties the outcome is representation-dependent and the token is usually rejected. That sends it to the unmatched set, which is adjudicated by hand, so the error direction is toward more manual review rather than toward a false match. A relaxation to a non-strict inequality was considered and rejected, because it would match both 0.12 and 0.13 against 0.125 and introduce an ambiguity in place of a conservative rejection.

Any figure whose classification turned on a tie is named in the report.

**Sign rule extended.** A7 listed a digit, a decimal point and a closing bracket as characters after which a hyphen is a separator rather than a sign. A letter was not listed, so top-6 produces a candidate token -6 that is then rejected for sitting adjacent to a letter, and the figure 6 is lost with no record. Corrected: a hyphen preceded by a letter is also a separator, so top-6 yields the token 6.

**Heading correction.** A7's heading reads "three definitions corrected"; it makes five corrections across two metrics. Recorded here rather than edited.

**Frozen-text edits.** M17b's matching rule, replacing A7's justification with this one and marking it "as amended by A8"; M17b's tokeniser sign rule, adding the letter case.

### A9. 2026-09-13. M17b gains hand-assigned classes for figures present in context but not as payload numbers

Adjudicating the twelve unmatched tokens showed the three-class scheme misdescribes most of them. Eleven of twelve were present in what the agent was given, but not as numeric payload leaves, so the automatic rule could not match them and "unmatched" reads as absent when they were not.

Classes added, assigned by hand only, only to tokens first classified unmatched, under the same evidence requirement as derived. A matched token is never reclassified.

**quoted:** the figure appears verbatim inside a payload string rather than as a numeric leaf, typically a data dictionary description or a tool's note field. The adjudicator records the payload string and the seq that returned it.

**prompt:** the figure appears in the system prompt. The adjudicator records the prompt text. Two limitations attach to this class. The figure is not written in `agent/prompts.py`; the prompt reads the held-out ROC-AUC from `outputs/models/best_params_canary.json` for canary runs and `best_params.json` otherwise. And the prompt text is not stored in any run record, only `system_prompt_chars`, so evidence for this class comes from re-rendering the code at the commit that produced the run. For the v1.0 records that means the earliest committed code, the same limitation A1 records for retrieval.

**multiply_sourced:** more than one of derived, quoted and prompt applies and the record cannot say which the agent used. The adjudicator records every source that applies. No precedence rule is defined, because choosing one would manufacture a determination the records do not support.

**Reporting.** M17b reports six counts per record: matched, unmatched, derived, quoted, prompt and multiply_sourced, with the source list attached to every multiply_sourced token.

**Consequence**, recorded because it is why these classes were added. The 0.8730 figure cited in every canary run's evidence has two possible sources and the records cannot distinguish them. `get_ablation_result` returns no baseline field, but it returns `roc_auc_without_feature` 0.7295752764 and `delta_roc_auc` -0.1434433444, whose difference is 0.8730186208, which is 0.8730 at four decimal places. The same figure is also stated verbatim in the system prompt. The token is therefore multiply_sourced. An earlier draft of this amendment asserted the figure could only have come from the prompt. That was wrong, and it was wrong because the subtraction was not checked before the claim was written.

**A related observation**, recorded here because it bears on how M17b is read. M17a marks these same records grounded, since they name a tool that was called. M17a and M17b are describing the same sentence and disagree about nothing: one asks whether the cited tool was used, the other whether the cited figure appears in what the tools returned. Neither alone is a check on the other.

**Frozen-text edits.** M17b's classification list and its reporting line. Each is marked "as amended by A9".
