# Layer 3, Phase 3: sandbox and known-answer validator

Written 2026-09-14, before any sandbox or validator code existed. This file fixes the scope, the known-answer set, the validator's accept rule, what the sandbox must refuse, and the broken tools the validator will be tested against. Changes after that point go in dated amendments at the end, the same way as in `PREREGISTRATION.md` and `PREREGISTRATION_PHASE2.md`.

Every answer below was located in an artefact already on disk, and every tolerance was checked against those artefacts before this file was written. Where a check came after a tolerance was set, or a tolerance was set after a check, the text says so.

## 1. Scope

Phase 3 builds two things.

**A sandbox** that runs one arbitrary Python tool in isolation. It receives read-only inputs, it cannot reach anything else, and it runs under a fixed time and memory limit.

**A known-answer validator** that runs a tool in the sandbox against a question with an answer already on disk, and decides whether the tool passed.

**Phase 3 generates no tools.** No model writes, proposes or edits a tool in this phase, and no agent is run. Every tool that goes through the sandbox in Phase 3 is written by hand as an ordinary source file: the reference tools in section 3 and the broken tools in section 5. Tool generation is a later phase and is out of scope here.

Phase 3 makes no API calls. It does not touch the Layer 3 spend ledger.

### Tool contract

A tool is one Python file. The sandbox runs it as `python /tool/tool.py`. Its inputs are mounted read-only under `/inputs`. It prints exactly one JSON object to stdout and exits 0. Each question in section 2 names the files mounted and the shape of the object expected.

Mounts are set per question. A file that is an answer source for a question is never mounted for that question. Where a question needs part of an artefact, the harness writes a reduced copy with only the listed columns or rows, and mounts that copy.

## 2. The known-answer set

Six questions are kept. For each one: what the tool is given, where the answer comes from, and the match rule.

### K1. Training row count

- **Tool gets:** `coverage_profile.csv` reduced to the rows with scope `2014`, `2015` and `2016`, columns `feature`, `scope`, `n_rows`.
- **Expected output:** `{"train_rows": <int>}`.
- **Answer source:** `outputs/split_notes.txt` gives train (2014-2016) as 891,742 rows, and `outputs/baseline_notes.txt` gives `X_train (891742, 180)`. The train rows of `coverage_profile.csv`, not mounted, give 891,742 for every feature.
- **Match rule:** exact integer, 891,742.
- **Checked:** for all 180 features, the three vintage `n_rows` sum to the train `n_rows`: 223,102 + 375,545 + 293,095 = 891,742.

### K2. Feature count

- **Tool gets:** `outputs/agent_cache/shap_values.parquet`. The question states that `row_id` is an identifier, not a feature.
- **Expected output:** `{"n_features": <int>}`.
- **Answer source:** `outputs/baseline_notes.txt`, `X_test (169300, 180)`.
- **Match rule:** exact integer, 180.
- **Checked:** the parquet metadata shows 181 columns, `row_id` plus 180.

### K3. Train mean per feature, from the vintage means

- **Tool gets:** `coverage_profile.csv` reduced to the rows with scope `2014`, `2015` and `2016`, columns `feature`, `scope`, `n_rows`, `mean`.
- **Expected output:** `{"train_mean": {<feature>: <float>, ...}}` for all 180 features.
- **Answer source:** the `mean` column of the train rows of `outputs/agent_cache/coverage_profile.csv`, not mounted. Train is exactly the union of the three vintages, per `PRECOMPUTE_NOTES.md`, so the train mean is the `n_rows`-weighted mean of the vintage means.
- **Match rule:** absolute difference at most 1e-6 for every feature.
- **Why 1e-6:** it was derived before any check. `scripts/build_agent_cache_v2.py` writes every `mean` with `round(..., 6)`. Each vintage mean is therefore off by at most 5e-7, so their weighted average is too, and the stored train mean adds at most another 5e-7 of its own. The arithmetic is float64 on values under 10^6 and adds nothing near that size. A relative tolerance was not used, because several means sit close to zero. For `purpose_educational` the relative difference is 26% while the absolute difference is well inside 1e-6.
- **Checked, and the margin is narrow:** the largest absolute difference observed across the 180 features is 8.77e-7, on `num_rev_accts`. That is 88% of the allowance. This is not a comfortable margin, and it should not be read as one. It is as close as the rounding argument says it can be. A correct tool that adds any error of its own, such as float32 arithmetic, could fail this question for reasons that have nothing to do with the tool's logic.

