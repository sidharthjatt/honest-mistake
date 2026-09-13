"""layer2_trajectory.py — trajectory metrics over the Layer 2 run records.

Implements the fourteen metrics specified in PREREGISTRATION.md, as amended
by A1 through A9. The specification is the authority. Where this file and
the specification disagree, this file is wrong.

Every run is passed through two gates before any metric runs on it: the
validity precondition, then the scope rule for that metric. A run that fails
a gate gets an exclusion row carrying the reason. Every (run, metric) pair
produces exactly one row, computed, excluded or withheld, so nothing is
skipped without a trace.

Missing data is never filled in. A field the specification needs that is
absent from a record raises MissingData, and the script stops without
writing any output.

Run:
    .venv/bin/python scripts/layer2_trajectory.py
    .venv/bin/python scripts/layer2_trajectory.py --run <dir> [--run <dir> ...]

Inputs taken by hand, never decided here:
    --adjudications FILE      M17b sources for unmatched tokens (derived, quoted,
                              prompt; two or more make multiply_sourced, A9)
    --rate-verification FILE  external verification of the M14 rate (A3)
"""

import argparse
import inspect
import json
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from agent.answer_key import CANARY  # noqa: E402
from agent.eval_canary import parse_final_answer  # noqa: E402
from agent.tools import _SCHEMA_ARGS, ToolLayer  # noqa: E402

RUNS_DIR = PROJECT_ROOT / "outputs" / "agent_runs"
OUT_JSON = PROJECT_ROOT / "outputs" / "agent_cache" / "trajectory_metrics.json"

SPECIFICATION = "PREREGISTRATION.md"
AMENDMENTS_APPLIED = ["A1", "A2", "A3", "A4", "A5", "A6", "A7", "A8", "A9"]

METRICS = ["M1", "M3", "M4", "M5", "M6", "M8", "M9", "M10", "M11",
           "M14", "M16", "M17a", "M17b", "M18"]

# Scope rules table in the specification.
ALL_REAL = "all_real"
USABLE_REAL = "usable_real"
USABLE_REAL_CANARY = "usable_real_canary"
SCOPE_OF = {m: USABLE_REAL for m in METRICS}
SCOPE_OF.update({"M1": ALL_REAL, "M14": ALL_REAL, "M18": USABLE_REAL_CANARY})

# Validity precondition, as amended by A1 and A4.
RETRIEVAL_MARKER = "-retrieval-"
RETRIEVAL_PASSING = {"pgvector-bge-small-en-v1.5", "unused"}

# "Tools available on a surface: the entries in TOOL_SCHEMAS at that
# version, five at 1.0 and eight at 2.0." The 1.0 list is TOOL_SCHEMAS at
# eb89b98, the commit that added the v1.0 records; 2.0 is TOOL_SCHEMAS at
# HEAD, unchanged since 97a339c. The argument names of the five 1.0 tools
# are identical at eb89b98 and HEAD, so _SCHEMA_ARGS from HEAD serves both
# surfaces. The test suite checks all of this against git.
SURFACE_TOOLS = {
    "1.0": ("lookup_feature", "search_data_dictionary", "get_shap_ranking",
            "get_feature_shap_detail", "get_ablation_result"),
    "2.0": ("lookup_feature", "search_data_dictionary", "get_shap_ranking",
            "get_feature_shap_detail", "get_ablation_result",
            "get_feature_coverage", "get_feature_target_association",
            "get_correlated_features"),
}

REJECTED_OUTCOMES = ("unknown_tool", "unexpected_argument", "bad_arguments",
                     "failed")
EMPTY_OUTCOMES = ("not_found", "not_precomputed", "not_available",
                  "match_count=0")
MATRIX_TOOLS = ("get_feature_shap_detail", "get_feature_coverage",
                "get_feature_target_association")

# M10 step 2 names these two defaults. They are read from the method
# signatures and checked against the specification before use.
M10_SPEC_DEFAULTS = {"get_shap_ranking": {"top_n": 20},
                     "get_correlated_features": {"top_k": 5}}

# M14, as amended by A3.
M14_RATES = {"claude-sonnet-5": {"input_per_mtok": 2.00,
                                 "output_per_mtok": 10.00}}
M14_RATES_TAKEN = "claude-api reference cached 2026-06-24"
M14_VERIFICATION_SOURCES = ("anthropic_console_billing",
                            "anthropic_first_party_pricing_page")

CONFIDENCE_VALUES = ("high", "medium", "low")

