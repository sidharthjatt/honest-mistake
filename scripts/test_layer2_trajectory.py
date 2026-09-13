"""Tests for scripts/layer2_trajectory.py. MOCK and synthetic records only.

Run:
    .venv/bin/python scripts/test_layer2_trajectory.py

Two guarantees are part of the suite, not scaffolding around it.

No REAL record is read. An audit hook installed before the module under test
is imported records every file opened under outputs/agent_runs/. The last
check fails the suite if any of those paths lies outside a __MOCK__
directory.

Expected values are not taken from the module under test. For mock-up they
come from the fixture design in agent/mock_replies.py, or from a separate
plain-json read of the record. Everything else is a synthetic record built
here.
"""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "outputs" / "agent_runs"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

OPENED_RUN_FILES: list[str] = []


def _record_run_file_opens(event, args):
    if event != "open":
        return
    try:
        path = str(args[0])
    except Exception:
        return
    if str(RUNS) in path or "/outputs/agent_runs/" in path:
        OPENED_RUN_FILES.append(path)


sys.addaudithook(_record_run_file_opens)

import layer2_trajectory as L  # noqa: E402

PASSED: list[str] = []
FAILED: list[str] = []


def check(name, cond, detail=""):
    (PASSED if cond else FAILED).append(name)
    tail = f"  -- {detail}" if (not cond and detail != "") else ""
    print(f"  {'PASS' if cond else 'FAIL'}  {name}{tail}")


def raises(fn, exc):
    try:
        fn()
    except exc:
        return True
    except Exception:
        return False
    return False


def raw(run_dir, fname):
    return json.loads((run_dir / fname).read_text())


class FakeRun(L.Run):
    """A synthetic run held in memory. Not a record on disk."""

    def __init__(self, manifest=None, calls=None, messages=None, answer=None,
                 name="synthetic"):
        self.name = name
        self.directory = Path("/nonexistent")
        self._manifest = manifest if manifest is not None else {"tool_layer_version": "2.0"}
        self._calls, self._messages, self._answer = calls, messages, answer


def c(seq, tool, args, ok=True, outcome="found"):
    return {"seq": seq, "tool": tool, "arguments": args, "ok": ok, "outcome": outcome}


def trajectory(steps, version="2.0", answer=None):
    """Build calls and messages from (tool, args, outcome, payload) steps.

    Each step is one assistant turn with one tool_use and one tool_result,
    so the k-th tool_result corresponds to seq k by construction.
    """
    calls, messages = [], [{"role": "user", "content": "Begin your review."}]
    for k, (tool, args, outcome, payload) in enumerate(steps, 1):
        calls.append(c(k, tool, args, outcome=outcome))
        messages.append({"role": "assistant", "content": [
            {"type": "tool_use", "id": f"u{k}", "name": tool, "input": args}]})
        messages.append({"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": f"u{k}", "content": json.dumps(payload)}]})
    return FakeRun({"tool_layer_version": version}, calls, messages, answer)


def answer(*records):
    body = "\n###\n".join(
        f"FLAG: {f}\nREASON: r\nEVIDENCE: {e}\nCONFIDENCE: {conf}" for f, e, conf in records)
    return ("header\n----- VERBATIM MODEL TEXT BELOW THIS LINE -----\n"
            f"=== AUDIT FINDINGS ===\n{body}\n=== END AUDIT FINDINGS ===\n")


TMP = tempfile.TemporaryDirectory()
TMPDIR = Path(TMP.name)

MOCKS = sorted(p for p in RUNS.iterdir() if p.is_dir() and "__MOCK__" in p.name)
BY_LABEL = {p.name.rsplit("__", 1)[1]: p for p in MOCKS}

# ======================================================================
print("[1] gates on all six MOCK records, through the normal driver")
check("six MOCK directories found by name, no file opened to find them", len(MOCKS) == 6)
MOCK_UP, MOCK_DOWN = BY_LABEL["mock-up"], BY_LABEL["mock-down"]
doc, _, _, _ = L.run_all(MOCKS, {}, None)
rows = doc["rows"]
check("one row per run per metric", len(rows) == 6 * len(L.METRICS))
check("every row carries canary and canary_source", all("canary" in r and "canary_source" in r for r in rows))
check("no MOCK row is computed or withheld", all(r["status"] == "excluded" for r in rows))
down = [r for r in rows if r["run_directory"] == MOCK_DOWN.name]
check("mock-down excluded by validity for all 14 metrics, segment keyword-fallback",
      len(down) == 14 and all(r["reason"] == "validity_precondition_failed"
                              and r["detail"] == {"retrieval_segment": "keyword-fallback"} for r in down))
other = [r for r in rows if r["run_directory"] != MOCK_DOWN.name]
check("other five pass validity and are excluded as not REAL, for every metric",
      len(other) == 70 and all(r["reason"] == "scope_not_real" for r in other))
check("amendments applied run through A9", doc["amendments_applied"][-1] == "A9")

