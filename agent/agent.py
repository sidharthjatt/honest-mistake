"""agent.py — Honest Mistake, Layer 2 ReAct loop.

Drives the audit agent: call the model, execute whatever tools it asks
for, feed the results back, repeat until it stops or a safeguard fires.

The loop does not read, parse, or interpret the agent's final answer. It
returns the text verbatim along with a record of how the run went, and
extraction is left to the scoring layer. It also never imports the
answer key: a loop that could see the ground truth could, however
accidentally, be shaped by it.

Several terminations are easy to confuse and are kept strictly apart. A
turn that ends because the model finished has no tool calls; so does one
cut off by the output limit, one declined on safety grounds, and one
that paused. Only the stop_reason distinguishes them, so it is
classified before anything else, and only "end_turn" yields a completed
run. An unrecognised value is never treated as a completion.

Assistant turns are stored as the raw content blocks the model produced,
so thinking blocks survive to be echoed back on the next request.

Run it against the fixtures with no API key:
    .venv/bin/python -m agent.agent
"""

import json
from dataclasses import dataclass, field
from typing import Any

from agent.llm import call_llm
from agent.prompts import build_system_prompt
from agent.tools import TOOL_SCHEMAS, ToolLayer

DEFAULT_MAX_TURNS = 12
DEFAULT_MAX_TOOL_CALLS = 40

COMPLETED = "completed"
TRUNCATED = "truncated"
REFUSAL = "refusal"
PAUSED = "paused"
STOP_SEQUENCE = "stop_sequence"
UNKNOWN_STOP = "unknown_stop_reason"
TURN_LIMIT = "turn_limit"
CALL_LIMIT = "call_limit"

# Only end_turn means the model decided it was done. Every other value,
# recognised or not, ends the run without producing a usable answer, and
# the raw stop_reason is recorded either way.
#
#   max_tokens     output limit hit mid-thought
#   refusal        declined on safety grounds; carries no tool calls, so
#                  without this it would look exactly like a finished turn
#   pause_turn     the turn paused and expects to be resumed; only arises
#                  with server-side tools, which this project does not use
#   stop_sequence  a configured stop sequence fired. No stop sequences are
#                  sent, so seeing this means the run stopped for a reason
#                  nobody asked for. If stop sequences are ever configured
#                  deliberately, reclassify this as a completion.
#   tool_use       handled by the tool branch, never reaches this mapping
_STOP_REASON_TERMINATION = {
    "max_tokens": TRUNCATED,
    "refusal": REFUSAL,
    "pause_turn": PAUSED,
    "stop_sequence": STOP_SEQUENCE,
}


@dataclass
class AuditRun:
    """Everything a caller needs to score or diagnose one run."""

    final_text: str
    termination: str
    last_stop_reason: str
    turns: int
    tool_calls: int
    usage: dict[str, int]
    tool_call_log: list[dict]
    config_id: str
    messages: list[dict] = field(repr=False, default_factory=list)

    @property
    def is_usable(self) -> bool:
        """True only for a run the model itself chose to end."""
        return self.termination == COMPLETED

    def summary(self) -> dict[str, Any]:
        """The run without the message history, for printing or logging."""
        return {
            "termination": self.termination,
            "is_usable": self.is_usable,
            "last_stop_reason": self.last_stop_reason,
            "turns": self.turns,
            "tool_calls": self.tool_calls,
            "usage": dict(self.usage),
            "config_id": self.config_id,
            "final_text_chars": len(self.final_text),
            "messages": len(self.messages),
        }


def _assistant_content(reply: dict) -> list[dict]:
    """The assistant turn's content blocks, for the message history.

    Uses the raw blocks the model produced. Rebuilding from text and
    tool calls would silently drop thinking blocks, which have to be
    echoed back unchanged when the conversation continues on the same
    model. The fallback covers a reply that carries no raw blocks at
    all, and is lossy by definition.
    """
    blocks = reply.get("content")
    if blocks:
        return [dict(b) for b in blocks]

    rebuilt: list[dict] = []
    if reply["text"]:
        rebuilt.append({"type": "text", "text": reply["text"]})
    for call in reply["tool_calls"]:
        rebuilt.append({
            "type": "tool_use",
            "id": call["id"],
            "name": call["name"],
            "input": call["input"],
        })
    return rebuilt


