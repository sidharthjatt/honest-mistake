"""run_audit.py — Honest Mistake, Layer 2 runner.

Constructs a tool layer, runs the ReAct loop once, and writes everything
needed to analyse or defend the run afterwards. It scores nothing and
never reads the answer key.

Naming: this module's entry point is main(). The loop it calls is
agent.agent.run_audit, imported here as run_react_loop so that no name
in this file collides with the module's own name.

Mock runs and real runs are stamped apart everywhere they could later be
confused: in the run directory name, in the manifest, and in a header at
the top of every file written. A mock run produces no network call and
its numbers are fixtures, not results.

Usage:
    .venv/bin/python -m agent.run_audit                    # mock, default
    .venv/bin/python -m agent.run_audit --no-populated     # mock, ablated
    .venv/bin/python -m agent.run_audit --real             # calls the API
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from agent.agent import run_audit as run_react_loop
from agent.llm import MAX_TOKENS, MODEL
from agent.prompts import build_system_prompt
from agent.tools import ToolLayer

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_RUNS_DIR = _PROJECT_ROOT / "outputs" / "agent_runs"
_CACHE = _PROJECT_ROOT / "outputs" / "agent_cache"
_CACHE_CANARY = _PROJECT_ROOT / "outputs" / "agent_cache_canary"
_PARAMS_CANARY = _PROJECT_ROOT / "outputs" / "models" / "best_params_canary.json"

MOCK_BANNER = (
    "MOCK RUN - SYNTHETIC FIXTURE REPLIES, NO API CALL WAS MADE. "
    "NOTHING BELOW IS A MODEL RESULT."
)
REAL_BANNER = "REAL RUN - LIVE API CALLS."

# Everything above this line in final_answer.txt is added by the runner;
# everything below it is the model's text byte for byte.
VERBATIM_DELIMITER = "----- VERBATIM MODEL TEXT BELOW THIS LINE -----"


def _preflight(cache_dir: Path) -> None:
    """Fail clearly if the cached artefacts the tools need are absent."""
    required = {
        "SHAP ranking": cache_dir / "shap_global.csv",
        "per-row SHAP values": cache_dir / "shap_values.parquet",
        "ablation results": cache_dir / "ablation_cache.csv",
    }
    missing = [label for label, path in required.items() if not path.exists()]
    if missing:
        raise SystemExit(
            "Cannot start: the cached artefacts the tools read are missing "
            f"({', '.join(missing)}). Generate them by running the precompute "
            "step, then try again."
        )


def _require_api_key() -> None:
    """Check the key before a real run, rather than failing mid-loop."""
    import os

    from dotenv import load_dotenv

    load_dotenv()
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit(
            "Cannot start a real run: ANTHROPIC_API_KEY is not set. Copy "
            ".env.example to .env and put your key in it, or drop --real to "
            "run against the fixtures instead."
        )


def print_real_run_warning(max_turns: int, max_tool_calls: int) -> None:
    """Unmissable notice shown before any live call."""
    line = "!" * 72
    print(line)
    print("!!  LIVE API RUN - THIS WILL INCUR COST".ljust(70) + "!!")
    print(line)
    print(f"  model            {MODEL}")
    print(f"  max_tokens/turn  {MAX_TOKENS}")
    print(f"  turn ceiling     {max_turns}")
    print(f"  tool call ceil.  {max_tool_calls}")
    print(f"  worst case       {max_turns} requests, each up to "
          f"{MAX_TOKENS} output tokens")
    print("  the full conversation is resent on every turn, so input")
    print("  tokens grow with each turn taken")
    print(line)


def _run_dir(config_id: str, mock: bool, label: str | None) -> Path:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    mode = "MOCK" if mock else "REAL"
    parts = [stamp, mode, config_id]
    if label:
        safe = "".join(ch if ch.isalnum() or ch in "-_" else "-"
                       for ch in label)[:40]
        parts.append(safe)
    path = _RUNS_DIR / "__".join(parts)
    path.mkdir(parents=True, exist_ok=False)
    return path


def _write_json(path: Path, banner: str, payload: dict) -> None:
    """Write JSON with the mode banner as its first key."""
    stamped = {"_MODE": banner, **payload}
    path.write_text(json.dumps(stamped, indent=2, default=str))


def _write_final_answer(path: Path, banner: str, text: str,
                        manifest: dict) -> None:
    header = [
        "=" * 72,
        banner,
        "=" * 72,
        f"run          {manifest['run_directory']}",
        f"generated    {manifest['timestamp']}",
        f"config_id    {manifest['config_id']}",
        f"termination  {manifest['termination']}  "
        f"(usable: {manifest['is_usable']})",
        "",
        "The runner did not parse or alter the text below.",
        VERBATIM_DELIMITER,
    ]
    path.write_text("\n".join(header) + "\n" + text + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_audit",
        description="Run one audit and persist its artefacts. Mock by "
                    "default; a live run must be asked for explicitly.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--mock", action="store_true",
                      help="use fixture replies, no network call (default)")
    mode.add_argument("--real", action="store_true",
                      help="opt in to live API calls, which cost money")
    parser.add_argument("--no-populated", action="store_true",
                        help="build the tool layer with the populated field "
                             "suppressed")
    parser.add_argument("--max-turns", type=int, default=12)
    parser.add_argument("--max-tool-calls", type=int, default=40)
    parser.add_argument("--canary", action="store_true",
                        help="audit the canary model and its parallel cache "
                             "instead of the Layer 1 model")
    parser.add_argument("--label", type=str, default=None,
                        help="short label appended to the run directory name")
    args = parser.parse_args(argv)

    # Mock is the default: a paid call has to be requested, never reached
    # by omission.
    mock = not args.real
    banner = MOCK_BANNER if mock else REAL_BANNER

    cache_dir = _CACHE_CANARY if args.canary else _CACHE
    n_features = 180
    tuning_record = None
    if args.canary:
        if not _PARAMS_CANARY.exists():
            raise SystemExit(
                "Cannot start a canary run: the canary model record is "
                "missing. Plant the canary first, then try again.")
        rec = json.loads(_PARAMS_CANARY.read_text())
        n_features = int(rec["n_features"])
        tuning_record = _PARAMS_CANARY

    _preflight(cache_dir)
    if not mock:
        print_real_run_warning(args.max_turns, args.max_tool_calls)
        _require_api_key()

    # Fresh layer per run, so no log or cached frame bleeds between runs.
    tools = ToolLayer(include_populated=not args.no_populated,
                      cache_dir=cache_dir)
    config = tools.run_config()

    # Built from the same values passed to the loop, so the ceilings the
    # prompt states and the ceilings enforced cannot diverge.
    system = build_system_prompt(args.max_turns, args.max_tool_calls,
                                 n_features=n_features,
                                 tuning_record=tuning_record)

    started = datetime.now()
    run = run_react_loop(
        tools,
        mock=mock,
        max_turns=args.max_turns,
        max_tool_calls=args.max_tool_calls,
        system=system,
    )
    finished = datetime.now()

    out_dir = _run_dir(config["config_id"], mock, args.label)

    manifest = {
        "mode": "MOCK" if mock else "REAL",
        "mock": mock,
        "network_calls_made": (not mock),
        "run_directory": out_dir.name,
        "timestamp": started.isoformat(timespec="seconds"),
        "finished": finished.isoformat(timespec="seconds"),
        "wall_seconds": round((finished - started).total_seconds(), 2),
        "model": MODEL if not mock else f"{MODEL} (not called; fixtures used)",
        "sampling_parameters": "none sent - removed for this model family",
        "max_tokens_per_turn": MAX_TOKENS,
        "config_id": config["config_id"],
        "artefact_variant": config["artefact_variant"],
        "cache_dir": config["cache_dir"],
        "canary": bool(args.canary),
        "n_features_stated_in_prompt": n_features,
        "tool_layer_version": config["tool_layer_version"],
        "dictionary_populated_field": config["dictionary_populated_field"],
        "termination": run.termination,
        "is_usable": run.is_usable,
        "last_stop_reason": run.last_stop_reason,
        "turns": run.turns,
        "tool_calls": run.tool_calls,
        "usage": dict(run.usage),
        "limits": {
            "max_turns": args.max_turns,
            "max_tool_calls": args.max_tool_calls,
        },
        "system_prompt_chars": len(system),
        "ceilings_stated_in_prompt": True,
    }

    _write_json(out_dir / "manifest.json", banner, manifest)
    _write_json(out_dir / "messages.json", banner,
                {"messages": run.messages})
    _write_json(out_dir / "tool_call_log.json", banner,
                {"config_id": run.config_id, "calls": run.tool_call_log})
    _write_final_answer(out_dir / "final_answer.txt", banner,
                        run.final_text, manifest)

    print(f"\n{banner}")
    print(f"run directory     {out_dir.relative_to(_PROJECT_ROOT)}")
    print(f"config_id         {run.config_id}")
    print(f"termination       {run.termination}  (usable: {run.is_usable})")
    print(f"turns / calls     {run.turns} / {run.tool_calls}")

    if mock:
        print("token usage       not applicable - fixtures report zero")
    else:
        u = run.usage
        print("token usage")
        print(f"  input           {u['input']:,}")
        print(f"  output          {u['output']:,}")
        print(f"  cache_creation  {u['cache_creation']:,}")
        print(f"  cache_read      {u['cache_read']:,}")
        print("  no cost figure is given here: pricing is not verified in "
              "this project, and a wrong number would be worse than none.")

    if not run.is_usable:
        print(f"\nNote: this run ended as '{run.termination}'. Its answer is "
              f"not a finished one and should not be scored as if it were.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
