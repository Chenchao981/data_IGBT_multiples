#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parse verified Dianji STS8203 FT-ALL CSV exports."""

from __future__ import annotations

from collections import Counter
import codecs
import csv
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path, PureWindowsPath
import re

import pandas as pd

from factories.dianji.config import (
    INVALID_NUMERIC_MARKERS,
    STS8203_ENCODING,
    STS8203_EXPECTED_COLUMN_COUNT,
    STS8203_EXPECTED_FIELD_INDEXES,
    STS8203_EXPECTED_SOURCE_UNITS,
    STS8203_PRODUCT_OUTPUT_FIELDS,
    STS8203_SIGNATURE,
)
from factories.dianji.powertech_parser import DianjiFormatError, FileIdentity


@dataclass
class ParsedSTS8203File:
    path: Path
    identity: FileIdentity
    metadata_lot: str
    lot_identity_warning: str | None
    data: pd.DataFrame
    specs: pd.DataFrame
    source_rows: int
    kept_rows: int
    invalid_marker_counts: dict[str, int]
    source_format: str = "STS8203 CSV"


_FILENAME_RE = re.compile(
    r"^(?P<product>.+)_Lot Id_"
    r"(?P<manufacturing_lot>[mMrR]\d{8}-\d{3})\s+"
    r"(?P<batch>[cC]\d{6}[.,，。]\d{2})_"
    r"(?P<label>ALL)_"
    r"(?P<date>\d{4}-\d{2}-\d{2})\s+"
    r"(?P<hour>\d{1,2})_(?P<minute>\d{2})_(?P<second>\d{2})$",
    flags=re.IGNORECASE,
)
_LOT_RE = re.compile(
    r"^(?P<manufacturing_lot>[mMrR]\d{8}-\d{3})\s+"
    r"(?P<batch>[cC]\d{6}[.,，。]\d{2})$"
)


def is_sts8203_csv_file(path: str | Path) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as handle:
            prefix = handle.read(len(STS8203_SIGNATURE) + len(codecs.BOM_UTF8) + 16)
    except OSError:
        return False
    if prefix.startswith(codecs.BOM_UTF8):
        prefix = prefix[len(codecs.BOM_UTF8) :]
    return prefix.startswith(STS8203_SIGNATURE.encode("ascii"))


def parse_sts8203_filename(path_or_name: str | Path) -> FileIdentity:
    stem = Path(path_or_name).stem
    match = _FILENAME_RE.fullmatch(stem)
    if not match:
        raise DianjiFormatError(
            "电基 STS8203 文件名不符合 "
            "'<产品>_Lot Id_<制造批次> <C...周记>_ALL_<日期 时_分_秒>.csv' 规则: "
            f"{Path(path_or_name).name}"
        )
    date = match.group("date")
    hour = int(match.group("hour"))
    minute = match.group("minute")
    second = match.group("second")
    return FileIdentity(
        product=match.group("product").strip(),
        manufacturing_lot=match.group("manufacturing_lot").upper(),
        batch=_normalize_batch(match.group("batch")),
        test_tag=f"ALL{date.replace('-', '')}{hour:02d}{minute}{second}",
    )


def parse_sts8203_file(path: str | Path) -> ParsedSTS8203File:
    path = Path(path)
    identity = parse_sts8203_filename(path.name)
    output_fields = STS8203_PRODUCT_OUTPUT_FIELDS.get(identity.product)
    if output_fields is None:
        raise DianjiFormatError(
            f"{path.name} 的 STS8203 产品尚未验证 Bias/输出映射: {identity.product}"
        )

    text = _read_source_text(path)
    lines = text.splitlines()
    rows = list(csv.reader(lines))
    if not rows or not rows[0] or not rows[0][0].startswith(STS8203_SIGNATURE):
        raise DianjiFormatError(f"不是支持的 STS8203 CSV 文件: {path.name}")

    header_index = _locate_header(rows, path)
    metadata_lot = _validate_metadata(lines[:header_index], identity, path)
    header = _trim_trailing_empty(rows[header_index])
    units = _control_row(rows, header_index + 1, "Unit", path)
    low_limits = _control_row(rows, header_index + 2, "LimitL", path)
    high_limits = _control_row(rows, header_index + 3, "LimitU", path)
    _validate_schema(header, units, path)

    field_indexes = {name: index for index, name in enumerate(header)}
    records: list[list[float | str]] = []
    source_rows = 0
    invalid_counts: Counter[str] = Counter()
    for raw_row in rows[header_index + 4 :]:
        row = _trim_trailing_empty(raw_row)
        if (
            len(row) < 2
            or not row[0].strip().isdigit()
            or not row[1].strip().isdigit()
        ):
            continue
        source_rows += 1
        values = [
            _parse_measurement(
                _at(row, field_indexes[source_name]),
                output_name,
                invalid_counts,
            )
            for source_name, output_name, _target_unit in output_fields
        ]
        # Keep the same business rule as PowerTECH: retain every row that
        # reached a valid DVDS measurement and preserve later failures as null.
        if math.isnan(values[0]):
            continue
        records.append([identity.batch, *values])

    output_names = [output_name for _source, output_name, _unit in output_fields]
    data = pd.DataFrame(records, columns=["批次", *output_names])
    specs = _build_specs(
        path,
        identity,
        output_fields,
        field_indexes,
        low_limits,
        high_limits,
    )
    return ParsedSTS8203File(
        path=path,
        identity=identity,
        metadata_lot=metadata_lot,
        lot_identity_warning=None,
        data=data,
        specs=specs,
        source_rows=source_rows,
        kept_rows=len(data),
        invalid_marker_counts=dict(invalid_counts),
    )


