#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parse the verified Dianji DP1205 SW+Trr (TF) CSV export."""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path
import re

import pandas as pd

from factories.dianji.models import DianjiFormatError, FileIdentity


TF_SOURCE_FORMAT = "Dianji TF CSV"
TF_ENCODING = "gb18030"
TF_SIGNATURE = "设备名称,DP1205"
TF_PRODUCT = "NCE40ED120VT(LA)"
TF_PROGRAM = "NCE40ED120VT(LA) Ver2.1 20251205 陪测10Ω,被测10Ω.out"
TF_TEST_TYPE = "SW+Trr"
TF_EQUIPMENT = "DP1205"
TF_OPERATOR = "YLC"
TF_HEADER_ROW_INDEX = 28
TF_COLUMN_COUNT = 57


@dataclass(frozen=True)
class TFOutputField:
    source_name: str
    output_name: str
    unit: str


_OUTPUT_NAMES = (
    "Udc", "VgePos", "VgeNeg", "No1VcePeak_off", "No2VcePeak_off",
    "IcPeak_on", "Ton", "Td_on", "Eon", "dvdt_on", "didt_on",
    "Tf_v_on", "Tr_i_on", "Toff", "Td_off", "Eoff", "dvdt_off",
    "didt_off", "Tr_v_off", "Tf_i_off", "IcMaxOff1", "IcMinOff1",
    "IcMaxOff2", "IcMinOff2", "It", "Tt", "Eoff2", "Ets", "Toff2",
    "Td_off2", "dvdt_off2", "didt_off2", "Tr_v_off2", "Tf_i_off2",
    "IrrPeak", "Erec", "Trr", "Qrr", "VrrPeak", "dvdt_rr", "didt_r",
    "didt_f", "PrrPeak", "Ta", "Tb", "Tb/Ta", "IF",
)
_OUTPUT_UNITS = (
    "V", "V", "V", "V", "V", "A", "ns", "ns", "mJ", "V/us", "A/us",
    "ns", "ns", "ns", "ns", "mJ", "V/us", "A/us", "ns", "ns", "A",
    "A", "A", "A", "A", "ns", "mJ", "mJ", "ns", "ns", "V/us", "A/us",
    "ns", "ns", "A", "mJ", "ns", "uC", "V", "V/us", "A/us", "A/us",
    "kW", "ns", "ns", "", "A",
)
TF_OUTPUT_FIELDS = tuple(
    TFOutputField(source, f"{source}({unit})" if unit else source, unit)
    for source, unit in zip(_OUTPUT_NAMES, _OUTPUT_UNITS)
)

TF_HEADER = (
    "serial_No", "date", "time", "test_time", "BIN", "Fail_project",
    "result", "contact", "componentCheck", *_OUTPUT_NAMES, "componentCheck",
)
TF_ITEM_NAMES = ("contact", "componentCheck", *_OUTPUT_NAMES, "componentCheck")

_MANUFACTURING_LOT = r"M(?:\d{9}|\d{11})-\d{3}(?:-A-B)?"
_BATCH = r"FA[A-Z0-9]{2}-\d{4}"
_FILENAME_RE = re.compile(
    rf"^,(?P<product>{re.escape(TF_PRODUCT)})-"
    rf"(?P<manufacturing_lot>{_MANUFACTURING_LOT})\s+"
    rf"(?P<batch>{_BATCH})"
    r"(?:\s+(?P<source_segment>1|4))?"
    rf"-{re.escape(TF_TEST_TYPE)}-"
    r"(?P<timestamp>\d{10})$",
    flags=re.IGNORECASE,
)


@dataclass
class ParsedDianjiTFFile:
    path: Path
    identity: FileIdentity
    metadata_lot: str
    lot_identity_warning: str | None
    data: pd.DataFrame
    specs: pd.DataFrame
    source_rows: int
    kept_rows: int
    invalid_marker_counts: dict[str, int]
    source_format: str = TF_SOURCE_FORMAT


