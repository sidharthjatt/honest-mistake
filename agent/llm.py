"""LLM call wrapper for the Honest Mistake audit agent.

Single entry point: call_llm(messages, tools, system, mock=False, cache=...).
Real and mock paths return the same shape, so callers never branch:
    {"text": str,
     "tool_calls": list,
     "content": list,      raw content blocks, as dicts
     "stop_reason": str,
     "usage": {"input": int, "output": int,
               "cache_creation": int, "cache_read": int}}

`content` carries every block the model produced, including thinking
blocks, which must be echoed back unchanged when the conversation
continues on the same model. `text` and `tool_calls` remain as flattened
conveniences; they are lossy and must not be used to rebuild a turn.

The request itself is built by build_request, on both paths, so a mock
run exercises the same request construction a real run sends.

The API key is read only when mock=False, so this module imports fine
with no key present.
"""

from agent import ledger
from agent.mock_replies import MOCK_REPLIES

MODEL = "claude-sonnet-5"

# Sized from the truncated run of 2026-08-25, where a 2000 ceiling cut off
# an intermediate turn mid-tool-call. Thinking is billed as output and is
# invisible in the transcript (display defaults to omitted), so most of the
# budget goes to reasoning the artefacts never show:
#   observed thinking   ~420 tokens/turn early, >=1849 by turn 4 and rising
#   answer block        ~2332 tokens for 39 records at ~58 tokens each
#   preamble prose      ~200 tokens
# Worst case taken as the answer block plus double the largest observed
# thinking demand: 2332 + 200 + 7000 = 9532, plus 30% for the error in that
# estimate. A ceiling is not a spend - unused headroom costs nothing - and
# this stays under the ~16000 that keeps a non-streaming request inside the
# default HTTP timeout.
MAX_TOKENS = 12_400
# No sampling parameters are sent. temperature, top_p and top_k were removed
# on this model family and are rejected with a 400.

THINKING = {"type": "adaptive", "display": "summarized"}

# "off" builds the request exactly as every Layer 2 run sent it.
# "moving-breakpoint" is the design in PREREGISTRATION_PHASE2.md: one
# marker on the last block of the newest user turn, so each request reads
# back everything the previous one wrote.
CACHE_OFF = "off"
CACHE_MOVING = "moving-breakpoint"
CACHE_MODES = (CACHE_OFF, CACHE_MOVING)

# The API rejects a request with more than four.
MAX_BREAKPOINTS = 4

# Cursor into MOCK_REPLIES; each mock call returns the next entry.
_mock_index = 0


def reset_mock() -> None:
    """Rewind the mock reply cursor to the first entry."""
    global _mock_index
    _mock_index = 0


def count_breakpoints(obj) -> int:
    """Number of cache_control markers anywhere inside a request part."""
    if isinstance(obj, dict):
        return (("cache_control" in obj)
                + sum(count_breakpoints(v) for v in obj.values()))
    if isinstance(obj, list):
        return sum(count_breakpoints(v) for v in obj)
    return 0


def build_request(messages, tools, system, cache=CACHE_OFF) -> dict:
    """The keyword arguments for messages.create, for either cache mode.

    The caller's messages are never modified. In caching mode every
    message is copied, a plain-string content becomes one text block on
    every request so its bytes do not change between turns, and the
    marker goes on the copy's last block. The stored history therefore
    never carries a marker, and each request carries exactly one.
    """
    if cache not in CACHE_MODES:
        raise ValueError(f"Unknown cache mode {cache!r}; expected one of "
                         f"{', '.join(CACHE_MODES)}.")

    if cache == CACHE_OFF:
        kwargs = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            # Thinking runs adaptively on this model whether or not it is
            # asked for; display defaults to omitted, which returns thinking
            # blocks with empty text. Asking for summaries puts the reasoning
            # into the transcript. Display affects visibility only - thinking
            # is billed the same either way - so this costs nothing and makes
            # the run auditable rather than a record of conclusions with no
            # working.
            thinking=THINKING,
            system=system,
            messages=messages,
        )
    else:
        if not messages or messages[-1]["role"] != "user":
            raise ValueError("A cached request must end on a user turn.")
        copied = []
        for message in messages:
            content = message["content"]
            if isinstance(content, str):
                content = [{"type": "text", "text": content}]
            else:
                content = [dict(block) for block in content]
            copied.append({**message, "content": content})
        if not copied[-1]["content"]:
            raise ValueError("The last user turn has no block to mark.")
        copied[-1]["content"][-1]["cache_control"] = {"type": "ephemeral"}
        kwargs = dict(
            model=MODEL,
            max_tokens=MAX_TOKENS,
            thinking=THINKING,
            # One block and no marker. The marker on the message already
            # caches tools and system, which render before it.
            system=[{"type": "text", "text": system}],
            messages=copied,
        )
    if tools:
        kwargs["tools"] = tools

    found = count_breakpoints(kwargs.get("tools", [])) + \
        count_breakpoints(kwargs["system"]) + \
        count_breakpoints(kwargs["messages"])
    if found > MAX_BREAKPOINTS:
        raise ValueError(f"The request carries {found} cache breakpoints; "
                         f"the API allows {MAX_BREAKPOINTS}.")
    return kwargs


