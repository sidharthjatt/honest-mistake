"""Phase 4: the detection runner and the spec-request path.

Implements the protocol in PREREGISTRATION_PHASE4.md section 1, as amended by
A1 (one run), A3 (the prompts and how they are sent) and A4 (the question
text and the spec request's user message).

Every request goes through agent.llm.call_llm, so the request builder, the
token count, the ledger check and the ledger record are the code that served
run11. Nothing here builds a request of its own.

The mock mode replaces the API client with scripted replies. It runs that
same path, ledger included, against a temporary ledger file. It refuses the
real ledger and never builds a real client.

The runner does not score. It parses the final reply against the frozen
output format and rejects anything that does not match, without repairing
it. Turns and output tokens per turn are recorded for every episode, since
the pilot exists to measure them.
"""

from __future__ import annotations

import contextlib
import copy
import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from agent import data_dictionary, ledger, llm
from agent.agent import (_STOP_REASON_TERMINATION, BUDGET_CAP, CALL_LIMIT,
                         COMPLETED, TURN_LIMIT, UNKNOWN_STOP,
                         _assistant_content)
from agent.ledger import BudgetExceeded
from agent.tools import TOOL_SCHEMAS, ToolLayer

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "layer3" / "prompts"
DETECTOR_PROMPT = PROMPTS / "phase4_detector_system.txt"
SPEC_PROMPT = PROMPTS / "phase4_spec_system.txt"

# From amendment A3. A prompt file whose bytes do not hash to these is refused.
DETECTOR_SHA256 = "db401deb03318893e45b7b2fbad804ac7560233b5c4f9d26e25afd0af281e0d8"
SPEC_SHA256 = "6c3cca8f5fca3df3e463f71bdd83a4c6463e6d0280521808bea9475a4db950ca"

RUNS_DIR = ROOT / "outputs" / "layer3" / "phase4_runs"
REAL_LEDGER = ledger.LEDGER_PATH

MAX_TURNS = 8
MAX_TOOL_CALLS = 16
LABELS = ("answerable", "answerable_with_difference", "not_answerable")
TOOL_NAMES = frozenset(s["name"] for s in TOOL_SCHEMAS)

# Worded exactly as in section 2 (items A to C) and section 4 (near-misses),
# Markdown code formatting included. question_text() removes the formatting,
# as A4 fixes; nothing else about a question changes.
QUESTIONS = {
    "A1": "How many features does the model read, and what are they?",
    "A2": "Is `purpose_wedding` constant on the test set?",
    "A3": "What is `all_util`'s standalone ROC-AUC within 2014?",
    "A4": "Is `all_util` documented in the data dictionary?",
    "A5": "Where does `max_bal_bc_was_missing` rank by mean absolute SHAP?",
    "A6": "How many 2014 rows does `all_util`'s coverage profile cover?",
    "A7": "Which 15 features are most correlated with `all_util` on the test set?",
    "A8": "How does held-out ROC-AUC change when the model is retrained without its highest-ranked feature?",
    "A9": "Is `addr_state` one of the model's inputs?",
    "B1": "How does held-out ROC-AUC change when the model is retrained without `percent_bc_gt_75`?",
    "B2": "Which features are most correlated with `purpose_wedding` on the test set?",
    "B3": "What does `addr_state`'s SHAP distribution look like?",
    "B4": "What share of `addr_state`'s rows hold exactly zero, in each year?",
    "B5": "What is `addr_state`'s standalone ROC-AUC on the test set?",
    "B6": "Which features are most correlated with `addr_state` on the test set?",
    "C1": "How does held-out ROC-AUC change when `term` and `sub_grade` are removed together?",
    "C2": "What is `all_util`'s 99th percentile value on the training split?",
    "C3": "When `all_util` is high, does its SHAP contribution push predictions up?",
    "C4": "Which test rows carry `all_util`'s largest SHAP attributions?",
    "C5": "What is `all_util`'s point-biserial correlation with the outcome on the training split?",
    "C6": "Which features are most correlated with `all_util` on the training split?",
    "C7": "What is the model's ROC-AUC on the 2016 vintage?",
    "NM1": "What is `max_bal_bc_was_missing`'s mean absolute SHAP value?",
    "NM3": "How many dictionary entries contain the literal text 'balance' in their name or definition?",
    "NM4": "What share of `loan_amnt`'s values were missing in the source data, in each year?",
    "NM6": "In what percentage of test rows does `all_util` contribute exactly zero to the prediction?",
}

