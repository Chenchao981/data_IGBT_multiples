#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Parse the verified Dianji PowerTECH native-XLSX Datalog format."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
from pathlib import Path, PureWindowsPath
import re
import zipfile

import pandas as pd

from factories.dianji.config import (
    INVALID_NUMERIC_MARKERS,
    POWERTECH_XLSX_BATCH_PATTERN,
    POWERTECH_XLSX_LABELS,
    POWERTECH_XLSX_MANUFACTURING_LOT_PATTERN,
    POWERTECH_XLSX_SIGNATURE,
    POWERTECH_XLSX_SUPPORTED_PRODUCTS,
    POWERTECH_XLSX_TRAILING_LOT_LABELS,
)
from factories.dianji.models import DianjiFormatError, FileIdentity


@dataclass(frozen=True)
class XlsxOutputField:
    item_no: int
    source_name: str
    output_name: str
    unit: str
    conditions: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class PowerTechXlsxLayout:
    name: str
    item_bases: tuple[str, ...]
    output_fields: tuple[XlsxOutputField, ...]
    filename_variants: frozenset[tuple[str, str, bool]]


@dataclass
class ParsedPowerTechXlsxFile:
    path: Path
    identity: FileIdentity
    metadata_lot: str
    lot_identity_warning: str | None
    data: pd.DataFrame
    specs: pd.DataFrame
    source_rows: int
    kept_rows: int
    invalid_marker_counts: dict[str, int]
    source_format: str = "PowerTECH XLSX"


_FILENAME_RE = re.compile(
    r"^(?P<product>.+)_"
    rf"(?P<manufacturing_lot>{POWERTECH_XLSX_MANUFACTURING_LOT_PATTERN})\s+"
    rf"(?P<batch>{POWERTECH_XLSX_BATCH_PATTERN})"
    r"(?P<label>(?:\s+(?:ALL|M05|DC|RT)|_)?)"
    r"_FT_(?P<test_time>\d{12})_(?P<station>[A-Z])_"
    r"(?P<tester>SDTS\d+)(?P<trailing_all>ALL)?$",
    flags=re.IGNORECASE,
)
_DATA_FILENAME_RE = re.compile(
    rf"^(?P<manufacturing_lot>{POWERTECH_XLSX_MANUFACTURING_LOT_PATTERN})\s+"
    rf"(?P<batch>{POWERTECH_XLSX_BATCH_PATTERN})"
    r"(?P<label>(?:\s+(?:M05|DC|RT)|_)?)"
    r"_FT_(?P<test_time>\d{12})_(?P<station>[A-Z])_"
    r"(?P<tester>SDTS\d+)\.plf$",
    flags=re.IGNORECASE,
)
_ITEM_RE = re.compile(r"^(?P<number>\d+)\s+(?P<name>.+?)\s*$")


def _field(
    item_no: int,
    source_name: str,
    output_name: str,
    unit: str,
    *conditions: tuple[str, str],
) -> XlsxOutputField:
    return XlsxOutputField(item_no, source_name, output_name, unit, conditions)


_COMMON_PREFIX = (
    _field(4, "DVCE_EX", "DVCE(mV)", "mV", ("Bias1", "VCE=15.00V"), ("Bias2", "IC=11.0A")),
    _field(8, "RG_EX", "Rg(R)", "R", ("Bias1", "DC Bias=0.0000V"), ("Bias3", "Freq=1.00MHz")),
    _field(16, "VTH", "VTH1(V)", "V", ("Bias1", "ID=500.0uA")),
    _field(17, "VTH", "VTH2(V)", "V", ("Bias1", "ID=1.000mA")),
)
_COMMON_MIDDLE = (
    _field(15, "ICES", "ICES1000(nA)", "nA", ("Bias1", "VCE=1000V")),
    _field(13, "IGSS", "IGSS30-1(nA)", "nA", ("Bias1", "VGS=30.00V")),
    _field(14, "IGSS", "ISGS30-1(nA)", "nA", ("Bias1", "VGS=-30.00V")),
    _field(19, "VDSON", "VDSON40A-11V(V)", "V", ("Bias1", "ID=40.00A"), ("Bias2", "VGS=11.0V")),
    _field(20, "VDSON", "VDSON40A-15V(V)", "V", ("Bias1", "ID=40.00A"), ("Bias2", "VGS=15.0V")),
    _field(21, "VDSON", "VDSON160A-15V(V)", "V", ("Bias1", "ID=160.0A"), ("Bias2", "VGS=15.0V")),
    _field(23, "VF", "VF40A(V)", "V", ("Bias1", "IAK=40.00A")),
)


