# Layer 3, Phase 2: prompt caching

Written 2026-09-14, before any caching code existed. This file fixes the design, the projection, the assumptions, the accept rule and the budget ahead of the first cached request. Changes after that point go in dated amendments at the end, the same way as in `PREREGISTRATION.md`.

## What step 2A measured

All counts below come from Anthropic's token counting endpoint for `claude-sonnet-5`, sent with the same thinking setting the agent uses. The endpoint is free. As a check, every one of run7-honest-v2's 14 requests was rebuilt from its `messages.json` and counted. The counts sum to 303,979, which is the input the run recorded, with no difference.

- The static prefix is 3,470 tokens: the system prompt is 1,491 and the eight tool schemas at tool layer 2.0 are 1,979. The canary and honest prompts count the same.
- Sent on all 14 turns, the prefix is 48,580 tokens, which is 15.98% of run7's input.
- The rest, 255,399 tokens or 84.02%, is conversation history: tool results, thinking blocks and text that grow on every turn.
- Caching only the static prefix from turn 2 moves 45,110 tokens to the cache-read price and costs one write of 3,470 at the write price. In base-input terms the run drops from 303,979 to 264,248, a saving of 13.1%.

The static prefix is the smaller part of the bill. The history is where the tokens are.

## Design

**Breakpoint.** A single `cache_control` breakpoint goes on the last content block of the most recent user turn. It moves forward every turn, so the cached span grows with the conversation. On turn N the span covers everything up to the end of the user turn that closed turn N-1, and the request reads that span back instead of paying for it again.

**Request order.** The API renders `tools`, then `system`, then `messages`. The tools therefore sit before the system prompt, and both sit inside the cached span from the first request.

**System prompt.** In caching mode the system prompt is sent as a list holding one text block, with no marker on it. The moving breakpoint does not strictly need this, because a marker on a message caches everything before it, system included. It is done so that a cached request has one fixed shape that the tests can check. A second breakpoint on the system block was considered and rejected. It would give turn 2 a cache read of about 3,470 tokens from the static prefix even if the moving breakpoint failed, and the accept rule below could then pass on the static prefix alone.

**First message.** The opening user message is a plain string in Layer 2. A marker needs a content block, so in caching mode that message is sent as one text block on every request, not only on the first. Otherwise its bytes would change between turn 1 and turn 2 and break the prefix.

**Markers never reach the record.** The breakpoint is placed on a copy of the history built for each request. The stored conversation carries no markers, so old markers cannot pile up, and each request carries exactly one. The API allows at most four per request, and the request builder refuses to return a request with more.

**Caching stays optional.** With caching off, the request is built exactly as in every Layer 2 run: system as a string and no markers anywhere. A run can be made either way for comparison, and the manifest records which mode it used.

**Lookback window.** A breakpoint looks back at most 20 positions for an earlier cache entry. In run7 each turn added at most four positions (thinking, text, a run of tool calls, a run of tool results), well inside that limit.

## Projected saving

This is a projection from run7's recorded token counts. It is not a result, and a cached run will follow its own trajectory with its own token counts.

With the moving breakpoint, every request from turn 2 onward reads back the whole of the previous request's prompt, and writes only what was added since.

- Reads are the sum of turns 1 to 13's input, which is 303,979 minus turn 14's 43,656, giving 260,323 tokens at 0.1x.
- Writes are turn 1's 3,482 plus each turn's growth over the one before. That sum telescopes to turn 14's size, 43,656 tokens at 1.25x.
- Base-equivalent input: 260,323 × 0.1 + 43,656 × 1.25 = 26,032 + 54,570 = 80,602.
- Against run7's 303,979, that is 26.5% of the uncached figure, a saving of roughly 73%.

At the rates in the budget section, run7's input would have cost $0.61 uncached and a projected $0.16 cached. Output is not affected by caching: run7's 18,754 output tokens cost $0.19 either way.

## Assumptions, none of them verified

1. **No gap between turns runs past the 5-minute TTL.** The TTL runs from the start of the request that wrote or last read the entry, so a turn whose generation and tool calls together take more than five minutes loses the cache. The run records carry no per-turn timestamps, so this has not been checked against any past run.
2. **Cache hits happen at all.** A request with a marker that silently fails to cache returns no error. Nothing so far in this project has shown a cache read.
3. **Thinking blocks in the history do not invalidate the cached span.** Every assistant turn carries a thinking block that is echoed back. Anthropic's documentation says Sonnet 4.6 and later models keep prior-turn thinking blocks, which would leave the span intact, but that has not been tested here.

## Accept rule

Caching is considered working only if a real call returns a non-zero `cache_read_input_tokens` on a turn after the first.

A zero cache read with no error is the documented failure mode, and it is the thing being tested. If the second request of the test comes back with a zero cache read, work stops and the result is reported as it is. The prompt is not changed and the call is not retried to make it pass.

