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

### A1. 2026-09-15. The validator is proven on the real artefact, and R7 failing the environment stops the phase

Written before step 2 begins, so these rules exist before the artefact they constrain. No Phase 5 artefact, prompt or request exists yet.

**What R7, N15, N16 and N17 run against.**
- **The rule:** every execution of R7, N15, N16 and N17 mounts `shap_values_long.parquet`, the full artefact built under Decision 1. It must be the same file, at the SHA-256 recorded in that step's amendment, that the generated tool will read. It is never a fixture, never a subset, and never a smaller file built for the checks.
- **How it is shown:** each execution's host-side hash of the mounted artefact is recorded before and after, and must equal the recorded SHA-256. This applies in process and in the sandbox.
- **Why:** if the validator is proven on anything smaller, it is proven under different conditions from the ones the generated tool faces. The 512 MiB memory limit in particular would go untested where it matters. A3 in `PREREGISTRATION_PHASE3.md` already records R5 at 55% of that limit on the smaller wide matrix.

**If R7 fails the environment.**
- **The rule:** if any sandbox execution of R7 ends in a refusal-class outcome, the checks stop there and the result is reported. The outcomes that count:
  - `memory_limit`;
  - `timeout`;
  - `crashed` caused by any of the other refusals in section 4 of `PREREGISTRATION_PHASE3.md`.
- **Crashes are not sorted while running.** Whether a crash was caused by a refusal is a judgement. So any `crashed` execution of R7 also stops the checks and is reported with its recorded error, and whether it was a refusal is decided afterwards, not while the checks run.
- **What is not done** without the decision being taken explicitly first:
  - no limit is raised;
  - the artefact is not shrunk or re-laid out;
  - R7 is not rewritten to fit.
- **What follows:** the generated tool does not run, and no code-generation request is made.
- **Why:** R7 is a correct tool written by hand. If it fails the environment, that is a result about the environment, not about R7. A paid request sent into a test that no correct tool can pass would produce a rejection that means nothing, and that is worse than not running it.

**How the wording changed.** This rule first named `memory_limit` only. It was widened to every refusal-class outcome before step 2 began, and before any artefact existed. Memory was named first because it was the case in mind, not because a timeout differs: a correct tool written by hand that runs out of time is equally a result about the environment.

**Context for the rule, not a threshold.** R5's peak upper bound has risen across three readings:

| Reading | R5 peak |
|---|---|
| Phase 3 | 272.7–282.7 MiB |
| First A4 check run | 266.4–286.2 MiB |
| Second A4 check run | 278.2–292.4 MiB, 57% of the limit |

- **Nothing has failed.** A4 reports peaks rather than comparing them.
- **R7 reads a much larger file:** 5,400,000 rows, against R5's 30,000 rows × 180 columns.
- **This is why the stop rule exists, not a limit.** It is not compared against anything, not investigated, and nothing is tuned on it.

**The order of steps is unchanged by this amendment.** The in-process mock checks enforce no time or memory limit, so this rule can only trigger in the sandbox.

### A2. 2026-09-15. The artefact, built and verified

Written after the artefact was built and verified, and before the code-generation prompt existed or any check had read the file. Under A1, this hash is the one R7, N15, N16, N17 and the generated tool must all read.

**The source.**
- `outputs/agent_cache/shap_values.parquet`, SHA-256 `d1d9465e85ad843d2c4537e55ecd0bb11566edc176848c9690aa0aa99a8e29b3`.
- 30,000 rows and 181 columns in 1 row group: `row_id` (int64) first, then 180 float32 feature columns.
- **Checked before the build, in a separate read-only pass:**
  - `row_id` is unique, and not sorted;
  - there are no nulls in any column;
  - the 180 feature columns hold no NaN and no negative zero.

