"""Check that each stale module copy under verify/stale/ is still the file it
says it is.

Part 6 of verify/_verify_verdict.html loads these copies to stand in for a
visitor's out-of-date cache. A copy that drifted would make Part 6 pass
against something no visitor ever had. Each copy's first line names its
source, and everything after that line must equal
`git show <commit>:<path>` byte for byte.

    python3 -m scripts.check_stale_copies
"""
from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
HEADER = re.compile(r"\A// Stale copy of (\S+) at ([0-9a-f]{7,40})\. [^\n]*\n")


def main() -> int:
    copies = sorted((ROOT / "verify" / "stale").glob("*.js"))
    if not copies:
        print("no stale copies found under verify/stale/")
        return 1
    bad = 0
    for copy in copies:
        data = copy.read_bytes()
        m = HEADER.match(data.decode("utf-8"))
        name = copy.relative_to(ROOT)
        if not m:
            print(f"FAIL {name}: first line does not name its source")
            bad += 1
            continue
        path, commit = m.group(1), m.group(2)
        source = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT,
                                capture_output=True, check=False)
        if source.returncode != 0:
            print(f"FAIL {name}: git show {commit}:{path} failed")
            bad += 1
            continue
        body = data[len(m.group(0).encode("utf-8")):]
        same = body == source.stdout
        print(f"{'ok  ' if same else 'FAIL'} {name} = {commit}:{path} ({len(body)} bytes)")
        bad += not same
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