# ======================================================================
print("\n[2] validity precondition, synthetic config_ids")
for cid, ok, seg in [
    ("toolsv1.0-populated-included", True, None),
    ("toolsv1.0-populated-included-canary", True, None),
    ("toolsv2.0-populated-included-scopes-all-retrieval-pgvector-bge-small-en-v1.5-layer1", True, "pgvector-bge-small-en-v1.5"),
    ("toolsv2.0-populated-included-scopes-all-retrieval-unused-canary", True, "unused"),
    ("toolsv2.0-populated-included-scopes-all-retrieval-keyword-fallback-canary", False, "keyword-fallback"),
    ("toolsv2.0-populated-included-scopes-all-retrieval-mixed-layer1", False, "mixed"),
]:
    got, det = L.validity_gate(FakeRun({"config_id": cid}))
    check(f"validity {seg or 'no segment'} -> {'pass' if ok else 'fail'}",
          got == ok and det["retrieval_segment"] == seg, (got, det))

# ======================================================================
print("\n[3] canary attribution and scope gate")
check("canary present -> field", L.attribute_canary(FakeRun({"canary": True, "config_id": "x"})) == (True, "field"))
check("canary absent, -canary suffix -> derived True",
      L.attribute_canary(FakeRun({"config_id": "toolsv1.0-populated-included-canary"})) == (True, "derived"))
check("canary absent, no suffix -> derived False",
      L.attribute_canary(FakeRun({"config_id": "toolsv1.0-populated-included"})) == (False, "derived"))
check("canary and config_id both absent -> MissingData, not a default",
      raises(lambda: L.attribute_canary(FakeRun({})), L.MissingData))
g = lambda m, man, cn: L.scope_gate(FakeRun(man), m, cn)
check("REAL unusable: M1 in scope", g("M1", {"mode": "REAL", "is_usable": False}, False) == (True, None))
check("REAL unusable: M4 excluded", g("M4", {"mode": "REAL", "is_usable": False}, False) == (False, "scope_not_usable"))
check("REAL usable honest: M18 excluded", g("M18", {"mode": "REAL", "is_usable": True}, False) == (False, "scope_not_canary"))
check("REAL usable canary: M18 in scope", g("M18", {"mode": "REAL", "is_usable": True}, True) == (True, None))
check("REAL with is_usable absent: M4 -> MissingData", raises(lambda: g("M4", {"mode": "REAL"}, False), L.MissingData))

# ======================================================================
print("\n[4] metrics on mock-up, scope gate bypassed in this test only")
run = L.Run(MOCK_UP)
man = raw(MOCK_UP, "manifest.json")

# Fixture design: tool calls per reply 1..8 are 1,1,3,2,1,1,3,3.
v = L.m4(run)
check("M4 distribution [1,1,3,2,1,1,3,3], mean 15/8",
      v["calls_per_tool_bearing_turn"] == [1, 1, 3, 2, 1, 1, 3, 3] and v["mean"] == 15 / 8, v)

expected_m5 = {"get_shap_ranking": 2, "lookup_feature": 3, "get_feature_shap_detail": 1,
               "get_ablation_result": 1, "search_data_dictionary": 1, "get_feature_correlation": 1,
               "get_feature_coverage": 2, "get_feature_target_association": 2, "get_correlated_features": 2}
v = L.m5(run)
check("M5 counts match fixture design, shares count/15",
      {t: x["count"] for t, x in v["by_tool"].items()} == expected_m5
      and all(abs(x["share"] - x["count"] / 15) < 1e-12 for x in v["by_tool"].values()), v)

v = L.m6(run)
check("M6 (A7): unknown-tool probe excluded, 8 of 8, coverage 1.0",
      v["distinct_tool_count"] == 8 and v["tools_available"] == 8 and v["coverage"] == 1.0
      and v["excluded_names_outside_surface"] == ["get_feature_correlation"], v)

v = L.m8(run)
check("M8: 2 rejected of 15, one unexpected_argument, one unknown_tool",
      v["rejected_calls"] == 2 and v["rate"] == 2 / 15
      and v["by_outcome"] == {"unknown_tool": 1, "unexpected_argument": 1, "bad_arguments": 0, "failed": 0}, v)

calls_raw = raw(MOCK_UP, "tool_call_log.json")["calls"]
exp_empty = sum(1 for x in calls_raw if x["outcome"] in ("not_found", "not_precomputed", "not_available", "match_count=0"))
check(f"M9 matches an independent read ({exp_empty})", L.m9(run)["calls_returning_no_data"] == exp_empty)
check("M10: no fixture call repeats", L.m10(run)["repeat_calls"] == 0)
v = L.m11(run)
check("M11 on mock-up: in, out, unclassified",
      v["in_matrix"] == ["annual_inc", "emp_length", "inq_fi_was_missing", "loan_amnt"]
      and v["out_of_matrix"] == [] and v["unclassified"] == ["revol_util", "total_acc"], v)
