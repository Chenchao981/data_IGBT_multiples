"""Independent Riyueguang FT DC adapter for the TMS formal-import route."""

from __future__ import annotations

import tempfile
from collections.abc import Mapping
from pathlib import Path

from factories.riyuexin.dc_cleaner import DCDataCleaner
from shared.excel_utils import read_excel_fast, scan_excel_files

from .identity import LotOverrideRequired, parse_riyueguang_dc_filename
from .workbook_profile import (
    rewrite_manifest_factory,
    validate_complete_source_coverage,
    validate_dc_workbook,
)


class RiyueguangTmsDCCleaner(DCDataCleaner):
    """Normalize the approved Time/Unit header in a temporary copy only."""

    def __init__(
        self,
        input_dir: str | Path,
        output_dir: str | Path,
        *,
        lot_overrides: Mapping[str, str] | None = None,
    ) -> None:
        self._lot_overrides = {
            Path(name).name.casefold(): str(value).strip()
            for name, value in (lot_overrides or {}).items()
        }
        super().__init__(str(input_dir), str(output_dir))

    def _lot_override(self, file_path: Path) -> str | None:
        return self._lot_overrides.get(file_path.name.casefold())

    def _identity(self, file_path: Path):
        return parse_riyueguang_dc_filename(
            file_path, lot_override=self._lot_override(file_path)
        )

    def _source_id(self, file_path: Path) -> str:
        self._identity(file_path)
        return file_path.stem

    def extract_dc_data(self, file_path: Path):
        identity = self._identity(file_path)
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
            specs.loc[:, "lot_ID"] = identity.lot_id
            self._parsed_specs[source_key] = specs
        if source_id is not None:
            self._parsed_source_ids[source_key] = source_id
        if result is not None and not result.empty:
            result = result.copy()
            result.loc[:, "lot_ID"] = identity.lot_id
            lots = set(result["lot_ID"].astype(str).str.upper())
            if lots != {identity.lot_id}:
                raise ValueError(
                    f"日月光 FT DC Lot 对账失败: 文件={identity.lot_id}, 输出={sorted(lots)}"
                )
        return result

    def process_all_dc_files(self) -> bool:
        missing: list[str] = []
        source_files = tuple(scan_excel_files(self.input_dir))
        for file_path in source_files:
            try:
                self._identity(file_path)
            except LotOverrideRequired as exc:
                missing.extend(exc.file_names)
        if missing:
            raise LotOverrideRequired(missing)
        success = super().process_all_dc_files()
        if success:
            validate_complete_source_coverage(
                self.last_scatter_manifest,
                expected_sources={path.stem for path in source_files},
                factory_name="日月光",
            )
            rewrite_manifest_factory(
                self.last_scatter_manifest, code="RIYUEGUANG", name="日月光"
            )
        return success