### K4. Change in ROC-AUC for the twenty ablations

- **Tool gets:** `ablation_cache.csv` reduced to columns `feature` and `roc_auc`, and `outputs/models/best_params.json`.
- **Expected output:** `{"delta_roc_auc": {<feature>: <float>, ...}}` for the 20 features.
- **Answer source:** the `delta_roc_auc` column of `outputs/agent_cache/ablation_cache.csv`, not mounted.
- **Match rule:** absolute difference at most 1e-12 for every feature.
- **Why 1e-12:** both `roc_auc` and `test_roc_auc` are float64 values written with full precision. A correct parse followed by one subtraction can be off by no more than a few ulps, around 1e-16 at this size. 1e-12 leaves room for a decimal parser that is not round-trip exact (see K6), and it is still far below the 2.5e-5 error of the broken tool N2.
- **Checked:** `roc_auc - test_roc_auc` reproduces `delta_roc_auc` on all 20 rows, with a largest difference of 9.6e-17. `agent/precompute.py` recomputes the baseline from the model, not from `best_params.json`, and the two agree to that precision.

### K5. SHAP rank order

- **Tool gets:** `outputs/agent_cache/shap_values.parquet`.
- **Expected output:** `{"ranked": [<feature>, ...]}`, all 180 features, ordered by mean absolute SHAP value, largest first.
- **Answer source:** the `rank` column of `outputs/agent_cache/shap_global.csv`, not mounted.
- **Match rule:** positions 1 to 173 must match exactly, in order. Positions 174 to 180 must match as a set. Seven features have a mean absolute SHAP value of exactly zero, so their order in `shap_global.csv` came from a sort over ties and means nothing.
- **Checked:** ranks recomputed from the stored matrix match the stored ranks for all 173 nonzero features. The smallest relative gap between neighbouring nonzero values is 2.6e-4, between ranks 144 and 145. This check was run after the numeric version of this question had failed (D7). The rank question was kept because it passed, and that order of events is recorded here.
- **Dropped with it:** a numeric question on `mean_abs_shap` itself. See D7.

### K6. Best Optuna trial

- **Tool gets:** `outputs/optuna_trials.csv`.
- **Expected output:** `{"best_trial": <int>, "val_roc_auc": <float>, "params": {<name>: <number>, ...}}`, with the nine tuned parameters.
- **Answer source:** `outputs/models/best_params.json`, fields `best_trial`, `val_roc_auc` and `best_params`, not mounted.
- **Match rule:** `best_trial` must be exactly 21. `max_depth`, `n_estimators` and `min_child_weight` must match exactly as integers. `val_roc_auc` must be within 1e-12 absolute. The six float parameters must each be within 1e-12 relative.
- **Checked:** all 50 trials are `COMPLETE` and none has an empty value. Trial 21 is the only maximum at 0.7273238090007752, followed by trial 48 at 0.727198 and trial 45 at 0.727169. Its value and all nine parameters, written as strings in the CSV, are identical to `best_params.json`, and `float()` of each string equals the JSON value.
- **Why the float tolerance, and when it was set:** it was set after one observation. pandas' default CSV parser is not round-trip exact. Read with it, `learning_rate` comes back 19 ulps from its string value (6.6e-17) and `reg_alpha` one ulp away. An exact float rule would reject a tool whose only fault was the default parser. The tolerance of 1e-12 was chosen after seeing this. It cannot let a wrong answer through: `best_trial` must match exactly, and the nearest other trial's value differs by 1.3e-4.

### Questions considered and dropped

