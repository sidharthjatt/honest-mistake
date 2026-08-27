"""LLM call wrapper for the Honest Mistake audit agent.

Single entry point: call_llm(messages, tools, system, mock=False).
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

The API key is read only when mock=False, so this module imports fine
with no key present.
"""

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

# Cursor into MOCK_REPLIES; each mock call returns the next entry.
_mock_index = 0


def reset_mock() -> None:
    """Rewind the mock reply cursor to the first entry."""
    global _mock_index
    _mock_index = 0


def call_llm(messages, tools, system, mock=False) -> dict:
    """Call the Anthropic Messages API, or return the next scripted reply.

    Args:
        messages: list of message dicts, Anthropic Messages API format.
        tools:    list of tool definitions (may be empty).
        system:   system prompt string.
        mock:     when True, no network call is made.

    Returns:
        {"text": str,
         "tool_calls": list,
         "content": list,
         "stop_reason": str,
         "usage": {"input": int, "output": int,
                   "cache_creation": int, "cache_read": int}}
    """
    if mock:
        return _call_mock()
    return _call_real(messages, tools, system)


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


def _call_real(messages, tools, system) -> dict:
    """Hit the real Messages API. Imports/keys are resolved lazily."""
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

    client = anthropic.Anthropic(api_key=api_key)
    kwargs = dict(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        # Thinking runs adaptively on this model whether or not it is asked
        # for; display defaults to omitted, which returns thinking blocks
        # with empty text. Asking for summaries puts the reasoning into the
        # transcript. Display affects visibility only - thinking is billed
        # the same either way - so this costs nothing and makes the run
        # auditable rather than a record of conclusions with no working.
        thinking={"type": "adaptive", "display": "summarized"},
        system=system,
        messages=messages,
    )
    if tools:
        kwargs["tools"] = tools
    response = client.messages.create(**kwargs)

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
        "usage": {
            "input": response.usage.input_tokens,
            "output": response.usage.output_tokens,
            "cache_creation": getattr(
                response.usage, "cache_creation_input_tokens", 0) or 0,
            "cache_read": getattr(
                response.usage, "cache_read_input_tokens", 0) or 0,
        },
    }
