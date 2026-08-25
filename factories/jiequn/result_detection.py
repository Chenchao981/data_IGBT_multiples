"""Detect an already-cleaned Jiequn specialized result directory safely."""

from pathlib import Path

import pandas as pd


def _sheet_names(path: Path) -> list[str]:
    try:
        with pd.ExcelFile(path, engine="calamine") as workbook:
            return list(workbook.sheet_names)
    except Exception:
        with pd.ExcelFile(path, engine="openpyxl") as workbook:
            return list(workbook.sheet_names)


def find_existing_specialized_result(
    input_dir: str | Path,
    label: str,
) -> Path | None:
    """Return one existing ``<LABEL>_Data`` workbook or reject ambiguity."""
    base = Path(input_dir).expanduser()
    if not base.is_dir():
        return None

    expected_sheet = f"{label.upper()}_Data"
    matches: list[Path] = []
    for path in sorted(base.glob("*.xlsx"), key=lambda item: item.name.lower()):
        if path.name.startswith("~$"):
            continue
        try:
            if expected_sheet in _sheet_names(path):
                matches.append(path.resolve())
        except Exception:
            continue

    if len(matches) > 1:
        rendered = ", ".join(path.name for path in matches)
        raise ValueError(
            f"目录中存在多个 {expected_sheet} 工作簿，不能确定使用哪一个: {rendered}"
        )
    return matches[0] if matches else None
