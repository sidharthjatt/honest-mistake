# Layer 3 report

Written 2026-09-16. This collects what Layer 3 of Honest Mistake established and what it did not. It adds no finding and no rule. Every statement points to the committed document it comes from. The documents remain the record; where this report and a document differ, the document is right.

The Layer 3 documents are:
- **The specifications:** `PREREGISTRATION_PHASE2.md` to `PREREGISTRATION_PHASE5.md`, with their dated amendments (A) and defect register entries (D).
- **The results:** `outputs/layer3/LAYER3_PHASE3.md`, `LAYER3_PHASE4.md` and `LAYER3_PHASE5.md`.
- **The records:** the spend ledger `outputs/ledger/layer3_spend.jsonl`, and the registry `outputs/layer3/registry.jsonl`.

`PREREGISTRATION.md` defines trajectory metrics over the Layer 2 run records, and is not reported here.

## What Layer 3 does and does not demonstrate

**What was built and exercised:**
- **Prompt caching, with a spend ledger that enforces a hard cap.** Measured on one audit run.
- **A sandbox and a known-answer validator.** They pass six hand-written correct tools and reject fourteen hand-written broken ones.
- **A gap detector and spec generator.** They did not meet their accept rules in either version.
- **One generated tool, admitted to a registry.** Admitted after a check against answers drawn from the same file as its data.

**What Layer 3 does not demonstrate:**
- that a detector can tell which questions the tools can answer, because the detector was not accepted;
- that any generated tool gives correct answers, because no independent answer was available;
- that the chain from detection to admission works end to end, because it never ran that way;
- that any agent uses a generated tool, because nothing reads the registry;
- human oversight or independent judging, because both were cut.

Four planned parts were cut, each for lack of a real target or an independent reference.

## Spend

The cap is $15.00 for all real requests from 2026-09-14 onward (`PREREGISTRATION_PHASE2.md`, Budget). The ledger stands at **$2.183232** (`LAYER3_PHASE5.md`, Step 5).

| What was bought | Cost | Source |
|---|---|---|
| Phase 2: a two-turn caching test | $0.009582 | `PREREGISTRATION_PHASE2.md` A3 |
| Phase 2: one cached audit run, `run11-honest-cached` | $0.352384; the ledger stood at $0.361965 afterwards | `PREREGISTRATION_PHASE2.md` A4 |
| Phase 3: sandbox and validator | nothing; Phase 3 made no API calls | `PREREGISTRATION_PHASE3.md` section 1 |
| Phase 4: a pilot of 4 episodes and 1 spec request, plus two runs of 26 episodes | $0.822974 in all ($0.090554, $0.431145, $0.301275) | `LAYER3_PHASE4.md`, What was run |
| Phase 4b: two runs of 26 episodes | $0.993556 ($0.516729, $0.476827) | `LAYER3_PHASE4.md`, Phase 4b, What was run |
| Phase 5: one code-generation request | $0.004736 | `LAYER3_PHASE5.md`, Step 5 |

The phase figures above add to one millionth of a dollar less than the ledger total. `PREREGISTRATION_PHASE2.md` D5 records how per-line rounding makes differences of that size.

Counting tokens was free (`PREREGISTRATION_PHASE4.md` section 6). So were building the Phase 5 artefact, the sandbox runs, validation and the registry write (`PREREGISTRATION_PHASE5.md` section 5).

## Phase 2: prompt caching and the spend ledger

Specification and results: `PREREGISTRATION_PHASE2.md`.

### Established

- **Caching works on a two-turn exchange with the real prefix.** The second request read back exactly the 3,505 tokens the first had written (A3).
- **The cache chain held on one full audit run.** `run11-honest-cached` completed after 11 turns and 33 tool calls. From turn 2 to turn 11, each turn's cache read equalled the previous turn's cache read plus its cache write, with no exception (A4).
- **Input cost on that run came out 71.1% below the base rate.**
  - Of 241,299 input tokens, 201,623 were read from the cache, 39,654 were written to it and 22 were billed at the base rate.
  - Input cost was $0.139504, against $0.482598 at the base rate (A4).
- **The cache-write premium was $0.019827 on that run** (A5).
- **The accept rule passed:** no turn after the first returned a cache read of zero (A6).
- **Thinking blocks in the history did not break caching on that run** (A6).
- **The cache survived gaps of 256 to 276 seconds** between one Phase 4 run and the next (D6, update).
- **The ledger:**
  - it refuses any request whose worst case would take recorded spend past the cap;
  - a failed token count stops the request;
  - mock runs never touch it (Budget).