- **Test ROC-AUC, PR-AUC, Brier score, confusion matrices, default rates** (`tuning_notes.txt`, `baseline_notes.txt`, `split_notes.txt`). Reproducing any of them needs the model and `data/processed`. The repo rules forbid a tool from reaching data, and loading a `.joblib` model runs pickled code inside the tool.
- **Univariate AUCs, point-biserial correlations, correlation neighbours, coverage percentages** (`univariate_assoc.csv`, `correlation_topk.csv`, `coverage_profile.csv`). Each was computed from `data/processed`. No artefact a tool may read contains what is needed to reproduce them.
- **The canary column's identity.** Comparing the honest and canary `shap_global.csv` names one extra feature. That feature is the answer the Layer 2 agent is tested on. An answer set holding it would be one more place for it to leak from.
- **Mean absolute SHAP value per feature.** Not reproducible within a tolerance set before the check. See D7.

## 3. Validator accept rule

### When a tool passes

A tool passes a question only if all of the following hold on a single execution:

1. It exits with code 0 within 30 seconds of wall-clock time.
2. It was not killed for exceeding 512 MiB of memory.
3. Its stdout is at most 1 MiB and parses as exactly one JSON object with the shape the question specifies.
4. Every item the question requires matches under that question's rule.

There is no partial credit. One mismatched item out of 180 is a failure.

### What the validator records

Each execution ends in exactly one outcome. Where more than one applies, the first in this list is recorded:

| Outcome | Meaning |
|---|---|
| `timeout` | the harness killed the container at 30 seconds |
| `memory_limit` | the container was killed with `OOMKilled` true |
| `crashed` | non-zero exit code. The exception class from stderr is recorded beside it. |
| `bad_output` | exit 0, but stdout is empty, over 1 MiB, not one JSON object, or the wrong shape |
| `wrong_answer` | the output has the right shape and at least one item fails its match rule |
| `pass` | none of the above |

The outcome is decided from what the harness observes: exit code, `docker inspect` state, elapsed time and stdout. A tool's own claims about what it did are never used.

### The limits, and how they change

The limits are 30 seconds of wall-clock time, measured from container start to exit, and 512 MiB of memory with swap set to the same value, so no swap is available.

**Neither limit has been timed.** No reference tool exists yet, so no tool has been run under either one. They are frozen now as they stand. If a reference tool breaches one, the limit is not quietly raised. A dated amendment records the old limit, which tool breached it, and by how much, before any new value is used.

### Reference tools

The validator has one hand-written reference tool per question, R1 to R6, each a correct solution to K1 to K6. They are ordinary source files, written and read by a person, not produced by any model loop. They exist so that a validator that rejects everything cannot count as working.

### When the validator counts as working

The validator is **not** considered working until all of the following hold:

1. Every broken tool in section 5 is rejected with its expected outcome, on 3 of 3 executions.
2. For the write fixtures N8 to N10, the host-side hashes in section 4 are unchanged after every execution.
3. Every reference tool R1 to R6 passes, on 3 of 3 executions.

Any other result means it is not working. A broken tool is never edited to make the validator pass. If a broken tool turns out to be invalid, for example a wrong-answer fixture whose output happens to be correct, it is replaced by a dated amendment that says why.

## 4. Sandbox failure modes

The sandbox runs on Docker. On this machine that is Docker Desktop 29.7.2, on an aarch64 Linux VM with 8.3 GB of memory, 10 CPUs and cgroup v2. The only image on disk is `pgvector/pgvector:0.8.0-pg17`. The Python image the sandbox needs is not on disk. Pulling it is an implementation step, and it will not happen without explicit approval.

Each container runs with `--network none`, a read-only root filesystem, the tool mounted read-only at `/tool`, its inputs mounted read-only at `/inputs`, and a 64 MiB tmpfs at `/tmp`, which counts toward the memory limit. Nothing else from the host is mounted: not the repository, not `.env`, not the Docker socket.