# Section 3 expects a spec or a decline only for items in parts b and c.
SPEC_ELIGIBLE = frozenset(k for k in QUESTIONS if k[0] in "BC")


def question_text(item: str) -> str:
    """The question as sent: section 2's wording without code formatting."""
    return re.sub(r"`([^`]*)`", r"\1", QUESTIONS[item])


class PromptMismatch(RuntimeError):
    """A prompt file no longer hashes to the value recorded in A3."""


def load_prompt(path: Path, expected_sha256: str) -> str:
    raw = Path(path).read_bytes()
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise PromptMismatch(f"{Path(path).name} hashes to {digest}, not the "
                             f"{expected_sha256} recorded in A3. A changed "
                             f"prompt needs its own amendment first.")
    return raw.decode("utf-8")


# ---------------------------------------------------------------- parsing

class ParseError(ValueError):
    """A final reply does not match the frozen output format."""


def _reject_constant(name):
    raise ValueError(f"non-finite number {name}")


def _one_object(text) -> dict:
    """Exactly one JSON object, with only whitespace around it. No repair."""
    if not isinstance(text, str) or not text.strip():
        raise ParseError("the reply holds no text")
    try:
        obj = json.loads(text, parse_constant=_reject_constant)
    except ValueError as exc:
        raise ParseError(f"the reply is not exactly one JSON object: {exc}") from None
    if not isinstance(obj, dict):
        raise ParseError(f"the reply is a JSON {type(obj).__name__}, not an object")
    return obj


def _exact_keys(obj: dict, keys: set, where: str) -> None:
    if set(obj) != keys:
        raise ParseError(f"{where} has keys {sorted(obj)}, expected {sorted(keys)}")


def parse_detector_output(text: str) -> dict:
    obj = _one_object(text)
    _exact_keys(obj, {"label", "calls", "difference_or_missing"}, "the output")
    label = obj["label"]
    if label not in LABELS:
        raise ParseError(f"label {label!r} is not one of {list(LABELS)}")
    calls = obj["calls"]
    if not isinstance(calls, list) or not calls:
        raise ParseError("calls is not a non-empty list")
    for i, call in enumerate(calls):
        if not isinstance(call, dict):
            raise ParseError(f"calls[{i}] is not an object")
        _exact_keys(call, {"tool", "arguments", "field"}, f"calls[{i}]")
        if call["tool"] not in TOOL_NAMES:
            raise ParseError(f"calls[{i}].tool {call['tool']!r} is not one of the eight tools")
        if not isinstance(call["arguments"], dict):
            raise ParseError(f"calls[{i}].arguments is not an object")
        if not isinstance(call["field"], str) or not call["field"].strip():
            raise ParseError(f"calls[{i}].field is not a non-empty string")
    dom = obj["difference_or_missing"]
    if label == "answerable":
        if dom is not None:
            raise ParseError("difference_or_missing must be null when the label is answerable")
    elif not isinstance(dom, str) or not dom.strip():
        raise ParseError(f"difference_or_missing must be a non-empty string when the label is {label}")
    return obj


def parse_spec_output(text: str) -> dict:
    """Shape only. Section 3's spec rules are scoring, applied elsewhere."""
    obj = _one_object(text)
    if set(obj) == {"decline"}:
        if not isinstance(obj["decline"], str) or not obj["decline"].strip():
            raise ParseError("decline is not a non-empty string")
        return obj
    if set(obj) != {"spec"}:
        raise ParseError(f"the output has keys {sorted(obj)}, expected exactly spec or decline")
    spec = obj["spec"]
    if not isinstance(spec, dict):
        raise ParseError("spec is not an object")
    _exact_keys(spec, {"name", "description", "input_schema", "data_source"}, "spec")
    for key in ("name", "description", "data_source"):
        if not isinstance(spec[key], str) or not spec[key].strip():
            raise ParseError(f"spec.{key} is not a non-empty string")
    if not isinstance(spec["input_schema"], dict):
        raise ParseError("spec.input_schema is not an object")
    return obj


# ---------------------------------------------------------------- detection

