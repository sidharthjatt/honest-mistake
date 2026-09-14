"""Mock checks for the Phase 4 runner and spec-request path.

Run:
    .venv/bin/python scripts/test_phase4_mock.py

No network call is made: anthropic.Anthropic is replaced before anything
runs, and the suite fails if it was ever constructed. Every request goes
through agent.llm.call_llm with a mock client, so the request builder, the
token count and the ledger are the real code. The real ledger is never
written, and the real Phase 4 run directory is compared before and after.
"""

import copy
import hashlib
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import anthropic  # noqa: E402

CLIENTS_BUILT = []


class _NoClient:
    def __init__(self, *a, **k):
        CLIENTS_BUILT.append(1)
        raise RuntimeError("the test suite must not build a real client")


anthropic.Anthropic = _NoClient

from agent import ledger, llm  # noqa: E402
from agent.tools import TOOL_SCHEMAS, ToolLayer  # noqa: E402
from layer3 import phase4  # noqa: E402
from layer3.phase4 import (MockClient, ParseError, mocked, parse_detector_output,  # noqa: E402
                           parse_spec_output, scripted)
from scripts import run_phase4  # noqa: E402

PASSED, FAILED = [], []


def check(name, cond, detail=None):
    (PASSED if cond else FAILED).append(name)
    print(f"  {'ok  ' if cond else 'FAIL'}  {name}" + ("" if cond or detail is None else f"  {detail}"))


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def _stat(path):
    return (path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None


def _listing(path):
    return sorted(p.name for p in path.iterdir()) if path.exists() else None


REAL_LEDGER_BEFORE = _stat(ledger.REAL_LEDGER) if hasattr(ledger, "REAL_LEDGER") else _stat(phase4.REAL_LEDGER)
RUNS_BEFORE = _listing(phase4.RUNS_DIR)
TMP = tempfile.TemporaryDirectory()
TMPDIR = Path(TMP.name)
DOC = (ROOT / "PREREGISTRATION_PHASE4.md").read_text()
DET_TEXT = phase4.DETECTOR_PROMPT.read_text(encoding="utf-8")
SPEC_TEXT = phase4.SPEC_PROMPT.read_text(encoding="utf-8")
EPHEMERAL = {"type": "ephemeral"}


def thinking(sig):
    return {"type": "thinking", "thinking": "mock", "signature": sig}


def tool_use(i, name="get_shap_ranking", args=None):
    return {"type": "tool_use", "id": f"toolu_t{i}", "name": name, "input": args or {"top_n": 1}}


def text(t):
    return {"type": "text", "text": t}


VALID = json.dumps({"label": "not_answerable",
                    "calls": [{"tool": "get_shap_ranking", "arguments": {"top_n": 1}, "field": "ranking"}],
                    "difference_or_missing": "Mock."})


def ledger_file(name, prior=None):
    path = TMPDIR / name
    path.write_text("" if prior is None else json.dumps({"cost_usd": prior}) + "\n")
    return path


def lines(path):
    return [x for x in path.read_text().splitlines() if x.strip()]


# ======================================================================
print("\n[1] prompts and questions against the document")
check("detector prompt hashes to A3's value",
      hashlib.sha256(phase4.DETECTOR_PROMPT.read_bytes()).hexdigest() == phase4.DETECTOR_SHA256)
check("spec prompt hashes to A3's value",
      hashlib.sha256(phase4.SPEC_PROMPT.read_bytes()).hexdigest() == phase4.SPEC_SHA256)
check("both hashes are the ones written in PREREGISTRATION_PHASE4.md",
      phase4.DETECTOR_SHA256 in DOC and phase4.SPEC_SHA256 in DOC)
check("load_prompt returns the file's text unchanged",
      phase4.load_prompt(phase4.DETECTOR_PROMPT, phase4.DETECTOR_SHA256) == DET_TEXT)
tampered = TMPDIR / "tampered.txt"
tampered.write_bytes(phase4.DETECTOR_PROMPT.read_bytes() + b" ")
check("a prompt changed by one byte is refused",
      raises(lambda: phase4.load_prompt(tampered, phase4.DETECTOR_SHA256), phase4.PromptMismatch))
check("26 questions: 9 + 6 + 7 + 4", len(phase4.QUESTIONS) == 26
      and [sum(k.startswith(p) for k in phase4.QUESTIONS) for p in ("A", "B", "C", "NM")] == [9, 6, 7, 4])
missing = [k for k, q in phase4.QUESTIONS.items() if q not in DOC]
check("every question appears word for word in the document", not missing, missing)
check("question_text removes code formatting and nothing else",
      phase4.question_text("A3") == "What is all_util's standalone ROC-AUC within 2014?"
      and phase4.question_text("NM3") == phase4.QUESTIONS["NM3"]
      and all("`" not in phase4.question_text(k) for k in phase4.QUESTIONS))
check("pilot items exist", all(k in phase4.QUESTIONS for k in ("A1", "C3", "B2", "NM3")))

# ======================================================================
print("\n[2] detection request built as A3 describes, through call_llm")
lp = ledger_file("ledger_shape.jsonl")
client = MockClient([
    scripted([thinking("sig-1"), tool_use(1)], "tool_use", output=700, cache_creation=2500),
    scripted([thinking("sig-2"), text(VALID)], "end_turn", output=400, cache_creation=2200, cache_read=2500),
])
with mocked(client, lp):
    ep = phase4.run_detection("A3", ToolLayer(), "mock-shape")
q = phase4.question_text("A3")
r1, r2 = client.created
check("two requests sent, two ledger lines written", len(client.created) == 2 and len(lines(lp)) == 2)
check("model, max_tokens and thinking are llm.py's",
      r1["model"] == "claude-sonnet-5" and r1["max_tokens"] == 12_400 and r1["thinking"] == llm.THINKING)
check("system is one text block holding the detector prompt exactly",
      r1["system"] == [{"type": "text", "text": DET_TEXT}]
      and hashlib.sha256(r1["system"][0]["text"].encode("utf-8")).hexdigest() == phase4.DETECTOR_SHA256)
check("tools are the eight schemas, unchanged", r1["tools"] == TOOL_SCHEMAS)
check("first message is the question alone, one text block, one marker",
      r1["messages"] == [{"role": "user", "content": [{"type": "text", "text": q, "cache_control": EPHEMERAL}]}])
check("exactly one breakpoint in each request", all(llm.count_breakpoints(r) == 1 for r in client.created))
check("each request equals build_request's output for the same history",
      r1 == llm.build_request([{"role": "user", "content": q}], TOOL_SCHEMAS, DET_TEXT, llm.CACHE_MOVING))
check("the count was taken on each request minus max_tokens",
      client.counted == [{k: v for k, v in r.items() if k != "max_tokens"} for r in client.created])
expected_result = json.dumps(ToolLayer().dispatch("get_shap_ranking", {"top_n": 1}), default=str)
check("second request echoes the thinking block and tool call unchanged",
      r2["messages"][1] == {"role": "assistant", "content": [thinking("sig-1"), tool_use(1)]})
check("second request carries the real tool result, marker on its last block",
      r2["messages"][2] == {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "toolu_t1",
                                                         "content": expected_result, "cache_control": EPHEMERAL}]})