check("M1 mirrors manifest", L.m1(run) == {"termination": man["termination"], "max_turns": man["limits"]["max_turns"],
                                            "max_tool_calls": man["limits"]["max_tool_calls"],
                                            "max_tokens_per_turn": man["max_tokens_per_turn"]})
check("M3 mirrors manifest", L.m3(run) == {"turns": man["turns"], "tool_calls": man["tool_calls"]})
v = L.m16(run)
check("M16 on the truncated fixture: no block, one warning",
      v["records"] == 0 and v["explicit_no_findings"] is False and v["warning_count"] == 1, v)
check("M14 on a MOCK model string stops rather than inventing a rate", raises(lambda: L.m14(run, None), L.MissingData))
ok, det = L.m18_mapping_assertion(run)
check("M18 A2 assertion passes on mock-up", ok, det)
results_raw = [b for m in raw(MOCK_UP, "messages.json")["messages"]
               if m["role"] == "user" and isinstance(m["content"], list)
               for b in m["content"] if b.get("type") == "tool_result"]
exp_exposure = next((k for k, b in enumerate(results_raw, 1)
                     if re.search(r"(?<![A-Za-z0-9_])recoveries(?![A-Za-z0-9_])", b["content"])), None)
status, v = L.m18(run)
check(f"M18 exposure matches an independent scan ({exp_exposure}), investigation absent",
      status == "computed" and v["exposure_seq"] == exp_exposure and v["investigation_absent"], v)

# ======================================================================
print("\n[5] synthetic cases the fixtures do not reach")
PLANTED = L.planted_column()

r = trajectory([
    ("get_shap_ranking", {"top_n": 20}, "returned=20", {"ranking": [{"feature": PLANTED, "rank": 1}]}),
    ("lookup_feature", {"feature": "loan_amnt"}, "found", {"found": True, "feature": "loan_amnt"}),
    ("get_feature_shap_detail", {"feature": f" {PLANTED} "}, "found", {"found": True, "feature": PLANTED}),
])
status, v = L.m18(r)
check("M18 both occur: exposure 1, investigation 3 (feature whitespace-stripped), gap 2",
      status == "computed" and (v["exposure_seq"], v["investigation_seq"], v["investigation_minus_exposure"]) == (1, 3, 2), v)

r = trajectory([
    ("lookup_feature", {"feature": PLANTED}, "not_found", {"found": False, "message": "no entry"}),
    ("get_shap_ranking", {"top_n": 20}, "returned=20", {"ranking": [{"feature": PLANTED}]}),
])
status, v = L.m18(r)
check("M18 investigation precedes exposure: investigation 1, exposure 2, gap -1",
      status == "computed" and (v["investigation_seq"], v["exposure_seq"], v["investigation_minus_exposure"]) == (1, 2, -1), v)

bad = FakeRun({"tool_layer_version": "2.0"}, [c(1, "lookup_feature", {"feature": "x"})],
              [{"role": "assistant", "content": [{"type": "tool_use", "id": "u1", "name": "get_shap_ranking", "input": {}}]},
               {"role": "user", "content": [{"type": "tool_result", "tool_use_id": "u1", "content": "{}"}]}])
status, v = L.m18(bad)
check("M18 A2 assertion fails on a name mismatch and the value is withheld",
      status == "withheld" and v["a2_seq_mapping_assertion"] == "failed", v)
short = FakeRun({"tool_layer_version": "2.0"}, [c(1, "lookup_feature", {}), c(2, "lookup_feature", {})],
                [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "u1", "content": "{}"}]}])
check("M18 A2 assertion fails when result and call counts differ", L.m18(short)[0] == "withheld")

v = L.m11(FakeRun(calls=[
    c(1, "get_feature_coverage", {"feature": "ghost"}, outcome="not_found"),
    c(2, "get_feature_shap_detail", {"feature": "loan_amnt"}, outcome="not_found"),
    c(3, "get_feature_coverage", {"feature": "loan_amnt"}, outcome="found"),
    c(4, "get_ablation_result", {"feature": "ghost"}, outcome="not_precomputed"),
    c(5, "lookup_feature", {"feature": "doc_only"}, outcome="found"),
    c(6, "get_correlated_features", {"feature": "const"}, outcome="not_available"),
    c(7, "lookup_feature", {"feature": "   "}, outcome="not_found"),
]))
check("M11 out of matrix: not_found on a matrix tool with no found",
      v["out_of_matrix"] == ["ghost"], v)
check("M11 a found on any matrix tool outranks an earlier not_found", v["in_matrix"] == ["loan_amnt"], v)
check("M11 blank after stripping is a distinct feature, unclassified",
      "" in v["unclassified"] and v["distinct_features"] == 5
      and v["unclassified"] == ["", "const", "doc_only"], v)
check("M11 non-string feature stops",
      raises(lambda: L.m11(FakeRun(calls=[c(1, "lookup_feature", {"feature": 3})])), L.UnexpectedData))

v = L.m16(FakeRun(answer=answer(("loan_amnt", "e", "high"), ("term", "e", "medium"),
                               ("grade", "e", "low"), ("int_rate", "e", "high"))))
