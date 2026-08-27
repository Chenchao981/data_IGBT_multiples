"""Strict TMS adapter around the stable Riyuexin DC Cleaner."""

from __future__ import annotations

from pathlib import Path

from factories.riyuexin.dc_cleaner import DCDataCleaner

from .identity import parse_riyuexin_dc_filename
from .workbook_profile import rewrite_manifest_factory, validate_dc_workbook


class RiyuexinTmsDCCleaner(DCDataCleaner):
    """Keep mature calculations while enforcing Riyuexin identity and layout."""

    @staticmethod
    def _source_id(file_path: Path) -> str:
        parse_riyuexin_dc_filename(file_path)
        return file_path.stem

    def extract_dc_data(self, file_path: Path):
        identity = parse_riyuexin_dc_filename(file_path)
        validate_dc_workbook(
            file_path,
            factory_name="日月新",
            unit_row_index=6,
            test_no_row_index=18,
            time_row_index=None,
        )
        result = super().extract_dc_data(file_path)
        if result is not None and not result.empty:
            lots = set(result["lot_ID"].astype(str).str.upper())
            if lots != {identity.lot_id}:
                raise ValueError(
                    f"日月新 FT DC Lot 对账失败: 文件={identity.lot_id}, 输出={sorted(lots)}"
                )
        return result

    def process_all_dc_files(self) -> bool:
        success = super().process_all_dc_files()
        if success:
            rewrite_manifest_factory(
                self.last_scatter_manifest, code="RIYUEXIN", name="日月新"
            )
        return success