check("stored history carries no marker", llm.count_breakpoints(ep.messages) == 0)
check("episode completed, parsed, with turns and output per turn recorded",
      ep.termination == "completed" and ep.output == json.loads(VALID) and ep.turns == 2
      and ep.tool_calls == 1 and ep.output_tokens_per_turn == [700, 400], ep.summary())
ledger_rows = [json.loads(x) for x in lines(lp)]
check("ledger lines carry the label, the cache mode and each reply's usage",
      [x["usage"]["output"] for x in ledger_rows] == [700, 400]
      and all(x["label"] == "mock-shape" and x["cache"] == llm.CACHE_MOVING for x in ledger_rows))
check("episode cost equals the sum of its ledger lines",
      abs(ep.cost_usd - sum(x["cost_usd"] for x in ledger_rows)) < 2e-6)

# ======================================================================
print("\n[3] spec request built as A4 describes")
lp = ledger_file("ledger_spec.jsonl")
det_client = MockClient(phase4.fabricated_detection_replies(1))
with mocked(det_client, lp):
    ep_c3 = phase4.run_detection("C3", ToolLayer(), "mock-spec")
spec_client = MockClient([phase4.fabricated_spec_reply()])
with mocked(spec_client, lp):
    spec = phase4.run_spec_request(ep_c3, "mock-spec")
