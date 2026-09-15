# Layer 3, Phase 5: result

Written 2026-09-15. This reports what was run against the specification in [PREREGISTRATION_PHASE5.md](../../PREREGISTRATION_PHASE5.md) and what happened. It adds no rule. Amendments are cited, not restated.

Phase 5 takes one generated spec, C4's `get_top_shap_rows`, through code generation, the sandbox, validation and a registry decision. Each step is reported under its own heading. Steps 1 to 3 are recorded elsewhere:
- **Step 1**, the arguments file: amendment A4 in `PREREGISTRATION_PHASE3.md`, with its results in [LAYER3_PHASE3.md](LAYER3_PHASE3.md).
- **Step 2**, the artefact: amendment A2 in `PREREGISTRATION_PHASE5.md`.
- **Step 3**, the code-generation prompt: amendment A3 in `PREREGISTRATION_PHASE5.md`.

## Step 4: the validator against R7, N15, N16 and N17

Run on 2026-09-15 with `scripts/validate_phase5_step4.py`, once, with no API request. Nothing was retried or adjusted.

### What was run

- **The order, per section 4 and A1:**
  - in process first, then in the sandbox on the image pinned in `PREREGISTRATION_PHASE3.md` A2 (`sha256:801f6454…50f6`);
  - in each, R7 on V1, V3 and V4 before any broken tool;
  - every case 3 times.
- **The inputs:** every execution mounted the full artefact from A2 and the case's `arguments.json`. No fixture and no subset were used (A1).
- **Before any run:** the artefact on disk hashed `07ff508bba87ec97ee4fe46f5577ce065076de865279dc6a6cce9e2bf864cc0d`, equal to A2. The source, `shap_values.parquet`, hashed `d1d9465e85ad843d2c4537e55ecd0bb11566edc176848c9690aa0aa99a8e29b3`, equal to the hash recorded in A2.
- **The answer source:** on every execution, before any verdict, the four confirmations in section 4 passed. The source holds 30,000 rows, `all_util` is a column, `addr_state` is not, and `row_id` is present.
- **The stop rules** were live and did not trigger:
  - A1's rule on any `crashed`, `memory_limit` or `timeout` run of R7 in the sandbox;
  - the script's own stop on any R7 result other than `pass`.

### Results

| Tool | Case | Arguments | Expected | In process, 3 runs | Sandbox, 3 runs |
|---|---|---|---|---|---|
| R7 | V1 | `{"feature": "all_util", "top_n": 10}` | pass | pass | pass |
| R7 | V3 | `{"feature": "addr_state", "top_n": 10}` | pass | pass | pass |
| R7 | V4 | `{"feature": "row_id", "top_n": 10}` | pass | pass | pass |
| N15, ranks by absolute value | V1 | as V1 | wrong_answer | wrong_answer | wrong_answer |
| N16, ranks ascending | V1 | as V1 | wrong_answer | wrong_answer | wrong_answer |
| N17, takes a column name for a feature | V4 | as V4 | wrong_answer | wrong_answer | wrong_answer |

Every tool gave the same outcome on all three runs, in both runners.

**The reasons cited:**
- **N15 and N16:** "returned values are not in non-increasing order; returned values are not, as a multiset, the 10 largest signed all_util values".
- **N17:** "found is true for row_id, expected false". It returned rows whose `row_id` and `shap_value` were both 169297, the largest `row_id`, repeated.

**What R7 printed:**
- **V1:** `found` true and 10 rows, the first three being row 19735 at 0.1251123994588852, row 46997 at 0.1216329038143158, and row 70290 at 0.1190614253282547.
- **V3 and V4:** `{"found": false}`.

The accept rule in section 4 is met:
- R7 passed V1, V3 and V4 on 3 of 3 executions, on mocks and in the sandbox;
- N15, N16 and N17 were each rejected as `wrong_answer` on the case listed, on 3 of 3 executions, in both;
- host-side state was unchanged after every execution.

### Hashes, before and after every execution

On all 36 executions, the mounted copy of the artefact hashed `07ff508b…cc0d` both before and after the run, equal to A2. The full hash was compared, not a prefix. The arguments file's hash was also identical before and after on every execution. The script printed the first 12 characters of each:

| Case | `arguments.json` |
|---|---|
| V1 | `0b4756583b48…` |
| V3 | `978bd5b25231…` |
| V4 | `f1a2e5141f63…` |

### Host-side checks

