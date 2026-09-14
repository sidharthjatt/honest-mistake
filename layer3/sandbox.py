"""Run one tool in a container and record what was observed.

The container is the one PREREGISTRATION_PHASE3.md fixes, on the image
pinned in amendment A2: no network, a read-only root filesystem, the tool
and its inputs mounted read-only, a 64 MiB tmpfs at /tmp, 512 MiB of
memory with no swap, and nothing else from the host.

PID 1 in the container is a few lines of Python passed on the command
line, not a mounted file, so the mounts stay exactly as specified. It runs
`python /tool/tool.py` as a child. Once the child has exited, it reads the
container's cgroup memory.peak and memory.events and writes them to stderr
as one marked line. The child's stdout is its own and is never touched.

That marked line is used for measurement only. Outcomes come from what
Docker reports, the harness's own clock, and hashes taken on the host. The
peak includes PID 1's own interpreter and any page cache the tool causes,
so it overstates what the tool itself allocated.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from layer3.questions import QUESTIONS, ROOT
from layer3.validator import Observation

# The derived image from amendment A2: the A1 base plus numpy, pandas and
# pyarrow at the versions in requirements.txt. A local image ID, not a
# registry digest; a rebuild gives a new ID and needs a new amendment.
IMAGE = "sha256:801f6454116549ae4369be7d1ed8e64c3b2143e255931c0c67bc312de67450f6"
TIME_LIMIT_S = 30.0
MEMORY_LIMIT = "512m"
TMPFS = "/tmp:rw,size=64m"
MARKER = "@@HARNESS@@"
LEDGER = ROOT / "outputs" / "ledger" / "layer3_spend.jsonl"

_PID1 = """\
import json, subprocess, sys
child = subprocess.run([sys.executable, "/tool/tool.py"])
record = {"child_returncode": child.returncode}
try:
    with open("/sys/fs/cgroup/memory.peak") as fh:
        record["memory_peak_bytes"] = int(fh.read())
except (OSError, ValueError):
    record["memory_peak_bytes"] = None
try:
    with open("/sys/fs/cgroup/memory.events") as fh:
        record["oom_kill"] = int(dict(l.split() for l in fh).get("oom_kill", -1))
except (OSError, ValueError):
    record["oom_kill"] = None
sys.stderr.write("\\n@@HARNESS@@ " + json.dumps(record) + "\\n")
sys.stderr.flush()
code = child.returncode
sys.exit(code if code >= 0 else 128 - code)
"""


@dataclass
class SandboxRun:
    observation: Observation
    harness_wall_s: float
    docker_elapsed_s: float | None
    killed_by_harness: bool
    exit_code: int
    oom_killed: bool
    memory_peak_bytes: int | None
    oom_kill_events: int | None
    child_returncode: int | None
    tool_stderr: list[str]
    container: dict
    host_unchanged: dict


def _docker(*args, timeout=None, check=True) -> subprocess.CompletedProcess:
    return subprocess.run(["docker", *args], capture_output=True,
                          timeout=timeout, check=check)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _host_state(tool: Path, inputs: Path) -> dict:
    state = {f"input {p.name}": _sha256(p) for p in sorted(inputs.iterdir())}
    state["tool file"] = _sha256(tool)
    state["ledger"] = _sha256(LEDGER)
    state["git status"] = subprocess.run(
        ["git", "status", "--porcelain"], cwd=ROOT, capture_output=True,
        text=True, check=True).stdout
    return state


def _timestamp(text: str) -> datetime:
    # Docker gives nanoseconds; datetime takes six digits.
    head, _, frac = text.rstrip("Z").partition(".")
    return datetime.fromisoformat(f"{head}.{(frac + '000000')[:6]}")


def _exception_name(lines: list[str]) -> str | None:
    """The class on a traceback's last line, if the tool printed one."""
    if not any(l.startswith("Traceback (most recent call last):")
               for l in lines):
        return None
    for line in reversed(lines):
        match = re.match(r"^([A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(?::\s|$)", line)
        if match:
            return match.group(1)
    return None


def run_in_container(tool: Path, qid: str) -> SandboxRun:
    question = QUESTIONS[qid]
    name = f"hm-sandbox-{uuid.uuid4().hex[:12]}"

    with tempfile.TemporaryDirectory(prefix=f"{qid}_inputs_") as tmp:
        inputs = Path(tmp)
        question.prepare(inputs)
        before = _host_state(tool, inputs)

        # Escape fixtures are told where the repository sits on the host,
        # so they can try to reach it by absolute path without that path
        # being written into their source. Other tools are not told.
        env = []
        if "SANDBOX_ONLY = True" in tool.read_text():
            env = ["--env", f"HOST_REPO_ROOT={ROOT}"]

        _docker("create", "--name", name, *env,
                "--network", "none",
                "--read-only",
                "--tmpfs", TMPFS,
                "--memory", MEMORY_LIMIT, "--memory-swap", MEMORY_LIMIT,
                "--workdir", "/",
                "--mount", f"type=bind,source={tool.resolve()},"
                           f"target=/tool/tool.py,readonly",
                "--mount", f"type=bind,source={inputs.resolve()},"
                           f"target=/inputs,readonly",
                IMAGE, "python", "-c", _PID1)
        killed = False
        try:
            start = time.monotonic()
            _docker("start", name)
            try:
                remaining = TIME_LIMIT_S - (time.monotonic() - start)
                _docker("wait", name, timeout=max(remaining, 0.0))
            except subprocess.TimeoutExpired:
                killed = True
                _docker("kill", name, check=False)
                _docker("wait", name, check=False, timeout=60)
            wall = time.monotonic() - start
            info = json.loads(_docker("inspect", name).stdout)[0]
            logs = _docker("logs", name)
        finally:
            _docker("rm", "-f", name, check=False)

        after = _host_state(tool, inputs)

    state, host = info["State"], info["HostConfig"]
    try:
        elapsed = (_timestamp(state["FinishedAt"])
                   - _timestamp(state["StartedAt"])).total_seconds()
    except ValueError:
        elapsed = None

    record, tool_stderr = {}, []
    for line in logs.stderr.decode("utf-8", errors="replace").splitlines():
        if line.startswith(MARKER + " "):
            record = json.loads(line[len(MARKER) + 1:])
        else:
            tool_stderr.append(line)
    while tool_stderr and not tool_stderr[-1].strip():
        tool_stderr.pop()

    observation = Observation(
        exit_code=state["ExitCode"],
        stdout=logs.stdout,
        timed_out=killed,
        oom_killed=bool(state["OOMKilled"]),
        exception=_exception_name(tool_stderr),
        elapsed_s=wall,
    )
    container = {
        "network_mode": host["NetworkMode"],
        "networks": sorted((info["NetworkSettings"].get("Networks") or {})),
        "readonly_rootfs": host["ReadonlyRootfs"],
        "memory_bytes": host["Memory"],
        "memory_swap_bytes": host["MemorySwap"],
        "tmpfs": host.get("Tmpfs"),
        "mounts": sorted((m["Destination"], m["RW"]) for m in info["Mounts"]),
        "image": info["Image"],
    }
    return SandboxRun(
        observation=observation,
        harness_wall_s=wall,
        docker_elapsed_s=elapsed,
        killed_by_harness=killed,
        exit_code=state["ExitCode"],
        oom_killed=bool(state["OOMKilled"]),
        memory_peak_bytes=record.get("memory_peak_bytes"),
        oom_kill_events=record.get("oom_kill"),
        child_returncode=record.get("child_returncode"),
        tool_stderr=tool_stderr,
        container=container,
        host_unchanged={k: before[k] == after[k] for k in before},
    )
