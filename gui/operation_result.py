#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Structured result returned by GUI background operations."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class OperationResult:
    success: bool
    output_file: Path | None = None
    scatter_manifest: Path | None = None

    def __bool__(self) -> bool:
        return self.success
