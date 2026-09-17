"""eval_canary.py — Honest Mistake, Layer 2 scoring.

Reads a completed run directory, extracts the flags from the agent's
final answer, and scores them against the answer key. It does not run
the agent and does not modify anything.

Parsing is strict on purpose. Malformed output is a result about the
agent, not an inconvenience to be smoothed over, so every departure from
the specified format is reported as a named warning and nothing is
repaired or guessed. An answer that fails to parse is reported as a
parse failure, never as a clean "nothing found" — those two outcomes
mean opposite things.

Two kinds of run are refused outright rather than scored: a run that did
not finish, and a mock run. Scoring either would produce a number that
looks comparable to a real result and is not.

Marker strings are imported, never written out here, so the parser
cannot drift away from the instruction the agent was given.
(VERBATIM_DELIMITER comes from the runner, which writes it; the rest
come from the prompt module, which specifies them.)

Usage:
    .venv/bin/python -m agent.eval_canary --run <directory>
    .venv/bin/python -m agent.eval_canary --compare <dir_a> <dir_b>
"""

import argparse
import csv
import json
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

from agent.answer_key import (CLEAN_UNDER_SUPPRESSION, HARD_NEGATIVES,
                              RESIDUAL_TIMING_LEAK, TIER_LABELS, score,
                              tier_counts)
from agent.data_dictionary import FEATURE_DOCS
from agent.prompts import (ANSWER_END, ANSWER_START, CONFIDENCE_VALUES,
                           FIELD_ORDER, NO_FINDINGS_MARKER, RECORD_SEPARATOR)
from agent.run_audit import VERBATIM_DELIMITER

RULE = "=" * 72
THIN = "-" * 72

_PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass
class ParseResult:
    """Outcome of reading one final answer."""

    records: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    explicit_no_findings: bool = False
    block_found: bool = False

    @property
    def flags(self) -> list[str]:
        return [r["FLAG"] for r in self.records if "FLAG" in r]

    @property
    def is_scoreable(self) -> bool:
        """True when a block was found, even if it declared no findings."""
        return self.block_found


def parse_final_answer(text: str) -> ParseResult:
    """Extract records from a final answer. Reports, never repairs."""
    out = ParseResult()

    # The runner prefixes a header; everything after the delimiter is the
    # model's own text. Absence of the delimiter is fine - the caller may
    # be passing raw text.
    if VERBATIM_DELIMITER in text:
        text = text.split(VERBATIM_DELIMITER, 1)[1]

    starts = text.count(ANSWER_START)
    ends = text.count(ANSWER_END)

    if starts == 0:
        out.warnings.append(
            f"missing start marker: no {ANSWER_START!r} in the answer")
        return out
    if starts > 1:
        out.warnings.append(
            f"repeated start marker: {ANSWER_START!r} appears {starts} times; "
            f"the first is used")
    if ends == 0:
        out.warnings.append(
            f"unclosed block: no {ANSWER_END!r} after the start marker")
        return out
    if ends > 1:
        out.warnings.append(
            f"repeated end marker: {ANSWER_END!r} appears {ends} times; "
            f"the first is used")

    out.block_found = True
    after_start = text.split(ANSWER_START, 1)[1]
    body, _, trailing = after_start.partition(ANSWER_END)

    if trailing.strip():
        preview = " ".join(trailing.split())[:60]
        out.warnings.append(
            f"text after the end marker: {len(trailing.strip())} characters "
            f"follow the block ({preview!r}...)")

    body = body.strip()
    if body == NO_FINDINGS_MARKER:
        out.explicit_no_findings = True
        return out
    if not body:
        out.warnings.append(
            "empty block: nothing between the markers, and the "
            f"{NO_FINDINGS_MARKER!r} marker was not used")
        return out

    chunks = [c.strip() for c in body.split(RECORD_SEPARATOR)]
    for i, chunk in enumerate(chunks, 1):
        if not chunk:
            out.warnings.append(
                f"record {i}: empty record, which means a stray "
                f"{RECORD_SEPARATOR!r} separator")
            continue

        rec, seen_order, stray = {}, [], []
        for line in chunk.splitlines():
            line = line.strip()
            if not line:
                continue
            name, sep, value = line.partition(":")
            name = name.strip()
            if not sep or name not in FIELD_ORDER:
                stray.append(line)
                continue
            if name in rec:
                out.warnings.append(
                    f"record {i}: field {name} given more than once; "
                    f"the first is used")
                continue
            rec[name] = value.strip()
            seen_order.append(name)

        if stray:
            preview = "; ".join(s[:40] for s in stray[:2])
            out.warnings.append(
                f"record {i}: {len(stray)} line(s) are not one of "
                f"{', '.join(FIELD_ORDER)} ({preview})")

        missing = [f for f in FIELD_ORDER if f not in rec]
        if missing:
            out.warnings.append(
                f"record {i}: missing field(s) {', '.join(missing)}")
        elif seen_order != list(FIELD_ORDER):
            out.warnings.append(
                f"record {i}: fields out of order - got "
                f"{', '.join(seen_order)}, expected {', '.join(FIELD_ORDER)}")

        flag = rec.get("FLAG", "")
        if flag and flag not in FEATURE_DOCS:
            out.warnings.append(
                f"record {i}: FLAG {flag!r} is not a documented column name; "
                f"it is scored as given, and will count against precision")

        conf = rec.get("CONFIDENCE")
        if conf is not None and conf not in CONFIDENCE_VALUES:
            out.warnings.append(
                f"record {i}: CONFIDENCE {conf!r} is not one of "
                f"{', '.join(CONFIDENCE_VALUES)}")

        if flag:
            out.records.append(rec)
        else:
            out.warnings.append(
                f"record {i}: no usable FLAG, so the record is not scored")

    return out


