"""Find a deploy that a stale copy of an old module couldn't link against.

A visitor's browser can hold a module from the last deploy for up to ten
minutes after the next one. If that old module imports a name the new build
no longer exports, it fails to link. Its stamp is never read, the modules
that did load all agree, and the scan page says it couldn't start instead of
saying its files are from different versions (see the loader's comment in
docs/scan.js). This check finds the deploy that would make that possible.
The opt-in pre-push hook in .githooks/ runs it on pushes to main. It is a
local guard, not enforcement: it runs only on a clone where the hook is turned
on, and a push can skip it (see the README).

For every `import { ... } from './x.js'` in the base version of
docs/scan-page.js and docs/agent/*.js, the new version of x.js must still
exist and still export each name. Only those files are read: docs/scan.js is
the loader, and it has no static imports.

The reader accepts only the forms these files use:
    export const NAME / export function NAME / export async function NAME /
    export class NAME
    import { a, b as c } from './x.js';   (on one line or several)
Any other line that starts with `export` or `import` fails the check, so a
form this reader doesn't know can't be misread as nothing to check.

    python3 -m scripts.check_export_diff BASE HEAD
    python3 -m scripts.check_export_diff              # origin/main against HEAD

Exit 0: every import of the base resolves in the head. Exit 1: some don't,
listed. Exit 2: a file couldn't be read, or holds a form the reader doesn't
accept.
"""
from __future__ import annotations

import posixpath
import re
import subprocess
import sys

EXPORT = re.compile(r"^export (?:async function|function|const|class) ([A-Za-z_$][\w$]*)")
IMPORT = re.compile(r"^import\s*\{([^}]*)\}\s*from\s*'([^']+)';", re.MULTILINE)
NAME = re.compile(r"^([A-Za-z_$][\w$]*)(?:\s+as\s+[A-Za-z_$][\w$]*)?$")


class Unreadable(Exception):
    pass


def git(*args: str) -> str:
    return subprocess.run(["git", *args], check=True, capture_output=True, text=True).stdout


def module_paths(rev: str) -> list[str]:
    listed = git("ls-tree", "-r", "--name-only", rev, "--", "docs/agent", "docs/scan-page.js")
    return sorted(p for p in listed.splitlines()
                  if p == "docs/scan-page.js" or (p.startswith("docs/agent/") and p.endswith(".js")))


def source(rev: str, path: str) -> str:
    return git("show", f"{rev}:{path}")


def exports(path: str, text: str) -> set[str]:
    names = set()
    for n, line in enumerate(text.splitlines(), 1):
        if not line.startswith("export"):
            continue
        m = EXPORT.match(line)
        if not m:
            raise Unreadable(f"{path}:{n}: an export form this check doesn't read: {line.strip()}")
        names.add(m.group(1))
    return names


def imports(path: str, text: str) -> list[tuple[str, str]]:
    found, covered = [], set()
    for m in IMPORT.finditer(text):
        first = text.count("\n", 0, m.start())
        covered.update(range(first, first + m.group(0).count("\n") + 1))
        target = posixpath.normpath(posixpath.join(posixpath.dirname(path), m.group(2)))
        for part in m.group(1).split(","):
            part = " ".join(part.split())
            if not part:
                continue
            nm = NAME.match(part)
            if not nm:
                raise Unreadable(f"{path}: an imported name this check doesn't read: {part}")
            found.append((target, nm.group(1)))
    for n, line in enumerate(text.splitlines()):
        if line.startswith("import") and n not in covered:
            raise Unreadable(f"{path}:{n + 1}: an import form this check doesn't read: {line.strip()}")
    return found


def check(base: str, head: str) -> list[str]:
    head_paths = set(module_paths(head))
    head_exports: dict[str, set[str]] = {}
    for p in head_paths:
        head_exports[p] = exports(p, source(head, p))
    missing = []
    for p in module_paths(base):
        for target, name in imports(p, source(base, p)):
            if target not in head_paths:
                missing.append(f"{p} (as of {base}) imports {name} from {target}, which {head} no longer has")
            elif name not in head_exports[target]:
                missing.append(f"{p} (as of {base}) imports {name} from {target}, which {head} no longer exports")
    return missing


def main(argv: list[str]) -> int:
    base, head = (argv + ["origin/main", "HEAD"][len(argv):])[:2]
    try:
        missing = check(base, head)
    except (Unreadable, subprocess.CalledProcessError) as err:
        detail = err.stderr.strip() if isinstance(err, subprocess.CalledProcessError) else str(err)
        print(f"check_export_diff: can't check {base} against {head}: {detail}", file=sys.stderr)
        return 2
    if missing:
        print(f"check_export_diff: a stale copy of the {base} build couldn't link against {head}:",
              file=sys.stderr)
        for line in missing:
            print(f"  {line}", file=sys.stderr)
        return 1
    print(f"check_export_diff: every import in {base} still resolves in {head}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