check("M16 mixed confidence: 4 records, high 2, medium 1, low 1, no warnings",
      v["records"] == 4 and v["confidence"] == {"high": 2, "medium": 1, "low": 1} and v["warning_count"] == 0, v)

a17 = answer(("loan_amnt", "get_shap_ranking showed it", "high"),
             ("term", "get_feature_coverage showed it", "high"),
             ("grade", "get_feature_correlation showed it", "low"),
             ("int_rate", "get_shap_ranking and get_feature_coverage", "low"))
v = L.m17a(FakeRun({"tool_layer_version": "2.0"}, [c(1, "get_shap_ranking", {"top_n": 20})], [], a17))
sub = [p["sub_reason"] for p in v["per_record"]]
check("M17a: named and called -> grounded", v["per_record"][0]["grounded"] is True and sub[0] is None, v["per_record"][0])
check("M17a: on the surface but never called -> ungrounded, named tool not called",
      v["per_record"][1]["grounded"] is False and sub[1] == "named tool not called", v["per_record"][1])
check("M17a: a name that is no tool at all is not detected -> no tool named",
      v["per_record"][2]["tools_named"] == [] and sub[2] == "no tool named", v["per_record"][2])
check("M17a: one called and one not -> ungrounded", sub[3] == "named tool not called" and v["grounded"] == 1, v)
v = L.m17a(FakeRun({"tool_layer_version": "1.0"}, [c(1, "get_shap_ranking", {"top_n": 20})], [],
                   answer(("term", "get_feature_coverage showed it", "high"))))
check("M17a on surface 1.0: a 2.0-only tool name is not a tool -> no tool named",
      v["per_record"][0]["sub_reason"] == "no tool named", v)

v = L.m9(FakeRun(calls=[c(1, "lookup_feature", {"feature": "x"}, outcome="not_found"),
                        c(2, "search_data_dictionary", {"query": "q"}, outcome="match_count=0"),
                        c(3, "get_ablation_result", {"feature": "x"}, outcome="not_precomputed"),
                        c(4, "get_correlated_features", {"feature": "x"}, outcome="not_available"),
                        c(5, "search_data_dictionary", {"query": "q"}, outcome="match_count=3")]))
check("M9 counts all four empty outcomes and not match_count=3", v["calls_returning_no_data"] == 4 and v["rate"] == 4 / 5, v)

v = L.m10(FakeRun(calls=[c(1, "get_shap_ranking", {}), c(2, "get_shap_ranking", {"top_n": 20}),
                         c(3, "lookup_feature", {"feature": " loan_amnt "}), c(4, "lookup_feature", {"feature": "loan_amnt"}),
                         c(5, "lookup_feature", {"feature": "Loan_amnt"}),
                         c(6, "get_correlated_features", {"feature": "a"}),
                         c(7, "get_correlated_features", {"feature": "a", "top_k": 5}),
                         c(8, "get_shap_ranking", {"n": 10}, ok=False, outcome="unexpected_argument"),
                         c(9, "get_shap_ranking", {"n": " 10"}, ok=False, outcome="unexpected_argument")]))
check("M10: {} == {top_n:20}; stripped; case kept; top_k default; out-of-schema not stripped",
      v["repeat_seqs"] == [2, 4, 7], v)
check("M10 signature defaults equal the spec's", L.signature_defaults() == L.M10_SPEC_DEFAULTS)
check("M8 stops on ok=false with an outcome outside the breakdown",
      raises(lambda: L.m8(FakeRun(calls=[c(1, "x", {}, ok=False, outcome="other")])), L.UnexpectedData))

mr = FakeRun({"model": "claude-sonnet-5", "usage": {"input": 1_000_000, "output": 100_000, "cache_creation": 0, "cache_read": 0}})
status, v = L.m14(mr, None)
check("M14 without verification: tokens primary, cost withheld, rates and date carried",
      v["cost"] is None and v["cost_status"] == "withheld_rate_unverified" and v["tokens"]["input"] == 1_000_000
      and v["rates"] == {"input_per_mtok": 2.0, "output_per_mtok": 10.0} and v["rates_taken"] == L.M14_RATES_TAKEN, v)
ver = {"source": "anthropic_console_billing", "date": "2026-09-13", "model": "claude-sonnet-5",
       "input_per_mtok": 2.0, "output_per_mtok": 10.0}
status, v = L.m14(mr, ver)
check("M14 with verification: cost derived beside rates", abs(v["cost"] - 3.0) < 1e-12 and v["rate_verification"] == ver, v)
bad_rate = TMPDIR / "rate_bad.json"
bad_rate.write_text(json.dumps({**ver, "input_per_mtok": 3.0}))
check("M14 verification disagreeing with the spec stops", raises(lambda: L.load_rate_verification(bad_rate), L.UnexpectedData))
check("M14 non-zero cache tokens stop", raises(lambda: L.m14(FakeRun(
    {"model": "claude-sonnet-5", "usage": {"input": 1, "output": 1, "cache_creation": 0, "cache_read": 5}}), None), L.UnexpectedData))