# ----------------------------------------------------------------------
# Run directory access
# ----------------------------------------------------------------------
def _read_run(directory: Path) -> tuple[dict, str, list[dict]]:
    manifest_path = directory / "manifest.json"
    answer_path = directory / "final_answer.txt"
    log_path = directory / "tool_call_log.json"

    if not manifest_path.exists():
        raise SystemExit(
            f"No manifest.json in {directory.name}. This does not look like a "
            f"run directory produced by the runner.")
    if not answer_path.exists():
        raise SystemExit(f"No final_answer.txt in {directory.name}.")

    manifest = json.loads(manifest_path.read_text())
    answer = answer_path.read_text()
    calls = []
    if log_path.exists():
        calls = json.loads(log_path.read_text()).get("calls", [])
    return manifest, answer, calls


def refusal_reason(manifest: dict) -> str | None:
    """Why this run must not be scored, or None if it may be."""
    if manifest.get("mock", manifest.get("mode") == "MOCK"):
        return (
            "This is a MOCK run. Its text comes from fixed fixtures written to "
            "exercise the loop, not from a model reasoning about the data. "
            "Scoring it would produce a number that looks like a result and "
            "measures nothing.")
    if not manifest.get("is_usable", False):
        return (
            f"This run ended as '{manifest.get('termination')}' "
            f"(last stop_reason '{manifest.get('last_stop_reason')}'), so the "
            f"agent never signalled that it had finished. A partial answer is "
            f"not an answer and is not scored.")
    return None


# ----------------------------------------------------------------------
# Reporting
# ----------------------------------------------------------------------
def _print_header(directory: Path, manifest: dict) -> None:
    print(RULE)
    print(f"RUN  {directory.name}")
    print(RULE)
    print(f"  mode              {manifest.get('mode')}")
    print(f"  config_id         {manifest.get('config_id')}")
    print(f"  populated field   {manifest.get('dictionary_populated_field')}")
    print(f"  termination       {manifest.get('termination')}  "
          f"(usable: {manifest.get('is_usable')})")
    print(f"  turns / calls     {manifest.get('turns')} / "
          f"{manifest.get('tool_calls')}")


def _print_parse(parsed: ParseResult) -> None:
    print()
    print("PARSE")
    if parsed.warnings:
        for w in parsed.warnings:
            print(f"  WARNING  {w}")
    else:
        print("  no warnings; the block matched the specified format")

    if not parsed.block_found:
        print("  RESULT   the answer could not be parsed. This is a parse "
              "failure,")
        print("           not a finding of 'nothing to report'.")
    elif parsed.explicit_no_findings:
        print(f"  RESULT   the agent used {NO_FINDINGS_MARKER!r}: it "
              f"deliberately reported nothing.")
    else:
        print(f"  RESULT   {len(parsed.records)} record(s) parsed")