# M17b numeric token, as amended by A7.
#   TOKEN_BODY    digits with optional thousands separators, optional
#                 decimal part, optional trailing percent sign
#   CORE          a body not begun directly after a digit or decimal point,
#                 and not followed by a letter, underscore, digit, or a
#                 decimal point that starts a longer number. Together these
#                 make a token a maximal match.
#   SCIENTIFIC    1e-3 form. Not parsed; masked out and reported (A7).
#   STRING_NUMBER the full token form a string payload leaf must match (A7).
TOKEN_BODY = r"(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?%?"
CORE = re.compile(rf"(?<![\d.])({TOKEN_BODY})(?![A-Za-z_\d]|\.\d)")
SCIENTIFIC = re.compile(
    r"(?<![A-Za-z_\d.])[+-]?\d+(?:\.\d+)?[eE][+-]?\d+(?![A-Za-z_\d])")
STRING_NUMBER = re.compile(rf"[+-]?{TOKEN_BODY}")
SIGN_SEPARATOR_BEFORE = set("0123456789.)]}")

# A8 requires any figure whose classification turned on a tie to be named.
# JSON parsing discards the payload's decimal text, so an exact tie cannot
# be recognised exactly. A token is treated as sitting on a tie with a
# payload number when its distance from that number is within this fraction
# of the half-interval of its own boundary. This threshold is an
# implementation choice, not part of the specification.
TIE_RELATIVE_EPSILON = 1e-9

# M17b classes, as amended by A9. The last four are assigned by hand only.
M17B_CLASSES = ("matched", "unmatched", "derived", "quoted", "prompt",
                "multiply_sourced")
HAND_SOURCE_CLASSES = ("derived", "quoted", "prompt")
SOURCE_EVIDENCE_FIELDS = {"derived": ("computation", "source_values"),
                          "quoted": ("payload_string", "seq"),
                          "prompt": ("prompt_text", "rendered_from_commit")}


class MissingData(Exception):
    """A field the specification needs is absent. The run stops."""


class UnexpectedData(Exception):
    """A value the specification does not provide for. The run stops."""


# ----------------------------------------------------------------------
# Record access. Each file is read only when a metric in scope needs it,
# so a run excluded by a gate has only its manifest opened.
# ----------------------------------------------------------------------
class Run:
    def __init__(self, directory: Path):
        self.directory = Path(directory)
        self.name = self.directory.name
        self._manifest = self._calls = self._messages = self._answer = None

    def _read(self, filename: str) -> str:
        path = self.directory / filename
        if not path.is_file():
            raise MissingData(f"{self.name}: {filename} is absent")
        return path.read_text()

    @property
    def manifest(self) -> dict:
        if self._manifest is None:
            self._manifest = json.loads(self._read("manifest.json"))
        return self._manifest

    @property
    def calls(self) -> list[dict]:
        if self._calls is None:
            log = json.loads(self._read("tool_call_log.json"))
            if "calls" not in log:
                raise MissingData(f"{self.name}: tool_call_log.json has no calls")
            self._calls = log["calls"]
        return self._calls

    @property
    def messages(self) -> list[dict]:
        if self._messages is None:
            doc = json.loads(self._read("messages.json"))
            if "messages" not in doc:
                raise MissingData(f"{self.name}: messages.json has no messages")
            self._messages = doc["messages"]
        return self._messages

    @property
    def final_answer(self) -> str:
        if self._answer is None:
            self._answer = self._read("final_answer.txt")
        return self._answer

    def field(self, *path):
        """A manifest field by path. Absent is MissingData, never a default."""
        node = self.manifest
        for key in path:
            if not isinstance(node, dict) or key not in node:
                raise MissingData(
                    f"{self.name}: manifest field {'.'.join(path)} is absent")
            node = node[key]
        return node


def call_field(run: Run, call: dict, key: str):
    if key not in call:
        raise MissingData(
            f"{run.name}: logged call {call.get('seq', '?')} has no {key}")
    return call[key]


# ----------------------------------------------------------------------
# Gates
# ----------------------------------------------------------------------
def retrieval_segment(config_id: str) -> str | None:
    """The retrieval value inside a config_id, or None if it has none.

    run_config() writes `...-retrieval-<value>-<variant>`, where the variant
    is the final hyphen-separated part and the value may itself contain
    hyphens.
    """
    if RETRIEVAL_MARKER not in config_id:
        return None
    after = config_id.split(RETRIEVAL_MARKER, 1)[1]
    if "-" not in after:
        raise UnexpectedData(
            f"config_id {config_id!r} has a retrieval segment with no variant "
            f"after it")
    return after.rsplit("-", 1)[0]


def validity_gate(run: Run) -> tuple[bool, dict]:
    config_id = run.field("config_id")
    segment = retrieval_segment(config_id)
    if segment is None:
        return True, {"retrieval_segment": None}
    return segment in RETRIEVAL_PASSING, {"retrieval_segment": segment}


