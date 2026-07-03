#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Generate Jiequn yield summary and SYL/SBL analysis workbooks."""

from __future__ import annotations

import argparse
import math
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import pandas as pd


SUMMARY_COLUMNS = ["产品名", "芯片名s", "批号", "片数", "封装数量\n(Kpcs)", "PO", "周记", "片号"]

ANALYSIS_COLUMNS = [
    "Customer\n客戶",
    "Device\n機種",
    "Package\n外型",
    "PO Sequ.\n訂單序號",
    "PO No.\n訂單號碼",
    "PO Qty\n訂單數",
    "PO Type\n訂單性質",
    "Wafer I.D.\n晶圓版本",
    "Wafer Lot\n晶圓批號",
    "Date Code\n日期代碼",
    "LotB No\nLotB 號碼",
    "Test Input\n測試輸入數",
    "Test Output\n良品數",
    "Test yield\n電性良率",
    "BIN 3 LV不良",
    "BIN 4 DVDS不良",
    "BIN 5 PINSHORT不良 SHORT不良",
    "BIN 6 BVDSS不良",
    "BIN 7 IGSS不良",
    "BIN 8 IDSS不良",
    "BIN 9 RG不良",
    "BIN 10 VTH,VFSD不良",
    "BIN 11 RDON不良",
    "BIN 12 CONT不良",
    "BIN 14 OPEN不良",
    "Lead       不良",
]

SOURCE_INDEX = {
    "Customer\n客戶": 0,
    "Device\n機種": 1,
    "Package\n外型": 2,
    "PO Sequ.\n訂單序號": 3,
    "PO No.\n訂單號碼": 4,
    "PO Qty\n訂單數": 5,
    "PO Type\n訂單性質": 6,
    "Wafer I.D.\n晶圓版本": 7,
    "Wafer Lot\n晶圓批號": 8,
    "Date Code\n日期代碼": 9,
    "LotB No\nLotB 號碼": 10,
    "Test Input\n測試輸入數": 11,
    "Test Output\n良品數": 12,
    "BIN 3 LV不良": 18,
    "BIN 4 DVDS不良": 19,
    "BIN 5 PINSHORT不良 SHORT不良": 20,
    "BIN 6 BVDSS不良": 21,
    "BIN 7 IGSS不良": 22,
    "BIN 8 IDSS不良": 23,
    "BIN 9 RG不良": 24,
    "BIN 10 VTH,VFSD不良": 25,
    "BIN 11 RDON不良": 26,
    "BIN 12 CONT不良": 27,
    "BIN 14 OPEN不良": 29,
    "Lead       不良": 33,
}

RATE_COLUMNS = ANALYSIS_COLUMNS[14:]


@dataclass(frozen=True)
class YieldReportConfig:
    """Report assumptions not present in Jiequn's source yield export."""

    wafer_count: int = 25
    kpcs_per_wafer: float = 3.35

    @property
    def package_qty_kpcs(self) -> float:
        return self.wafer_count * self.kpcs_per_wafer

    @property
    def wafer_no_text(self) -> str:
        return f"1-{self.wafer_count}#"


def find_source_file(data_dir: str | Path, pattern: str | None = None) -> Path:
    """Find the newest Jiequn yield source workbook in a directory."""
    data_dir = Path(data_dir)
    if not data_dir.exists():
        raise FileNotFoundError(f"数据目录不存在: {data_dir}")

    patterns = [pattern] if pattern else ["*良率报表*.xls*", "*报表*.xls*", "*.xls", "*.xlsx"]
    candidates: list[Path] = []
    for item in patterns:
        candidates.extend(
            path
            for path in data_dir.glob(item)
            if path.is_file() and not path.name.startswith("~$")
        )

    unique = sorted(set(candidates), key=lambda p: p.stat().st_mtime, reverse=True)
    if not unique:
        raise FileNotFoundError(f"未在 {data_dir} 找到良率报表 Excel 文件")
    return unique[0]


