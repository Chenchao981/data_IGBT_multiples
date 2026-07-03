#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Command line entry for Dianji SYL/SBL yield report generation."""

from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from factories.dianji.yield_report import main


if __name__ == "__main__":
    raise SystemExit(main())
