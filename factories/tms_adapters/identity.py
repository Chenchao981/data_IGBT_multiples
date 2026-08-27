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


@dataclass(frozen=True, slots=True)
class FtFileIdentity:
    source_id: str
    product: str
    lot_id: str
    layout: str


def _from_match(match: re.Match[str], layout: str) -> FtFileIdentity:
    return FtFileIdentity(
        source_id=match.group("source").upper(),
        product=match.group("product").strip(),
        lot_id=match.group("lot").upper(),
        layout=layout,
    )


def parse_riyuexin_dc_filename(file_path: str | Path) -> FtFileIdentity:
    """Parse either of the two approved Riyuexin DC filename directions."""
    stem = Path(file_path).stem
    match = _SOURCE_FIRST.fullmatch(stem)
    if match:
        return _from_match(match, "SOURCE_PRODUCT_LOT")
    match = _RIYUEXIN_PRODUCT_FIRST.fullmatch(stem)
    if match:
        return _from_match(match, "PRODUCT_LOT_SOURCE")
    raise ValueError(f"日月新 FT DC 文件名不符合已批准格式: {Path(file_path).name}")


def parse_riyueguang_dc_filename(file_path: str | Path) -> FtFileIdentity:
    """Parse the independently approved Riyueguang/ASE DC filename."""
    match = _SOURCE_FIRST.fullmatch(Path(file_path).stem)
    if not match:
        raise ValueError(f"日月光 FT DC 文件名不符合已批准格式: {Path(file_path).name}")
    return _from_match(match, "SOURCE_PRODUCT_LOT")
