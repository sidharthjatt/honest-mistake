"""Stamp every module the scan page runs with one build stamp.

The stamp lets docs/scan.js refuse a page whose modules come from different
builds. It is a short hash of the whole set, so a change to any one module
changes the stamp in all of them. Each file's own stamp line is blanked
before hashing, so a stamp never hashes itself.

The set is docs/scan.js (the loader), docs/scan-page.js and every .js file
under docs/agent/. Each file's first line is its stamp:

    export const BUILD = '<12 hex characters>';

A file without one gets one. The loader's MODULES list is written here too,
so a module added under docs/agent/ can't be left out of the check.

Every new file is computed before any is written. --check writes nothing and
exits 1 if any file differs from what this would write: a stale stamp, a
missing one, or a stale list. It runs in the pre-push gate.

This is its own step on purpose. scripts/export_site_bundle.py writes
docs/data/ and carries provenance hashes; nothing here touches either.

    python3 -m scripts.stamp_modules          # write
    python3 -m scripts.stamp_modules --check  # verify only
"""
from __future__ import annotations

import hashlib
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
LOADER = DOCS / "scan.js"
PAGE = DOCS / "scan-page.js"

STAMP_LINE = re.compile(r"\Aexport const BUILD = '([0-9a-f]{12})?';\n")
MODULES_BLOCK = re.compile(r"^const MODULES = \[[^\]]*\];$", re.MULTILINE)


def module_set() -> list[Path]:
    return [LOADER, PAGE, *sorted((DOCS / "agent").glob("*.js"))]


def stamp_line(value: str) -> str:
    return f"export const BUILD = '{value}';\n"


def body_of(text: str) -> str:
    """The file without its stamp line, whether or not it has one."""
    m = STAMP_LINE.match(text)
    return text[m.end():] if m else text


def modules_block(paths: list[Path]) -> str:
    rel = [f"'./{p.relative_to(DOCS).as_posix()}'" for p in paths if p != LOADER]
    return "const MODULES = [\n" + "".join(f"  {r},\n" for r in rel) + "];"


def desired() -> tuple[dict[Path, str], str]:
    paths = module_set()
    bodies = {p: body_of(p.read_text(encoding="utf-8")) for p in paths}

    found = MODULES_BLOCK.findall(bodies[LOADER])
    if len(found) != 1:
        sys.exit(f"{LOADER.relative_to(ROOT)} must hold exactly one MODULES list; found {len(found)}.")
    bodies[LOADER] = MODULES_BLOCK.sub(lambda _: modules_block(paths), bodies[LOADER])

    digest = hashlib.sha256()
    for p in paths:
        digest.update(p.relative_to(ROOT).as_posix().encode() + b"\0")
        digest.update((stamp_line("") + bodies[p]).encode("utf-8") + b"\0")
    stamp = digest.hexdigest()[:12]
    return {p: stamp_line(stamp) + bodies[p] for p in paths}, stamp


def main(argv: list[str]) -> int:
    check = "--check" in argv
    files, stamp = desired()
    stale = [p for p, text in files.items() if p.read_text(encoding="utf-8") != text]
    if check:
        if stale:
            for p in stale:
                print(f"stale: {p.relative_to(ROOT)}")
            print(f"{len(stale)} of {len(files)} files are not stamped with {stamp}. "
                  "Run python3 -m scripts.stamp_modules.")
            return 1
        print(f"all {len(files)} files carry {stamp}, and MODULES lists all {len(files) - 1} modules")
        return 0
    for p in stale:
        p.write_text(files[p], encoding="utf-8")
    print(f"stamp {stamp}: wrote {len(stale)} of {len(files)} files")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