**The build.** `scripts/build_phase5_artefact.py`, run once. It refuses to overwrite an existing file, and no earlier file existed.
- **Written by:** pyarrow 24.0.0, the version pinned in `PREREGISTRATION_PHASE3.md` A2 for the sandbox image. The file's own metadata reads `parquet-cpp-arrow version 24.0.0`.
- **Layout, as Decision 1 froze it:**
  - `row_id` int64, `feature` dictionary-encoded, `shap_value` float32;
  - one row group per feature;
  - features in the source's column order;
  - rows within each group in the source's row order.
- **Settings not frozen by Decision 1, left at pyarrow's defaults and read back from the file's metadata:**
  - Parquet format version 2.6;
  - Snappy compression on every column;
  - dictionary encoding requested for `feature` only. The encodings recorded are `RLE_DICTIONARY` for `feature`, and `PLAIN` and `RLE` for `row_id` and `shap_value`;
  - Arrow type read back for `feature`: `dictionary<values=string, indices=int32>`.
- **The file:** `outputs/layer3/phase5/shap_values_long.parquet`, 46,312,085 bytes.
- **SHA-256:** `07ff508bba87ec97ee4fe46f5577ce065076de865279dc6a6cce9e2bf864cc0d`.

**What the verification checked.** Every check read the written file back from disk, not the arrays used to build it. Each passed.
- **Row count and groups:** the metadata gives 5,400,000 rows in 180 row groups, and every row group holds exactly 30,000 rows.
- **Types and nulls:** read back, the columns are `row_id`, `feature` and `shap_value`, in that order, with `row_id` int64 and `shap_value` float32. No column holds a null.
- **Row groups:** each row group's decoded `feature` values are a single name, and group *i*'s name is the source's *i*-th feature column.
- **The round trip, done without using the row groups:**
  - **Pivot:** the file's rows were split by decoded `feature` value, keeping file order within each feature.
  - **Features:** in order of first appearance, they are the source's 180 feature columns, in the source's order.
  - **Row order:** for each of the 180 features, the sequence of `row_id` values is identical, element for element, to the source's `row_id` column. That is the same 30,000 rows in the same order.
  - **Values:** for each of the 180 features, the `shap_value` sequence is bit-identical as float32 to the source column. The raw 32-bit patterns were compared, not the values.
  - **The whole matrix:** the 180 rebuilt columns, stacked into a 30,000 × 180 float32 matrix, are bit-identical to the source's 180 feature columns stacked the same way.

**What the verification does not establish.**
- **Nothing about whether the values are correct.** It shows the long file reproduces `shap_values.parquet` exactly. Whether that file's SHAP values are right is outside it, as section 2 says.
- **That a rebuild gives the same hash.** The build was run once. Pyarrow writes its own version into the file, so a different version would give a different hash, and a rebuild would need its own amendment.
- **Bit comparison and plain equality give the same verdict here.** Bit comparison would treat 0.0 and -0.0 as different and NaN as equal to itself. The source holds neither, so on this file the two tests agree.

**Kept out of git.** The file is not committed. A line added to `.gitignore`, `outputs/layer3/phase5/*.parquet`, keeps it out, the same way `outputs/agent_cache/*.parquet` keeps out its source.

### A3. 2026-09-15. The code-generation prompt, recorded in full and by hash

Written after the prompt existed and before any request, count or check used it. Nothing has been sent.

**The request, as it will be made.**

| Part | Source | SHA-256 | Size |
|---|---|---|---|
| System prompt | `layer3/prompts/phase5_codegen_system.txt` | `e0d0ef68478b67da51bc1ed0be7af6324e9e2493241fc55039859e8fdac9e035` | 1,441 bytes, 19 lines |
| User message | the `text` field of item C4 in `outputs/layer3/phase4_runs/20260914T135142__REAL__phase4-run1/spec_requests.json` | `cc6d4fbe5da53e87abbaea367671aa3188b3bcd3af760ad50532123299f734f9` | 712 bytes |

