#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parse Dianji PowerTECH tab-delimited reports stored with an .xls suffix."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import re
from pathlib import Path, PureWindowsPath
import pandas as pd

from factories.dianji.config import (
    EXPECTED_ITEM_COUNTS,
    INVALID_NUMERIC_MARKERS,
    POWERTECH_BATCH_PATTERN,
    POWERTECH_ITEM_LAYOUTS,
    POWERTECH_MANUFACTURING_LOT_PATTERN,
    POWERTECH_METADATA_FILENAME_PROGRAMS,
    POWERTECH_TEST_TAG_PATTERN,
    PowerTechItemLayout,
    SOURCE_ENCODINGS,
    SOURCE_SIGNATURE,
    TARGET_UNITS,
    UNIT_FACTORS,
)
from factories.dianji.models import DianjiFormatError, FileIdentity


@dataclass(frozen=True)
class TestItem:
    item_no: int
    field_index: int
    base_name: str
    bias1: str
    bias2: str
    bias3: str
    unit: str


@dataclass(frozen=True)
class OutputColumn:
    item: TestItem
    name: str
    factor: float


@dataclass
class ParsedPowerTechFile:
    path: Path
    identity: FileIdentity
    metadata_lot: str
    lot_identity_warning: str | None
    data: pd.DataFrame
    specs: pd.DataFrame
    source_rows: int
    kept_rows: int
    invalid_marker_counts: dict[str, int]
    source_format: str = "PowerTECH"


_FILENAME_RE = re.compile(
    r"^(?P<product>.+)_"
    rf"(?P<manufacturing_lot>{POWERTECH_MANUFACTURING_LOT_PATTERN})\s*"
    rf"(?P<batch>{POWERTECH_BATCH_PATTERN})\s*"
    rf"(?P<test_tag>{POWERTECH_TEST_TAG_PATTERN})$",
    flags=re.IGNORECASE,
)
_LOT_RE = re.compile(
    rf"(?P<manufacturing_lot>{POWERTECH_MANUFACTURING_LOT_PATTERN})\s*"
    rf"(?P<batch>{POWERTECH_BATCH_PATTERN})",
    flags=re.IGNORECASE,
)
_METADATA_FILENAME_RE = re.compile(
    rf"^(?P<manufacturing_lot>{POWERTECH_MANUFACTURING_LOT_PATTERN})\s*"
    rf"(?P<batch>{POWERTECH_BATCH_PATTERN})\s*"
    rf"(?P<test_tag>{POWERTECH_TEST_TAG_PATTERN})"
    r"(?:\((?P<copy_number>[1-9]\d*)\))?$",
    flags=re.IGNORECASE,
)
_METADATA_DATA_FILENAME_RE = re.compile(
    rf"^(?P<manufacturing_lot>{POWERTECH_MANUFACTURING_LOT_PATTERN})\s*"
    rf"(?P<batch>{POWERTECH_BATCH_PATTERN})\s*"
    rf"(?P<test_tag>{POWERTECH_TEST_TAG_PATTERN})\.plf$",
    flags=re.IGNORECASE,
)
_ITEM_RE = re.compile(r"^(?P<number>\d+)\s+(?P<name>.+?)\s*$")


def parse_dianji_filename(path_or_name: str | Path) -> FileIdentity:
    """Extract product, manufacturing lot, batch/week code, and test tag."""
    stem = Path(path_or_name).stem
    match = _FILENAME_RE.fullmatch(stem)
    if not match:
        raise DianjiFormatError(
            "电基文件名不符合 '<产品>_<M/R制造批次> <C...周记/FA...批次>"
            "[标签]<测试时间>.xls' 规则（已验证可选 -A-A、DC M08 标签和无空格变体）: "
            f"{Path(path_or_name).name}"
        )
    return FileIdentity(
        product=match.group("product").strip(),
        manufacturing_lot=match.group("manufacturing_lot").upper(),
        batch=_normalize_batch(match.group("batch")),
        test_tag=re.sub(r"\s+", " ", match.group("test_tag")).upper(),
    )