def load_source_rows(source_file: str | Path) -> pd.DataFrame:
    """Read source workbook and keep only data rows from repeated table sections."""
    raw = pd.read_excel(source_file, sheet_name=0, header=None)
    if raw.shape[1] <= max(SOURCE_INDEX.values()):
        raise ValueError(f"源文件列数不足，当前 {raw.shape[1]} 列，无法解析杰群良率格式")

    first_col = raw.iloc[:, 0].astype("string")
    row_mask = first_col.notna() & ~first_col.str.contains("Customer", na=False)
    data = raw.loc[row_mask].copy()
    data = data[data.iloc[:, SOURCE_INDEX["Test Input\n測試輸入數"]].notna()]

    rows = pd.DataFrame({name: data.iloc[:, idx] for name, idx in SOURCE_INDEX.items()})
    rows = rows.reset_index(drop=True)

    text_cols = [c for c in rows.columns if c not in {"PO Qty\n訂單數", "Test Input\n測試輸入數", "Test Output\n良品數"} | set(RATE_COLUMNS)]
    for col in text_cols:
        rows[col] = rows[col].map(clean_text)

    numeric_cols = ["PO Qty\n訂單數", "Test Input\n測試輸入數", "Test Output\n良品數", *RATE_COLUMNS]
    for col in numeric_cols:
        rows[col] = pd.to_numeric(rows[col], errors="coerce").fillna(0)

    rows = rows[rows["Test Input\n測試輸入數"] > 0].copy()
    if rows.empty:
        raise ValueError("源文件未解析到有效测试明细行")

    for col in RATE_COLUMNS:
        rows[col] = rows[col] / rows["Test Input\n測試輸入數"]

    return rows


def build_summary(rows: pd.DataFrame, config: YieldReportConfig | None = None) -> pd.DataFrame:
    """Build the summary sheet, one row per device + PO + wafer lot."""
    config = config or YieldReportConfig()
    base = rows.drop_duplicates(
        subset=["Device\n機種", "Wafer I.D.\n晶圓版本", "Wafer Lot\n晶圓批號", "PO No.\n訂單號碼"],
        keep="first",
    ).copy()

    summary = pd.DataFrame(
        {
            "产品名": base["Device\n機種"],
            "芯片名s": base["Wafer I.D.\n晶圓版本"],
            "批号": base["Wafer Lot\n晶圓批號"],
            "片数": config.wafer_count,
            "封装数量\n(Kpcs)": config.package_qty_kpcs,
            "PO": base["PO No.\n訂單號碼"],
            "周记": base["Date Code\n日期代碼"].map(to_week_code),
            "片号": config.wafer_no_text,
        }
    )
    return summary[SUMMARY_COLUMNS].reset_index(drop=True)


def build_analysis(rows: pd.DataFrame) -> pd.DataFrame:
    """Build SYL/SBL detail rows with yield formulas written later in Excel."""
    analysis = rows.copy()
    analysis["PO Sequ.\n訂單序號"] = analysis["PO Sequ.\n訂單序號"].map(lambda v: str(int(v)) if pd.notna(v) else "")
    analysis["Test yield\n電性良率"] = None
    return analysis[ANALYSIS_COLUMNS].reset_index(drop=True)