**How the two parts are used.**
- **The system prompt** is the file's UTF-8 text exactly as it is, with nothing stripped or added. It ends with one newline.
- **The user message** is the only content of the one user message. It is the spec's raw reply text from the record, byte for byte, with nothing added, removed or resolved. It is the spec quoted in section 3.
- **No tools are passed.** The frozen rules in section 4 do not say whether tools are passed with the code-generation request. The decision to pass none was made here, at step 3, and not earlier. A code-generation request has no use for them.
- The other settings are those in the code-generation rules in section 4.

**The system prompt, in full.** The file is authoritative. The text between the fences below is its content.

```text
You write one Python tool from a specification.

The user message is a tool specification, as JSON. Write the tool it describes, as a single Python file.

How the tool is run:
- It is run as `python /tool/tool.py`, with no command-line arguments.
- It reads its arguments from /inputs/arguments.json. That file holds one JSON object with a value for each property in the specification's input_schema.
- Its data is one Parquet file, /inputs/shap_values_long.parquet, with three columns: row_id (int64), feature (string, dictionary-encoded) and shap_value (float32).
- Those two files are the only files under /inputs.
- It runs on Python 3.11.16 with numpy 2.4.6, pandas 3.0.3 and pyarrow 24.0.0, plus the standard library. Nothing else is installed, and nothing can be installed.
- It must finish within 30 seconds and use no more than 512 MiB of memory.

What the tool prints: exactly one JSON object on standard output, and then it exits with status 0. The object has these keys:
- "found": required, true or false.
- When "found" is true, "rows" is required: a list of objects, each with "row_id" (an integer, not a boolean) and "shap_value" (a finite number).
- When "found" is false, "rows" may be left out. If it is present, it must be an empty list.
- Other keys are allowed, both at the top level and in each row.

Reply with the contents of tool.py and nothing else: no explanation before or after it, and no Markdown code fences.
```

**What comes from the spec.** Everything in the user message:
- the tool's name and description;
- the `feature` and `top_n` parameters with their descriptions, including "ranked by SHAP value descending" and the clamp clause;
- the `found=false` clause;
- the data source's three column names.

The prompt restates none of it.

**What we supply, as interface specification and not as validation rules.** These are facts about our harness, not the spec. A correct tool cannot find or produce what it was never told about, and a failure on those grounds would say nothing about capability. With one attempt and no retry, it would also be a rejection that means nothing.
1. **Where the data is, and its format.** The mount path `/inputs/shap_values_long.parquet`, that it is Parquet, and its column types from Decision 1 and A2. The spec names the columns but not the file, its location, its format or its types. The prompt also says that this file and the arguments file are the only files under `/inputs`, which is a fact about the mount.
2. **Where the arguments are.** `/inputs/arguments.json`, a JSON object holding a value for each input property, per A4 in `PREREGISTRATION_PHASE3.md`, and that the tool is run with no command-line arguments (Decision 5).
3. **The output contract.** Decision 2, stated in full.
4. **The environment.** Python and library versions from `PREREGISTRATION_PHASE3.md` A2, and the 30 second and 512 MiB limits, as the code-generation rules require.
5. **The reply format.** Reply with the file's contents only, with no prose and no code fences. The reason is the same: the reply-parsing rule rejects prose and fences without repair, so a correct tool delivered inside a fence would be rejected for its wrapping, not its code.
   - **Why this is interface and not an exclusion:** telling the model what shape to reply in is interface. Telling it how the reply will be checked is an exclusion. The prompt does the first and not the second. It asks for the file's contents only, with no explanation and no fences. It says nothing about how the reply is parsed, how many times anything runs, or what is compared.
   - **What leaving it out would do:** a correct tool wrapped in a fence would be rejected for its wrapping. Under one attempt, that rejection says nothing about capability.

**What is not in the prompt.** Unchanged from the code-generation rules:
- the test values `all_util`, `top_n` = 10, `addr_state` and `row_id` as a feature argument, and any row_id or SHAP value;
- the signed-versus-absolute resolution (Decision 3);
- the tie rule (Decision 4);
- the number of runs per test;
- any statement of how the tool will be checked.

