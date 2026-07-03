#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Generate Dianji SYL/SBL yield report workbooks."""

from __future__ import annotations

import argparse
import math
import re
from pathlib import Path

import pandas as pd


SUMMARY_COLUMNS = ["产品名", "芯片名", "批号", "片数", "封装数量\n(Kpcs)", "PO", "周记", "片号"]

DETAIL_COLUMNS = [
    "测试批号",
    "产品型号",
    "扩散批号",
    "周记",
    "主数量",
    "PASS数",
    "FAIL数",
    "良率",
    "BIN2/Cont",
    "BIN3/Open",
    "BIN4/Short",
    "BIN5/DVDS",
    "BIN6/EAS",
    "BIN7/RG",
    "BIN8/IGSS",
    "BIN9/IDSS",
    "BIN10/BVDSS",
    "BIN11/VTH",
    "BIN12/VFSD",
    "BIN13/RDSON",
    "BIN14/MARK失效",
    "BIN15/LEAD失效",
]

BASE_COLUMNS = DETAIL_COLUMNS[:8]
RATE_COLUMNS = DETAIL_COLUMNS[8:]

SOURCE_RATE_COLUMNS = [
    "BIN2/Cont",
    "BIN3/Open",
    "BIN4/Short",
    "BIN5/DVDS",
    "BIN6/EAS",
    "BIN7/RG",
    "BIN8/IGSS",
    "BIN9/IDSS",
    "BIN10/BVDSS",
    "BIN11/VTH",
    "BIN12/VFSD",
    "BIN13/RDSON",
    "BIN14/MARK失效",
    "BIN15/LEAD失效",
]


def find_source_file(data_dir: str | Path, pattern: str | None = None) -> Path:
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"数据目录不存在: {data_dir}")
    patterns = [pattern] if pattern else ["*.xls", "*.xlsx"]
    candidates: list[Path] = []
    for item in patterns:
        candidates.extend(
            path
            for path in data_dir.glob(item)
            if path.is_file() and not path.name.startswith("~$")
        )
    if not candidates:
        raise FileNotFoundError(f"未在 {data_dir} 找到电基良率源 Excel 文件")
    return sorted(set(candidates), key=lambda p: p.stat().st_mtime, reverse=True)[0]


def find_summary_template(output_dir: str | Path) -> Path | None:
    output_dir = Path(output_dir)
    if not output_dir.exists():
        return None
    candidates = [
        path
        for path in output_dir.glob("*.xlsx")
        if path.is_file()
        and not path.name.startswith("~$")
        and "DJ" in path.name.upper()
        and "SYL" in path.name.upper()
        and "SBL" in path.name.upper()
    ]
    if not candidates:
        return None
    return sorted(candidates, key=lambda p: p.stat().st_mtime, reverse=True)[0]


def load_source_rows(source_file: str | Path) -> pd.DataFrame:
    rows = pd.read_excel(source_file, sheet_name=0)
    missing = [col for col in [*BASE_COLUMNS, *SOURCE_RATE_COLUMNS] if col not in rows.columns]
    if missing:
        raise ValueError(f"源文件缺少字段: {missing}")

    rows = rows.dropna(subset=["测试批号", "产品型号", "扩散批号", "主数量"]).copy()
    for col in ["测试批号", "产品型号", "扩散批号", "周记"]:
        rows[col] = rows[col].map(clean_text)
    for col in ["主数量", "PASS数", "FAIL数", "良率", *SOURCE_RATE_COLUMNS]:
        rows[col] = pd.to_numeric(rows[col], errors="coerce").fillna(0)
    rows = rows[rows["主数量"] > 0].reset_index(drop=True)
    if rows.empty:
        raise ValueError("源文件未解析到有效测试明细行")
    return rows


def build_detail(rows: pd.DataFrame) -> pd.DataFrame:
    detail = rows[BASE_COLUMNS].copy()
    for col in SOURCE_RATE_COLUMNS:
        detail[col] = rows[col] / rows["主数量"]
    return detail[DETAIL_COLUMNS].reset_index(drop=True)


