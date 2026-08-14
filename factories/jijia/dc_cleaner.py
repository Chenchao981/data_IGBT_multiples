"""Clean approved Jijia FT CSV files into the ASE-style DC workbook."""

from __future__ import annotations

import argparse
from collections import Counter
import logging
from pathlib import Path

import pandas as pd

from factories.base.base_cleaner import BaseCleaner
from factories.jijia.config import DATA_TYPES, FACTORY_NAME, OUTPUT_SHEET_NAME
from factories.jijia.parser import (
    JijiaFormatError,
    is_jijia_csv_file,
    parse_jijia_file,
)
from shared.excel_utils import (
    create_output_run_dir,
    generate_run_filename,
    write_excel_fast,
)


logger = logging.getLogger(__name__)


class JijiaFTCleaner(BaseCleaner):
    """Merge one approved Jijia product layout without filtering PASS/FAIL rows."""

    factory_name = FACTORY_NAME
    data_types = DATA_TYPES
    unit_conversions = {}

    def __init__(self, input_dir: str | Path, output_dir: str | Path):
        super().__init__(str(input_dir), str(output_dir))
        self.last_output_file: Path | None = None
        self.last_run_summary: dict[str, object] = {}

    def scan_source_files(self) -> list[Path]:
        if not self.input_dir.exists():
            raise FileNotFoundError(f"集佳输入目录不存在: {self.input_dir}")
        files = sorted(
            path
            for path in self.input_dir.rglob("*.csv")
            if path.is_file() and not path.name.startswith("~$")
        )
        if not files:
            raise FileNotFoundError(f"未在 {self.input_dir} 找到集佳 CSV 文件")
        unsupported = [path.name for path in files if not is_jijia_csv_file(path)]
        if unsupported:
            raise JijiaFormatError(
                "输入目录混有非集佳 STS8203 CSV 文件，请分开选择目录: "
                + ", ".join(unsupported[:5])
            )
        return files

    def process_all(self, data_type: str | None = None) -> bool:
        if data_type not in (None, "FT-ALL", "DC"):
            raise ValueError(f"集佳不支持的数据类型: {data_type}")
        self.last_output_file = None
        self.last_run_summary = {}

        files = self.scan_source_files()
        logger.info("集佳 FT-ALL 清洗开始，共 %s 个文件", len(files))
        parsed_files = []
        for path in files:
            parsed = parse_jijia_file(path)
            parsed_files.append(parsed)
            logger.info(
                "已解析 %s: 记录=%s, PASS=%s, FAIL=%s, lot_ID=%s",
                path.name,
                parsed.source_rows,
                parsed.pass_rows,
                parsed.fail_rows,
                parsed.identity.batch,
            )

        products = {parsed.identity.product for parsed in parsed_files}
        if len(products) != 1:
            raise JijiaFormatError(
                "一次只能合并一个集佳产品: " + ", ".join(sorted(products))
            )
        schemas = {tuple(parsed.data.columns) for parsed in parsed_files}
        if len(schemas) != 1:
            raise JijiaFormatError("集佳文件输出参数不一致，拒绝错列合并")

        merged = pd.concat(
            [parsed.data for parsed in parsed_files],
            ignore_index=True,
            sort=False,
        )
        if merged.empty:
            raise JijiaFormatError("集佳源文件没有有效测试记录，未生成输出")
        merged.insert(0, "NUM", range(1, len(merged) + 1))

        run_dir = create_output_run_dir(self.output_dir, merged["lot_ID"].tolist())
        output_file = run_dir / generate_run_filename(run_dir)
        if not write_excel_fast(
            merged,
            output_file,
            index=False,
            sheet_name=OUTPUT_SHEET_NAME,
        ):
            raise OSError(f"集佳清洗结果写入失败: {output_file}")

        batch_counts = merged["lot_ID"].value_counts().sort_index().to_dict()
        self.last_output_file = output_file.resolve()
        self.last_run_summary = {
            "files": len(parsed_files),
            "product": next(iter(products)),
            "source_rows": sum(parsed.source_rows for parsed in parsed_files),
            "kept_rows": len(merged),
            "pass_rows": sum(parsed.pass_rows for parsed in parsed_files),
            "fail_rows": sum(parsed.fail_rows for parsed in parsed_files),
            "batch_counts": batch_counts,
            "columns": list(merged.columns),
        }
        logger.info(
            "集佳清洗完成: %s；文件=%s，记录=%s，参数=%s",
            output_file,
            len(parsed_files),
            len(merged),
            len(merged.columns) - 2,
        )
        return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="清洗集佳 NCE15TD120BT STS8203 FT CSV")
    parser.add_argument("input_dir", help="包含集佳 CSV 的输入目录")
    parser.add_argument("output_dir", help="输出目录")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    cleaner = JijiaFTCleaner(args.input_dir, args.output_dir)
    cleaner.process_all()
    print(cleaner.last_output_file)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
