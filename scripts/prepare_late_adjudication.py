"""Prepare the late adjudication of Phase 4's 16 pending judgements.

Late, as D18 in PREREGISTRATION_PHASE4.md records: performed after the
scores were computed and published on 2026-09-14. Its one purpose is a
reference made by a person, not a model, for the next phase's judge. It
completes no section 3 rule and changes no Phase 4 or 4b outcome.

The 16 are found from the run records, not copied from the results document:
- part c: a parsed reply labelled not_answerable that cites at least one call
  listed as succeeding in section 2c, in any of the four scored runs;
- material near-misses NM3 and NM4: a parsed reply labelled
  answerable_with_difference or not_answerable.
The script stops unless exactly the 16 recorded in D18 come out.

Each is written as a record holding only two texts: the detector's
difference_or_missing, and the frozen reference it is judged against. Section
2c's last column is the reference for part c, and "The difference" in
section 4 for a near-miss. There is no run, item, label, call or count.

The records are shuffled with a seed drawn once and saved in setup.json.
The mapping from position to run and item is not written anywhere. It is
rebuilt from the seed and the canonical order: the four scored runs sorted
by directory name, then each run's episodes.json order.

It refuses to run if the output directory already holds items.json.

    .venv/bin/python -m scripts.prepare_late_adjudication
"""

import hashlib
import json
import random
import secrets
import sys
from pathlib import Path

from layer3.phase4 import ParseError, parse_detector_output

ROOT = Path(__file__).resolve().parent.parent
RUNS = sorted(p for p in (ROOT / "outputs" / "layer3" / "phase4_runs").iterdir()
              if p.is_dir() and "pilot" not in p.name)
OUT = ROOT / "outputs" / "layer3" / "late_adjudication"

# Section 2c, "Calls that succeed", as frozen: tool and arguments.
LISTED = {
    "C1": [("get_ablation_result", {"feature": "term"}),
           ("get_ablation_result", {"feature": "sub_grade"})],
    "C2": [("get_feature_coverage", {"feature": "all_util"})],
    "C3": [("get_feature_shap_detail", {"feature": "all_util"}),
           ("get_feature_coverage", {"feature": "all_util"})],
    "C4": [("get_feature_shap_detail", {"feature": "all_util"})],
    "C5": [("get_feature_target_association", {"feature": "all_util"})],
    "C6": [("get_correlated_features", {"feature": "all_util"})],
    "C7": [("get_ablation_result", {"feature": "term"}),
           ("get_feature_target_association", {"feature": "all_util"})],
}

# The frozen reference texts, verbatim from PREREGISTRATION_PHASE4.md.
REFERENCE = {
    "C1": "The schema takes one `feature`, and each figure is one retrain without one column. Two single-column deltas are not a joint retrain, and nothing returns one.",
    "C2": "Each scope returns `mean`, `std` and `p50`, and no other percentile",
    "C3": "One returns a summary of SHAP values, the other a summary of feature values. Neither has rows, so there is nothing to pair a value with its contribution.",
    "C4": "It returns summary statistics only, with no row identifiers and no per-row values",
    "C5": "Only `point_biserial_test` is returned. The training-split figures are AUCs, not correlations.",
    "C6": "Schema: correlations are \"over the full held-out test set\". No training-split figure exists in any tool.",
    "C7": "Ablation reports held-out 2017 scores only, and does not return the full model's score itself. The yearly AUCs are for one feature, not the model. No tool returns a model metric for any year.",
    "NM3": "`match_count` counts column names containing the text, plus up to 10 further entries matched by meaning within cosine distance 0.45. Those need not contain the text at all. The tool's own no-match message speaks of containing the term, which is how a substring search would behave.",
    "NM4": "`loan_amnt` has no missingness flag, verified, so no missing percentage is returned. Every scope's `n_rows` is complete, and the matrices hold no nulls. That completeness is a property of the matrices, not evidence about the source.",
}

EXPECTED = {
    "phase4-run1": ["C1", "C3", "C4", "NM3"],
    "phase4-run2": ["C3", "NM3", "NM4"],
    "phase4b-run1": ["C1", "C2", "C5", "C7", "NM3", "NM4"],
    "phase4b-run2": ["C2", "C3", "NM3"],
}

INSTRUCTION = (
    "LATE adjudication (D18 in PREREGISTRATION_PHASE4.md). For each position, "
    "read the reference, then the reply. Record whether the reply states what "
    "the reference describes: yes or no, with a note if you want one.")