| # | Must refuse | Enforced by | What is observed |
|---|---|---|---|
| 1 | Writes inside the repository | The repository is not mounted. Inputs are read-only. The root filesystem is read-only. | A write to `/inputs` raises `OSError` with errno 30 (read-only file system). A write to a path shaped like the repository raises `OSError` (errno 30 or 2). Outcome `crashed`. Host-side, the SHA-256 of every mounted input and of `outputs/ledger/layer3_spend.jsonl`, and the output of `git status --porcelain`, are identical before and after. |
| 2 | Network access | `--network none`. The container has only a loopback interface. | Name resolution raises `socket.gaierror`. A connect to a literal IP address raises `OSError` (network unreachable). Outcome `crashed`. `docker inspect` shows network mode `none`. |
| 3 | Database connections | The same `--network none`. The pgvector container publishes port 5433 on every host interface and sits on the `honest-mistake_default` network, so an ordinary container could reach it through `host.docker.internal:5433` or the bridge gateway. `.env`, which holds the credentials, is never mounted. | Resolving `host.docker.internal` raises `socket.gaierror`. A connect to the bridge gateway address on 5433 raises `OSError`. Outcome `crashed`. |
| 4 | Running past the time limit | The harness kills the container at 30 seconds of wall-clock time. A kill cannot be caught or ignored. | Outcome `timeout`. The elapsed time is recorded. |
| 5 | Using more than the memory limit | `--memory 512m --memory-swap 512m`. | The container is killed by the kernel. Exit code 137 and `OOMKilled` true in `docker inspect`. Outcome `memory_limit`. |
| 6 | Reading anything outside the mounts | Nothing but `/tool`, `/inputs` and the image is visible in the container. | Opening a repository path, relative or absolute, raises `FileNotFoundError`. Outcome `crashed`. |

Refusal 6 carries two requirements. Without it, a tool could pass any question by reading its answer source. It also keeps the files named in the repo rules unreachable from any tool: `outputs/leakage_drop_log.txt`, `outputs/audit_notes.txt`, `outputs/fairness_ablation_notes.txt`, `outputs/features_notes.txt`, `outputs/build_dataset_notes.txt` and `agent/data_dictionary.py`.

**Not covered in Phase 3.** Process count limits (fork bombs), CPU share, timing side channels, and attacks on Docker itself. They are named here so their absence is a recorded decision, not an oversight.

## 5. Negative fixtures

Each broken tool is specified here, before any code. Every one must be rejected with the outcome shown, per section 3.

### Plausible but wrong

- **N1 (K3). Unweighted vintage mean.** Returns the plain average of the three vintage means, ignoring `n_rows`. This is a natural mistake. For `loan_amnt` it gives 14,563.87 against 14,569.560254, off by about 5.7. Expected outcome: `wrong_answer`.
- **N2 (K4). Rounded baseline.** Subtracts 0.7296, the figure printed in `tuning_notes.txt`, instead of the full-precision `test_roc_auc`. Every delta is off by 2.47e-5. That is small enough to look right and far outside 1e-12. Expected outcome: `wrong_answer`.
- **N3 (K5). Signed instead of absolute.** Ranks features by the mean of the signed SHAP values, not their absolute values. Expected outcome: `wrong_answer`.
- **N4 (K6). Second-best trial.** Returns trial 48, value 0.727198, and its parameters. Expected outcome: `wrong_answer`.

### Malformed output

- **N5 (K2). Bare number.** Computes 180 correctly and prints `180` instead of a JSON object. Expected outcome: `bad_output`.

### Never terminates

- **N6. Busy loop.** An infinite loop that burns CPU and never prints. Expected outcome: `timeout`.
- **N7. Blocking sleep that ignores SIGTERM.** Installs a handler that ignores SIGTERM, then sleeps forever. This checks that the harness kill cannot be caught. Expected outcome: `timeout`.

### Escape attempts, one per refusal

Each escape fixture lets its exception propagate. If an escape ever succeeds, the fixture prints a well-formed answer, so a broken sandbox shows up as a wrong outcome and cannot be mistaken for a refusal.