(sr,) = spec_client.created
expected_message = (f"Question: {phase4.question_text('C3')}\n\nCheck output:\n{ep_c3.final_text}\n\n"
                    f"Tool definitions:\n{json.dumps(TOOL_SCHEMAS)}")
check("system is one text block holding the spec prompt exactly",
      sr["system"] == [{"type": "text", "text": SPEC_TEXT}])
check("no tools are passed", "tools" not in sr)
check("one user message, exactly A4's template with the detector's raw text",
      sr["messages"] == [{"role": "user", "content": [{"type": "text", "text": expected_message,
                                                       "cache_control": EPHEMERAL}]}])
check("one breakpoint; thinking and model as llm.py",
      llm.count_breakpoints(sr) == 1 and sr["thinking"] == llm.THINKING and sr["model"] == llm.MODEL)
check("decline parsed; one more ledger line",
      spec.termination == "completed" and spec.output == {"decline": "Fabricated mock reply."}
      and len(lines(lp)) == 3)
answered = copy.copy(ep_c3)
answered.output = {"label": "answerable", "calls": [], "difference_or_missing": None}
before = len(spec_client.created)
check("no spec request for an item not labelled not_answerable",
      raises(lambda: phase4.run_spec_request(answered, "x"), ValueError) and len(spec_client.created) == before)
not_bc = copy.copy(ep_c3)
not_bc.item = "A1"
check("no spec request for an item outside parts b and c",
      raises(lambda: phase4.run_spec_request(not_bc, "x"), ValueError))

# ======================================================================
print("\n[4] the detector parser rejects malformed output rather than coercing it")


def obj(**over):
    base = json.loads(VALID)
    base.update(over)
    return json.dumps(base)


accepted = {
    "not_answerable": VALID,
    "answerable with null": obj(label="answerable", difference_or_missing=None),
    "with_difference": obj(label="answerable_with_difference"),
    "surrounding whitespace only": "\n  " + VALID + "\n",
}
for name, t in accepted.items():
    check(f"accepted: {name}", not raises(lambda t=t: parse_detector_output(t), ParseError)
          and parse_detector_output(t) == json.loads(t))
rejected = {
    "empty text": "",
    "whitespace only": "   ",
    "fenced in ```json": "```json\n" + VALID + "\n```",
    "leading prose": "Here is my answer: " + VALID,
    "trailing prose": VALID + "\nDone.",
    "two objects": VALID + VALID,
    "a list": "[" + VALID + "]",
    "a string": json.dumps(VALID),
    "extra key": obj(confidence=0.9),
    "missing key": json.dumps({"label": "not_answerable", "calls": json.loads(VALID)["calls"]}),
    "label wrong case": obj(label="Answerable"),
    "label not a value": obj(label="declared"),
    "label null": obj(label=None),
    "calls not a list": obj(calls={"tool": "get_shap_ranking"}),
    "calls empty": obj(calls=[]),
    "call extra key": obj(calls=[{"tool": "get_shap_ranking", "arguments": {}, "field": "x", "note": 1}]),
    "call missing field": obj(calls=[{"tool": "get_shap_ranking", "arguments": {}}]),
    "unknown tool": obj(calls=[{"tool": "read_file", "arguments": {}, "field": "x"}]),
    "arguments not an object": obj(calls=[{"tool": "get_shap_ranking", "arguments": "top_n=1", "field": "x"}]),
    "field empty": obj(calls=[{"tool": "get_shap_ranking", "arguments": {}, "field": " "}]),
    "null difference on not_answerable": obj(difference_or_missing=None),
    "empty difference on with_difference": obj(label="answerable_with_difference", difference_or_missing=""),
    "text difference on answerable": obj(label="answerable", difference_or_missing="x"),
    "NaN in output": VALID[:-1] + ', "n": NaN}',
}
for name, t in rejected.items():
    check(f"rejected: {name}", raises(lambda t=t: parse_detector_output(t), ParseError))

