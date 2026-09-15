"""Phase 5, step 5: send the one code-generation request, and record the reply.

One attempt. Nothing here retries, repairs or re-requests, whatever comes
back. The parts are loaded by layer3.phase5_codegen, which refuses unless
both hash to the values in amendment A3, and the request goes through
agent.llm.call_llm, so the ledger check before sending and the ledger line
after are the same code that served Phase 4.

The first thing done with the reply is to write it to disk, before anything
else is computed, so a failure later in this script cannot lose it. Then it
records the usage, cost, ledger position, whether output fell inside
section 5's guess, and whether the reply parses as Python as returned. It
does not run or judge the code.

It refuses to start if a record already exists or the ledger already holds a
line with this label, so it cannot send twice.

    .venv/bin/python -m scripts.send_phase5_request          # sends
    .venv/bin/python -m scripts.send_phase5_request --mock DIR   # no request
"""

import ast
import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

from agent import ledger
from agent.llm import MAX_TOKENS, MODEL, THINKING, call_llm
from layer3.phase5_codegen import (CACHE, PROMPT_SHA256, ROOT, SPEC_ITEM,
                                   SPEC_RECORD, SPEC_SHA256, load_parts)

LABEL = "phase5-codegen"
RECORD_DIR = ROOT / "outputs" / "layer3" / "phase5" / "codegen"
OUTPUT_GUESS = (1_500, 5_000)


def _ledger_lines() -> list[dict]:
    return [json.loads(l) for l in ledger.LEDGER_PATH.read_text().splitlines()
            if l.strip()]


def main(argv) -> int:
    mock = len(argv) == 3 and argv[1] == "--mock"
    if not mock and len(argv) != 1:
        print("usage: send_phase5_request [--mock DIR]")
        return 2
    out = Path(argv[2]) if mock else RECORD_DIR
    reply_path, record_path = out / "reply.txt", out / "response.json"

    if reply_path.exists() or record_path.exists():
        print(f"A record already exists in {out}. Nothing is sent.")
        return 2
    if not mock and any(r.get("label") == LABEL for r in _ledger_lines()):
        print(f"The ledger already holds a {LABEL} line. Nothing is sent.")
        return 2

    system, spec = load_parts()
    before_usd = ledger.spent_usd()
    before_lines = len(_ledger_lines())
    sent_at = datetime.now().isoformat(timespec="seconds")

    result = call_llm([{"role": "user", "content": spec}], [], system,
                      mock=mock, cache=CACHE, label=LABEL)

    # Written first, before anything that could fail.
    out.mkdir(parents=True, exist_ok=True)
    reply = result["text"].encode("utf-8")
    reply_path.write_bytes(reply)
    record = {
        "sent_at": sent_at, "mock": mock, "label": LABEL, "model": MODEL,
        "max_tokens": MAX_TOKENS, "thinking": THINKING, "cache": CACHE,
        "tools": [], "prompt_sha256": PROMPT_SHA256,
        "spec_record": str(SPEC_RECORD.relative_to(ROOT)),
        "spec_item": SPEC_ITEM, "spec_sha256": SPEC_SHA256,
        "result": result,
    }
    record_path.write_text(json.dumps(record, indent=1, default=str))

    after_usd = ledger.spent_usd()
    after_lines = _ledger_lines()
    usage = result["usage"]
    text_blocks = [b for b in result["content"] if b.get("type") == "text"]
    kinds = [b.get("type") for b in result["content"]]
    try:
        ast.parse(result["text"])
        ast_ok = True
    except (SyntaxError, ValueError):
        ast_ok = False
    # ast.parse accepts an empty string, but section 4 rejects an empty
    # reply, so both facts are reported and the rule uses both.
    empty = not result["text"].strip()
    parses = "yes" if ast_ok and not empty else "no"

    print(f"mock: {mock}; stop_reason: {result['stop_reason']}")
    print(f"content blocks: {kinds}; text blocks joined into the reply: "
          f"{len(text_blocks)}")
    print(f"reply: {len(reply):,} bytes, sha256 "
          f"{hashlib.sha256(reply).hexdigest()}; written to {reply_path}")
    print(f"usage: input {usage['input']:,}, output {usage['output']:,} "
          f"(thinking included), cache_creation {usage['cache_creation']:,}, "
          f"cache_read {usage['cache_read']:,}")
    if not mock:
        line = after_lines[-1]
        print(f"ledger line: label {line['label']}, cost_usd "
              f"{line['cost_usd']}, cumulative_usd {line['cumulative_usd']}")
    print(f"ledger: ${before_usd:.6f} over {before_lines} lines before; "
          f"${after_usd:.6f} over {len(after_lines)} lines after; this "
          f"request ${after_usd - before_usd:.6f}")
    low, high = OUTPUT_GUESS
    inside = low <= usage["output"] <= high
    print(f"output inside section 5's guess of {low:,}-{high:,}: "
          f"{'yes' if inside else 'no'}")
    print(f"ast.parse on the reply as returned succeeds: "
          f"{'yes' if ast_ok else 'no'}; reply empty: "
          f"{'yes' if empty else 'no'}")
    print(f"parses as Python as returned (section 4: ast.parse succeeds and "
          f"the reply is not empty): {parses}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
