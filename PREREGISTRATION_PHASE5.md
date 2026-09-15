# Layer 3, Phase 5: one generated tool, from code to a registry decision

Written 2026-09-15, before any Phase 5 artefact, prompt, code or request existed. This file fixes the scope, what the phase will and will not establish, the spec used and where it came from, the validation rules, the registry decision rule and the cost position. Changes after that point go in dated amendments at the end, the same way as in `PREREGISTRATION_PHASE3.md` and `PREREGISTRATION_PHASE4.md`.

## 1. Scope, and why it narrowed

### What Phase 5 was going to be

`PREREGISTRATION_PHASE4.md` A2 costed Phase 5 as code generated from the 8 expected specs, run through the Phase 3 sandbox and validator, with retries. That scope came from the README roadmap, which describes a chain that detects a gap, generates a spec, executes the tool in a sandbox, validates it against a known answer, and admits what survives into a registry.

### What the records support

Phase 4 and 4b produced 21 specs, for 9 distinct tool ideas.
- **Known answers:** none of the 21 has a known answer for the question it was generated to answer.
- **New data:** 8 of the 9 tool ideas need new artefacts computed from `data/`. Two of those, the full ablation and the joint ablation, need the model retrained, up to about 1.7 hours at Layer 1's measured 38.7 seconds per retrain for the full set.
- **Source episodes:** only 8 specs come from episodes scored correct, all of them part b items. 10 come from part c episodes that were eligible but never adjudicated, 1 from the unscored pilot, and 2 from episodes scored incorrect (C7 in Phase 4 run 2 and in 4b run 2).

### The circularity

This is the reason for the narrowing, not an aside.

**A gap means no answer exists.** Any known answer built for a gap is built by the same process that builds the tool: the same data, the same choices, the same reading of the question. A validator checking the tool against it would be checking output against something derived from the same source, and agreement would show only that the two derivations agree.

Phase 3's known answers worked precisely because those questions could be answered from artefacts that already existed. That is, they were not gaps.

### What Phase 5 does

One thing only: take one generated spec, C4's `get_top_shap_rows`, through code generation, the sandbox, validation, and a registry decision, once. C4 is the only tool idea whose data can be derived from an existing artefact without touching `data/`.

**What actually runs.** This is not the full chain end to end.
- **Read from the record, not re-run:** detection and spec generation, from Phase 4 run 1.
- **Run live:** code generation, the sandbox runs, validation, and the registry decision.

**Why detection is not re-run.** C4's detection reply parsed in only 1 of the 4 scored runs: Phase 4 run 1. It was unparsed in Phase 4 run 2 and in both 4b runs. Re-running it would likely not parse, and would likely produce a different spec. That is itself a finding about the detector, recorded in `outputs/layer3/LAYER3_PHASE4.md`. It is not a reason to re-run until a reply parses.

**An earlier phrasing corrected.** The request that set this phase described running "the full chain end to end". That was wrong, and this section states what actually runs.

## 2. What Phase 5 will and will not establish

Recorded before any result exists.

### It establishes

- that code generation, the sandbox, validation and a registry decision run in sequence on a generated spec;
- whether a generated tool executes under Phase 3's six refusals and limits;
- whether its output matches the spec on the three test cases in section 4.

### It does not establish

- **That the tool's answer is correct.**
  - **Why:** the tool reads a long-format artefact built from `outputs/agent_cache/shap_values.parquet`, and V1's expected answer is recomputed from that same parquet. That is a self-consistency check, not independent validation.
  - **What agreement shows:** only that the tool reproduces an ordering of values already on disk. No artefact exists that answers C4's question independently of that file.
- **That detection or spec generation works end to end.** Both are read from the record (section 1).
- **The spec's clamp clause.** V2, which would test it, is dropped (section 4, D13).
- **Anything about other tools or specs.** One spec, one code-generation attempt.

### The test values are our choices, not derived from the spec

The spec does not name any feature or `top_n` to test. Each value below was chosen to exercise one clause of the spec as generated.