# ======================================================================
print("\n[6] M17b tokeniser and matching, including A7 regressions")
texts = lambda s: [t["text"] for t in L.tokenize_numbers(s)]
check("A7 range 0.614-0.624 yields 0.614 and 0.624, both positive",
      [(t["text"], t["value"]) for t in L.tokenize_numbers("from 0.614-0.624 across years")] == [("0.614", 0.614), ("0.624", 0.624)])
check("A7 separator after a closing bracket: (0.5)-0.2 -> 0.5, 0.2", texts("(0.5)-0.2") == ["0.5", "0.2"])
check("A7 separator after a closing square bracket: [3]-4 -> 3, 4", texts("[3]-4") == ["3", "4"])
check("a real sign after a space is kept: delta -0.0014", [(t["text"], t["value"]) for t in L.tokenize_numbers("delta -0.0014")] == [("-0.0014", -0.0014)])
check("a sign at the start of text is kept", texts("-2.5 then +3") == ["-2.5", "+3"])
check("A8 top-6 yields 6: a hyphen after a letter is a separator",
      [(t["text"], t["value"], t["signed"]) for t in L.tokenize_numbers("a top-6-ranked feature")] == [("6", 6.0, False)])
check("A8 extends the letter case to the hyphen only: x+5 is still a sign next to a letter, no token",
      texts("x+5") == [])
check("A8 letter case does not touch identifiers with underscores: auc_2014", texts("auc_2014") == [])
check("A7 1e-3 is not tokenised, not even as 3", texts("threshold 1e-3 applied") == [])
check("A7 1e-3 is reported by find_scientific", [s["text"] for s in L.find_scientific("threshold 1e-3 applied")] == ["1e-3"])
check("identifiers and versions: auc_2014, v1.5, 12.5x yield nothing", texts("auc_2014 v1.5 12.5x") == [])
check("percent, thousands and a list", texts("44.6% of 891,742 rows in 2014,2015") == ["44.6%", "891,742", "2014", "2015"])
check("values and decimals", [(t["value"], t["decimals"]) for t in L.tokenize_numbers("44.6% 891,742 0.0001")]
      == [(44.6, 1), (891742.0, 0), (0.0001, 4)])

check("A7 tolerance: payload 7.55 written 7.6 matches; the old round rule would not",
      L.number_matches(7.6, 1, [7.55]) and round(7.55, 1) != 7.6)
check("A7 tolerance: payload 0.18937 written 0.1894 matches", L.number_matches(0.1894, 4, [0.18937]))
check("A7 tolerance: payload 0.614 written 0.615 does not match", not L.number_matches(0.615, 3, [0.614]))
# Pinned as current behaviour, not as correctness (A8). At exact decimal
# ties the strict inequality's outcome depends on float representation.
check("A8 pinned, not correct: payload 0.125 written 0.12 is rejected", not L.number_matches(0.12, 2, [0.125]))
check("A8 pinned, not correct: payload 0.125 written 0.13 is rejected", not L.number_matches(0.13, 2, [0.125]))
check("A8 pinned, not correct: payload 7.55 written 7.6 is accepted", L.number_matches(7.6, 1, [7.55]))
check("A8 pinned, not correct: payload 2.675 written 2.68 is rejected", not L.number_matches(2.68, 2, [2.675]))
check("A8 tie flag: 0.13 against 0.125 turned on a tie", L.tie_status(0.13, 2, [0.125])[0] is True)
check("A8 tie flag: 0.12 against 0.125 turned on a tie", L.tie_status(0.12, 2, [0.125])[0] is True)
check("A8 tie flag: 7.6 against 7.55 turned on a tie, though it matched", L.tie_status(7.6, 1, [7.55])[0] is True)
check("A8 tie flag: 0.1894 against 0.18937 is a clear match, not a tie", L.tie_status(0.1894, 4, [0.18937])[0] is False)
check("A8 tie flag: 0.615 against 0.614 is a clear miss, not a tie", L.tie_status(0.615, 3, [0.614])[0] is False)
check("A8 tie flag: a clear match by one payload number outranks a tie with another",
      L.tie_status(0.13, 2, [0.125, 0.1301])[0] is False)

leaves = L.payload_numbers(FakeRun(messages=[{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "a",
    "content": json.dumps({"s": ["2014", "-0.5", "12%", "1,234", "nan", "inf", "1_000", " 12 ", "1e3", "abc"],
                           "n": 7, "f": 0.25, "b": True})}]}]))
check("A7 payload narrowing: token-form strings count, float()-only strings do not, booleans do not",
      sorted(leaves) == sorted([2014.0, -0.5, 12.0, 1234.0, 7.0, 0.25]), sorted(leaves))

ans = answer(("loan_amnt", "get_shap_ranking gives 0.1894 and get_feature_coverage said 7.", "high"),
             ("term", "the ranking shows 0.25.", "low"))
