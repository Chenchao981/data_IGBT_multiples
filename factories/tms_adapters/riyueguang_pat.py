"""日月光 PAT：使用独立 DC Adapter 直接分析原始 XLSX。"""

from __future__ import annotations

from pathlib import Path
import re

import pandas as pd

from factories.jiequn.pat_cleaner import save_pat
from factories.tms_adapters.riyueguang_dc import RiyueguangTmsDCCleaner
from shared.excel_utils import read_excel_fast
from shared.pat_engine import RawPatGroup, build_spooled_raw_pat


RAW_TYPES = ("DC", "DVDS", "RG")
_PRODUCT_PATTERN = re.compile(
    r"(NCE[A-Z0-9]+(?:\([A-Z0-9]+\))?-\d[A-Z]\d{2})",
    re.IGNORECASE,
)
_LOT_PATTERN = re.compile(r"[A-Z0-9]{4}-\d{4}", re.IGNORECASE)
_CONTROL_ITEMS = frozenset({"CONT", "OPEN", "SHORT"})


def _product(path: Path) -> str:
    match = _PRODUCT_PATTERN.search(path.stem)
    if not match:
        raise ValueError(f"无法从日月光原始文件名识别产品: {path.name}")
    return match.group(1).upper()


def _valid_xlsx(path: Path) -> bool:
    return (
        path.is_file()
        and path.suffix.lower() == ".xlsx"
        and not path.name.startswith("~$")
    )


def _resolve_raw_files(source_dir: str | Path) -> dict[str, tuple[Path, ...]]:
    source = Path(source_dir).expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"日月光 PAT 原始目录不存在: {source}")

    files_by_type: dict[str, tuple[Path, ...]] = {}
    selected_type = source.name.upper()
    if selected_type in RAW_TYPES:
        files_by_type[selected_type] = tuple(
            sorted(
                (path.resolve() for path in source.iterdir() if _valid_xlsx(path)),
                key=lambda path: str(path).casefold(),
            )
        )
    else:
        for raw_type in RAW_TYPES:
            directory = source / raw_type
            if directory.is_dir():
                files_by_type[raw_type] = tuple(
                    sorted(
                        (
                            path.resolve()
                            for path in directory.iterdir()
                            if _valid_xlsx(path)
                        ),
                        key=lambda path: str(path).casefold(),
                    )
                )

    files_by_type = {
        raw_type: files for raw_type, files in files_by_type.items() if files
    }
    all_files = tuple(path for files in files_by_type.values() for path in files)
    if not all_files:
        raise FileNotFoundError(
            f"未找到日月光原始 DC/DVDS/RG XLSX: {source}"
        )
    products = {_product(path) for path in all_files}
    if len(products) != 1:
        raise ValueError(
            "日月光 PAT 原始目录包含多个产品，不能合并计算: "
            + ", ".join(sorted(products))
        )
    return files_by_type


def _extract_ebr_measurements(path: Path, *, raw_type: str) -> pd.DataFrame:
    """Parse the strict Riyueguang EBR DVDS/RG table from the reviewed layout."""

    frame = read_excel_fast(path, header=None)
    if len(frame) <= 13 or frame.shape[1] <= 4:
        raise ValueError(f"日月光 {raw_type} 文件结构不完整: {path.name}")
    test_columns = [
        column
        for column, value in enumerate(frame.iloc[0].tolist())
        if str(value).strip().casefold() == "test"
    ]
    if len(test_columns) != 1:
        raise ValueError(
            f"日月光 {raw_type} 首行必须且只能有一个 Test: {path.name}"
        )
    marker_column = test_columns[0]
    expected_markers = ((1, marker_column, "Item"), (5, marker_column, "Unit"))
    for row, column, expected in expected_markers:
        actual = str(frame.iat[row, column]).strip()
        if actual.casefold() != expected.casefold():
            raise ValueError(
                f"日月光 {raw_type} 表头位置异常: {path.name}; "
                f"第{row + 1}行第{column + 1}列={actual!r}"
            )
    if str(frame.iat[12, 0]).strip().casefold() != "test no.":
        raise ValueError(f"日月光 {raw_type} 第13行缺少 Test No.: {path.name}")

    item_columns: list[tuple[int, str, str]] = []
    seen: set[str] = set()
    for column in range(marker_column + 1, frame.shape[1]):
        item = str(frame.iat[1, column]).strip()
        if not item or item.upper() in _CONTROL_ITEMS or item.lower() == "nan":
            continue
        unit = str(frame.iat[5, column]).strip()
        if not unit or unit.lower() == "nan":
            raise ValueError(
                f"日月光 {raw_type} 参数 {item} 缺少单位: {path.name}"
            )
        output_name = f"{item}({unit})"
        if output_name in seen:
            raise ValueError(
                f"日月光 {raw_type} 参数重名: {output_name}; {path.name}"
            )
        seen.add(output_name)
        item_columns.append((column, item, output_name))

    item_names = {item.upper() for _, item, _ in item_columns}
    required = {"DVCE", "DVF"} if raw_type == "DVDS" else {"RG", "CISS"}
    if not required.issubset(item_names):
        raise ValueError(
            f"日月光 {raw_type} 参数结构未经验证: {path.name}; "
            f"缺少={sorted(required - item_names)}"
        )

    values: dict[str, pd.Series] = {}
    for column, item, output_name in item_columns:
        raw_values = frame.iloc[13:, column]
        numeric = pd.to_numeric(raw_values, errors="coerce")
        text_values = raw_values.astype("string").str.strip()
        invalid = raw_values.notna() & text_values.ne("") & numeric.isna()
        if invalid.any():
            first = int(invalid[invalid].index[0]) + 1
            raise ValueError(
                f"日月光 {raw_type} 参数 {item} 第{first}行不是数值: {path.name}"
            )
        values[output_name] = numeric.reset_index(drop=True)

    result = pd.DataFrame(values).dropna(how="all").reset_index(drop=True)
    if result.empty:
        raise ValueError(f"日月光 {raw_type} 没有有效测量数据: {path.name}")
    lot_match = _LOT_PATTERN.search(path.stem)
    if not lot_match:
        raise ValueError(f"日月光 {raw_type} 文件名缺少批次号: {path.name}")
    result.insert(0, "lot_ID", lot_match.group().upper())
    return result


def build_raw_pat(
    source_dir: str | Path,
    spool_dir: str | Path | None = None,
    progress_interval: int = 25,
) -> pd.DataFrame:
    """逐文件调用日月光严格 DC Adapter，并使用 FT 统一公式计算 PAT。"""

    files_by_type = _resolve_raw_files(source_dir)
    source = Path(source_dir).expanduser().resolve()
    dc_adapter = RiyueguangTmsDCCleaner(source, spool_dir or source)

    extractors = {
        "DC": dc_adapter.extract_dc_data,
        "DVDS": lambda path: _extract_ebr_measurements(path, raw_type="DVDS"),
        "RG": lambda path: _extract_ebr_measurements(path, raw_type="RG"),
    }
    return build_spooled_raw_pat(
        tuple(
            RawPatGroup(raw_type, files, extractors[raw_type])
            for raw_type, files in files_by_type.items()
        ),
        spool_dir=spool_dir,
        progress_interval=progress_interval,
        factory_label="日月光",
    )


def generate_raw_pat(
    source_dir: str | Path,
    output_dir: str | Path = "output/日月光-output",
) -> Path | None:
    """从日月光原始 DC XLSX 目录直接生成 PAT 报表。"""

    return save_pat(
        build_raw_pat(source_dir, spool_dir=output_dir),
        output_dir,
    )
