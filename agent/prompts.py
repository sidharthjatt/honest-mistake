"""prompts.py — Honest Mistake, Layer 2.

The system prompt for the audit agent, and the specification of the
final-answer format it must produce.

This module is where the evaluation is most easily invalidated. The
agent is asked whether the model's held-out result can be trusted; it is
not told what kind of problem to look for, and it is not pointed at any
column, family of columns, or property of the dictionary. Whether it
arrives at a productive hypothesis is the thing being measured. If it
does not arrive at one, that is a result to record, not a defect to
correct by adding a hint here.

_self_check() enforces this mechanically: it asserts that none of the
steering terms in FORBIDDEN_TERMS appears in the prompt or the format
specification, and that no documented column name appears anywhere in
this file.

The headline figures in the prompt are read from the tuning record on
disk rather than written in by hand, so they cannot drift away from the
model actually being audited.

Run the checks:
    .venv/bin/python -m agent.prompts
"""

import json
import re
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TUNING_RECORD = _PROJECT_ROOT / "outputs" / "models" / "best_params.json"

DEFAULT_N_FEATURES = 180

# ----------------------------------------------------------------------
# Final-answer format
#
# Exported as constants so that a parser imports the same strings the
# instruction uses, and the two cannot drift apart.
# ----------------------------------------------------------------------
ANSWER_START = "=== AUDIT FINDINGS ==="
ANSWER_END = "=== END AUDIT FINDINGS ==="
RECORD_SEPARATOR = "###"
NO_FINDINGS_MARKER = "NO FINDINGS"
FIELD_ORDER = ("FLAG", "REASON", "EVIDENCE", "CONFIDENCE")
CONFIDENCE_VALUES = ("high", "medium", "low")

FINAL_ANSWER_FORMAT = f"""\
{ANSWER_START}
FLAG: <exact column name, and nothing else on this line>
REASON: <one sentence: why this column makes the held-out result \
misleading>
EVIDENCE: <one sentence: the specific tool output that supports the \
reason above>
CONFIDENCE: <{" | ".join(CONFIDENCE_VALUES)}>
{RECORD_SEPARATOR}
FLAG: <exact column name>
REASON: <...>
EVIDENCE: <...>
CONFIDENCE: <...>
{ANSWER_END}

Rules for this block:
  - Emit the block exactly once, as the last thing you write.
  - One record per column. Separate consecutive records with a line
    containing only {RECORD_SEPARATOR}. Do not put {RECORD_SEPARATOR} \
before the first record or after the last.
  - Every record must carry all four fields, in the order \
{", ".join(FIELD_ORDER)}, one field per line, each beginning with the \
field name in capitals followed by a colon and a space.
  - FLAG must contain one column name exactly as the tools spell it,
    with no quotation marks, no punctuation, and no commentary.
  - REASON must state why, on its own, without referring to another
    record. It is read independently of the rest of your output.
  - EVIDENCE must point at something a tool actually returned. If you
    have no tool output to point at, write: no supporting tool output.
  - Put nothing else between the two markers: no headings, no blank
    lines, no numbering, no summary.
  - If you conclude there is nothing to report, put exactly
    {NO_FINDINGS_MARKER} between the two markers and nothing else.
"""


def _headline_figures(tuning_record: Path | None = None) -> dict:
    """Read the audited model's held-out figures from its tuning record."""
    record = json.loads((tuning_record or _TUNING_RECORD).read_text())
    return {
        "test_roc_auc": float(record["test_roc_auc"]),
        "val_roc_auc": float(record["val_roc_auc"]),
    }


