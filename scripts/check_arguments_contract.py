"""Check for PREREGISTRATION_PHASE3.md amendment A4: the arguments file.

On the host, no tool involved: H1, the harness refuses to overwrite an
arguments file. Pass rule, on each of three runs: in a fresh directory,
write_arguments writes one set of arguments, then a second call with
different arguments for the same path raises RuntimeError, and the file's
bytes afterwards are exactly the bytes of the first write.

In process: R1-R6 with no arguments, then P1 with arguments. In the
container: R1-R6 first, and if any of them does not pass on all three runs,
nothing else runs. Then P1, then N18. Every case runs three times. Nothing
is retried or adjusted.

P1 answers no question, so it is judged on the raw observation: exit 0 and
stdout exactly the arguments plus the SHA-256 of the bytes the harness
wrote. N18 is classified under K1 like the Phase 3 escape fixtures.

No API request is made.

    .venv/bin/python -m scripts.check_arguments_contract
"""

import hashlib
import json
import sys
import tempfile
from pathlib import Path

from layer3.sandbox import IMAGE, run_in_container
from layer3.validator import (ARGUMENTS_FILE, classify, run_in_process,
                              write_arguments)

TOOLS = Path(__file__).resolve().parent.parent / "layer3" / "tools"
RUNS = 3
MIB = 1024 * 1024

ARGUMENTS = {"feature": "loan_amnt", "top_n": 3}
ARGUMENTS_SHA256 = hashlib.sha256(
    json.dumps(ARGUMENTS).encode("utf-8")).hexdigest()
P1_EXPECTED = {"arguments": ARGUMENTS, "sha256": ARGUMENTS_SHA256}

REFERENCE = [
    ("R1", "K1", "reference/r1_train_rows.py"),
    ("R2", "K2", "reference/r2_feature_count.py"),
    ("R3", "K3", "reference/r3_train_mean.py"),
    ("R4", "K4", "reference/r4_ablation_delta.py"),
    ("R5", "K5", "reference/r5_shap_ranks.py"),
    ("R6", "K6", "reference/r6_best_trial.py"),
]
P1 = TOOLS / "contract" / "p1_read_arguments.py"
N18 = TOOLS / "broken" / "n18_write_arguments.py"

# Section 4 of PREREGISTRATION_PHASE3.md, as the container must still be.
CONTAINER = {
    "network_mode": "none",
    "readonly_rootfs": True,
    "memory_bytes": 512 * MIB,
    "memory_swap_bytes": 512 * MIB,
    "mounts": [("/inputs", False), ("/tool/tool.py", False)],
    "image": IMAGE,
}


def _mib(n):
    return "n/a" if n is None else f"{n / MIB:.1f} MiB"