def is_powertech_text_file(path: str | Path) -> bool:
    path = Path(path)
    try:
        with path.open("rb") as handle:
            prefix = handle.read(len(SOURCE_SIGNATURE) + 8)
    except OSError:
        return False
    return prefix.startswith(SOURCE_SIGNATURE.encode("ascii"))


def parse_powertech_file(path: str | Path) -> ParsedPowerTechFile:
    path = Path(path)
    text, _encoding = _read_source_text(path)
    rows = [[field.strip() for field in line.split("\t")] for line in text.splitlines()]
    if not rows or not rows[0] or rows[0][0] != SOURCE_SIGNATURE:
        raise DianjiFormatError(f"不是 PowerTECH 文本导出文件: {path.name}")

    labels = _locate_header_rows(rows, path)
    identity = _resolve_file_identity(rows, labels["Serial#"], path)
    metadata_lot, lot_identity_warning = _validate_metadata_lot(
        rows, labels["Serial#"], identity, path
    )
    items, item_layout = _build_test_items(rows, labels, path)
    output_columns = _build_output_columns(items, item_layout, path)
    specs = _build_scatter_specs(rows, labels, output_columns, identity, path)

    records: list[list[float | str]] = []
    source_rows = 0
    invalid_counts: Counter[str] = Counter()
    for row in rows[labels["Serial#"] + 1 :]:
        if not row or not row[0].isdigit():
            continue
        source_rows += 1
        values = [
            _parse_measurement(row, column, invalid_counts)
            for column in output_columns
        ]
        # The reference workbook keeps every row that reached the DVDS test.
        if math.isnan(values[0]):
            continue
        records.append([identity.batch, *values])

    column_names = ["批次", *(column.name for column in output_columns)]
    data = pd.DataFrame(records, columns=column_names)
    return ParsedPowerTechFile(
        path=path,
        identity=identity,
        metadata_lot=metadata_lot,
        lot_identity_warning=lot_identity_warning,
        data=data,
        specs=specs,
        source_rows=source_rows,
        kept_rows=len(data),
        invalid_marker_counts=dict(invalid_counts),
    )


def _resolve_file_identity(
    rows: list[list[str]], serial_index: int, path: Path
) -> FileIdentity:
    """Use the legacy filename contract or the strictly verified dj8 fallback."""
    try:
        return parse_dianji_filename(path.name)
    except DianjiFormatError:
        if _METADATA_FILENAME_RE.fullmatch(path.stem) is None:
            raise
    return _parse_metadata_filename_identity(rows, serial_index, path)


def _parse_metadata_filename_identity(
    rows: list[list[str]], serial_index: int, path: Path
) -> FileIdentity:
    """Resolve a product-less filename only when tester metadata proves it."""
    source_match = _METADATA_FILENAME_RE.fullmatch(path.stem)
    if source_match is None:
        raise DianjiFormatError(f"电基 dj8 文件名未经验证: {path.name}")

    data_file = _metadata_value(rows, serial_index, "DataFileName", path)
    data_name = PureWindowsPath(data_file).name
    data_match = _METADATA_DATA_FILENAME_RE.fullmatch(data_name)
    if data_match is None:
        raise DianjiFormatError(
            f"{path.name} 的 DataFileName 未经验证: {data_name}"
        )

    source_identity = (
        source_match.group("manufacturing_lot").upper(),
        _normalize_batch(source_match.group("batch")),
        _normalize_test_tag(source_match.group("test_tag")),
    )
    data_identity = (
        data_match.group("manufacturing_lot").upper(),
        _normalize_batch(data_match.group("batch")),
        _normalize_test_tag(data_match.group("test_tag")),
    )
    if source_identity != data_identity:
        raise DianjiFormatError(
            f"{path.name} 的文件名与 DataFileName 身份不一致: "
            f"filename={source_identity}, DataFileName={data_identity}"
        )

    test_file = _metadata_value(rows, serial_index, "TestFileName", path)
    test_name = PureWindowsPath(test_file).name
    products = [
        product
        for program, product in POWERTECH_METADATA_FILENAME_PROGRAMS.items()
        if test_name.casefold() == program.casefold()
    ]
    if len(products) != 1:
        raise DianjiFormatError(
            f"{path.name} 的 TestFileName 产品/程序未经验证: {test_name}"
        )

    copy_number = source_match.group("copy_number")
    return FileIdentity(
        product=products[0],
        manufacturing_lot=source_identity[0],
        batch=source_identity[1],
        test_tag=source_identity[2],
        source_segment=f"copy-{copy_number}" if copy_number else None,
    )