def attribute_canary(run: Run) -> tuple[bool, str]:
    """Canary attribution: field where present, derived from config_id where absent."""
    if "canary" in run.manifest:
        return bool(run.manifest["canary"]), "field"
    return run.field("config_id").endswith("-canary"), "derived"


def scope_gate(run: Run, metric: str, canary: bool) -> tuple[bool, str | None]:
    scope = SCOPE_OF[metric]
    if run.field("mode") != "REAL":
        return False, "scope_not_real"
    if scope == ALL_REAL:
        return True, None
    if run.field("is_usable") is not True:
        return False, "scope_not_usable"
    if scope == USABLE_REAL:
        return True, None
    if not canary:
        return False, "scope_not_canary"
    return True, None


def surface_tools(run: Run) -> tuple[str, ...]:
    version = run.field("tool_layer_version")
    if version not in SURFACE_TOOLS:
        raise UnexpectedData(
            f"{run.name}: tool_layer_version {version!r} has no tool list")
    return SURFACE_TOOLS[version]


# ----------------------------------------------------------------------
# Metrics
# ----------------------------------------------------------------------
def m1(run: Run) -> dict:
    return {"termination": run.field("termination"),
            "max_turns": run.field("limits", "max_turns"),
            "max_tool_calls": run.field("limits", "max_tool_calls"),
            "max_tokens_per_turn": run.field("max_tokens_per_turn")}


def m3(run: Run) -> dict:
    return {"turns": run.field("turns"), "tool_calls": run.field("tool_calls")}


def m4(run: Run) -> dict:
    counts = []
    for msg in run.messages:
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        n = sum(1 for b in content
                if isinstance(b, dict) and b.get("type") == "tool_use")
        if n:
            counts.append(n)
    return {"calls_per_tool_bearing_turn": counts,
            "tool_bearing_turns": len(counts),
            "mean": (sum(counts) / len(counts)) if counts else None}


def m5(run: Run) -> dict:
    total = len(run.calls)
    counts: dict[str, int] = {}
    for call in run.calls:
        tool = call_field(run, call, "tool")
        counts[tool] = counts.get(tool, 0) + 1
    return {"surface": run.field("tool_layer_version"),
            "logged_calls": total,
            "by_tool": {t: {"count": c, "share": (c / total) if total else None}
                        for t, c in sorted(counts.items())}}


def m6(run: Run) -> dict:
    """As amended by A7: only tool names available on the surface count."""
    available = surface_tools(run)
    names = {call_field(run, c, "tool") for c in run.calls}
    distinct = sorted(names & set(available))
    return {"surface": run.field("tool_layer_version"),
            "distinct_tools": distinct,
            "distinct_tool_count": len(distinct),
            "tools_available": len(available),
            "coverage": len(distinct) / len(available),
            "excluded_names_outside_surface": sorted(names - set(available))}


def m8(run: Run) -> dict:
    total = len(run.calls)
    breakdown = {o: 0 for o in REJECTED_OUTCOMES}
    rejected = 0
    for call in run.calls:
        if call_field(run, call, "ok") is False:
            rejected += 1
            outcome = call_field(run, call, "outcome")
            if outcome not in breakdown:
                raise UnexpectedData(
                    f"{run.name}: call {call.get('seq')} has ok == false with "
                    f"outcome {outcome!r}, outside the breakdown in the "
                    f"specification")
            breakdown[outcome] += 1
    return {"logged_calls": total, "rejected_calls": rejected,
            "rate": (rejected / total) if total else None,
            "by_outcome": breakdown}


def m9(run: Run) -> dict:
    total = len(run.calls)
    empty = sum(1 for c in run.calls
                if call_field(run, c, "outcome") in EMPTY_OUTCOMES)
    return {"logged_calls": total, "calls_returning_no_data": empty,
            "rate": (empty / total) if total else None}


def signature_defaults() -> dict[str, dict]:
    """Default argument values from the tool method signatures."""
    out = {}
    for tool in SURFACE_TOOLS["2.0"]:
        sig = inspect.signature(getattr(ToolLayer, tool))
        d = {p.name: p.default for p in sig.parameters.values()
             if p.name != "self" and p.default is not inspect.Parameter.empty}
        if d:
            out[tool] = d
    if out != M10_SPEC_DEFAULTS:
        raise UnexpectedData(
            f"tool signature defaults {out} differ from those named in the "
            f"specification {M10_SPEC_DEFAULTS}")
    return out


def canonical_form(call: dict, defaults: dict[str, dict]) -> tuple[str, str]:
    tool = call["tool"]
    args = call["arguments"]
    if not isinstance(args, dict):
        return tool, json.dumps(args, sort_keys=True)
    schema = set(_SCHEMA_ARGS.get(tool, ()))
    canon = {}
    for k, v in args.items():
        if k in schema and isinstance(v, str):
            canon[k] = v.strip()
        else:
            # In-schema non-strings, and every argument outside the schema,
            # are kept as written.
            canon[k] = v
    for k, v in defaults.get(tool, {}).items():
        if k not in canon:
            canon[k] = v
    return tool, json.dumps(canon, sort_keys=True)


