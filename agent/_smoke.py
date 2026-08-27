"""Smoke test: call_llm in mock mode. Runs with NO API key present.

Run:  .venv/bin/python -m agent._smoke
"""

from agent.llm import call_llm


def main() -> None:
    result = call_llm(
        messages=[{"role": "user", "content": "smoke test"}],
        tools=[],
        system="smoke test system prompt",
        mock=True,
    )
    print(result)


if __name__ == "__main__":
    main()