| Value | Chosen by | Clause it exercises |
|---|---|---|
| `feature = "all_util"`, `top_n = 10` (V1) | taken from C4's question ("Which test rows carry `all_util`'s largest SHAP attributions?"); 10 is an arbitrary small count | "List the test rows with the largest SHAP attribution for one feature, highest first", and `top_n`: "How many top rows to return, ranked by SHAP value descending" |
| `feature = "addr_state"`, `top_n = 10` (V3) | a column the dictionary documents but the model does not read, verified in Phase 4 step 1 | "a feature the model does not read returns found=false" |
| `feature = "row_id"`, `top_n = 10` (V4) | a column present in `shap_values.parquet` that is an identifier, not a feature | "a feature the model does not read returns found=false", for a name that exists in the source file |
| `top_n` above 30,000 (V2, dropped) | would have exercised the clamp | "Values above the available count are clamped". Untested, per D13. |

## 3. The spec used, and where it came from

**Source.** `outputs/layer3/phase4_runs/20260914T135142__REAL__phase4-run1/`, item C4.

**The detection episode.**
- C4's question: "Which test rows carry all_util's largest SHAP attributions?"
- Completed in 2 turns and 1 tool call, with detector prompt `db401deb…`.
- Label `not_answerable`, citing `get_feature_shap_detail(feature="all_util")`, field `min/max/percentiles`.
- Stated missing element: the tool gives only aggregate statistics and does not identify which rows carry the largest attributions.
- **Scored eligible in part c, and never adjudicated.** It was not scored correct.

**The spec request.** Spec prompt `6c3cca8f…`, 393 output tokens, parsed as a spec.

**The spec, as generated and parsed:**
- **name:** `get_top_shap_rows`
- **description:** "List the test rows with the largest SHAP attribution for one feature, highest first. Covers the same 30,000 sampled test rows and features used for get_shap_ranking and get_feature_shap_detail; a feature the model does not read returns found=false."
- **input_schema:**
  - `feature`: string, "Exact name of one of the model's features."
  - `top_n`: integer, "How many top rows to return, ranked by SHAP value descending. Values above the available count are clamped."
  - both required.
- **data_source:** `new precomputed artefact: row_id, feature, shap_value`

The code-generation request receives this spec as the raw reply text recorded in that run's `spec_requests.json`, unchanged.

## 4. Decisions, validation rules, and the registry decision

### Decision 1. The artefact is built as the spec names it

The spec names a new precomputed artefact in long format. It is built from `outputs/agent_cache/shap_values.parquet` and mounted as the tool's data source.
- **Derived, not new data:** it is derived from an existing artefact, not computed from `data/`. It reshapes values already on disk and adds none.
- **An earlier reading corrected:** the statement that C4 "needs no new artefact" came from the scope survey's reading that its data is derivable from `shap_values.parquet`. It did not come from the spec text, which names a new artefact. That reading was wrong.

**Layout.** These are our choices, not the spec's.
- A parquet file, `outputs/layer3/phase5/shap_values_long.parquet`, written with pyarrow.
- Columns: `row_id` (int64), `feature` (string, dictionary-encoded), `shap_value` (float32, copied exactly).
- 5,400,000 rows (30,000 rows × 180 features), in one row group per feature, 180 row groups.
- Features in `shap_values.parquet`'s column order, and rows within each group in that file's row order.

These choices affect how much memory a tool needs to read the file. A tool that loads all of it at once with pandas could plausibly pass 512 MiB, where R5 already peaked at 282 MiB on the smaller wide matrix. A tool killed for memory is the limit working (Phase 3 A3), not a defect.

**Verification before use.**
- Pivoting the long file back by `row_id` and `feature` must reproduce every value and the row order of `shap_values.parquet` exactly.
- The file must hold 5,400,000 rows in 180 row groups.
- Its SHA-256 and the pyarrow version that wrote it are recorded in a dated amendment before any code-generation request.
- The file is not committed: it is regenerable and large, like `shap_values.parquet`.

### Decision 2. The output contract is invented by us

A tool spec defines inputs only. The C4 spec names `found` and implies rows carrying a `row_id` and a SHAP value, but it defines no output shape. **The contract below is invented by us, and labelled as such.**

