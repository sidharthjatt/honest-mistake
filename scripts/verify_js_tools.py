"""Generate the expected tool outputs the JavaScript port must reproduce.

Writes verify/cases.json. Each case is a dispatch call under a named
configuration, with the result agent/tools.py returned and the exact bytes
agent/agent.py would have sent to the model for it.

The harnesses in verify/ run the same cases through docs/agent/tools.js and
compare both. They live outside docs/ so that nothing used for checking the
port is ever published with the site. Serve the repository root and open
verify/_verify_tools.html. Nothing here touches the network.

    .venv/bin/python -m scripts.verify_js_tools
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.tools import ToolLayer  # noqa: E402

OUT = ROOT / "verify" / "cases.json"

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


def main() -> None:
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
