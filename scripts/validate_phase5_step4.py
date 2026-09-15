"""Phase 5, step 4: the validator against R7 and N15-N17.

Order, per PREREGISTRATION_PHASE5.md section 4 and amendment A1:
- in process first, then in the sandbox on the image pinned in Phase 3 A2;
- in each, R7 on V1, V3 and V4 before any broken tool;
- every case three times.

Every execution mounts the full artefact. Its hash among the run's inputs is
recorded before and after, and must equal the SHA-256 recorded in A2.

Stopping:
- In the sandbox, A1's rule is live: the first execution of R7 that ends in
  crashed, memory_limit or timeout stops everything, whatever the cause.
- Any other R7 result that is not pass also stops before a broken tool runs,
  because the validator cannot count as working without its reference tool.
- Nothing is retried, and no limit, artefact or tool is changed.

No API request is made.

    .venv/bin/python -m scripts.validate_phase5_step4
"""

import hashlib
import subprocess
import sys
from pathlib import Path

import layer3.phase5_questions  # noqa: F401  registers V1, V3 and V4
from layer3.phase5_questions import ARTEFACT, ARTEFACT_SHA256
from layer3.questions import QUESTIONS, ROOT, SHAP_VALUES
from layer3.sandbox import IMAGE, LEDGER, run_in_container
from layer3.validator import classify, run_in_process

TOOLS = ROOT / "layer3" / "tools"
RUNS = 3
MIB = 1024 * 1024
A1_STOP = {"crashed", "memory_limit", "timeout"}

R7 = [("R7", "V1", "reference/r7_top_shap_rows.py", "pass"),
      ("R7", "V3", "reference/r7_top_shap_rows.py", "pass"),
      ("R7", "V4", "reference/r7_top_shap_rows.py", "pass")]
BROKEN = [("N15", "V1", "broken/n15_absolute_ranking.py", "wrong_answer"),
          ("N16", "V1", "broken/n16_ascending.py", "wrong_answer"),
          ("N17", "V4", "broken/n17_column_name.py", "wrong_answer")]

CONTAINER = {
    "network_mode": "none",
    "readonly_rootfs": True,
    "memory_bytes": 512 * MIB,
    "memory_swap_bytes": 512 * MIB,
    "mounts": [("/inputs", False), ("/tool/tool.py", False)],
    "image": IMAGE,
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _repo_state() -> tuple:
    return _sha256(LEDGER), subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
        text=True, check=True).stdout


def _hash_problems(hashes: dict) -> list[str]:
    name = ARTEFACT.name
    problems = []
    for when in ("before", "after"):
        got = hashes.get(when, {}).get(name)
        if got != ARTEFACT_SHA256:
            problems.append(f"artefact hash {when} the run is {got}, not the "
                            f"A2 hash")
    if hashes.get("before") != hashes.get("after"):
        problems.append("an input's hash changed during the run")
    return problems


def _hash_line(hashes: dict) -> str:
    b, a = hashes["before"], hashes["after"]
    return (f"artefact {b[ARTEFACT.name][:12]}.. -> {a[ARTEFACT.name][:12]}..; "
            f"arguments.json {b['arguments.json'][:12]}.. -> "
            f"{a['arguments.json'][:12]}..")


def _one_in_process(case, qid, rel, expected):
    hashes = {}
    state = _repo_state()
    obs = run_in_process(TOOLS / rel, qid, QUESTIONS[qid].ARGUMENTS, hashes)
    verdict = classify(qid, obs)
    problems = _hash_problems(hashes)
    if _repo_state() != state:
        problems.append("the ledger or git status changed")
    if verdict.outcome != expected:
        problems.append(f"outcome {verdict.outcome}, expected {expected}")
    stdout = obs.stdout.decode("utf-8", errors="replace").strip()
    print(f"{case} {qid} run: {verdict.outcome}  ({verdict.reason})")
    print(f"  {obs.elapsed_s:.2f} s; {_hash_line(hashes)}; repo state "
          f"unchanged {not any('ledger' in p for p in problems)}")
    print(f"  stdout {stdout[:200]!r}{' ...' if len(stdout) > 200 else ''}")
    for p in problems:
        print(f"  UNEXPECTED: {p}")
    return verdict, problems