The test is one minimal exchange, not an audit. It sends the real tools and the real system prompt, rendered from HEAD, plus two short user turns. If it passes, that shows caching works on a two-turn exchange with this prefix. It does not show that the projection above holds for a full audit.

## Budget

**Cap.** Layer 3 has a hard cap of $15.00 in API spend. This covers every real request made from 2026-09-14 onward, including the caching test above. Layer 2 spend before that date is not counted.

**Rates.** The rates are for `claude-sonnet-5`, read from Anthropic's pricing page (https://platform.claude.com/docs/en/about-claude/pricing) on 2026-09-14, per million tokens:

| Kind | Rate |
|---|---|
| Base input | $2.00 |
| 5-minute cache write | $2.50 |
| Cache read | $0.20 |
| Output | $10.00 |

Cost figures in Layer 3 are reported beside these rates and that date.

**The ledger.** An append-only file, `outputs/ledger/layer3_spend.jsonl`, holds one line per real request, with the usage the API returned and the cost at the rates above.

- **Before every real request,** the request's input is counted with the free counting endpoint and a worst case is computed: all input at the cache-write rate, plus the full `max_tokens` at the output rate.
- **The ledger refuses** any request where recorded spend plus that worst case would exceed the cap. A run is refused at the start by the same check on its first request, before a run directory is created. If a later request in a run would cross the cap, the run ends with the termination `budget_cap`.
- **If counting fails,** the request is not sent.
- **Mock runs** never read or write the ledger.

## Amendments

### A1. 2026-09-14. Comparison rule for the baseline run

Written after the two-turn caching test and before the first audit run with caching on.

This run is not compared to run7-honest-v2 trajectory by trajectory. The model is not deterministic, so turns, tool calls and payload sizes will differ, and any token difference between the two runs confounds caching with a different trajectory.

The only comparison this run supports is within itself: how many of its own input tokens were read at the cache rate against how many were billed at the full input rate, and the cost that follows. The 73% projection was computed on run7's turn sizes and is not an accept rule for this run.

What would count as the mechanism failing: any turn after the first returning a cache_read of zero.

### A2. 2026-09-14. The assumptions after the two-turn test

The two-turn caching test settled less than it might appear to. The three assumptions stand as follows.

1. **No gap between turns runs past the 5-minute TTL.** Still unverified. The two requests started 2 seconds apart, so the TTL was never tested.
2. **Cache hits happen at all.** Settled for a two-turn exchange with this prefix: the second request returned a non-zero cache read. Still unverified for a run of audit length.
3. **Thinking blocks in the history do not invalidate the cached span.** Still unverified. Turn 1 returned a single text block with no thinking, so the history the second request sent carried no thinking block to test against.

The 73% projection remains a projection. Nothing measured so far bears on it.

### A3. 2026-09-14. Measured result of the two-turn test

This is a measurement, kept apart from the projection above.

One two-turn exchange, using the real tools and the honest system prompt rendered from HEAD, with caching on:

| Request | input | output | cache_creation | cache_read |
|---|---|---|---|---|
| 1 | 2 | 4 | 3,505 | 0 |
| 2 | 2 | 3 | 16 | 3,505 |

The second request read back exactly the 3,505 tokens the first had written, and wrote only the 16 tokens added since. Recorded cost for both requests was $0.009582.

This establishes that the mechanism works. It establishes nothing about a full audit: not the saving, not the behaviour across many turns, and not the effect of thinking blocks or tool results in the history.

### A4. 2026-09-14. Measured result of the baseline cached run

This is a measurement on one run, `run11-honest-cached`, and applies to that run alone. It used the same configuration as run7-honest-v2 with `--cache moving-breakpoint` added, and pgvector retrieval served it. It ended `completed` after 11 turns and 33 tool calls.

Per-turn usage, from the run's 11 ledger lines. The totals equal the manifest's.

| Turn | input | output | cache_creation | cache_read |
|---|---|---|---|---|
| 1 | 2 | 174 | 3,480 | 0 |
| 2 | 2 | 661 | 1,025 | 3,480 |
| 3 | 2 | 701 | 10,199 | 4,505 |
| 4 | 2 | 763 | 2,034 | 14,704 |
| 5 | 2 | 1,561 | 2,993 | 16,738 |
| 6 | 2 | 1,079 | 2,500 | 19,731 |
| 7 | 2 | 754 | 3,375 | 22,231 |
| 8 | 2 | 997 | 3,359 | 25,606 |
| 9 | 2 | 1,410 | 2,449 | 28,965 |
| 10 | 2 | 3,107 | 2,835 | 31,414 |
| 11 | 2 | 10,081 | 5,405 | 34,249 |
| Total | 22 | 21,288 | 39,654 | 201,623 |