@dataclass
class Episode:
    item: str
    question: str
    label_in_ledger: str
    prompt_sha256: str
    termination: str
    last_stop_reason: str
    turns: int
    tool_calls: int
    usage_per_request: list[dict]
    final_text: str
    output: dict | None
    parse_error: str | None
    retrieval: str
    tool_call_log: list[dict] = field(default_factory=list)
    messages: list[dict] = field(repr=False, default_factory=list)

    @property
    def output_tokens_per_turn(self) -> list[int]:
        return [u["output"] for u in self.usage_per_request]

    @property
    def cost_usd(self) -> float:
        return sum(ledger.cost_usd(llm.MODEL, u) for u in self.usage_per_request)

    def summary(self) -> dict:
        return {
            "item": self.item, "question": self.question,
            "termination": self.termination, "last_stop_reason": self.last_stop_reason,
            "turns": self.turns, "tool_calls": self.tool_calls,
            "output_tokens_per_turn": self.output_tokens_per_turn,
            "usage_per_request": self.usage_per_request,
            "cost_usd": round(self.cost_usd, 6),
            "output": self.output, "parse_error": self.parse_error,
            "retrieval": self.retrieval, "prompt_sha256": self.prompt_sha256,
        }


def run_detection(item: str, tools: ToolLayer, label: str) -> Episode:
    """One detection episode, to termination. Never retried."""
    system = load_prompt(DETECTOR_PROMPT, DETECTOR_SHA256)
    question = question_text(item)
    data_dictionary.reset_retrieval_paths()
    tools.reset_call_log()

    messages: list[dict] = [{"role": "user", "content": question}]
    usage: list[dict] = []
    turns = calls_made = 0
    final_text, last_stop_reason, termination = "", "", TURN_LIMIT

    while True:
        if turns >= MAX_TURNS:
            termination = TURN_LIMIT
            break
        try:
            reply = llm.call_llm(messages, TOOL_SCHEMAS, system, mock=False,
                                 cache=llm.CACHE_MOVING, label=label)
        except BudgetExceeded:
            termination = BUDGET_CAP
            break
        turns += 1
        usage.append(dict(reply["usage"]))
        # Only the last reply's text is the output. An earlier turn's text is
        # never carried forward to stand in for an empty final reply.
        final_text = reply["text"]
        last_stop_reason = reply["stop_reason"]
        tool_calls = reply["tool_calls"]

        blocks = _assistant_content(reply)
        if blocks:
            messages.append({"role": "assistant", "content": blocks})

        if last_stop_reason in _STOP_REASON_TERMINATION:
            termination = _STOP_REASON_TERMINATION[last_stop_reason]
            break
        if tool_calls:
            if calls_made + len(tool_calls) > MAX_TOOL_CALLS:
                termination = CALL_LIMIT
                break
        elif last_stop_reason == "end_turn":
            termination = COMPLETED
            break
        else:
            termination = UNKNOWN_STOP
            break

        results = []
        for call in tool_calls:
            output = tools.dispatch(call["name"], call["input"])
            calls_made += 1
            results.append({"type": "tool_result", "tool_use_id": call["id"],
                            "content": json.dumps(output, default=str)})
        messages.append({"role": "user", "content": results})

    output, parse_error = None, None
    if termination == COMPLETED:
        try:
            output = parse_detector_output(final_text)
        except ParseError as exc:
            parse_error = str(exc)

    return Episode(
        item=item, question=question, label_in_ledger=label,
        prompt_sha256=DETECTOR_SHA256, termination=termination,
        last_stop_reason=last_stop_reason, turns=turns, tool_calls=calls_made,
        usage_per_request=usage, final_text=final_text, output=output,
        parse_error=parse_error, retrieval=tools.run_config()["retrieval"],
        tool_call_log=tools.get_call_log()["calls"], messages=messages)


# ---------------------------------------------------------------- spec requests

def spec_user_message(question: str, detector_text: str) -> str:
    """The single user message of a spec request, exactly as A4 fixes it."""
    return (f"Question: {question}\n\nCheck output:\n{detector_text}\n\n"
            f"Tool definitions:\n{json.dumps(TOOL_SCHEMAS)}")


