"""Phase 3, step 2, part A: the validator against R1-R6 and N1-N5, in process.

No container is involved and nothing is refused. N1-N5 attempt no escape,
which is the only reason they can be run this way. Every case runs three
times. The script reports each verdict, whether the three agreed, and
whether the outcome is the one PREREGISTRATION_PHASE3.md predicts. It does
not retry, and it adjusts nothing.

    .venv/bin/python -m scripts.validate_part_a
"""

import sys
from pathlib import Path

from layer3.validator import classify, run_in_process

TOOLS = Path(__file__).resolve().parent.parent / "layer3" / "tools"
RUNS = 3

# (case, question, tool file, expected outcome, what the document predicts)
CASES = [
    ("R1", "K1", "reference/r1_train_rows.py", "pass", "correct"),
    ("R2", "K2", "reference/r2_feature_count.py", "pass", "correct"),
    ("R3", "K3", "reference/r3_train_mean.py", "pass", "correct"),
    ("R4", "K4", "reference/r4_ablation_delta.py", "pass", "correct"),
    ("R5", "K5", "reference/r5_shap_ranks.py", "pass", "correct"),
    ("R6", "K6", "reference/r6_best_trial.py", "pass", "correct"),
    ("N1", "K3", "broken/n1_unweighted_mean.py", "wrong_answer",
     "ignores n_rows; loan_amnt off by about 5.7"),
    ("N2", "K4", "broken/n2_rounded_baseline.py", "wrong_answer",
     "subtracts 0.7296; every delta off by 2.47e-5"),
    ("N3", "K5", "broken/n3_signed_shap.py", "wrong_answer",
     "ranks by signed, not absolute, SHAP"),
    ("N4", "K6", "broken/n4_second_best_trial.py", "wrong_answer",
     "returns trial 48"),
    ("N5", "K2", "broken/n5_bare_number.py", "bad_output",
     "prints a bare 180, not a JSON object"),
]


def main() -> int:
    unexpected = 0
    for case, qid, rel, expected, predicted in CASES:
        verdicts = []
        for run in range(1, RUNS + 1):
            obs = run_in_process(TOOLS / rel, qid)
            verdict = classify(qid, obs)
            verdicts.append(verdict)
            print(f"{case} {qid} run {run}: {verdict.outcome:<12} "
                  f"{obs.elapsed_s:6.2f} s  {verdict.reason}")
        identical = len(set(verdicts)) == 1
        as_expected = all(v.outcome == expected for v in verdicts)
        status = "as expected" if as_expected else "UNEXPECTED"
        print(f"{case}: expected {expected} ({predicted}); {status}; "
              f"three runs identical: {identical}\n")
        if not (as_expected and identical):
            unexpected += 1
    print(f"{unexpected} case(s) unexpected or inconsistent across runs.")
    return 1 if unexpected else 0


if __name__ == "__main__":
    sys.exit(main())
