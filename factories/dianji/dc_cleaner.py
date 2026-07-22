#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Clean Dianji PowerTECH FT-ALL reports into the user's RAW workbook format."""

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
from factories.dianji.powertech_parser import (
    DianjiFormatError,
    ParsedPowerTechFile,
    is_powertech_text_file,
    parse_powertech_file,
)
from shared.excel_utils import write_excel_fast


logger = logging.getLogger(__name__)


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
            and path.suffix.lower() == ".xls"
            and not path.name.startswith("~$")
        )
        if not files:
            raise FileNotFoundError(f"未在 {self.input_dir} 找到电基 PowerTECH .xls 文件")
        unsupported = [path.name for path in files if not is_powertech_text_file(path)]
        if unsupported:
            raise DianjiFormatError(
                "输入目录混有非 PowerTECH 文本的 .xls 文件，请分开选择目录: "
                + ", ".join(unsupported[:5])
            )
        return files

    def process_all(self, data_type: str | None = None) -> bool:
        if data_type not in (None, "FT-ALL", "DC"):
            raise ValueError(f"电基不支持的数据类型: {data_type}")
        self.last_output_file = None
        self.last_scatter_manifest = None

        files = self.scan_source_files()
        logger.info("电基 PowerTECH 清洗开始，共 %s 个文件", len(files))
        parsed_files: list[ParsedPowerTechFile] = []
        for path in files:
            parsed = parse_powertech_file(path)
            parsed_files.append(parsed)
            if parsed.lot_identity_warning:
                logger.warning("%s", parsed.lot_identity_warning)
            logger.info(
                "已解析 %s: 源记录=%s, 保留=%s, 周记=%s",
                path.name,
                parsed.source_rows,
                parsed.kept_rows,
                parsed.identity.batch,
            )

        products = {parsed.identity.product for parsed in parsed_files}
        if len(products) != 1:
            raise DianjiFormatError(
                "一次只能合并一个产品，当前目录包含: " + ", ".join(sorted(products))
            )

        schemas = {tuple(parsed.data.columns) for parsed in parsed_files}
        if len(schemas) != 1:
            details = " | ".join(
                f"{parsed.path.name}: {list(parsed.data.columns)}" for parsed in parsed_files
            )
            raise DianjiFormatError(f"电基文件输出参数不一致，拒绝错列合并: {details}")

        source_frames = []
        for parsed in parsed_files:
            frame = parsed.data.copy()
            frame["_source_id"] = parsed.path.stem
            source_frames.append(frame)
        merged = pd.concat(source_frames, ignore_index=True, sort=False)
        if merged.empty:
            raise DianjiFormatError("所有源文件都没有测到有效 DVDS 数据，未生成输出")
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
            "source_rows": source_rows,
            "kept_rows": len(merged),
            "dropped_before_dvds": source_rows - len(merged),
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
            "电基清洗完成: %s；源记录=%s，保留=%s，DVDS前失效=%s",
            output_file,
            source_rows,
            len(merged),
            source_rows - len(merged),
        )
        logger.info("FT散点图数据包: %s", self.last_scatter_manifest)
        return True


def next_output_path(output_dir: str | Path, product: str) -> Path:
    """Match '<product> DJ PAT.xlsx' and add _001/_002 only on reruns."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    base = output_dir / f"{product}{OUTPUT_FILE_SUFFIX}"
    if not base.exists():
        return base

    stem = base.stem
    suffix = base.suffix
    pattern = re.compile(rf"^{re.escape(stem)}_(\d{{3,}}){re.escape(suffix)}$", re.I)
    sequence = max(
        (
            int(match.group(1))
            for path in output_dir.iterdir()
            if path.is_file() and (match := pattern.match(path.name))
        ),
        default=0,
    ) + 1
    return output_dir / f"{stem}_{sequence:03d}{suffix}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="清洗电基 PowerTECH FT-ALL 源数据")
    parser.add_argument("input_dir", help="包含 PowerTECH 伪 .xls 文本文件的目录")
    parser.add_argument("output_dir", help="输出目录")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    cleaner = DianjiDCCleaner(args.input_dir, args.output_dir)
    cleaner.process_all()
    print(cleaner.last_output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
