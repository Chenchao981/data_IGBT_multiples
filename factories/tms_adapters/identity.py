"""Approved filename identities for the Riyuexin and Riyueguang FT DC routes."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


_LOT = r"[A-Z0-9]{4}-\d{4}"
_SOURCE = r"NCT\d+"
_SOURCE_FIRST = re.compile(
    rf"^(?P<source>{_SOURCE})_(?P<product>.+)_(?P<lot>{_LOT})_"
    r"(?P<date>\d{8})_(?P<time>\d{6})$",
    re.IGNORECASE,
)
_RIYUEXIN_PRODUCT_FIRST = re.compile(
    rf"^(?P<product>.+)_(?P<lot>{_LOT})_(?P<source>{_SOURCE})_DC_"
    r"(?P<timestamp>\d{12,14})$",
    re.IGNORECASE,
)
_APPROVED_PRODUCT = r"NCE[A-Z0-9()\-]+"
_SOURCE_FIRST_MISSING_LOT = re.compile(
    rf"^(?P<source>{_SOURCE})_(?P<product>{_APPROVED_PRODUCT})_"
    r"(?P<date>\d{8})_(?P<time>\d{6})$",
    re.IGNORECASE,
)
_RIYUEXIN_PRODUCT_FIRST_MISSING_LOT = re.compile(
    rf"^(?P<product>{_APPROVED_PRODUCT})_(?P<source>{_SOURCE})_DC_"
    r"(?P<timestamp>\d{12,14})$",
    re.IGNORECASE,
)
_LOT_FULL = re.compile(rf"^{_LOT}$", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class FtFileIdentity:
    source_id: str
    product: str
    lot_id: str
    layout: str


class LotOverrideRequired(ValueError):
    """Signal that an approved filename profile is missing only the business Lot."""

    def __init__(self, file_names: list[str] | tuple[str, ...]) -> None:
        self.file_names = tuple(dict.fromkeys(file_names))
        super().__init__(
            "以下 FT 文件符合已批准布局，但缺少批次号: "
            + ", ".join(self.file_names)
        )


def normalize_lot_override(value: str) -> str:
    """Validate a manual Lot against the approved Riyuexin/Riyueguang contract."""
    lot_id = value.strip().upper()
    if not _LOT_FULL.fullmatch(lot_id):
        raise ValueError(f"人工批次号不符合当前厂家已批准格式: {value!r}")
    return lot_id


def _from_match(
    match: re.Match[str], layout: str, *, lot_override: str | None = None
) -> FtFileIdentity:
    return FtFileIdentity(
        source_id=match.group("source").upper(),
        product=match.group("product").strip(),
        lot_id=(lot_override or match.group("lot")).upper(),
        layout=layout,
    )


def _with_optional_override(
    match: re.Match[str], layout: str, lot_override: str | None
) -> FtFileIdentity:
    identity = _from_match(match, layout)
    if lot_override is None:
        return identity
    normalized = normalize_lot_override(lot_override)
    if normalized != identity.lot_id:
        raise ValueError(
            "人工批次号与文件中已识别批次号冲突: "
            f"文件={identity.lot_id}, 人工={normalized}"
        )
    return identity


def _missing_lot_identity(
    match: re.Match[str] | None,
    layout: str,
    file_path: str | Path,
    lot_override: str | None,
) -> FtFileIdentity | None:
    if match is None:
        return None
    if lot_override is None:
        raise LotOverrideRequired([Path(file_path).name])
    return _from_match(
        match,
        layout,
        lot_override=normalize_lot_override(lot_override),
    )


def parse_riyuexin_dc_filename(
    file_path: str | Path, *, lot_override: str | None = None
) -> FtFileIdentity:
    """Parse either of the two approved Riyuexin DC filename directions."""
    stem = Path(file_path).stem
    match = _SOURCE_FIRST.fullmatch(stem)
    if match:
        return _with_optional_override(match, "SOURCE_PRODUCT_LOT", lot_override)
    match = _RIYUEXIN_PRODUCT_FIRST.fullmatch(stem)
    if match:
        return _with_optional_override(match, "PRODUCT_LOT_SOURCE", lot_override)
    missing = _missing_lot_identity(
        _SOURCE_FIRST_MISSING_LOT.fullmatch(stem),
        "SOURCE_PRODUCT_MANUAL_LOT",
        file_path,
        lot_override,
    )
    if missing is not None:
        return missing
    missing = _missing_lot_identity(
        _RIYUEXIN_PRODUCT_FIRST_MISSING_LOT.fullmatch(stem),
        "PRODUCT_MANUAL_LOT_SOURCE",
        file_path,
        lot_override,
    )
    if missing is not None:
        return missing
    raise ValueError(f"日月新 FT DC 文件名不符合已批准格式: {Path(file_path).name}")


def parse_riyueguang_dc_filename(
    file_path: str | Path, *, lot_override: str | None = None
) -> FtFileIdentity:
    """Parse the independently approved Riyueguang/ASE DC filename."""
    match = _SOURCE_FIRST.fullmatch(Path(file_path).stem)
    if match:
        return _with_optional_override(match, "SOURCE_PRODUCT_LOT", lot_override)
    missing = _missing_lot_identity(
        _SOURCE_FIRST_MISSING_LOT.fullmatch(Path(file_path).stem),
        "SOURCE_PRODUCT_MANUAL_LOT",
        file_path,
        lot_override,
    )
    if missing is not None:
        return missing
    raise ValueError(f"日月光 FT DC 文件名不符合已批准格式: {Path(file_path).name}")
