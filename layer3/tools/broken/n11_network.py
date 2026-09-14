"""N11, broken tool: tries to reach the network (refusal 2).

Resolves example.com, then, skipping name resolution, opens a TCP
connection to 1.1.1.1:443 and sends nothing. Both are attempted and each
result is reported on stderr.

Expected outcome: crashed with socket.gaierror from the first attempt, and
OSError from the second. If either succeeds, it prints a well-formed K1
answer. Runs only in the sandbox.
"""

import json
import socket
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


def _resolve():
    socket.getaddrinfo("example.com", 443)


def _connect():
    socket.create_connection(("1.1.1.1", 443), timeout=5).close()


def main():
    errors = [attempt("resolve example.com", _resolve),
              attempt("connect 1.1.1.1:443", _connect)]
    if any(e is None for e in errors):
        print(json.dumps({"train_rows": 891742}))
        return
    raise errors[0]


if __name__ == "__main__":
    main()