def _read_source_text(path: Path) -> str:
    raw = path.read_bytes()
    signature_payload = (
        raw[len(codecs.BOM_UTF8) :]
        if raw.startswith(codecs.BOM_UTF8)
        else raw
    )
    if not signature_payload.startswith(STS8203_SIGNATURE.encode("ascii")):
        raise DianjiFormatError(
            f"{path.name} 扩展名虽为 .csv，但内容不是支持的 STS8203 格式"
        )
    try:
        return raw.decode(STS8203_ENCODING)
    except UnicodeDecodeError as exc:
        raise DianjiFormatError(f"无法按 UTF-8 解码 STS8203 文件 {path.name}: {exc}") from exc


def _locate_header(rows: list[list[str]], path: Path) -> int:
    matches = [
        index
        for index, row in enumerate(rows[:120])
        if row and row[0].strip() == "SITE_NUM"
    ]
    if len(matches) != 1:
        raise DianjiFormatError(
            f"{path.name} 必须且只能包含一个 STS8203 SITE_NUM 表头，实际={len(matches)}"
        )
    return matches[0]


def _validate_metadata(
    metadata_lines: list[str],
    identity: FileIdentity,
    path: Path,
) -> str:
    metadata = {}
    for line in metadata_lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()

    required = ("Date", "Program", "Lot Id", "Beginning Time")
    missing = [key for key in required if not metadata.get(key)]
    if missing:
        raise DianjiFormatError(f"{path.name} 缺少 STS8203 元数据: {missing}")

    lot_text = metadata["Lot Id"]
    lot_match = _LOT_RE.fullmatch(lot_text)
    if not lot_match:
        raise DianjiFormatError(f"{path.name} 的 Lot Id 格式无法识别: {lot_text}")
    metadata_lot = lot_match.group("manufacturing_lot").upper()
    metadata_batch = _normalize_batch(lot_match.group("batch"))
    expected_lot = f"{identity.manufacturing_lot} {identity.batch}"
    if metadata_lot != identity.manufacturing_lot or metadata_batch != identity.batch:
        raise DianjiFormatError(
            f"{path.name} 的文件名与 Lot Id 元数据不一致: "
            f"filename={expected_lot}, Lot Id={lot_text}"
        )

    program_name = PureWindowsPath(metadata["Program"]).name
    expected_program_prefix = f"{identity.product}_ALL_"
    if not program_name.upper().startswith(expected_program_prefix.upper()):
        raise DianjiFormatError(
            f"{path.name} 的文件名产品与 Program 不一致: "
            f"filename={identity.product}, Program={program_name}"
        )

    match = _FILENAME_RE.fullmatch(path.stem)
    if match is None:
        raise DianjiFormatError(f"{path.name} 的 STS8203 文件名无法重新校验")
    filename_time = datetime.strptime(
        f"{match.group('date')} {int(match.group('hour')):02d}:"
        f"{match.group('minute')}:{match.group('second')}",
        "%Y-%m-%d %H:%M:%S",
    )
    try:
        metadata_time = datetime.strptime(
            metadata["Beginning Time"], "%Y-%m-%d %H:%M:%S"
        )
    except ValueError as exc:
        raise DianjiFormatError(
            f"{path.name} 的 Beginning Time 无法识别: {metadata['Beginning Time']}"
        ) from exc
    if metadata["Date"] != match.group("date") or metadata_time != filename_time:
        raise DianjiFormatError(
            f"{path.name} 的文件名与测试时间元数据不一致: "
            f"filename={filename_time}, Date={metadata['Date']}, "
            f"Beginning Time={metadata['Beginning Time']}"
        )
    return lot_text


