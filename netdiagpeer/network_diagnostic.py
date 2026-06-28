#!/usr/bin/env python3

try:
    from .netdiag_core import main
except ImportError:
    from netdiag_core import main


if __name__ == "__main__":
    raise SystemExit(main())