print("\n[5] the spec parser")
good_spec = {"spec": {"name": "get_x", "description": "d", "input_schema": {"type": "object", "properties": {}},
                      "data_source": "new precomputed artefact: a, b"}}
check("accepted: spec", parse_spec_output(json.dumps(good_spec)) == good_spec)
check("accepted: decline", parse_spec_output('{"decline": "no tool can"}') == {"decline": "no tool can"})
spec_rejected = {
    "both keys": json.dumps({**good_spec, "decline": "x"}),
    "neither key": json.dumps({"tool": good_spec["spec"]}),
    "fenced": "```\n" + json.dumps(good_spec) + "\n```",
    "empty decline": '{"decline": ""}',
    "spec missing data_source": json.dumps({"spec": {k: v for k, v in good_spec["spec"].items() if k != "data_source"}}),
    "spec extra key": json.dumps({"spec": {**good_spec["spec"], "code": "print(1)"}}),
    "input_schema not an object": json.dumps({"spec": {**good_spec["spec"], "input_schema": "object"}}),
    "trailing prose": json.dumps(good_spec) + " ok",
}
for name, t in spec_rejected.items():
    check(f"rejected: {name}", raises(lambda t=t: parse_spec_output(t), ParseError))

# ======================================================================
print("\n[6] terminations, and a malformed final reply is recorded, not repaired")


def episode_with(replies, item="B2", prior=None, name="t.jsonl"):
    path = ledger_file(name, prior)
    c = MockClient(replies)
    with mocked(c, path):
        e = phase4.run_detection(item, ToolLayer(), "mock-term")
    return e, c, path


e, c, p = episode_with([scripted([text("```json\n" + VALID + "\n```")], "end_turn")], name="bad.jsonl")
check("fenced final reply: completed, output None, parse error recorded",
      e.termination == "completed" and e.output is None and e.parse_error, e.summary())
e, c, p = episode_with([scripted([text(VALID), tool_use(1)], "tool_use"),
                        scripted([thinking("s")], "end_turn")], name="empty_final.jsonl")
check("an earlier turn's text never stands in for an empty final reply",
      e.termination == "completed" and e.output is None and e.parse_error == "the reply holds no text")
e, c, p = episode_with([scripted([tool_use(i)], "tool_use") for i in range(9)], name="turns.jsonl")
check("turn limit: 8 requests, no ninth, 8 ledger lines",
      e.termination == "turn_limit" and e.turns == 8 and len(c.created) == 8 and len(lines(p)) == 8
      and len(c.replies) == 1, e.summary())
e, c, p = episode_with([scripted([tool_use(i) for i in range(17)], "tool_use")], name="calls17.jsonl")
check("call limit in one turn: 17 requested, none executed",
      e.termination == "call_limit" and e.tool_calls == 0 and len(c.created) == 1)
e, c, p = episode_with([scripted([tool_use(i) for i in range(8)], "tool_use"),
                        scripted([tool_use(i) for i in range(8, 17)], "tool_use")], name="calls8_9.jsonl")
check("call limit across turns: 8 executed, then 9 more refused",
      e.termination == "call_limit" and e.tool_calls == 8 and e.turns == 2)
e, c, p = episode_with([scripted([text("partial")], "max_tokens")], name="trunc.jsonl")
check("max_tokens ends as truncated, nothing parsed", e.termination == "truncated" and e.output is None)
e, c, p = episode_with([scripted([text(VALID)], "refusal")], name="refusal.jsonl")
check("refusal ends as refusal even with valid JSON text", e.termination == "refusal" and e.output is None)

# ======================================================================
print("\n[7] the ledger refuses at the cap")
e, c, p = episode_with([scripted([text(VALID)], "end_turn")], prior=14.99, name="cap_first.jsonl")
check("refused before the first request: budget_cap, no turn, nothing sent, ledger unchanged",
      e.termination == "budget_cap" and e.turns == 0 and c.created == [] and len(lines(p)) == 1, e.summary())