LIMITATIONS = [
    "Late: performed after the Phase 4 and 4b scores were computed and "
    "published on 2026-09-14, against section 3's rule that adjudication "
    "happens before any score is computed (D18). It completes no section 3 "
    "rule and changes no Phase 4 or 4b outcome.",
    "Not blind to the results: the adjudicator has seen all Phase 4 and 4b "
    "results, the scores and the analysis that led here. That includes a "
    "report on 2026-09-15 that quoted all 16 replies next to their item and "
    "run. This cannot be removed.",
    "The reference text identifies its item, because it names tools, fields "
    "and features. Positions that share a reference share an item, so how "
    "many judgements each item has can be seen.",
    "The reply text often names the feature or tool it is about, which also "
    "points to its item.",
    "One wording is used for both criteria. Section 3 asks whether a part c "
    "reply 'states the missing element in that row's last column'. Section 4 "
    "asks whether a near-miss reply 'states the difference'. The single "
    "wording 'states what the reference describes' was chosen so that the "
    "instruction does not reveal which part a position comes from. It is a "
    "paraphrase, not the frozen text.",
    "For NM3 and NM4, only section 4's 'The difference' text is shown as the "
    "reference, not 'Why material'. That choice is ours.",
    "Blinding is by presentation only. The mapping can be rebuilt from the "
    "seed in setup.json and the run records, so it depends on the adjudicator "
    "not doing that while judging.",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical() -> list[dict]:
    found = []
    for run in RUNS:
        label = run.name.split("__")[-1]
        for episode in json.loads((run / "episodes.json").read_text()):
            item = episode["item"]
            if not (item.startswith("C") or item in ("NM3", "NM4")):
                continue
            try:
                out = parse_detector_output(episode["final_text"])
            except (ParseError, ValueError):
                continue
            if item.startswith("C"):
                cited = [(c["tool"], c["arguments"]) for c in out["calls"]]
                eligible = (out["label"] == "not_answerable"
                            and any(c in LISTED[item] for c in cited))
            else:
                eligible = out["label"] in ("answerable_with_difference",
                                            "not_answerable")
            if eligible:
                found.append({"run": label, "item": item,
                              "reply": out["difference_or_missing"]})
    return found


def main() -> int:
    if (OUT / "items.json").exists():
        print("items.json already exists. Nothing is regenerated.")
        return 2
    found = canonical()
    by_run = {}
    for f in found:
        by_run.setdefault(f["run"], []).append(f["item"])
    if by_run != EXPECTED or len(found) != 16:
        print(f"STOP: the records give {len(found)} judgements, {by_run}, "
              f"not the 16 recorded in D18.")
        return 2

    seed = secrets.randbits(64)
    order = list(range(len(found)))
    random.Random(seed).shuffle(order)

    OUT.mkdir(parents=True, exist_ok=True)
    items = {
        "late_adjudication": True,
        "instruction": INSTRUCTION,
        "items": [{"position": pos, "reference": REFERENCE[found[i]["item"]],
                   "reply": found[i]["reply"]}
                  for pos, i in enumerate(order, start=1)],
    }
    setup = {
        "late_adjudication": True,
        "seed": seed,
        "shuffle": "random.Random(seed).shuffle(list(range(16))); position n "
                   "holds canonical index order[n-1]",
        "canonical_order": "the four scored runs sorted by directory name, "
                           "then each run's episodes.json order, keeping the "
                           "eligible part c and material near-miss replies",
        "count": len(found),
        "sources": {str(p.relative_to(ROOT)): _sha256(p) for p in
                    [ROOT / "PREREGISTRATION_PHASE4.md"]
                    + [r / "episodes.json" for r in RUNS]},
        "mapping_written": False,
    }
    judgements = {
        "late_adjudication": True,
        "purpose": "A reference made by a person, not a model, for the next "
                   "phase's judge. It completes no section 3 rule and changes "
                   "no Phase 4 or 4b outcome (D18).",
        "limitations": LIMITATIONS,
        "response": "yes or no per position, with an optional note",
        "judgements": [],
    }
    (OUT / "items.json").write_text(json.dumps(items, indent=1) + "\n")
    (OUT / "setup.json").write_text(json.dumps(setup, indent=1) + "\n")
    (OUT / "judgements.json").write_text(json.dumps(judgements, indent=1) + "\n")
    print(f"16 records written to {OUT.relative_to(ROOT)}; seed recorded in "
          f"setup.json; mapping not written.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
