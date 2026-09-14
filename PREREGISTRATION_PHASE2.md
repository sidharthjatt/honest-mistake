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

## Defect register

Numbering continues from D1 and D2 in `PREREGISTRATION.md`.

**D3. 2026-09-14.** A reporting gap, not a code defect: a new termination value exists that the Layer 2 specification never anticipated. agent.py can now end a run with termination "budget_cap". scripts/layer2_trajectory.py does not enumerate termination values: M1 passes the manifest field through unchanged, and the scope gate keys on is_usable, which is false for such a run. The first run refused at the cap would therefore be reported under M1 and excluded from trajectory metrics without error. No record carries the value today. It is recorded because PREREGISTRATION.md's M1 was written before this value existed, so any report that describes the termination values it saw should name it, and a budget_cap run ends for a reason outside the agent and the harness ceilings.