def m10(run: Run) -> dict:
    defaults = signature_defaults()
    seen, repeats = set(), []
    for call in run.calls:
        call_field(run, call, "tool")
        call_field(run, call, "arguments")
        form = canonical_form(call, defaults)
        if form in seen:
            repeats.append(call_field(run, call, "seq"))
        seen.add(form)
    return {"logged_calls": len(run.calls), "repeat_calls": len(repeats),
            "repeat_seqs": repeats}


def m11(run: Run) -> dict:
    found, not_found, features = set(), set(), set()
    for call in run.calls:
        args = call_field(run, call, "arguments")
        if not isinstance(args, dict) or "feature" not in args:
            continue
        value = args["feature"]
        if not isinstance(value, str):
            raise UnexpectedData(
                f"{run.name}: call {call.get('seq')} has a non-string feature "
                f"argument {value!r}")
        feature = value.strip()
        features.add(feature)
        if call_field(run, call, "tool") in MATRIX_TOOLS:
            outcome = call_field(run, call, "outcome")
            if outcome == "found":
                found.add(feature)
            elif outcome == "not_found":
                not_found.add(feature)
    in_matrix = sorted(found)
    out_matrix = sorted(not_found - found)
    unclassified = sorted(features - found - not_found)
    return {"distinct_features": len(features),
            "in_matrix": in_matrix, "out_of_matrix": out_matrix,
            "unclassified": unclassified}


def m14(run: Run, rate_verification: dict | None) -> tuple[str, dict]:
    tokens = {k: run.field("usage", k)
              for k in ("input", "output", "cache_creation", "cache_read")}
    model = run.field("model")
    if model not in M14_RATES:
        raise MissingData(
            f"{run.name}: no rate in the specification for model {model!r}")
    if tokens["cache_creation"] or tokens["cache_read"]:
        raise UnexpectedData(
            f"{run.name}: cache tokens are non-zero, but the specification "
            f"states prompt caching was not enabled in any run")
    rates = M14_RATES[model]
    value = {"tokens": tokens, "model": model, "rates": rates,
             "rates_taken": M14_RATES_TAKEN}
    if rate_verification is None:
        value.update({"cost": None, "cost_status": "withheld_rate_unverified",
                      "rate_verification": None})
        return "computed", value
    cost = (tokens["input"] * rates["input_per_mtok"]
            + tokens["output"] * rates["output_per_mtok"]) / 1_000_000
    value.update({"cost": cost, "cost_status": "derived_rate_verified",
                  "rate_verification": rate_verification})
    return "computed", value


def m16(run: Run) -> dict:
    parsed = parse_final_answer(run.final_answer)
    conf = {v: 0 for v in CONFIDENCE_VALUES}
    for rec in parsed.records:
        if rec.get("CONFIDENCE") in conf:
            conf[rec["CONFIDENCE"]] += 1
    return {"records": len(parsed.records), "confidence": conf,
            "explicit_no_findings": parsed.explicit_no_findings,
            "warning_count": len(parsed.warnings),
            "warnings": list(parsed.warnings)}


def _evidence(run: Run, rec: dict, index: int) -> str:
    if "EVIDENCE" not in rec:
        raise MissingData(f"{run.name}: parsed record {index} has no EVIDENCE")
    return rec["EVIDENCE"]


def tool_names_in(text: str, tools) -> list[str]:
    return [t for t in tools
            if re.search(rf"(?<![A-Za-z0-9_]){re.escape(t)}(?![A-Za-z0-9_])",
                         text)]


def m17a(run: Run) -> dict:
    parsed = parse_final_answer(run.final_answer)
    logged = {call_field(run, c, "tool") for c in run.calls}
    tools = surface_tools(run)
    per_record, grounded = [], 0
    for i, rec in enumerate(parsed.records, 1):
        named = tool_names_in(_evidence(run, rec, i), tools)
        if not named:
            ok, sub = False, "no tool named"
        else:
            missing = [t for t in named if t not in logged]
            ok = not missing
            sub = None if ok else "named tool not called"
        grounded += ok
        per_record.append({"record_index": i, "flag": rec.get("FLAG"),
                           "tools_named": named, "grounded": ok,
                           "sub_reason": sub})
    return {"records": len(parsed.records), "grounded": grounded,
            "per_record": per_record}


