"""Run Phase 4 detection episodes and spec requests.

A mode must be named. --mock replays fabricated replies through the real
request path against a temporary ledger and makes no API request. --real
spends money, and is only run after its projection has been reported and
approved.

    .venv/bin/python -m scripts.run_phase4 --mock --items A1,C3,B2,NM3 --spec-items C3 --label phase4-pilot
    .venv/bin/python -m scripts.run_phase4 --real --items A1,C3,B2,NM3 --spec-items C3 --label phase4-pilot
"""

import argparse
import sys
import tempfile
from pathlib import Path

from agent import ledger
from agent.tools import ToolLayer
from layer3 import phase4


def _print_results(episodes, specs, skipped):
    for e in episodes:
        print(f"  {e.item:<4} {e.termination:<13} turns {e.turns}  tool calls {e.tool_calls}  "
              f"output per turn {e.output_tokens_per_turn}  cost ${e.cost_usd:.6f}  "
              f"label {e.output['label'] if e.output else None}"
              + (f"  parse error: {e.parse_error}" if e.parse_error else ""))
    for s in specs:
        kind = next(iter(s.output)) if s.output else None
        print(f"  spec {s.item:<4} {s.termination:<13} output tokens "
              f"{s.usage['output'] if s.usage else None}  cost ${s.cost_usd:.6f}  result {kind}"
              + (f"  parse error: {s.parse_error}" if s.parse_error else ""))
    for s in skipped:
        print(f"  spec {s['item']} not requested: {s['reason']}")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--mock", action="store_true")
    mode.add_argument("--real", action="store_true")
    p.add_argument("--items", required=True)
    p.add_argument("--spec-items", default="")
    p.add_argument("--label", required=True)
    p.add_argument("--out", default=str(phase4.RUNS_DIR))
    args = p.parse_args(argv)

    items = [i.strip() for i in args.items.split(",") if i.strip()]
    spec_items = [i.strip() for i in args.spec_items.split(",") if i.strip()]
    unknown = [i for i in items if i not in phase4.QUESTIONS]
    if unknown:
        raise SystemExit(f"Unknown items: {unknown}")
    stray = [i for i in spec_items if i not in items or i not in phase4.SPEC_ELIGIBLE]
    if stray:
        raise SystemExit(f"Spec items must be run items from parts b or c: {stray}")

    tools = ToolLayer()  # honest cache, both suppression switches on

    if args.real:
        print("REAL RUN - LIVE API CALLS.")
        stats = phase4.preflight_retrieval()
        print(f"  retrieval ready: {stats['rows']} rows, dimension {stats['dimension']}")
        print(f"  ledger before: ${ledger.spent_usd():.6f} of ${ledger.CAP_USD:.2f}")
        episodes, specs, skipped = phase4.run_items(items, spec_items, tools, args.label)
        run_dir = phase4.write_record("REAL", args.label, episodes, specs, skipped, Path(args.out))
        print(f"  ledger after: ${ledger.spent_usd():.6f}")
    else:
        print("MOCK RUN - fabricated replies, no API request.")
        replies = []
        for n, _ in enumerate(items, start=1):
            replies += phase4.fabricated_detection_replies(n)
        replies += [phase4.fabricated_spec_reply() for _ in spec_items]
        with tempfile.TemporaryDirectory() as tmp:
            client = phase4.MockClient(replies)
            with phase4.mocked(client, Path(tmp) / "mock_ledger.jsonl"):
                episodes, specs, skipped = phase4.run_items(items, spec_items, tools, args.label)
                print(f"  mock ledger lines: {len(ledger.LEDGER_PATH.read_text().splitlines())}")
        run_dir = phase4.write_record("MOCK", args.label, episodes, specs, skipped, Path(args.out))

    _print_results(episodes, specs, skipped)
    print(f"  record: {run_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