### Not established

- **Any saving beyond `run11`.** The 71.1% applies to that run alone. The 73% projection was not compared with it (A1, A4).
- **What a cache expiry costs.** No gap between requests has passed five minutes, so an expiry has never been observed (A6, D6 update).
- **Whether thinking blocks are themselves inside the cached span.** The counts show that caching did not break, not that the blocks were cached (A6).
- **Exact recorded spend.** Per-line rounding lets recorded spend drift from the true total by up to $0.0000005 a line, in either direction (D5).
- **Which embedding revision built the index.** The retrieval stamp's model revision comes from a code constant, not from the index (D4).
- **The `budget_cap` termination value.** It did not exist when Layer 2's trajectory specification was written (D3).

## Phase 3: sandbox and known-answer validator

Specification: `PREREGISTRATION_PHASE3.md`. Results: `outputs/layer3/LAYER3_PHASE3.md`.

### Established

- **All six known answers reconcile with their artefacts,** K1 to K6, on every execution (`LAYER3_PHASE3.md`, The known-answer questions).
- **All six reference tools pass,** R1 to R6, on 3 of 3 executions in the container on the derived image (Reference tools).
- **All fourteen broken tools are rejected** with their predicted outcome, N1 to N14, on 3 of 3 executions. Host-side hashes were unchanged (Broken tools).
- **All six outcome classes were exercised.** `timeout` and `memory_limit` are told apart by the harness's own kill record and Docker's `OOMKilled` flag, not by the exit code (Outcome classes).
- **The container runs a pinned image.**
  - The base image is pinned by digest (A1).
  - The stock image had none of the libraries the reference tools need: R2 and R5 crashed on it. A derived image with numpy, pandas and pyarrow at pinned versions is recorded (A2).
- **R5 peaked at 272.7 to 282.7 MiB,** 55% of the 512 MiB limit. The limit was not changed (A3).
- **A tool can read arguments from `/inputs/arguments.json`** (A4; `LAYER3_PHASE3.md`, Amendment A4).
  - **P1** read its arguments exactly.
  - **N18** was refused with errno 30 on every write attempt.
  - **H1** showed the harness refuses to overwrite an existing arguments file.
  - **R1 to R6** passed unchanged.

### Not established

- **That a generated tool can be validated.** No tool was generated in Phase 3 (`LAYER3_PHASE3.md`, What Phase 3 does not establish).
- **Failures nobody anticipated.** The broken tools were written by the same process as the validator (same section).
- **Attacks beyond the six refusals.** Fork bombs, CPU share, timing side channels and attacks on Docker itself were excluded on purpose (`PREREGISTRATION_PHASE3.md` section 4).
- **A sandbox reproducible anywhere else.** The derived image is identified by a local image ID (D8).
- **The report-script fix.** It was never run in a graded run (`LAYER3_PHASE3.md`, What Phase 3 does not establish).
- **A comfortable margin on K3.** Its tolerance is met with 88% of the allowance used (K3).
- **Mean absolute SHAP values.** Recomputed from the stored matrix, they do not reproduce `shap_global.csv` within 1e-5 relative, so the numeric question was dropped (D7).
- **What A4's check leaves out.** N1 to N14 were not re-run, and H1 called the harness function directly, not through a runner (`LAYER3_PHASE3.md`, Amendment A4, What this does not establish).

## Phase 4 and 4b: gap detector and spec generator

Specification: `PREREGISTRATION_PHASE4.md`. Results: `outputs/layer3/LAYER3_PHASE4.md`.

### Established

- **The detector is not accepted in Phase 4.** Parts a, b and c each fail in both runs, as does the rule on how many expected specs are produced (Outcome).
- **The detector is not accepted under 4b either.** Parts a, b and c fail in both runs, the material near-miss rule fails, and the spec count rule fails (Phase 4b, Outcome).

| Rule | Phase 4 run 1 | Phase 4 run 2 | 4b run 1 | 4b run 2 |
|---|---|---|---|---|
| Part a, non-gaps (needs 8 of 9, with A3 and A9) | 6 of 9 | 5 of 9 | 5 of 9 | 7 of 9 |
| Part b, declared gaps (needs 6 of 6) | 3 of 6 | 3 of 6 | 4 of 6 | 4 of 6 |
| Part c, silent gaps (needs 5 of 7), upper bound | at most 3 | at most 1 | at most 4 | at most 2 |
| Expected specs produced (needs 7 of 8) | 4 of 8 | 3 of 8 | 5 of 8 | 4 of 8 |