@dataclass(frozen=True)
class TFFilenameDetails:
    identity: FileIdentity
    test_time: datetime


def is_dianji_tf_csv_file(path: str | Path) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as handle:
            prefix = handle.read(256)
    except OSError:
        return False
    return prefix.startswith(TF_SIGNATURE.encode(TF_ENCODING))


def parse_dianji_tf_filename(path_or_name: str | Path) -> FileIdentity:
    return _parse_filename_details(path_or_name).identity


def _parse_filename_details(path_or_name: str | Path) -> TFFilenameDetails:
    path = Path(path_or_name)
    match = _FILENAME_RE.fullmatch(path.stem)
    if match is None:
        raise DianjiFormatError(
            "电基 TF 文件名不符合 "
            "',<产品>-<制造批次> <FA...周记> [分段号]-SW+Trr-<YYMMDDhhmm>.csv' "
            f"规则: {path.name}"
        )
    try:
        test_time = datetime.strptime(match.group("timestamp"), "%y%m%d%H%M")
    except ValueError as exc:
        raise DianjiFormatError(f"{path.name} 的测试时间无效: {exc}") from exc
    source_segment = match.group("source_segment")
    identity = FileIdentity(
        product=match.group("product"),
        manufacturing_lot=match.group("manufacturing_lot").upper(),
        batch=match.group("batch").upper(),
        test_tag=TF_TEST_TYPE,
        source_segment=source_segment,
    )
    return TFFilenameDetails(identity=identity, test_time=test_time)


def parse_dianji_tf_file(path: str | Path) -> ParsedDianjiTFFile:
    path = Path(path)
    details = _parse_filename_details(path.name)
    text = _read_text(path)
    rows = list(csv.reader(text.splitlines()))
    _validate_layout(rows, path)
    metadata_lot, program = _validate_metadata(rows, details, path)

    header = _trim(rows[TF_HEADER_ROW_INDEX])
    field_indexes = {name: index for index, name in enumerate(header[:-1])}
    low_limits = _trim(rows[19])
    high_limits = _trim(rows[20])

    records: list[list[float | str]] = []
    source_rows = 0
    invalid_counts: Counter[str] = Counter()
    for raw_row in rows[TF_HEADER_ROW_INDEX + 2 :]:
        row = _trim(raw_row)
        if not row or not row[0].strip().isdigit():
            continue
        if len(row) != TF_COLUMN_COUNT:
            raise DianjiFormatError(
                f"{path.name} 的数据行 {row[0]!r} 列数未经验证: "
                f"{len(row)} != {TF_COLUMN_COUNT}"
            )
        source_rows += 1
        values = [
            _parse_measurement(
                row[field_indexes[field.source_name]],
                field.output_name,
                invalid_counts,
                path,
            )
            for field in TF_OUTPUT_FIELDS
        ]
        # Align with Dianji DC: discard only records that never reached the
        # first numeric business measurement, preserving later failures as NaN.
        if math.isnan(values[0]):
            continue
        records.append([details.identity.batch, *values])

    output_names = [field.output_name for field in TF_OUTPUT_FIELDS]
    data = pd.DataFrame(records, columns=["批次", *output_names])
    specs = _build_specs(
        path,
        details.identity,
        program,
        field_indexes,
        low_limits,
        high_limits,
    )
    return ParsedDianjiTFFile(
        path=path,
        identity=details.identity,
        metadata_lot=metadata_lot,
        lot_identity_warning=None,
        data=data,
        specs=specs,
        source_rows=source_rows,
        kept_rows=len(data),
        invalid_marker_counts=dict(invalid_counts),
    )