@dataclass
class SpecRequest:
    item: str
    question: str
    prompt_sha256: str
    termination: str
    last_stop_reason: str
    usage: dict | None
    text: str
    output: dict | None
    parse_error: str | None
    user_message: str = field(repr=False, default="")

    @property
    def cost_usd(self) -> float:
        return ledger.cost_usd(llm.MODEL, self.usage) if self.usage else 0.0

    def summary(self) -> dict:
        return {"item": self.item, "termination": self.termination,
                "last_stop_reason": self.last_stop_reason, "usage": self.usage,
                "output_tokens": self.usage["output"] if self.usage else None,
                "cost_usd": round(self.cost_usd, 6), "output": self.output,
                "parse_error": self.parse_error, "prompt_sha256": self.prompt_sha256}


def run_spec_request(episode: Episode, label: str) -> SpecRequest:
    """One spec request for an item the detector labelled not_answerable."""
    if episode.item not in SPEC_ELIGIBLE:
        raise ValueError(f"{episode.item} is not in parts b or c, so no spec request is made for it")
    if episode.output is None or episode.output["label"] != "not_answerable":
        raise ValueError(f"{episode.item} was not labelled not_answerable, so no spec request is made for it")
    system = load_prompt(SPEC_PROMPT, SPEC_SHA256)
    content = spec_user_message(episode.question, episode.final_text)
    messages = [{"role": "user", "content": content}]
    try:
        reply = llm.call_llm(messages, [], system, mock=False,
                             cache=llm.CACHE_MOVING, label=label)
    except BudgetExceeded:
        return SpecRequest(episode.item, episode.question, SPEC_SHA256, BUDGET_CAP,
                           "", None, "", None, None, content)

    stop = reply["stop_reason"]
    if stop in _STOP_REASON_TERMINATION:
        termination = _STOP_REASON_TERMINATION[stop]
    elif stop == "end_turn" and not reply["tool_calls"]:
        termination = COMPLETED
    else:
        termination = UNKNOWN_STOP
    output, parse_error = None, None
    if termination == COMPLETED:
        try:
            output = parse_spec_output(reply["text"])
        except ParseError as exc:
            parse_error = str(exc)
    return SpecRequest(episode.item, episode.question, SPEC_SHA256, termination,
                       stop, dict(reply["usage"]), reply["text"], output,
                       parse_error, content)


# ---------------------------------------------------------------- preflight and records

def preflight_retrieval() -> dict:
    """Section 1: a run whose retrieval is degraded is not started."""
    from agent import retrieval
    stats = retrieval.index_stats()
    if (stats["rows"], stats["non_null_embeddings"], stats["dimension"]) != (224, 224, 384):
        raise RuntimeError(f"the retrieval index is not as verified in step 0b: {stats}")
    return stats


def write_record(mode: str, label: str, episodes: list[Episode],
                 specs: list[SpecRequest], skipped: list[dict],
                 out_dir: Path = RUNS_DIR) -> Path:
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    run_dir = Path(out_dir) / f"{stamp}__{mode}__{label}"
    run_dir.mkdir(parents=True, exist_ok=False)
    manifest = {
        "_MODE": ("REAL RUN - LIVE API CALLS." if mode == "REAL"
                  else "MOCK RUN - scripted replies, no API request."),
        "mode": mode, "label": label,
        "generated": datetime.now().isoformat(timespec="seconds"),
        "model": llm.MODEL, "max_tokens_per_turn": llm.MAX_TOKENS,
        "thinking": llm.THINKING, "cache": llm.CACHE_MOVING,
        "limits": {"max_turns": MAX_TURNS, "max_tool_calls": MAX_TOOL_CALLS},
        "prompts": {"detector_sha256": DETECTOR_SHA256, "spec_sha256": SPEC_SHA256},
        "episodes": [e.summary() for e in episodes],
        "spec_requests": [s.summary() for s in specs],
        "spec_requests_not_made": skipped,
        "totals": {
            "episodes": len(episodes),
            "detection_requests": sum(e.turns for e in episodes),
            "detection_cost_usd": round(sum(e.cost_usd for e in episodes), 6),
            "spec_requests": sum(1 for s in specs if s.usage),
            "spec_cost_usd": round(sum(s.cost_usd for s in specs), 6),
        },
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest, indent=2, default=str))
    (run_dir / "episodes.json").write_text(json.dumps(
        [{"item": e.item, "final_text": e.final_text, "tool_call_log": e.tool_call_log,
          "messages": e.messages} for e in episodes], indent=2, default=str))
    (run_dir / "spec_requests.json").write_text(json.dumps(
        [{"item": s.item, "user_message": s.user_message, "text": s.text} for s in specs],
        indent=2, default=str))
    return run_dir


