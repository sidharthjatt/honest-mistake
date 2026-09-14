"""N13, broken tool: allocates 1 GiB in 64 MiB chunks (refusal 5).

Each chunk is built by repeating a non-zero byte, so every page is written
and the memory is committed, not just reserved. Progress goes to stderr.

Expected outcome: memory_limit. If all 1 GiB is allocated, it prints a
well-formed K1 answer. Runs only in the sandbox.
"""

import json
import sys

SANDBOX_ONLY = True

CHUNK = 64 * 1024 * 1024
CHUNKS = 16


def main():
    held = []
    for i in range(1, CHUNKS + 1):
        held.append(b"\x01" * CHUNK)
        print(f"allocated {i * 64} MiB", file=sys.stderr, flush=True)
    print(json.dumps({"train_rows": 891742}))


if __name__ == "__main__":
    main()
