"""Strict parser for the approved Jijia NCE15TD120BT STS8203 layout."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
import math
from pathlib import Path, PureWindowsPath
import re

import pandas as pd

from factories.jijia.config import (
    EXPECTED_COLUMN_COUNT,
    EXPECTED_SOURCE_HEADER,
    EXPECTED_SOURCE_UNITS,
    OUTPUT_PARAMETER_NAMES,
    PARAMETER_START_INDEX,
    SOURCE_ENCODING,
    SOURCE_SIGNATURE,
    SUPPORTED_PRODUCT,
)


class JijiaFormatError(ValueError):
    """Raised when a Jijia source cannot be mapped safely."""


@dataclass(frozen=True)
class JijiaFileIdentity:
    product: str
    batch: str
    test_lot: str
    export_time: datetime


@dataclass
class ParsedJijiaFile:
    path: Path
    identity: JijiaFileIdentity
    metadata_lot: str
    data: pd.DataFrame
    source_rows: int
    pass_rows: int
    fail_rows: int
    source_format: str = "Jijia STS8203 CSV"


_FILENAME_RE = re.compile(
    r"^(?P<product>[^_]+)_"
    r"(?P<batch>C\d{6}\.\d{2})_"
    r"(?P<test_lot>26PA\d{8}-\d{2})_"
    r"DC_(?P<timestamp>\d{12})$",
    flags=re.IGNORECASE,
)


def is_jijia_csv_file(path: str | Path) -> bool:
    path = Path(path)
    try:
        prefix = path.read_bytes()[: len(SOURCE_SIGNATURE) + 16]
    except OSError:
        return False
    return path.suffix.lower() == ".csv" and prefix.startswith(SOURCE_SIGNATURE)


def parse_jijia_filename(path_or_name: str | Path) -> JijiaFileIdentity:
    path = Path(path_or_name)
    match = _FILENAME_RE.fullmatch(path.stem)
    if not match:
        raise JijiaFormatError(
            "集佳文件名必须符合 "
            "'<产品>_<C批次>_<测试批次>_DC_<YYMMDDhhmmss>.csv': "
            f"{path.name}"
        )
    product = match.group("product")
    if product.upper() != SUPPORTED_PRODUCT.upper():
        raise JijiaFormatError(f"集佳产品尚未验证: {product}")
    try:
        export_time = datetime.strptime(match.group("timestamp"), "%y%m%d%H%M%S")
    except ValueError as exc:
        raise JijiaFormatError(f"集佳文件名时间无法识别: {path.name}") from exc
    return JijiaFileIdentity(
        product=SUPPORTED_PRODUCT,
        batch=match.group("batch").upper(),
        test_lot=match.group("test_lot").upper(),
        export_time=export_time,
    )


def parse_jijia_file(path: str | Path) -> ParsedJijiaFile:
    path = Path(path)
    identity = parse_jijia_filename(path.name)
    text = _read_source_text(path)
    lines = text.splitlines()
    rows = list(csv.reader(lines))
    if not rows or not rows[0] or not rows[0][0].startswith("STS8203 Station"):
        raise JijiaFormatError(f"不是支持的集佳 STS8203 CSV: {path.name}")

    header_index = _locate_header(rows, path)
    metadata_lot = _validate_metadata(lines[:header_index], identity, path)
    header = _trim_trailing_empty(rows[header_index])
    units = _control_row(rows, header_index + 1, "Unit", path)
    _control_row(rows, header_index + 2, "LimitL", path, numeric=True)
    _control_row(rows, header_index + 3, "LimitU", path, numeric=True)
    _validate_schema(header, units, path)

    records: list[list[float | str]] = []
    source_rows = 0
    pass_rows = 0
    fail_rows = 0
    for row_number, raw_row in enumerate(rows[header_index + 4 :], header_index + 5):
        row = _trim_trailing_empty(raw_row)
        if not row or not any(cell.strip() for cell in row):
            continue
        if len(row) < PARAMETER_START_INDEX + 1:
            raise JijiaFormatError(f"{path.name} 第 {row_number} 行字段过少: {len(row)}")
        if len(row) > EXPECTED_COLUMN_COUNT:
            raise JijiaFormatError(f"{path.name} 第 {row_number} 行字段过多: {len(row)}")
        if not row[0].strip().isdigit() or not row[1].strip().isdigit():
            raise JijiaFormatError(
                f"{path.name} 第 {row_number} 行 SITE_NUM/PART_ID 不是整数"
            )
        pass_flag = row[2].strip()
        if pass_flag not in {"True", "False"}:
            raise JijiaFormatError(
                f"{path.name} 第 {row_number} 行 PASSFG 无法识别: {pass_flag!r}"
            )
        source_rows += 1
        pass_rows += int(pass_flag == "True")
        fail_rows += int(pass_flag == "False")
        values = [
            _parse_measurement(_at(row, index), path, row_number, header[index])
            for index in range(PARAMETER_START_INDEX, EXPECTED_COLUMN_COUNT)
        ]
        records.append([identity.batch, *values])

    data = pd.DataFrame(records, columns=["lot_ID", *OUTPUT_PARAMETER_NAMES])
    return ParsedJijiaFile(
        path=path,
        identity=identity,
        metadata_lot=metadata_lot,
        data=data,
        source_rows=source_rows,
        pass_rows=pass_rows,
        fail_rows=fail_rows,
    )


def _read_source_text(path: Path) -> str:
    raw = path.read_bytes()
    if not raw.startswith(SOURCE_SIGNATURE):
        raise JijiaFormatError(f"{path.name} 不是集佳 STS8203 内容签名")
    try:
        return raw.decode(SOURCE_ENCODING)
    except UnicodeDecodeError as exc:
        raise JijiaFormatError(
            f"无法按 {SOURCE_ENCODING} 解码集佳文件 {path.name}: {exc}"
        ) from exc


def _locate_header(rows: list[list[str]], path: Path) -> int:
    matches = [
        index
        for index, row in enumerate(rows[:120])
        if row and row[0].strip() == "SITE_NUM"
    ]
    if len(matches) != 1:
        raise JijiaFormatError(
            f"{path.name} 必须且只能有一个 SITE_NUM 参数行，实际={len(matches)}"
        )
    return matches[0]


def _validate_metadata(
    metadata_lines: list[str],
    identity: JijiaFileIdentity,
    path: Path,
) -> str:
    metadata: dict[str, str] = {}
    for line in metadata_lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        metadata[key.strip()] = value.strip()
    required = ("Date", "Program", "Lot Id", "Beginning Time", "Ending Time")
    missing = [key for key in required if not metadata.get(key)]
    if missing:
        raise JijiaFormatError(f"{path.name} 缺少元数据: {missing}")

    metadata_lot = metadata["Lot Id"].upper()
    expected_lot_re = re.compile(rf"^{re.escape(identity.test_lot)}-FT\d*$")
    if not expected_lot_re.fullmatch(metadata_lot):
        raise JijiaFormatError(
            f"{path.name} 文件名测试批次与 Lot Id 不一致: "
            f"filename={identity.test_lot}, Lot Id={metadata['Lot Id']}"
        )

    program_name = PureWindowsPath(metadata["Program"]).name
    if not program_name.upper().startswith(identity.product.upper()):
        raise JijiaFormatError(
            f"{path.name} 文件名产品与 Program 不一致: "
            f"filename={identity.product}, Program={program_name}"
        )
    try:
        beginning = datetime.strptime(metadata["Beginning Time"], "%Y-%m-%d %H:%M:%S")
        ending = datetime.strptime(metadata["Ending Time"], "%Y-%m-%d %H:%M:%S")
        metadata_date = datetime.strptime(metadata["Date"], "%Y-%m-%d").date()
    except ValueError as exc:
        raise JijiaFormatError(f"{path.name} 测试时间元数据无法识别") from exc
    if ending < beginning:
        raise JijiaFormatError(f"{path.name} Ending Time 早于 Beginning Time")
    if metadata_date != ending.date():
        raise JijiaFormatError(
            f"{path.name} Date 与 Ending Time 日期不一致: "
            f"Date={metadata['Date']}, Ending Time={metadata['Ending Time']}"
        )
    return metadata["Lot Id"]


def _control_row(
    rows: list[list[str]],
    index: int,
    label: str,
    path: Path,
    *,
    numeric: bool = False,
) -> tuple[str, ...]:
    if index >= len(rows):
        raise JijiaFormatError(f"{path.name} 缺少 {label} 行")
    row = tuple(_trim_trailing_empty(rows[index]))
    if not row or row[0].strip() != label:
        actual = row[0].strip() if row else ""
        raise JijiaFormatError(f"{path.name} 的 {label} 行位置异常: {actual!r}")
    if len(row) != EXPECTED_COLUMN_COUNT:
        raise JijiaFormatError(
            f"{path.name} 的 {label} 列数异常: {len(row)} != {EXPECTED_COLUMN_COUNT}"
        )
    if numeric:
        for column, value in enumerate(row[1:], 2):
            text = value.strip()
            if not text:
                continue
            try:
                number = float(text)
            except ValueError as exc:
                raise JijiaFormatError(
                    f"{path.name} 的 {label} 第 {column} 列不是数值: {text!r}"
                ) from exc
            if not math.isfinite(number):
                raise JijiaFormatError(
                    f"{path.name} 的 {label} 第 {column} 列不是有限数值: {text!r}"
                )
    return row


def _validate_schema(header: list[str], units: tuple[str, ...], path: Path) -> None:
    actual_header = tuple(cell.strip() for cell in header)
    if actual_header != EXPECTED_SOURCE_HEADER:
        difference = next(
            (
                f"第 {index + 1} 列应为 {expected!r}，实际为 {actual!r}"
                for index, (expected, actual) in enumerate(
                    zip(EXPECTED_SOURCE_HEADER, actual_header)
                )
                if expected != actual
            ),
            f"列数 {len(actual_header)} != {EXPECTED_COLUMN_COUNT}",
        )
        raise JijiaFormatError(f"{path.name} 参数结构未经验证: {difference}")
    actual_units = tuple(cell.strip() for cell in units)
    if actual_units != EXPECTED_SOURCE_UNITS:
        difference = next(
            (
                f"{EXPECTED_SOURCE_HEADER[index]} 单位应为 {expected!r}，实际为 {actual!r}"
                for index, (expected, actual) in enumerate(
                    zip(EXPECTED_SOURCE_UNITS, actual_units)
                )
                if expected != actual
            ),
            "单位列数异常",
        )
        raise JijiaFormatError(f"{path.name} 单位结构未经验证: {difference}")


def _parse_measurement(
    raw_value: str,
    path: Path,
    row_number: int,
    field_name: str,
) -> float:
    text = raw_value.strip()
    if not text:
        return math.nan
    try:
        value = float(text)
    except ValueError as exc:
        raise JijiaFormatError(
            f"{path.name} 第 {row_number} 行 {field_name} 出现未经验证的非数值: {text!r}"
        ) from exc
    if not math.isfinite(value):
        raise JijiaFormatError(
            f"{path.name} 第 {row_number} 行 {field_name} 不是有限数值: {text!r}"
        )
    return value


def _trim_trailing_empty(row: list[str]) -> list[str]:
    return row[:-1] if row and row[-1] == "" else row


def _at(row: list[str], index: int) -> str:
    return row[index] if index < len(row) else ""