def find_scientific(text: str) -> list[dict]:
    """1e-3 form, which A7 puts out of scope for parsing."""
    return [{"text": m.group(0), "span": [m.start(), m.end()]}
            for m in SCIENTIFIC.finditer(text)]


def _token_value(text: str) -> tuple[float, int]:
    body = text.replace(",", "").rstrip("%")
    decimals = len(body.split(".", 1)[1]) if "." in body else 0
    return float(body), decimals


def tokenize_numbers(text: str) -> list[dict]:
    """Numeric tokens in EVIDENCE text, as amended by A7."""
    masked = list(text)
    for sci in find_scientific(text):
        a, b = sci["span"]
        masked[a:b] = " " * (b - a)
    masked = "".join(masked)

    out = []
    for m in CORE.finditer(masked):
        start, end = m.start(1), m.end(1)
        before = masked[start - 1] if start >= 1 else ""
        sign = ""
        if before in "+-" and before != "":
            prior = masked[start - 2] if start >= 2 else ""
            separator = prior != "" and (
                prior in SIGN_SEPARATOR_BEFORE
                # As amended by A8: a hyphen after a letter, as in top-6.
                or (before == "-" and prior.isalpha()))
            if separator:
                # Not a sign but a separator, as in 0.614-0.624 or top-6.
                edge = before
            else:
                sign, start, edge = before, start - 1, prior
        else:
            edge = before
        if edge != "" and (edge.isalpha() or edge == "_"):
            # Adjacent to a letter or underscore. The match is not a token,
            # and no shorter part of it is taken instead.
            continue
        raw = masked[start:end]
        value, decimals = _token_value(raw)
        out.append({"text": raw, "value": value, "decimals": decimals,
                    "span": [start, end], "signed": bool(sign)})
    return out


def _numeric_leaves(node, out: list):
    if isinstance(node, bool):
        return
    if isinstance(node, (int, float)):
        out.append(float(node))
    elif isinstance(node, str):
        # As amended by A7: only strings in the numeric token form count.
        if STRING_NUMBER.fullmatch(node):
            out.append(_token_value(node)[0])
    elif isinstance(node, dict):
        for v in node.values():
            _numeric_leaves(v, out)
    elif isinstance(node, list):
        for v in node:
            _numeric_leaves(v, out)


def tool_result_blocks(run: Run) -> list[dict]:
    out = []
    for msg in run.messages:
        content = msg.get("content")
        if msg.get("role") != "user" or not isinstance(content, list):
            continue
        out += [b for b in content
                if isinstance(b, dict) and b.get("type") == "tool_result"]
    return out


def payload_numbers(run: Run) -> list[float]:
    numbers: list[float] = []
    for block in tool_result_blocks(run):
        if "content" not in block:
            raise MissingData(f"{run.name}: a tool_result block has no content")
        if not isinstance(block["content"], str):
            raise UnexpectedData(
                f"{run.name}: tool_result content is not a JSON string")
        try:
            payload = json.loads(block["content"])
        except json.JSONDecodeError as exc:
            raise UnexpectedData(
                f"{run.name}: tool_result content is not valid JSON "
                f"({exc.msg})") from None
        _numeric_leaves(payload, numbers)
    return numbers


def number_matches(value: float, decimals: int, numbers: list[float]) -> bool:
    """As amended by A7: abs(x - v) < 0.5 * 10**(-d)."""
    tolerance = 0.5 * 10 ** (-decimals)
    return any(abs(x - value) < tolerance for x in numbers)


def tie_status(value: float, decimals: int, numbers: list[float]) -> tuple[bool, list[float]]:
    """Whether a token's classification turned on a tie (A8).

    A payload number ties with the token when their distance sits on the
    half-interval boundary, within TIE_RELATIVE_EPSILON. The classification
    turned on a tie when at least one payload number ties and none matches
    clearly inside the boundary, because then the strict inequality decided
    the outcome, one way or the other, on float representation alone.
    """
    tolerance = 0.5 * 10 ** (-decimals)
    band = TIE_RELATIVE_EPSILON * tolerance
    ties = [x for x in numbers if abs(abs(x - value) - tolerance) <= band]
    clear = any(abs(x - value) < tolerance - band for x in numbers)
    return (bool(ties) and not clear), ties