def build_system_prompt(max_turns: int, max_tool_calls: int,
                        n_features: int = DEFAULT_N_FEATURES,
                        tuning_record: Path | None = None) -> str:
    """Assemble the system prompt for one run.

    The ceilings are arguments rather than defaults so that the prompt
    cannot state a limit different from the one being enforced. There is
    no module-level rendering of this prompt: every caller must supply
    the limits it will actually apply.
    """
    figures = _headline_figures(tuning_record)
    return f"""\
You are reviewing a machine learning model that another team has built
and is preparing to rely on.

The model estimates whether a consumer loan will end in default. It was
fitted on loans issued between 2014 and 2016 and then scored once on
loans issued in 2017, which were held back and not used in fitting or
in selecting settings. It reads {n_features} input columns. Its score on
the held-back 2017 loans is a ROC-AUC of {figures['test_roc_auc']:.4f};
on the 2016 loans used while selecting settings it scored
{figures['val_roc_auc']:.4f}.

The team intends to read that held-back figure as an estimate of how the
model will perform on loans it has never seen. Your job is to decide
whether that reading is justified, and to report anything you find that
would make it misleading. Nobody has told you what, if anything, is
wrong. It is possible that nothing is.

Five tools are available to you. Use them to investigate. You can ask
what a column contains, search across the column descriptions, see which
columns the model relies on most heavily and how one column's influence
is distributed across loans, and see how the model scores when it is
refitted without a particular column.

How to work:

  - Form a hypothesis about what could make the held-back figure
    misleading, then test it against what the tools return. Say what you
    are testing and why before you call a tool.
  - Treat your own first idea sceptically. A plausible story is not an
    established one. Where a tool result is consistent with more than
    one explanation, say so and look for something that separates them.
  - You may abandon or revise a hypothesis at any point. Nothing you
    said earlier binds you.
  - Every claim you end up making must rest on something a tool actually
    returned. Where you cannot support a claim, drop it or state plainly
    that it is unsupported.
  - Investigate as widely as you judge necessary before concluding. Do
    not stop at the first thing that looks interesting, and do not pad
    your answer with items you cannot defend.

What you are allowed to spend:

  - at most {max_turns} exchanges in this session
  - at most {max_tool_calls} tool calls in total across those exchanges

These are hard stops. The moment either is reached you are cut off
mid-sentence, nothing further is recorded, and the session ends with no
answer at all. There is no warning beforehand and no opportunity to
finish afterwards. An unfinished session is worth nothing, whereas an
answer you hold with low confidence still says something.

So pace yourself. Keep enough of both allowances in hand to write your
final answer in full, and stop looking things up while you still can. If
you are getting close to either allowance, stop investigating and write
the answer from what you already have.

When you have finished investigating, write your final answer in exactly
the following format:

{FINAL_ANSWER_FORMAT}"""


# ----------------------------------------------------------------------
# Scope enforcement
# ----------------------------------------------------------------------
FORBIDDEN_TERMS = [
    "leakage", "leaky", "leak",
    "timing", "prediction time", "available at application",
    "lifecycle", "post-origination", "post origination",
    "future information", "look-ahead", "lookahead",
    "populated", "when a field is set", "removed during construction",
    "dropped column", "how many",
]


def _self_check() -> None:
    from agent.data_dictionary import FEATURE_DOCS

    # Rendered at two different settings so the check covers the text as
    # it is actually sent, whatever the ceilings happen to be.
    sample = build_system_prompt(12, 40)
    checked_text = (sample + "\n" + build_system_prompt(3, 8)
                    + "\n" + FINAL_ANSWER_FORMAT)
    low = checked_text.lower()

    hits = [t for t in FORBIDDEN_TERMS if t in low]
    assert not hits, f"steering terms present in the prompt: {hits}"

    # No documented column name anywhere in this file, not merely in the
    # prompt: a name in a comment would still be visible to anyone
    # editing the prompt later.
    source = Path(__file__).read_text()
    named = sorted(
        c for c in FEATURE_DOCS
        if re.search(rf"\b{re.escape(c)}\b", source)
    )
    assert not named, f"column names present in this file: {named}"

    # The format must be self-consistent with the exported constants.
    for token in (ANSWER_START, ANSWER_END, RECORD_SEPARATOR,
                  NO_FINDINGS_MARKER, *FIELD_ORDER, *CONFIDENCE_VALUES):
        assert token in FINAL_ANSWER_FORMAT, \
            f"'{token}' is exported but absent from the format spec"
    assert FINAL_ANSWER_FORMAT in sample, \
        "the prompt does not carry the format specification"

    # The stated ceilings must be the ones passed in, never anything else.
    for turns, calls in ((12, 40), (3, 8), (25, 100)):
        text = build_system_prompt(turns, calls)
        assert f"at most {turns} exchanges" in text, \
            f"prompt does not state the turn ceiling {turns}"
        assert f"at most {calls} tool calls" in text, \
            f"prompt does not state the call ceiling {calls}"

    print("prompts self-check")
    print(f"  prompt length                 {len(sample):>6} characters "
          f"(at 12 turns / 40 calls)")
    print(f"  steering terms checked        {len(FORBIDDEN_TERMS):>6}")
    print(f"  steering terms found          {len(hits):>6}")
    print(f"  documented columns checked    {len(FEATURE_DOCS):>6}")
    print(f"  column names found in file    {len(named):>6}")
    print("  format constants all present in the specification")
    print("  all assertions passed")


if __name__ == "__main__":
    _self_check()
