"""
杰群 · 数据格式2 — 单文件格式清洗器

从单个 CSV 中提取 DC+DVDS+RG 全部参数，一次输出三个 Excel 文件。
适用场景：杰群厂线B，所有参数在同一个 CSV 文件中。
"""
import sys
sys.path.insert(0, '.')
from pathlib import Path
from factories.jiequn.csv_parser import parse_dta_csv
from factories.jiequn.formatting import BATCH_COL, LEGACY_BATCH_COL
from shared.excel_utils import write_excel_fast, generate_lot_based_filename
import pandas as pd

NUM_CONV = {"IDSS": 1e9, "IGSS": 1e9, "ISGS": 1e9, "RDON": 1000, "LRDON": 1000, "DVDS": 1000}

DC_PARAMS = [
    "LCR-RG",
    "VTH",
    "BVDSS",
    "IDSS",
    "ISGS",
    "RDON",
    "VFSDS",
    "DELAY",
    "ABSDEL",
]

def apply_conv(df):
    for col in df.columns:
        if col in ('周记', 'NUM'): continue
        for pn, factor in NUM_CONV.items():
            if pn.upper() in col.upper():
                df[col] = pd.to_numeric(df[col], errors='coerce') * factor; break
    return df

TYPES = [
    ("DC",   DC_PARAMS, False),
    ("DVDS", ["DVDS"], True),
    ("RG",   ["LCR-RG"], True),
]

def run(input_dir, output_dir):
    inp, out = Path(input_dir), Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(inp.glob("*DTA.CSV"))
    print(f"文件: {len(files)}")
    success = False
    for label, params, unique in TYPES:
        dfs = [
            parse_dta_csv(
                str(f),
                params,
                unique_only=unique,
                preserve_source_order=True,
                skip_match_counts={"VTH": 1} if label == "DC" else None,
            )
            for f in files
        ]
        dfs = [d for d in dfs if d is not None and not d.empty]
        if not dfs: print(f"{label}: 无数据"); continue
        merged = pd.concat(dfs, ignore_index=True, sort=False)
        merged = apply_conv(merged)
        merged.dropna(subset=["周记"], inplace=True)
        if label == "DVDS":
            before = len(merged)
            value_cols = [c for c in merged.columns if c != "周记"]
            merged.dropna(subset=value_cols, how="all", inplace=True)
            removed = before - len(merged)
            if removed:
                print(f"{label}: 已删除空值记录 {removed:,} 行")
        merged.reset_index(drop=True, inplace=True)
        merged.insert(0, "NUM", range(1, len(merged)+1))
        merged = _normalize_unified_columns(merged)
        fname = generate_lot_based_filename(merged[BATCH_COL].tolist(), f"{label}_JQ2")
        write_excel_fast(merged, out / fname, sheet_name=f"{label}_Data")
        print(f"{label}: {len(merged):,} 行 -> {fname}")
        success = True
    return success


def _normalize_unified_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Keep Jiequn2 parameter columns in source CSV order and expose 批次."""
    df = df.rename(columns={LEGACY_BATCH_COL: BATCH_COL})
    front = [c for c in ("NUM", BATCH_COL) if c in df.columns]
    rest = [c for c in df.columns if c not in front]
    return df[front + rest]

if __name__ == "__main__":
    import sys as _s
    inp = _s.argv[1] if len(_s.argv) > 1 else "data/杰群2/RAW"
    out = _s.argv[2] if len(_s.argv) > 2 else "output/杰群2"
    run(inp, out)
