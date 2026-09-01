#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Clean verified Dianji FT-ALL sources into the user's RAW workbook format."""

from __future__ import annotations

import argparse
from collections import Counter
import logging
from pathlib import Path
import re

import pandas as pd

from factories.base.base_cleaner import BaseCleaner
from factories.dianji.config import (
    DATA_TYPES,
    FACTORY_NAME,
    OUTPUT_FILE_SUFFIX,
    OUTPUT_SHEET_NAME,
)
from factories.dianji.models import DianjiFormatError
from factories.dianji.source_registry import (
    SUPPORTED_SOURCE_EXTENSIONS,
    detect_dianji_source_format,
    parse_dianji_source_file,
)
from shared.excel_utils import create_output_run_dir, write_excel_fast
from shared.pat_engine import extract_parameter_schema, merge_parameter_schemas


logger = logging.getLogger(__name__)


_PACKAGE_CODE_SUFFIX_RE = re.compile(r"-\d[A-Z]\d{2}$", re.IGNORECASE)
_POWERTECH_SOURCE_FORMATS = frozenset({"PowerTECH", "PowerTECH XLSX"})
_OUTPUT_IDENTIFIER_COLUMNS = frozenset({"批次"})


def _parsed_parameter_keys(parsed) -> object | None:
    """Read the optional semantic schema exposed by a newer parser."""

    for name in ("parameter_keys", "parameter_schema"):
        value = getattr(parsed, name, None)
        if value is not None:
            return value
    for name in ("parameter_keys", "parameter_schema"):
        value = parsed.data.attrs.get(name)
        if value is not None:
            return value
    return None


def _frame_with_parameter_keys(parsed) -> pd.DataFrame:
    """Return a shallow frame copy carrying parser semantic keys when present."""

    frame = parsed.data.copy(deep=False)
    parameter_keys = _parsed_parameter_keys(parsed)
    if parameter_keys is not None:
        frame.attrs["parameter_keys"] = parameter_keys
    return frame


def _resolve_output_parameter_schema(
    parsed_files: list[object], source_format: str
) -> tuple[str, ...]:
    """Resolve one exact or strictly right-appended output schema."""

    mode = (
        "nested_prefix"
        if source_format in _POWERTECH_SOURCE_FORMATS
        else "exact"
    )
    canonical_columns: tuple[str, ...] | None = None
    canonical_keys: tuple[object, ...] | None = None
    for parsed in parsed_files:
        frame = _frame_with_parameter_keys(parsed)
        try:
            columns, keys = extract_parameter_schema(
                frame, identifier_columns=_OUTPUT_IDENTIFIER_COLUMNS
            )
            canonical_columns, canonical_keys, _added = merge_parameter_schemas(
                canonical_columns,
                canonical_keys,
                columns,
                keys,
                mode=mode,
                context=parsed.path.name,
            )
        except ValueError as exc:
            raise DianjiFormatError(
                f"电基文件输出参数不兼容，拒绝错列合并: {exc}"
            ) from exc
    if not canonical_columns:
        raise DianjiFormatError("电基文件没有可输出的测试参数")
    return canonical_columns


