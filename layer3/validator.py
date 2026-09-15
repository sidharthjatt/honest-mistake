"""Decide a tool's outcome from what was observed while it ran.

The outcome is one of six classes, taken in the order PREREGISTRATION_PHASE3.md
fixes: timeout, memory_limit, crashed, bad_output, wrong_answer, pass. Where
more than one applies, the first is recorded.

classify() looks only at an Observation: exit code, whether the runner
killed the tool for time or memory, and the bytes on stdout. It never reads
anything the tool says about itself. The runner that produced the
Observation is kept apart from the decision, so the same classification
serves the in-process runner here and the container runner later.
"""

from __future__ import annotations

import contextlib
import hashlib
import io
import json
import os
import runpy
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

from layer3.questions import QUESTIONS, BadShape

MAX_STDOUT_BYTES = 1024 * 1024

# Tools read their inputs from this directory. In the container it is
# unset and tools fall back to /inputs, which is where the mount goes.
INPUTS_ENV = "TOOL_INPUTS"

# A tool that takes arguments reads them from this file among its inputs
# (PREREGISTRATION_PHASE3.md, amendment A4). Questions K1 to K6 take none,
# and for them the file is never written.
ARGUMENTS_FILE = "arguments.json"

OUTCOMES = ("timeout", "memory_limit", "crashed", "bad_output",
            "wrong_answer", "pass")


@dataclass(frozen=True)
class Observation:
    exit_code: int
    stdout: bytes
    timed_out: bool = False
    oom_killed: bool = False
    exception: str | None = None
    elapsed_s: float = 0.0


@dataclass(frozen=True)
class Verdict:
    outcome: str
    reason: str


def _reject_constant(name: str):
    raise ValueError(f"non-finite number {name}")


def classify(qid: str, obs: Observation) -> Verdict:
    """The outcome for one execution. AnswerSourceError is not caught: if the
    answer cannot be read, there is no verdict to give."""
    question = QUESTIONS[qid]

    if obs.timed_out:
        return Verdict("timeout", f"killed at the time limit after "
                                  f"{obs.elapsed_s:.1f} s")
    if obs.oom_killed:
        return Verdict("memory_limit", "killed for exceeding the memory limit")
    if obs.exit_code != 0:
        detail = f", {obs.exception}" if obs.exception else ""
        return Verdict("crashed", f"exit code {obs.exit_code}{detail}")

    if not obs.stdout.strip():
        return Verdict("bad_output", "stdout is empty")
    if len(obs.stdout) > MAX_STDOUT_BYTES:
        return Verdict("bad_output", f"stdout is {len(obs.stdout):,} bytes, "
                                     f"over the 1 MiB limit")
    try:
        output = json.loads(obs.stdout.decode("utf-8"),
                            parse_constant=_reject_constant)
    except (UnicodeDecodeError, ValueError) as exc:
        return Verdict("bad_output", f"stdout is not one JSON object: {exc}")
    if not isinstance(output, dict):
        kind = "number" if isinstance(output, (int, float)) else \
            type(output).__name__
        return Verdict("bad_output", f"stdout is a JSON {kind}, not an object")

    answer = question.answer()
    try:
        question.check_shape(output, answer)
    except BadShape as exc:
        return Verdict("bad_output", str(exc))

    misses = question.compare(output, answer)
    if misses:
        return Verdict("wrong_answer", "; ".join(misses))
    return Verdict("pass", "every item matches")


def write_arguments(dest: Path, arguments: dict | None) -> None:
    """Write the arguments file after a question's inputs are prepared.

    Nothing is written when there are no arguments. A question whose own
    inputs already hold a file of that name is refused, not overwritten.
    """
    if arguments is None:
        return
    path = dest / ARGUMENTS_FILE
    if path.exists():
        raise RuntimeError(f"the inputs already hold {ARGUMENTS_FILE}; it is "
                           f"not overwritten.")
    path.write_bytes(json.dumps(arguments).encode("utf-8"))


def input_hashes(dest: Path) -> dict:
    """SHA-256 of every file among a run's inputs, by file name."""
    hashes = {}
    for path in sorted(dest.iterdir()):
        digest = hashlib.sha256()
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                digest.update(chunk)
        hashes[path.name] = digest.hexdigest()
    return hashes


def run_in_process(tool: Path, qid: str, arguments: dict | None = None,
                   hashes: dict | None = None) -> Observation:
    """Run a tool inside this interpreter, with no isolation at all.

    Only for tools that attempt no escape. Nothing is refused and no time or
    memory limit is enforced, so a tool run this way can do anything this
    process can. Tools marked SANDBOX_ONLY attempt an escape and are refused
    here, so one can never run against the real repository by mistake.
    """
    if "SANDBOX_ONLY = True" in tool.read_text():
        raise RuntimeError(f"{tool.name} attempts an escape and runs only in "
                           f"the sandbox.")
    question = QUESTIONS[qid]
    buffer = io.StringIO()
    exit_code, exception = 0, None
    previous = os.environ.get(INPUTS_ENV)

    with tempfile.TemporaryDirectory(prefix=f"{qid}_inputs_") as tmp:
        question.prepare(Path(tmp))
        write_arguments(Path(tmp), arguments)
        if hashes is not None:
            hashes["before"] = input_hashes(Path(tmp))
        os.environ[INPUTS_ENV] = tmp
        start = time.monotonic()
        try:
            with contextlib.redirect_stdout(buffer):
                runpy.run_path(str(tool), run_name="__main__")
        except SystemExit as exc:
            code = exc.code
            exit_code = 0 if code is None else (code if isinstance(code, int)
                                                else 1)
        except Exception as exc:
            exit_code, exception = 1, type(exc).__name__
        finally:
            elapsed = time.monotonic() - start
            if previous is None:
                os.environ.pop(INPUTS_ENV, None)
            else:
                os.environ[INPUTS_ENV] = previous
        if hashes is not None:
            hashes["after"] = input_hashes(Path(tmp))

    return Observation(exit_code=exit_code,
                       stdout=buffer.getvalue().encode("utf-8"),
                       exception=exception, elapsed_s=elapsed)