def write_report(
    summary: pd.DataFrame,
    analysis: pd.DataFrame,
    output_file: str | Path,
    overwrite: bool = True,
) -> Path:
    """Write the final two-sheet workbook."""
    output_file = Path(output_file)
    output_file.parent.mkdir(parents=True, exist_ok=True)
    if output_file.exists() and not overwrite:
        raise FileExistsError(f"输出文件已存在: {output_file}")

    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        summary.to_excel(writer, sheet_name="总", index=False)
        workbook = writer.book
        ws_sum = writer.sheets["总"]
        fmt_header = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter", "border": 1})
        fmt_text = workbook.add_format({"align": "center", "valign": "vcenter", "border": 1})
        fmt_qty = workbook.add_format({"num_format": "0.00", "align": "center", "valign": "vcenter", "border": 1})
        ws_sum.set_row(0, 30, fmt_header)
        widths = [26, 14, 12, 7, 18, 22, 10, 8]
        for idx, width in enumerate(widths):
            ws_sum.set_column(idx, idx, width, fmt_qty if idx == 4 else fmt_text)

        analysis.to_excel(writer, sheet_name="SYL&SBL", index=False, header=False, startrow=2)
        ws = writer.sheets["SYL&SBL"]
        fmt_pct = workbook.add_format({"num_format": "0.000%", "align": "center", "valign": "vcenter", "border": 1})
        fmt_int = workbook.add_format({"num_format": "0", "align": "center", "valign": "vcenter", "border": 1})
        fmt_analysis_header = workbook.add_format(
            {"bold": True, "align": "center", "valign": "vcenter", "border": 1, "text_wrap": True}
        )
        fmt_analysis_text = workbook.add_format({"align": "center", "valign": "vcenter", "border": 1})
        fmt_section = workbook.add_format({"bold": True, "align": "center", "valign": "vcenter"})
        fmt_label = workbook.add_format({"align": "center", "valign": "vcenter"})
        fmt_round = workbook.add_format({"num_format": "0.000", "align": "center", "valign": "vcenter"})
        fmt_syl_round = workbook.add_format({"num_format": "0.00", "align": "center", "valign": "vcenter"})

        ws.set_row(0, 42, fmt_analysis_header)
        ws.set_row(1, 8)
        for col in range(len(ANALYSIS_COLUMNS)):
            ws.merge_range(0, col, 1, col, ANALYSIS_COLUMNS[col], fmt_analysis_header)

        data_start = 2
        data_end = data_start + len(analysis) - 1
        for row in range(data_start, data_end + 1):
            excel_row = row + 1
            ws.write_formula(row, 13, f"=M{excel_row}/L{excel_row}", fmt_pct)
            for col in range(14, 26):
                ws.write_number(row, col, float(analysis.iloc[row - data_start, col]), fmt_pct)

        ws.set_column(0, 0, 12, fmt_analysis_text)
        ws.set_column(1, 1, 26, fmt_analysis_text)
        ws.set_column(2, 2, 16, fmt_analysis_text)
        ws.set_column(3, 3, 10, fmt_analysis_text)
        ws.set_column(4, 4, 22, fmt_analysis_text)
        ws.set_column(5, 5, 11, fmt_int)
        ws.set_column(6, 10, 16, fmt_analysis_text)
        ws.set_column(11, 12, 13, fmt_int)
        ws.set_column(13, 25, 11, fmt_pct)

        write_sigma_block(
            ws,
            data_start + len(analysis) + 2,
            "3Sigma",
            3,
            len(analysis),
            rounded_limits(analysis, 3),
            fmt_section,
            fmt_label,
            fmt_pct,
            fmt_round,
            fmt_syl_round,
        )
        write_sigma_block(
            ws,
            data_start + len(analysis) + 9,
            "4Sigma",
            4,
            len(analysis),
            rounded_limits(analysis, 4),
            fmt_section,
            fmt_label,
            fmt_pct,
            fmt_round,
            fmt_syl_round,
        )
        ws.freeze_panes(2, 0)

    return output_file


def write_sigma_block(
    ws,
    top_row: int,
    title: str,
    sigma: int,
    row_count: int,
    limit_values: list[float],
    fmt_section,
    fmt_label,
    fmt_pct,
    fmt_round,
    fmt_syl_round,
) -> None:
    """Write one Sigma summary block. top_row is zero-based."""
    first_excel = 3
    last_excel = first_excel + row_count - 1
    metric_headers = ["良率", "LV", "DVDS", "SHORT", "BVDSS", "IGSS", "IDSS", "RG", "VTH,VFSD", "RDON", "CONT", "OPEN", "Lead"]
    ws.write(top_row, 11, title, fmt_section)
    for offset, header in enumerate(metric_headers):
        ws.write(top_row, 13 + offset, header, fmt_section)

    ws.write(top_row + 1, 12, "均值", fmt_label)
    ws.write(top_row + 2, 12, "标准差", fmt_label)
    ws.write(top_row + 3, 12, "SYL", fmt_label)
    ws.write(top_row + 4, 12, "SBL", fmt_label)

    for col in range(13, 26):
        letter = excel_col(col)
        ws.write_formula(top_row + 1, col, f"=AVERAGE({letter}{first_excel}:{letter}{last_excel})", fmt_pct)
        ws.write_formula(top_row + 2, col, f"=STDEV({letter}{first_excel}:{letter}{last_excel})", fmt_pct)

    ws.write_formula(top_row + 3, 13, f"=N{top_row + 2}-{sigma}*N{top_row + 3}", fmt_pct)
    for col in range(14, 26):
        letter = excel_col(col)
        ws.write_formula(top_row + 4, col, f"={letter}{top_row + 2}+{sigma}*{letter}{top_row + 3}", fmt_pct)

    ws.write_number(top_row + 5, 13, limit_values[0], fmt_syl_round)
    for idx, col in enumerate(range(14, 26), start=1):
        ws.write_number(top_row + 5, col, limit_values[idx], fmt_round)