def _control_row(
    rows: list[list[str]],
    index: int,
    label: str,
    path: Path,
) -> list[str]:
    if index >= len(rows):
        raise DianjiFormatError(f"{path.name} 缺少 STS8203 {label} 行")
    row = _trim_trailing_empty(rows[index])
    if not row or row[0].strip() != label:
        actual = row[0].strip() if row else ""
        raise DianjiFormatError(
            f"{path.name} 的 STS8203 {label} 行位置异常: {actual!r}"
        )
    if len(row) != STS8203_EXPECTED_COLUMN_COUNT:
        raise DianjiFormatError(
            f"{path.name} 的 {label} 列数异常: "
            f"{len(row)} != {STS8203_EXPECTED_COLUMN_COUNT}"
        )
    return row


def _validate_schema(header: list[str], units: list[str], path: Path) -> None:
    if len(header) != STS8203_EXPECTED_COLUMN_COUNT:
        raise DianjiFormatError(
            f"{path.name} 的 STS8203 表头列数异常: "
            f"{len(header)} != {STS8203_EXPECTED_COLUMN_COUNT}"
        )
    if len(set(header)) != len(header):
        raise DianjiFormatError(f"{path.name} 的 STS8203 表头包含重复列")
    for field, expected_index in STS8203_EXPECTED_FIELD_INDEXES.items():
        actual = header[expected_index]
        if actual != field:
            raise DianjiFormatError(
                f"{path.name} 的 STS8203 第 {expected_index + 1} 列应为 "
                f"{field}，实际为 {actual!r}"
            )
    for field, expected_unit in STS8203_EXPECTED_SOURCE_UNITS.items():
        index = STS8203_EXPECTED_FIELD_INDEXES[field]
        actual_unit = units[index].strip()
        if actual_unit.casefold() != expected_unit.casefold():
            raise DianjiFormatError(
                f"{path.name} 的 {field} 单位不支持: "
                f"{actual_unit!r} != {expected_unit!r}"
            )


def _build_specs(
    path: Path,
    identity: FileIdentity,
    output_fields: tuple[tuple[str, str, str], ...],
    field_indexes: dict[str, int],
    low_limits: list[str],
    high_limits: list[str],
) -> pd.DataFrame:
    records = []
    for source_name, output_name, target_unit in output_fields:
        index = field_indexes[source_name]
        low_raw = _at(low_limits, index)
        high_raw = _at(high_limits, index)
        low_value = _parse_limit(low_raw)
        high_value = _parse_limit(high_raw)
        normalized = (
            low_value is not None
            and high_value is not None
            and low_value > high_value
        )
        if normalized:
            low_value, high_value = high_value, low_value
        records.append(
            {
                "Source_ID": path.stem,
                "lot_ID": identity.batch,
                "Parameter": output_name,
                "Unit": target_unit,
                "Low_Limit": low_value,
                "High_Limit": high_value,
                "Low_Limit_Raw": low_raw,
                "High_Limit_Raw": high_raw,
                "Test_Condition": f"STS8203 source column={source_name}",
                "Limit_Order_Normalized": normalized,
                "Source_File": path.name,
            }
        )
    return pd.DataFrame.from_records(records)


def _parse_measurement(
    raw_value: str,
    output_name: str,
    invalid_counts: Counter[str],
) -> float:
    text = raw_value.strip()
    if not text:
        return math.nan
    try:
        value = float(text)
    except ValueError:
        return math.nan
    if not math.isfinite(value):
        return math.nan
    if value in INVALID_NUMERIC_MARKERS:
        invalid_counts[output_name] += 1
        return math.nan
    return value


def _parse_limit(raw_value: str) -> float | None:
    text = raw_value.strip()
    if not text:
        return None
    try:
        value = float(text)
    except ValueError:
        return None
    return value if math.isfinite(value) else None


def _normalize_batch(value: str) -> str:
    return value.upper().replace(",", ".").replace("，", ".").replace("。", ".")


def _trim_trailing_empty(row: list[str]) -> list[str]:
    if row and row[-1] == "":
        return row[:-1]
    return row


def _at(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""