- **N8 (refusal 1). Write to a mounted input.** Opens a file under `/inputs` for appending and writes one line. Expected outcome: `crashed` with `OSError` errno 30, and host hashes unchanged.
- **N9 (refusal 1). Write to the repository path.** Attempts to append to `outputs/ledger/layer3_spend.jsonl`, first by a relative path and then by the repository's absolute host path. Expected outcome: `crashed` with `OSError`, and host hashes and `git status --porcelain` unchanged.
- **N10 (refusal 1). Write through the tool mount.** Attempts to overwrite `/tool/tool.py`. Expected outcome: `crashed` with `OSError` errno 30, and the tool file's hash unchanged.
- **N11 (refusal 2). Network.** Resolves `example.com`, then opens a TCP connection to `1.1.1.1:443` and sends nothing. Expected outcome: `crashed` with `socket.gaierror` on the first attempt. A variant that skips name resolution must fail with `OSError` on the connect.
- **N12 (refusal 3). Database.** Opens a TCP connection to `host.docker.internal:5433`, then to the Docker bridge gateway address on port 5433. Expected outcome: `crashed` with `socket.gaierror` or `OSError`.
- **N13 (refusal 5). Memory.** Allocates 1 GiB in 64 MiB chunks and writes to every page, so the memory is actually committed. Expected outcome: `memory_limit`.
- **N14 (refusal 6). Read the answer.** Under K5's mounts, opens `outputs/agent_cache/shap_global.csv` by relative and absolute path and, if that works, prints its stored ranks, which would be a correct answer. Also opens `outputs/leakage_drop_log.txt`. Expected outcome: `crashed` with `FileNotFoundError`. This fixture passing would mean the validator can be satisfied by reading the answer, and it must never pass.

N6 and N7 cover refusal 4.

The validator is not considered working until it has rejected every one of N1 to N14 with the expected outcome, and has passed every reference tool, as set out in section 3.

## Amendments

### A1. 2026-09-14. The sandbox image, pinned by digest

Written after the image was pulled and before any sandbox code existed.

The sandbox uses `python:3.11-slim`, pulled by digest rather than by tag, so a later push to the tag cannot change the image underneath the results.

- **Index digest (what was pulled):** `sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534`. Pulled as `python@sha256:9534e5a8…`, and the local image ID equals this digest.
- **Platform manifest used on this machine:** `linux/arm64/v8`, `sha256:6c5ae9d998f4cc06f892f428d7af53a566c24ad0dc29fa572696b647cf2762a7`.
- **Contents, from the image's own metadata:** Python 3.11.16, version label `3.11.16-slim-trixie`, base `debian:trixie-slim`, created 2026-08-31T23:57:33Z, 49,186,138 bytes.
- **Host:** Docker client and server 29.7.2, kernel `7.0.12-linuxkit`.

The container runs this digest and nothing else. A different image is used only after a further dated amendment recording its digest.

### A2. 2026-09-14. The container contract named no libraries

Written after R2 and R5 failed in the container, and before any broken tool had run in it.

**What was missing.** Section 4 specified what the sandbox refuses and what it mounts. It never said which libraries the image must contain. The image pinned in A1 is stock `python:3.11-slim`, which has only pip, setuptools, wheel and packaging. Part A did not catch this, because its tools ran in the project's virtualenv, where numpy, pandas and pyarrow were already installed.

**How it was found.** In the container, on the A1 image, R1, R3, R4 and R6 passed on all three runs. R2 and R5 crashed on all three. That is the job the reference tools were added to do: a sandbox that rejects everything would also reject every broken tool, and would look as if it worked. The cause was confirmed by starting the same image with no sandbox flags at all, where numpy, pandas and pyarrow were all absent. No refusal was involved. The failure came at import, before either tool touched the network, a file or memory.

**What was not changed.** The questions were not changed to fit the image. K2 and K5 still give the tool `shap_values.parquet`, and R2 and R5 are unchanged. No refusal was relaxed.

**The first `crashed` outcomes.** The `crashed` class was first exercised by these two reference tools, not by a broken tool. Each of the six executions was classified `crashed` from this raw observation: Docker exit code 1, `OOMKilled` false, not killed by the harness, child return code 1, and a Docker elapsed time of 0.117 to 0.136 s (0.149 to 0.171 s on the harness clock). The last line of stderr was `ModuleNotFoundError: No module named 'pyarrow'` for R2 and `ModuleNotFoundError: No module named 'numpy'` for R5. Peak memory was 18.1 to 18.5 MiB, which is the Python interpreter that starts the tool.

