"""Entrypoint for python -m hostkeeper."""

import sys


def main() -> int:
    """Minimal main entrypoint for stage 1.1."""
    print("hostkeeper", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
