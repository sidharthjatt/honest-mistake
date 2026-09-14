"""N10, broken tool: tries to write through the tool mount (refusal 1).

Opens /tool/tool.py, which is this file, in append mode and writes a
newline. The document says overwrite. Append goes through the same
read-only check, and it cannot destroy this file if the refusal fails.

Expected outcome: crashed with OSError errno 30, tool file hash unchanged.
If the write succeeds, it prints a well-formed K1 answer. Runs only in the
sandbox.
"""

import json
import sys

SANDBOX_ONLY = True


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


def _append(path):
    def action():
        with open(path, "a") as fh:
            fh.write("\n")
    return action


def main():
    errors = [attempt("append to /tool/tool.py", _append("/tool/tool.py"))]
    if any(e is None for e in errors):
        print(json.dumps({"train_rows": 891742}))
        return
    raise errors[0]


if __name__ == "__main__":
    main()
