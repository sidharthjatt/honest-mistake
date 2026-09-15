"""Phase 5, step 5: count the code-generation request and project its cost.

Counts the request exactly as layer3.phase5_codegen builds it, with the free
token-counting endpoint. Sends nothing to messages.create. The ledger total
is read before and after, to show the count spent nothing.

The projection:
- input is known from the count. It is priced at the plain input rate for
  the low end and at the cache-write rate for the high end, because the
  moving breakpoint writes the prompt to the cache only if it is long enough
  to be cached, and this script does not assume which;
- output cannot be counted before a reply exists. The range is section 5's
  guess, 1,500 to 5,000 tokens, including thinking;
- the worst case is the ledger's own rule: all input at the cache-write rate
  plus the full 12,400 max tokens as output.

    .venv/bin/python -m scripts.count_phase5_request
"""

import sys

from agent import ledger
from agent.llm import _client
from layer3.phase5_codegen import build

OUTPUT_GUESS = (1_500, 5_000)


def main() -> int:
    kwargs = build()
    before = ledger.spent_usd()
    lines_before = sum(1 for l in ledger.LEDGER_PATH.read_text().splitlines()
                       if l.strip())

    client = _client()
    counted = client.messages.count_tokens(
        **{k: v for k, v in kwargs.items() if k != "max_tokens"}
    ).input_tokens

    after = ledger.spent_usd()
    lines_after = sum(1 for l in ledger.LEDGER_PATH.read_text().splitlines()
                      if l.strip())

    rates = ledger.RATES_PER_MTOK[kwargs["model"]]
    low = (counted * rates["input"] + OUTPUT_GUESS[0] * rates["output"]) / 1e6
    high = (counted * rates["cache_write_5m"]
            + OUTPUT_GUESS[1] * rates["output"]) / 1e6
    worst = ledger.worst_case_usd(kwargs["model"], counted,
                                  kwargs["max_tokens"])

    print(f"model {kwargs['model']}; max_tokens {kwargs['max_tokens']}; "
          f"thinking {kwargs['thinking']}; tools {'tools' in kwargs}; "
          f"messages {len(kwargs['messages'])}; cache breakpoints on the last "
          f"block {'cache_control' in kwargs['messages'][-1]['content'][-1]}")
    print(f"counted input tokens: {counted:,}")
    print(f"rates per MTok: {rates} ({ledger.RATES_SOURCE})")
    print(f"projection: ${low:.6f} to ${high:.6f} "
          f"(output guessed at {OUTPUT_GUESS[0]:,} to {OUTPUT_GUESS[1]:,})")
    print(f"worst case under the ledger rule: ${worst:.6f}")
    print(f"ledger before the count: ${before:.6f} over {lines_before} lines; "
          f"after: ${after:.6f} over {lines_after} lines")
    print(f"ledger after a request at the projection: ${before + low:.6f} to "
          f"${before + high:.6f}; at the worst case: ${before + worst:.6f} of "
          f"${ledger.CAP_USD:.2f}")
    print(f"the ledger check would "
          f"{'allow' if before + worst <= ledger.CAP_USD else 'REFUSE'} it")
    return 0


if __name__ == "__main__":
    sys.exit(main())
