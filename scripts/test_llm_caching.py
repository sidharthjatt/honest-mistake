"""Tests for prompt caching in agent/llm.py and the ledger in agent/ledger.py.

Run:
    .venv/bin/python scripts/test_llm_caching.py

Three guarantees are part of the suite.

No network call is made. anthropic.Anthropic is replaced before anything
runs, and the last check fails the suite if it was ever constructed. The
real-path tests use a fake client passed in through llm._client.

No REAL record is read. An audit hook records every file opened under
outputs/agent_runs/, and the suite fails if any lies outside a __MOCK__
directory.

The real ledger is never written. Every ledger test points LEDGER_PATH at a
temporary file, and the real file's state is compared before and after.
"""

import copy
import json
import os
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
RUNS = ROOT / "outputs" / "agent_runs"

OPENED_RUN_FILES: set[str] = set()


def _audit(event, args):
    if event == "open" and args and isinstance(args[0], (str, bytes, os.PathLike)):
        path = os.path.abspath(os.fsdecode(args[0]))
        if path.startswith(str(RUNS) + os.sep):
            OPENED_RUN_FILES.add(path)


sys.addaudithook(_audit)

import anthropic  # noqa: E402

CLIENTS_BUILT = []


class _NoClient:
    def __init__(self, *a, **k):
        CLIENTS_BUILT.append(1)
        raise RuntimeError("the test suite must not build a real client")


anthropic.Anthropic = _NoClient

from agent import agent as loop  # noqa: E402
from agent import data_dictionary, ledger, llm, run_audit  # noqa: E402
from agent.prompts import build_system_prompt  # noqa: E402
from agent.tools import TOOL_SCHEMAS, ToolLayer  # noqa: E402

PASSED, FAILED = [], []


def check(name, cond, detail=None):
    if cond:
        PASSED.append(name)
        print(f"  ok    {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name}" + (f"  {detail}" if detail is not None else ""))