class DianjiDCCleaner(BaseCleaner):
    """Merge one product's Dianji FT-ALL source reports into a RAW workbook."""

    factory_name = FACTORY_NAME
    data_types = DATA_TYPES
    unit_conversions = {}

    def __init__(self, input_dir: str | Path, output_dir: str | Path):
        super().__init__(str(input_dir), str(output_dir))
        self.last_output_file: Path | None = None
        self.last_scatter_manifest: Path | None = None
        self.last_run_summary: dict[str, object] = {}

    def scan_source_files(self) -> list[Path]:
        if not self.input_dir.exists():
            raise FileNotFoundError(f"电基输入目录不存在: {self.input_dir}")
        files = sorted(
            path
            for path in self.input_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() in SUPPORTED_SOURCE_EXTENSIONS
            and not path.name.startswith("~$")
        )
        if not files:
            raise FileNotFoundError(
                f"未在 {self.input_dir} 找到电基 PowerTECH .xls/.xlsx、STS8203 .csv 或 TF .csv 文件"
            )
        unsupported = []
        for path in files:
            try:
                detect_dianji_source_format(path)
            except DianjiFormatError as exc:
                unsupported.append(f"{path.name} ({exc})")
        if unsupported:
            raise DianjiFormatError(
                "输入目录混有不支持的电基 .xls/.xlsx/.csv 文件，请分开选择目录: "
                + ", ".join(unsupported[:5])
            )
        return files

    def process_all(self, data_type: str | None = None) -> bool:
        if data_type not in (None, "FT-ALL", "DC"):
            raise ValueError(f"电基不支持的数据类型: {data_type}")
        self.last_output_file = None
        self.last_scatter_manifest = None

        files = self.scan_source_files()
        logger.info("电基 FT-ALL 清洗开始，共 %s 个文件", len(files))
        parsed_files = []
        for path in files:
            parsed = parse_dianji_source_file(path)
            parsed_files.append(parsed)
            if parsed.lot_identity_warning:
                logger.warning("%s", parsed.lot_identity_warning)
            logger.info(
                "已解析 %s [%s]: 源记录=%s, 保留=%s, 批次=%s",
                path.name,
                parsed.source_format,
                parsed.source_rows,
                parsed.kept_rows,
                parsed.identity.batch,
            )

        source_formats = {
            parsed.source_format
            for parsed in parsed_files
        }
        if len(source_formats) != 1:
            raise DianjiFormatError(
                "一次只能清洗一种电基源格式，当前目录包含: "
                + ", ".join(sorted(source_formats))
            )

        products = {parsed.identity.product for parsed in parsed_files}
        if len(products) != 1:
            raise DianjiFormatError(
                "一次只能合并一个产品，当前目录包含: " + ", ".join(sorted(products))
            )

        source_format = next(iter(source_formats))
        parameter_columns = _resolve_output_parameter_schema(
            parsed_files, source_format
        )

        source_frames = []
        for parsed in parsed_files:
            frame = parsed.data.reindex(
                columns=["批次", *parameter_columns]
            ).copy()
            frame["_source_id"] = parsed.path.stem
            source_frames.append(frame)
        merged = pd.concat(source_frames, ignore_index=True, sort=False)
        if merged.empty:
            raise DianjiFormatError("所有源文件都没有测到有效入口参数，未生成输出")
        source_ids = merged.pop("_source_id").astype(str)
        merged.insert(0, "NUM", range(1, len(merged) + 1))

        product = next(iter(products))
        output_file = next_output_path(self.output_dir, product)
        if not write_excel_fast(
            merged,
            output_file,
            index=False,
            sheet_name=OUTPUT_SHEET_NAME,
        ):
            raise OSError(f"电基清洗结果写入失败: {output_file}")

        invalid_counts: Counter[str] = Counter()
        for parsed in parsed_files:
            invalid_counts.update(parsed.invalid_marker_counts)
        batch_counts = merged["批次"].value_counts().sort_index().to_dict()
        source_rows = sum(parsed.source_rows for parsed in parsed_files)
        self.last_output_file = output_file.resolve()
        from frontend.ft_scatter import export_scatter_bundle

        scatter_data = merged.rename(columns={"批次": "lot_ID"}).copy()
        scatter_data.insert(2, "Source_ID", source_ids.tolist())
        specs = pd.concat(
            [parsed.specs for parsed in parsed_files], ignore_index=True, sort=False
        )
        bundle_stem = f"{output_file.stem}_ft_scatter"
        self.last_scatter_manifest = export_scatter_bundle(
            scatter_data,
            specs,
            output_file.parent,
            cleaned_file=self.last_output_file,
            factory=FACTORY_NAME,
            data_type="FT-ALL",
            bundle_stem=bundle_stem,
        ).resolve()
        self.last_run_summary = {
            "files": len(parsed_files),
            "product": product,
            "source_formats": dict(
                Counter(
                    parsed.source_format
                    for parsed in parsed_files
                )
            ),
            "source_rows": source_rows,
            "kept_rows": len(merged),
            "dropped_before_dvds": source_rows - len(merged),
            "dropped_before_retention": source_rows - len(merged),
            "retention_parameter": (
                "DVCE(mV)" if source_formats == {"PowerTECH XLSX"}
                else "Udc(V)" if source_formats == {"Dianji TF CSV"}
                else "DVDS(mV)"
            ),
            "batch_counts": batch_counts,
            "invalid_marker_counts": dict(invalid_counts),
            "identity_warnings": [
                parsed.lot_identity_warning
                for parsed in parsed_files
                if parsed.lot_identity_warning
            ],
            "columns": list(merged.columns),
        }
        logger.info(
            "电基清洗完成: %s；源记录=%s，保留=%s，入口参数前失效=%s",
            output_file,
            source_rows,
            len(merged),
            source_rows - len(merged),
        )
        logger.info("FT散点图数据包: %s", self.last_scatter_manifest)
        return True


def next_output_path(output_dir: str | Path, product: str) -> Path:
    """Create '<product family>_NNN' and place the RAW workbook inside it."""
    run_dir = create_output_run_dir(output_dir, [output_product_name(product)])
    return run_dir / f"{product}{OUTPUT_FILE_SUFFIX}"


def output_product_name(product: str) -> str:
    """Drop a trailing package code such as '-3E00' from the run-folder name."""
    product = product.strip()
    family = _PACKAGE_CODE_SUFFIX_RE.sub("", product).strip()
    return family or product


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="自动识别并清洗电基 PowerTECH/PowerTECH XLSX/STS8203/TF FT-ALL 源数据"
    )
    parser.add_argument(
        "input_dir",
        help="包含 PowerTECH 伪 .xls、PowerTECH .xlsx、STS8203 .csv 或 TF .csv 文件的目录",
    )
    parser.add_argument("output_dir", help="输出目录")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    cleaner = DianjiDCCleaner(args.input_dir, args.output_dir)
    cleaner.process_all()
    print(cleaner.last_output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