def _read_text(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise DianjiFormatError(f"无法读取电基 TF 文件 {path.name}: {exc}") from exc
    if not raw.startswith(TF_SIGNATURE.encode(TF_ENCODING)):
        raise DianjiFormatError(f"{path.name} 不是已验证的电基 TF CSV")
    try:
        return raw.decode(TF_ENCODING)
    except UnicodeDecodeError as exc:
        raise DianjiFormatError(f"无法按 GB18030 解码电基 TF 文件 {path.name}: {exc}") from exc


def _validate_layout(rows: list[list[str]], path: Path) -> None:
    if len(rows) <= TF_HEADER_ROW_INDEX + 1:
        raise DianjiFormatError(f"{path.name} 的 TF 文件行数不足")
    expected_metadata_labels = (
        (0, "设备名称"), (1, "工号"), (2, "程序名称"), (3, "保存路径"),
        (4, "批次信息"), (5, "测试类型"), (6, "开始时间"), (7, "结束时间"),
    )
    for index, expected in expected_metadata_labels:
        if not rows[index] or rows[index][0].strip() != expected:
            raise DianjiFormatError(
                f"{path.name} 第 {index + 1} 行元数据标签未经验证: "
                f"{rows[index][0] if rows[index] else ''!r} != {expected!r}"
            )

    header = tuple(_trim(rows[TF_HEADER_ROW_INDEX]))
    if header != TF_HEADER:
        raise DianjiFormatError(f"{path.name} 的 57 列 TF 参数表头未经验证")
    chinese_header = _trim(rows[TF_HEADER_ROW_INDEX + 1])
    if len(chinese_header) != TF_COLUMN_COUNT:
        raise DianjiFormatError(f"{path.name} 的中文参数行列数未经验证")

    test_row = _trim(rows[17])
    item_row = _trim(rows[18])
    low_row = _trim(rows[19])
    high_row = _trim(rows[20])
    source_item_row = _trim(rows[22])
    if len(test_row) != TF_COLUMN_COUNT or test_row[6] != "Test":
        raise DianjiFormatError(f"{path.name} 的 TF Test 控制行未经验证")
    expected_numbers = tuple(f"{number:.6f}" for number in range(1, 51))
    if tuple(test_row[7:]) != expected_numbers:
        raise DianjiFormatError(f"{path.name} 的 TF Item 编号不是严格的 1..50")
    if len(item_row) != TF_COLUMN_COUNT or item_row[6] != "Item":
        raise DianjiFormatError(f"{path.name} 的中文 Item 控制行未经验证")
    if len(source_item_row) != TF_COLUMN_COUNT or source_item_row[6] != "Item":
        raise DianjiFormatError(f"{path.name} 的英文 Item 控制行未经验证")
    if tuple(source_item_row[7:]) != TF_ITEM_NAMES:
        raise DianjiFormatError(f"{path.name} 的 50 项 TF Item 顺序未经验证")
    if tuple(item_row[7:]) != tuple(chinese_header[7:]):
        raise DianjiFormatError(f"{path.name} 的中文 Item 与数据表头不一致")
    if len(low_row) != TF_COLUMN_COUNT or low_row[6].strip() != "Low  Limit":
        raise DianjiFormatError(f"{path.name} 的 Low Limit 控制行未经验证")
    if len(high_row) != TF_COLUMN_COUNT or high_row[6].strip() != "High Limit":
        raise DianjiFormatError(f"{path.name} 的 High Limit 控制行未经验证")

    for field, source_index in zip(TF_OUTPUT_FIELDS, range(9, 56)):
        actual_unit = _description_unit(chinese_header[source_index])
        if actual_unit != field.unit:
            raise DianjiFormatError(
                f"{path.name} 的 {field.source_name} 单位未经验证: "
                f"{actual_unit!r} != {field.unit!r}"
            )


def _validate_metadata(
    rows: list[list[str]], details: TFFilenameDetails, path: Path
) -> tuple[str, str]:
    identity = details.identity
    if rows[0][1].strip() != TF_EQUIPMENT:
        raise DianjiFormatError(f"{path.name} 的设备未经验证: {rows[0][1]!r}")
    if rows[1][1].strip() != TF_OPERATOR:
        raise DianjiFormatError(f"{path.name} 的工号未经验证: {rows[1][1]!r}")
    program = ",".join(value.strip() for value in rows[2][1:] if value.strip())
    if program != TF_PROGRAM:
        raise DianjiFormatError(f"{path.name} 的测试程序未经验证: {program!r}")
    metadata_lot = rows[4][1].strip()
    expected_lot = f"{identity.manufacturing_lot} {identity.batch}"
    if identity.source_segment:
        expected_lot += f" {identity.source_segment}"
    if metadata_lot.upper() != expected_lot.upper():
        raise DianjiFormatError(
            f"{path.name} 的文件名/批次信息不一致: "
            f"{expected_lot!r} != {metadata_lot!r}"
        )
    if rows[5][1].strip() != TF_TEST_TYPE:
        raise DianjiFormatError(f"{path.name} 的测试类型未经验证: {rows[5][1]!r}")
    try:
        start_time = datetime.strptime(
            f"{rows[6][1].strip()} {rows[6][2].strip()}", "%Y-%m-%d %H:%M:%S"
        )
    except (ValueError, IndexError) as exc:
        raise DianjiFormatError(f"{path.name} 的开始时间无效: {exc}") from exc
    if start_time.strftime("%y%m%d%H%M") != details.test_time.strftime("%y%m%d%H%M"):
        raise DianjiFormatError(
            f"{path.name} 的文件名/开始时间不一致: "
            f"{details.test_time:%Y-%m-%d %H:%M} != {start_time:%Y-%m-%d %H:%M}"
        )
    return metadata_lot, program


def _build_specs(
    path: Path,
    identity: FileIdentity,
    program: str,
    field_indexes: dict[str, int],
    low_limits: list[str],
    high_limits: list[str],
) -> pd.DataFrame:
    records = []
    for field in TF_OUTPUT_FIELDS:
        index = field_indexes[field.source_name]
        low_raw = low_limits[index].strip()
        high_raw = high_limits[index].strip()
        low = _parse_limit(low_raw, field.output_name, path)
        high = _parse_limit(high_raw, field.output_name, path)
        normalized = low > high
        if normalized:
            low, high = high, low
        records.append(
            {
                "Source_ID": path.stem,
                "lot_ID": identity.batch,
                "Parameter": field.output_name,
                "Unit": field.unit,
                "Low_Limit": low,
                "High_Limit": high,
                "Low_Limit_Raw": low_raw,
                "High_Limit_Raw": high_raw,
                "Test_Condition": f"{TF_EQUIPMENT}; {TF_TEST_TYPE}; {program}",
                "Limit_Order_Normalized": normalized,
                "Source_File": path.name,
            }
        )
    return pd.DataFrame.from_records(records)


def _parse_measurement(
    value: str,
    output_name: str,
    invalid_counts: Counter[str],
    path: Path,
) -> float:
    text = value.strip()
    if not text or text == "/":
        if text == "/":
            invalid_counts[output_name] += 1
        return math.nan
    try:
        result = float(text)
    except ValueError as exc:
        raise DianjiFormatError(
            f"{path.name} 的 {output_name} 包含未经验证的非数值标记: {text!r}"
        ) from exc
    if not math.isfinite(result):
        raise DianjiFormatError(f"{path.name} 的 {output_name} 包含非有限数值: {text!r}")
    return result


def _parse_limit(value: str, output_name: str, path: Path) -> float:
    try:
        result = float(value)
    except ValueError as exc:
        raise DianjiFormatError(
            f"{path.name} 的 {output_name} 上下限不是数值: {value!r}"
        ) from exc
    if not math.isfinite(result):
        raise DianjiFormatError(f"{path.name} 的 {output_name} 上下限不是有限数值")
    return result


def _description_unit(description: str) -> str:
    match = re.search(r"\(([^()]*)\)\s*$", description.strip())
    return match.group(1) if match else ""


def _trim(row: list[str]) -> list[str]:
    result = [value.strip() for value in row]
    while result and result[-1] == "":
        result.pop()
    return result