def _one_in_container(case, qid, rel, expected):
    hashes = {}
    result = run_in_container(TOOLS / rel, qid, QUESTIONS[qid].ARGUMENTS,
                              hashes)
    verdict = classify(qid, result.observation)
    problems = _hash_problems(hashes)
    changed = [k for k, same in result.host_unchanged.items() if not same]
    if changed:
        problems.append(f"host state changed: {changed}")
    config = dict(result.container)
    config["mounts"] = [tuple(m) for m in config["mounts"]]
    for key, value in CONTAINER.items():
        if config.get(key) != value:
            problems.append(f"container {key} is {config.get(key)!r}")
    if verdict.outcome != expected:
        problems.append(f"outcome {verdict.outcome}, expected {expected}")
    peak = result.memory_peak_bytes
    stdout = result.observation.stdout.decode("utf-8", errors="replace").strip()
    print(f"{case} {qid} run: {verdict.outcome}  ({verdict.reason})")
    print(f"  harness: wall {result.harness_wall_s:.3f} s, exit "
          f"{result.exit_code}, killed by harness {result.killed_by_harness}, "
          f"OOMKilled {result.oom_killed}, peak "
          f"{'n/a' if peak is None else f'{peak / MIB:.1f} MiB'}, "
          f"host state unchanged {not changed}")
    print(f"  {_hash_line(hashes)}")
    print(f"  stdout {stdout[:200]!r}{' ...' if len(stdout) > 200 else ''}")
    if result.tool_stderr:
        print("  stderr tail: " + " | ".join(result.tool_stderr[-4:]))
    for p in problems:
        print(f"  UNEXPECTED: {p}")
    return verdict, problems


def _phase(label, one, a1_live) -> int:
    print(f"=== {label}: R7 ===")
    for case, qid, rel, expected in R7:
        for run in range(1, RUNS + 1):
            print(f"[run {run}]", end=" ")
            verdict, problems = one(case, qid, rel, expected)
            if a1_live and verdict.outcome in A1_STOP:
                print(f"\nSTOP (A1): R7 on {qid}, run {run}, ended in "
                      f"{verdict.outcome}. Nothing else runs.")
                return -1
            if problems:
                print(f"\nSTOP: R7 on {qid}, run {run}, did not pass cleanly. "
                      f"No broken tool runs.")
                return -1
        print()

    print(f"=== {label}: broken tools ===")
    unexpected = 0
    for case, qid, rel, expected in BROKEN:
        verdicts = []
        for run in range(1, RUNS + 1):
            print(f"[run {run}]", end=" ")
            verdict, problems = one(case, qid, rel, expected)
            verdicts.append(verdict)
            unexpected += bool(problems)
        print(f"{case}: identical across runs {len(set(verdicts)) == 1}\n")
    return unexpected


def main() -> int:
    on_disk = _sha256(ARTEFACT)
    print(f"artefact on disk {on_disk}; A2 {ARTEFACT_SHA256}; "
          f"match {on_disk == ARTEFACT_SHA256}")
    print(f"source {SHAP_VALUES.name} {_sha256(SHAP_VALUES)}\n")
    if on_disk != ARTEFACT_SHA256:
        print("STOP: the artefact on disk is not the one recorded in A2.")
        return 2

    mocks = _phase("In process", _one_in_process, a1_live=False)
    if mocks != 0:
        print(f"STOP: in process gave {'a stop' if mocks < 0 else f'{mocks} unexpected run(s)'}. "
              f"The sandbox was not run.")
        return 2
    sandbox = _phase("Sandbox", _one_in_container, a1_live=True)
    if sandbox < 0:
        return 2
    print(f"{sandbox} unexpected broken-tool run(s) in the sandbox.")
    return 1 if sandbox else 0


if __name__ == "__main__":
    sys.exit(main())
