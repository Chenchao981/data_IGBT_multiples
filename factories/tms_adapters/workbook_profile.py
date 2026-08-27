"""Fail-closed workbook signatures for TMS FT DC adapters."""

from __future__ import annotations

from pathlib import Path

from openpyxl import load_workbook


def _row_values(rows: list[tuple[object, ...]], row_index: int) -> set[str]:
    if row_index >= len(rows):
        return set()
    return {
        str(value).strip()
        for value in rows[row_index]
        if value is not None and str(value).strip()
    }


def validate_dc_workbook(
    file_path: str | Path,
    *,
    factory_name: str,
    unit_row_index: int,
    test_no_row_index: int,
    time_row_index: int | None,
) -> None:
    """Validate the exact header rows without loading measurement rows."""
    path = Path(file_path)
    if path.suffix.lower() != ".xlsx":
        raise ValueError(f"{factory_name} FT DC 只支持 XLSX: {path.name}")
    workbook = load_workbook(path, read_only=True, data_only=True)
    try:
        if workbook.sheetnames != ["Test Data"]:
            raise ValueError(
                f"{factory_name} FT DC 工作表必须且只能是 Test Data: {path.name}"
            )
        worksheet = workbook["Test Data"]
        max_row = max(test_no_row_index, unit_row_index, time_row_index or 0) + 1
        rows = list(
            worksheet.iter_rows(min_row=1, max_row=max_row, values_only=True)
        )
    finally:
        workbook.close()

    item_row = _row_values(rows, 1)
    if "Item" not in item_row or "CONT" not in item_row:
        raise ValueError(f"{factory_name} FT DC 第2行缺少 Item/CONT: {path.name}")
    if "Unit" not in _row_values(rows, unit_row_index):
        raise ValueError(
            f"{factory_name} FT DC Unit 行应为第{unit_row_index + 1}行: {path.name}"
        )
    test_row = _row_values(rows, test_no_row_index)
    if not ({"Test No.", "Test No"} & test_row):
        raise ValueError(
            f"{factory_name} FT DC Test No. 行应为第{test_no_row_index + 1}行: {path.name}"
        )
    if time_row_index is not None and "Time" not in _row_values(rows, time_row_index):
        raise ValueError(
            f"{factory_name} FT DC Time 行应为第{time_row_index + 1}行: {path.name}"
        )


def rewrite_manifest_factory(manifest_path: Path | None, *, code: str, name: str) -> None:
    """Correct the portable bundle identity produced by the mature base Cleaner."""
    if manifest_path is None or not manifest_path.is_file():
        raise ValueError(f"{name} FT DC 未生成散点图清单")
    import json

    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["factory"] = name
    payload["factory_code"] = code
    manifest_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