def _print_tools(calls: list[dict]) -> None:
    print()
    print("TOOL USE")
    if not calls:
        print("  no tool call log found for this run")
        return
    per_tool = Counter(c["tool"] for c in calls)
    rejected = [c for c in calls if not c.get("ok", True)]
    print(f"  total calls       {len(calls)}")
    for tool, n in sorted(per_tool.items(), key=lambda kv: (-kv[1], kv[0])):
        print(f"    {tool:<28} {n}")
    if rejected:
        print(f"  rejected calls    {len(rejected)} attempted")
        for c in rejected:
            print(f"    seq {c['seq']:<3} {c['tool']:<28} {c['outcome']}")
    else:
        print("  rejected calls    none attempted")


def _print_score(result: dict) -> None:
    print()
    print("SCORE")
    print(f"  flagged           {result['flagged_count']}  "
          f"(scored: {result['scored_count']}, out of scope and excluded: "
          f"{result['out_of_scope_flagged_count']})")
    if result["out_of_scope_flagged"]:
        print(f"    excluded        {', '.join(result['out_of_scope_flagged'])}")
    print(f"  true positives    {result['true_positive_count']}")
    print(f"  false positives   {result['false_positive_count']}")
    print(f"  false negatives   {result['false_negative_count']}")
    derived = result.get("derivative_resolutions", [])
    if derived:
        print(f"  derivative flags  {len(derived)} scored against a parent "
              f"column rather than as unknown names")
        for e in derived:
            print(f"    {e['flag']} -> {e['parent']} "
                  f"({e['kind']}, {e['parent_set']})")
    print(f"  precision         {result['precision']}")
    print(f"  recall            {result['recall']}")
    print(f"  f1                {result['f1']}")

    tiers = result["true_positives_by_residual_tier"]
    print()
    print("  correct flags by residual tier")
    for t in ("A", "B", "C"):
        row = tiers[t]
        share = row["count"] / row["of_possible"] if row["of_possible"] else 0
        print(f"    tier {t}  {row['count']:>2}/{row['of_possible']:<3} "
              f"({share:.0%})  {row['label']}")
    clean = result["true_positives_clean_under_suppression"]
    print(f"    clean   {len(clean):>2}/{len(CLEAN_UNDER_SUPPRESSION):<3} "
          f"({len(clean) / max(len(CLEAN_UNDER_SUPPRESSION), 1):.0%})  "
          f"no lifecycle phrase in the description")


def _print_canary(result: dict, records: list[dict]) -> None:
    """Canary detection, reported on its own before anything aggregate."""
    canary = result.get("canary") or {}
    if not canary.get("planted"):
        return
    by_flag = {r.get("FLAG"): r for r in records}

    print()
    print(RULE)
    print("CANARY")
    print(RULE)
    for column in canary["planted"]:
        detail = canary["detail"].get(column, {})
        base = detail.get("baseline_test_roc_auc")
        with_c = detail.get("canary_test_roc_auc")
        caught = column in canary["caught"]
        print(f"  planted          {column}  (tier {detail.get('tier')})")
        if base is not None and with_c is not None:
            print(f"  held-out ROC-AUC {base:.4f} without it, "
                  f"{with_c:.4f} with it  ({with_c - base:+.4f})")
        print(f"  result           {'CAUGHT' if caught else 'MISSED'}")
        if caught:
            rec = by_flag.get(column, {})
            print(f"    confidence     {rec.get('CONFIDENCE', '(not given)')}")
            print(f"    stated reason  {rec.get('REASON', '(not given)')}")
            print(f"    stated evidence {rec.get('EVIDENCE', '(not given)')}")
        else:
            print("    the planted column was not among the flags")