Source: `LAYER3_PHASE4.md`, Scores, as frozen, for Phase 4 and for 4b.

- **Two rule groups pass in all four runs:** spec rules 1 to 4, and the rule for non-material near-misses (same sections).
- **Rewriting one prompt sentence roughly halved parse failures.** 20 of 52 replies did not parse in Phase 4. After that sentence was changed in 4b, 11 of 52 did not parse (The format finding).
- **A3 was labelled `not_answerable` in all four scored runs.** Its replies parsed and gave the right reason. The prediction in A6 held (A3, against the prediction in A6).
- **The failures are of three kinds:**
  - **format:** the reply does not parse;
  - **judgement:** A3, a null answer read as no answer;
  - **grounding:** A2, the right label citing a call the accept rule does not list.

  An accept rule that matched labels alone would have scored A2 correct (Three kinds of failure).
- **All 31 unparsed replies are valid JSON with prose in front of it.** The JSON alone passes the frozen parser in every one. This is a measurement, not a rescoring (The format failure has no request-level fix).
- **No request-level fix exists for the format failure, with this output format.** Five mechanisms were ruled out (same section):
  - prefill;
  - stop sequences;
  - strict tool use;
  - forced `tool_choice`;
  - structured outputs. The frozen `calls[].arguments` is an open object, and structured outputs require every schema object to be closed.
- **Phase 4 and 4b produced 21 specs for 9 distinct tool ideas** (`PREREGISTRATION_PHASE5.md` section 1).
  - None has a known answer for the question it was generated to answer.
  - 8 of the 9 ideas need new artefacts computed from `data/`.

### Not established

- **Spec quality.** No generated spec was implemented in Phase 4, and whether any would answer its question was not scored (What Phase 4 does not establish).
- **Any rule that needs adjudication.** No adjudication was performed within the timing section 3 requires (What Phase 4 does not establish).
  - A late adjudication was recorded (D18), set up, and stopped before any judgement (`PREREGISTRATION_PHASE5.md` A7).
  - Part c's figures are therefore upper bounds, not scores.
- **How any other prompt would perform.** Each version is one prompt on one model on one date (What Phase 4 does not establish; What 4b does not establish).
- **Label stability.** Two runs are not an estimate of it, and format failures left even fewer usable comparisons (A5; Label stability).
- **The field-matching reading.** It is stated, not frozen. A literal reading would lower part a but change no outcome (What Phase 4 does not establish).
- **A clean cost comparison between runs.**
  - **Phase 4:** every run 2 episode's first request read about 2,500 tokens from run 1's cache (What these runs measure, and what they do not).
  - **4b:** run 2 probably benefited from run 1's cache in the same way, but that was not measured (Phase 4b, What was run; What 4b does not establish).
- **Whether structured outputs constrain turns that should call a tool.** The documentation does not say, and no probe was sent (The format failure has no request-level fix).
- **That NaN was ruled out in the float columns.** The no-null finding rests on `null_count`, which does not count NaN (D9).
- **Complete scope risks for Phase 5.** D10 flagged Phase 5's scope risk (D10), but D12 later recorded that D10 was incomplete (`PREREGISTRATION_PHASE5.md` D12).
- **An accurate reason in the runner's output** when a reply does not parse (D11).

## Phase 5: one generated tool, from code to a registry decision

Specification: `PREREGISTRATION_PHASE5.md`. Results: `outputs/layer3/LAYER3_PHASE5.md`. Registry: `outputs/layer3/registry.jsonl`.

### Established

- **The phase was narrowed to one spec, C4's `get_top_shap_rows`.**
  - **Why:** a known answer built for a gap comes from the same process as the tool.
  - **Why C4:** 8 of the 9 tool ideas need new artefacts computed from `data/`. C4 is the only one whose data can be derived from an existing artefact without touching `data/` (section 1). It still needed a new artefact, built from `shap_values.parquet` (Decision 1).
- **The long-format artefact reproduces its source exactly.** It holds 5,400,000 rows in 180 row groups, and converting it back reproduces `shap_values.parquet` bit for bit. SHA-256 `07ff508b…cc0d` (A2).
- **The validator was proven on that artefact,** on 3 of 3 executions, in process and in the sandbox, with host-side state unchanged (`LAYER3_PHASE5.md`, Step 4).
  - **R7** passed V1, V3 and V4.
  - **N15, N16 and N17** were each rejected as `wrong_answer`.
