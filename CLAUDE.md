# Honest Mistake — repo rules

Repo: honest-mistake. A multi-layer ML audit project.

- Layer 1 (done): leakage-free credit default model, XGBoost,
  180 features, temporal split, ROC-AUC 0.7296.
- Layer 2 (shipped, 97a339c): a raw ReAct agent in agent/ that audits
  that model. Eight read-only tools, pgvector semantic retrieval over
  the data dictionary, two ablation switches. Plain Python + Anthropic
  API. No LangChain, no frameworks.

Layer 2 has 8 read-only tools in agent/tools.py:
lookup_feature, search_data_dictionary, get_shap_ranking,
get_feature_shap_detail, get_ablation_result, get_feature_coverage,
get_feature_target_association, get_correlated_features.
All reachable only through dispatch(). All read fixed artefacts under
outputs/agent_cache/, except search_data_dictionary, whose second tier
queries a local pgvector index built from the dictionary descriptions.

Two ablation switches, both constructor arguments on ToolLayer and
neither present in any published tool schema: include_populated and
include_vintage_scopes.

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