The tool prints exactly one JSON object:
- **`"found"`:** required, a boolean.
- **When `found` is true, `"rows"`:** required, a list of objects, each with `"row_id"` (an integer, not a boolean) and `"shap_value"` (a finite number).
- **When `found` is false:** `"rows"` may be absent, and if present must be an empty list.
- **Extra keys** are permitted at the top level and in each row.

**The rejected alternative:** letting the generated code define its own output, with a validator that maps whatever shape it chose onto rows. A validator that maps arbitrary output shapes is tuned to whatever the code produced, so it was rejected.

### Decision 3. Signed, descending

Rows are ranked by signed SHAP value, highest first. This follows the explicit `top_n` text ("ranked by SHAP value descending") over the description's "largest SHAP attribution", which is ambiguous.
- **The ambiguity recorded:** C4's question ("largest SHAP attributions") could mean largest in magnitude.
- **The consequence:** a tool that ranks by absolute value fails V1. That is the rule discriminating between two readings, not a defect in the rule.

### Decision 4. Ties and non-positive `top_n`

- **Ties.** SHAP values are float32, and equal values can occur. The spec does not say how to order ties. V1 therefore requires that the returned values are in non-increasing order and equal, as a multiset, the 10 largest values in the column. It does not fix the order of rows holding equal values, or which of several tied rows at the boundary are returned. This accepts every ordering consistent with the spec, and no ordering the spec rules out.
- **`top_n` of 0 or less.** The spec does not say what happens. No test uses such a value, because any expected result would be invented, not read from the spec.

### Decision 5. The Phase 3 contract gains an arguments file

**The limitation found.** Phase 3's tool contract runs `python /tool/tool.py` with inputs mounted under `/inputs`, and passes no arguments. K1 to K6 needed none, so the contract had none. It fell short at the first generated tool, which takes `feature` and `top_n`. This is a limitation of Phase 3, found by first use.

**The extension.** A generated tool reads its arguments from `/inputs/arguments.json`, a JSON object holding exactly the spec's input properties, mounted read-only with the other inputs. Nothing else about the contract changes: the refusals, the limits, the 1 MiB stdout cap and the outcome classes stay as frozen.

**Before any code uses it:**
- the extension is written as a dated amendment to `PREREGISTRATION_PHASE3.md`;
- it gets its own mock check: the arguments file arrives read-only and unchanged, a tool cannot write to it, and K1 to K6 and R1 to R6 behave exactly as before.

### Decision 6. What runs live

As section 1 states: detection and spec generation are read from Phase 4 run 1, and only code generation, the sandbox runs, validation and the registry decision run live.

### Code generation

- **One request.** One attempt, no retries. Retrying until a tool passes would be tuning on the observation, and a rejection after one attempt is a result.
- **Settings:** `claude-sonnet-5`, the thinking setting in `agent/llm.py`, the moving cache breakpoint, and 12,400 max tokens. The request goes through `agent.llm.call_llm`, so the token count, the cap check and the ledger record are the same code that served Phases 2 to 4.
- **The system prompt:**
  - it states the tool contract (Decision 5), the output contract (Decision 2), the artefact's filename and column schema (Decision 1), the image's Python and library versions (Phase 3 A2), and the 30 second and 512 MiB limits;
  - it is written after this document, and recorded with its SHA-256 in a dated amendment before the request.

**The output contract goes into the prompt, as an interface specification.** It is not a validation rule.
- **Why it has to be there:** the contract is ours, not the spec's. The spec defines inputs only, so a tool that is otherwise correct has no way to produce our shape unless it is told.
- **What leaving it out would do:** V1 would fail on shape rather than on capability. With one attempt and no retry, that rejection would mean nothing.
- **What it gives the code:** the shape of the one JSON object the tool prints (Decision 2). It says nothing about which values are right.

