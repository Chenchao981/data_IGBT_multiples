"""
杰群 · 数据格式2 — 单文件格式清洗器

从单个 CSV 中提取 DC+DVDS+RG 全部参数，一次输出三个 Excel 文件。
适用场景：杰群厂线B，所有参数在同一个 CSV 文件中。
"""
import sys
sys.path.insert(0, '.')
from dataclasses import dataclass
from pathlib import Path
from typing import Optional
from factories.jiequn.config import JIEQUN_DC_PARAMS, JIEQUN_DC_SKIP_MATCH_COUNTS
from factories.jiequn.csv_parser import parse_dta_csv
from factories.jiequn.formatting import BATCH_COL, LEGACY_BATCH_COL
from shared.excel_utils import create_output_run_dir, generate_run_filename, write_excel_fast
import pandas as pd

NUM_CONV = {"IDSS": 1e9, "IGSS": 1e9, "ISGS": 1e9, "RDON": 1000, "LRDON": 1000, "DVDS": 1000}

DC_PARAMS = JIEQUN_DC_PARAMS

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


@dataclass(frozen=True)
class UnifiedRunResult:
    success: bool
    output_file: Optional[Path] = None
    scatter_manifest: Optional[Path] = None

    def __bool__(self):
        return self.success


def run_with_result(input_dir, output_dir) -> UnifiedRunResult:
    inp, out = Path(input_dir), Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    files = sorted(inp.glob("*DTA.CSV"))
    print(f"文件: {len(files)}")
    success = False
    run_dir = None
    dc_output_file = None
    scatter_manifest = None
    for label, params, unique in TYPES:
        dfs = []
        spec_frames = []
        for f in files:
            df = parse_dta_csv(
                str(f),
                params,
                unique_only=unique,
                preserve_source_order=True,
                skip_match_counts=JIEQUN_DC_SKIP_MATCH_COUNTS if label == "DC" else None,
                spec_unit_factors=NUM_CONV if label == "DC" else None,
            )
            if df is not None and not df.empty:
                if label == "DC":
                    specs = df.attrs.get("scatter_specs")
                    if specs is not None and not specs.empty:
                        spec_frames.append(specs)
                    source_id = df.attrs.get("source_id", f.stem)
                    df = df.copy()
                    df["_source_id"] = source_id
                dfs.append(df)
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
        source_ids = merged.pop("_source_id") if label == "DC" else None
        merged.insert(0, "NUM", range(1, len(merged)+1))
        merged = _normalize_unified_columns(merged)
        if run_dir is None:
            run_dir = create_output_run_dir(out, merged[BATCH_COL].tolist())
        fname = generate_run_filename(run_dir, label)
        output_file = run_dir / fname
        if not write_excel_fast(merged, output_file, sheet_name=f"{label}_Data"):
            raise OSError(f"杰群统一CSV {label} 清洗结果写入失败: {output_file}")
        if label == "DC":
            if not spec_frames:
                raise ValueError("没有从杰群统一CSV读取到 DC 参数上下限")
            from frontend.ft_scatter import export_scatter_bundle

            scatter_data = merged.rename(columns={BATCH_COL: "lot_ID"}).copy()
            scatter_data.insert(2, "Source_ID", source_ids.astype(str).tolist())
            specs = pd.concat(spec_frames, ignore_index=True, sort=False)
            dc_output_file = output_file.resolve()
            scatter_manifest = export_scatter_bundle(
                scatter_data,
                specs,
                run_dir,
                cleaned_file=dc_output_file,
                factory="杰群",
                data_type="DC",
            ).resolve()
        print(f"{label}: {len(merged):,} 行 -> {fname}")
        success = True
    return UnifiedRunResult(success, dc_output_file, scatter_manifest)


def run(input_dir, output_dir):
    """Backward-compatible boolean entry point."""
    return bool(run_with_result(input_dir, output_dir))


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