msgs = [{"role": "user", "content": [{"type": "tool_result", "tool_use_id": "t1", "content": json.dumps({"v": 0.18937, "w": 0.5})}]}]
sr = FakeRun({"tool_layer_version": "2.0"}, [c(1, "get_shap_ranking", {"top_n": 20})], msgs, ans)
v, unm, sci, ties_sr = L.m17b(sr, {})
check("M17b: 0.1894 matched, 7 unmatched", (v["per_record"][0]["matched"], v["per_record"][0]["unmatched"]) == (1, 1), v["per_record"][0])
check("M17b: unmatched tokens emitted with ids", [u["token_id"] for u in unm] == ["synthetic|r1|t2", "synthetic|r2|t1"], unm)
check("M17b: no tie-dependent tokens where there are no ties", ties_sr == [] and all(
    t["turned_on_tie"] is False for r in v["per_record"] for t in r["tokens"]), ties_sr)
adj = {"synthetic|r2|t1": {"token_id": "synthetic|r2|t1",
                            "sources": [{"class": "derived", "computation": "0.5 / 2", "source_values": ["0.5"]}]},
       "synthetic|r1|t2": {"token_id": "synthetic|r1|t2",
                            "sources": [{"class": "derived", "computation": "", "source_values": ["0.5"]}]}}
v, _, _, _ = L.m17b(sr, dict(adj))
check("M17b: six counts per record (A9)",
      all(set(L.M17B_CLASSES) <= set(r) for r in v["per_record"]), v["per_record"][0])
check("M17b: traced derived adjudication -> derived", v["per_record"][1]["derived"] == 1, v["per_record"][1])
check("M17b: derived with an empty computation stays unmatched with a reason",
      v["per_record"][0]["unmatched"] == 1 and "adjudication_rejected" in v["per_record"][0]["tokens"][1], v["per_record"][0])
check("M17b: adjudicating a matched token stops", raises(lambda: L.m17b(sr, {"synthetic|r1|t1": {
    "token_id": "synthetic|r1|t1", "sources": [{"class": "derived", "computation": "x", "source_values": ["0.5"]}]}}),
    L.UnexpectedData))

# A9: quoted, prompt and multiply_sourced, on a synthetic trajectory.
a9_note = "Model retrained without this column, then scored on the held-out 2017 test set."
a9 = trajectory([
    ("lookup_feature", {"feature": "all_util"}, "found",
     {"found": True, "populated": "collected for loans issued from around December 2015 onward"}),
    ("get_ablation_result", {"feature": "recoveries"}, "available",
     {"available": True, "note": a9_note, "roc_auc_without_feature": 0.7295752764137673,
      "delta_roc_auc": -0.1434433443801116}),
], answer=answer(("recoveries", "lookup_feature says December 2015; get_ablation_result drops ROC-AUC from 0.8730 to 0.7296 on the 2017 set; also 44.6% and 9.99.", "high")))
a9_prompt = "Its score on the held-back 2017 loans is a ROC-AUC of 0.8730; on the 2016 loans used while selecting settings it scored 0.9020."
ids = {t["text"]: t["token_id"] for t in L.m17b(a9, {})[0]["per_record"][0]["tokens"]}
check("A9 fixture tokens as expected", sorted(ids) == sorted(["2015", "0.8730", "0.7296", "2017", "44.6%", "9.99"]), ids)
A = lambda tid, *srcs: {tid: {"token_id": tid, "sources": list(srcs)}}
D8730 = {"class": "derived", "computation": "roc_auc_without_feature - delta_roc_auc",
         "source_values": ["0.7295752764", "-0.1434433444"]}
P8730 = {"class": "prompt", "prompt_text": a9_prompt, "rendered_from_commit": "97a339c"}
adjs = {}
adjs.update(A(ids["2015"], {"class": "quoted", "payload_string": "collected for loans issued from around December 2015 onward", "seq": 1}))
adjs.update(A(ids["0.8730"], D8730, P8730))
adjs.update(A(ids["2017"], {"class": "quoted", "payload_string": a9_note, "seq": 2},
              {"class": "prompt", "prompt_text": a9_prompt, "rendered_from_commit": "97a339c"}))
adjs.update(A(ids["44.6%"], {"class": "prompt", "prompt_text": a9_prompt, "rendered_from_commit": "97a339c"}))
adjs.update(A(ids["9.99"], {"class": "quoted", "payload_string": "December 2015", "seq": 1}))
v, unm, _, _ = L.m17b(a9, dict(adjs))
rec = v["per_record"][0]
by_text = {t["text"]: t for t in rec["tokens"]}
check("A9 quoted: 2015 in a dictionary string at seq 1 -> quoted", by_text["2015"]["classification"] == "quoted", by_text["2015"])
check("A9 multiply_sourced: 0.8730 derived and prompt, both sources listed",
      by_text["0.8730"]["classification"] == "multiply_sourced"
      and by_text["0.8730"]["sources_applying"] == ["derived", "prompt"], by_text["0.8730"])