def _item_bases(*names: str) -> tuple[str, ...]:
    return tuple(names)


_BASE_35 = _item_bases(
    "CONT_TR", "VF_EX", "SAME", "DVCE_EX", "DVF_EX", "TSD", "CONT_LCR",
    "RG_EX", "CISS_EX", "CONT", "VTH", "SAME", "IGSS", "IGSS", "ICES",
    "VTH", "VTH", "DELTA", "VDSON", "VDSON", "VDSON", "DELAY", "VF",
    "ICES", "ICES", "BVDSS", "DELAY", "BVDSS", "DELAY", "BVDSS", "DELTA",
    "ICES", "IGSS", "IGSS", "DELAY",
)
_BASE_34 = _BASE_35[:-1]
_BASE_38 = _item_bases(
    "CONT_TR", "VF_EX", "SAME", "DVCE_EX", "DVF_EX", "TSD", "CONT_LCR",
    "RG_EX", "CISS_EX", "CONT", "VTH", "SAME", "IGSS", "IGSS", "ICES",
    "VTH", "VTH", "DELTA", "VDSON", "VDSON", "VDSON", "DELAY", "VF",
    "SAME", "SAME", "SAME", "ICES", "ICES", "BVDSS", "DELAY", "BVDSS",
    "DELAY", "BVDSS", "DELTA", "ICES", "IGSS", "IGSS", "DELAY",
)
_BASE_39 = _item_bases(
    "CONT_TR", "VF_EX", "SAME", "DVCE_EX", "DVF_EX", "TSD", "CONT_LCR",
    "RG_EX", "CISS_EX", "CONT", "VTH", "SAME", "IGSS", "IGSS", "ICES",
    "VTH", "VTH", "DELTA", "VDSON", "VDSON", "VDSON", "DELAY", "VF",
    "SAME", "SAME", "SAME", "SAME", "ICES", "ICES", "BVDSS", "DELAY",
    "BVDSS", "DELAY", "BVDSS", "DELTA", "ICES", "IGSS", "IGSS", "DELAY",
)


def _layout_fields(
    bvdss: tuple[int, int, int],
    later_ices: tuple[int, int, int],
    later_igss: tuple[int, int],
    delta_bv: int,
) -> tuple[XlsxOutputField, ...]:
    return (
        *_COMMON_PREFIX,
        _field(bvdss[0], "BVDSS", "BVDSS1(V)", "V", ("Bias1", "ID=500.0uA")),
        _field(bvdss[1], "BVDSS", "BVDSS2(V)", "V", ("Bias1", "ID=1.000mA")),
        _field(bvdss[2], "BVDSS", "BVDSS3(V)", "V", ("Bias1", "ID=5.000mA")),
        *_COMMON_MIDDLE,
        _field(later_ices[0], "ICES", "ICES1200-1(nA)", "nA", ("Bias1", "VCE=1200V")),
        _field(later_ices[1], "ICES", "ICES1250(nA)", "nA", ("Bias1", "VCE=1250V")),
        _field(later_ices[2], "ICES", "ICES1200-2(nA)", "nA", ("Bias1", "VCE=1200V")),
        _field(later_igss[0], "IGSS", "IGSS30-2(nA)", "nA", ("Bias1", "VGS=30.00V")),
        _field(later_igss[1], "IGSS", "ISGS30-2(nA)", "nA", ("Bias1", "VGS=-30.00V")),
        _field(delta_bv, "DELTA", "DELTA BV", "", ("Bias1", f"Value=#{bvdss[1]}"), ("Bias2", f"Value=#{bvdss[0]}")),
        _field(18, "DELTA", "DELTA VTH", "", ("Bias1", "Value=#17"), ("Bias2", "Value=#16")),
    )