def _print_discriminators(result: dict) -> None:
    tiers = result["true_positives_by_residual_tier"]
    c = tiers["C"]
    c_recall = c["count"] / c["of_possible"] if c["of_possible"] else 0.0
    hn = result["hard_negatives_flagged_count"]

    print()
    print(RULE)
    print("DISCRIMINATING PAIR")
    print(RULE)
    print("  Tiers A and B are recoverable by matching phrases in the column")
    print("  descriptions. Tier C is not, and the hard negatives are the case")
    print("  a string matcher gets wrong. Read these two before the headline.")
    print()
    raw = result.get("hard_negatives_flagged_raw", [])
    derived = result.get("hard_negatives_flagged_via_derivative", [])
    distinct = result.get("hard_negatives_distinct_count", hn)

    print(f"  tier C recall            {c['count']}/{c['of_possible']} "
          f"({c_recall:.0%})")
    how = ""
    if hn:
        parts = []
        if raw:
            parts.append(f"{len(raw)} named directly")
        if derived:
            parts.append(f"{len(derived)} via _was_missing derivatives")
        how = f"  ({', '.join(parts)})"
    print(f"  hard negatives flagged   {hn}{how}")
    print(f"  distinct hard negatives  {distinct}/{len(HARD_NEGATIVES)}")
    if raw:
        print(f"    named directly    {', '.join(raw)}")
    for entry in result.get("derivative_resolutions", []):
        if entry["parent_set"] == "HARD_NEGATIVES":
            print(f"    via derivative    {entry['flag']} "
                  f"-> {entry['parent']} ({entry['kind']})")


def _print_reasons(records: list[dict]) -> None:
    print()
    print(RULE)
    print("REASONS - NOT SCORED. These require human grading; nothing below")
    print("was checked mechanically, and a correct flag can carry a wrong")
    print("reason without affecting any number above.")
    print(RULE)
    if not records:
        print("  no records to review")
        return
    for i, r in enumerate(records, 1):
        print(f"  [{i}] FLAG        {r.get('FLAG', '(none)')}")
        print(f"      CONFIDENCE  {r.get('CONFIDENCE', '(none)')}")
        print(f"      REASON      {r.get('REASON', '(none)')}")
        print(f"      EVIDENCE    {r.get('EVIDENCE', '(none)')}")
        print(f"      grade: [ ] reason correct   [ ] reason wrong   "
              f"[ ] reason unsupported")
        if i < len(records):
            print(THIN)


def _canary_present(manifest: dict) -> bool:
    """Whether the planted column was in this run's data.

    The preregistered rule, from PREREGISTRATION.md's canary attribution
    section: use the manifest's `canary` field where it exists, and where
    it does not, derive from `config_id`, which ends with `-canary` for a
    canary run. The field is absent from the five v1.0 manifests, which
    predate it.
    """
    if "canary" in manifest:
        return bool(manifest["canary"])
    return str(manifest.get("config_id", "")).endswith("-canary")


def _model_columns(manifest: dict) -> list[str] | None:
    """The audited model's feature list, from the cache the run read.

    Taken from that cache's shap_global.csv, which lists every feature the
    model has and is the same artefact get_shap_ranking serves. It is used
    rather than data/processed/X_test.parquet because the parquet holds
    the honest matrix only, and a canary run's model has a column the
    honest matrix does not. Returns None when the cache cannot be located,
    so reachability is reported as unknown rather than guessed at.
    """
    cache = manifest.get("cache_dir")
    if not cache:
        # The five v1.0 manifests predate the field. Which cache a run read
        # follows from whether the canary was in it, and that is already
        # established by the preregistered rule above, so this falls back
        # to it rather than reporting the answer unknown for those runs.
        cache = "agent_cache_canary" if _canary_present(manifest) else "agent_cache"
    path = _PROJECT_ROOT / "outputs" / cache / "shap_global.csv"
    if not path.is_file():
        return None
    with path.open(newline="") as fh:
        return [row["feature"] for row in csv.DictReader(fh)]


def evaluate(directory: Path, quiet: bool = False) -> dict | None:
    """Score one run directory, or refuse and explain why."""
    manifest, answer, calls = _read_run(directory)
    if not quiet:
        _print_header(directory, manifest)

    refusal = refusal_reason(manifest)
    if refusal:
        if not quiet:
            print()
            print("REFUSED - NOT SCORED")
            for line in refusal.split(". "):
                if line.strip():
                    print(f"  {line.strip().rstrip('.')}.")
        return None

    parsed = parse_final_answer(answer)
    if not quiet:
        _print_parse(parsed)
        _print_tools(calls)

    if not parsed.is_scoreable:
        if not quiet:
            print()
            print("NOT SCORED - the final answer could not be parsed.")
        return None

    result = score(parsed.flags,
                   canary_present=_canary_present(manifest),
                   model_columns=_model_columns(manifest))
    if not quiet:
        _print_canary(result, parsed.records)
        _print_score(result)
        _print_discriminators(result)
        _print_reasons(parsed.records)
    return {"manifest": manifest, "parsed": parsed, "score": result,
            "calls": calls}


