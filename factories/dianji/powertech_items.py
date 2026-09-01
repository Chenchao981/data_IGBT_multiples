#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Shared dynamic Item planning for Dianji PowerTECH exports.

The two PowerTECH containers (tab text and native XLSX) expose the same
business identity on their Item/Bias/Unit rows.  This module deliberately
plans columns from that identity instead of treating a complete tester layout
as the data contract.  Existing business names and ordering remain stable;
new, non-control Items are appended without guessing a unit conversion.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, replace
from pathlib import Path
import re

from factories.dianji.models import DianjiFormatError


@dataclass(frozen=True)
class PowerTechItem:
    item_no: int
    field_index: int
    base_name: str
    bias1: str
    bias2: str
    bias3: str
    unit: str
    min_limit: str = ""
    max_limit: str = ""
    source_name: str = ""

    @property
    def semantic_key(self) -> tuple[str, str, str, str, str]:
        return (
            self.base_name.casefold(),
            _normalized_text(self.bias1).casefold(),
            _normalized_text(self.bias2).casefold(),
            _normalized_text(self.bias3).casefold(),
            self.unit.strip().casefold(),
        )


@dataclass(frozen=True)
class PlannedPowerTechColumn:
    item: PowerTechItem
    name: str
    unit: str
    factor: float
    parameter_key: tuple[str, ...]


# These are tester controls, screening helpers, or placeholders that were
# explicitly excluded from the approved Dianji business output.  CONT_NEW,
# CONTX, CONTACT, and future CONT* variants are covered by the prefix rule in
# _is_control_item.
EXCLUDED_ITEM_BASES = frozenset(
    {
        "CONT",
        "CONT_TR",
        "CONT_LCR",
        "CONT_RF",
        "SAME",
        "DELAY",
        "VF_EX",
        "VFSE",
        "EAS",
        "RF-SCANBOX",
        "CISS_EX",
        "DVF_EX",
        "TSD",
    }
)


_UNIT_FACTORS = {
    ("v", "mv"): 1_000.0,
    ("a", "na"): 1_000_000_000.0,
    ("ua", "na"): 1_000.0,
    ("r", "mr"): 1_000.0,
}


def plan_powertech_text_columns(
    items: list[PowerTechItem], path: str | Path
) -> list[PlannedPowerTechColumn]:
    """Plan pseudo-XLS business columns from Item/Bias/Unit semantics."""
    source = Path(path)
    selected = _select_business_items(items)
    if not selected:
        raise DianjiFormatError(f"{source.name} 没有可输出的 PowerTECH 业务参数")

    by_number = {item.item_no: item for item in items}
    occurrences = _occurrence_indexes(selected)
    planned: list[PlannedPowerTechColumn] = []
    for item in selected:
        base = item.base_name
        occurrence = occurrences[item.item_no]
        if base in {"DVDS", "DVDS_EX"}:
            name = "DVDS(mV)" if occurrence == 1 else f"DVDS{occurrence}(mV)"
            planned.append(_known_column(item, name, "mV", source))
        elif base in {"LCR-RG", "RG_EX"}:
            name = "Rg(R)" if occurrence == 1 else f"Rg{occurrence}(R)"
            planned.append(_known_column(item, name, "R", source))
        elif base == "VTH":
            planned.append(
                _known_column(item, f"VTH{occurrence}(V)", "V", source)
            )
        elif base == "BVDSS":
            planned.append(
                _known_column(item, f"BVDSS{occurrence}(V)", "V", source)
            )
        elif base == "IDSS":
            condition = condition_value(item.bias1, "VDS", source, item.item_no)
            planned.append(
                _known_column(item, f"IDSS{condition}(nA)", "nA", source)
            )
        elif base == "IGSS":
            condition = condition_decimal(item.bias1, "VGS", source, item.item_no)
            prefix = "ISGS" if condition.startswith("-") else "IGSS"
            planned.append(
                _known_column(
                    item,
                    f"{prefix}{condition.lstrip('+-')}(nA)",
                    "nA",
                    source,
                )
            )
        elif base == "RDON":
            condition_text = item.bias2 if "VGS" in item.bias2.upper() else item.bias1
            condition = condition_value(
                condition_text, "VGS", source, item.item_no
            )
            planned.append(
                _known_column(item, f"RDON{condition}(mR)", "mR", source)
            )
        elif base == "VFSD":
            name = "VFSD(V)" if occurrence == 1 else f"VFSD{occurrence}(V)"
            planned.append(_known_column(item, name, "V", source))
        elif base == "DELTA":
            planned.append(_delta_column(item, by_number, source))
        else:
            planned.append(_generic_column(item))

    planned = _deduplicate_or_reject(planned, source)
    return _legacy_text_order(planned)


