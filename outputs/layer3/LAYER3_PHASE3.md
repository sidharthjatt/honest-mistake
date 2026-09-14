# Layer 3, Phase 3: result

Written 2026-09-14. This reports what was run against the specification in [PREREGISTRATION_PHASE3.md](../../PREREGISTRATION_PHASE3.md) and what happened. It adds no rule. Where the specification was amended along the way (A1 to A3, D7 and D8), the amendment is cited, not restated.

The Layer 2 analyses measure the audit agent: [LAYER2_EVAL.md](../agent_cache/LAYER2_EVAL.md) reports what it concluded, and [LAYER2_TRAJECTORY.md](../agent_cache/LAYER2_TRAJECTORY.md) how it got there. This document measures something else: the machinery that will validate a tool before any agent is allowed to use it. No agent ran and no API call was made in Phase 3.

## What was run

- **Part A (in process, no container).** The validator ran against the reference tools R1 to R6 and against the broken tools N1 to N5, which attempt no escape. Three runs each. Commit `fa64fa3`.
- **Part B, first attempt (stock image).** R1 to R6 ran in the container on `python:3.11-slim` pinned by digest (A1). Three runs each. R2 and R5 failed, so no broken tool was run on that image.
- **Part B (derived image).** R1 to R6, then N6 to N14, ran in the container on the derived image pinned in A2. Three graded runs each. Commit `ea0439c`.
- **Diagnostic run.** N8 to N14 ran once more each, outside the graded runs, because the graded report printed only the last six lines of stderr and cut off the per-attempt lines. The attempt details quoted below for N9, N11, N12 and N14 come from that run. Its outcomes matched the graded runs.

N1 to N5 were run in process only, not in the container. Nothing in the specification requires them to run in the container, since they attempt no escape.

## The known-answer questions

Each question re-reads its answer from the named artefacts on every execution, and checks it against the value the specification froze. Every execution in Parts A and B produced a verdict, so every answer still reconciled with its artefacts as of 2026-09-14.

| Question | Tool gets | Answer source | Match rule | Reconciles |
|---|---|---|---|---|
| K1 train rows | vintage rows of `coverage_profile.csv` | `split_notes.txt`, `baseline_notes.txt`, train rows of `coverage_profile.csv` | exact, 891,742 | yes |
| K2 feature count | `shap_values.parquet` | `baseline_notes.txt` | exact, 180 | yes |
| K3 train mean | vintage `n_rows` and `mean` | train `mean` in `coverage_profile.csv` | absolute difference at most 1e-6, all 180 features | yes. The largest observed difference on disk is 8.77e-7, 88% of the tolerance. |
| K4 ablation delta | `roc_auc` column and `best_params.json` | `delta_roc_auc` in `ablation_cache.csv` | absolute difference at most 1e-12, all 20 features | yes |
| K5 SHAP ranks | `shap_values.parquet` | `rank` in `shap_global.csv` | positions 1 to 173 exact; positions 174 to 180 as a set | yes. The numeric version was dropped (D7). |
| K6 best trial | `optuna_trials.csv` | `best_params.json` | trial 21 and the integer parameters exact; `val_roc_auc` within 1e-12 absolute; float parameters within 1e-12 relative | yes. The float tolerance was set after observing pandas' parser. |

## Reference tools

Every run of every reference tool gave `pass` on the derived image, and each tool's outcome was identical across its three runs.

| Tool | In process, 3 runs | Stock image, 3 runs | Derived image, 3 runs | Wall time, derived image | Peak memory, derived image |
|---|---|---|---|---|---|
| R1 | pass | pass | pass | 0.088–0.092 s | 11.5–11.9 MiB |
| R2 | pass | crashed | pass | 0.147–0.178 s | 29.2–31.6 MiB |
| R3 | pass | pass | pass | 0.090–0.095 s | 11.4–11.9 MiB |
| R4 | pass | pass | pass | 0.088–0.094 s | 11.2–13.6 MiB |
| R5 | pass | crashed | pass | 0.320–0.356 s | 272.7–282.7 MiB |
| R6 | pass | pass | pass | 0.086–0.092 s | 11.2–11.7 MiB |

Wall time is the harness clock from `docker start` to exit. Peak memory is the container's cgroup `memory.peak`, which includes about 11 MiB for the interpreter that starts the tool, and any page cache the tool causes.

R5's peak is 55% of the 512 MiB limit. The limit was not changed (A3). No reference tool came near half of the 30 s limit.

In-process wall times are not reported as evidence about the limits, because they include no container start-up, and imports were cached after each tool's first run.

## Broken tools

Three graded runs each. Every run gave the predicted outcome, and each tool's outcome was identical across its three runs. For N6 to N14, stdout was empty on every run, so no escape attempt produced a well-formed answer. The host-side hashes of the mounted inputs, the tool file and the spend ledger, and the output of `git status --porcelain`, were unchanged after every run.

