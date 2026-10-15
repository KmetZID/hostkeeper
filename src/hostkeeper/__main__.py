"""Entrypoint for python -m hostkeeper."""

import sys

from hostkeeper.cli import main

if __name__ == "__main__":
    sys.exit(main())
