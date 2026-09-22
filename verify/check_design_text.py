"""Design pass checks 3, 4 and 6, as DESIGN_PASS.md defines them.

    python verify/check_design_text.py              # checks 3, 4 and 6
    python verify/check_design_text.py --check 6    # one check only
    python verify/check_design_text.py --tree REV   # read the files at REV
    python verify/check_design_text.py --snapshot   # rebuild check 6's snapshot

Check 3: over the six text files (the four pages and the two READMEs), no
banned phrase, at most one em-dash per paragraph outside claim sentences,
none in each README's first three lines, and no README paragraph over 360
characters with table rows left out.

Check 4: each README's first three non-blank lines hold a non-heading line
(what it is) and a code span, a code fence or a run command (how to run it).

Check 6: every sentence in the claim manifest is still in its file. Page
text is compared with runs of whitespace collapsed and tags kept; a
JavaScript string literal is compared byte for byte. Either may move
within its file.

The snapshot, verify/design_claims_62f8d3e.json, holds what check 6
compares against: each manifest entry resolved to its full source at
62f8d3e. It is built from DESIGN_PASS.md and git, and building it stops on
any entry it cannot resolve rather than guessing.

Plain Python, nothing to install. Exit status 1 if any check fails.
"""

import argparse
import html
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SPEC = ROOT / "DESIGN_PASS.md"
SNAPSHOT = ROOT / "verify" / "design_claims_62f8d3e.json"
FROZEN_AT = "62f8d3e"

PAGES = ["docs/index.html", "docs/runs.html", "docs/replay.html", "docs/scan.html"]
READMES = ["README.md", "docs/README.md"]

BANNED = ["delve", "leverage", "robust", "seamless", "dive into",
          "it's worth noting", "in today's world"]
EM = "—"
MAX_README_PARA = 360


# ---------------------------------------------------------------- reading

def read(path: str, tree: str | None) -> str:
    if tree is None:
        return (ROOT / path).read_text(encoding="utf-8")
    out = subprocess.run(["git", "show", f"{tree}:{path}"], cwd=ROOT,
                         capture_output=True, text=True)
    if out.returncode != 0:
        raise SystemExit(f"{path} is not in {tree}.")
    return out.stdout