def m17b(run: Run, adjudications: dict[str, dict]
         ) -> tuple[dict, list[dict], list[dict], list[dict]]:
    """The metric value, unmatched tokens, scientific-notation reports and
    tokens whose classification turned on a tie."""
    parsed = parse_final_answer(run.final_answer)
    numbers = payload_numbers(run)
    per_record, unmatched_out, scientific_out, tie_out = [], [], [], []
    for i, rec in enumerate(parsed.records, 1):
        evidence = _evidence(run, rec, i)
        counts = {c: 0 for c in M17B_CLASSES}
        tokens = []
        for j, tok in enumerate(tokenize_numbers(evidence), 1):
            token_id = f"{run.name}|r{i}|t{j}"
            matched = number_matches(tok["value"], tok["decimals"], numbers)
            on_tie, tie_values = tie_status(tok["value"], tok["decimals"], numbers)
            entry = {"token_id": token_id, "text": tok["text"],
                     "span": tok["span"],
                     "classification": "matched" if matched else "unmatched",
                     "turned_on_tie": on_tie}
            if on_tie:
                entry["tie_payload_values"] = tie_values
                tie_out.append({"token_id": token_id, "run_directory": run.name,
                                "record_index": i, "flag": rec.get("FLAG"),
                                "text": tok["text"], "span": tok["span"],
                                "automatic_classification":
                                    "matched" if matched else "unmatched",
                                "tie_payload_values": tie_values,
                                "evidence": evidence})
            adj = adjudications.pop(token_id, None)
            if adj is not None:
                if matched:
                    raise UnexpectedData(
                        f"adjudication given for {token_id}, which is matched; "
                        f"a matched token is never reclassified")
                cls, applying, reason = _adjudicate(adj, tok["text"], numbers, run)
                entry["adjudication"] = dict(adj)
                if cls is None:
                    entry["adjudication_rejected"] = reason
                else:
                    entry["classification"] = cls
                    if cls == "multiply_sourced":
                        entry["sources_applying"] = applying
            counts[entry["classification"]] += 1
            if entry["classification"] == "unmatched" and "adjudication" not in entry:
                unmatched_out.append({"token_id": token_id,
                                      "run_directory": run.name,
                                      "record_index": i,
                                      "flag": rec.get("FLAG"),
                                      "text": tok["text"], "span": tok["span"],
                                      "evidence": evidence})
            tokens.append(entry)
        scientific = find_scientific(evidence)
        for sci in scientific:
            scientific_out.append({"run_directory": run.name,
                                   "record_index": i, "flag": rec.get("FLAG"),
                                   "text": sci["text"], "span": sci["span"],
                                   "evidence": evidence})
        per_record.append({"record_index": i, "flag": rec.get("FLAG"),
                           **counts, "tokens": tokens,
                           "scientific_notation": [s["text"] for s in scientific]})
    return ({"records": len(parsed.records), "per_record": per_record},
            unmatched_out, scientific_out, tie_out)


def _figure_in(figure: str, text: str) -> bool:
    """The token text appears verbatim in text, not inside a longer number."""
    return re.search(rf"(?<![\d.]){re.escape(figure)}(?!\d|\.\d)", text) is not None


def _string_leaves(node, out: list):
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, dict):
        for v in node.values():
            _string_leaves(v, out)
    elif isinstance(node, list):
        for v in node:
            _string_leaves(v, out)


def _check_source(src, figure: str, numbers: list[float], run: Run) -> str | None:
    """None if one recorded source carries its required evidence (A9), else why not."""
    if not isinstance(src, dict):
        return "a source is not an object"
    cls = src.get("class")
    if cls not in HAND_SOURCE_CLASSES:
        return f"source class {cls!r} is not one of {', '.join(HAND_SOURCE_CLASSES)}"
    for field in SOURCE_EVIDENCE_FIELDS[cls]:
        if field not in src:
            return f"{cls} source has no {field}"
    if cls == "derived":
        computation, values = src["computation"], src["source_values"]
        if not isinstance(computation, str) or not computation.strip():
            return "derived source has an empty computation"
        if not isinstance(values, list) or not values:
            return "derived source records no source payload values"
        for v in values:
            toks = tokenize_numbers(str(v))
            if len(toks) != 1 or not number_matches(toks[0]["value"],
                                                    toks[0]["decimals"], numbers):
                return f"derived source value {v!r} is not a payload number of this run"
        return None
    if cls == "quoted":
        payload_string, seq = src["payload_string"], src["seq"]
        if not isinstance(payload_string, str) or not _figure_in(figure, payload_string):
            return f"quoted payload_string does not contain {figure!r} verbatim"
        if not isinstance(seq, int) or isinstance(seq, bool):
            return "quoted seq is not an integer"
        ok, _ = m18_mapping_assertion(run)
        if not ok:
            return "quoted seq cannot be resolved: the seq mapping assertion fails for this run"
        blocks = tool_result_blocks(run)
        if not 1 <= seq <= len(blocks):
            return f"quoted seq {seq} has no tool result in this run"
        leaves: list[str] = []
        _string_leaves(json.loads(blocks[seq - 1]["content"]), leaves)
        if not any(payload_string in leaf for leaf in leaves):
            return f"quoted payload_string is not a string in the payload returned at seq {seq}"
        return None
    prompt_text, commit = src["prompt_text"], src["rendered_from_commit"]
    if not isinstance(prompt_text, str) or not _figure_in(figure, prompt_text):
        return f"prompt source text does not contain {figure!r} verbatim"
    if not isinstance(commit, str) or not commit.strip():
        return "prompt source has an empty rendered_from_commit"
    # The prompt text is not stored in any run record (A9), so it cannot be
    # checked here against what the run was given. It is recorded as supplied.
    return None