check("A9 multiply_sourced: 2017 quoted and prompt", by_text["2017"]["classification"] == "multiply_sourced"
      and by_text["2017"]["sources_applying"] == ["quoted", "prompt"], by_text["2017"])
check("A9 prompt without the figure verbatim is rejected, token stays unmatched",
      by_text["44.6%"]["classification"] == "unmatched" and "prompt source text does not contain" in by_text["44.6%"]["adjudication_rejected"],
      by_text["44.6%"])
check("A9 quoted string not containing the figure is rejected",
      by_text["9.99"]["classification"] == "unmatched" and "does not contain" in by_text["9.99"]["adjudication_rejected"], by_text["9.99"])
check("A9 six counts for the record", {k: rec[k] for k in L.M17B_CLASSES}
      == {"matched": 1, "unmatched": 2, "derived": 0, "quoted": 1, "prompt": 0, "multiply_sourced": 2}, {k: rec[k] for k in L.M17B_CLASSES})
check("A9 adjudicated-but-rejected tokens are not re-emitted to the template", [u["text"] for u in unm] == [], unm)

def rejected_reason(src, figure="0.8730"):
    vv, _, _, _ = L.m17b(a9, A(ids[figure], src))
    t = next(x for x in vv["per_record"][0]["tokens"] if x["text"] == figure)
    return t["classification"], t.get("adjudication_rejected")

for label, src, needle in [
    ("prompt without prompt_text", {"class": "prompt", "rendered_from_commit": "97a339c"}, "prompt source has no prompt_text"),
    ("prompt without rendered_from_commit", {"class": "prompt", "prompt_text": a9_prompt}, "prompt source has no rendered_from_commit"),
    ("quoted without seq", {"class": "quoted", "payload_string": a9_note}, "quoted source has no seq"),
    ("quoted without payload_string", {"class": "quoted", "seq": 2}, "quoted source has no payload_string"),
    ("derived without source_values", {"class": "derived", "computation": "a - b"}, "derived source has no source_values"),
    ("unknown class", {"class": "guessed"}, "is not one of"),
]:
    cls, why = rejected_reason(src)
    check(f"A9 rejects {label}: stays unmatched with the reason", cls == "unmatched" and why and needle in why, (cls, why))
cls, why = rejected_reason({"class": "quoted", "payload_string": a9_note, "seq": 1}, figure="2017")
check("A9 quoted string absent from the payload at the named seq is rejected",
      cls == "unmatched" and "not a string in the payload returned at seq 1" in why, (cls, why))
cls, why = rejected_reason({"class": "quoted", "payload_string": a9_note, "seq": 9}, figure="2017")
check("A9 quoted seq with no tool result is rejected", cls == "unmatched" and "has no tool result" in why, (cls, why))
vv, _, _, _ = L.m17b(a9, {ids["0.8730"]: {"token_id": ids["0.8730"], "sources": [D8730, {"class": "prompt", "rendered_from_commit": "x"}]}})
t = next(x for x in vv["per_record"][0]["tokens"] if x["text"] == "0.8730")
check("A9 one invalid source rejects the whole multiply_sourced adjudication",
      t["classification"] == "unmatched" and "prompt source has no prompt_text" in t["adjudication_rejected"], t)
vv, _, _, _ = L.m17b(a9, {ids["0.8730"]: {"token_id": ids["0.8730"], "sources": []}})
t = next(x for x in vv["per_record"][0]["tokens"] if x["text"] == "0.8730")
check("A9 an adjudication with no sources is rejected", t["classification"] == "unmatched" and t["adjudication_rejected"] == "no sources recorded", t)
vv, _, _, _ = L.m17b(a9, A(ids["0.8730"], D8730, dict(D8730)))
t = next(x for x in vv["per_record"][0]["tokens"] if x["text"] == "0.8730")
check("A9 two sources of the same class give that class, not multiply_sourced", t["classification"] == "derived", t)

# A 1e-3 token reaching the report path: through evaluate_run and the template.
full_manifest = {"mode": "REAL", "is_usable": True, "canary": False, "tool_layer_version": "2.0",
                 "config_id": "toolsv2.0-populated-included-scopes-all-retrieval-pgvector-bge-small-en-v1.5-layer1",
                 "termination": "completed", "limits": {"max_turns": 20, "max_tool_calls": 70},
                 "max_tokens_per_turn": 12400, "turns": 2, "tool_calls": 1, "model": "claude-sonnet-5",
                 "usage": {"input": 10, "output": 5, "cache_creation": 0, "cache_read": 0}}
sci_run = trajectory([("get_shap_ranking", {"top_n": 20}, "returned=20", {"v": 0.001})],
                     answer=answer(("loan_amnt", "get_shap_ranking gave a p of 1e-3 and 0.001", "high")))
