"""Generate the expected parse results the JavaScript port must reproduce.

Writes verify/parse_cases.json. Each case is a final-answer text with the
ParseResult agent/eval_canary.parse_final_answer produced for it: the
records, the warnings verbatim, explicit_no_findings, block_found, the
derived flags, and is_scoreable.

The real cases are the twelve recorded runs' own final answers, read from
the exported bundle. Eight carry a findings block and four do not, so both
branches of is_scoreable are covered by actual model output rather than by
something written to pass.

The synthetic cases cover what the twelve never produced: absent and
repeated markers, an unclosed block, an empty block, NO FINDINGS in each
form the parser does and does not accept, missing and duplicated and
misordered fields, stray lines, malformed separators, text after the end
marker, an undocumented FLAG, and a bad CONFIDENCE value.

    .venv/bin/python -m scripts.verify_js_parse
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.eval_canary import parse_final_answer  # noqa: E402
from agent.prompts import (ANSWER_END, ANSWER_START,  # noqa: E402
                           NO_FINDINGS_MARKER, RECORD_SEPARATOR)
from scripts.verify_js_tools import _check_pinned_versions  # noqa: E402

OUT = ROOT / "verify" / "parse_cases.json"
RUNS = ROOT / "docs" / "data" / "runs"

S, E, SEP, NF = ANSWER_START, ANSWER_END, RECORD_SEPARATOR, NO_FINDINGS_MARKER


def _record(flag="recoveries", reason="r", evidence="e", confidence="high"):
    return (f"FLAG: {flag}\nREASON: {reason}\n"
            f"EVIDENCE: {evidence}\nCONFIDENCE: {confidence}")


def _synthetic() -> list[tuple[str, str]]:
    """(name, text) for the paths the recorded runs never take."""
    one = _record()
    return [
        # Markers.
        ("no markers at all", "I looked at the model and found nothing."),
        ("start marker only", f"prose\n{S}\n{one}"),
        ("end marker only", f"prose\n{one}\n{E}"),
        ("markers in the wrong order", f"{E}\n{one}\n{S}"),
        ("repeated start marker", f"{S}\n{one}\n{S}\n{one}\n{E}"),
        ("repeated end marker", f"{S}\n{one}\n{E}\ntail\n{E}"),
        ("repeated both", f"{S}\n{one}\n{S}\n{E}\n{E}"),

        # NO FINDINGS, in the accepted form and in forms that are not.
        ("no findings, exact", f"{S}\n{NF}\n{E}"),
        ("no findings, no surrounding newlines", f"{S}{NF}{E}"),
        ("no findings, lowercase", f"{S}\nno findings\n{E}"),
        ("no findings with trailing prose", f"{S}\n{NF}\nand nothing else\n{E}"),
        ("no findings plus a record", f"{S}\n{NF}\n{SEP}\n{one}\n{E}"),

        # Empty and whitespace-only blocks.
        ("empty block", f"{S}\n{E}"),
        ("whitespace-only block", f"{S}\n   \n\t\n{E}"),

        # Separators.
        ("leading separator", f"{S}\n{SEP}\n{one}\n{E}"),
        ("trailing separator", f"{S}\n{one}\n{SEP}\n{E}"),
        ("doubled separator", f"{S}\n{one}\n{SEP}\n{SEP}\n{one}\n{E}"),
        ("separator with text on its line", f"{S}\n{one}\n{SEP} and more\n{one}\n{E}"),
        ("two good records", f"{S}\n{one}\n{SEP}\n{_record(flag='term')}\n{E}"),

        # Fields.
        ("missing CONFIDENCE",
         f"{S}\nFLAG: recoveries\nREASON: r\nEVIDENCE: e\n{E}"),
        ("missing REASON and EVIDENCE",
         f"{S}\nFLAG: recoveries\nCONFIDENCE: high\n{E}"),
        ("no FLAG at all",
         f"{S}\nREASON: r\nEVIDENCE: e\nCONFIDENCE: high\n{E}"),
        ("empty FLAG value",
         f"{S}\nFLAG:\nREASON: r\nEVIDENCE: e\nCONFIDENCE: high\n{E}"),
        ("duplicate FLAG",
         f"{S}\nFLAG: recoveries\nFLAG: term\nREASON: r\n"
         f"EVIDENCE: e\nCONFIDENCE: high\n{E}"),
        ("fields out of order",
         f"{S}\nREASON: r\nFLAG: recoveries\nEVIDENCE: e\nCONFIDENCE: high\n{E}"),
        ("stray lines among the fields",
         f"{S}\nHere is my finding.\n{one}\nThat is all.\n{E}"),
        ("field with no colon",
         f"{S}\nFLAG recoveries\nREASON: r\nEVIDENCE: e\nCONFIDENCE: high\n{E}"),
        ("colon inside the value",
         f"{S}\nFLAG: recoveries\nREASON: because: it leaks\n"
         f"EVIDENCE: e\nCONFIDENCE: high\n{E}"),
        ("lowercase field names",
         f"{S}\nflag: recoveries\nreason: r\nevidence: e\nconfidence: high\n{E}"),
        ("extra whitespace around fields",
         f"{S}\n   FLAG:   recoveries   \n  REASON:  r \n"
         f" EVIDENCE: e \n CONFIDENCE:  high  \n{E}"),

        # Values.
        ("undocumented FLAG", _wrap(_record(flag="not_a_real_column"))),
        ("FLAG with surrounding quotes", _wrap(_record(flag='"recoveries"'))),
        ("bad CONFIDENCE", _wrap(_record(confidence="very high"))),
        ("empty CONFIDENCE", _wrap(_record(confidence=""))),
        ("CONFIDENCE in capitals", _wrap(_record(confidence="HIGH"))),

        # Trailing text.
        ("text after the end marker", f"{S}\n{one}\n{E}\nI hope that helps."),
        ("long text after the end marker",
         f"{S}\n{one}\n{E}\n" + "word " * 40),
        ("whitespace after the end marker", f"{S}\n{one}\n{E}\n   \n\t"),

        # Line endings and empties.
        ("CRLF line endings", _wrap(one).replace("\n", "\r\n")),
        ("empty string", ""),
        ("whitespace only", "   \n\t  \n"),
    ]


def _wrap(body: str) -> str:
    return f"{S}\n{body}\n{E}"


def _recorded() -> list[tuple[str, str]]:
    """Every recorded run's final answer, from the exported bundle."""
    if not RUNS.is_dir():
        raise SystemExit(
            f"{RUNS.relative_to(ROOT)} is missing. Run "
            f"scripts/export_site_bundle first; the recorded cases are read "
            f"from the published bundle so the harness tests what the browser "
            f"is actually given.")
    out = []
    for path in sorted(RUNS.glob("*.json")):
        if path.name == "index.json":
            continue
        run = json.loads(path.read_text())
        text = run.get("final_answer_text")
        if text is None:
            continue
        out.append((f"recorded: {run['label']}", text))
    if not out:
        raise SystemExit("No recorded final answers found in the bundle.")
    return out


def _as_dict(result) -> dict:
    return {
        "records": result.records,
        "warnings": result.warnings,
        "explicit_no_findings": result.explicit_no_findings,
        "block_found": result.block_found,
        "flags": result.flags,
        "is_scoreable": result.is_scoreable,
    }


def main() -> None:
    _check_pinned_versions("parse_cases.json")

    synthetic = _synthetic()
    recorded = _recorded()

    cases = []
    for name, text in synthetic + recorded:
        cases.append({
            "name": name,
            "text": text,
            "result": _as_dict(parse_final_answer(text)),
        })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"generated_by": "scripts/verify_js_parse.py",
         "case_count": len(cases),
         "synthetic_count": len(synthetic),
         "recorded_count": len(recorded),
         "cases": cases}, indent=1, ensure_ascii=False, allow_nan=False) + "\n")

    scoreable = sum(1 for c in cases if c["result"]["is_scoreable"])
    print(f"wrote {len(cases)} cases to {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size:,} bytes)")
    print(f"  {len(recorded)} recorded, {len(synthetic)} synthetic")
    print(f"  scoreable: {scoreable}, not scoreable: {len(cases) - scoreable}")


if __name__ == "__main__":
    main()