POWERTECH_XLSX_LAYOUTS = (
    PowerTechXlsxLayout(
        "dj7-35",
        _BASE_35,
        _layout_fields((26, 28, 30), (24, 25, 32), (33, 34), 31),
        frozenset(
            {
                ("ALL", "SDTS10212518", False),
                ("", "SDTS10212518", True),
                ("M05", "SDTS10212518", True),
            }
        ),
    ),
    PowerTechXlsxLayout(
        "dj7-34",
        _BASE_34,
        _layout_fields((26, 28, 30), (24, 25, 32), (33, 34), 31),
        frozenset({("", "SDTS10212518", True)}),
    ),
    PowerTechXlsxLayout(
        "dj7-38",
        _BASE_38,
        _layout_fields((29, 31, 33), (27, 28, 35), (36, 37), 34),
        frozenset({("", "SDTS10255062", True)}),
    ),
    PowerTechXlsxLayout(
        "dj7-39",
        _BASE_39,
        _layout_fields((30, 32, 34), (28, 29, 36), (37, 38), 35),
        frozenset(
            {
                ("DC", "SDTS10255062", False),
                ("", "SDTS10255062", False),
                ("RT", "SDTS10255062", False),
                ("_", "SDTS10255062", False),
            }
        ),
    ),
)


def parse_powertech_xlsx_filename(path_or_name: str | Path) -> FileIdentity:
    stem = Path(path_or_name).stem
    match = _FILENAME_RE.fullmatch(stem)
    if match is None:
        raise DianjiFormatError(
            "电基 PowerTECH XLSX 文件名不符合已验证的 dj7 规则: "
            f"{Path(path_or_name).name}"
        )
    product = match.group("product").strip()
    if product.upper() not in {value.upper() for value in POWERTECH_XLSX_SUPPORTED_PRODUCTS}:
        raise DianjiFormatError(f"电基 PowerTECH XLSX 产品未经验证: {product}")
    label = _normalize_label(match.group("label"))
    if label not in POWERTECH_XLSX_LABELS:
        raise DianjiFormatError(f"电基 PowerTECH XLSX 测试标签未经验证: {label}")
    return FileIdentity(
        product=product,
        manufacturing_lot=match.group("manufacturing_lot").upper(),
        batch=match.group("batch").upper(),
        test_tag=" ".join(
            value for value in (label, "FT", match.group("test_time")) if value
        ),
        source_segment=f"{match.group('station').upper()}_{match.group('tester').upper()}",
    )


def is_powertech_xlsx_file(path: str | Path) -> bool:
    path = Path(path)
    if path.suffix.lower() != ".xlsx":
        return False
    try:
        with zipfile.ZipFile(path) as archive:
            workbook_xml = archive.read("xl/workbook.xml")
            sheet_xml = archive.read("xl/worksheets/sheet1.xml")
    except (OSError, KeyError, zipfile.BadZipFile):
        return False
    return (
        b'name="Datalog"' in workbook_xml
        and POWERTECH_XLSX_SIGNATURE.encode("utf-8") in sheet_xml[:4096]
    )


def parse_powertech_xlsx_file(path: str | Path) -> ParsedPowerTechXlsxFile:
    path = Path(path)
    identity = parse_powertech_xlsx_filename(path.name)
    frame = _read_workbook(path)
    rows = _header_rows(frame)
    _validate_header_labels(rows, path)
    layout = _detect_layout(rows["Item Name"], path)
    _validate_filename_layout(path, layout)
    metadata_lot = _validate_metadata(frame, identity, path)
    _validate_output_fields(rows, layout, path)
    specs = _build_specs(rows, layout, identity, path)

    source = frame.iloc[18:].copy()
    serial_text = source.iloc[:, 0].astype("string").str.strip()
    serial_numbers = pd.to_numeric(serial_text, errors="coerce")
    unexpected_rows = serial_text.notna() & serial_text.ne("") & serial_numbers.isna()
    if unexpected_rows.any():
        examples = serial_text[unexpected_rows].drop_duplicates().head(5).tolist()
        raise DianjiFormatError(f"{path.name} 数据区存在非 Serial# 记录: {examples}")
    source = source.loc[serial_numbers.notna()].copy()

    records = pd.DataFrame(index=source.index)
    invalid_counts: Counter[str] = Counter()
    for field in layout.output_fields:
        raw_values = source.iloc[:, field.item_no + 2]
        records[field.output_name] = _parse_measurement_series(
            raw_values, field.output_name, invalid_counts, path
        )
    source_rows = len(records)
    records = records.loc[records["DVCE(mV)"].notna()].copy()
    records.insert(0, "批次", identity.batch)
    records.reset_index(drop=True, inplace=True)

    return ParsedPowerTechXlsxFile(
        path=path,
        identity=identity,
        metadata_lot=metadata_lot,
        lot_identity_warning=None,
        data=records,
        specs=specs,
        source_rows=source_rows,
        kept_rows=len(records),
        invalid_marker_counts=dict(invalid_counts),
    )