**What does not go into the prompt.** These are what V1, V3 and V4 discriminate on, so none of them appears in the prompt in any form:
- the test values: `all_util`, `top_n` = 10, `addr_state` and `row_id`, and any row_id or SHAP value;
- the signed-versus-absolute resolution (Decision 3). The spec's own wording reaches the code unchanged, and nothing is added to settle it;
- the tie rule (Decision 4);
- the number of runs per test;
- any statement of how the tool will be checked.
- **The request itself:** the user message is the spec's raw reply text from the record, unchanged.
- **Parsing the reply:** the reply's text must parse as Python with `ast.parse`, as returned. Anything else is rejected and not repaired, including prose before code, code fences, or an empty reply. A reply that does not parse ends the phase with the registry decision "rejected".

### The validation rules

Each test is one sandbox execution, with the generated tool mounted at `/tool/tool.py`, and `shap_values_long.parquet` and `arguments.json` under `/inputs`. Everything runs under Phase 3's refusals and limits, unchanged, on the image pinned in Phase 3 A2.

**Every test runs 3 times.** The outcome is classified exactly as in Phase 3 section 3, in order: `timeout`, `memory_limit`, `crashed`, `bad_output`, `wrong_answer`, `pass`. `bad_output` covers anything that is not one JSON object meeting Decision 2's contract, including stdout over 1 MiB.

**V1.** Arguments `{"feature": "all_util", "top_n": 10}`. A pass requires all of:
1. `found` is true;
2. `rows` has exactly 10 entries, and no `row_id` appears twice;
3. every `row_id` is a row in `shap_values.parquet`, and its returned `shap_value` equals that row's `all_util` value;
4. the returned values are in non-increasing order;
5. as a multiset, the returned values equal the 10 largest signed values of the `all_util` column.

Values are compared after conversion to float32, so a tool that prints the float32 value in either its short or its full float64 form matches, and any other value does not.

**V2. Dropped.** It would pass `top_n` above 30,000 and require all 30,000 rows. Under Decision 2's contract that output is about 1.35 MB, over Phase 3's 1 MiB stdout cap, so a correct tool would be scored `bad_output`. See D13.

**V3.** Arguments `{"feature": "addr_state", "top_n": 10}`. A pass requires `found` to be false, and `rows`, if present, to be empty.

**V4.** Arguments `{"feature": "row_id", "top_n": 10}`. A pass requires `found` to be false, and `rows`, if present, to be empty.

**Where the expected answers come from.** They are read from `shap_values.parquet` at validation time. Before any verdict, the validator confirms that the file still holds 30,000 rows, that `all_util` is one of its columns, that `addr_state` is not, and that `row_id` is present. If any of these fails, no verdict is given.

**The validator counts as working** only if all three of these pass on 3 of 3 executions, on mocks and in the sandbox, before the generated tool runs:
1. **A hand-written reference tool, R7,** passes V1, V3 and V4.
2. **Three hand-written broken tools** are each rejected as `wrong_answer` on the case listed:
   - **N15** ranks by absolute value, on V1;
   - **N16** ranks ascending, on V1;
   - **N17** returns `found=true` with rows for `row_id`, on V4.
3. **Host-side state is unchanged** after every execution, as in Phase 3.

### The registry decision

**The registry** is an append-only file, `outputs/layer3/registry.jsonl`, with one entry per decision. Each entry holds:
- the spec's name and its source record and item;
- the code-generation prompt's hash and the generated code's hash;
- the image ID and the artefact hash;
- each test's outcome on each run;
- the decision;
- the limitations recorded against the tool.

**Admitted, with limitations recorded.** A tool is admitted only if all of these hold:
1. the code-generation reply parsed as Python;
2. V1, V3 and V4 each passed on 3 of 3 executions;
3. no execution ended in a refusal outcome;
4. host-side state was unchanged after every execution.

An admitted tool's entry records these limitations against it, and admission never omits them:
- self-consistency only, not independently validated;
- the clamp clause untested (D13);
- ranked by signed value, where the question could mean absolute (Decision 3);
- generated from an episode that was eligible but never adjudicated, and that parsed in 1 of 4 scored runs.

**Admitted is not validated.** A tool passing its self-consistency check is admitted with those limitations. It is never recorded as validated.

