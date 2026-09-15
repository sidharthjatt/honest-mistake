"""Phase 5, step 6: the generated tool against V1, V3 and V4, in the sandbox.

What runs is outputs/layer3/phase5/codegen/reply.txt itself, mounted
read-only as /tool/tool.py, so the code executed is byte for byte the reply.
Its hash is confirmed before anything runs. It never runs in process.

Every case runs three times on the image pinned in PREREGISTRATION_PHASE3.md
A2, under Phase 3's refusals and limits, with the full artefact from A2 and
the case's arguments file mounted. Each run's inputs are hashed before and
after.

Each run's full record is appended to runs.jsonl as soon as the run ends,
before anything about it is printed. All nine runs go ahead whatever their
outcomes. A1's stop rule is for R7 only, and a memory_limit here is an
outcome, not a stop (A4). The only thing that halts the runs is the
validator being unable to give a verdict at all (AnswerSourceError), which
is recorded first.

It refuses to start if runs.jsonl already exists, so the runs cannot be
repeated. No API request is made.

    .venv/bin/python -m scripts.run_phase5_step6
"""

import hashlib
import json
import sys
from datetime import datetime
from pathlib import Path

import layer3.phase5_questions  # noqa: F401  registers V1, V3 and V4
from layer3.phase5_questions import ARTEFACT, ARTEFACT_SHA256
from layer3.questions import QUESTIONS, ROOT, AnswerSourceError
from layer3.sandbox import IMAGE, run_in_container
from layer3.validator import MAX_STDOUT_BYTES, classify

TOOL = ROOT / "outputs" / "layer3" / "phase5" / "codegen" / "reply.txt"
TOOL_SHA256 = "94199ea50aa1b9e32d8fc182570864ababe873ce317149124d52d1dc2791f27a"
RECORDS = ROOT / "outputs" / "layer3" / "phase5" / "validation" / "runs.jsonl"
CASES = ("V1", "V3", "V4")
RUNS = 3
MIB = 1024 * 1024


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _append(record: dict) -> None:
    RECORDS.parent.mkdir(parents=True, exist_ok=True)
    with RECORDS.open("a") as fh:
        fh.write(json.dumps(record, default=str) + "\n")


def main() -> int:
    if RECORDS.exists():
        print(f"{RECORDS.name} already exists. The runs are not repeated.")
        return 2
    tool_sha, artefact_sha = _sha256(TOOL), _sha256(ARTEFACT)
    print(f"tool {tool_sha} (expected {TOOL_SHA256}); artefact "
          f"{artefact_sha} (A2 {ARTEFACT_SHA256}); image {IMAGE}")
    if tool_sha != TOOL_SHA256 or artefact_sha != ARTEFACT_SHA256:
        print("STOP: the tool or the artefact is not the recorded file. "
              "Nothing runs.")
        return 2

    for qid in CASES:
        arguments = QUESTIONS[qid].ARGUMENTS
        for run in range(1, RUNS + 1):
            hashes = {}
            started = datetime.now().isoformat(timespec="seconds")
            result = run_in_container(TOOL, qid, arguments, hashes)
            obs = result.observation
            record = {
                "case": qid, "run": run, "started": started,
                "arguments": arguments,
                "exit_code": result.exit_code,
                "killed_by_harness": result.killed_by_harness,
                "oom_killed": result.oom_killed,
                "memory_peak_bytes": result.memory_peak_bytes,
                "oom_kill_events": result.oom_kill_events,
                "child_returncode": result.child_returncode,
                "harness_wall_s": result.harness_wall_s,
                "docker_elapsed_s": result.docker_elapsed_s,
                "exception": obs.exception,
                "stdout_bytes": len(obs.stdout),
                "stdout_sha256": hashlib.sha256(obs.stdout).hexdigest(),
                "stdout": (obs.stdout.decode("utf-8", errors="replace")
                           if len(obs.stdout) <= MAX_STDOUT_BYTES else None),
                "stderr": result.tool_stderr,
                "input_hashes": hashes,
                "host_unchanged": result.host_unchanged,
                "container": result.container,
            }
            try:
                verdict = classify(qid, obs)
                record["outcome"], record["reason"] = (verdict.outcome,
                                                       verdict.reason)
            except AnswerSourceError as exc:
                record["outcome"], record["reason"] = None, f"no verdict: {exc}"
                _append(record)
                print(f"{qid} run {run}: NO VERDICT ({exc}). Recorded. The "
                      f"runs stop, because no verdict can be given.")
                return 2
            _append(record)

            peak = result.memory_peak_bytes
            b, a = hashes["before"], hashes["after"]
            print(f"{qid} run {run}: {record['outcome']}  ({record['reason']})")
            print(f"  exit {result.exit_code}, killed by harness "
                  f"{result.killed_by_harness}, OOMKilled {result.oom_killed}, "
                  f"oom_kill events {result.oom_kill_events}, child returncode "
                  f"{result.child_returncode}, wall {result.harness_wall_s:.3f} "
                  f"s, peak {'n/a' if peak is None else f'{peak / MIB:.1f} MiB'}")
            print(f"  artefact {b.get(ARTEFACT.name)} -> {a.get(ARTEFACT.name)}")
            print(f"  arguments.json {b.get('arguments.json')} -> "
                  f"{a.get('arguments.json')}")
            print(f"  host state unchanged {all(result.host_unchanged.values())}"
                  f"; container {result.container}")
            print(f"  stdout ({len(obs.stdout):,} bytes): "
                  f"{obs.stdout.decode('utf-8', errors='replace')[:300]!r}")
            if result.tool_stderr:
                print("  stderr tail: " + " | ".join(result.tool_stderr[-4:]))
    print(f"\nnine runs recorded in {RECORDS}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
