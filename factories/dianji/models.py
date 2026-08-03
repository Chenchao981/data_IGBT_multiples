#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Shared Dianji source identities and parser contracts."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd


class DianjiFormatError(ValueError):
    """Raised when a source file cannot be safely mapped to the Dianji contract."""


@dataclass(frozen=True)
class FileIdentity:
    product: str
    manufacturing_lot: str
    batch: str
    test_tag: str
    source_segment: str | None = None


class ParsedDianjiSource(Protocol):
    """Common result shape implemented by every registered source parser."""

    path: Path
    identity: FileIdentity
    lot_identity_warning: str | None
    data: pd.DataFrame
    specs: pd.DataFrame
    source_rows: int
    kept_rows: int
    invalid_marker_counts: dict[str, int]
    source_format: str
