#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Registry-based detection and dispatch for Dianji source formats."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from factories.dianji.models import DianjiFormatError, ParsedDianjiSource
from factories.dianji.powertech_parser import (
    is_powertech_text_file,
    parse_powertech_file,
)
from factories.dianji.sts8203_parser import (
    is_sts8203_csv_file,
    parse_sts8203_file,
)


Detector = Callable[[str | Path], bool]
Parser = Callable[[str | Path], ParsedDianjiSource]


@dataclass(frozen=True)
class DianjiSourceFormat:
    """One independently maintained source format plug-in."""

    key: str
    display_name: str
    extensions: frozenset[str]
    detector: Detector
    parser: Parser

    def supports_extension(self, path: str | Path) -> bool:
        return Path(path).suffix.lower() in self.extensions


SOURCE_FORMATS: tuple[DianjiSourceFormat, ...] = (
    DianjiSourceFormat(
        key="powertech_text",
        display_name="PowerTECH",
        extensions=frozenset({".xls"}),
        detector=is_powertech_text_file,
        parser=parse_powertech_file,
    ),
    DianjiSourceFormat(
        key="sts8203_csv",
        display_name="STS8203 CSV",
        extensions=frozenset({".csv"}),
        detector=is_sts8203_csv_file,
        parser=parse_sts8203_file,
    ),
)

SUPPORTED_SOURCE_EXTENSIONS = frozenset(
    extension
    for source_format in SOURCE_FORMATS
    for extension in source_format.extensions
)


def detect_dianji_source_format(path: str | Path) -> DianjiSourceFormat:
    """Detect exactly one registered format from extension plus content signature."""
    path = Path(path)
    candidates = [
        source_format
        for source_format in SOURCE_FORMATS
        if source_format.supports_extension(path)
        and source_format.detector(path)
    ]
    if not candidates:
        registered = ", ".join(
            f"{source_format.display_name} ({'/'.join(sorted(source_format.extensions))})"
            for source_format in SOURCE_FORMATS
        )
        raise DianjiFormatError(
            f"无法识别电基源文件格式: {path.name}；已注册格式: {registered}"
        )
    if len(candidates) != 1:
        raise DianjiFormatError(
            f"电基源文件格式识别不唯一: {path.name} -> "
            + ", ".join(candidate.display_name for candidate in candidates)
        )
    return candidates[0]


def parse_dianji_source_file(path: str | Path) -> ParsedDianjiSource:
    """Detect a registered source format and call only its parser module."""
    source_format = detect_dianji_source_format(path)
    parsed = source_format.parser(path)
    if parsed.source_format != source_format.display_name:
        raise DianjiFormatError(
            f"解析器格式标识不一致: registry={source_format.display_name}, "
            f"parser={parsed.source_format}"
        )
    return parsed