- **In process:** the SHA-256 of `outputs/ledger/layer3_spend.jsonl` and the output of `git status --porcelain` were identical before and after every execution. No isolation applies in process, so these checks are the whole of the host-side check there.
- **In the sandbox:** the harness's host-state record was unchanged after every execution. That record covers every mounted input, the tool file, the ledger and `git status --porcelain`.

### Container configuration

On every sandbox execution:
- network mode `none`;
- a read-only root filesystem;
- `/inputs` and `/tool/tool.py` mounted read-only;
- memory and swap both 536,870,912 bytes (512 MiB);
- image `sha256:801f6454116549ae4369be7d1ed8e64c3b2143e255931c0c67bc312de67450f6`.

These are the values section 4 of `PREREGISTRATION_PHASE3.md` fixes.

### Time and memory in the sandbox

Peak memory is the container's cgroup `memory.peak`, which the 512 MiB limit is enforced against. It includes the interpreter that starts the tool and page cache from reading the 46 MB artefact.

| Tool | Case | Wall time | Peak memory | Share of 512 MiB |
|---|---|---|---|---|
| R7 | V1 | 0.367–0.563 s | 440.0–461.1 MiB | 86–90% |
| R7 | V3 | 0.362–0.375 s | 446.6–464.1 MiB | 87–91% |
| R7 | V4 | 0.352–0.375 s | 442.8–462.3 MiB | 86–90% |
| N15 | V1 | 0.355–0.364 s | 440.8–450.6 MiB | 86–88% |
| N16 | V1 | 0.360–0.381 s | 450.9–454.8 MiB | 88–89% |
| N17 | V4 | 0.645–0.656 s | 475.8–479.6 MiB | 93–94% |

- **Memory:** no execution was killed for memory. R7's headroom is the finding recorded before the code-generation request, in amendment A4.
- **Time:** no execution came near half of the 30 s limit.
- **In process:** wall times were 0.04–1.03 s. They are not evidence about the limits, because in process there is no container and no limit.

### Checks on the data behind N15 and N16

Run before N15 and N16 were written, in a read-only pass over `shap_values.parquet`, to confirm each could fail V1.
- **N15:** of the 10 `all_util` values largest in magnitude, 9 are negative. So they are not, as a multiset, the 10 largest signed values.
- **N16:** the 10 smallest signed values do not equal the 10 largest as a multiset.
- **Ties:** the 10th and 11th largest signed values differ (0.10786306 and 0.10772558), so V1's answer has no tie at the boundary. All 10 of the largest values are distinct.
- **Range:** `all_util` runs from -0.14693719 to 0.1251124.

### Limitations

