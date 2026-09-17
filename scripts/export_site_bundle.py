"""Export the static data bundle for the Honest Mistake site.

Writes JSON under docs/data/ and nothing else. It makes no network request
and needs no API key.

What it writes:
- bundle.json: provenance, what was stripped and why, what the bundle cannot
  carry, and the list of files.
- runs/index.json: the facts for each of the 12 real runs.
- runs/<label>.json: one replayable run, message by message, with each tool
  result joined to the call that produced it.
- scoring.json: the answer key's sets and every flag from every scorable run,
  with the verdict the scorer gave it.

The scoring export cannot be recomputed from a fresh clone.
agent/answer_key.py reads column names from data/processed/X_test.parquet,
which is not committed. So scoring.json is produced once, from the local
data, and the bundle records when, from which commit, and the hash of every
file the scoring was built from.

Verdicts are taken from the scorer's own output (agent.eval_canary.evaluate
and agent.answer_key.score), never re-derived here.

    .venv/bin/python -m scripts.export_site_bundle
"""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import re
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import agent.answer_key as ak  # noqa: E402
import agent.eval_canary as ec  # noqa: E402

RUNS_DIR = ROOT / "outputs" / "agent_runs"
LEDGER = ROOT / "outputs" / "ledger" / "layer3_spend.jsonl"
OUT = ROOT / "docs" / "data"

SCORING_SOURCES = [
    "outputs/leakage_drop_log.txt",
    "agent/data_dictionary.py",
    "agent/answer_key.py",
    "agent/eval_canary.py",
    "agent/prompts.py",
    "outputs/models/best_params_canary.json",
    "data/processed/X_test.parquet",
]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True,
                          text=True, check=True).stdout.strip()


def _label(directory: Path) -> str:
    return directory.name.split("__")[-1]


def _write(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=1, ensure_ascii=False) + "\n")


def _canary(manifest: dict, results: list[str]) -> dict:
    if "canary" in manifest:
        return {"present": bool(manifest["canary"]),
                "established_by": "manifest field 'canary'",
                "column": next(iter(ak.CANARY)) if manifest["canary"] else None}
    counts = sorted({int(n) for s in results
                     for n in re.findall(r'"total_features"\s*:\s*(\d+)', s)})
    present = None
    if counts == [180]:
        present = False
    elif counts == [181]:
        present = True
    return {
        "present": present,
        "established_by": ("derived: this manifest has no 'canary' field, so "
                           "presence is read from the feature count the run's "
                           "own tool results report (180 without the canary, "
                           "181 with it)"),
        "feature_counts_seen_in_tool_results": counts,
        "column": next(iter(ak.CANARY)) if present else None,
    }


def _run_file(directory: Path, run11_turn_usage: list[dict] | None) -> tuple[dict, dict, int]:
    msgs = json.loads((directory / "messages.json").read_text())["messages"]
    results, errors = {}, {}
    for m in msgs:
        if isinstance(m["content"], list):
            for b in m["content"]:
                if b.get("type") == "tool_result":
                    c = b.get("content")
                    results[b["tool_use_id"]] = c if isinstance(c, str) else json.dumps(c)
                    errors[b["tool_use_id"]] = bool(b.get("is_error", False))

    stripped_bytes = 0
    messages, unexecuted = [], 0
    for i, m in enumerate(msgs):
        blocks = []
        content = m["content"]
        if isinstance(content, str):
            blocks.append({"type": "text", "text": content})
        else:
            for b in content:
                t = b.get("type")
                if t == "thinking":
                    stripped_bytes += len(b.get("signature", ""))
                    blocks.append({"type": "thinking",
                                   "summary": b.get("thinking", ""),
                                   "summary_empty": not (b.get("thinking") or "").strip()})
                elif t == "text":
                    blocks.append({"type": "text", "text": b.get("text", "")})
                elif t == "tool_use":
                    has = b["id"] in results
                    unexecuted += not has
                    blocks.append({"type": "tool_call", "id": b["id"],
                                   "tool": b["name"], "arguments": b["input"],
                                   "result": results.get(b["id"]),
                                   "result_is_error": errors.get(b["id"]) if has else None,
                                   "executed": has})
                elif t == "tool_result":
                    blocks.append({"type": "tool_result_ref",
                                   "tool_use_id": b["tool_use_id"]})
                else:
                    blocks.append({"type": t, "note": "block type not expanded by the export"})
        messages.append({"index": i, "role": m["role"], "blocks": blocks})

    manifest = json.loads((directory / "manifest.json").read_text())
    label = _label(directory)
    refusal = ec.refusal_reason(manifest)
    facts = {
        "label": label,
        "directory": directory.name,
        "model": manifest.get("model"),
        "started": manifest.get("timestamp"),
        "finished": manifest.get("finished"),
        "canary": _canary(manifest, list(results.values())),
        "tool_layer_version": manifest.get("tool_layer_version"),
        "dictionary_populated_field": manifest.get("dictionary_populated_field"),
        "coverage_scopes": manifest.get("coverage_scopes"),
        "retrieval": manifest.get("retrieval"),
        "prompt_caching": manifest.get("prompt_caching"),
        "limits": manifest.get("limits"),
        "max_tokens_per_turn": manifest.get("max_tokens_per_turn"),
        "termination": manifest.get("termination"),
        "last_stop_reason": manifest.get("last_stop_reason"),
        "scorer_accepted": refusal is None,
        "scorer_refusal_reason": refusal,
        "turns": manifest.get("turns"),
        "tool_calls": manifest.get("tool_calls"),
        "usage_totals": manifest.get("usage"),
        "system_prompt_chars": manifest.get("system_prompt_chars"),
        "fields_not_in_manifest": sorted(
            k for k in ("canary", "coverage_scopes", "retrieval", "prompt_caching")
            if k not in manifest),
    }
    run = {
        "label": label,
        "facts": facts,
        "final_answer_text": (directory / "final_answer.txt").read_text(),
        "tool_calls_without_results": unexecuted,
        "ends_on_role": msgs[-1]["role"] if msgs else None,
        "per_turn_usage": run11_turn_usage,
        "per_turn_usage_note": (
            "From the Layer 3 spend ledger, which recorded one line per request "
            "for this run." if run11_turn_usage is not None else
            "Not recorded for this run: its manifest holds usage totals only."),
        "messages": messages,
    }
    return run, facts, stripped_bytes