def _read_workbook(path: Path) -> pd.DataFrame:
    try:
        with pd.ExcelFile(path, engine="calamine") as excel:
            if excel.sheet_names != ["Datalog"]:
                raise DianjiFormatError(
                    f"{path.name} 必须且只能包含 Datalog 工作表，实际={excel.sheet_names}"
                )
            return pd.read_excel(excel, sheet_name="Datalog", header=None)
    except DianjiFormatError:
        raise
    except Exception as exc:
        raise DianjiFormatError(f"无法读取 PowerTECH XLSX 文件 {path.name}: {exc}") from exc


def _header_rows(frame: pd.DataFrame) -> dict[str, list[object]]:
    labels = {
        "Item Name": 7,
        "Bias1": 8,
        "Bias2": 9,
        "Bias3": 10,
        "Min Limit": 11,
        "Max Limit": 12,
        "Serial#": 17,
    }
    return {label: frame.iloc[index].tolist() for label, index in labels.items()}


def _validate_header_labels(rows: dict[str, list[object]], path: Path) -> None:
    for label, row in rows.items():
        actual = _text(row[0])
        if actual != label:
            raise DianjiFormatError(
                f"{path.name} 的 PowerTECH XLSX {label} 行位置异常: {actual!r}"
            )


def _detect_layout(item_row: list[object], path: Path) -> PowerTechXlsxLayout:
    actual = []
    for expected_number, value in enumerate(item_row[3:], start=1):
        if pd.isna(value):
            continue
        match = _ITEM_RE.fullmatch(_text(value))
        if match is None or int(match.group("number")) != expected_number:
            raise DianjiFormatError(
                f"{path.name} 的 Item 编号/名称不连续: {value!r}"
            )
        actual.append(match.group("name").strip().upper())
    actual_tuple = tuple(actual)
    for layout in POWERTECH_XLSX_LAYOUTS:
        if actual_tuple == layout.item_bases:
            return layout
    raise DianjiFormatError(
        f"{path.name} 的 PowerTECH XLSX Item 布局未经验证: "
        f"数量={len(actual_tuple)}, Item={list(actual_tuple)}"
    )


def _validate_filename_layout(path: Path, layout: PowerTechXlsxLayout) -> None:
    match = _FILENAME_RE.fullmatch(path.stem)
    assert match is not None
    variant = (
        _normalize_label(match.group("label")),
        match.group("tester").upper(),
        bool(match.group("trailing_all")),
    )
    if variant not in layout.filename_variants:
        raise DianjiFormatError(
            f"{path.name} 的 {layout.name} 文件名/机台组合未经验证: {variant}"
        )


def _validate_metadata(
    frame: pd.DataFrame, identity: FileIdentity, path: Path
) -> str:
    metadata = _header_metadata(frame)
    if metadata["signature"] != POWERTECH_XLSX_SIGNATURE:
        raise DianjiFormatError(f"不是 PowerTECH XLSX Datalog: {path.name}")
    filename_match = _FILENAME_RE.fullmatch(path.stem)
    assert filename_match is not None

    tester = filename_match.group("tester").upper()
    station = filename_match.group("station").upper()
    if metadata["tester"].upper() != tester or metadata["station"].upper() != station:
        raise DianjiFormatError(
            f"{path.name} 的文件名与机台元数据不一致: "
            f"filename={station}/{tester}, workbook={metadata['station']}/{metadata['tester']}"
        )

    data_name = PureWindowsPath(metadata["data_file"]).name
    data_match = _DATA_FILENAME_RE.fullmatch(data_name)
    if data_match is None:
        raise DianjiFormatError(f"{path.name} 的 DataFileName 未经验证: {data_name}")
    for group in ("manufacturing_lot", "batch", "test_time", "station", "tester"):
        if data_match.group(group).upper() != filename_match.group(group).upper():
            raise DianjiFormatError(
                f"{path.name} 的文件名与 DataFileName {group} 不一致: {data_name}"
            )
    data_label = _normalize_label(data_match.group("label"))
    if data_label not in POWERTECH_XLSX_LABELS:
        raise DianjiFormatError(f"{path.name} 的 DataFileName 标签未经验证: {data_label}")

    program_name = PureWindowsPath(metadata["test_file"]).name
    if not program_name.upper().startswith(f"{identity.product} ".upper()):
        raise DianjiFormatError(
            f"{path.name} 的文件名产品与 TestFileName 不一致: {program_name}"
        )

    expected = f"{identity.manufacturing_lot} {identity.batch}"
    lot_text = metadata["lot"]
    if not lot_text.upper().startswith(expected.upper()):
        raise DianjiFormatError(
            f"{path.name} 的文件名与 Lot 元数据不一致: filename={expected}, Lot={lot_text}"
        )
    lot_label = _normalize_label(lot_text[len(expected):])
    if lot_label not in POWERTECH_XLSX_TRAILING_LOT_LABELS:
        raise DianjiFormatError(f"{path.name} 的 Lot 尾部标签未经验证: {lot_label}")
    return lot_text