def _adjudicate(adj: dict, figure: str, numbers: list[float], run: Run
                ) -> tuple[str | None, list[str], str | None]:
    """Classification, the classes applying, and a rejection reason (A9).

    One source class gives that class. Two or more distinct classes give
    multiply_sourced. Any source lacking its evidence rejects the whole
    adjudication, and the token stays unmatched.
    """
    sources = adj.get("sources")
    if not isinstance(sources, list) or not sources:
        return None, [], "no sources recorded"
    for src in sources:
        reason = _check_source(src, figure, numbers, run)
        if reason is not None:
            return None, [], reason
    applying = sorted({src["class"] for src in sources},
                      key=HAND_SOURCE_CLASSES.index)
    if len(applying) == 1:
        return applying[0], applying, None
    return "multiply_sourced", applying, None


def m18_mapping_assertion(run: Run) -> tuple[bool, dict]:
    results = tool_result_blocks(run)
    calls = run.calls
    if len(results) != len(calls):
        return False, {"tool_result_blocks": len(results),
                       "logged_calls": len(calls)}
    name_of = {}
    for msg in run.messages:
        content = msg.get("content")
        if msg.get("role") == "assistant" and isinstance(content, list):
            for b in content:
                if isinstance(b, dict) and b.get("type") == "tool_use":
                    name_of[b.get("id")] = b.get("name")
    by_seq = {call_field(run, c, "seq"): c for c in calls}
    for k, block in enumerate(results, 1):
        if k not in by_seq:
            return False, {"position": k, "problem": "no logged call with this seq"}
        use_name = name_of.get(block.get("tool_use_id"))
        logged = call_field(run, by_seq[k], "tool")
        if use_name != logged:
            return False, {"position": k, "tool_use_name": use_name,
                           "logged_tool": logged}
    return True, {}


def planted_column() -> str:
    names = sorted(CANARY)
    if len(names) != 1:
        raise MissingData(
            f"the specification names one planted column; CANARY holds "
            f"{len(names)}")
    return names[0]


def m18(run: Run) -> tuple[str, dict]:
    ok, detail = m18_mapping_assertion(run)
    if not ok:
        return "withheld", {"a2_seq_mapping_assertion": "failed", **detail}
    name = planted_column()
    word = re.compile(rf"(?<![A-Za-z0-9_]){re.escape(name)}(?![A-Za-z0-9_])")
    exposure = next((k for k, b in enumerate(tool_result_blocks(run), 1)
                     if word.search(b.get("content", ""))), None)
    investigation = None
    for call in run.calls:
        args = call_field(run, call, "arguments")
        if (isinstance(args, dict) and isinstance(args.get("feature"), str)
                and args["feature"].strip() == name):
            seq = call_field(run, call, "seq")
            investigation = seq if investigation is None else min(investigation, seq)
    gap = (investigation - exposure
           if exposure is not None and investigation is not None else None)
    return "computed", {"planted_column": name,
                        "a2_seq_mapping_assertion": "passed",
                        "exposure_seq": exposure,
                        "investigation_seq": investigation,
                        "investigation_minus_exposure": gap,
                        "exposure_absent": exposure is None,
                        "investigation_absent": investigation is None}


# ----------------------------------------------------------------------
# Driver
# ----------------------------------------------------------------------
def evaluate_run(run: Run, adjudications: dict[str, dict],
                 rate_verification: dict | None
                 ) -> tuple[list[dict], list[dict], list[dict], list[dict]]:
    canary, canary_source = attribute_canary(run)
    base = {"run_directory": run.name,
            "tool_layer_version": run.field("tool_layer_version"),
            "canary": canary, "canary_source": canary_source}
    rows, unmatched, scientific, ties = [], [], [], []

    valid, vdetail = validity_gate(run)
    for metric in METRICS:
        row = {**base, "metric": metric}
        if not valid:
            rows.append({**row, "status": "excluded",
                         "reason": "validity_precondition_failed",
                         "detail": vdetail, "value": None})
            continue
        in_scope, reason = scope_gate(run, metric, canary)
        if not in_scope:
            rows.append({**row, "status": "excluded", "reason": reason,
                         "detail": {"scope": SCOPE_OF[metric]}, "value": None})
            continue
        status, value, detail = "computed", None, None
        if metric == "M14":
            status, value = m14(run, rate_verification)
        elif metric == "M17b":
            value, unm, sci, tie = m17b(run, adjudications)
            unmatched += unm
            scientific += sci
            ties += tie
        elif metric == "M18":
            status, value = m18(run)
            if status == "withheld":
                detail, value = value, None
        else:
            value = {"M1": m1, "M3": m3, "M4": m4, "M5": m5, "M6": m6,
                     "M8": m8, "M9": m9, "M10": m10, "M11": m11,
                     "M16": m16, "M17a": m17a}[metric](run)
        rows.append({**row, "status": status,
                     "reason": ("a2_seq_mapping_assertion_failed"
                                if status == "withheld" else None),
                     "detail": detail, "value": value})
    return rows, unmatched, scientific, ties