def _stat(path):
    return (path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None


REAL_LEDGER = ledger.LEDGER_PATH
REAL_LEDGER_BEFORE = _stat(REAL_LEDGER)
TMP = tempfile.TemporaryDirectory()
TMPDIR = Path(TMP.name)

SYSTEM = build_system_prompt(20, 70)
MOCKS = sorted(p for p in RUNS.iterdir() if p.is_dir() and "__MOCK__" in p.name)


def strip_markers(obj):
    if isinstance(obj, dict):
        return {k: strip_markers(v) for k, v in obj.items() if k != "cache_control"}
    if isinstance(obj, list):
        return [strip_markers(v) for v in obj]
    return obj


def marker_locations(obj, where=()):
    found = []
    if isinstance(obj, dict):
        if "cache_control" in obj:
            found.append(where)
        for k, v in obj.items():
            found += marker_locations(v, where + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            found += marker_locations(v, where + (i,))
    return found


def normalised(messages):
    return [{**m, "content": [{"type": "text", "text": m["content"]}]
             if isinstance(m["content"], str) else m["content"]}
            for m in messages]


def user_prefixes(messages):
    return [messages[:i + 1] for i, m in enumerate(messages) if m["role"] == "user"]


def check_moving_request(req, sent_messages, tag):
    """Every structural claim the design makes about one cached request."""
    ok = True
    sys_blocks = req["system"]
    ok &= (isinstance(sys_blocks, list) and len(sys_blocks) == 1
           and sys_blocks[0] == {"type": "text", "text": SYSTEM})
    ok &= req.get("tools") == TOOL_SCHEMAS and llm.count_breakpoints(req["tools"]) == 0
    locations = marker_locations({"system": req["system"], "tools": req.get("tools", []),
                                  "messages": req["messages"]})
    last = len(req["messages"]) - 1
    last_block = len(req["messages"][-1]["content"]) - 1
    ok &= locations == [("messages", last, "content", last_block)]
    ok &= len(locations) <= llm.MAX_BREAKPOINTS
    ok &= req["messages"][-1]["role"] == "user"
    ok &= req["messages"][-1]["content"][-1]["cache_control"] == {"type": "ephemeral"}
    ok &= req["messages"][-1]["content"][-1]["type"] in ("text", "tool_result")
    ok &= all(isinstance(m["content"], list) and all(isinstance(b, dict) for b in m["content"])
              for m in req["messages"])
    ok &= strip_markers(req["messages"]) == normalised(sent_messages)
    if not ok:
        print(f"        detail {tag}: markers at {locations}")
    return ok


# ======================================================================
print("\n[1] caching off builds the Layer 2 request unchanged")
msgs = json.loads((MOCKS[0] / "messages.json").read_text())["messages"]
all_same = True
for prefix in user_prefixes(msgs):
    kw = llm.build_request(prefix, TOOL_SCHEMAS, SYSTEM, llm.CACHE_OFF)
    expected = dict(model="claude-sonnet-5", max_tokens=12_400,
                    thinking={"type": "adaptive", "display": "summarized"},
                    system=SYSTEM, messages=prefix, tools=TOOL_SCHEMAS)
    all_same &= (kw == expected and list(kw) == list(expected)
                 and kw["messages"] is prefix and kw["system"] is SYSTEM
                 and llm.count_breakpoints(kw) == 0)
check("off: same keys, order, values and objects as the eb89b98 construction, no markers", all_same)
check("off: default mode of build_request and call_llm is off",
      llm.build_request(msgs[:1], TOOL_SCHEMAS, SYSTEM) ==
      llm.build_request(msgs[:1], TOOL_SCHEMAS, SYSTEM, llm.CACHE_OFF))
check("off: no tools key when tools are empty", "tools" not in llm.build_request(msgs[:1], [], SYSTEM))

# ======================================================================
print("\n[2] moving breakpoint on every user turn of every MOCK record")
checked = 0
for run_dir in MOCKS:
    msgs = json.loads((run_dir / "messages.json").read_text())["messages"]
    before = copy.deepcopy(msgs)
    prefixes = user_prefixes(msgs)
    reqs = [llm.build_request(p, TOOL_SCHEMAS, SYSTEM, llm.CACHE_MOVING) for p in prefixes]
    structure = all(check_moving_request(r, p, run_dir.name) for r, p in zip(reqs, prefixes))
    checked += len(reqs)
    stable = all(
        json.dumps(strip_markers(b["messages"])[:len(a["messages"])])
        == json.dumps(strip_markers(a["messages"]))
        and json.dumps(a["system"]) == json.dumps(b["system"])
        and json.dumps(a["tools"]) == json.dumps(b["tools"])
        for a, b in zip(reqs, reqs[1:]))
    name = run_dir.name.split("__")[-1]
    check(f"{name}: {len(reqs)} requests well formed, one marker on the last user block", structure)
    check(f"{name}: each request, markers removed, is a byte prefix of the next", stable)
    check(f"{name}: record not modified and carries no marker",
          msgs == before and llm.count_breakpoints(msgs) == 0)
check("requests checked across MOCK records is non-zero", checked > 0, checked)

# ======================================================================
print("\n[3] mock loop end to end, both modes, requests captured as built")
data_dictionary.mark_retrieval_unavailable()
_orig_build = llm.build_request
captured = []


def _capturing_build(*a, **k):
    req = _orig_build(*a, **k)
    captured.append((copy.deepcopy(req), copy.deepcopy(a[0])))
    return req


llm.build_request = _capturing_build
histories = {}
for mode in llm.CACHE_MODES:
    llm.reset_mock()
    captured.clear()
    run = loop.run_audit(ToolLayer(cache_dir=ROOT / "outputs" / "agent_cache"),
                         mock=True, cache=mode)
    histories[mode] = json.dumps(run.messages)
    check(f"{mode}: one request built per turn ({run.turns} turns)", len(captured) == run.turns,
          (len(captured), run.turns))
    check(f"{mode}: usage is fixture zeros", all(v == 0 for v in run.usage.values()), run.usage)
    check(f"{mode}: stored history carries no marker", llm.count_breakpoints(run.messages) == 0)
    if mode == llm.CACHE_MOVING:
        check(f"{mode}: every built request passes the structure checks",
              all(check_moving_request(r, sent, f"loop turn {i}")
                  for i, (r, sent) in enumerate(captured, start=1)))
        check(f"{mode}: never more than {llm.MAX_BREAKPOINTS} breakpoints",
              max(llm.count_breakpoints(r) for r, _ in captured) <= llm.MAX_BREAKPOINTS)
    else:
        check(f"{mode}: every built request has a string system and no marker",
              all(isinstance(r["system"], str) and llm.count_breakpoints(r) == 0
                  for r, _ in captured))
llm.build_request = _orig_build
check("both modes produce the same mock conversation", histories[llm.CACHE_OFF] == histories[llm.CACHE_MOVING])

# ======================================================================
print("\n[4] requests the builder refuses")


def raises(fn, exc=ValueError):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


one = [{"role": "user", "content": "hi"}]
check("unknown cache mode", raises(lambda: llm.build_request(one, TOOL_SCHEMAS, SYSTEM, "on")))
check("cached request ending on an assistant turn",
      raises(lambda: llm.build_request(one + [{"role": "assistant", "content": "x"}],
                                       TOOL_SCHEMAS, SYSTEM, llm.CACHE_MOVING)))
check("cached request whose last user turn is empty",
      raises(lambda: llm.build_request([{"role": "user", "content": []}],
                                       TOOL_SCHEMAS, SYSTEM, llm.CACHE_MOVING)))


def history_with(n_markers):
    h = []
    for i in range(n_markers):
        h += [{"role": "user", "content": [{"type": "text", "text": f"u{i}",
                                            "cache_control": {"type": "ephemeral"}}]},
              {"role": "assistant", "content": [{"type": "text", "text": f"a{i}"}]}]
    return h + [{"role": "user", "content": "last"}]


check("three stray markers plus the moving one is accepted at four",
      llm.count_breakpoints(llm.build_request(history_with(3), TOOL_SCHEMAS, SYSTEM,
                                              llm.CACHE_MOVING)) == 4)
check("four stray markers plus the moving one is refused at five",
      raises(lambda: llm.build_request(history_with(4), TOOL_SCHEMAS, SYSTEM, llm.CACHE_MOVING)))
check("a request over the limit is refused on the off path too",
      raises(lambda: llm.build_request(history_with(5), TOOL_SCHEMAS, SYSTEM, llm.CACHE_OFF)))

# ======================================================================
print("\n[5] ledger arithmetic on temporary files")
M = "claude-sonnet-5"
close = lambda a, b: abs(a - b) < 1e-12  # noqa: E731
check("run7-sized uncached usage costs 303,979 x $2 + 18,754 x $10 per MTok",
      close(ledger.cost_usd(M, {"input": 303_979, "output": 18_754}), 0.607958 + 0.18754))
check("each usage field priced at its own rate",
      close(ledger.cost_usd(M, {"input": 100, "cache_creation": 1000, "cache_read": 10_000,
                                "output": 10}), (200 + 2500 + 2000 + 100) / 1e6))
check("worst case prices all input as a write and the full max_tokens",
      close(ledger.worst_case_usd(M, 3482, 12_400), (3482 * 2.5 + 12_400 * 10) / 1e6))
check("unknown model has no rates and is refused", raises(lambda: ledger.cost_usd("other", {}),
                                                         ledger.BudgetExceeded))
lp = TMPDIR / "ledger_a.jsonl"
check("missing ledger means zero spent", ledger.spent_usd(lp) == 0.0)
ledger.record(M, {"input": 1_000_000}, "off", "t1", path=lp)
e2 = ledger.record(M, {"output": 100_000}, "moving-breakpoint", "t2", path=lp)
check("two records sum, with a running cumulative figure",
      close(ledger.spent_usd(lp), 3.0) and close(e2["cumulative_usd"], 3.0)
      and len(lp.read_text().splitlines()) == 2)
lp_cap = TMPDIR / "ledger_cap.jsonl"
lp_cap.write_text(json.dumps({"cost_usd": 14.5}) + "\n")
check("a projection landing exactly on the cap is allowed",
      not raises(lambda: ledger.check(M, 0.5, path=lp_cap), ledger.BudgetExceeded))
check("a projection past the cap is refused",
      raises(lambda: ledger.check(M, 0.5001, path=lp_cap), ledger.BudgetExceeded))
lp_bad = TMPDIR / "ledger_bad.jsonl"
lp_bad.write_text(json.dumps({"cost_usd": 1.0}) + "\nnot json\n")
check("an unreadable ledger line refuses instead of undercounting",
      raises(lambda: ledger.spent_usd(lp_bad), ledger.BudgetExceeded))

# ======================================================================
print("\n[6] real path through a fake client, no network")


class Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump(self, exclude_none=True):
        return dict(self.__dict__)


class FakeMessages:
    def __init__(self, count, fail_count=False):
        self.count, self.fail_count = count, fail_count
        self.counted, self.created = [], []

    def count_tokens(self, **kw):
        self.counted.append(kw)
        if self.fail_count:
            raise RuntimeError("count failed")
        return SimpleNamespace(input_tokens=self.count)

    def create(self, **kw):
        self.created.append(kw)
        return SimpleNamespace(
            content=[Block(type="text", text="ready")], stop_reason="end_turn",
            usage=SimpleNamespace(input_tokens=12, output_tokens=5,
                                  cache_creation_input_tokens=0, cache_read_input_tokens=3480))


def use_fake(count, fail_count=False, ledger_file=None, prior=None):
    fake = SimpleNamespace(messages=FakeMessages(count, fail_count))
    llm._client = lambda: fake
    ledger.LEDGER_PATH = ledger_file
    ledger_file.write_text("" if prior is None else json.dumps({"cost_usd": prior}) + "\n")
    return fake.messages


_orig_client = llm._client

fm = use_fake(3482, ledger_file=TMPDIR / "real_a.jsonl")
reply = llm.call_llm(one, TOOL_SCHEMAS, SYSTEM, cache=llm.CACHE_MOVING, label="fake")
sent = llm.build_request(one, TOOL_SCHEMAS, SYSTEM, llm.CACHE_MOVING)
check("room under the cap: exactly one request sent, built by build_request",
      len(fm.created) == 1 and fm.created[0] == sent)
check("the count was taken on the same request minus max_tokens",
      len(fm.counted) == 1 and fm.counted[0] == {k: v for k, v in sent.items() if k != "max_tokens"})
lines = [json.loads(x) for x in (TMPDIR / "real_a.jsonl").read_text().splitlines()]
check("one ledger line with the returned usage and its cost",
      len(lines) == 1 and lines[0]["usage"] == {"input": 12, "output": 5, "cache_creation": 0,
                                                "cache_read": 3480}
      and close(lines[0]["cost_usd"], round((12 * 2 + 3480 * 0.2 + 5 * 10) / 1e6, 6))
      and lines[0]["cache"] == llm.CACHE_MOVING and lines[0]["label"] == "fake")
check("usage returned to the caller matches the ledger", reply["usage"] == lines[0]["usage"])

fm = use_fake(3482, ledger_file=TMPDIR / "real_b.jsonl", prior=14.99)
check("near the cap: refused with BudgetExceeded",
      raises(lambda: llm.call_llm(one, TOOL_SCHEMAS, SYSTEM, cache=llm.CACHE_MOVING),
             ledger.BudgetExceeded))
check("near the cap: nothing sent, ledger unchanged",
      fm.created == [] and len((TMPDIR / "real_b.jsonl").read_text().splitlines()) == 1)

fm = use_fake(3482, fail_count=True, ledger_file=TMPDIR / "real_c.jsonl")
check("count failure: the call raises", raises(lambda: llm.call_llm(one, TOOL_SCHEMAS, SYSTEM),
                                               RuntimeError))
check("count failure: nothing sent, nothing recorded",
      fm.created == [] and (TMPDIR / "real_c.jsonl").read_text() == "")

fm = use_fake(3482, ledger_file=TMPDIR / "real_d.jsonl", prior=14.99)
run = loop.run_audit(ToolLayer(cache_dir=ROOT / "outputs" / "agent_cache"), mock=False,
                     cache=llm.CACHE_MOVING)
check("loop: refused first request ends the run as budget_cap with no turn taken",
      run.termination == loop.BUDGET_CAP and run.turns == 0 and fm.created == [],
      (run.termination, run.turns))

fm = use_fake(3482, ledger_file=TMPDIR / "real_e.jsonl", prior=14.99)
_saved = (run_audit._preflight, run_audit._require_api_key, run_audit.print_real_run_warning)
run_audit._preflight = lambda *a, **k: None
run_audit._require_api_key = lambda: None
run_audit.print_real_run_warning = lambda *a, **k: None
dirs_before = sorted(p.name for p in RUNS.iterdir())
try:
    run_audit.main(["--real", "--cache", llm.CACHE_MOVING])
    refused, message = False, ""
except SystemExit as exc:
    refused, message = True, str(exc)
run_audit._preflight, run_audit._require_api_key, run_audit.print_real_run_warning = _saved
check("run_audit: a real run over the cap is refused at start",
      refused and "Refused" in message and fm.created == [], message)
check("run_audit: the refused run left no run directory",
      sorted(p.name for p in RUNS.iterdir()) == dirs_before)

llm._client = _orig_client
ledger.LEDGER_PATH = REAL_LEDGER

# ======================================================================
print("\n[7] guarantees")
outside = sorted(p for p in OPENED_RUN_FILES if "__MOCK__" not in p)
check("every run file opened lies under a __MOCK__ directory", not outside, outside[:5])
check("the hook observed MOCK record reads, so it was live", len(OPENED_RUN_FILES) > 0)
check("no real anthropic client was constructed", CLIENTS_BUILT == [])
check("the real ledger file was not created or modified", _stat(REAL_LEDGER) == REAL_LEDGER_BEFORE,
      (REAL_LEDGER_BEFORE, _stat(REAL_LEDGER)))

TMP.cleanup()
print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
if FAILED:
    print("FAILED:", *FAILED, sep="\n  ")
sys.exit(1 if FAILED else 0)
