"""Scripted replies for call_llm(mock=True).

These are plumbing fixtures, not sample answers. They exist so the ReAct
loop can be built and debugged with no network call and no API key. The
narration is deliberately generic: it states what a turn is doing, never
what it concluded, and names no feature in a way that would suggest an
answer. Any resemblance to a finding would prejudge the audit these
fixtures are meant to support.

The sequence exercises, in order:
     1  a single tool call, no text
     2  text and a tool call together
     3  a thinking block, then several tool calls in one turn
     4  text and several tool calls together
     5  a tool call with an argument name the tool does not accept
     6  a tool call naming a tool that does not exist
     7  the three per-column tools, on ordinary arguments
     8  the same three, on the arguments that reach their edge paths
     9  a truncated turn (stop_reason "max_tokens"), no tool calls
    10  text only with stop_reason "end_turn", which ends the loop
    11  stop_reason "refusal", no tool calls
    12  an unrecognised stop_reason, no tool calls

The loop halts at 9, so 10, 11 and 12 are reached by continuing the mock
cursor into successive runs rather than by resetting it. Entries 9 to 12
exist because a turn carrying no tool calls looks the same whether the
model finished, was cut off, declined, or stopped for a reason the loop
has never seen; only stop_reason separates them, and each needs a
fixture.

Entry 3 carries a thinking block. Sonnet 5 thinks adaptively by default
and its thinking blocks must be echoed back unchanged on later turns, so
the mock path has to carry one through the same code the real path uses
rather than around it.

Entries 7 and 8 exist because a tool that is only ever called through
dispatch() has never been proved to work inside the loop, where its result
has to survive being turned into a tool_result block and echoed back.
Entry 8 picks arguments that reach the paths where those three tools
return something other than a full result: a column with no companion
missingness flag, a column that holds one value throughout the evaluation
split, and a neighbour count above the number that was precomputed.

Entries 5 and 6 are the deliberate error cases; their tool_use ids are
listed in DELIBERATE_ERROR_CALLS. Every other tool call names a real
tool and uses its real argument names, checked by _self_check() against
the published schemas.

Content blocks are the source of truth here, exactly as they are in a
real response: `text` and `tool_calls` are derived from them below, so a
fixture cannot drift into claiming text or calls its blocks do not
contain.

Each entry matches the call_llm return shape:
    {"text": str,
     "tool_calls": list,
     "content": list,
     "stop_reason": str,
     "usage": {"input": int, "output": int,
               "cache_creation": int, "cache_read": int}}

Run the validity check:
    .venv/bin/python -m agent.mock_replies
"""

_ZERO_USAGE = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}


def _text(text: str) -> dict:
    return {"type": "text", "text": text}


def _tool(call_id: str, name: str, args: dict) -> dict:
    return {"type": "tool_use", "id": call_id, "name": name, "input": args}


def _thinking(summary: str, signature: str) -> dict:
    return {"type": "thinking", "thinking": summary, "signature": signature}