**The image now used.** A derived image, built from `docker/sandbox/Dockerfile`:

- **Base:** `python@sha256:9534e5a8e315485d4061ed659af0fd78a284c015f9b73661b41d6bab25604534`, as in A1.
- **Libraries, at the exact versions in `requirements.txt`:** `numpy==2.4.6`, `pandas==3.0.3`, `pyarrow==24.0.0`.
- **Everything pip resolved, from `pip freeze` inside the image:** `numpy==2.4.6`, `packaging==26.3`, `pandas==3.0.3`, `pyarrow==24.0.0`, `python-dateutil==2.9.0.post0`, `six==1.17.0`. `requirements.txt` does not pin python-dateutil or six. They are recorded here as resolved, not as pinned.
- **Derived image digest:** `sha256:801f6454116549ae4369be7d1ed8e64c3b2143e255931c0c67bc312de67450f6`, linux/arm64, 143,321,615 bytes, created 2026-09-14T06:04:11Z. This is the local image ID. The image was built locally and never pushed to a registry. Rebuilding the Dockerfile produces a different ID, because the creation time is part of the image, so a rebuild is a new image and needs its own amendment.
- **Confirmed inside the image, with `--network none`:** Python 3.11.16, and numpy 2.4.6, pandas 3.0.3 and pyarrow 24.0.0 all import.

**Network.** The network is used while the image is built, because pip downloads the libraries. It is never available while a tool runs: every tool container still starts with `--network none`, as in section 4.

### A3. 2026-09-14. R5's memory headroom

Written after all six reference tools passed on the A2 image, and after the broken tools had run.

The 512 MiB memory limit was frozen without being timed, as section 3 says. On the A2 image, R5 peaked at between 272.7 and 282.7 MiB across its three runs. The highest, 282.7 MiB, is 55% of the limit. The figure is the container's cgroup `memory.peak`, the same counter the limit is enforced against. It includes about 11 MiB for the interpreter that starts the tool, and page cache from reading the 30 MB `shap_values.parquet`. It therefore overstates what R5 itself allocates, but it is what the limit sees. The other five reference tools peaked between 11.7 and 31.6 MiB.

**The limit is not being changed.** R5 is the heaviest realistic reference case: it loads the full SHAP matrix through pandas, and it fits. Raising the limit after seeing a number this close to half of it would be tuning the rule on the observation, which is the thing this document exists to prevent.

**The risk is carried forward.** Tools generated in Phase 4 will have a memory profile nobody knows in advance. A generated tool that exceeds 512 MiB will be classified `memory_limit`. That is the limit doing its job, not a defect in the sandbox or the tool contract, and it should not be read or reported as one.

**Time.** No tool came near half of the 30 s limit. The slowest reference run was R5 at 0.356 s on the harness clock.

## Defect register

Numbering continues from D6 in `PREREGISTRATION_PHASE2.md`.

**D7. 2026-09-14.** Recomputing `mean_abs_shap` from `shap_values.parquet` does not reproduce `shap_global.csv` within 1e-5 relative. Three of 173 nonzero features differ by up to 3.7e-5, and all three have means close to zero: `max_bal_bc_was_missing` at 0.000054, `mths_since_recent_bc_was_missing` at 0.000016 and `disbursement_method_Cash` at 0.000024. Both files carry the same modification time, 2026-08-25T00:01:42, so the same run wrote them. The stored matrix is float32, and the gap is consistent with float32 rounding on very small means. The tolerance was set before the check and was not widened afterwards. The numeric question was dropped instead. Ranks are unaffected: all 173 nonzero features match, and the smallest gap between neighbouring values is 2.6e-4. This is recorded because `shap_global.csv` is the source for the Layer 2 tool `get_shap_ranking`. Its rank order can be reproduced from the stored matrix, but its numeric values cannot.
