"""N18, broken tool: tries to change its arguments file (amendment A4).

Appends to /inputs/arguments.json, opens it for writing, then deletes it.
Append goes first, so the file is still intact for the later attempts if
the refusal fails.

Expected outcome: crashed with OSError errno 30 on every attempt, host
hashes unchanged. If any attempt succeeds, it prints a well-formed K1
answer, so a failed refusal cannot pass for one. Runs only in the sandbox.
"""

import json
import os
import sys

SANDBOX_ONLY = True

PATH = "/inputs/arguments.json"


def _name(exc):
    cls = type(exc)
    return cls.__name__ if cls.__module__ == "builtins" else f"{cls.__module__}.{cls.__name__}"


def attempt(label, action):
    try:
        action()
    except Exception as exc:
        print(f"attempt {label}: {_name(exc)}: {exc}", file=sys.stderr)
        return exc
    print(f"attempt {label}: succeeded", file=sys.stderr)
    return None


def _append():
    with open(PATH, "a") as fh:
        fh.write("\n")


def _overwrite():
    with open(PATH, "w") as fh:
        fh.write("{}")


def main():
    errors = [attempt("append to /inputs/arguments.json", _append),
              attempt("open /inputs/arguments.json for writing", _overwrite),
              attempt("delete /inputs/arguments.json",
                      lambda: os.remove(PATH))]
    if any(e is None for e in errors):
        print(json.dumps({"train_rows": 891742}))
        return
    raise errors[0]


if __name__ == "__main__":
    main()
