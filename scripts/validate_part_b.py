"""Phase 3, step 2, part B: R1-R6, then N6-N14, in the sandbox.

The reference tools go first. If any of them does not pass on all three
runs, the script stops before any broken tool runs: a sandbox that refuses
everything would reject every broken tool and look like it works.

For each run it prints the verdict, then what the harness observed (wall
time on its own clock and Docker's, exit code, whether it killed the
container, OOMKilled, peak memory from the cgroup, the container's
configuration, and whether host hashes changed), then what the tool
observed, which is whatever the tool wrote to stderr. Nothing is retried
or adjusted.

    .venv/bin/python -m scripts.validate_part_b
"""

import sys
from pathlib import Path

from layer3.sandbox import TIME_LIMIT_S, run_in_container
from layer3.validator import classify

TOOLS = Path(__file__).resolve().parent.parent / "layer3" / "tools"
RUNS = 3
MIB = 1024 * 1024
MEMORY_LIMIT_BYTES = 512 * MIB

REFERENCE = [
    ("R1", "K1", "reference/r1_train_rows.py"),
    ("R2", "K2", "reference/r2_feature_count.py"),
    ("R3", "K3", "reference/r3_train_mean.py"),
    ("R4", "K4", "reference/r4_ablation_delta.py"),
    ("R5", "K5", "reference/r5_shap_ranks.py"),
    ("R6", "K6", "reference/r6_best_trial.py"),
]

# (case, question, tool, expected outcome, acceptable exception classes)
BROKEN = [
    ("N6", "K1", "broken/n6_busy_loop.py", "timeout", None),
    ("N7", "K1", "broken/n7_ignore_sigterm.py", "timeout", None),
    ("N8", "K1", "broken/n8_write_input.py", "crashed", {"OSError"}),
    ("N9", "K1", "broken/n9_write_repo.py", "crashed",
     {"OSError", "FileNotFoundError"}),
    ("N10", "K1", "broken/n10_write_tool.py", "crashed", {"OSError"}),
    ("N11", "K1", "broken/n11_network.py", "crashed", {"socket.gaierror"}),
    ("N12", "K1", "broken/n12_database.py", "crashed",
     {"socket.gaierror", "OSError"}),
    ("N13", "K1", "broken/n13_memory.py", "memory_limit", None),
    ("N14", "K5", "broken/n14_read_answer.py", "crashed",
     {"FileNotFoundError"}),
]


def _mib(n):
    return "n/a" if n is None else f"{n / MIB:.1f} MiB"


def _report(case, qid, run, result, verdict, show_container):
    obs = result.observation
    print(f"{case} {qid} run {run}: {verdict.outcome}  ({verdict.reason})")
    elapsed = ("n/a" if result.docker_elapsed_s is None
               else f"{result.docker_elapsed_s:.3f} s")
    print(f"  harness: wall {result.harness_wall_s:.3f} s, docker elapsed "
          f"{elapsed}, exit {result.exit_code}, killed by harness "
          f"{result.killed_by_harness}, OOMKilled {result.oom_killed}, "
          f"peak {_mib(result.memory_peak_bytes)}, oom_kill events "
          f"{result.oom_kill_events}, child returncode "
          f"{result.child_returncode}")
    changed = [k for k, same in result.host_unchanged.items() if not same]
    print(f"  harness: host state unchanged: {not changed}"
          + (f" CHANGED: {changed}" if changed else ""))
    if show_container:
        print(f"  harness: container {result.container}")
    stdout = obs.stdout.decode("utf-8", errors="replace").strip()
    print(f"  tool stdout: {stdout[:160]!r}{' ...' if len(stdout) > 160 else ''}")
    # Escape fixtures report each attempt on its own line and then raise, so
    # a traceback follows. Every attempt and allocation line is printed in
    # full, then the end of the traceback, so no attempt is pushed out.
    lines = result.tool_stderr
    reported = [l for l in lines if l.startswith(("attempt ", "allocated "))]
    print("  tool stderr:" + ("" if lines else " (empty)"))
    for line in reported:
        print(f"    {line}")
    tail = [l for l in lines[-6:] if l not in reported]
    if tail:
        print("    ... end of stderr:")
        for line in tail:
            print(f"    {line}")


def main() -> int:
    failures = 0
    print("=== Reference tools ===")
    for case, qid, rel in REFERENCE:
        verdicts, walls, peaks = [], [], []
        for run in range(1, RUNS + 1):
            result = run_in_container(TOOLS / rel, qid)
            verdict = classify(qid, result.observation)
            verdicts.append(verdict)
            walls.append(result.harness_wall_s)
            peaks.append(result.memory_peak_bytes)
            _report(case, qid, run, result, verdict,
                    show_container=(case == "R1" and run == 1))
        ok = all(v.outcome == "pass" for v in verdicts)
        identical = len(set(verdicts)) == 1
        near = [w for w in walls if w >= TIME_LIMIT_S / 2] + \
               [p for p in peaks if p is not None and p >= MEMORY_LIMIT_BYTES / 2]
        print(f"{case}: pass on all runs {ok}; identical {identical}; "
              f"wall max {max(walls):.3f} s; peak max "
              f"{_mib(max((p for p in peaks if p is not None), default=None))}; "
              f"within half of a limit: {bool(near)}\n")
        if not (ok and identical):
            failures += 1

    if failures:
        print(f"STOP: {failures} reference tool(s) did not pass in the "
              f"container. No broken tool was run.")
        return 2

    print("=== Broken tools ===")
    unexpected = 0
    for case, qid, rel, expected, exceptions in BROKEN:
        verdicts = []
        for run in range(1, RUNS + 1):
            result = run_in_container(TOOLS / rel, qid)
            verdict = classify(qid, result.observation)
            verdicts.append(verdict)
            _report(case, qid, run, result, verdict, show_container=False)
            good = verdict.outcome == expected
            if exceptions is not None:
                good = good and result.observation.exception in exceptions
            good = good and all(result.host_unchanged.values())
            if not good:
                unexpected += 1
                print(f"  UNEXPECTED for {case} run {run}: expected "
                      f"{expected}" + (f" with {sorted(exceptions)}"
                                       if exceptions else ""))
        print(f"{case}: identical across runs {len(set(verdicts)) == 1}\n")

    print(f"{unexpected} broken-tool run(s) unexpected.")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