def build_summary(rows: pd.DataFrame, output_dir: str | Path | None = None, template_file: str | Path | None = None) -> pd.DataFrame:
    template = Path(template_file) if template_file else (find_summary_template(output_dir) if output_dir else None)
    if template and template.exists():
        summary = pd.read_excel(template, sheet_name="总")
        return summary[SUMMARY_COLUMNS]

    grouped = rows.drop_duplicates(subset=["产品型号", "扩散批号", "周记"], keep="first").copy()
    return pd.DataFrame(
        {
            "产品名": grouped["产品型号"].map(normalize_product_name),
            "芯片名": "",
            "批号": grouped["扩散批号"],
            "片数": 13,
            "封装数量\n(Kpcs)": 87.1,
            "PO": "",
            "周记": grouped["周记"].map(lambda v: f"{clean_text(v)}XX" if clean_text(v) else ""),
            "片号": "",
        }
    )[SUMMARY_COLUMNS].reset_index(drop=True)


def write_report(summary: pd.DataFrame, detail: pd.DataFrame, output_file: str | Path, overwrite: bool = True) -> Path:
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists() and not overwrite:
        raise FileExistsError(f"输出文件已存在: {output_file}")

    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        workbook = writer.book
        summary.to_excel(writer, sheet_name="总", index=False)
        ws_sum = writer.sheets["总"]
        header_fmt = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1})
        text_fmt = workbook.add_format({"align": "center", "valign": "vcenter", "border": 1})
        qty_fmt = workbook.add_format({"num_format": "0.0", "align": "center", "valign": "vcenter", "border": 1})
        ws_sum.set_row(0, 30, header_fmt)
        for idx, width in enumerate([27, 14, 13, 7, 11, 23, 10, 9]):
            ws_sum.set_column(idx, idx, width, qty_fmt if idx == 4 else text_fmt)

        detail.to_excel(writer, sheet_name="SYL&SBL", index=False)
        ws = writer.sheets["SYL&SBL"]
        detail_header_fmt = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1})
        detail_text_fmt = workbook.add_format({"align": "center", "valign": "vcenter", "border": 1})
        int_fmt = workbook.add_format({"num_format": "0", "align": "center", "valign": "vcenter", "border": 1})
        yield_fmt = workbook.add_format({"num_format": "0.0000", "align": "center", "valign": "vcenter", "border": 1})
        rate_fmt = workbook.add_format({"num_format": "0.000000", "align": "center", "valign": "vcenter", "border": 1})
        section_fmt = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter"})
        label_fmt = workbook.add_format({"align": "center", "valign": "vcenter"})
        limit_fmt = workbook.add_format({"num_format": "0.000", "align": "center", "valign": "vcenter"})
        syl_fmt = workbook.add_format({"num_format": "0.00", "align": "center", "valign": "vcenter"})

        ws.set_row(0, 24, detail_header_fmt)
        widths = [18, 35, 13, 9, 8, 9, 8, 10, 11, 12, 12, 13, 11, 10, 12, 12, 15, 12, 14, 16, 18, 18]
        for idx, width in enumerate(widths):
            if idx in {4, 5, 6}:
                fmt = int_fmt
            elif idx == 7:
                fmt = yield_fmt
            elif idx >= 8:
                fmt = rate_fmt
            else:
                fmt = detail_text_fmt
            ws.set_column(idx, idx, width, fmt)

        data_count = len(detail)
        write_sigma_block(ws, data_count + 3, "3Sigma", 3, data_count, rounded_limits(detail, 3), section_fmt, label_fmt, limit_fmt, syl_fmt)
        write_sigma_block(ws, data_count + 10, "4Sigma", 4, data_count, rounded_limits(detail, 4), section_fmt, label_fmt, limit_fmt, syl_fmt)
        ws.freeze_panes(1, 0)

    return output_file


def write_sigma_block(ws, top_row: int, title: str, sigma: int, row_count: int, limit_values: list[float], section_fmt, label_fmt, limit_fmt, syl_fmt) -> None:
    first_excel = 2
    last_excel = first_excel + row_count - 1
    metric_headers = ["良率", *RATE_COLUMNS]
    ws.write(top_row, 5, title, section_fmt)
    for offset, header in enumerate(metric_headers):
        ws.write(top_row, 7 + offset, header, section_fmt)

    ws.write(top_row + 1, 6, "均值", label_fmt)
    ws.write(top_row + 2, 6, "标准差", label_fmt)
    ws.write(top_row + 3, 6, "SYL", label_fmt)
    ws.write(top_row + 4, 6, "SBL", label_fmt)

    for col in range(7, 22):
        letter = excel_col(col)
        ws.write_formula(top_row + 1, col, f"=AVERAGE({letter}{first_excel}:{letter}{last_excel})", limit_fmt)
        ws.write_formula(top_row + 2, col, f"=STDEV({letter}{first_excel}:{letter}{last_excel})", limit_fmt)

    ws.write_formula(top_row + 3, 7, f"=H{top_row + 2}-{sigma}*H{top_row + 3}", limit_fmt)
    for col in range(8, 22):
        letter = excel_col(col)
        ws.write_formula(top_row + 4, col, f"={letter}{top_row + 2}+{sigma}*{letter}{top_row + 3}", limit_fmt)

    ws.write_number(top_row + 5, 7, limit_values[0], syl_fmt)
    for idx, col in enumerate(range(8, 22), start=1):
        ws.write_number(top_row + 5, col, limit_values[idx], limit_fmt)


