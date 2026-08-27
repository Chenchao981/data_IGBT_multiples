"""Strict TMS adapter around the stable Riyuexin DC Cleaner."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

from factories.riyuexin.dc_cleaner import DCDataCleaner
from shared.excel_utils import scan_excel_files

from .identity import LotOverrideRequired, parse_riyuexin_dc_filename
from .workbook_profile import (
    rewrite_manifest_factory,
    validate_complete_source_coverage,
    validate_dc_workbook,
)


class RiyuexinTmsDCCleaner(DCDataCleaner):
    """Keep mature calculations while enforcing Riyuexin identity and layout."""

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
        return parse_riyuexin_dc_filename(
            file_path, lot_override=self._lot_override(file_path)
        )

    def _source_id(self, file_path: Path) -> str:
        self._identity(file_path)
        return file_path.stem

    def extract_dc_data(self, file_path: Path):
        identity = self._identity(file_path)
        validate_dc_workbook(
            file_path,
            factory_name="日月新",
            unit_row_index=6,
            test_no_row_index=18,
            time_row_index=None,
        )
        result = super().extract_dc_data(file_path)
        if result is not None and not result.empty:
            result = result.copy()
            result.loc[:, "lot_ID"] = identity.lot_id
            specs = self._parsed_specs.get(file_path.resolve())
            if specs is not None:
                specs.loc[:, "lot_ID"] = identity.lot_id
            lots = set(result["lot_ID"].astype(str).str.upper())
            if lots != {identity.lot_id}:
                raise ValueError(
                    f"日月新 FT DC Lot 对账失败: 文件={identity.lot_id}, 输出={sorted(lots)}"
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
                factory_name="日月新",
            )
            rewrite_manifest_factory(
                self.last_scatter_manifest, code="RIYUEXIN", name="日月新"
            )
        return success