def plan_powertech_xlsx_columns(
    items: list[PowerTechItem], path: str | Path
) -> list[PlannedPowerTechColumn]:
    """Plan native-XLSX business columns and retain the approved 21-column core."""
    source = Path(path)
    selected = _select_business_items(items)
    if not selected:
        raise DianjiFormatError(f"{source.name} 没有可输出的 PowerTECH XLSX 业务参数")

    by_number = {item.item_no: item for item in items}
    occurrences = _occurrence_indexes(selected)
    ices_groups = _condition_groups(selected, "ICES", "VCE")
    igss_groups = _signed_condition_groups(selected, "IGSS", "VGS")
    planned: list[PlannedPowerTechColumn] = []

    for item in selected:
        base = item.base_name
        occurrence = occurrences[item.item_no]
        if base in {"DVCE", "DVCE_EX"}:
            name = "DVCE(mV)" if occurrence == 1 else f"DVCE{occurrence}(mV)"
            planned.append(_known_column(item, name, "mV", source))
        elif base in {"LCR-RG", "RG_EX"}:
            name = "Rg(R)" if occurrence == 1 else f"Rg{occurrence}(R)"
            planned.append(_known_column(item, name, "R", source))
        elif base == "VTH":
            planned.append(
                _known_column(item, f"VTH{occurrence}(V)", "V", source)
            )
        elif base == "BVDSS":
            planned.append(
                _known_column(item, f"BVDSS{occurrence}(V)", "V", source)
            )
        elif base == "ICES":
            condition = condition_value(item.bias1, "VCE", source, item.item_no)
            group = ices_groups[condition]
            index = group.index(item.item_no) + 1
            stem = f"ICES{condition}"
            name = _with_numbered_occurrence(stem, "nA", index, len(group))
            planned.append(_known_column(item, name, "nA", source))
        elif base == "IGSS":
            condition = condition_decimal(item.bias1, "VGS", source, item.item_no)
            prefix = "ISGS" if condition.startswith("-") else "IGSS"
            magnitude = condition.lstrip("+-")
            group = igss_groups[(prefix, magnitude)]
            index = group.index(item.item_no) + 1
            name = _with_numbered_occurrence(
                f"{prefix}{magnitude}", "nA", index, len(group)
            )
            planned.append(_known_column(item, name, "nA", source))
        elif base == "VDSON":
            drain = condition_value(item.bias1, "ID", source, item.item_no)
            gate = condition_value(item.bias2, "VGS", source, item.item_no)
            planned.append(
                _known_column(
                    item, f"VDSON{drain}A-{gate}V(V)", "V", source
                )
            )
        elif base == "VF":
            current = condition_value(item.bias1, "IAK", source, item.item_no)
            name = f"VF{current}A(V)"
            planned.append(_known_column(item, name, "V", source))
        elif base == "DELTA":
            planned.append(_delta_column(item, by_number, source))
        else:
            planned.append(_generic_column(item))

    planned = _deduplicate_or_reject(planned, source)
    return _legacy_xlsx_order(planned)


def condition_value(
    text: str, key: str, path: str | Path, item_no: int
) -> str:
    return condition_decimal(text, key, path, item_no).lstrip("+")