def rounded_limits(detail: pd.DataFrame, sigma: int) -> list[float]:
    metrics = detail[["良率", *RATE_COLUMNS]].apply(pd.to_numeric, errors="coerce")
    means = metrics.mean()
    stds = metrics.std(ddof=1)
    values = [floor_to(float(means.iloc[0] - sigma * stds.iloc[0]), 0.01)]
    values.extend(ceil_to(float(means.iloc[i] + sigma * stds.iloc[i]), 0.001) for i in range(1, len(metrics.columns)))
    return values


def generate_report(
    data_dir: str | Path = "data",
    output_dir: str | Path = "output",
    source_file: str | Path | None = None,
    output_file: str | Path | None = None,
    template_file: str | Path | None = None,
) -> Path:
    source = Path(source_file) if source_file else find_source_file(data_dir)
    rows = load_source_rows(source)
    detail = build_detail(rows)
    summary = build_summary(rows, output_dir=output_dir, template_file=template_file)
    target = Path(output_file) if output_file else sequenced_output_path(output_dir, default_output_name(rows))
    return write_report(summary, detail, target)


def default_output_name(rows: pd.DataFrame) -> str:
    products = rows["产品型号"].map(normalize_product_name).drop_duplicates().tolist()
    product = product_family_name(products)
    return f"{product} DJ SYL&SBL.xlsx"


def sequenced_output_path(output_dir: str | Path, filename: str) -> Path:
    """Return an output path with a running sequence suffix to avoid overwrites."""
    output_dir = Path(output_dir)
    stem = Path(filename).stem
    suffix = Path(filename).suffix
    output_dir.mkdir(parents=True, exist_ok=True)

    pattern = re.compile(rf"^{re.escape(stem)}_(\d{{3,}}){re.escape(suffix)}$", re.IGNORECASE)
    sequence = max(
        (
            int(match.group(1))
            for path in output_dir.iterdir()
            if path.is_file() and (match := pattern.match(path.name))
        ),
        default=0,
    ) + 1

    while True:
        candidate = output_dir / f"{stem}_{sequence:03d}{suffix}"
        if not candidate.exists():
            return candidate
        sequence += 1


def normalize_product_name(value: object) -> str:
    text = clean_text(value)
    return re.sub(r"-AT-\d+$", "", text)


def product_family_name(products: list[str]) -> str:
    products = [p for p in dict.fromkeys(products) if p]
    if not products:
        return "DJ"
    if len(products) == 1:
        return products[0]
    prefix = common_prefix(products)
    match = re.match(r"^(.*-7E)", prefix)
    if match:
        return f"{match.group(1)}XX"
    return f"{prefix.rstrip('-_ ')}XX"


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("\xa0", " ").strip()
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def common_prefix(values: list[str]) -> str:
    prefix = values[0] if values else ""
    for value in values[1:]:
        while prefix and not value.startswith(prefix):
            prefix = prefix[:-1]
    return prefix


def excel_col(zero_based_col: int) -> str:
    n = zero_based_col + 1
    letters = ""
    while n:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def floor_to(value: float, step: float) -> float:
    return round(math.floor((value + 1e-12) / step) * step, 12)


def ceil_to(value: float, step: float) -> float:
    return round(math.ceil((value - 1e-12) / step) * step, 12)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成电基 SYL/SBL 良率分析报表")
    parser.add_argument("--data-dir", default="data", help="良率源数据目录，默认 data")
    parser.add_argument("--output-dir", default="output", help="输出目录，默认 output")
    parser.add_argument("--source-file", help="指定源 Excel 文件；不指定时自动扫描 data-dir")
    parser.add_argument("--output-file", help="指定输出 xlsx 文件；不指定时按产品自动命名")
    parser.add_argument("--template-file", help="指定已有电基报表，用其“总”sheet作为汇总模板")
    args = parser.parse_args(argv)
    output = generate_report(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        source_file=args.source_file,
        output_file=args.output_file,
        template_file=args.template_file,
    )
    print(f"已生成: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