Also not in the prompt:
- **The artefact's layout from A2:** the row count, one row group per feature, and row order within groups.
  - **Why it is left out:** telling the model about the 180 row groups would hand it a reading strategy. The generated tool's memory behaviour on a 5,400,000-row file is part of what this step observes. The code-generation rules also name only the filename and the column schema.
- **The sandbox's refusals.** The prompt states the limits, as the rules require, but not what is refused.
  - **Why they are left out:** what the sandbox blocks is how the execution is policed, not something a correct tool needs to know. A tool for this spec has no reason to use the network, write a file or read outside `/inputs`, and listing the refusals would describe the test environment rather than the interface.

**The generated tool running out of memory is not the same as R7 running out of memory.**
- **The generated tool:** if it is killed for exceeding 512 MiB, that is a result about the code it wrote. It is not a defect in the environment, and it is not a reason to stop. It is recorded as `memory_limit`, the tool is rejected under the registry rule, and the phase ends with that decision.
- **R7:** A1's stop rule applies to R7 only. If R7, the correct tool we wrote by hand, fails the environment, that is a result about the environment, and the generated tool never runs.
- **These two cases are never to be read as the same thing.**

**How the exclusions were checked.** Both parts were searched as text, without regard to case.
- **The system prompt** gave no match for:
  - the test values: `all_util`, `addr_state`, `top_n`, `10`, `loan_amnt`, `example`;
  - words about ranking and ties: `signed`, `absolute`, `magnitude`, `abs(`, `tie`, `equal`, `order`, `descending`, `ascending`, `sort`, `largest`, `highest`, `clamp`, `found=false`;
  - words about checking: `check`, `test`, `valid`, `verif`, `correct`, `pass`, `score`, `expect`.
- **Terms that did match,** each for an interface reason:
  - `row_id` twice, as the column name and as the output key;
  - `run` three times, in "is run as" and "runs on";
  - `three` once, in "three columns".
- **Digits in the prompt:** the versions, the limits `30` and `512`, `0` in "status 0", and `32` and `64` in the type names.
- **The user message** gave no match for `all_util`, `addr_state`, `10`, `absolute` or `signed`.
  - `row_id` appears once, in the data source's column list.
  - `tie` appears once, inside the word "properties".
  - `test` appears twice, in "test rows".

**Changes.** Any change to either part after this amendment needs a new dated amendment recording the new hash before any request uses it.

### A4. 2026-09-15. Memory headroom found in step 4, and a prediction written before the request

**When this was written.** After step 4's checks and before the code-generation request was counted or sent.
- **Why the timing matters:** written after the result, the prediction below would read as an explanation built around it. Written now, it can only be right or wrong.
- **What is recorded here:** the observation, and one prediction. No rule changes.

**What step 4 observed in the sandbox.** Every figure is the container's cgroup `memory.peak`, the counter the 512 MiB limit is enforced against.
- **R7:** 440.0–464.1 MiB across V1, V3 and V4, which is 86–91% of the limit. It passed on every run.
- **N17:** up to 479.6 MiB, 94% of the limit.
- **Context, not a comparison or a threshold:** R5 peaked at 57% of the same limit on the smaller wide matrix, in the second A4 check run in `LAYER3_PHASE3.md`.

**What R7's figure means.** R7 is deliberately plain.
- It reads the whole artefact with pyarrow, filters on the feature name, and sorts.
- It uses only what the code-generation prompt tells the model: the arguments file, the artefact's name, its format and its three columns. It uses nothing about the layout.
- So its peak is the headroom a straightforward correct tool has under these conditions: about 48 MiB at best.
- **Part of the peak is page cache** from reading the 46 MB file. The limit counts it, so it counts here.