def _p1_problem(obs) -> str | None:
    if obs.timed_out or obs.oom_killed or obs.exit_code != 0:
        return (f"exit {obs.exit_code}, timed out {obs.timed_out}, "
                f"OOMKilled {obs.oom_killed}, {obs.exception}")
    try:
        output = json.loads(obs.stdout.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        return f"stdout is not JSON: {exc}"
    if output != P1_EXPECTED:
        return f"stdout is {output!r}, expected {P1_EXPECTED!r}"
    return None


def _container_problems(result) -> list[str]:
    problems = []
    config = dict(result.container)
    config["mounts"] = [tuple(m) for m in config["mounts"]]
    for key, expected in CONTAINER.items():
        if config.get(key) != expected:
            problems.append(f"container {key} is {config.get(key)!r}, "
                            f"expected {expected!r}")
    changed = [k for k, same in result.host_unchanged.items() if not same]
    if changed:
        problems.append(f"host state changed: {changed}")
    return problems


def _harness_line(result):
    changed = [k for k, same in result.host_unchanged.items() if not same]
    print(f"  harness: wall {result.harness_wall_s:.3f} s, exit "
          f"{result.exit_code}, killed by harness {result.killed_by_harness}, "
          f"OOMKilled {result.oom_killed}, peak "
          f"{_mib(result.memory_peak_bytes)}, host state unchanged "
          f"{not changed}, inputs hashed {sorted(k for k in result.host_unchanged if k.startswith('input '))}")


def host_side() -> int:
    """H1: a second write to the same arguments file is refused."""
    failures = 0
    second = {"feature": "int_rate", "top_n": 5}
    print("=== Host side: H1, no overwrite ===")
    for run in range(1, RUNS + 1):
        problems = []
        with tempfile.TemporaryDirectory(prefix="h1_") as tmp:
            dest = Path(tmp)
            write_arguments(dest, ARGUMENTS)
            first = (dest / ARGUMENTS_FILE).read_bytes()
            try:
                write_arguments(dest, second)
                refused = "no exception"
            except RuntimeError as exc:
                refused = f"RuntimeError: {exc}"
            else:
                problems.append("the second write was not refused")
            after = (dest / ARGUMENTS_FILE).read_bytes()
        if after != first:
            problems.append(f"the file's bytes changed: {after!r}")
        if hashlib.sha256(first).hexdigest() != ARGUMENTS_SHA256:
            problems.append("the first write did not produce the expected bytes")
        print(f"H1 run {run}: {'as expected' if not problems else 'UNEXPECTED'}"
              f"  second call: {refused}; bytes unchanged {after == first}")
        for p in problems:
            print(f"  UNEXPECTED: {p}")
        failures += bool(problems)
    print()
    return failures


def in_process() -> int:
    failures = 0
    print("=== In process ===")
    for case, qid, rel in REFERENCE:
        verdicts = []
        for run in range(1, RUNS + 1):
            obs = run_in_process(TOOLS / rel, qid)
            verdict = classify(qid, obs)
            verdicts.append(verdict)
            print(f"{case} {qid} run {run}: {verdict.outcome}  "
                  f"({verdict.reason})")
        ok = all(v.outcome == "pass" for v in verdicts)
        identical = len(set(verdicts)) == 1
        print(f"{case}: pass on all runs {ok}; identical {identical}\n")
        failures += not (ok and identical)

    for run in range(1, RUNS + 1):
        obs = run_in_process(P1, "K1", ARGUMENTS)
        problem = _p1_problem(obs)
        print(f"P1 K1+arguments run {run}: "
              f"{'as expected' if problem is None else 'UNEXPECTED'}  "
              f"stdout {obs.stdout.decode('utf-8', errors='replace').strip()!r}"
              + (f"  {problem}" if problem else ""))
        failures += problem is not None
    print()
    return failures


def in_container() -> int:
    failures = 0
    print("=== Container: reference tools, no arguments ===")
    for case, qid, rel in REFERENCE:
        verdicts = []
        for run in range(1, RUNS + 1):
            result = run_in_container(TOOLS / rel, qid)
            verdict = classify(qid, result.observation)
            verdicts.append(verdict)
            problems = _container_problems(result)
            if any(k == f"input {ARGUMENTS_FILE}" for k in result.host_unchanged):
                problems.append(f"{ARGUMENTS_FILE} was among the inputs")
            print(f"{case} {qid} run {run}: {verdict.outcome}  "
                  f"({verdict.reason})")
            _harness_line(result)
            if case == "R1" and run == 1:
                print(f"  harness: container {result.container}")
            for p in problems:
                print(f"  UNEXPECTED: {p}")
            failures += bool(problems)
        ok = all(v.outcome == "pass" for v in verdicts)
        identical = len(set(verdicts)) == 1
        print(f"{case}: pass on all runs {ok}; identical {identical}\n")
        failures += not (ok and identical)

    if failures:
        print(f"STOP: {failures} problem(s) with the reference tools in the "
              f"container. P1 and N18 were not run.")
        return failures

    print("=== Container: P1 reads its arguments ===")
    for run in range(1, RUNS + 1):
        result = run_in_container(P1, "K1", ARGUMENTS)
        problems = _container_problems(result)
        if f"input {ARGUMENTS_FILE}" not in result.host_unchanged:
            problems.append(f"{ARGUMENTS_FILE} was not among the hashed inputs")
        problem = _p1_problem(result.observation)
        if problem:
            problems.append(problem)
        print(f"P1 K1+arguments run {run}: "
              f"{'as expected' if not problems else 'UNEXPECTED'}  stdout "
              f"{result.observation.stdout.decode('utf-8', errors='replace').strip()!r}")
        _harness_line(result)
        for p in problems:
            print(f"  UNEXPECTED: {p}")
        failures += bool(problems)
    print()

    print("=== Container: N18 tries to change its arguments ===")
    for run in range(1, RUNS + 1):
        result = run_in_container(N18, "K1", ARGUMENTS)
        verdict = classify("K1", result.observation)
        problems = _container_problems(result)
        if f"input {ARGUMENTS_FILE}" not in result.host_unchanged:
            problems.append(f"{ARGUMENTS_FILE} was not among the hashed inputs")
        if verdict.outcome != "crashed":
            problems.append(f"outcome {verdict.outcome}, expected crashed")
        if result.observation.exception != "OSError":
            problems.append(f"exception {result.observation.exception}, "
                            f"expected OSError")
        attempts = [l for l in result.tool_stderr if l.startswith("attempt ")]
        if len(attempts) != 3 or not all("[Errno 30]" in l for l in attempts):
            problems.append("not every attempt was refused with errno 30")
        if result.observation.stdout.strip():
            problems.append("stdout is not empty")
        print(f"N18 K1+arguments run {run}: {verdict.outcome}  "
              f"({verdict.reason})")
        _harness_line(result)
        for line in attempts:
            print(f"    {line}")
        for p in problems:
            print(f"  UNEXPECTED: {p}")
        failures += bool(problems)
    print()
    return failures


def main() -> int:
    print(f"arguments {json.dumps(ARGUMENTS)}, sha256 {ARGUMENTS_SHA256}\n")
    failures = host_side()
    failures += in_process()
    failures += in_container()
    print(f"{failures} problem(s).")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