# (content blocks, stop_reason)
_REPLY_SPECS: list[tuple[list[dict], str]] = [
    # 1 — a single tool call, no accompanying text.
    (
        [_tool("toolu_mock_01", "get_shap_ranking", {"top_n": 20})],
        "tool_use",
    ),

    # 2 — text and one tool call in the same turn.
    (
        [
            _text("Taking the columns one at a time to see how each is "
                  "described before drawing any comparison."),
            _tool("toolu_mock_02", "lookup_feature", {"feature": "loan_amnt"}),
        ],
        "tool_use",
    ),

    # 3 — a thinking block ahead of several tool calls in one turn.
    (
        [
            _thinking("Deciding which columns to retrieve together.",
                      "sig_mock_thinking_03"),
            _tool("toolu_mock_03a", "lookup_feature",
                  {"feature": "annual_inc"}),
            _tool("toolu_mock_03b", "get_feature_shap_detail",
                  {"feature": "annual_inc"}),
            _tool("toolu_mock_03c", "get_ablation_result",
                  {"feature": "annual_inc"}),
        ],
        "tool_use",
    ),

    # 4 — text plus several tool calls.
    (
        [
            _text("Widening the search to see which other columns are "
                  "described in similar terms."),
            _tool("toolu_mock_04a", "search_data_dictionary",
                  {"query": "balance"}),
            _tool("toolu_mock_04b", "lookup_feature",
                  {"feature": "total_acc"}),
        ],
        "tool_use",
    ),

    # 5 — DELIBERATE ERROR: real tool, argument name it does not accept.
    (
        [
            _text("Requesting a larger slice of the ranking."),
            _tool("toolu_mock_05", "get_shap_ranking", {"n": 10}),
        ],
        "tool_use",
    ),

    # 6 — DELIBERATE ERROR: a tool that does not exist.
    (
        [
            _text("Checking whether a different view of the same data is "
                  "available."),
            _tool("toolu_mock_06", "get_feature_correlation",
                  {"feature": "revol_util"}),
        ],
        "tool_use",
    ),

    # 7 — the three per-column tools on ordinary arguments, in one turn.
    (
        [
            _text("Looking at one column three ways: how it is spread, how "
                  "it stands on its own, and what it moves with."),
            _tool("toolu_mock_07a", "get_feature_coverage",
                  {"feature": "emp_length"}),
            _tool("toolu_mock_07b", "get_feature_target_association",
                  {"feature": "emp_length"}),
            _tool("toolu_mock_07c", "get_correlated_features",
                  {"feature": "emp_length"}),
        ],
        "tool_use",
    ),

    # 8 — the same three on arguments that reach their edge paths: a column
    #     with no companion flag, a column holding one value throughout the
    #     evaluation split, and a neighbour count above what was precomputed.
    #     These are valid calls, not errors, and each returns a shape the
    #     ordinary path does not produce.
    (
        [
            _text("Repeating the three views on columns where each is "
                  "expected to report something other than a full result."),
            _tool("toolu_mock_08a", "get_feature_coverage",
                  {"feature": "loan_amnt"}),
            _tool("toolu_mock_08b", "get_feature_target_association",
                  {"feature": "inq_fi_was_missing"}),
            _tool("toolu_mock_08c", "get_correlated_features",
                  {"feature": "loan_amnt", "top_k": 99}),
        ],
        "tool_use",
    ),

    # 9 — a turn cut off by the output limit. No tool calls, and the loop
    #     must not read this as a finished answer.
    (
        [_text("Working through the remaining columns in order, starting "
               "with the ones already retrieved and then")],
        "max_tokens",
    ),

    # 10 — text only, end_turn: the loop terminates normally here.
    (
        [_text("That is enough material from the tools. Writing up the "
               "assessment now.")],
        "end_turn",
    ),

    # 11 — declined. Carries no tool calls, so without an explicit check
    #      this is shaped exactly like a finished turn.
    (
        [_text("I am not going to continue with this request.")],
        "refusal",
    ),

    # 12 — a stop_reason the loop has never seen. Must not be read as a
    #      completion, and the raw value must survive into the record.
    (
        [_text("Partial output before an unfamiliar stop.")],
        "some_future_stop_reason",
    ),
]


def _derive(content: list[dict], stop_reason: str) -> dict:
    """Flatten blocks the way call_llm flattens a real response."""
    return {
        "text": "".join(b["text"] for b in content if b["type"] == "text"),
        "tool_calls": [
            {"id": b["id"], "name": b["name"], "input": b["input"]}
            for b in content if b["type"] == "tool_use"
        ],
        "content": [dict(b) for b in content],
        "stop_reason": stop_reason,
        "usage": dict(_ZERO_USAGE),
    }


MOCK_REPLIES = [_derive(content, stop) for content, stop in _REPLY_SPECS]

# tool_use ids whose calls are invalid on purpose, with the path each
# one is there to exercise.
DELIBERATE_ERROR_CALLS = {
    "toolu_mock_05": "argument name the tool does not accept",
    "toolu_mock_06": "tool name that does not exist",
}