def compare(dir_a: Path, dir_b: Path) -> None:
    """Two runs side by side, for reading the ablation."""
    a = evaluate(dir_a, quiet=True)
    b = evaluate(dir_b, quiet=True)

    print(RULE)
    print("COMPARISON")
    print(RULE)
    for tag, d, res in (("A", dir_a, a), ("B", dir_b, b)):
        if res is None:
            manifest, _, _ = _read_run(d)
            print(f"  run {tag}  {d.name}")
            print(f"          NOT SCOREABLE - {refusal_reason(manifest) or 'answer did not parse'}")
        else:
            print(f"  run {tag}  {d.name}")
            print(f"          config {res['manifest'].get('config_id')}")
    if a is None or b is None:
        print()
        print("  Cannot compare: at least one run was not scoreable.")
        return

    sa, sb = a["score"], b["score"]
    print()
    print(f"  {'metric':<26}{'run A':>12}{'run B':>12}{'B - A':>12}")
    print(f"  {THIN[:60]}")
    for label, key in (("flags scored", "scored_count"),
                       ("true positives", "true_positive_count"),
                       ("false positives", "false_positive_count"),
                       ("hard negatives flagged",
                        "hard_negatives_flagged_count")):
        va, vb = sa[key], sb[key]
        print(f"  {label:<26}{va:>12}{vb:>12}{vb - va:>+12}")
    for label, key in (("precision", "precision"), ("recall", "recall"),
                       ("f1", "f1")):
        va, vb = sa[key], sb[key]
        print(f"  {label:<26}{va:>12.4f}{vb:>12.4f}{vb - va:>+12.4f}")

    print()
    print("  correct flags by residual tier")
    print(f"  {'tier':<26}{'run A':>12}{'run B':>12}{'B - A':>12}")
    for t in ("A", "B", "C"):
        ra = sa["true_positives_by_residual_tier"][t]
        rb = sb["true_positives_by_residual_tier"][t]
        print(f"  {t + '  ' + TIER_LABELS[t][:20]:<26}"
              f"{str(ra['count']) + '/' + str(ra['of_possible']):>12}"
              f"{str(rb['count']) + '/' + str(rb['of_possible']):>12}"
              f"{rb['count'] - ra['count']:>+12}")

    fa, fb = set(sa["true_positives"] + sa["false_positives"]), \
        set(sb["true_positives"] + sb["false_positives"])
    only_a, only_b = sorted(fa - fb), sorted(fb - fa)
    print()
    print(f"  flagged in A only ({len(only_a)}): "
          f"{', '.join(only_a) if only_a else 'none'}")
    print(f"  flagged in B only ({len(only_b)}): "
          f"{', '.join(only_b) if only_b else 'none'}")
    print(f"  flagged in both   ({len(fa & fb)}): "
          f"{', '.join(sorted(fa & fb)) if fa & fb else 'none'}")

    print()
    print("  confidence distribution")
    ca = Counter(r.get("CONFIDENCE") for r in a["parsed"].records)
    cb = Counter(r.get("CONFIDENCE") for r in b["parsed"].records)
    print(f"  {'value':<26}{'run A':>12}{'run B':>12}{'B - A':>12}")
    for value in CONFIDENCE_VALUES:
        print(f"  {value:<26}{ca.get(value, 0):>12}{cb.get(value, 0):>12}"
              f"{cb.get(value, 0) - ca.get(value, 0):>+12}")

    print()
    print("  Reasons are not compared here. Whether a flag was reached for a")
    print("  sound reason cannot be settled mechanically; grade each run's")
    print("  reason list by hand before drawing a conclusion from the numbers.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="eval_canary",
        description="Score an audit run against the answer key.")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--run", type=Path, help="one run directory to score")
    group.add_argument("--compare", type=Path, nargs=2,
                       metavar=("DIR_A", "DIR_B"),
                       help="two run directories, side by side")
    args = parser.parse_args(argv)

    if args.run:
        evaluate(args.run)
    else:
        compare(args.compare[0], args.compare[1])
    return 0


if __name__ == "__main__":
    sys.exit(main())
