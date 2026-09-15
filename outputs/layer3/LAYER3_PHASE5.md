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
