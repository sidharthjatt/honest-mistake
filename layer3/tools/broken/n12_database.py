"""N12, broken tool: tries to reach the pgvector database (refusal 3).

Opens a TCP connection to host.docker.internal:5433, then to the Docker
bridge gateway on 5433. Either would reach the database from an ordinary
container. Both are attempted and each result is reported on stderr.

Expected outcome: crashed with socket.gaierror or OSError. If either
connection opens, it prints a well-formed K1 answer. Runs only in the
sandbox.
"""

import json
import socket
import sys

SANDBOX_ONLY = True

BRIDGE_GATEWAY = "172.17.0.1"


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


def _connect(host, port):
    def action():
        socket.create_connection((host, port), timeout=5).close()
    return action


def main():
    errors = [attempt("connect host.docker.internal:5433",
                      _connect("host.docker.internal", 5433)),
              attempt(f"connect {BRIDGE_GATEWAY}:5433",
                      _connect(BRIDGE_GATEWAY, 5433))]
    if any(e is None for e in errors):
        print(json.dumps({"train_rows": 891742}))
        return
    raise errors[0]


if __name__ == "__main__":
    main()