def run_audit(
    tools: ToolLayer,
    mock: bool = False,
    max_turns: int = DEFAULT_MAX_TURNS,
    max_tool_calls: int = DEFAULT_MAX_TOOL_CALLS,
    system: str | None = None,
) -> AuditRun:
    """Run the loop to termination and return the record of it.

    The caller supplies the ToolLayer, so the caller decides the
    dictionary configuration; the loop neither inspects nor changes it.
    The tool call log is not cleared here — a caller reusing one layer
    across runs should reset it between them.

    When `system` is omitted the prompt is built from this call's own
    ceilings, so the limits the agent is told about are by construction
    the limits this loop enforces.
    """
    if system is None:
        system = build_system_prompt(max_turns, max_tool_calls)
    messages: list[dict] = [{
        "role": "user",
        "content": "Begin your review.",
    }]

    usage = {"input": 0, "output": 0, "cache_creation": 0, "cache_read": 0}
    turns = 0
    calls_made = 0
    final_text = ""
    last_stop_reason = ""
    termination = TURN_LIMIT

    while True:
        if turns >= max_turns:
            termination = TURN_LIMIT
            break

        reply = call_llm(messages, TOOL_SCHEMAS, system, mock=mock)
        turns += 1
        for k in usage:
            usage[k] += reply["usage"].get(k, 0)

        text = reply["text"]
        tool_calls = reply["tool_calls"]
        last_stop_reason = reply["stop_reason"]
        if text:
            final_text = text

        blocks = _assistant_content(reply)
        if blocks:
            messages.append({"role": "assistant", "content": blocks})

        # Classified before the tool-call test. Several stop reasons
        # carry no tool calls and would otherwise be indistinguishable
        # from a finished turn by content alone.
        if last_stop_reason in _STOP_REASON_TERMINATION:
            termination = _STOP_REASON_TERMINATION[last_stop_reason]
            break

        if tool_calls:
            # Enforced before the batch runs, so the recorded call count
            # never exceeds the ceiling that was set.
            if calls_made + len(tool_calls) > max_tool_calls:
                termination = CALL_LIMIT
                break
        elif last_stop_reason == "end_turn":
            termination = COMPLETED
            break
        else:
            # An unrecognised stop reason never becomes a completion.
            # The raw value is kept in last_stop_reason.
            termination = UNKNOWN_STOP
            break

        results = []
        for call in tool_calls:
            # dispatch never raises; a rejected call comes back as a
            # message, which is fed to the model like any other result
            # so that it can correct itself and carry on.
            output = tools.dispatch(call["name"], call["input"])
            calls_made += 1
            results.append({
                "type": "tool_result",
                "tool_use_id": call["id"],
                "content": json.dumps(output, default=str),
            })

        messages.append({"role": "user", "content": results})

    log = tools.get_call_log()
    return AuditRun(
        final_text=final_text,
        termination=termination,
        last_stop_reason=last_stop_reason,
        turns=turns,
        tool_calls=calls_made,
        usage=usage,
        tool_call_log=log["calls"],
        config_id=log["config"]["config_id"],
        messages=messages,
    )


def _demo() -> None:
    """Run the loop against the mock fixtures. No API key required."""
    from agent.llm import reset_mock

    reset_mock()
    tools = ToolLayer(include_populated=True)
    run = run_audit(tools, mock=True)  # prompt built from the default ceilings
    print(json.dumps(run.summary(), indent=2))
    print()
    print("final text:")
    print(f"  {run.final_text!r}")


if __name__ == "__main__":
    _demo()