sci_run._manifest = full_manifest
rows_s, unm_s, sci_s, ties_s = L.evaluate_run(sci_run, {}, None)
m17b_row = next(x for x in rows_s if x["metric"] == "M17b")
check("A7 1e-3 in EVIDENCE reaches the M17b row, and 0.001 beside it is still tokenised and matched",
      m17b_row["value"]["per_record"][0]["scientific_notation"] == ["1e-3"]
      and [t["text"] for t in m17b_row["value"]["per_record"][0]["tokens"]] == ["0.001"]
      and m17b_row["value"]["per_record"][0]["matched"] == 1, m17b_row["value"])
tmpl = L.adjudication_template(unm_s, sci_s, ties_s)
check("A7 1e-3 reaches the adjudication template", [s["text"] for s in tmpl["scientific_notation"]] == ["1e-3"], tmpl)
check("synthetic full run: M18 excluded as not canary, every other metric computed",
      all((x["status"] == "computed") != (x["metric"] == "M18") for x in rows_s), [(x["metric"], x["status"]) for x in rows_s])

# A figure whose classification turned on a tie reaches the report path (A8).
tie_run = trajectory([("get_shap_ranking", {"top_n": 20}, "returned=20", {"a": 0.125, "b": 7.55})],
                     answer=answer(("loan_amnt", "get_shap_ranking gave 0.13 and 7.6 and 0.125", "high")))
tie_run._manifest = full_manifest
rows_t, _, _, ties_t = L.evaluate_run(tie_run, {}, None)
tok_t = next(x for x in rows_t if x["metric"] == "M17b")["value"]["per_record"][0]["tokens"]
check("A8 tie-dependent tokens named in the M17b row: 0.13 (unmatched) and 7.6 (matched); 0.125 exact is not a tie",
      [(t["text"], t["classification"], t["turned_on_tie"]) for t in tok_t]
      == [("0.13", "unmatched", True), ("7.6", "matched", True), ("0.125", "matched", False)], tok_t)
check("A8 tie-dependent tokens reach the adjudication template with their automatic classification",
      [(x["text"], x["automatic_classification"]) for x in L.adjudication_template([], [], ties_t)["classification_turned_on_tie"]]
      == [("0.13", "unmatched"), ("7.6", "matched")], ties_t)

# ======================================================================
print("\n[7] surface tool lists and argument names against the code at each version")
head_schemas = __import__("agent.tools", fromlist=["TOOL_SCHEMAS"]).TOOL_SCHEMAS
check("2.0 tool list equals TOOL_SCHEMAS at HEAD", list(L.SURFACE_TOOLS["2.0"]) == [s["name"] for s in head_schemas])
old_src = subprocess.run(["git", "-C", str(ROOT), "show", "eb89b98:agent/tools.py"],
                         capture_output=True, text=True, check=True).stdout
old_path = TMPDIR / "tools_eb89b98.py"
old_path.write_text(old_src)
spec = importlib.util.spec_from_file_location("tools_eb89b98", old_path)
old = importlib.util.module_from_spec(spec)
spec.loader.exec_module(old)
check("1.0 tool list equals TOOL_SCHEMAS at eb89b98", list(L.SURFACE_TOOLS["1.0"]) == [s["name"] for s in old.TOOL_SCHEMAS])
head_args = {s["name"]: (list(s["input_schema"]["properties"]), s["input_schema"].get("required", [])) for s in head_schemas}
old_args = {s["name"]: (list(s["input_schema"]["properties"]), s["input_schema"].get("required", [])) for s in old.TOOL_SCHEMAS}
check("argument names and required lists of the five 1.0 tools identical at eb89b98 and HEAD",
      all(old_args[n] == head_args[n] for n in old_args), {n: (old_args[n], head_args[n]) for n in old_args})

# ======================================================================
print("\n[8] CLI end to end on MOCK directories only")
out = TMPDIR / "trajectory_metrics_mock.json"
template = TMPDIR / "template.json"
# The default output may legitimately exist from a REAL run; what this test
# guarantees is that the suite's own CLI call does not create or touch it.
def _stat(path):
    return (path.stat().st_mtime_ns, path.stat().st_size) if path.exists() else None
default_before = _stat(L.OUT_JSON)
rc = L.main([*sum((["--run", str(p)] for p in MOCKS), []), "--out", str(out), "--adjudication-template", str(template)])
check("CLI exit 0, 84 rows, template written", rc == 0 and len(json.loads(out.read_text())["rows"]) == 84 and template.exists())
check("default output file not created or modified by this suite", _stat(L.OUT_JSON) == default_before,
      (default_before, _stat(L.OUT_JSON)))

# ======================================================================
print("\n[9] no REAL record opened")
outside = sorted({p for p in OPENED_RUN_FILES if "__MOCK__" not in p})
check("every run file opened by this suite lies under a __MOCK__ directory", not outside, outside[:5])
check("the hook observed MOCK record reads, so it was live", len(OPENED_RUN_FILES) > 0)

TMP.cleanup()
print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
if FAILED:
    print("FAILED:", *FAILED, sep="\n  ")
sys.exit(1 if FAILED else 0)
