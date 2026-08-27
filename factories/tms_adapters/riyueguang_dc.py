"""Independent Riyueguang FT DC adapter for the TMS formal-import route."""

from __future__ import annotations

import tempfile
from pathlib import Path

from factories.riyuexin.dc_cleaner import DCDataCleaner
from shared.excel_utils import read_excel_fast

from .identity import parse_riyueguang_dc_filename
from .workbook_profile import rewrite_manifest_factory, validate_dc_workbook


class RiyueguangTmsDCCleaner(DCDataCleaner):
    """Normalize the approved Time/Unit header in a temporary copy only."""

    @staticmethod
    def _source_id(file_path: Path) -> str:
        parse_riyueguang_dc_filename(file_path)
        return file_path.stem

    def extract_dc_data(self, file_path: Path):
        identity = parse_riyueguang_dc_filename(file_path)
        validate_dc_workbook(
            file_path,
            factory_name="日月光",
            unit_row_index=7,
            test_no_row_index=14,
            time_row_index=6,
        )
        source_key = file_path.resolve()
        frame = read_excel_fast(file_path, header=None)
        normalized = frame.drop(index=6).reset_index(drop=True)
        with tempfile.TemporaryDirectory(prefix="tms_riyueguang_dc_") as temporary:
            normalized_path = Path(temporary) / file_path.name
            normalized.to_excel(
                normalized_path,
                index=False,
                header=False,
                sheet_name="Test Data",
                engine="xlsxwriter",
            )
            result = super().extract_dc_data(normalized_path)
            normalized_key = normalized_path.resolve()
            specs = self._parsed_specs.pop(normalized_key, None)
            source_id = self._parsed_source_ids.pop(normalized_key, None)
        if specs is not None:
            self._parsed_specs[source_key] = specs
        if source_id is not None:
            self._parsed_source_ids[source_key] = source_id
        if result is not None and not result.empty:
            lots = set(result["lot_ID"].astype(str).str.upper())
            if lots != {identity.lot_id}:
                raise ValueError(
                    f"日月光 FT DC Lot 对账失败: 文件={identity.lot_id}, 输出={sorted(lots)}"
                )
        return result

    def process_all_dc_files(self) -> bool:
        success = super().process_all_dc_files()
        if success:
            rewrite_manifest_factory(
                self.last_scatter_manifest, code="RIYUEGUANG", name="日月光"
            )
        return success
