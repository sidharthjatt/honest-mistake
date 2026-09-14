"""Spend ledger for Layer 3.

Every real request is checked against a hard cap before it is sent and
recorded after it returns. The rule is fixed in PREREGISTRATION_PHASE2.md:
a request is refused when the spend already recorded plus that request's
worst case would exceed the cap.

The ledger is an append-only JSON-lines file, one line per real request.
Mock calls never touch it. A line that cannot be read stops the check
instead of being skipped, since a ledger that quietly undercounts is worse
than one that refuses to answer.
"""

import json
from datetime import datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
LEDGER_PATH = _PROJECT_ROOT / "outputs" / "ledger" / "layer3_spend.jsonl"

CAP_USD = 15.00

# Per million tokens, read from the pricing page on the date below. Only
# the 5-minute write is listed because no request asks for the 1-hour TTL.
RATES_PER_MTOK = {
    "claude-sonnet-5": {
        "input": 2.00,
        "cache_write_5m": 2.50,
        "cache_read": 0.20,
        "output": 10.00,
    },
}
RATES_SOURCE = ("https://platform.claude.com/docs/en/about-claude/pricing, "
                "read 2026-09-14")


class BudgetExceeded(RuntimeError):
    """A request was refused because it could take spend past the cap."""


def _rates(model: str) -> dict:
    if model not in RATES_PER_MTOK:
        raise BudgetExceeded(
            f"No verified rates are recorded for {model}, so its cost cannot "
            f"be checked against the cap.")
    return RATES_PER_MTOK[model]


def cost_usd(model: str, usage: dict) -> float:
    """Cost of one usage record, in the shape call_llm returns."""
    r = _rates(model)
    return (usage.get("input", 0) * r["input"]
            + usage.get("cache_creation", 0) * r["cache_write_5m"]
            + usage.get("cache_read", 0) * r["cache_read"]
            + usage.get("output", 0) * r["output"]) / 1_000_000


def worst_case_usd(model: str, input_tokens: int, max_tokens: int) -> float:
    """Upper bound for one request.

    All input is priced at the cache-write rate, the dearest input class,
    and the output at the full max_tokens. A real request cannot cost more.
    """
    r = _rates(model)
    return (input_tokens * r["cache_write_5m"]
            + max_tokens * r["output"]) / 1_000_000


def spent_usd(path: Path | None = None) -> float:
    """Total recorded spend. A missing ledger means nothing has been spent."""
    path = path or LEDGER_PATH
    if not path.exists():
        return 0.0
    total = 0.0
    for n, line in enumerate(path.read_text().splitlines(), start=1):
        if not line.strip():
            continue
        try:
            total += float(json.loads(line)["cost_usd"])
        except (ValueError, KeyError, TypeError) as exc:
            raise BudgetExceeded(
                f"Ledger line {n} cannot be read, so recorded spend is "
                f"unknown. Fix the ledger before making any real request."
            ) from exc
    return total


def check(model: str, projected_usd: float, path: Path | None = None) -> None:
    """Refuse when recorded spend plus the projection would exceed the cap."""
    spent = spent_usd(path)
    if spent + projected_usd > CAP_USD:
        raise BudgetExceeded(
            f"Refused: ${spent:.4f} is already recorded and this request "
            f"could cost up to ${projected_usd:.4f}, which would pass the "
            f"${CAP_USD:.2f} cap.")


def record(model: str, usage: dict, cache: str, label: str | None,
           path: Path | None = None) -> dict:
    """Append one real request to the ledger and return the entry."""
    path = path or LEDGER_PATH
    cost = cost_usd(model, usage)
    entry = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "label": label,
        "model": model,
        "cache": cache,
        "usage": dict(usage),
        "cost_usd": round(cost, 6),
        "cumulative_usd": round(spent_usd(path) + cost, 6),
        "cap_usd": CAP_USD,
        "rates": RATES_SOURCE,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as fh:
        fh.write(json.dumps(entry) + "\n")
    return entry
