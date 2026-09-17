"""Generate the expected scorer output the JavaScript port must reproduce.

Writes verify/scoring_cases.json. Each case is a flag list scored under a
stated canary presence, with the dict agent/answer_key.score returned.

Two kinds of case. The eight scored runs in the published bundle are the
real ones: their flags are replayed through the Python scorer and the port
must match. The synthetic ones cover paths no recorded run exercises — the
derivative resolutions, an out-of-scope flag, a hard negative reached
through its missingness twin, and the three canary states.

Each recorded case is also compared against the score the published
bundle carries for that run, which puts a third party in the comparison:
Python now, Python at export time, and the JavaScript port. Two faults
can show up there and they look identical until they are separated.

A key the bundle carries whose value has moved means the scorer and the
published result disagree. That is what the check exists to catch, and it
stops the run: a port verified against a bundle the scorer no longer
reproduces is verified against nothing.

A key the bundle does not carry at all means a field was added to the
scorer since the last export. Nothing disagrees; the bundle is simply
behind, and the fix is to re-export. Treating that as a disagreement
would have reported all eight recorded runs as stale the moment
true_positive_reachability was added, which is loud, wrong, and exactly
the kind of noise that teaches people to ignore a check. The two are
reported separately, and only the first is a failure.

    .venv/bin/python -m scripts.verify_js_scoring

The interpreter is enforced for the same reason as scripts/verify_js_tools:
see _check_pinned_versions there. Nothing here recomputes a float, so the
numpy pin does not bite, but running the two harnesses under different
interpreters is a trap worth closing.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from agent.answer_key import (  # noqa: E402
    CANARY, HARD_NEGATIVES, OUT_OF_SCOPE, TRUE_POSITIVES, score,
)
from scripts.verify_js_tools import _check_pinned_versions  # noqa: E402

OUT = ROOT / "verify" / "scoring_cases.json"
SCORING = ROOT / "docs" / "data" / "scoring.json"
TOOLS = ROOT / "docs" / "data" / "tools"


def _feature_lists() -> dict[str, list[str]]:
    """Each variant's model features, from the exported SHAP ranking.

    The same list the browser reads, so a reachability disagreement is
    the port's and not a difference in what the two were told.
    """
    out = {}
    for variant in ("layer1", "canary"):
        path = TOOLS / variant / "shap_global.json"
        out[variant] = [r["feature"] for r in json.loads(path.read_text())]
    return out


def _synthetic() -> list[dict]:
    """Cases for the paths the recorded runs never take."""
    tp = sorted(TRUE_POSITIVES)
    hn = sorted(HARD_NEGATIVES)
    oos = sorted(OUT_OF_SCOPE)
    canary = sorted(CANARY)

    cases = [
        ("empty", [], None),
        ("empty, canary present", [], True),
        ("empty, canary absent", [], False),

        # Canary, all three states, with and without the planted column.
        ("canary caught", canary, True),
        ("canary missed", [hn[0]], True),
        ("canary not applicable", [hn[0]], False),
        ("canary unstated", [hn[0]], None),

        # Out of scope: removed before scoring, counts neither way.
        ("out of scope alone", oos, False),
        ("out of scope with a true positive", [oos[0], tp[0]], True),
        ("both out-of-scope columns", oos, True),

        # Hard negatives, raw and through a derivative.
        ("hard negative, raw", [hn[0]], False),
        ("hard negatives, several", hn[:4], False),
        ("hard negative via was_missing", [hn[0] + "_was_missing"], False),
        ("hard negative raw and derived together",
         [hn[0], hn[0] + "_was_missing"], False),
        ("every hard negative's missingness twin",
         [c + "_was_missing" for c in hn], False),

        # One-hot derivatives. No family is itself graded, so these resolve
        # to an ungraded parent and stay false positives — the case that
        # proves resolution never adds a column to a set.
        ("one-hot value, ungraded family", ["home_ownership_RENT"], False),
        ("one-hot value of every family",
         ["home_ownership_RENT", "verification_status_Verified",
          "purpose_car", "initial_list_status_w",
          "application_type_Joint App", "disbursement_method_Cash",
          "addr_state_CA"], False),

        # True positives, including the tier breakdown and the clean set.
        ("one true positive", [tp[0]], True),
        ("every true positive", tp, True),
        ("true positive via was_missing", [tp[0] + "_was_missing"], True),
        ("true positive raw and derived", [tp[0], tp[0] + "_was_missing"], True),

        # Input hygiene: whitespace, duplicates, empties, order.
        ("duplicates collapse", [hn[0], hn[0], hn[0]], False),
        ("whitespace stripped", [f"  {hn[0]}  "], False),
        ("empty and blank entries dropped", ["", "   ", hn[0]], False),
        ("order preserved for first occurrence", [hn[1], hn[0], hn[1]], False),

        # Unknown names are false positives, not errors.
        ("unknown column", ["no_such_column_anywhere"], False),
        ("unknown with a was_missing suffix", ["no_such_column_was_missing"], False),
        ("suffix alone", ["_was_missing"], False),
        ("mixed bag",
         [tp[0], hn[0], oos[0], "no_such_column", hn[1] + "_was_missing"], True),
    ]
    # Reachability is checked against the variant a case implies: a case
    # stating the canary was present is scored against the 181-feature
    # list, one stating it was absent against the 180-feature one, and a
    # case that does not say passes no list at all so the port must
    # report reachability unknown.
    return [{"name": name, "flags": flags, "canary_present": present,
             "variant": None if present is None else ("canary" if present else "layer1")}
            for name, flags, present in cases]


def _recorded() -> list[dict]:
    """The scored runs from the published bundle, replayed."""
    if not SCORING.is_file():
        raise SystemExit(
            f"{SCORING.relative_to(ROOT)} is missing. Run "
            f"scripts/export_site_bundle first; the recorded cases are read "
            f"from the published bundle so that the harness tests what the "
            f"browser will actually be given.")
    bundle = json.loads(SCORING.read_text())
    index = json.loads((ROOT / "docs" / "data" / "runs" / "index.json").read_text())
    present_by_label = {r["label"]: r["canary"]["present"] for r in index["runs"]}

    out = []
    for run in bundle["runs"]:
        if not run.get("scored"):
            continue
        label = run["label"]
        out.append({
            "name": f"recorded: {label}",
            "flags": [f["flag"] for f in run["flags"]],
            "canary_present": present_by_label[label],
            "variant": "canary" if present_by_label[label] else "layer1",
            # The score the published bundle carries for this run. The port
            # must reproduce it from the flags alone.
            "published_score": run["score"],
        })
    return out


def main() -> None:
    _check_pinned_versions("scoring_cases.json")

    features = _feature_lists()
    cases = []
    for case in _synthetic() + _recorded():
        variant = case.get("variant")
        result = score(case["flags"], canary_present=case["canary_present"],
                       model_columns=features[variant] if variant else None)
        entry = {
            "name": case["name"],
            "flags": case["flags"],
            "canary_present": case["canary_present"],
            "variant": case.get("variant"),
            "result": result,
        }
        if "published_score" in case:
            # A third party in the comparison: Python now, Python at export
            # time, and the JavaScript port. If these two disagree the
            # bundle is stale, which is a different fault from a bad port
            # and the harness should not report it as one.
            published = case["published_score"]
            entry["published_score"] = published
            # A key the published bundle does not carry is a field added
            # since it was exported, which is a re-export waiting to
            # happen and not a disagreement. A key it does carry whose
            # value has moved is a disagreement, and is what this guard
            # exists to catch. The two are reported separately.
            entry["fields_added_since_export"] = sorted(
                k for k in result if k not in published)
            entry["matches_published"] = all(
                result[k] == v for k, v in published.items())
        cases.append(entry)

    stale = [c["name"] for c in cases
             if "matches_published" in c and not c["matches_published"]]
    added = sorted({k for c in cases for k in c.get("fields_added_since_export", [])})

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(
        {"generated_by": "scripts/verify_js_scoring.py",
         "case_count": len(cases),
         "synthetic_count": len(_synthetic()),
         "recorded_count": len(cases) - len(_synthetic()),
         "stale_against_published": stale,
         "fields_added_since_export": added,
         "cases": cases}, indent=1, ensure_ascii=False, allow_nan=False) + "\n")

    print(f"wrote {len(cases)} cases to {OUT.relative_to(ROOT)} "
          f"({OUT.stat().st_size:,} bytes)")
    if stale:
        raise SystemExit(
            "The scorer no longer reproduces the published bundle for: "
            + ", ".join(stale)
            + ". Re-export before trusting the port against these cases.")
    if added:
        print(f"  new since the last export, re-export to publish: {', '.join(added)}")
    print("  every recorded case reproduces the published score on every "
          "field that bundle carries")


if __name__ == "__main__":
    main()