def _metadata_value(
    rows: list[list[str]], serial_index: int, label: str, path: Path
) -> str:
    expected = label.casefold()
    for row in rows[:serial_index]:
        if not row or row[0].rstrip(":").strip().casefold() != expected:
            continue
        value = " ".join(field for field in row[1:] if field).strip()
        if value:
            return value
        break
    raise DianjiFormatError(f"{path.name} 缺少 {label} 元数据")


def _normalize_test_tag(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip().upper()


def _read_source_text(path: Path) -> tuple[str, str]:
    raw = path.read_bytes()
    if not raw.startswith(SOURCE_SIGNATURE.encode("ascii")):
        raise DianjiFormatError(
            f"{path.name} 扩展名虽为 .xls，但内容不是支持的 PowerTECH 文本格式"
        )
    errors = []
    for encoding in SOURCE_ENCODINGS:
        try:
            return raw.decode(encoding), encoding
        except UnicodeDecodeError as exc:
            errors.append(f"{encoding}: {exc}")
    raise DianjiFormatError(f"无法解码电基源文件 {path.name}: {'; '.join(errors)}")


def _locate_header_rows(rows: list[list[str]], path: Path) -> dict[str, int]:
    required = (
        "Item Name",
        "Bias1",
        "Bias2",
        "Bias3",
        "Min Limit",
        "Max Limit",
        "Serial#",
    )
    located: dict[str, int] = {}
    for index, row in enumerate(rows[:80]):
        if row and row[0] in required and row[0] not in located:
            located[row[0]] = index
    missing = [label for label in required if label not in located]
    if missing:
        raise DianjiFormatError(f"{path.name} 缺少 PowerTECH 头部行: {missing}")
    if located["Serial#"] <= located["Item Name"]:
        raise DianjiFormatError(f"{path.name} 的 Item/Serial 头部顺序异常")
    return located


def _validate_metadata_lot(
    rows: list[list[str]], serial_index: int, identity: FileIdentity, path: Path
) -> tuple[str, str | None]:
    lot_text = ""
    for row in rows[:serial_index]:
        if row and row[0].rstrip(":").strip().lower() == "lot":
            lot_text = " ".join(value for value in row[1:] if value).strip()
            break
    if not lot_text:
        raise DianjiFormatError(f"{path.name} 缺少 Lot 元数据")
    expected = f"{identity.manufacturing_lot} {identity.batch}"
    match = _LOT_RE.search(lot_text)
    if not match:
        raise DianjiFormatError(
            f"{path.name} 的文件名与 Lot 元数据不一致: filename={expected}, Lot={lot_text}"
        )

    metadata_manufacturing_lot = match.group("manufacturing_lot").upper()
    metadata_batch = _normalize_batch(match.group("batch"))
    if (
        metadata_manufacturing_lot == identity.manufacturing_lot
        and metadata_batch == identity.batch
    ):
        return lot_text, None

    filename_main_lot = _manufacturing_main_lot(identity.manufacturing_lot)
    metadata_main_lot = _manufacturing_main_lot(metadata_manufacturing_lot)
    if metadata_batch != identity.batch or metadata_main_lot != filename_main_lot:
        raise DianjiFormatError(
            f"{path.name} 的文件名与 Lot 元数据不一致: filename={expected}, Lot={lot_text}"
        )

    warning = (
        f"{path.name} 的 Lot 片号后缀未刷新: filename={expected}, Lot={lot_text}；"
        f"制造主批 {filename_main_lot} 和批次标识 {identity.batch} 一致，已按文件名继续"
    )
    return lot_text, warning


def _normalize_batch(value: str) -> str:
    return value.upper().replace(",", ".").replace("，", ".").replace("。", ".")


def _manufacturing_main_lot(value: str) -> str:
    match = re.match(r"^[MR]\d{9}", value.upper())
    if match is None:
        return value.upper()
    return match.group(0)


def _build_test_items(
    rows: list[list[str]], labels: dict[str, int], path: Path
) -> tuple[list[TestItem], PowerTechItemLayout]:
    item_row = rows[labels["Item Name"]]
    bias1 = rows[labels["Bias1"]]
    bias2 = rows[labels["Bias2"]]
    bias3 = rows[labels["Bias3"]]
    units = rows[labels["Serial#"]]
    items: list[TestItem] = []
    for field_index, cell in enumerate(item_row):
        if not cell:
            continue
        match = _ITEM_RE.fullmatch(cell)
        if not match:
            continue
        items.append(
            TestItem(
                item_no=int(match.group("number")),
                field_index=field_index,
                base_name=match.group("name").strip().upper(),
                bias1=_at(bias1, field_index),
                bias2=_at(bias2, field_index),
                bias3=_at(bias3, field_index),
                unit=_at(units, field_index),
            )
        )

    numbers = [item.item_no for item in items]
    if len(numbers) != len(set(numbers)):
        raise DianjiFormatError(f"{path.name} 的 Item 编号重复")

    by_number = {item.item_no: item for item in items}
    item_layout = _detect_item_layout(items, by_number, path)

    counts = Counter(item.base_name for item in items)
    for base_name, expected_count in EXPECTED_ITEM_COUNTS.items():
        actual_count = counts.get(base_name, 0)
        if actual_count != expected_count:
            raise DianjiFormatError(
                f"{path.name} 的 {base_name} 测试项数量应为 {expected_count}，实际为 {actual_count}"
            )
    return items, item_layout


def _detect_item_layout(
    items: list[TestItem],
    by_number: dict[int, TestItem],
    path: Path,
) -> PowerTechItemLayout:
    failures = []
    for layout in POWERTECH_ITEM_LAYOUTS:
        if len(items) != layout.item_count:
            failures.append(
                f"{layout.name}: Item 数量 {len(items)} != {layout.item_count}"
            )
            continue
        expected_numbers = list(range(1, layout.item_count + 1))
        actual_numbers = [item.item_no for item in items]
        if actual_numbers != expected_numbers:
            failures.append(
                f"{layout.name}: Item 编号不连续，实际={actual_numbers}"
            )
            continue
        mismatch = next(
            (
                (number, expected_bases, by_number[number].base_name)
                for number, expected_bases in layout.expected_item_bases.items()
                if by_number[number].base_name not in expected_bases
            ),
            None,
        )
        if mismatch is not None:
            number, expected_bases, actual = mismatch
            failures.append(
                f"{layout.name}: Item #{number} 应为 {sorted(expected_bases)}，实际为 {actual}"
            )
            continue
        actual_tail = tuple(
            by_number[number].base_name for number in layout.tail_item_numbers
        )
        if actual_tail not in layout.supported_tail_bases:
            failures.append(
                f"{layout.name}: Item {layout.tail_item_numbers} 尾部布局未经验证: {actual_tail}"
            )
            continue
        return layout

    raise DianjiFormatError(
        f"{path.name} 的 PowerTECH Item 布局未经验证: " + "；".join(failures)
    )


def _build_output_columns(
    items: list[TestItem], item_layout: PowerTechItemLayout, path: Path
) -> list[OutputColumn]:
    by_number = {item.item_no: item for item in items}
    vth_numbers = {
        item.item_no: index
        for index, item in enumerate(
            [item for item in items if item.base_name == "VTH"][1:], start=1
        )
    }
    bvdss_numbers = {
        item.item_no: index
        for index, item in enumerate(
            [item for item in items if item.base_name == "BVDSS"], start=1
        )
    }
    output_item_numbers = _ordered_output_item_numbers(by_number, item_layout, path)
    columns = [
        _make_output_column(by_number[number], vth_numbers, bvdss_numbers, by_number, path)
        for number in output_item_numbers
    ]
    names = [column.name for column in columns]
    duplicates = [name for name, count in Counter(names).items() if count > 1]
    if duplicates:
        raise DianjiFormatError(f"{path.name} 生成了重复输出列: {duplicates}")
    return columns


def _build_scatter_specs(
    rows: list[list[str]],
    labels: dict[str, int],
    output_columns: list[OutputColumn],
    identity: FileIdentity,
    path: Path,
) -> pd.DataFrame:
    """Capture PowerTECH limits in the same units as the cleaned RAW data."""
    min_limits = rows[labels["Min Limit"]]
    max_limits = rows[labels["Max Limit"]]
    source_id = path.stem
    records = []
    for column in output_columns:
        item = column.item
        low_raw = _at(min_limits, item.field_index)
        high_raw = _at(max_limits, item.field_index)
        low_value = _parse_limit_value(low_raw, column.factor)
        high_value = _parse_limit_value(high_raw, column.factor)
        normalized = (
            low_value is not None
            and high_value is not None
            and low_value > high_value
        )
        if normalized:
            low_value, high_value = high_value, low_value
        conditions = [
            value.strip()
            for value in (item.bias1, item.bias2, item.bias3)
            if value.strip()
        ]
        records.append(
            {
                "Source_ID": source_id,
                "lot_ID": identity.batch,
                "Parameter": column.name,
                "Unit": TARGET_UNITS.get(item.base_name, ""),
                "Low_Limit": low_value,
                "High_Limit": high_value,
                "Low_Limit_Raw": low_raw,
                "High_Limit_Raw": high_raw,
                "Test_Condition": "; ".join(conditions),
                "Limit_Order_Normalized": normalized,
                "Source_File": path.name,
            }
        )
    return pd.DataFrame.from_records(records)


def _parse_limit_value(value: str, factor: float) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", text)
    if not match:
        return None
    return float(match.group(0)) * factor


def _ordered_output_item_numbers(
    items_by_number: dict[int, TestItem],
    item_layout: PowerTechItemLayout,
    path: Path,
) -> list[int]:
    """Return one stable RAW order for every explicitly verified layout."""
    tail_items = [
        items_by_number[number] for number in item_layout.tail_item_numbers
    ]
    idss_items = [item for item in tail_items if item.base_name == "IDSS"]
    igss_items = [item for item in tail_items if item.base_name == "IGSS"]
    if len(idss_items) != 1 or len(igss_items) != 2:
        raise DianjiFormatError(
            f"{path.name} 的 {item_layout.name} 尾部 Item "
            f"{item_layout.tail_item_numbers} 必须包含 1 个 IDSS 和 2 个 IGSS"
        )

    igss_with_conditions = [
        (item, _condition_decimal(item.bias1, "VGS", path, item.item_no))
        for item in igss_items
    ]
    negative_igss = [
        item for item, condition in igss_with_conditions if condition.startswith("-")
    ]
    positive_igss = [
        item for item, condition in igss_with_conditions if not condition.startswith("-")
    ]
    magnitudes = {condition.lstrip("+-") for _, condition in igss_with_conditions}
    if len(negative_igss) != 1 or len(positive_igss) != 1 or len(magnitudes) != 1:
        raise DianjiFormatError(
            f"{path.name} 的 {item_layout.name} 尾部 IGSS 必须是一组正负对称 VGS 条件: "
            f"{[(item.item_no, condition) for item, condition in igss_with_conditions]}"
        )

    return [
        *item_layout.output_prefix,
        negative_igss[0].item_no,
        positive_igss[0].item_no,
        idss_items[0].item_no,
        *item_layout.output_suffix,
    ]


def _make_output_column(
    item: TestItem,
    vth_numbers: dict[int, int],
    bvdss_numbers: dict[int, int],
    items_by_number: dict[int, TestItem],
    path: Path,
) -> OutputColumn:
    base = item.base_name
    target_unit = TARGET_UNITS.get(base, "")
    if base in {"DVDS", "DVDS_EX"}:
        name = "DVDS(mV)"
    elif base == "LCR-RG":
        name = "Rg(R)"
    elif base == "VTH":
        name = f"VTH{vth_numbers[item.item_no]}(V)"
    elif base == "BVDSS":
        name = f"BVDSS{bvdss_numbers[item.item_no]}(V)"
    elif base == "IDSS":
        condition = _condition_value(item.bias1, "VDS", path, item.item_no)
        name = f"IDSS{condition}(nA)"
    elif base == "IGSS":
        condition = _condition_decimal(item.bias1, "VGS", path, item.item_no)
        prefix = "ISGS" if condition.startswith("-") else "IGSS"
        name = f"{prefix}{condition.lstrip('+-')}(nA)"
    elif base == "RDON":
        condition_text = item.bias2 if "VGS" in item.bias2.upper() else item.bias1
        condition = _condition_value(condition_text, "VGS", path, item.item_no)
        name = f"RDON{condition}(mR)"
    elif base == "VFSD":
        name = "VFSD(V)"
    elif base == "DELTA":
        referenced = _referenced_item_bases(item, items_by_number)
        if referenced and referenced <= {"BVDSS"}:
            name = "DELTA BV"
        elif referenced and referenced <= {"VTH"}:
            name = "DELTA VTH"
        else:
            raise DianjiFormatError(
                f"{path.name} 的 DELTA Item #{item.item_no} 引用无法识别: "
                f"{item.bias1!r}, {item.bias2!r}"
            )
    else:
        raise DianjiFormatError(f"{path.name} 不支持输出 Item #{item.item_no}: {base}")

    factor = _unit_factor(item.unit, target_unit, path, item)
    return OutputColumn(item=item, name=name, factor=factor)


def _referenced_item_bases(
    item: TestItem, items_by_number: dict[int, TestItem]
) -> set[str]:
    numbers = {
        int(value)
        for value in re.findall(r"#(\d+)", " ".join((item.bias1, item.bias2, item.bias3)))
    }
    return {
        items_by_number[number].base_name
        for number in numbers
        if number in items_by_number
    }


def _condition_value(text: str, key: str, path: Path, item_no: int) -> str:
    value = _condition_decimal(text, key, path, item_no)
    return value.lstrip("+")


def _condition_decimal(text: str, key: str, path: Path, item_no: int) -> str:
    match = re.search(
        rf"(?:^|\b){re.escape(key)}\s*=\s*([+-]?\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if not match:
        raise DianjiFormatError(
            f"{path.name} 的 Item #{item_no} 缺少 {key} 测试条件: {text!r}"
        )
    raw = match.group(1)
    sign = "-" if raw.startswith("-") else ("+" if raw.startswith("+") else "")
    magnitude = raw.lstrip("+-")
    if "." in magnitude:
        magnitude = magnitude.rstrip("0").rstrip(".")
    return f"{sign}{magnitude or '0'}"


def _unit_factor(source_unit: str, target_unit: str, path: Path, item: TestItem) -> float:
    if not target_unit:
        return 1.0
    normalized_source = source_unit.strip()
    if normalized_source.casefold() == target_unit.casefold():
        return 1.0
    factor = UNIT_FACTORS.get((normalized_source, target_unit))
    if factor is None:
        raise DianjiFormatError(
            f"{path.name} 的 Item #{item.item_no} 单位不支持: "
            f"{source_unit!r} -> {target_unit!r}"
        )
    return factor


def _parse_measurement(
    row: list[str], column: OutputColumn, invalid_counts: Counter[str]
) -> float:
    index = column.item.field_index
    if index >= len(row) or not row[index]:
        return math.nan
    try:
        value = float(row[index])
    except ValueError:
        return math.nan
    if not math.isfinite(value):
        return math.nan
    if value in INVALID_NUMERIC_MARKERS:
        invalid_counts[column.name] += 1
        return math.nan
    return value * column.factor


def _at(row: list[str], index: int) -> str:
    return row[index].strip() if index < len(row) else ""
