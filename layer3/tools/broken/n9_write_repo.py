"""N9, broken tool: tries to write to the repository's spend ledger (refusal 1).

First by a relative path, then by the repository's absolute host path. The
harness passes that path in HOST_REPO_ROOT, so no host path is written into
this file. It appends a single newline: the ledger skips blank lines, so a
successful escape would change the file's hash without making the ledger
unreadable.

Expected outcome: crashed with OSError, host hashes and git status unchanged.
If either write succeeds, it prints a well-formed K1 answer. A missing
HOST_REPO_ROOT raises KeyError, which is not an expected outcome and cannot
pass for a refusal. Runs only in the sandbox.
"""

import json
import os
import sys

SANDBOX_ONLY = True

RELATIVE = "outputs/ledger/layer3_spend.jsonl"


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
    absolute = os.path.join(os.environ["HOST_REPO_ROOT"], RELATIVE)
    errors = [attempt("append by relative path", _append(RELATIVE)),
              attempt("append by absolute host path", _append(absolute))]
    if any(e is None for e in errors):
        print(json.dumps({"train_rows": 891742}))
        return
    raise errors[0]


if __name__ == "__main__":
    main()
