# Honest Mistake — repo rules

Repo: honest-mistake. A multi-layer ML audit project.

- Layer 1 (done): leakage-free credit default model, XGBoost,
  180 features, temporal split, ROC-AUC 0.7296.
- Layer 2 (in progress): a raw ReAct agent in agent/ that audits that
  model. Plain Python + Anthropic API. No LangChain, no frameworks.

Layer 2 currently has 5 read-only tools in agent/tools.py:
lookup_feature, search_data_dictionary, get_shap_ranking,
get_feature_shap_detail, get_ablation_result.
All reachable only through dispatch(). All read fixed artefacts under
outputs/agent_cache/.

## Standing rules — not negotiable

- The agent must never reach raw data, arbitrary paths, directory
  listings, shell, or eval. Tools read one specific known artefact each.
- These files must stay unreachable from any tool, because they contain
  the answer the agent is being tested on:
    outputs/leakage_drop_log.txt
    outputs/audit_notes.txt
    outputs/fairness_ablation_notes.txt
    outputs/features_notes.txt
    outputs/build_dataset_notes.txt
    agent/data_dictionary.py
- No tool returns a filesystem path, module name, or traceback to the
  agent. Errors return a plain sentence.
- Never invent a fallback when data is missing. Say it is missing and
  stop.
- Do not add Co-Authored-By or any AI attribution to commits.
- Do not commit anything unless I explicitly ask.
- Prose written into the repo must read as human-written.