def _header_metadata(header: pd.DataFrame) -> dict[str, str]:
    return {
        "signature": _cell(header, 0, 0),
        "tester": _cell(header, 0, 3),
        "station": _cell(header, 0, 6),
        "data_file": _cell(header, 1, 2),
        "test_file": _cell(header, 2, 2),
        "lot": _cell(header, 4, 2),
    }


def _validate_output_fields(
    rows: dict[str, list[object]], layout: PowerTechXlsxLayout, path: Path
) -> None:
    for field in layout.output_fields:
        column = field.item_no + 2
        item_match = _ITEM_RE.fullmatch(_text(rows["Item Name"][column]))
        actual_name = item_match.group("name").strip().upper() if item_match else ""
        if actual_name != field.source_name:
            raise DianjiFormatError(
                f"{path.name} 的 Item #{field.item_no} 应为 {field.source_name}，实际={actual_name}"
            )
        actual_unit = _text(rows["Serial#"][column])
        if actual_unit.casefold() != field.unit.casefold():
            raise DianjiFormatError(
                f"{path.name} 的 Item #{field.item_no} 单位不支持: "
                f"{actual_unit!r} != {field.unit!r}"
            )
        for row_label, expected in field.conditions:
            actual = _text(rows[row_label][column])
            if actual.casefold() != expected.casefold():
                raise DianjiFormatError(
                    f"{path.name} 的 Item #{field.item_no} {row_label} 未经验证: "
                    f"{actual!r} != {expected!r}"
                )


def _build_specs(
    rows: dict[str, list[object]],
    layout: PowerTechXlsxLayout,
    identity: FileIdentity,
    path: Path,
) -> pd.DataFrame:
    records = []
    for field in layout.output_fields:
        column = field.item_no + 2
        low_raw = _text(rows["Min Limit"][column])
        high_raw = _text(rows["Max Limit"][column])
        low_value = _parse_limit(low_raw)
        high_value = _parse_limit(high_raw)
        normalized = (
            low_value is not None and high_value is not None and low_value > high_value
        )
        if normalized:
            low_value, high_value = high_value, low_value
        conditions = [
            _text(rows[label][column])
            for label in ("Bias1", "Bias2", "Bias3")
            if _text(rows[label][column])
        ]
        records.append(
            {
                "Source_ID": path.stem,
                "lot_ID": identity.batch,
                "Parameter": field.output_name,
                "Unit": field.unit,
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


def _parse_measurement_series(
    raw_values: pd.Series,
    output_name: str,
    invalid_counts: Counter[str],
    path: Path,
) -> pd.Series:
    text = raw_values.astype("string").str.strip()
    numeric = pd.to_numeric(text, errors="coerce").astype(float)
    overflow = text.str.casefold().eq("over").fillna(False)
    sentinels = numeric.isin(INVALID_NUMERIC_MARKERS)
    invalid_count = int(overflow.sum() + sentinels.sum())
    if invalid_count:
        invalid_counts[output_name] += invalid_count
    unexpected = text.notna() & text.ne("") & numeric.isna() & ~overflow
    if unexpected.any():
        examples = text[unexpected].drop_duplicates().head(5).tolist()
        raise DianjiFormatError(
            f"{path.name} 的 {output_name} 包含未经验证的非数值标记: {examples}"
        )
    numeric.loc[overflow | sentinels] = math.nan
    return numeric


def _parse_limit(value: str) -> float | None:
    if not value:
        return None
    match = re.search(r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?", value)
    if match is None:
        return None
    result = float(match.group(0))
    return result if math.isfinite(result) else None


def _normalize_label(value: str) -> str:
    text = re.sub(r"\s+", " ", value).strip().upper()
    return text


def _cell(frame: pd.DataFrame, row: int, column: int) -> str:
    if row >= len(frame.index) or column >= len(frame.columns):
        return ""
    return _text(frame.iat[row, column])


def _text(value: object) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()