def rounded_limits(analysis: pd.DataFrame, sigma: int) -> list[float]:
    """Return rounded SYL/SBL control limits matching Jiequn's workbook convention."""
    metrics = pd.DataFrame({"yield": analysis["Test Output\n良品數"] / analysis["Test Input\n測試輸入數"]})
    for col in RATE_COLUMNS:
        metrics[col] = pd.to_numeric(analysis[col], errors="coerce")

    means = metrics.mean()
    stds = metrics.std(ddof=1)
    values = [floor_to(float(means.iloc[0] - sigma * stds.iloc[0]), 0.01)]
    values.extend(ceil_to(float(means.iloc[i] + sigma * stds.iloc[i]), 0.001) for i in range(1, len(metrics.columns)))
    return values


def floor_to(value: float, step: float) -> float:
    return round(math.floor((value + 1e-12) / step) * step, 12)


def ceil_to(value: float, step: float) -> float:
    return round(math.ceil((value - 1e-12) / step) * step, 12)


def generate_report(
    data_dir: str | Path = "data",
    output_dir: str | Path = "output",
    source_file: str | Path | None = None,
    output_file: str | Path | None = None,
    config: YieldReportConfig | None = None,
) -> Path:
    """Generate a Jiequn yield report from source export."""
    source = Path(source_file) if source_file else find_source_file(data_dir)
    rows = load_source_rows(source)
    summary = build_summary(rows, config)
    analysis = build_analysis(rows)
    target = Path(output_file) if output_file else sequenced_output_path(output_dir, default_output_name(summary))
    return write_report(summary, analysis, target)


def default_output_name(summary: pd.DataFrame) -> str:
    product = product_family_name(summary["产品名"].dropna().astype(str).tolist())
    return f"{product} JQ SYL&SBL.xlsx"


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


def product_family_name(devices: Iterable[str]) -> str:
    unique = [device for device in dict.fromkeys(devices) if device]
    if not unique:
        return "JQ"
    if len(unique) == 1:
        return unique[0]
    match = re.match(r"^(.*-1J)", unique[0])
    if match and all(item.startswith(match.group(1)) for item in unique):
        return f"{match.group(1)}XX"
    return f"{common_prefix(unique).rstrip('-_ ')}XX"


def to_week_code(date_code: object) -> str:
    text = clean_text(date_code)
    return f"{text[:5]}XX" if len(text) >= 5 else text


def clean_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).replace("\xa0", " ").strip()
    if re.fullmatch(r"\d+\.0", text):
        return text[:-2]
    return text


def common_prefix(values: list[str]) -> str:
    if not values:
        return ""
    prefix = values[0]
    for value in values[1:]:
        while not value.startswith(prefix) and prefix:
            prefix = prefix[:-1]
    return prefix


def excel_col(zero_based_col: int) -> str:
    n = zero_based_col + 1
    letters = ""
    while n:
        n, remainder = divmod(n - 1, 26)
        letters = chr(65 + remainder) + letters
    return letters


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="生成杰群良率汇总和 SYL/SBL 分析报表")
    parser.add_argument("--data-dir", default="data", help="良率源数据目录，默认 data")
    parser.add_argument("--output-dir", default="output", help="输出目录，默认 output")
    parser.add_argument("--source-file", help="指定源 Excel 文件；不指定时自动扫描 data-dir")
    parser.add_argument("--output-file", help="指定输出 xlsx 文件；不指定时按产品自动命名")
    parser.add_argument("--wafer-count", type=int, default=25, help="汇总 sheet 的片数，默认 25")
    parser.add_argument("--kpcs-per-wafer", type=float, default=3.35, help="每片封装数量(Kpcs)，默认 3.35")
    args = parser.parse_args(argv)

    config = YieldReportConfig(wafer_count=args.wafer_count, kpcs_per_wafer=args.kpcs_per_wafer)
    output = generate_report(
        data_dir=args.data_dir,
        output_dir=args.output_dir,
        source_file=args.source_file,
        output_file=args.output_file,
        config=config,
    )
    print(f"已生成: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