**The prediction.** A generated tool that loads the file through pandas, or makes one more copy of the data than R7 does, could plausibly be killed for memory.
- **If that happens,** it is a result about the code the model wrote, and it is recorded as the outcome: `memory_limit`, and the tool is rejected under the registry rule.
- **What it is not:**
  - not a defect;
  - not a reason to raise the limit;
  - not a reason to rewrite the prompt, the artefact or anything else;
  - not a reason for a second attempt.
- **A1's stop rule applies to R7 only,** and R7 passed. The distinction in A3 stands: the generated tool running out of memory is not the same as R7 running out of memory.

### A5. 2026-09-15. The counted projection, before the request

Written after the request was counted and before it was approved or sent. Section 5's rule is count, report, approve. Recording the projection before approval keeps it from being written next to the result. Phase 4 did the same in its A4.

**What was counted.**
- **The count:** 753 input tokens, from the free token-counting endpoint.
- **The request counted is the request that will be sent.** `scripts/count_phase5_request.py` counted the request as `layer3/phase5_codegen.py` builds it, and the send uses the same function.
- **Hash check:** that module refuses to build unless the system prompt and the spec reply text each hash to the values recorded in A3. So what is sent is what A3 records.
- **Nothing was spent.** The ledger stood at $2.178496 over 301 lines both before and after the count.

**The request's settings.**
- model `claude-sonnet-5`;
- 12,400 max tokens;
- adaptive thinking, the setting in `agent/llm.py`;
- the moving cache breakpoint, on the one user message;
- no tools.

**The projection.**

| | |
|---|---|
| Projected cost | $0.016506 to $0.051882 |
| Worst case under the ledger rule (all input at the cache-write rate, output at the full 12,400 max tokens) | $0.125883 |
| Ledger now | $2.178496 of $15.00 |
| Ledger after the request, at most | $2.304379 |

Rates are those in `agent/ledger.py`: $2.00 input, $2.50 cache write, $10.00 output per million tokens, read 2026-09-14.

**How input was priced.** At both the plain input rate, for the low end, and the cache-write rate, for the high end.
- **Why both:** 753 tokens may be below the minimum length the cache will store, and that minimum was not checked. Neither case was assumed.
- **What this does not claim:** it does not say the cache minimum doesn't apply. It says only that it was not checked.
- Input is under $0.002 either way.

**A finding about section 5's input guess.**
- **The figures:** the counted input is 753 tokens, against section 5's guess of 2,500 to 3,500.
- **How far off:** the guess was made before the prompt existed, and it was high by 3.3 to 4.6 times.
- **What it fed:** it was the basis of section 5's estimate of $0.02 to $0.06.

**Output.**
- **The guess:** section 5's guess stands, 1,500 to 5,000 output tokens including thinking.
- **Why it is only a guess:** output cannot be counted before a reply exists, and it is nearly all of the cost.
- **After the request:** the actual output tokens, from the response's usage and the ledger line, are recorded.
- **A figure outside 1,500 to 5,000** is a finding about the guess, not an overrun. The spend cap is enforced by the ledger check, not by this range.

### A6. 2026-09-15. HITL is descoped, and the approvals that do exist

Written after Phase 5's registry decision and after D16 and D17. No code, request or checkpoint exists for this amendment to describe.

**The decision.** A human-in-the-loop checkpoint, and override logging with it, are descoped. This is not a change of mind. It is what a survey of the repository found on 2026-09-15.
- **Nothing reads the registry.** No code opens `outputs/layer3/registry.jsonl`. Admission exposes nothing, so there is no downstream decision for a person to stand in front of.
- **Nothing is queued.** The one admission, `get_top_shap_rows`, has already been made, and D17 records that it is not revisited. No other spec has been through code generation.
- **An override log would be empty by design.**
  - The frozen rules forbid repair, retry, taking a label from an unparsed reply, and second attempts. So no automated verdict in this project is one a person is allowed to overturn, and no overridable event exists.
  - The spend ledger holds 0 refusal lines. A refusal raises an error and is never written down.
- **Building a checkpoint now would mean manufacturing a decision for it to gate.** That is the reason for descoping. It is not a deferral, and no date is attached to it.

