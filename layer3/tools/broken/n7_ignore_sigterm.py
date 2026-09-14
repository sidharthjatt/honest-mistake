"""N7, broken tool: ignores SIGTERM, then sleeps forever.

Expected outcome: timeout. The harness kill must not be catchable.
Runs only in the sandbox.
"""

import signal
import time

SANDBOX_ONLY = True


def main():
    signal.signal(signal.SIGTERM, signal.SIG_IGN)
    while True:
        time.sleep(3600)


if __name__ == "__main__":
    main()