From turn 2 to turn 11, each turn's cache_read equals the previous turn's cache_read plus its cache_creation, with no exception. Each request therefore read back the whole prompt the one before it had cached, and wrote only what had been added since.

The run sent 241,299 input tokens: 201,623 read at the cache rate, 39,654 written to the cache, and 22 billed at the base input rate. Input cost was $0.139504. The same tokens at the base input rate would have cost $0.482598. Output cost $0.212880, and the run total was $0.352384. The ledger stood at $0.361965 afterwards.

Input cost came out 71.1% below the base-rate figure. That is a measurement on this run. The 73% in the design section is a projection computed on run7's turn sizes. The two figures are not compared here: per A1, this run was not compared to run7.

### A5. 2026-09-14. The cache-write premium

The premium is kept separate from the saving. A4's input cost already bills the writes at the rate charged, so it is not subtracted from the saving again here. The run's 39,654 cache-write tokens were billed at $2.50 per MTok, against $2.00 at the base rate. The extra $0.019827 was paid so that later turns could read the prefix cheaply.

### A6. 2026-09-14. What the baseline cached run settled

The accept rule passed: no turn after the first returned a cache_read of zero.

1. **No gap between turns runs past the 5-minute TTL.** Not tested. Ledger lines are stamped to the second when a response returns. The gaps between consecutive lines were 8, 9, 10, 19, 15, 12, 17, 16, 38 and 121 seconds. The largest, 121 seconds, came before turn 11, which produced 10,081 output tokens. What the TTL measures is the time from one request's start to the next's. That time is at most the sum of two consecutive gaps, here no more than 159 seconds, about half the TTL. No gap came near five minutes, so the run cannot show what happens when one does.
2. **Cache hits happen at all.** Settled for one 11-turn audit with this configuration.
3. **Thinking blocks in the history do not invalidate the cached span.** Tested and held, on this run. All 11 assistant turns in `messages.json` begin with a `thinking` block that carries a signature, from 223 characters on turn 1 to 15,545 on turn 11. `agent._assistant_content` stores those raw blocks in the history, and `build_request` copies every block into each request unchanged. The blocks from turns 1 to 10 were therefore in the history sent on requests 2 to 11, and the cache_read chain in A4 never broke.

   The counts show one thing and not another. The chain identity proves that on every turn the accumulated prefix was read at the cache rate. It does not prove the API kept the thinking blocks inside the cached span. Had they been left out of the cached region, each turn's cache_creation would have been smaller, but the chain would still hold. What is settled is only what assumption 3 claims: thinking blocks in the history did not break caching. This record does not show whether those blocks were themselves cached, and should not be cited as if it did.

## Defect register

Numbering continues from D1 and D2 in `PREREGISTRATION.md`.

**D3. 2026-09-14.** A reporting gap, not a code defect: a new termination value exists that the Layer 2 specification never anticipated. agent.py can now end a run with termination "budget_cap". scripts/layer2_trajectory.py does not enumerate termination values: M1 passes the manifest field through unchanged, and the scope gate keys on is_usable, which is false for such a run. The first run refused at the cap would therefore be reported under M1 and excluded from trajectory metrics without error. No record carries the value today. It is recorded because PREREGISTRATION.md's M1 was written before this value existed, so any report that describes the termination values it saw should name it, and a budget_cap run ends for a reason outside the agent and the harness ceilings.

**D4. 2026-09-14.** `retrieval.index_stats()` takes the embedding model's revision from the code constant `_MODEL_REVISION`, not from anything stored with the index. That field therefore cannot prove which revision built the index. The stamp's model name, `pgvector-bge-small-en-v1.5`, is likewise a constant in `agent/tools.py`. What the run actually measures is which backend served each search. For this run the revision was checked indirectly during the retrieval check before it started: sample descriptions were encoded again and compared against their stored vectors, and every pair gave a cosine of 1.000000. This matters because the validity precondition in `PREREGISTRATION.md` rests on the retrieval stamp, and part of that stamp is reported by the code about itself rather than read from the index.

**D5. 2026-09-14.** `ledger.record` rounds each line's `cost_usd` to the nearest millionth of a dollar with Python's `round`, so a line can be off by up to $0.0000005 either way. `ledger.check` sums those rounded per-line figures and does not recompute cost from the token counts. The `cumulative_usd` field is never read by the check. Recorded spend can therefore drift from the true total, but not in a fixed direction. The drift is at most $0.0000005 per line, and n lines can add up to at most n × $0.0000005. run11's lines sum to $0.352383 against $0.3523836 computed from its token totals, so there the ledger ran low by $0.0000006. At run11's average of about $0.032 per request, the $15.00 cap allows roughly 470 requests, where the drift could reach $0.00024 in either direction. A request could therefore be admitted by that much past the cap. Against the worst-case projection added to every check, over $0.12 per request at current sizes, that margin is negligible, but it exists.