def call_llm(messages, tools, system, mock=False, cache=CACHE_OFF,
             label=None) -> dict:
    """Call the Anthropic Messages API, or return the next scripted reply.

    Args:
        messages: list of message dicts, Anthropic Messages API format.
        tools:    list of tool definitions (may be empty).
        system:   system prompt string.
        mock:     when True, no network call is made.
        cache:    CACHE_OFF or CACHE_MOVING.
        label:    written beside the request in the spend ledger.

    Returns:
        {"text": str,
         "tool_calls": list,
         "content": list,
         "stop_reason": str,
         "usage": {"input": int, "output": int,
                   "cache_creation": int, "cache_read": int}}

    Raises:
        ledger.BudgetExceeded when a real request could take recorded
        spend past the cap. Nothing is sent in that case.
    """
    kwargs = build_request(messages, tools, system, cache)
    if mock:
        return _call_mock()
    return _call_real(kwargs, cache, label)


def _block_to_dict(block) -> dict:
    """Convert one SDK content block to a plain dict.

    Dicts are both valid to send back to the API and JSON-serialisable,
    so the run artefacts record what was actually sent. `exclude_none`
    drops optional fields the SDK leaves unset; every field the API
    needs on replay, including a thinking block's signature, is set.
    """
    if hasattr(block, "model_dump"):
        return block.model_dump(exclude_none=True)
    return dict(block)


def _call_mock() -> dict:
    """Return the next scripted reply, cycling if calls exceed the list."""
    global _mock_index
    if not MOCK_REPLIES:
        raise RuntimeError("MOCK_REPLIES is empty — nothing to return")
    reply = MOCK_REPLIES[_mock_index % len(MOCK_REPLIES)]
    _mock_index += 1
    return {
        "text": reply["text"],
        "tool_calls": list(reply["tool_calls"]),
        "content": [dict(b) for b in reply["content"]],
        "stop_reason": reply.get("stop_reason", "end_turn"),
        "usage": {"input": 0, "output": 0,
                  "cache_creation": 0, "cache_read": 0},
    }


def _client():
    """An API client. Imports and the key are resolved lazily."""
    import os

    import anthropic
    from dotenv import load_dotenv

    load_dotenv()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not found — copy .env.example to .env and set it, "
            "or call with mock=True"
        )
    return anthropic.Anthropic(api_key=api_key)


def projected_request_usd(client, kwargs) -> float:
    """Worst-case cost of one built request, from a free token count."""
    counted = client.messages.count_tokens(
        **{k: v for k, v in kwargs.items() if k != "max_tokens"}
    ).input_tokens
    return ledger.worst_case_usd(kwargs["model"], counted,
                                 kwargs["max_tokens"])


def _call_real(kwargs, cache, label) -> dict:
    """Check the cap, hit the real Messages API, record the spend."""
    client = _client()
    # A failed count raises here and the request is never sent.
    ledger.check(kwargs["model"], projected_request_usd(client, kwargs))
    response = client.messages.create(**kwargs)

    usage = {
        "input": response.usage.input_tokens,
        "output": response.usage.output_tokens,
        "cache_creation": getattr(
            response.usage, "cache_creation_input_tokens", 0) or 0,
        "cache_read": getattr(
            response.usage, "cache_read_input_tokens", 0) or 0,
    }
    ledger.record(kwargs["model"], usage, cache, label)

    text_parts = []
    tool_calls = []
    for block in response.content:
        if block.type == "text":
            text_parts.append(block.text)
        elif block.type == "tool_use":
            tool_calls.append({
                "id": block.id,
                "name": block.name,
                "input": block.input,
            })

    return {
        "text": "".join(text_parts),
        "tool_calls": tool_calls,
        "content": [_block_to_dict(b) for b in response.content],
        "stop_reason": response.stop_reason,
        "usage": usage,
    }