**Rejected.** A tool is rejected on any other result, and the entry records the first reason:
- the ledger refused the code-generation request;
- the reply did not parse as Python;
- a test failed, with the test, the run and the outcome class.

There is no partial admission and no second attempt.

**What admission does not do.** It does not add the tool to the eight Layer 2 tools, does not change `agent/tools.py`, and does not make the tool reachable by any agent. Phase 5 has no human-in-the-loop checkpoint and exposes nothing.

## 5. Cost

**What spends.** One code-generation request to `claude-sonnet-5`. Building the artefact, the sandbox runs, validation, the mock checks and the registry write cost nothing, and so does token counting.

**Rough size.** This is an estimate, not a projection.
- The prompt will be the code-generation system prompt plus the spec, about 2,500 to 3,500 tokens. This is guessed, because the prompt does not exist yet.
- The output will be a short Python file plus thinking, about 1,500 to 5,000 tokens. This is guessed from Phase 4's spec requests, which ran 121 to 1,395 output tokens.
- **Estimate:** about $0.02 to $0.06.
- **The ledger's worst case for one request:** all input at the write rate plus 12,400 output tokens, about $0.13.

**The rule.** No request is made until the code-generation prompt has been written and recorded by hash, counted with the free endpoint, the projection reported, and the request approved.

**The position.** The Layer 3 ledger stands at $2.178496 of the $15.00 cap.

## Amendments

None yet.

## Defect register

Numbering continues from D11 in `PREREGISTRATION_PHASE4.md`.

**D12. 2026-09-15.** D10 in `PREREGISTRATION_PHASE4.md`, the entry that flagged Phase 5's scope risk, was itself incomplete.
- **What D10 named:** C2, C3, C5 and C7, as specs that would need new artefacts built from `data/`.
- **What it missed:**
  - B1 and C1, which need the model retrained, the full ablation at up to about 1.7 hours;
  - B5 and B6, which need `addr_state` as a raw column. It exists only in `train.parquet` and `test.parquet`, not in the feature matrices or any artefact a tool can read.
- **What it got wrong:** C4 needs no data from `data/`. Its data can be derived from `shap_values.parquet`, although the spec as generated names a new long-format artefact built from that file (section 4, Decision 1).

This is recorded because an entry written to prevent a scope decision being taken in the middle of building was accurate in direction and wrong in coverage. The audit came from the specs actually produced and the columns actually on disk, not from D10's reasoning.

**D13. 2026-09-15.** Phase 3's 1 MiB stdout cap was frozen when every known answer was small, and the first generated tool exceeds it.
- **The case:** `get_top_shap_rows`, with `top_n` above the available count, must return all 30,000 rows. That is about 1.35 MB under the frozen output contract, so a correct tool would be scored `bad_output`.
- **The consequence:** V2 is dropped, and the spec's clamp clause goes untested.
- **What was not done:** the cap was not raised, and the output contract was not reshaped to fit under it, because either would change a frozen limit to accommodate a test.

This is recorded because the constraint is general: any row-level tool admitted later will meet the same cap.

**D14. 2026-09-15.** D12's date was set without a source for it.
- **What happened:** when this document was drafted, D12 was dated 2026-09-15 to match D13, on the grounds that the V2 conflict was found that day. That is D13's discovery, not D12's. D12's findings come from the scope report, and its date should have been taken from there.
- **What the source shows:** the scope report was given at 00:19 IST on 2026-09-15 (18:49 UTC on 2026-09-14). It came in the same reply that pushed `161fefb`, whose addition to `LAYER3_PHASE4.md` is dated 2026-09-15. The report text carries no date of its own. The V2 conflict was raised eight minutes later, at 00:27 IST. The dates in this repo follow local time, as the commits do.
- **The result:** D12's date stays 2026-09-15, and it now rests on the scope report's own timestamp. A proposed correction back to 2026-09-14 was checked against the same record and not applied, because nothing in the record carries that date for the scope report.

This is recorded because it is the error the register exists to catch: a date copied from a different finding. The value happened to be right, and that does not make the provenance right.
