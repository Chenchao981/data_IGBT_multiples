#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Detect Jiequn's three DC layouts and dispatch the matching cleaner.

``DC-AI`` is intentionally deterministic: it inspects directory structure and
the DTA ``Item`` header only.  It never reads measurement rows during format
detection and refuses mixed or incomplete layouts instead of guessing.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from factories.jiequn.clean_unified import run as run_unified
from factories.jiequn.config import JIEQUN_DC_PARAMS
from factories.jiequn.csv_parser import _item_matches_param, read_header_info
from factories.jiequn.dc_cleaner import JiequnDCCleaner


DC_FORMAT_1 = "DC-1"
DC_FORMAT_UNIFIED = "DC-统一CSV"
DC_FORMAT_3 = "DC-3"

_DC_SIGNAL_PARAMS = tuple(param for param in JIEQUN_DC_PARAMS if param != "LCR-RG")
_OTHER_TYPE_DIRS = {"DVDS", "RG"}


class DCFormatDetectionError(ValueError):
    """Raised when a directory cannot be mapped safely to one DC format."""


@dataclass(frozen=True)
class DCFormatDetection:
    """Result of a DC-AI header and directory-structure inspection."""

    format_name: str
    source_dir: Path
    files: tuple[Path, ...]
    reason: str

    @property
    def file_count(self) -> int:
        return len(self.files)


def _scan_dta_csv_files(input_dir: Path) -> list[Path]:
    return sorted(
        (
            path
            for path in input_dir.rglob("*")
            if path.is_file()
            and path.suffix.lower() == ".csv"
            and "DTA" in path.name.upper()
            and not path.name.startswith("~$")
        ),
        key=lambda path: str(path).lower(),
    )


def _directory_names(input_dir: Path, file_path: Path) -> set[str]:
    relative_dirs = file_path.relative_to(input_dir).parts[:-1]
    return {input_dir.name.upper(), *(part.upper() for part in relative_dirs)}


def _is_auxiliary_type_file(input_dir: Path, file_path: Path) -> bool:
    name = file_path.name.upper()
    return (
        bool(_directory_names(input_dir, file_path) & _OTHER_TYPE_DIRS)
        or "_DVDS" in name
        or "_RG" in name
        or "PAT" in name
    )


def _has_param(item_names: Iterable[str], target_param: str) -> bool:
    return any(name and _item_matches_param(name, target_param) for name in item_names)


def _classify_flat_file(file_path: Path) -> str:
    info = read_header_info(str(file_path))
    item_names = info.get("item_names") or []
    if not item_names:
        raise DCFormatDetectionError(f"文件缺少 Item 头部，无法判断: {file_path}")

    has_dc = any(_has_param(item_names, param) for param in _DC_SIGNAL_PARAMS)
    has_dvds = _has_param(item_names, "DVDS")
    has_rg = _has_param(item_names, "LCR-RG")

    if not has_dc:
        raise DCFormatDetectionError(f"Item 行未发现杰群 DC 参数: {file_path}")
    if has_dvds and has_rg:
        return DC_FORMAT_UNIFIED
    if has_dvds and not has_rg:
        raise DCFormatDetectionError(
            f"文件含 DVDS 但缺少 LCR-RG，不能安全归类为统一CSV: {file_path}"
        )
    return DC_FORMAT_3


def _validate_classic_dc_files(files: Iterable[Path]) -> None:
    for file_path in files:
        info = read_header_info(str(file_path))
        item_names = info.get("item_names") or []
        if not item_names:
            raise DCFormatDetectionError(f"DC-1 文件缺少 Item 头部: {file_path}")
        if not any(_has_param(item_names, param) for param in _DC_SIGNAL_PARAMS):
            raise DCFormatDetectionError(f"DC-1 目录中的文件未发现 DC 参数: {file_path}")


def detect_dc_format(input_dir: str | Path) -> DCFormatDetection:
    """Detect DC-1, DC-unified, or DC-3 from a user-selected directory."""

    base = Path(input_dir).expanduser()
    if not base.is_dir():
        raise DCFormatDetectionError(f"输入目录不存在或不是文件夹: {base}")

    all_files = _scan_dta_csv_files(base)
    if not all_files:
        raise DCFormatDetectionError(f"未找到文件名含 DTA 的 CSV: {base}")

    classic_files = [
        file_path
        for file_path in all_files
        if "DC" in _directory_names(base, file_path)
    ]
    flat_files = [
        file_path
        for file_path in all_files
        if "DC" not in _directory_names(base, file_path)
        and not _is_auxiliary_type_file(base, file_path)
    ]

    if classic_files and flat_files:
        raise DCFormatDetectionError(
            "同一输入目录同时存在 DC-1 的 DC 子目录文件和其他平铺 DTA 文件；"
            "请分别选择单一格式目录。"
        )

    if classic_files:
        _validate_classic_dc_files(classic_files)
        return DCFormatDetection(
            format_name=DC_FORMAT_1,
            source_dir=base,
            files=tuple(classic_files),
            reason=f"发现名为 DC 的分类型目录，共 {len(classic_files)} 个 DC DTA CSV",
        )

    if not flat_files:
        raise DCFormatDetectionError(f"未找到可用于 DC 判断的 DTA CSV: {base}")

    classified: dict[str, list[Path]] = {}
    for file_path in flat_files:
        format_name = _classify_flat_file(file_path)
        classified.setdefault(format_name, []).append(file_path)

    if len(classified) != 1:
        counts = ", ".join(f"{name}={len(files)}" for name, files in sorted(classified.items()))
        raise DCFormatDetectionError(
            f"同一输入目录检测到多种杰群 DC 格式（{counts}）；请拆分目录后再清洗。"
        )

    format_name = next(iter(classified))
    detected_files = tuple(classified[format_name])
    if format_name == DC_FORMAT_UNIFIED:
        parents = {file_path.parent for file_path in detected_files}
        if len(parents) != 1:
            raise DCFormatDetectionError(
                "统一CSV分布在多个子目录，现有统一CSV清洗器要求文件位于同一目录；"
                "请直接选择对应 RAW 目录。"
            )
        source_dir = next(iter(parents))
        reason = (
            f"Item 行同时包含 DC、DVDS 和 LCR-RG，共 {len(detected_files)} 个统一 DTA CSV"
        )
    else:
        source_dir = base
        reason = (
            f"未发现 DC 分类型目录，Item 行包含 DC 参数且不含 DVDS，"
            f"共 {len(detected_files)} 个平铺/产品目录 DTA CSV"
        )

    return DCFormatDetection(
        format_name=format_name,
        source_dir=source_dir,
        files=detected_files,
        reason=reason,
    )


def run_auto_dc(input_dir: str | Path, output_dir: str | Path) -> bool:
    """Detect the input format, log the evidence, and run its cleaner."""

    detection = detect_dc_format(input_dir)
    print("=" * 60)
    print(f"DC-AI 识别结果: {detection.format_name}")
    print(f"识别依据: {detection.reason}")
    print(f"清洗输入: {detection.source_dir}")
    print("=" * 60)

    if detection.format_name == DC_FORMAT_UNIFIED:
        return bool(run_unified(detection.source_dir, output_dir))

    return bool(
        JiequnDCCleaner(
            input_dir=detection.source_dir,
            output_dir=output_dir,
        ).process_all()
    )


if __name__ == "__main__":
    import sys

    source = sys.argv[1] if len(sys.argv) > 1 else "data/杰群"
    target = sys.argv[2] if len(sys.argv) > 2 else "output/杰群-output"
    raise SystemExit(0 if run_auto_dc(source, target) else 1)