- **N15 and N16 print the same first row.** Both begin with row 90298 at -0.14693719148635864. That value is the column's minimum, so it is both the smallest signed value (N16's first) and the largest in magnitude (N15's first). The two outputs are not the same set: N15's holds one positive value, because only 9 of its 10 are negative, and N16's holds the 10 smallest values. They also cite the same reason, because both breaches, the order and the multiset, apply to each. The output shown was cut at 200 characters, so beyond the first rows this rests on the data check, not on the printed output.
- **V1's answer was read only after the prompt was committed.** The data checks above, which looked at the values behind V1's answer, ran after the code-generation prompt had been written, hashed and committed (`9809b46`). Nothing seen in the answer could reach the prompt.
- **This is a self-consistency check, as section 2 states.** The artefact and V1's expected answer both come from `shap_values.parquet`. R7 passing shows the validator accepts a tool that reproduces an ordering of values already on disk, not that the ordering is correct.
- **The broken tools test anticipated failures only.** N15, N16 and N17 were written by the same process that wrote R7 and the validator. They show that three foreseen mistakes are caught, not that unforeseen ones would be.
- **The clamp clause is untested (D13).** No case passes a `top_n` above the available count, and none passes `top_n` of 0 or less (Decision 4).
- **R7 fits the memory limit narrowly.** Its highest peak was 464.1 MiB, about 48 MiB under the limit. See amendment A4.

## Step 5: the code-generation request

Sent on 2026-09-15 with `scripts/send_phase5_request.py`, once, after the counted projection was recorded in amendment A5 and approved. One attempt, with no retry.

### The request as sent

- **The parts:**
  - **System prompt:** `layer3/prompts/phase5_codegen_system.txt`, SHA-256 `e0d0ef68478b67da51bc1ed0be7af6324e9e2493241fc55039859e8fdac9e035`.
  - **User message:** the `text` field of item C4 in the Phase 4 run 1 record, SHA-256 `cc6d4fbe5da53e87abbaea367671aa3188b3bcd3af760ad50532123299f734f9`.
  - Both are as recorded in A3.
- **The hashes were enforced.** The parts were loaded by `layer3/phase5_codegen.py`, which refuses to build unless both hash to A3's values. The request was built, as it was counted, and was not refused.
- **Settings:** `claude-sonnet-5`, 12,400 max tokens, adaptive thinking with summarised display, the moving cache breakpoint on the one user message, and no tools.
- **The call path:** `agent.llm.call_llm`, so the ledger check before sending and the ledger line after it are the same code Phase 4 used. The ledger label is `phase5-codegen`.
- **What was written first:** the reply and the full response, before anything else was computed.
  - `outputs/layer3/phase5/codegen/reply.txt` is the reply text exactly as returned.
  - `outputs/layer3/phase5/codegen/response.json` is the complete result, thinking block included, with the settings and both hashes.

### What came back

- **The reply:** 646 bytes, SHA-256 `94199ea50aa1b9e32d8fc182570864ababe873ce317149124d52d1dc2791f27a`.
- **Stop reason:** `end_turn`.
- **The response content:** one thinking block and one text block. The reply is that single text block.

### Usage, cost and ledger

| | |
|---|---|
| Input tokens | 753, the same as the count in A5 |
| Output tokens | 323, thinking included. Usage does not report thinking separately. |
| Cache | none written (0) and none read (0) |
| Cost | $0.004736 |
| Ledger | $2.178496 over 301 lines before; $2.183232 over 302 lines after |

**On the cache, A5's wording stands.** No write and no read is consistent with the prompt being below the cache minimum, but it does not prove it. The minimum was never checked.

### The section 4 verdict

**The reply parses as Python, as returned, and it is not empty.** So under section 4 it is accepted for validation.
- `ast.parse` on the reply as returned succeeded.
- The reply is not empty.

**This is a verdict on the reply's form only.** Nothing is yet said about the code: it has not been run, read for correctness or validated.

### A finding about section 5's estimating

Section 5 guessed both the input and the output of this request before the prompt existed, and both guesses were wrong by large margins. They were wrong in the same direction: both were too high. So they did not offset each other, and the cost came in below the projection's low end.

| | Section 5's guess | Actual | How far off |
|---|---|---|---|
| Input tokens | 2,500–3,500 | 753, counted | high by 3.3–4.6 times |
| Output tokens, thinking included | 1,500–5,000 | 323 | the low end alone is 4.6 times the actual |
| Cost | A5's projected low end, $0.016506 | $0.004736 | the low end is 3.5 times the actual |

- **What the guesses rested on:** the input guess was made before the prompt existed. The output guess was drawn from Phase 4's spec requests, which ran 121 to 1,395 output tokens; this reply's 323 falls inside that range.
- **The two halves stand differently.** The input guess had no comparable source to draw on. The output guess did, and the actual output landed inside that source's range. Section 5's output range, 1,500 to 5,000, was set wholly above that source's 121 to 1,395.
- **What A5 did about input:** it replaced the input guess with a count before the request.
- **Output could not be replaced before a reply existed.**

The projection's high end, $0.051882, and the ledger's worst case, $0.125883, were never approached. This is a finding about the estimate, not about the spend, which stayed far inside the cap.

### A defect found before sending

The empty-reply case was found in mock mode, before the real request, and fixed then. It is recorded as D15 in the defect register of `PREREGISTRATION_PHASE5.md`.

## Step 6: the generated tool against V1, V3 and V4

Run on 2026-09-15 with `scripts/run_phase5_step6.py`, once. No API request was made. These are the raw results, written before any interpretation and before the registry decision.

### What ran

- **The code:** `outputs/layer3/phase5/codegen/reply.txt` itself, SHA-256 `94199ea50aa1b9e32d8fc182570864ababe873ce317149124d52d1dc2791f27a`, mounted read-only as `/tool/tool.py`.
  - The script confirmed its hash before any run.
  - The code executed is byte for byte the reply.
  - It was never run in process.
- **Where:** in the sandbox, on the image pinned in `PREREGISTRATION_PHASE3.md` A2, `sha256:801f6454116549ae4369be7d1ed8e64c3b2143e255931c0c67bc312de67450f6`, under Phase 3's refusals and limits.
- **The data:** the full artefact from A2. The file on disk hashed `07ff508b…cc0d`, equal to A2, before any run.
- **The runs:** each case 3 times, with that case's `arguments.json`.
- **Nothing stopped the runs.** All 9 went ahead regardless of outcome, as A4 requires: A1's stop rule is for R7 only. The only thing that would have halted them was the validator being unable to give a verdict, and that did not happen.
- **Records before printing:** each run's full record was appended to `outputs/layer3/phase5/validation/runs.jsonl` before anything about it was printed. That covers exit state, peak memory, full stdout and stderr, full input hashes, the host-state check, the container settings and the verdict. The script refuses to run again while that file exists.

### Results

| Case | Run | Outcome | Exit | Harness kill / OOMKilled / oom_kill events | Wall | Peak memory | stdout |
|---|---|---|---|---|---|---|---|
| V1 | 1 | pass | 0 | False / False / 0 | 0.450 s | 383.7 MiB | 568 bytes |
| V1 | 2 | pass | 0 | False / False / 0 | 0.334 s | 387.2 MiB | 568 bytes |
| V1 | 3 | pass | 0 | False / False / 0 | 0.331 s | 365.4 MiB | 568 bytes |
| V3 | 1 | pass | 0 | False / False / 0 | 0.335 s | 359.9 MiB | 17 bytes |
| V3 | 2 | pass | 0 | False / False / 0 | 0.328 s | 374.1 MiB | 17 bytes |
| V3 | 3 | pass | 0 | False / False / 0 | 0.329 s | 359.9 MiB | 17 bytes |
| V4 | 1 | pass | 0 | False / False / 0 | 0.327 s | 364.1 MiB | 17 bytes |
| V4 | 2 | pass | 0 | False / False / 0 | 0.335 s | 369.2 MiB | 17 bytes |
| V4 | 3 | pass | 0 | False / False / 0 | 0.349 s | 363.4 MiB | 17 bytes |

- **Reasons:** every run's recorded reason was "every item matches". Child return code was 0 on every run.
- **Output:**
  - **V1:** `found` true and a `rows` list, on every run. As printed, the first five row ids were 19735, 46997, 70290, 155258 and 19927, and the first value was 0.1251123994588852.
  - **V3 and V4:** `{"found": false}` followed by a newline, on every run.

### Hashes, before and after every run

| Input | Case | Before | After |
|---|---|---|---|
| `shap_values_long.parquet` | all nine runs | `07ff508bba87ec97ee4fe46f5577ce065076de865279dc6a6cce9e2bf864cc0d` | the same |
| `arguments.json` | V1 | `0b4756583b482335b5206690ca91b458d42cbedbbb92dc22ac8c2be9764d3383` | the same |
| `arguments.json` | V3 | `978bd5b252319aa981ceb312feba5791382354c2db33e232371a8af0b13b1724` | the same |
| `arguments.json` | V4 | `f1a2e5141f63879d857548d42d4f929d94cfe7664a2acee2724274c516ddbd61` | the same |

### Host state and container

- **Host state:** the harness's record was unchanged after every run. It covers every mounted input, the tool file (`reply.txt`), the spend ledger and `git status --porcelain`.
- **Container, on every run:**
  - network mode `none`;
  - a read-only root filesystem;
  - a 64 MiB tmpfs at `/tmp`;
  - `/inputs` and `/tool/tool.py` mounted read-only;
  - memory and swap both 536,870,912 bytes;
  - image `sha256:801f6454…50f6`.

### The memory finding

- **The prediction.** Amendment A4 was written after step 4 and before the request was sent, on R7's peaks of 86–91% of the 512 MiB limit. It predicted that a generated tool that "loads the file through pandas, or makes one more copy of the data than R7 does, could plausibly be killed for memory".
- **The observation.** The generated tool was not killed for memory on any run. It peaked at 359.9–387.2 MiB, 70–76% of the limit. That is below R7's 440.0–464.1 MiB on the same cases, image and artefact.
- **A4's prediction was wrong.** That is recorded as a result. A4 stays exactly as written, and nothing in it is removed or softened.
  - A4's wording is conditional on how a tool loads the file.
  - Whether this tool meets that condition is not examined here.
- **Lower peak memory is not a judgement about the code's quality.** It is peak memory and nothing else. Whether the tool's answers are right comes from V1, V3 and V4.
- **Why the peak is lower is not investigated here.** The code was not read for a cause, and none is given. Anything about how the code reads the file belongs with the registry decision, after these results.
