"""Check that the published bundle was built from the published sources.

This replaces a byte-identity check. While the bundle never changed, it was
enough to fetch the live files and compare them to the repository: identical
bytes meant nothing had drifted. That test is spent the moment the bundle
legitimately changes, and it says nothing about *where* the bytes came from
— a bundle built from edited sources passes it as easily as an honest one.

What is checkable instead is the chain the bundle publishes for itself.
Both manifests record a SHA-256 for every file their contents were derived
from, the commit they were exported at, and whether the working tree was
dirty in the paths that matter. This verifies all three: every source still
hashes to what the manifest claims, the export was made from a clean tree,
and the commit it names is an ancestor of HEAD.

    .venv/bin/python -m scripts.verify_bundle_provenance

Exits non-zero if any source fails, if either export was made from a dirty
tree, or if either names a commit this branch does not contain.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BUNDLE = ROOT / "docs" / "data" / "bundle.json"
TOOLS = ROOT / "docs" / "data" / "tools" / "manifest.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _tracked(path: Path) -> bool:
    """Whether git has this file, i.e. whether a fresh clone would."""
    rel = path.relative_to(ROOT) if path.is_absolute() else path
    return subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(rel)],
        cwd=ROOT, capture_output=True).returncode == 0


def _is_ancestor(commit: str) -> bool:
    return subprocess.run(
        ["git", "merge-base", "--is-ancestor", commit, "HEAD"],
        cwd=ROOT, capture_output=True).returncode == 0


def _resolve_bundle(path: str, _manifest: dict) -> Path:
    """bundle.json records paths from the repository root, as written."""
    return ROOT / path


def _resolve_tools(path: str, manifest: dict) -> Path:
    """tools/manifest.json records the two source modules from the repository
    root, but each variant's five tables under the variant's own name —
    'layer1/shap_global.csv', not 'outputs/agent_cache/shap_global.csv'. The
    directory that prefix stands for is in the manifest's own `variants`
    block, under `cache`.

    This is the rule worth spelling out. Resolving these from the repository
    root finds nothing, and a checker that treats a missing file as a failure
    then reports ten confident FAILs against data that is perfectly sound —
    while a checker that treats missing as "skip" would pass a bundle whose
    sources had all been replaced. Neither is a provenance check. Each
    manifest is read by its own rule instead.
    """
    caches = {name: spec["cache"] for name, spec in manifest["variants"].items()}
    head, _, rest = path.partition("/")
    if head in caches:
        return ROOT / caches[head] / rest
    return ROOT / path


MANIFESTS = [
    ("docs/data/bundle.json", BUNDLE, "scoring_sources_sha256", _resolve_bundle,
     "paths from the repository root"),
    ("docs/data/tools/manifest.json", TOOLS, "source_sha256", _resolve_tools,
     "repository root for modules, variant cache for tables"),
]


def check_manifest(label, path, key, resolve, rule) -> tuple[int, list[str]]:
    """Returns (failure count, names of sources a fresh clone would lack)."""
    if not path.is_file():
        print(f"{label}: MISSING — nothing to verify.")
        return 1, []

    manifest = json.loads(path.read_text())
    print(f"{label}")
    print(f"  source hashes ({rule})")

    failures = 0
    unverifiable = []
    for source, want in manifest[key].items():
        target = resolve(source, manifest)
        if not target.is_file():
            print(f"    FAIL  {source}")
            print(f"          expected at {target.relative_to(ROOT)}, which is not there")
            failures += 1
            continue
        got = _sha256(target)
        ok = got == want
        if not ok:
            failures += 1
        shown = str(target.relative_to(ROOT))
        suffix = "" if shown == source else f"  -> {shown}"
        print(f"    {'ok  ' if ok else 'FAIL'}  {source}{suffix}")
        if not ok:
            print(f"          have {got}")
            print(f"          want {want}")
        if not _tracked(target):
            unverifiable.append(shown)

    dirty = manifest.get("uncommitted_changes_in_source_paths") or []
    commit = manifest.get("exported_from_commit", "")
    ancestor = _is_ancestor(commit) if commit else False

    print(f"  clean-tree stamp   {'clean' if not dirty else 'DIRTY: ' + ', '.join(dirty)}")
    print(f"  exported at        {commit[:12] or '(none recorded)'}"
          f"  {'(ancestor of HEAD)' if ancestor else '(NOT AN ANCESTOR OF HEAD)'}")
    if dirty:
        failures += 1
    if not ancestor:
        failures += 1
    print()
    return failures, unverifiable


def main() -> None:
    failures = 0
    unverifiable: list[str] = []
    for label, path, key, resolve, rule in MANIFESTS:
        n, u = check_manifest(label, path, key, resolve, rule)
        failures += n
        unverifiable.extend(u)

    # Said plainly rather than hidden or treated as a fault. These hash
    # correctly here and cannot be checked at all by anyone who clones the
    # repository, because the file is not in it. The bundle's own
    # scoring_note says the same thing; this repeats it where someone
    # running the check will see it.
    if unverifiable:
        print("Verified here, but not verifiable from a fresh clone:")
        for name in sorted(set(unverifiable)):
            print(f"  {name}  — not committed")
        print("  The hash above is a record of what the export read, not "
              "something a third party can reproduce.")
        print()

    if failures:
        print(f"FAILED: {failures} problem(s).")
        raise SystemExit(1)
    print("Every published source hashes to what the bundle claims, both "
          "exports were made from a clean tree, and both name a commit this "
          "branch contains.")


if __name__ == "__main__":
    main()