def collapse(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def strip_tags_mapped(src: str) -> tuple[str, list[int]]:
    """Text with tags removed and whitespace collapsed, plus, for each
    character kept, its index in src. Entities are left as written."""
    out, idx = [], []
    i, n, in_space = 0, len(src), False
    while i < n:
        c = src[i]
        if c == "<":
            j = src.find(">", i)
            if j == -1:
                break
            i = j + 1
            continue
        if c.isspace():
            if out and not in_space:
                out.append(" ")
                idx.append(i)
            in_space = True
        else:
            out.append(c)
            idx.append(i)
            in_space = False
        i += 1
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


# ------------------------------------------------------------- the spec

ENTRY = re.compile(r"^(\d+)\. `([^`]+?):(\d+)(?:-(\d+))?` (.*)$")


def parse_spec() -> tuple[list[dict], list[dict]]:
    """The claim manifest (check 6) and the README claim list (check 7),
    each as the spec prints them."""
    manifest, readme_claims = [], []
    part, kind = None, None
    for line in SPEC.read_text(encoding="utf-8").splitlines():
        if line.startswith("## Claim manifest"):
            part = "manifest"
            continue
        if line.startswith("## Check 7 scope"):
            part = "readme"
            continue
        if line.startswith("### Released prose") or line.startswith("## Check 7 entries"):
            part = None
            continue
        if line.startswith("### ") and part == "manifest":
            kind = "text" if line.endswith("(page text)") else "js"
            continue
        m = ENTRY.match(line)
        if not m or part is None:
            continue
        e = {"n": int(m[1]), "file": m[2], "first": int(m[3]),
             "last": int(m[4] or m[3]), "excerpt": m[5]}
        if part == "manifest":
            e["kind"] = kind
            manifest.append(e)
        else:
            readme_claims.append(e)
    return manifest, readme_claims


# -------------------------------------------------- JavaScript literals

def js_literals(src: str, base: int = 0) -> list[tuple[int, int]]:
    """(start, end) offsets of every string and template literal, found by
    a small lexer that knows comments, regex literals and ${} nesting."""
    lits, i, n = [], 0, len(src)
    prev = ""  # last significant character, to tell a regex from a division

    def skip_template(i: int) -> int:
        # i is just past the opening backtick; returns index past the close.
        while i < n:
            c = src[i]
            if c == "\\":
                i += 2
                continue
            if c == "`":
                return i + 1
            if c == "$" and i + 1 < n and src[i + 1] == "{":
                i = skip_code(i + 2, "}")
                continue
            i += 1
        return n

    def skip_code(i: int, close: str) -> int:
        depth = 0
        while i < n:
            c = src[i]
            if c in "'\"":
                j = skip_string(i)
                lits.append((base + i, base + j))
                i = j
                continue
            if c == "`":
                j = skip_template(i + 1)
                lits.append((base + i, base + j))
                i = j
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                if depth == 0 and close == "}":
                    return i + 1
                depth -= 1
            i += 1
        return n

    def skip_string(i: int) -> int:
        q, i = src[i], i + 1
        while i < n and src[i] != q:
            if src[i] == "\\":
                i += 1
            elif src[i] == "\n":
                break
            i += 1
        return i + 1

    while i < n:
        c = src[i]
        if c == "/" and i + 1 < n and src[i + 1] == "/":
            j = src.find("\n", i)
            i = n if j == -1 else j
            continue
        if c == "/" and i + 1 < n and src[i + 1] == "*":
            j = src.find("*/", i + 2)
            i = n if j == -1 else j + 2
            continue
        if c == "/" and (prev == "" or prev in "(,=:[!&|?{};+-*%<>~^" or
                         re.search(r"\b(return|typeof|case|in|of)\s*$", src[max(0, i - 8):i])):
            j, in_class = i + 1, False
            while j < n and src[j] != "\n":
                if src[j] == "\\":
                    j += 2
                    continue
                if src[j] == "[":
                    in_class = True
                elif src[j] == "]":
                    in_class = False
                elif src[j] == "/" and not in_class:
                    break
                j += 1
            i, prev = j + 1, "x"
            continue
        if c in "'\"":
            j = skip_string(i)
            lits.append((base + i, base + j))
            i, prev = j, "x"
            continue
        if c == "`":
            j = skip_template(i + 1)
            lits.append((base + i, base + j))
            i, prev = j, "x"
            continue
        if not c.isspace():
            prev = c
        i += 1
    return lits


def script_regions(doc: str) -> list[tuple[int, int]]:
    return [(m.start(1), m.end(1)) for m in
            re.finditer(r"<script\b[^>]*>(.*?)</script>", doc, re.S | re.I)]


def literals_in_file(doc: str, path: str) -> list[tuple[int, int]]:
    if path.endswith(".js"):
        return js_literals(doc)
    out = []
    for a, b in script_regions(doc):
        out += js_literals(doc[a:b], base=a)
    return out


def line_span(doc: str, first: int, last: int) -> tuple[int, int]:
    starts = [0] + [m.end() for m in re.finditer("\n", doc)]
    a = starts[first - 1]
    b = starts[last] if last < len(starts) else len(doc)
    return a, b


# ------------------------------------------------------------- snapshot

def quotes(s: str) -> str:
    """Curly quotes as straight ones, one character for one, so offsets hold.
    Only used to find a manifest excerpt; what is stored is the source."""
    return s.translate(str.maketrans("\u2018\u2019\u201c\u201d", "''\"\""))


SENT_END = re.compile(r"[.!?][’”\"')]*(?= |$)")


def resolve_text(e: dict, doc: str) -> dict:
    a, b = line_span(doc, e["first"], e["last"])
    block = doc[a:b]
    ex = e["excerpt"]
    m = re.match(r'^meta description: "(.*)"$', ex)
    if m:
        attr = re.search(r'<meta name="description" content="([^"]*)"', block)
        if not attr or quotes(attr[1]) != quotes(m[1]):
            raise ValueError("meta description not found on its line")
        return {"unit": attr[1], "text": attr[1]}
    text, idx = strip_tags_mapped(block)
    key = collapse(ex)
    start = quotes(text).find(quotes(key))
    if start == -1:
        raise ValueError("excerpt not found in the tag-stripped lines")
    end_m = SENT_END.search(text, start + min(len(key), 1) - 1)
    end = end_m.end() if end_m else len(text)
    if end < start + len(key) and len(key) < 110:
        end = start + len(key)
    src_a, src_b = idx[start], idx[end - 1] + 1
    return {"unit": collapse(block[src_a:src_b]), "text": text[start:end]}


def resolve_js(e: dict, doc: str) -> dict:
    a, b = line_span(doc, e["first"], e["last"])
    units = [doc[s:t] for s, t in literals_in_file(doc, e["file"])
             if s < b and t > a and re.search(r"[A-Za-z]", doc[s:t])]
    if not units:
        raise ValueError("no string literal with a letter in it on these lines")
    return {"units": units}


def build_snapshot() -> None:
    manifest, _ = parse_spec()
    docs, entries, errors = {}, [], []
    for e in manifest:
        doc = docs.setdefault(e["file"], read(e["file"], FROZEN_AT))
        try:
            got = resolve_text(e, doc) if e["kind"] == "text" else resolve_js(e, doc)
        except ValueError as exc:
            errors.append(f"  entry {e['n']} {e['file']}:{e['first']}: {exc}")
            continue
        entries.append({**e, **got})
    if errors:
        print("The snapshot was not written. These entries did not resolve at "
              f"{FROZEN_AT}:\n" + "\n".join(errors))
        raise SystemExit(1)
    SNAPSHOT.write_text(json.dumps({"frozen_at": FROZEN_AT, "entries": entries},
                                   ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    units = sum(len(x.get("units", [x.get("unit")])) for x in entries)
    print(f"snapshot: {len(entries)} manifest entries, {units} units, written to "
          f"{SNAPSHOT.relative_to(ROOT)}")


# ---------------------------------------------------------------- check 6

def check6(tree: str | None) -> list[str]:
    if not SNAPSHOT.exists():
        raise SystemExit("The check 6 snapshot is missing. Build it with --snapshot.")
    snap = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    fails, docs, units = [], {}, 0
    for e in snap["entries"]:
        doc = docs.setdefault(e["file"], read(e["file"], tree))
        if e["kind"] == "text":
            units += 1
            if e["unit"] not in collapse(doc):
                fails.append(f"entry {e['n']} {e['file']}: changed or gone: "
                             f"{e['text'][:90]}")
        else:
            for u in e["units"]:
                units += 1
                if u not in doc:
                    fails.append(f"entry {e['n']} {e['file']}: literal changed or gone: "
                                 f"{collapse(u)[:90]}")
    print(f"check 6: {len(snap['entries'])} entries, {units} units compared, "
          f"{len(fails)} failing")
    return fails


# ------------------------------------------------------------ text model

BLOCK_TAGS = r"(p|li|h[1-6]|dt|dd|td|th|figcaption|summary|label|button|div|section|header|footer|main|nav|ul|ol|dl|table|tr|details|pre|blockquote|option|select|title)"


def html_paragraphs(doc: str) -> list[str]:
    doc = re.sub(r"<(script|style|head)\b.*?</\1>", " ", doc, flags=re.S | re.I)
    doc = re.sub(r"<!--.*?-->", " ", doc, flags=re.S)
    doc = re.sub(rf"</?{BLOCK_TAGS}\b[^>]*>", "\n\n", doc, flags=re.I)
    doc = re.sub(r"<[^>]+>", "", doc)
    doc = html.unescape(doc)
    return [collapse(p) for p in re.split(r"\n\s*\n", doc) if collapse(p)]


def md_paragraphs(doc: str) -> list[str]:
    """Paragraphs of a README: blank-line blocks, split again at list items,
    with code fences, headings and table rows left out."""
    doc = re.sub(r"```.*?```", "\n\n", doc, flags=re.S)
    paras = []
    for block in re.split(r"\n\s*\n", doc):
        cur = []
        for line in block.split("\n"):
            if re.match(r"\s*([-*+]|\d+\.)\s", line) and cur:
                paras.append(" ".join(cur))
                cur = []
            cur.append(line.strip())
        if cur:
            paras.append(" ".join(cur))
    return [collapse(p) for p in paras
            if collapse(p) and not p.lstrip().startswith(("|", "#"))]


def sentences(p: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+(?=[A-Z0-9*`(\"'_\[“<])", p) if s]


def claim_key(s: str) -> str:
    """Letters and digits only, lower-cased, first 50: stable across the
    punctuation-only changes check 7 allows."""
    return re.sub(r"[^a-z0-9]", "", html.unescape(re.sub(r"<[^>]+>", "", s)).lower())[:50]


def claim_keys() -> set[str]:
    manifest, readme_claims = parse_spec()
    keys = {claim_key(e["excerpt"]) for e in readme_claims}
    if SNAPSHOT.exists():
        for e in json.loads(SNAPSHOT.read_text(encoding="utf-8"))["entries"]:
            if e["kind"] == "text":
                keys.add(claim_key(e["text"]))
    return {k for k in keys if len(k) >= 12}


def is_claim(sentence: str, keys: set[str]) -> bool:
    k = claim_key(sentence)
    return any(k.startswith(c) or c.startswith(k) for c in keys if len(k) >= 12)


# ---------------------------------------------------------------- check 3

def check3(tree: str | None) -> list[str]:
    keys, fails = claim_keys(), []
    banned = [re.compile(r"\b" + re.escape(b).replace("'", "['’]") + r"\b", re.I)
              for b in BANNED]
    for path in PAGES + READMES:
        doc = read(path, tree)
        paras = md_paragraphs(doc) if path.endswith(".md") else html_paragraphs(doc)
        for p in paras:
            for rx, word in zip(banned, BANNED):
                if rx.search(p):
                    fails.append(f"{path}: banned phrase \"{word}\": {p[:90]}")
            loose = [s for s in sentences(p) if not is_claim(s, keys)]
            dashes = sum(s.count(EM) for s in loose)
            if dashes > 1:
                fails.append(f"{path}: {dashes} em-dashes outside claim sentences "
                             f"in one paragraph: {p[:90]}")
            if path in READMES and len(p) > MAX_README_PARA:
                fails.append(f"{path}: paragraph of {len(p)} characters: {p[:90]}")
        if path in READMES:
            head = [line for line in doc.splitlines() if line.strip()][:3]
            n = sum(line.count(EM) for line in head)
            if n:
                fails.append(f"{path}: {n} em-dash(es) in the first three lines")
    print(f"check 3: {len(PAGES + READMES)} files, {len(fails)} failing")
    return fails


# ---------------------------------------------------------------- check 4

RUN_COMMAND = re.compile(r"^\s*(\$ )?(python3?|pip3?|docker|npm|npx|node|git|make|uv|bash|sh)\b")


def check4(tree: str | None) -> list[str]:
    fails = []
    for path in READMES:
        head = [line for line in read(path, tree).splitlines() if line.strip()][:3]
        what = next((line for line in head if not line.lstrip().startswith("#")), None)
        how = any("`" in line or line.lstrip().startswith("```") or RUN_COMMAND.match(line)
                  for line in head)
        if not what:
            fails.append(f"{path}: no non-heading line in the first three")
        if not how:
            fails.append(f"{path}: no code span, code fence or run command in the "
                         "first three lines")
    print(f"check 4: {len(READMES)} files, {len(fails)} failing")
    return fails


# ------------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--check", type=int, choices=[3, 4, 6])
    ap.add_argument("--tree", help="read the in-scope files at this commit")
    ap.add_argument("--snapshot", action="store_true",
                    help=f"rebuild check 6's snapshot from {FROZEN_AT}")
    args = ap.parse_args()
    if args.snapshot:
        build_snapshot()
        return 0
    runs = {3: check3, 4: check4, 6: check6}
    wanted = [args.check] if args.check else [3, 4, 6]
    failed = False
    for n in wanted:
        fails = runs[n](args.tree)
        for f in fails:
            print("  FAIL " + f)
        print(f"  check {n}: {'FAIL' if fails else 'PASS'}\n")
        failed |= bool(fails)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