def condition_decimal(
    text: str, key: str, path: str | Path, item_no: int
) -> str:
    match = re.search(
        rf"(?:^|\b){re.escape(key)}\s*=\s*([+-]?\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if match is None:
        raise DianjiFormatError(
            f"{Path(path).name} 的 Item #{item_no} 缺少 {key} 测试条件: {text!r}"
        )
    raw = match.group(1)
    sign = "-" if raw.startswith("-") else ("+" if raw.startswith("+") else "")
    magnitude = raw.lstrip("+-")
    if "." in magnitude:
        magnitude = magnitude.rstrip("0").rstrip(".")
    return f"{sign}{magnitude or '0'}"


def _select_business_items(items: list[PowerTechItem]) -> list[PowerTechItem]:
    by_number = {item.item_no: item for item in items}
    selected = []
    for item in items:
        if _is_control_item(item):
            continue
        if item.base_name == "VTH" and _is_prescreen_vth(item, by_number):
            continue
        selected.append(item)
    return selected


def _is_control_item(item: PowerTechItem) -> bool:
    base = item.base_name
    return base in EXCLUDED_ITEM_BASES or base.startswith("CONT")


def _is_prescreen_vth(
    item: PowerTechItem, by_number: dict[int, PowerTechItem]
) -> bool:
    if item.min_limit.strip():
        return False
    following = by_number.get(item.item_no + 1)
    if following is None or following.base_name != "SAME":
        return False
    reference = re.fullmatch(r"M#\s*=\s*(\d+)", following.bias1.strip(), re.I)
    return reference is not None and int(reference.group(1)) == item.item_no


def _occurrence_indexes(items: list[PowerTechItem]) -> dict[int, int]:
    counts: Counter[str] = Counter()
    result = {}
    for item in items:
        key = _family(item.base_name)
        counts[key] += 1
        result[item.item_no] = counts[key]
    return result


def _family(base: str) -> str:
    if base in {"DVDS", "DVDS_EX"}:
        return "DVDS"
    if base in {"DVCE", "DVCE_EX"}:
        return "DVCE"
    if base in {"LCR-RG", "RG_EX"}:
        return "RG"
    return base


def _known_column(
    item: PowerTechItem, name: str, target_unit: str, path: Path
) -> PlannedPowerTechColumn:
    return PlannedPowerTechColumn(
        item=item,
        name=name,
        unit=target_unit,
        factor=_unit_factor(item.unit, target_unit, path, item),
        parameter_key=(
            "known",
            name.casefold(),
            _family(item.base_name).casefold(),
            _normalized_text(item.bias1).casefold(),
            _normalized_text(item.bias2).casefold(),
            _normalized_text(item.bias3).casefold(),
            target_unit.casefold(),
        ),
    )


def _generic_column(item: PowerTechItem) -> PlannedPowerTechColumn:
    conditions = [
        _normalized_text(value)
        for value in (item.bias1, item.bias2, item.bias3)
        if _normalized_text(value)
    ]
    # Known Items are normalized for matching, but an unrecognized business
    # parameter must retain the spelling supplied by the tester export.
    name = item.source_name.strip() or item.base_name
    if conditions:
        name += f"[{'; '.join(conditions)}]"
    if item.unit.strip():
        name += f"({item.unit.strip()})"
    return PlannedPowerTechColumn(
        item=item,
        name=name,
        unit=item.unit.strip(),
        factor=1.0,
        parameter_key=(
            "generic",
            name.casefold(),
            item.base_name.casefold(),
            _normalized_text(item.bias1).casefold(),
            _normalized_text(item.bias2).casefold(),
            _normalized_text(item.bias3).casefold(),
            item.unit.strip().casefold(),
        ),
    )


def _delta_column(
    item: PowerTechItem,
    by_number: dict[int, PowerTechItem],
    path: Path,
) -> PlannedPowerTechColumn:
    references = {
        by_number[number].base_name
        for number in (
            int(value)
            for value in re.findall(
                r"#(\d+)", " ".join((item.bias1, item.bias2, item.bias3))
            )
        )
        if number in by_number
    }
    if references and references <= {"BVDSS"}:
        name = "DELTA BV"
    elif references and references <= {"VTH"}:
        name = "DELTA VTH"
    else:
        raise DianjiFormatError(
            f"{path.name} 的 DELTA Item #{item.item_no} 引用无法识别: "
            f"{item.bias1!r}, {item.bias2!r}"
        )
    return PlannedPowerTechColumn(
        item=item,
        name=name,
        unit="",
        factor=1.0,
        # Item numbers legitimately shift when SAME placeholders are inserted
        # or removed.  The referenced business families are the stable DELTA
        # identity, so do not leak raw #numbers into the schema key.
        parameter_key=("known", name.casefold(), "delta", ""),
    )


def _unit_factor(
    source_unit: str,
    target_unit: str,
    path: Path,
    item: PowerTechItem,
) -> float:
    if not target_unit:
        return 1.0
    source = source_unit.strip().casefold()
    target = target_unit.strip().casefold()
    if source == target:
        return 1.0
    factor = _UNIT_FACTORS.get((source, target))
    if factor is None:
        raise DianjiFormatError(
            f"{path.name} 的 Item #{item.item_no} 单位不支持: "
            f"{source_unit!r} -> {target_unit!r}"
        )
    return factor


def _condition_groups(
    items: list[PowerTechItem], base: str, key: str
) -> dict[str, list[int]]:
    groups: dict[str, list[int]] = defaultdict(list)
    for item in items:
        if item.base_name != base:
            continue
        # The public planner will emit the contextual error if this is absent.
        match = re.search(
            rf"(?:^|\b){re.escape(key)}\s*=\s*([+-]?\d+(?:\.\d+)?)",
            item.bias1,
            flags=re.IGNORECASE,
        )
        if match:
            raw = match.group(1).lstrip("+")
            groups[_trim_decimal(raw)].append(item.item_no)
    return groups


def _signed_condition_groups(
    items: list[PowerTechItem], base: str, key: str
) -> dict[tuple[str, str], list[int]]:
    groups: dict[tuple[str, str], list[int]] = defaultdict(list)
    for item in items:
        if item.base_name != base:
            continue
        match = re.search(
            rf"(?:^|\b){re.escape(key)}\s*=\s*([+-]?\d+(?:\.\d+)?)",
            item.bias1,
            flags=re.IGNORECASE,
        )
        if match:
            condition = _trim_decimal(match.group(1))
            prefix = "ISGS" if condition.startswith("-") else "IGSS"
            groups[(prefix, condition.lstrip("+-"))].append(item.item_no)
    return groups


def _with_numbered_occurrence(
    stem: str, unit: str, index: int, total: int
) -> str:
    suffix = f"-{index}" if total > 1 else ""
    return f"{stem}{suffix}({unit})"


def _deduplicate_or_reject(
    columns: list[PlannedPowerTechColumn], path: Path
) -> list[PlannedPowerTechColumn]:
    used: dict[str, tuple[str, ...]] = {}
    exact_counts: Counter[str] = Counter()
    result = []
    for column in columns:
        name_key = column.name.casefold()
        semantic = column.parameter_key
        previous = used.get(name_key)
        if previous is None:
            used[name_key] = semantic
            exact_counts[name_key] = 1
            result.append(column)
            continue
        if previous != semantic:
            raise DianjiFormatError(
                f"{path.name} 生成输出列名语义冲突: {column.name}; "
                f"已有={previous}, 新增={semantic}"
            )
        exact_counts[name_key] += 1
        renamed = _suffix_before_unit(column.name, exact_counts[name_key])
        renamed_key = renamed.casefold()
        while renamed_key in used:
            exact_counts[name_key] += 1
            renamed = _suffix_before_unit(column.name, exact_counts[name_key])
            renamed_key = renamed.casefold()
        occurrence_key = (*semantic, f"occurrence={exact_counts[name_key]}")
        used[renamed_key] = occurrence_key
        result.append(
            replace(column, name=renamed, parameter_key=occurrence_key)
        )
    return result


def _legacy_text_order(
    columns: list[PlannedPowerTechColumn],
) -> list[PlannedPowerTechColumn]:
    # Only the first 19 business Items of the two established 32/34 layouts
    # receive their historical RAW ordering.  A shorter layout that happens to
    # reach 19 columns through a new right-side parameter must keep source order.
    # Conversely, right-side additions to a verified legacy core remain appended.
    if not _has_legacy_text_core(columns):
        return columns

    groups = _planned_groups(columns)
    required = {
        "DVDS": 1,
        "RG": 1,
        "VTH": 3,
        "BVDSS": 2,
        "IDSS": 2,
        "IGSS": 6,
        "RDON": 1,
        "VFSD": 1,
        "DELTA BV": 1,
        "DELTA VTH": 1,
    }
    if any(len(groups[key]) < count for key, count in required.items()):
        return columns

    tail_igss = groups["IGSS"][4:6]
    tail_igss = sorted(
        tail_igss, key=lambda column: 0 if column.name.startswith("ISGS") else 1
    )
    core = [
        groups["DVDS"][0],
        groups["RG"][0],
        *groups["VTH"][:2],
        *groups["BVDSS"][:2],
        groups["IDSS"][0],
        *groups["IGSS"][:4],
        groups["RDON"][0],
        groups["VFSD"][0],
        *tail_igss,
        groups["IDSS"][1],
        groups["VTH"][2],
        groups["DELTA BV"][0],
        groups["DELTA VTH"][0],
    ]
    return _append_unconsumed(core, columns)


def _has_legacy_text_core(
    columns: list[PlannedPowerTechColumn],
) -> bool:
    if len(columns) < 19:
        return False
    core_bases = [_family(column.item.base_name) for column in columns[:19]]
    prefix = [
        "DVDS", "RG", "VTH", "VTH", "BVDSS", "BVDSS", "IDSS",
        "IGSS", "IGSS", "IGSS", "IGSS", "RDON", "VFSD",
    ]
    if core_bases[:13] != prefix:
        return False
    if core_bases[13:16] not in (
        ["IDSS", "IGSS", "IGSS"],
        ["IGSS", "IGSS", "IDSS"],
    ):
        return False
    return core_bases[16:] == ["VTH", "DELTA", "DELTA"]


def _legacy_xlsx_order(
    columns: list[PlannedPowerTechColumn],
) -> list[PlannedPowerTechColumn]:
    groups = _planned_groups(columns)
    required = {
        "DVCE": 1,
        "RG": 1,
        "VTH": 2,
        "BVDSS": 3,
        "ICES": 4,
        "IGSS": 4,
        "VDSON": 3,
        "VF": 1,
        "DELTA BV": 1,
        "DELTA VTH": 1,
    }
    if any(len(groups[key]) < count for key, count in required.items()):
        return columns

    ices = groups["ICES"]
    primary_ices = next(
        (column for column in ices if column.name == "ICES1000(nA)"), ices[0]
    )
    remaining_ices = [column for column in ices if column is not primary_ices]
    positive_igss = [
        column for column in groups["IGSS"] if column.name.startswith("IGSS")
    ]
    negative_igss = [
        column for column in groups["IGSS"] if column.name.startswith("ISGS")
    ]
    if len(positive_igss) < 2 or len(negative_igss) < 2:
        return columns

    core = [
        groups["DVCE"][0],
        groups["RG"][0],
        *groups["VTH"][:2],
        *groups["BVDSS"][:3],
        primary_ices,
        positive_igss[0],
        negative_igss[0],
        *groups["VDSON"][:3],
        groups["VF"][0],
        *remaining_ices[:3],
        positive_igss[1],
        negative_igss[1],
        groups["DELTA BV"][0],
        groups["DELTA VTH"][0],
    ]
    return _append_unconsumed(core, columns)


def _planned_groups(
    columns: list[PlannedPowerTechColumn],
) -> dict[str, list[PlannedPowerTechColumn]]:
    groups: dict[str, list[PlannedPowerTechColumn]] = defaultdict(list)
    for column in columns:
        base = _family(column.item.base_name)
        if column.item.base_name == "IGSS":
            base = "IGSS"
        elif column.item.base_name == "DELTA":
            base = column.name.split("-", 1)[0]
        groups[base].append(column)
    return groups


def _append_unconsumed(
    core: list[PlannedPowerTechColumn],
    source_order: list[PlannedPowerTechColumn],
) -> list[PlannedPowerTechColumn]:
    consumed = {id(column) for column in core}
    return [*core, *(column for column in source_order if id(column) not in consumed)]


def _suffix_before_unit(name: str, occurrence: int) -> str:
    match = re.fullmatch(r"(.*?)(\([^()]*\))?", name)
    assert match is not None
    stem = match.group(1)
    unit = match.group(2) or ""
    return f"{stem}-{occurrence}{unit}"


def _trim_decimal(raw: str) -> str:
    sign = "-" if raw.startswith("-") else ("+" if raw.startswith("+") else "")
    magnitude = raw.lstrip("+-")
    if "." in magnitude:
        magnitude = magnitude.rstrip("0").rstrip(".")
    return f"{sign}{magnitude or '0'}"


def _normalized_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value)).strip()