def _self_check() -> None:
    """Validate every scripted tool call against the published schemas."""
    # Imported here, not at module scope: llm.py imports this module, and
    # keeping the tool layer out of that path avoids a heavier import
    # chain for anyone who only wants the fixtures.
    from agent.tools import TOOL_SCHEMAS

    schemas = {s["name"]: s for s in TOOL_SCHEMAS}
    required_usage = {"input", "output", "cache_creation", "cache_read"}
    valid, deliberate = [], []

    for i, reply in enumerate(MOCK_REPLIES, 1):
        assert set(reply) == {"text", "tool_calls", "content", "stop_reason",
                              "usage"}, \
            f"reply {i} does not match the call_llm return shape"
        assert isinstance(reply["text"], str)
        assert isinstance(reply["tool_calls"], list)
        assert isinstance(reply["content"], list)
        assert isinstance(reply["stop_reason"], str)
        assert set(reply["usage"]) == required_usage, \
            f"reply {i} is missing one of the four usage keys"
        assert reply["content"], f"reply {i} has no content blocks"

        # The flattened views must agree with the blocks they came from,
        # so a fixture cannot exercise a path the real client would not.
        joined = "".join(b["text"] for b in reply["content"]
                         if b["type"] == "text")
        assert joined == reply["text"], \
            f"reply {i}: text does not match its text blocks"
        block_calls = [b["id"] for b in reply["content"]
                       if b["type"] == "tool_use"]
        assert block_calls == [c["id"] for c in reply["tool_calls"]], \
            f"reply {i}: tool_calls do not match its tool_use blocks"

        for call in reply["tool_calls"]:
            assert set(call) == {"id", "name", "input"}, \
                f"reply {i}: tool call does not match the call_llm shape"
            row = (i, call["id"], call["name"], call["input"])
            if call["id"] in DELIBERATE_ERROR_CALLS:
                deliberate.append(row)
                continue
            assert call["name"] in schemas, \
                f"reply {i}: '{call['name']}' is not a published tool"
            allowed = set(schemas[call["name"]]["input_schema"]["properties"])
            unexpected = set(call["input"]) - allowed
            assert not unexpected, \
                (f"reply {i}: '{call['name']}' does not accept "
                 f"{sorted(unexpected)}")
            required = set(schemas[call["name"]]["input_schema"]
                           .get("required", []))
            missing = required - set(call["input"])
            assert not missing, \
                f"reply {i}: '{call['name']}' requires {sorted(missing)}"
            valid.append(row)

    thinking = [i for i, r in enumerate(MOCK_REPLIES, 1)
                if any(b["type"] == "thinking" for b in r["content"])]
    assert thinking, "no fixture carries a thinking block"

    stops = {r["stop_reason"] for r in MOCK_REPLIES}
    for needed in ("end_turn", "max_tokens", "refusal"):
        assert needed in stops, f"no fixture with stop_reason {needed!r}"

    print(f"MOCK_REPLIES: {len(MOCK_REPLIES)} replies, "
          f"{len(valid) + len(deliberate)} tool calls")
    print(f"  content blocks agree with text and tool_calls in every reply")
    print(f"  thinking block present in reply/replies: {thinking}")
    print(f"\nvalid against the published schemas ({len(valid)}):")
    for i, cid, name, args in valid:
        print(f"  reply {i}  {cid:<16} {name}({args})")
    print(f"\ndeliberate error cases ({len(deliberate)}):")
    for i, cid, name, args in deliberate:
        print(f"  reply {i}  {cid:<16} {name}({args})")
        print(f"                              -> {DELIBERATE_ERROR_CALLS[cid]}")
    print("\nstop_reason sequence:")
    for i, r in enumerate(MOCK_REPLIES, 1):
        kinds = ",".join(sorted({b["type"] for b in r["content"]}))
        print(f"  reply {i:>2}  {r['stop_reason']:<24} "
              f"tool_calls={len(r['tool_calls'])}  blocks=[{kinds}]")
    print("\nall assertions passed")


if __name__ == "__main__":
    _self_check()