def load_adjudications(path: Path | None) -> dict[str, dict]:
    if path is None:
        return {}
    doc = json.loads(Path(path).read_text())
    if "adjudications" not in doc:
        raise MissingData(f"{path}: no adjudications list")
    out = {}
    for entry in doc["adjudications"]:
        if "token_id" not in entry:
            raise MissingData(f"{path}: an adjudication has no token_id")
        if entry["token_id"] in out:
            raise UnexpectedData(f"{path}: {entry['token_id']} adjudicated twice")
        out[entry["token_id"]] = entry
    return out


def load_rate_verification(path: Path | None) -> dict | None:
    if path is None:
        return None
    doc = json.loads(Path(path).read_text())
    for key in ("source", "date", "model", "input_per_mtok", "output_per_mtok"):
        if key not in doc:
            raise MissingData(f"{path}: rate verification has no {key}")
    if doc["source"] not in M14_VERIFICATION_SOURCES:
        raise UnexpectedData(
            f"{path}: source {doc['source']!r} is not one the specification "
            f"accepts ({', '.join(M14_VERIFICATION_SOURCES)})")
    spec = M14_RATES.get(doc["model"])
    if spec is None:
        raise UnexpectedData(f"{path}: no specification rate for {doc['model']!r}")
    if (doc["input_per_mtok"], doc["output_per_mtok"]) != (
            spec["input_per_mtok"], spec["output_per_mtok"]):
        raise UnexpectedData(
            f"{path}: verified rates differ from the specification's; record "
            f"an amendment before any cost figure is produced")
    return {k: doc[k] for k in ("source", "date", "model",
                                "input_per_mtok", "output_per_mtok")}


def adjudication_template(unmatched: list[dict], scientific: list[dict],
                          ties: list[dict]) -> dict:
    """The file handed to the adjudicator. Decisions go in `adjudications`."""
    return {"unmatched_tokens": unmatched,
            "scientific_notation": scientific,
            "classification_turned_on_tie": ties,
            "adjudications": []}


def run_all(run_dirs: list[Path], adjudications: dict[str, dict],
            rate_verification: dict | None
            ) -> tuple[dict, list[dict], list[dict], list[dict]]:
    pending = dict(adjudications)
    rows, unmatched, scientific, ties = [], [], [], []
    for d in run_dirs:
        r, u, s, t = evaluate_run(Run(d), pending, rate_verification)
        rows += r
        unmatched += u
        scientific += s
        ties += t
    if pending:
        raise UnexpectedData(
            f"adjudications given for tokens that do not exist in scope: "
            f"{sorted(pending)}")
    doc = {"specification": SPECIFICATION,
           "amendments_applied": AMENDMENTS_APPLIED,
           "rows": rows}
    return doc, unmatched, scientific, ties


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run", action="append", type=Path, default=None,
                    help="a run directory; repeat for several. Default: all "
                         "directories under outputs/agent_runs/")
    ap.add_argument("--out", type=Path, default=OUT_JSON)
    ap.add_argument("--adjudications", type=Path, default=None)
    ap.add_argument("--rate-verification", type=Path, default=None)
    ap.add_argument("--adjudication-template", type=Path, default=None,
                    help="write the unmatched M17b tokens, any scientific "
                         "notation, and tie-dependent tokens here")
    args = ap.parse_args(argv)

    run_dirs = args.run or sorted(p for p in RUNS_DIR.iterdir() if p.is_dir())
    try:
        doc, unmatched, scientific, ties = run_all(
            run_dirs,
            load_adjudications(args.adjudications),
            load_rate_verification(args.rate_verification))
    except (MissingData, UnexpectedData) as exc:
        print(f"stopped: {type(exc).__name__}: {exc}", file=sys.stderr)
        print("no output written", file=sys.stderr)
        return 2

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(doc, indent=2))
    if args.adjudication_template is not None:
        args.adjudication_template.write_text(
            json.dumps(adjudication_template(unmatched, scientific, ties), indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
