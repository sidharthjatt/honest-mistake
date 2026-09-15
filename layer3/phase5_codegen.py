"""The Phase 5 code-generation request, built one way for counting and sending.

Both parts are loaded from where amendment A3 in PREREGISTRATION_PHASE5.md
says they live, and each must hash to the value A3 recorded, or nothing is
built. The request goes through agent.llm.build_request with the settings in
section 4: claude-sonnet-5, the thinking setting in agent/llm.py, the moving
cache breakpoint and 12,400 max tokens. No tools are passed (A3).

Counting and sending use this same function, so the request that is counted
is the request that is sent.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from agent.llm import CACHE_MOVING, build_request

ROOT = Path(__file__).resolve().parent.parent
PROMPT = ROOT / "layer3" / "prompts" / "phase5_codegen_system.txt"
PROMPT_SHA256 = "e0d0ef68478b67da51bc1ed0be7af6324e9e2493241fc55039859e8fdac9e035"
SPEC_RECORD = (ROOT / "outputs" / "layer3" / "phase4_runs"
               / "20260914T135142__REAL__phase4-run1" / "spec_requests.json")
SPEC_ITEM = "C4"
SPEC_SHA256 = "cc6d4fbe5da53e87abbaea367671aa3188b3bcd3af760ad50532123299f734f9"
CACHE = CACHE_MOVING


class RequestMismatch(RuntimeError):
    """A part of the request no longer hashes to the value recorded in A3."""


def _checked(label: str, raw: bytes, expected: str) -> str:
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected:
        raise RequestMismatch(f"The {label} hashes to {digest}, not the "
                              f"{expected} recorded in A3. A changed part "
                              f"needs its own amendment first.")
    return raw.decode("utf-8")


def load_parts() -> tuple[str, str]:
    """The system prompt and the user message, each checked against A3."""
    system = _checked("system prompt", PROMPT.read_bytes(), PROMPT_SHA256)
    records = [r for r in json.loads(SPEC_RECORD.read_text())
               if r.get("item") == SPEC_ITEM]
    if len(records) != 1:
        raise RequestMismatch(f"The record holds {len(records)} entries for "
                              f"{SPEC_ITEM}, not one.")
    spec = _checked("spec reply text", records[0]["text"].encode("utf-8"),
                    SPEC_SHA256)
    return system, spec


def build() -> dict:
    """The keyword arguments for messages.create."""
    system, spec = load_parts()
    return build_request([{"role": "user", "content": spec}], [], system,
                         CACHE)
