"""集佳 PAT：直接读取严格校验后的 STS8203 原始 CSV。"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from factories.jiequn.pat_cleaner import save_pat
from factories.jijia.dc_cleaner import JijiaFTCleaner
from factories.jijia.parser import parse_jijia_file
from shared.pat_engine import RawPatGroup, build_spooled_raw_pat


def build_raw_pat(
    source_dir: str | Path,
    spool_dir: str | Path | None = None,
    progress_interval: int = 25,
) -> pd.DataFrame:
    """逐文件解析集佳原始 CSV，并使用 FT 统一公式计算精确 PAT。"""

    source = Path(source_dir).expanduser().resolve()
    files = tuple(JijiaFTCleaner(source, source).scan_source_files())

    def extract(path: Path) -> pd.DataFrame:
        return parse_jijia_file(path).data

    return build_spooled_raw_pat(
        (RawPatGroup("DC", files, extract),),
        spool_dir=spool_dir,
        progress_interval=progress_interval,
        factory_label="集佳",
    )


def generate_raw_pat(
    source_dir: str | Path,
    output_dir: str | Path = "output/集佳-output",
) -> Path | None:
    """从集佳原始 CSV 目录直接生成 PAT 报表。"""

    return save_pat(
        build_raw_pat(source_dir, spool_dir=output_dir),
        output_dir,
    )
