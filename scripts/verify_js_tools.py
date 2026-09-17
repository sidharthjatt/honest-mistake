"""Generate the expected tool outputs the JavaScript port must reproduce.

Writes verify/cases.json. Each case is a dispatch call under a named
configuration, with the result agent/tools.py returned and the exact bytes
agent/agent.py would have sent to the model for it.

The harnesses in verify/ run the same cases through docs/agent/tools.js and
compare both. They live outside docs/ so that nothing used for checking the
port is ever published with the site. Serve the repository root and open
verify/_verify_tools.html. Nothing here touches the network.

    .venv/bin/python -m scripts.verify_js_tools

The interpreter is not a formality, and _check_pinned_versions below
enforces it. See its docstring for why.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.tools import ToolLayer  # noqa: E402

OUT = ROOT / "verify" / "cases.json"
REQUIREMENTS = ROOT / "requirements.txt"

# The libraries whose version changes the numbers. Read from
# requirements.txt at run time rather than written out here, so that
# repinning cannot leave this check asserting a version the repo no longer
# claims.
VERSION_CRITICAL = ("numpy", "pandas")

VARIANTS = {"layer1": ROOT / "outputs" / "agent_cache",
            "canary": ROOT / "outputs" / "agent_cache_canary"}

SWITCHES = [
    ("populated+scopes", True, True),
    ("nopop+scopes", False, True),
    ("populated+splitonly", True, False),
    ("nopop+splitonly", False, False),
]

# Chosen to hit every branch that returns something different: a top-ranked
# feature, a missingness twin, one constant on test, one outside the
# ablation set, a column the dictionary documents but the model never
# reads, an unknown name, and the argument errors dispatch handles itself.
CASES = [
    ("lookup_feature", {"feature": "recoveries"}),
    ("lookup_feature", {"feature": "revol_util"}),
    ("lookup_feature", {"feature": "total_pymnt"}),
    ("lookup_feature", {"feature": "no_such_column"}),
    ("lookup_feature", {"feature": "   "}),
    ("search_data_dictionary", {"query": "balance"}),
    ("search_data_dictionary", {"query": "hardship"}),
    ("search_data_dictionary", {"query": "zzzznope"}),
    ("search_data_dictionary", {"query": "util"}),
    ("get_shap_ranking", {"top_n": 5}),
    ("get_shap_ranking", {"top_n": 10000}),
    ("get_shap_ranking", {"top_n": 0}),
    ("get_shap_ranking", {"top_n": "not a number"}),
    ("get_feature_shap_detail", {"feature": "term"}),
    ("get_feature_shap_detail", {"feature": "all_util_was_missing"}),
    ("get_feature_shap_detail", {"feature": "recoveries"}),
    ("get_feature_shap_detail", {"feature": "loan_status"}),
    ("get_ablation_result", {"feature": "term"}),
    ("get_ablation_result", {"feature": "recoveries"}),
    ("get_ablation_result", {"feature": "pub_rec"}),
    ("get_ablation_result", {"feature": "not_a_feature"}),
    ("get_feature_coverage", {"feature": "all_util_was_missing"}),
    ("get_feature_coverage", {"feature": "open_acc_6m"}),
    ("get_feature_coverage", {"feature": "term"}),
    ("get_feature_coverage", {"feature": "nope"}),
    ("get_feature_target_association", {"feature": "open_acc_6m_was_missing"}),
    ("get_feature_target_association", {"feature": "term"}),
    ("get_feature_target_association", {"feature": "all_util"}),
    ("get_feature_target_association", {"feature": "nope"}),
    ("get_correlated_features", {"feature": "term"}),
    ("get_correlated_features", {"feature": "term", "top_k": 15}),
    ("get_correlated_features", {"feature": "term", "top_k": 99}),
    ("get_correlated_features", {"feature": "term", "top_k": 0}),
    ("get_correlated_features", {"feature": "recoveries"}),
    ("get_correlated_features", {"feature": "nope"}),
    # dispatch's own guards
    ("no_such_tool", {"feature": "term"}),
    ("lookup_feature", {"wrong_arg": "term"}),
    ("lookup_feature", {}),
    ("get_correlated_features", {"feature": "term", "bad": 1}),
]


def _pinned_versions() -> dict[str, str]:
    """The pins for the version-critical libraries, read from the file."""
    if not REQUIREMENTS.is_file():
        raise SystemExit(f"Cannot check versions: {REQUIREMENTS} is missing.")
    pins = {}
    for line in REQUIREMENTS.read_text().splitlines():
        line = line.split("#", 1)[0].strip()
        if "==" not in line:
            continue
        name, _, version = line.partition("==")
        name = name.strip().lower()
        if name in VERSION_CRITICAL:
            pins[name] = version.strip()
    missing = [n for n in VERSION_CRITICAL if n not in pins]
    if missing:
        raise SystemExit(
            f"Cannot check versions: {REQUIREMENTS.name} has no == pin for "
            f"{', '.join(missing)}. Pin them, or drop them from "
            f"VERSION_CRITICAL if they no longer affect the numbers.")
    return pins


def _check_pinned_versions(writes: str = "cases.json") -> None:
    """Refuse to write a cases file from the wrong interpreter.

    `writes` names the file the caller would produce, so the refusal names
    it too; scripts/verify_js_scoring.py shares this check.

    Six of the seven exported artefacts are table copies: read a CSV, copy
    the values, no arithmetic, nothing to drift. shap_detail.json is the
    exception. Its twenty statistics per feature are computed here, over
    30,000 float64 rows, and a summation order that differs between minor
    numpy releases moves the last bit of `std`.

    That is about 10^-16, far below anything a tool result means. But the
    harness compares the exact bytes a tool_result carries, so one bit is a
    failure, and it reads exactly like a bug in the JavaScript port. It is
    not. It is the wrong Python.

    Under the pinned versions the port matches on all 312 cases. Run it
    under anything else and the mismatches are the interpreter's, so this
    stops rather than writing a cases file that would indict the port for
    something it did not do.
    """
    pins = _pinned_versions()
    import numpy
    import pandas

    found = {"numpy": numpy.__version__, "pandas": pandas.__version__}
    wrong = {n: (found[n], pins[n]) for n in VERSION_CRITICAL if found[n] != pins[n]}
    if not wrong:
        return

    # Which generator is asking. Only the tools one is guarding a float;
    # the other two are guarded so that all three case sets are produced by
    # the same interpreter, which is what makes them comparable at all.
    kind = ("tools" if writes == "cases.json"
            else "scoring" if "scoring" in writes
            else "parse")
    module = f"scripts.verify_js_{kind}"
    lines = [
        f"Refusing to write {writes}: this interpreter is not the one the "
        f"repository pins.",
        "",
        f"  running:  {sys.executable}",
    ]
    for name in VERSION_CRITICAL:
        have, want = found[name], pins[name]
        mark = "  <- differs" if name in wrong else ""
        lines.append(f"  {name + ':':<9} {have:<10} (requirements.txt pins {want}){mark}")
    lines += [""]
    lines += ([
        f"The {kind} port does no floating-point reduction, so this check is",
        "not guarding a number here. It is guarding against the three case",
        "sets being generated by different interpreters, which would leave",
        "one reproducible and another not for no visible reason.",
    ] if kind != "tools" else [
        "Why this matters here, and not in most scripts: shap_detail.json is",
        "the one exported artefact that is computed rather than copied. Its",
        "`std` is a sum over 30,000 float64 rows, and numpy changes the last",
        "bit of that sum between minor releases. The parity harness compares",
        "the exact bytes a tool_result carries, so that one bit fails eight",
        "of the 312 cases and looks like a defect in docs/agent/tools.js.",
        "It is not. The JavaScript is fine; the Python is the wrong build.",
    ])
    lines += [
        "",
        "Run it under the pinned environment instead:",
        "",
        f"    .venv/bin/python -m {module}",
        "",
        "If the venv itself is stale: .venv/bin/pip install -r requirements.txt",
    ]
    raise SystemExit("\n".join(lines))


def main() -> None:
    _check_pinned_versions()
    cases = []
    for variant, cache_dir in VARIANTS.items():
        if not cache_dir.is_dir():
            raise SystemExit(f"Missing cache for '{variant}': {cache_dir}")
        for label, populated, scopes in SWITCHES:
            tools = ToolLayer(cache_dir=cache_dir,
                              include_populated=populated,
                              include_vintage_scopes=scopes)
            for name, args in CASES:
                result = tools.dispatch(name, args)
                cases.append({
                    "variant": variant,
                    "switches": label,
                    "include_populated": populated,
                    "include_vintage_scopes": scopes,
                    "tool": name,
                    "arguments": args,
                    "result": result,
                    # Exactly what agent.py puts in the tool_result block.
                    "wire": json.dumps(result, default=str),
                })

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"generated_by": "scripts/verify_js_tools.py",
         "case_count": len(cases),
         "cases": cases}, indent=1, ensure_ascii=False, allow_nan=False) + "\n")
    print(f"wrote {len(cases)} cases to {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