# Worst case per request: 2,500 x $2.50 + 12,400 x $10 per MTok = $0.13025. The first
# reply costs $0.011254, so 14.865 passes the first check and fails the second.
first = scripted([tool_use(1)], "tool_use", input=2, output=500, cache_creation=2500)
e, c, p = episode_with([first, scripted([text(VALID)], "end_turn")], prior=14.865, name="cap_mid.jsonl")
check("refused mid-episode: one request sent and recorded, then budget_cap",
      e.termination == "budget_cap" and e.turns == 1 and len(c.created) == 1 and len(lines(p)) == 2, e.summary())
p = ledger_file("cap_spec.jsonl", prior=14.99)
sc = MockClient([phase4.fabricated_spec_reply()])
with mocked(sc, p):
    s = phase4.run_spec_request(ep_c3, "mock-cap")
check("spec request refused at the cap: budget_cap, nothing sent",
      s.termination == "budget_cap" and sc.created == [] and s.usage is None)
check("the mock context refuses the real ledger",
      raises(lambda: mocked(MockClient([]), phase4.REAL_LEDGER).__enter__(), ValueError))

# ======================================================================
print("\n[8] the command line in mock mode")
out = TMPDIR / "runs"
rc = run_phase4.main(["--mock", "--items", "A1,C3,B2,NM3", "--spec-items", "C3",
                      "--label", "phase4-mock-check", "--out", str(out)])
run_dirs = sorted(out.iterdir())
manifest = json.loads((run_dirs[0] / "manifest.json").read_text()) if run_dirs else {}
check("exit 0 and one __MOCK__ record", rc == 0 and len(run_dirs) == 1 and "__MOCK__" in run_dirs[0].name)
check("four episodes, each with turns and output per turn recorded",
      [x["item"] for x in manifest.get("episodes", [])] == ["A1", "C3", "B2", "NM3"]
      and all(x["turns"] == 2 and x["output_tokens_per_turn"] == [700, 400] for x in manifest["episodes"]))
check("one spec request for C3, a decline, and none for the others",
      [x["item"] for x in manifest["spec_requests"]] == ["C3"]
      and manifest["spec_requests"][0]["output"] == {"decline": "Fabricated mock reply."})
check("manifest records the prompt hashes, limits and model",
      manifest["prompts"] == {"detector_sha256": phase4.DETECTOR_SHA256, "spec_sha256": phase4.SPEC_SHA256}
      and manifest["limits"] == {"max_turns": 8, "max_tool_calls": 16} and manifest["model"] == llm.MODEL)
check("no mode named is refused", raises(lambda: run_phase4.main(["--items", "A1", "--label", "x"]), SystemExit))
check("an unknown item is refused",
      raises(lambda: run_phase4.main(["--mock", "--items", "Z9", "--label", "x", "--out", str(out)]), SystemExit))
check("a spec item outside the run is refused",
      raises(lambda: run_phase4.main(["--mock", "--items", "A1", "--spec-items", "C3", "--label", "x",
                                      "--out", str(out)]), SystemExit))
check("a spec item outside parts b and c is refused",
      raises(lambda: run_phase4.main(["--mock", "--items", "A1", "--spec-items", "A1", "--label", "x",
                                      "--out", str(out)]), SystemExit))

# ======================================================================
print("\n[9] guarantees")
check("no real anthropic client was constructed", CLIENTS_BUILT == [])
check("llm._client and the ledger path were restored",
      ledger.LEDGER_PATH == phase4.REAL_LEDGER and llm._client.__name__ == "_client")
check("the real ledger was not created or modified", _stat(phase4.REAL_LEDGER) == REAL_LEDGER_BEFORE)
check("the real Phase 4 run directory was not touched", _listing(phase4.RUNS_DIR) == RUNS_BEFORE)

TMP.cleanup()
print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
if FAILED:
    print("FAILED:", *FAILED, sep="\n  ")
sys.exit(1 if FAILED else 0)
