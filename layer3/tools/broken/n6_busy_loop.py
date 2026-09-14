"""N6, broken tool: an infinite loop that burns CPU and never prints.

Expected outcome: timeout. Runs only in the sandbox.
"""

SANDBOX_ONLY = True


def main():
    n = 0
    while True:
        n += 1


if __name__ == "__main__":
    main()
