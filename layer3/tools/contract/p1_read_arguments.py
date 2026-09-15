"""P1, contract check for amendment A4: reads its arguments file.

Prints the parsed arguments and the SHA-256 of the bytes it read, so the
harness can compare both with what it wrote. Answers no question.
"""

import hashlib
import json
import os
from pathlib import Path

INPUTS = Path(os.environ.get("TOOL_INPUTS", "/inputs"))


def main():
    raw = (INPUTS / "arguments.json").read_bytes()
    print(json.dumps({"arguments": json.loads(raw),
                      "sha256": hashlib.sha256(raw).hexdigest()}))


if __name__ == "__main__":
    main()