def run_items(items: list[str], spec_items: list[str], tools: ToolLayer,
              label: str) -> tuple[list[Episode], list[SpecRequest], list[dict]]:
    episodes: list[Episode] = []
    for item in items:
        episode = run_detection(item, tools, label)
        episodes.append(episode)
        if episode.termination == BUDGET_CAP:
            break
    specs, skipped = [], []
    for item in spec_items:
        episode = next((e for e in episodes if e.item == item), None)
        if episode is None:
            skipped.append({"item": item, "reason": "no detection episode ran for it"})
        elif episode.output is None or episode.output["label"] != "not_answerable":
            got = episode.output["label"] if episode.output else episode.termination
            skipped.append({"item": item, "reason": f"the detector's result was {got}, not not_answerable"})
        else:
            spec = run_spec_request(episode, label)
            specs.append(spec)
            if spec.termination == BUDGET_CAP:
                break
    return episodes, specs, skipped


# ---------------------------------------------------------------- mock client

class _Block:
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def model_dump(self, exclude_none=True):
        return {k: v for k, v in self.__dict__.items() if not (exclude_none and v is None)}


def scripted(content: list[dict], stop_reason: str, output: int = 500, input: int = 2,
             cache_creation: int = 0, cache_read: int = 0) -> dict:
    """One scripted reply, in the shape the mock client replays."""
    return {"content": content, "stop_reason": stop_reason,
            "usage": {"input": input, "output": output,
                      "cache_creation": cache_creation, "cache_read": cache_read}}


class MockClient:
    """Stands in for anthropic.Anthropic. Replays scripted replies and sends nothing."""

    def __init__(self, replies: list[dict], count: int = 2500):
        self.replies = list(replies)
        self.count = count
        self.counted: list[dict] = []
        self.created: list[dict] = []
        self.messages = SimpleNamespace(count_tokens=self._count, create=self._create)

    def _count(self, **kw):
        self.counted.append(copy.deepcopy(kw))
        return SimpleNamespace(input_tokens=self.count)

    def _create(self, **kw):
        if not self.replies:
            raise RuntimeError("the mock client has no scripted reply left")
        self.created.append(copy.deepcopy(kw))
        r = self.replies.pop(0)
        u = r["usage"]
        return SimpleNamespace(
            content=[_Block(**b) for b in r["content"]], stop_reason=r["stop_reason"],
            usage=SimpleNamespace(input_tokens=u["input"], output_tokens=u["output"],
                                  cache_creation_input_tokens=u["cache_creation"],
                                  cache_read_input_tokens=u["cache_read"]))


@contextlib.contextmanager
def mocked(client: MockClient, ledger_path: Path):
    """Route call_llm to a mock client and a temporary ledger, then restore both."""
    ledger_path = Path(ledger_path)
    if ledger_path.resolve() == Path(REAL_LEDGER).resolve():
        raise ValueError("a mock run must not use the real ledger")
    saved = (llm._client, ledger.LEDGER_PATH)
    llm._client = lambda: client
    ledger.LEDGER_PATH = ledger_path
    try:
        yield client
    finally:
        llm._client, ledger.LEDGER_PATH = saved


def fabricated_detection_replies(n: int) -> list[str]:
    """Fabricated replies for the mock mode: one tool call, then a final answer."""
    final = json.dumps({"label": "not_answerable",
                        "calls": [{"tool": "get_shap_ranking", "arguments": {"top_n": 1},
                                   "field": "ranking"}],
                        "difference_or_missing": "Fabricated mock reply."})
    return [
        scripted([{"type": "thinking", "thinking": "Fabricated mock turn.", "signature": f"mock-sig-{n}-1"},
                  {"type": "tool_use", "id": f"toolu_mock_{n}_1", "name": "get_shap_ranking",
                   "input": {"top_n": 1}}], "tool_use", output=700, cache_creation=2500),
        scripted([{"type": "thinking", "thinking": "Fabricated mock turn.", "signature": f"mock-sig-{n}-2"},
                  {"type": "text", "text": final}], "end_turn", output=400,
                 cache_creation=2200, cache_read=2500),
    ]


def fabricated_spec_reply() -> dict:
    return scripted([{"type": "text", "text": json.dumps({"decline": "Fabricated mock reply."})}],
                    "end_turn", output=300, cache_creation=2230)