- **R7 peaked at 440.0 to 464.1 MiB,** 86% to 91% of the memory limit (A4).
- **The code-generation request ran once** (Step 5):
  - 753 input tokens and 323 output tokens, costing $0.004736;
  - the 646-byte reply parsed as Python, and was not empty.
- **The cost estimates were well off, all too high** (Step 5, A finding about section 5's estimating):
  - input by 3.3 to 4.6 times;
  - output by 4.6 times at the low end;
  - the projected low cost by 3.5 times.
- **The generated tool passed V1, V3 and V4 on 9 of 9 sandbox runs,** peaking at 359.9 to 387.2 MiB (Step 6).
- **It was admitted with six limitations recorded, never as validated** (The registry decision; `registry.jsonl`).
- **A4's memory condition held, and its outcome did not occur.** The tool loads the whole file through pandas, and the outcome A4 called plausible, being killed for memory, did not happen. No cause was measured (The open memory point, settled).

### Not established

- **That the tool's answers are correct.** Expected answers were read from the same parquet the artefact was built from. This is self-consistency only (section 2; registry limitation 1).
- **The clamp clause.** V2 was dropped, because a correct all-rows output would exceed the 1 MiB stdout cap (D13; registry limitation 2).
- **Which ranking the question meant.** The tool ranks by signed value, where the spec's wording could also mean absolute value (Decision 3; registry limitation 3).
- **A sound source episode.** The detector labelled it `not_answerable`. It was eligible but never adjudicated, and its reply parsed in 1 of 4 scored runs (section 3; registry limitation 4).
- **The chain end to end.** Detection and the spec were read from the Phase 4 run 1 record. Only code generation, the sandbox, validation and the registry decision ran live (section 1; registry limitation 5).
- **That the spec alone was enough.** The output contract, the mount paths and the reply-shape instruction were supplied by us, not by the spec (A3; registry limitation 6).
- **Any use by an agent.** Admission does not add the tool to the Layer 2 tools or make it reachable by any agent (section 4, The registry decision).
- **Anything beyond one spec and one attempt** (section 2).
- **Behaviour outside the tests.** Behaviour above the available count, zero or negative `top_n`, the order of equal values, and running outside the sandbox were never exercised (`LAYER3_PHASE5.md`, Observations from the code read).
- **A first send script that reported correctly.** The first version reported an empty reply as parsing. It was found in mock mode and fixed before the real request (D15).

## The four cuts

Each cut is a finding: what it would have required did not exist in the system as built.

### A human-in-the-loop checkpoint

**Cut because there is nothing real to gate** (`PREREGISTRATION_PHASE5.md` A6).
- Nothing reads the registry, so admission exposes nothing.
- The one admission has been made and is not revisited (D17).
- An override log would be empty by design, because the frozen rules forbid repair, retry and second attempts, and the ledger holds no refusal lines.
- Building a checkpoint would mean manufacturing a decision for it to gate.

**The approvals that do exist are process approvals made in conversation:** the paid request, each commit and each push. They are not a checkpoint in a running pipeline (A6).

### An Agent-as-a-Judge with a separate verifier

**Cut because a judge would have nothing independent to be compared against** (`PREREGISTRATION_PHASE5.md` A7). It would judge material of one of two kinds:
- material that already has a mechanical reference, so it would re-derive a written rule;
- material with no independent reference at all, the same circularity that narrowed Phase 5.

**The late adjudication that would have served as its reference was set up and stopped before any judgement** (A7). It could change no Phase 4 or 4b outcome, and could not complete section 3's rule, whose timing condition was gone (D18).

### A request-level fix for the detector's format failure

**Cut because no request-level mechanism fits the frozen output format** (`LAYER3_PHASE4.md`, The format failure has no request-level fix).
- **The planned measurement was not run.** Its one candidate variable, structured outputs, failed the schema requirement before any request.
- **What was planned:** four runs, a fresh before and an after.
- **The design consequence:** the frozen output format, fixed before this mattered, is what blocks the structured-outputs route.

### An adversarial test

**Cut because no Layer 3 component has both a live target and an independent reference without building something new** (`PREREGISTRATION_PHASE5.md` A8).
- **The sandbox:** its anticipated refusals are already exercised.
- **The validator:** it is self-consistency only.
- **The detector:** it is already unaccepted.
- **The registry, HITL and the judge:** the registry is unread, and the other two do not exist.

**The one real target, prompt injection or a subtle canary against the Layer 2 agent, is in Layer 2.** It would need a new artefact and paid runs.

**The attacks it would have made are already covered** (A8):
- broken tools N1 to N18;
- Phase 4's traps;
- Layer 2's canary and hard negatives.

## Departures from plan, as recorded

- **The phase numbering changed without being recorded** (`PREREGISTRATION_PHASE5.md` D16).
  - A plan agreed in conversation had phase 5 as HITL policy and override logging, and phase 6 as judge, verifier and agreement.
  - The committed documents number phase 5 as code generation, and no amendment recorded the change.
- **Phase 5 admitted a tool without recording a departure from the README.** The README said a human-in-the-loop checkpoint sits in front of admission (D17).
- **A defect entry was dated from another finding.** D12's date was first copied from D13's discovery, not from its own source (D14).
- **The adjudication was late.** It came after the scores were published, against section 3's timing rule (`PREREGISTRATION_PHASE4.md` D18).

## Corrections made to the record

Claims that were written, then corrected against the records.

- **D12's date.**
  - **Claimed:** D12 was dated 2026-09-15, on the grounds that the V2 conflict was found that day.
  - **The record showed:** that was D13's discovery, not D12's. D12's own source, the scope report, was given at 00:19 IST on 2026-09-15, so the date stands, now resting on that source. A proposed correction to 2026-09-14 was checked and not applied.
  - **Recorded in:** `PREREGISTRATION_PHASE5.md` D14.
- **The send script's parse verdict.**
  - **Claimed:** the first version of `scripts/send_phase5_request.py` decided "parses as Python" with `ast.parse` alone.
  - **The record showed:** `ast.parse` accepts an empty string, and section 4 rejects an empty reply. It was found in mock mode, and the verdict was split into its conditions before the real request.
  - **Recorded in:** `PREREGISTRATION_PHASE5.md` D15.
- **C4 "needs no new artefact".**
  - **Claimed:** C4 needs no new artefact, a reading taken from the scope survey.
  - **The record showed:** the spec names a new long-format artefact built from `shap_values.parquet`. The reading came from the survey, not the spec.
  - **Recorded in:** `PREREGISTRATION_PHASE5.md` section 4, Decision 1 ("An earlier reading corrected"), and D12.
- **The source episode's description.**
  - **Claimed:** at the registry decision, in conversation, the episode was described as "scored not_answerable".
  - **The record showed:** the detector labelled it `not_answerable`. The episode was eligible for adjudication, never adjudicated, and not scored correct (`PREREGISTRATION_PHASE5.md` section 3).
  - **Recorded in:** the corrected wording is what was committed, in `LAYER3_PHASE5.md` (registry limitation 4) and `registry.jsonl`. The wrong wording was never committed, so no document records the correction itself.

## Unresolved

- **The runtime audit hook claim.** `README.md` states: "A runtime audit hook re-run over all eight tools and every error path confirms that a tool call opens the six cache artefacts and nothing else, with no file under `data/` touched and no subprocess started." The committed code has two audit hooks, in `scripts/test_layer2_trajectory.py` and `scripts/test_llm_caching.py`. Each records only the files opened under `outputs/agent_runs/`, so that its suite can fail if a real run record is read.
  - Neither hook checks which files a tool call opens, whether anything under `data/` is touched, or whether a subprocess starts.
  - `test_llm_caching.py` does build a `ToolLayer` and run the audit loop, but its hook watches only the run records.
  - No committed code performs the check the README describes. Whether that check was run and not committed is unresolved.
- **What a cache expiry costs.** It is still unobserved (`PREREGISTRATION_PHASE2.md` D6, update).
- **Whether thinking blocks are inside the cached span** (`PREREGISTRATION_PHASE2.md` A6).
- **Whether structured outputs constrain turns that should call a tool** (`LAYER3_PHASE4.md`, The format failure has no request-level fix).
- **The 16 Phase 4 and 4b judgements that were never adjudicated** (`PREREGISTRATION_PHASE5.md` A7).

## Amendments

### A1. 2026-09-20. The D numbering continues in `SCAN_DEFECTS.md`

`SCAN_DEFECTS.md` now exists, and the D numbering continues in it, from D19. No finding in this report is changed.