def main() -> int:
    if not (ROOT / "data" / "processed" / "X_test.parquet").exists():
        print("data/processed/X_test.parquet is missing. The answer key cannot "
              "be built, so nothing is exported.")
        return 2

    ledger_run11 = [json.loads(l) for l in LEDGER.read_text().splitlines()
                    if l.strip() and json.loads(l).get("label") == "run11-honest-cached"]
    run11_usage = [{"request": n, "completed_at": r["timestamp"], **r["usage"],
                    "cost_usd": r["cost_usd"]}
                   for n, r in enumerate(sorted(ledger_run11, key=lambda r: r["timestamp"]), start=1)]

    directories = sorted(d for d in RUNS_DIR.iterdir() if d.is_dir() and "__REAL__" in d.name)
    index, stripped_total, scoring_runs = [], 0, []
    unexecuted_by_run = {}
    for d in directories:
        label = _label(d)
        run, facts, stripped = _run_file(d, run11_usage if label == "run11-honest-cached" else None)
        stripped_total += stripped
        unexecuted_by_run[label] = {"tool_calls_without_results": run["tool_calls_without_results"],
                                    "ends_on_role": run["ends_on_role"]}
        _write(OUT / "runs" / f"{label}.json", run)
        index.append(facts)

        with redirect_stdout(io.StringIO()):
            result = ec.evaluate(d, quiet=True)
        if result is None:
            scoring_runs.append({"label": label, "scored": False,
                                 "reason": facts["scorer_refusal_reason"],
                                 "flags": []})
            continue
        score, parsed = result["score"], result["parsed"]
        tp, fp = set(score["true_positives"]), set(score["false_positives"])
        oos = set(score.get("out_of_scope_flagged", []))
        hard = set(score.get("hard_negatives_flagged", []))
        derivs = {x["flag"]: x for x in score["derivative_resolutions"]}
        flags = []
        for rec in parsed.records:
            name = rec["FLAG"]
            if name in tp:
                verdict = "true_positive"
            elif name in fp:
                verdict = "false_positive"
            elif name in oos:
                verdict = "out_of_scope"
            else:
                verdict = "not_classified_by_scorer"
            flags.append({"flag": name, "reason": rec.get("REASON"),
                          "evidence": rec.get("EVIDENCE"),
                          "confidence": rec.get("CONFIDENCE"),
                          "verdict": verdict,
                          "hard_negative": name in hard,
                          "scored_as_parent": derivs.get(name)})
        scoring_runs.append({"label": label, "scored": True,
                             "parse_warnings": list(parsed.warnings),
                             "score": score, "flags": flags})

    _write(OUT / "runs" / "index.json", {"runs": index})

    scoring = {
        "true_positives": [{"column": c, **ak.RESIDUAL_TIMING_LEAK.get(c, {}),
                            "clean_under_suppression": c in ak.CLEAN_UNDER_SUPPRESSION}
                           for c in ak.TRUE_POSITIVES],
        "out_of_scope": ak.OUT_OF_SCOPE,
        "hard_negatives": ak.HARD_NEGATIVES,
        "tier_labels": ak.TIER_LABELS,
        "canary": ak.CANARY,
        "counts": {"true_positives": len(ak.TRUE_POSITIVES),
                   "out_of_scope": len(ak.OUT_OF_SCOPE),
                   "hard_negatives": len(ak.HARD_NEGATIVES)},
        # The two rules that let a flag be scored as the column it derives
        # from, so a browser port can resolve a flag the same way the Python
        # scorer does rather than guessing at the naming conventions. They
        # are read off the private names because making them public would
        # change answer_key.py, whose hash this bundle publishes, for a
        # rename that alters no behaviour.
        "derivative_rules": {
            "was_missing_suffix": ak._WAS_MISSING_SUFFIX,
            "one_hot_families": sorted(ak._ONE_HOT_FAMILIES),
            "note": ("A flag not itself in one of the three lists is scored "
                     "as its parent where it has one and the parent is "
                     "listed: NAME_was_missing resolves to NAME, and "
                     "FAMILY_value resolves to FAMILY for the families "
                     "above. Resolution never adds a column to a list."),
        },
        "runs": scoring_runs,
        "notes": [
            ("Each run's score is the scorer's own output, unchanged. Its "
             "score.canary block is per-run: 'applicable' is true only where "
             "the planted column was in that run's data. Where it is false "
             "nothing was planted, 'planted' and 'missed' are empty, and "
             "'detected' is null, because a run cannot miss a canary it was "
             "never given. 'detected' is false only where the canary was "
             "present and was not flagged. Whether the canary was present is "
             "also recorded in runs/index.json, under canary.present."),
            ("A flag's verdict is read from the scorer's lists: true_positives, "
             "false_positives and out_of_scope_flagged. hard_negative is true "
             "when the flag is in hard_negatives_flagged. scored_as_parent is "
             "the scorer's derivative_resolutions entry for that flag, or null."),
        ],
    }
    _write(OUT / "scoring.json", scoring)

    dirty = _git("status", "--porcelain", "--", "agent", "outputs/agent_runs",
                 "outputs/leakage_drop_log.txt", "outputs/models",
                 "outputs/ledger").splitlines()
    bundle = {
        "exported_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "exported_from_commit": _git("rev-parse", "HEAD"),
        "uncommitted_changes_in_source_paths": dirty,
        "export_script_sha256": _sha256(Path(__file__)),
        "scoring_sources_sha256": {p: _sha256(ROOT / p) for p in SCORING_SOURCES},
        "scoring_note": (
            "scoring.json was produced once, from local data. agent/answer_key.py "
            "reads column names from data/processed/X_test.parquet, which is not "
            "committed, so it cannot be recomputed from a fresh clone. The hashes "
            "above identify every file it was built from."),
        "stripped": {
            "fields": ["thinking[].signature"],
            "bytes_removed": stripped_total,
            "why": ("Opaque encoded blobs the API returns with each thinking "
                    "block, used when a conversation is continued on the same "
                    "model. A reader cannot use them. They were 43.6% of the "
                    "bytes of the runs' messages.json files."),
        },
        "reasoning_note": (
            "Thinking blocks hold summaries, not raw reasoning: the runner asked "
            "for summarised display (agent/llm.py, THINKING). In firstlight and "
            "run1 every thinking summary is empty in the record."),
        "cannot_carry": [
            {"what": "the system prompt text",
             "why": ("Manifests store only its length (system_prompt_chars). "
                     "Re-rendering it from the code at each run's commit would be "
                     "a reconstruction, not the record.")},
            {"what": "per-turn token usage for every run except run11-honest-cached",
             "why": ("Manifests hold totals only. The Layer 3 ledger recorded "
                     "run11's requests one by one, so only that run carries it.")},
            {"what": "tool results for calls in the final turn of stopped runs",
             "why": ("The run was stopped before those calls executed, so no "
                     "result exists."),
             "by_run": {k: v for k, v in unexecuted_by_run.items()
                        if v["tool_calls_without_results"]}},
            {"what": "a final answer turn for run9-honest-nopop",
             "why": ("It hit the turn limit after its last tool results were "
                     "returned, so no assistant turn follows them."),
             "ends_on_role": unexecuted_by_run.get("run9-honest-nopop", {}).get("ends_on_role")},
        ],
    }
    # Derived from a directory scan, not from what this script wrote: the
    # tool artefacts under tools/ come from export_tool_artefacts.py. So an
    # export redirected at an empty scratch directory produces a short list
    # and the diff shows sixteen entries vanishing, which is an artefact of
    # the scratch and not a change. This list can only be diffed from a real
    # export into docs/data.
    files = sorted(p for p in OUT.rglob("*.json") if p.name != "bundle.json")
    bundle["files"] = [str(p.relative_to(OUT)) for p in files] + ["bundle.json"]
    _write(OUT / "bundle.json", bundle)

    total = sum(p.stat().st_size for p in OUT.rglob("*.json"))
    zipped = sum(len(gzip.compress(p.read_bytes(), 9)) for p in OUT.rglob("*.json"))
    print(f"wrote {len(list(OUT.rglob('*.json')))} files under {OUT.relative_to(ROOT)}; "
          f"{total:,} bytes, {zipped:,} bytes gzipped per file; "
          f"{stripped_total:,} signature bytes stripped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