| Tool | Where | Predicted | Observed | Reason cited |
|---|---|---|---|---|
| N1 unweighted mean (K3) | in process | wrong_answer | wrong_answer | 177 of 180 features differ by more than 1e-6; largest miss 259.043 on `total_bal_ex_mort`. Checked separately: `loan_amnt` is off by 5.69, as the specification predicts. |
| N2 rounded baseline (K4) | in process | wrong_answer | wrong_answer | 20 of 20 features differ by more than 1e-12; each off by 2.47236e-5 |
| N3 signed SHAP (K5) | in process | wrong_answer | wrong_answer | 173 of positions 1–173 differ, the first at position 1 (`int_rate` for `term`); positions 174–180 hold 7 features outside the zero set |
| N4 second-best trial (K6) | in process | wrong_answer | wrong_answer | `best_trial` is 48, expected 21; `val_roc_auc` off by 1.26e-4; all nine parameters differ |
| N5 bare number (K2) | in process | bad_output | bad_output | stdout is a JSON number, not an object |
| N6 busy loop | container | timeout | timeout | killed at the time limit after 30.1 s |
| N7 ignores SIGTERM | container | timeout | timeout | killed at the time limit after 30.1 s |
| N8 write to input | container | crashed | crashed | exit 1, `OSError: [Errno 30] Read-only file system: '/inputs/coverage_profile.csv'` |
| N9 write to ledger | container | crashed | crashed | exit 1, `FileNotFoundError: [Errno 2]` on the relative path. In the diagnostic run, the absolute host path also gave `FileNotFoundError`. |
| N10 write to tool file | container | crashed | crashed | exit 1, `OSError: [Errno 30] Read-only file system: '/tool/tool.py'` |
| N11 network | container | crashed | crashed | exit 1, `socket.gaierror: [Errno -3]` resolving `example.com`. In the diagnostic run, connecting to `1.1.1.1:443` gave `OSError: [Errno 101] Network is unreachable`. |
| N12 database | container | crashed | crashed | exit 1, `socket.gaierror: [Errno -3]` for `host.docker.internal:5433`. In the diagnostic run, `172.17.0.1:5433` gave `OSError: [Errno 101]`. |
| N13 memory | container | memory_limit | memory_limit | killed for exceeding the memory limit |
| N14 read the answer | container | crashed | crashed | exit 1, `FileNotFoundError` for `shap_global.csv` by relative path. In the diagnostic run, the absolute path and both paths to `leakage_drop_log.txt` also gave `FileNotFoundError`. |

The accept rule in section 3 of the specification is met:
- every broken tool was rejected with its expected outcome on three of three runs;
- the host hashes were unchanged for N8 to N10;
- every reference tool passed on three of three runs.

## Outcome classes, and what exercised each

| Class | First exercised by | Raw observation |
|---|---|---|
| pass | R1–R6, Part A | exit 0, one JSON object of the right shape, every item within its match rule |
| wrong_answer | N1–N4, Part A | exit 0, right shape, at least one item outside its match rule |
| bad_output | N5, Part A | exit 0, stdout parsed as a JSON number, not an object |
| crashed | R2 and R5 on the stock image, not a fixture | Docker exit code 1, `OOMKilled` false, not killed by the harness, child return code 1. Docker elapsed 0.117–0.136 s, harness 0.149–0.171 s. The last stderr line was `ModuleNotFoundError: No module named 'pyarrow'` for R2 and `'numpy'` for R5. Peak 18.1–18.5 MiB. |
| timeout | N6 and N7 | `docker wait` was still blocking when the 30 s budget ran out. The harness sent `docker kill` (SIGKILL) and recorded that it had done so. Exit code 137, `OOMKilled` false. N6: harness 30.059–30.062 s, Docker 30.005–30.012 s. N7: harness 30.097–30.100 s, Docker 30.030–30.036 s. No peak memory was recorded, because the kill took down the process that records it. Neither tool wrote to stdout or stderr. |
| memory_limit | N13 | Exit code 137, `OOMKilled` true, one `oom_kill` event in the cgroup's `memory.events`. The child's return code was −9: the kernel killed the tool, and the process that starts it survived to record this. Peak 512.0 MiB. Harness 0.110–0.199 s, Docker 0.072–0.161 s. The tool's last stderr line was `allocated 448 MiB`. |

The harness decides between `timeout` and a normal exit from its own record of whether it sent the kill, not from the exit code. Exit code 137 appears for both `timeout` and `memory_limit`. They are told apart by that kill record and by Docker's `OOMKilled` flag.

## What Phase 3 does not establish

- **No tool was generated.** Nothing here shows that a generated tool can be validated. It shows that the machinery to validate one exists, passes six hand-written correct tools, and rejects every broken tool written for it.
- **The broken tools test anticipated failures only.** The fourteen broken tools were written by the same process that wrote the validator and the sandbox. They test the refusals that were anticipated, not the ones that were not.
- **The escape attempts cover the six refusals only.** Fork bombs, CPU share, timing side channels and attacks on Docker itself are out of scope, as section 4 of the specification says. Nothing was run against them.
- **The sandbox is reproducible on this machine only.** It is pinned by a local image ID, and a rebuild elsewhere gives a different image (D8).
- **The report-script fix was never run.** Every attempt line now prints in full, but no graded run has used it. Per-attempt evidence in this document comes from the diagnostic run.
- **K3's margin is narrow.** The tolerance is met with 88% of the allowance used, so a correct tool that adds any error of its own could fail K3.
