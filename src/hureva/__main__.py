"""Enable `python -m hureva <command>` (mirrors the `hureva` console script)."""

import sys

from .cli import main

if __name__ == "__main__":
    sys.exit(main())