**The human approval that does exist, under its own name.** A person approved each of these in conversation:
- the one paid code-generation request;
- each commit;
- the push.

These are process approvals, not a checkpoint in a running pipeline. No pipeline paused for them. The repository records them only indirectly: through amendments written before the step they preceded, such as A5, which was written before the request was approved, and through the commit history.

**What this means for the README.** The README's sentence "A human-in-the-loop checkpoint sits in front of admission" is not true of the system as built. D17 records that Phase 5 departed from it without saying so. This amendment records the decision not to close that departure now.

**What stays open.** Two decisions are not taken here, and nothing is proposed for either:
- whether the README is amended;
- whether a checkpoint is built later, when something real is there to gate.

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

**D15. 2026-09-15.** The first version of `scripts/send_phase5_request.py` reported a rejected reply as accepted.
- **What went wrong:** it decided "parses as Python" with `ast.parse` alone. `ast.parse` accepts an empty string, so an empty reply would have been reported as "parses: yes". Section 4 rejects an empty reply.
- **How it was found:** in mock mode, before the real request. The mock reply had no text block, so the reply was empty, and the script printed "parses as Python as returned: yes".
- **What was changed, before the real send:** the report was split into three lines:
  - whether `ast.parse` on the reply as returned succeeds;
  - whether the reply is empty;
  - the verdict under section 4, which requires both.

  A second mock run then reported an empty reply as "no" under section 4. Only after that was the real request sent.
- **It did not affect the real reply,** which is 646 bytes and non-empty.

This is recorded because the general problem is not this one check. A single yes-or-no that merges several conditions can hide a case the rule rejects, and the report would read as a pass. Where a rule has more than one condition, each condition is reported on its own, next to the verdict that combines them.

**D16. 2026-09-15.** The Layer 3 phase numbering changed, and nothing recorded the change.
- **The plan:** a plan agreed in chat, before this repository existed, had eight phases. Phase 5 was HITL policy and override logging, and phase 6 was judge, verifier and agreement. That plan is not written anywhere in the repository or its history. A search of every commit found no phase list, no numbered HITL phase and no mention of override logging. Its content is recorded here as the project owner states it, not as something the repository can show.
- **What was committed instead:** A2 in `PREREGISTRATION_PHASE4.md`, dated 2026-09-14, numbers phase 5 as code generated from the expected specs, with its scope "taken from the README roadmap". It numbers phase 6 as judges and a verifier, and phase 7 as end-to-end audit runs. Phase 5 was then built as code generation, narrowed in section 1 of this document.
- **What no amendment records:** that the numbering changed, or where HITL policy and override logging went. HITL has no phase number anywhere in the repository.
- **The nature of the divergence:** it is between a committed document and a plan that was never committed. Nothing in the repository contradicts itself. The repository simply never recorded that it departed from the plan.

This is recorded because a plan that lives only in conversation can be replaced without anyone noticing, and then the committed record reads as if it had always been the plan.

**D17. 2026-09-15.** Phase 5 departed from the README roadmap, and did not record that it had.
- **What the README says:** "A human-in-the-loop checkpoint sits in front of admission."
- **What Phase 5 did:** it admitted `get_top_shap_rows` to the registry. Section 4 states "Phase 5 has no human-in-the-loop checkpoint and exposes nothing". That sentence says what Phase 5 lacks. It does not say that this departs from the README's design, and no amendment or defect entry did so at the time.
- **Why Phase 4 had no such departure:** Phase 4 also had no checkpoint, but it admitted nothing. Its section 1 gives the reason: "There is nothing to admit."
- **The admitted entry stands.** It is not being revisited, and the registry entry is not amended. What is recorded here is only that the departure from the README went unrecorded when the admission was made.

This is recorded because a stated absence and a recorded departure are not the same thing. A reader of section 4 learns that no checkpoint existed, but not that the project's own roadmap said one would.
