#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""FT-specific static scatter and box charts.

The business contract here is intentionally different from CP wafer charts:

* ``lot_ID`` is the FT batch identity and the box grouping key.
* ``NUM`` only provides a stable within-batch display order.
* ``Source_ID`` only binds source-specific limits and traceability.
* no wafer, site, tester, file, or test-round subgroup is inferred.

Viewport focusing and PNG rendering are display operations only.  They never
filter measurements or change Cleaner, Bin, yield, PAT, or Cpk calculations.
"""

from __future__ import annotations

from colorsys import hsv_to_rgb
from dataclasses import dataclass
from io import BytesIO
import re
from threading import RLock
from typing import Mapping, Sequence

import numpy as np
import pandas as pd


FOCUS_MIN_GROUP_SIZE = 20
FOCUS_IQR_MULTIPLIER = 3.0
FOCUS_PADDING_RATIO = 0.15
BOX_WHISKER_IQR_MULTIPLIER = 1.5
BOX_FOCUS_PADDING_RATIO = 0.03
_RENDER_LOCK = RLock()
_VALUE_REFERENCE_PATTERN = re.compile(r"\bValue\s*=\s*#\d+\b", re.IGNORECASE)
_APPROVED_VALUE_REFERENCE_PARAMETERS = frozenset({"DELTA BV", "DELTA VTH"})
_BATCH_COLORS = (
    "#0057a8",
    "#a31318",
    "#008322",
    "#9412ad",
    "#555555",
    "#ce8b00",
    "#008c99",
    "#ec6635",
    "#6673ca",
    "#ac517b",
    "#627b20",
    "#794329",
    "#13a885",
    "#bb6141",
    "#586c85",
    "#b29117",
    "#9b6ab3",
    "#4584b0",
    "#60529b",
    "#a55555",
)


@dataclass(frozen=True)
class FTBatchGroup:
    """One complete FT ``lot_ID`` batch in stable ``NUM`` order."""

    lot_id: str
    row_positions: np.ndarray
    x_positions: np.ndarray


@dataclass(frozen=True)
class FTChartLayout:
    """Reusable row layout prepared once and shared across parameters."""

    batches: tuple[FTBatchGroup, ...]
    x_by_row: np.ndarray
    batch_index_by_row: np.ndarray
    source_rows: Mapping[str, np.ndarray]
    row_count: int


def _required_identity(value: object, label: str) -> str:
    if pd.isna(value):
        raise ValueError(f"FT 图表数据存在空{label}，停止绘图")
    text = str(value)
    if not text.strip() or text.strip().lower() == "nan":
        raise ValueError(f"FT 图表数据存在空{label}，停止绘图")
    return text


def _optional_text(value: object) -> str:
    if pd.isna(value):
        return ""
    text = str(value).strip()
    return "" if text.lower() == "nan" else text


def prepare_ft_chart_layout(data: pd.DataFrame | None) -> FTChartLayout:
    """Prepare the confirmed FT grouping contract without inventing subgroups."""

    if data is None or data.empty:
        return FTChartLayout(
            (), np.empty(0, dtype=float), np.empty(0, dtype=np.int64), {}, 0
        )
    missing = {"NUM", "lot_ID", "Source_ID"}.difference(data.columns)
    if missing:
        raise ValueError(f"FT 图表数据缺少必要列: {', '.join(sorted(missing))}")

    row_count = len(data)
    row_positions = np.arange(row_count, dtype=np.int64)
    lot_values = np.asarray(
        [_required_identity(value, "批次 lot_ID") for value in data["lot_ID"]],
        dtype=object,
    )
    lot_codes, lot_labels = pd.factorize(lot_values, sort=False)
    numeric_order = pd.to_numeric(data["NUM"], errors="coerce").to_numpy(
        dtype=float, na_value=np.nan
    )
    if not np.isfinite(numeric_order).all():
        raise ValueError("FT 图表数据的 NUM 存在空值或非有限数，停止绘图")
    sortable_order = np.where(np.isfinite(numeric_order), numeric_order, np.inf)
    ordered_rows = np.lexsort((row_positions, sortable_order, lot_codes))

    x_by_row = np.empty(row_count, dtype=float)
    batch_index_by_row = np.empty(row_count, dtype=np.int64)
    batches: list[FTBatchGroup] = []
    for batch_index, lot_id in enumerate(lot_labels):
        batch_rows = ordered_rows[lot_codes[ordered_rows] == batch_index]
        batch_x = batch_index + (np.arange(len(batch_rows), dtype=float) + 0.5) / len(
            batch_rows
        )
        x_by_row[batch_rows] = batch_x
        batch_index_by_row[batch_rows] = batch_index
        batches.append(
            FTBatchGroup(
                lot_id=str(lot_id),
                row_positions=batch_rows,
                x_positions=batch_x,
            )
        )

    source_values = np.asarray(
        [_required_identity(value, "来源 Source_ID") for value in data["Source_ID"]],
        dtype=object,
    )
    source_codes, source_labels = pd.factorize(source_values, sort=False)
    source_rows = {
        str(source_id): row_positions[source_codes == source_index]
        for source_index, source_id in enumerate(source_labels)
    }
    return FTChartLayout(
        tuple(batches), x_by_row, batch_index_by_row, source_rows, row_count
    )


def parameter_values(data: pd.DataFrame, parameter: str) -> np.ndarray:
    """Coerce one parameter without changing the source frame."""

    if parameter not in data.columns:
        raise KeyError(parameter)
    return pd.to_numeric(data[parameter], errors="coerce").to_numpy(
        dtype=float, na_value=np.nan
    )


def focused_y_range(
    numeric: np.ndarray, batches: Sequence[FTBatchGroup]
) -> tuple[float, float] | None:
    """Union each FT batch's central range for viewport use only."""

    ranges: list[tuple[float, float]] = []
    for batch in batches:
        values = numeric[batch.row_positions]
        values = values[np.isfinite(values)]
        if not len(values):
            continue
        if len(values) < FOCUS_MIN_GROUP_SIZE:
            ranges.append((float(values.min()), float(values.max())))
            continue
        q1, q3 = np.quantile(values, [0.25, 0.75], method="linear")
        iqr = q3 - q1
        central = values[
            (values >= q1 - FOCUS_IQR_MULTIPLIER * iqr)
            & (values <= q3 + FOCUS_IQR_MULTIPLIER * iqr)
        ]
        if not len(central):
            central = values
        ranges.append((float(central.min()), float(central.max())))
    if not ranges:
        return None
    low = min(pair[0] for pair in ranges)
    high = max(pair[1] for pair in ranges)
    span = high - low
    padding = (
        span * FOCUS_PADDING_RATIO
        if span > 0
        else max(abs(low) * 0.005, 1e-12)
    )
    return low - padding, high + padding


def ft_batch_box_statistics(
    numeric: np.ndarray, batches: Sequence[FTBatchGroup]
) -> tuple[dict[str, float | list], ...]:
    """Compute one Tukey box per FT ``lot_ID`` from all finite values.

    This is the FT chart's explicit new display definition.  It is not PAT and
    does not reuse CP's per-wafer slices.
    """

    statistics: list[dict[str, float | list]] = []
    for batch in batches:
        values = numeric[batch.row_positions]
        values = values[np.isfinite(values)]
        if not len(values):
            statistics.append({})
            continue
        q1, median, q3 = np.quantile(
            values, [0.25, 0.5, 0.75], method="linear"
        )
        iqr = q3 - q1
        inside = values[
            (values >= q1 - BOX_WHISKER_IQR_MULTIPLIER * iqr)
            & (values <= q3 + BOX_WHISKER_IQR_MULTIPLIER * iqr)
        ]
        statistics.append(
            {
                "q1": float(q1),
                "med": float(median),
                "q3": float(q3),
                "whislo": float(inside.min()) if len(inside) else float(q1),
                "whishi": float(inside.max()) if len(inside) else float(q3),
                "fliers": [],
            }
        )
    return tuple(statistics)


def batch_color(index: int) -> str:
    if index < len(_BATCH_COLORS):
        return _BATCH_COLORS[index]
    red, green, blue = hsv_to_rgb((index * 0.61803398875) % 1, 0.75, 0.68)
    return "#" + "".join(
        f"{round(channel * 255):02x}" for channel in (red, green, blue)
    )


def _normalized_unit(value: object) -> str:
    unit = _optional_text(value)
    return "" if unit in {"0", "0.0"} else unit


def _normalized_condition(parameter: str, value: object) -> str:
    condition = _optional_text(value)
    if not condition:
        return ""
    if str(parameter).strip().upper() in _APPROVED_VALUE_REFERENCE_PARAMETERS:
        # The reviewed PowerTECH XLSX profiles place the same DELTA operands at
        # different item numbers.  Only these two canonical fields have an
        # approved semantic equivalence; every other condition stays exact.
        return _VALUE_REFERENCE_PATTERN.sub("Value=#", condition)
    return condition


def _parameter_specs(specs: pd.DataFrame, parameter: str) -> pd.DataFrame:
    if specs is None or specs.empty or "Parameter" not in specs.columns:
        return pd.DataFrame(columns=["Source_ID", "Low_Limit", "High_Limit"])
    relevant = specs.loc[specs["Parameter"].astype(str) == str(parameter)].copy()
    if relevant.empty:
        return relevant
    if "Source_ID" not in relevant.columns:
        raise ValueError(f"参数 {parameter} 的规格缺少 Source_ID")
    relevant["Source_ID"] = relevant["Source_ID"].map(
        lambda value: _required_identity(value, "规格来源 Source_ID")
    )
    for column in ("Low_Limit", "High_Limit"):
        if column not in relevant.columns:
            relevant[column] = np.nan
        raw_values = relevant[column]
        missing = raw_values.map(
            lambda value: pd.isna(value) or not str(value).strip()
        )
        numeric_values = pd.to_numeric(raw_values, errors="coerce")
        invalid = ~missing & (
            numeric_values.isna() | ~np.isfinite(numeric_values)
        )
        if invalid.any():
            row = relevant.loc[invalid].iloc[0]
            raise ValueError(
                f"参数 {parameter} 的 {column} 不是有限数字: "
                f"Source_ID={row.get('Source_ID', '')}, "
                f"lot_ID={row.get('lot_ID', '')}, 原值={row.get(column)!r}"
            )
        relevant[column] = numeric_values

    if "lot_ID" in relevant.columns:
        relevant["lot_ID"] = relevant["lot_ID"].map(
            lambda value: _required_identity(value, "规格批次 lot_ID")
        )
    relevant["_unit_normalized"] = (
        relevant["Unit"].map(_normalized_unit)
        if "Unit" in relevant.columns
        else ""
    )
    relevant["_condition_normalized"] = (
        relevant["Test_Condition"].map(
            lambda value: _normalized_condition(parameter, value)
        )
        if "Test_Condition" in relevant.columns
        else ""
    )

    compare_columns = ["Low_Limit", "High_Limit", "_unit_normalized", "_condition_normalized"]
    identity_columns = ["Source_ID"] + (["lot_ID"] if "lot_ID" in relevant.columns else [])
    for identity, group in relevant.groupby(identity_columns, sort=False, dropna=False):
        if len(group[compare_columns].drop_duplicates()) > 1:
            identity_text = " / ".join(
                str(value) for value in (identity if isinstance(identity, tuple) else (identity,))
            )
            raise ValueError(
                f"参数 {parameter} 的来源 {identity_text} 存在冲突规格，停止绘图"
            )
    return relevant.drop_duplicates(identity_columns, keep="last")


def validate_parameter_contract(
    data: pd.DataFrame,
    specs: pd.DataFrame,
    parameter: str,
    numeric: np.ndarray,
    layout: FTChartLayout,
) -> tuple[pd.DataFrame, str, tuple[str, ...]]:
    """Validate source-bound FT specs before any figure is allocated.

    Dynamic parameter columns are accepted, but every source that contains a
    finite value must have an unambiguous spec record.  Unit and test-condition
    compatibility is checked across those measured sources before a complete
    ``lot_ID`` is combined into one box.
    """

    relevant = _parameter_specs(specs, parameter)
    if not np.isfinite(numeric).any():
        return relevant.iloc[0:0].copy(), "", ()

    measured_records: list[tuple[str, str]] = []
    ambiguous_sources: list[str] = []
    for source_id, source_rows in layout.source_rows.items():
        active_rows = source_rows[np.isfinite(numeric[source_rows])]
        if not len(active_rows):
            continue
        batch_indices = np.unique(layout.batch_index_by_row[active_rows])
        if len(batch_indices) > 1:
            ambiguous_sources.append(source_id)
            continue
        measured_records.append(
            (source_id, layout.batches[int(batch_indices[0])].lot_id)
        )
    if ambiguous_sources:
        raise ValueError(
            f"参数 {parameter} 的 Source_ID 跨多个 lot_ID，无法唯一绑定规格: "
            + "、".join(ambiguous_sources[:3])
        )
    measured = pd.DataFrame(measured_records, columns=["Source_ID", "lot_ID"])

    if relevant.empty:
        raise ValueError(f"参数 {parameter} 的有效测量来源没有规格记录，停止绘图")

    measured_sources = measured["Source_ID"].tolist()
    missing_sources = [
        source_id
        for source_id in measured_sources
        if not relevant["Source_ID"].eq(source_id).any()
    ]
    if missing_sources:
        raise ValueError(
            f"参数 {parameter} 的有效测量来源缺少规格: "
            + "、".join(missing_sources[:3])
        )
    relevant = relevant.loc[relevant["Source_ID"].isin(measured_sources)].copy()

    if "lot_ID" in relevant.columns:
        spec_lot_counts = relevant.groupby("Source_ID", sort=False)["lot_ID"].nunique()
        ambiguous_spec_sources = spec_lot_counts[spec_lot_counts > 1].index.tolist()
        if ambiguous_spec_sources:
            raise ValueError(
                f"参数 {parameter} 的规格 Source_ID 对应多个 lot_ID: "
                + "、".join(ambiguous_spec_sources[:3])
            )
        expected_lot_by_source = dict(
            measured[["Source_ID", "lot_ID"]].itertuples(index=False, name=None)
        )
        mismatches: list[str] = []
        for source_id, lot_id in expected_lot_by_source.items():
            source_specs = relevant.loc[relevant["Source_ID"].eq(source_id)]
            if not source_specs["lot_ID"].eq(lot_id).any():
                actual_spec_lots = "、".join(source_specs["lot_ID"].drop_duplicates())
                mismatches.append(f"{source_id}: 数据={lot_id}, 规格={actual_spec_lots}")
        if mismatches:
            raise ValueError(
                f"参数 {parameter} 的 Source_ID/lot_ID 规格绑定不一致: "
                + "；".join(mismatches[:3])
            )
        relevant = relevant.merge(measured, on=["Source_ID", "lot_ID"], how="inner")
    else:
        relevant = relevant.copy()

    units = relevant["_unit_normalized"].drop_duplicates().tolist()
    if len(units) > 1:
        labels = [unit or "空单位" for unit in units]
        raise ValueError(
            f"参数 {parameter} 存在不兼容单位: {', '.join(labels)}，停止同轴绘图"
        )
    unit = units[0] if units else ""

    normalized_conditions = relevant["_condition_normalized"].drop_duplicates().tolist()
    if len(normalized_conditions) > 1:
        labels = [condition or "空测试条件" for condition in normalized_conditions]
        raise ValueError(
            f"参数 {parameter} 存在不兼容测试条件: "
            + "；".join(labels[:3])
        )
    raw_conditions: list[str] = []
    if "Test_Condition" in relevant.columns:
        for value in relevant["Test_Condition"]:
            condition = _optional_text(value)
            if condition and condition not in raw_conditions:
                raw_conditions.append(condition)
    return relevant, unit, tuple(raw_conditions)


def parameter_unit(specs: pd.DataFrame, parameter: str) -> str:
    relevant = _parameter_specs(specs, parameter)
    if relevant.empty or "Unit" not in relevant.columns:
        return ""
    units: list[str] = []
    for value in relevant["Unit"]:
        unit = _normalized_unit(value)
        if unit and unit not in units:
            units.append(unit)
    if len(units) > 1:
        raise ValueError(
            f"参数 {parameter} 存在不兼容单位: {', '.join(units)}，停止同轴绘图"
        )
    return units[0] if units else ""


def parameter_conditions(specs: pd.DataFrame, parameter: str) -> tuple[str, ...]:
    relevant = _parameter_specs(specs, parameter)
    if relevant.empty or "Test_Condition" not in relevant.columns:
        return ()
    values: list[str] = []
    for value in relevant["Test_Condition"]:
        condition = _optional_text(value)
        if condition and condition not in values:
            values.append(condition)
    return tuple(values)


def _parameter_label(parameter: str, unit: str) -> str:
    if not unit:
        return parameter
    escaped = re.escape(unit)
    if re.search(rf"(?:\(|\[)\s*{escaped}\s*(?:\)|\])$", parameter, re.I):
        return parameter
    return f"{parameter} [{unit}]"


def _spec_segments(
    relevant: pd.DataFrame,
    layout: FTChartLayout,
    numeric: np.ndarray,
    column: str,
) -> list[tuple[float, float, float, str]]:
    if relevant.empty:
        return []
    values = relevant.dropna(subset=[column])
    if values.empty:
        return []

    actual_sources = {
        source_id
        for source_id, rows in layout.source_rows.items()
        if np.isfinite(numeric[rows]).any()
    }
    spec_sources = set(values["Source_ID"].astype(str))
    unique_limits = values[column].drop_duplicates().tolist()
    if len(unique_limits) == 1 and actual_sources.issubset(spec_sources):
        return [(0.0, float(len(layout.batches)), float(unique_limits[0]), "")]

    segments: list[tuple[float, float, float, str]] = []
    for spec in values.itertuples(index=False):
        source_id = str(getattr(spec, "Source_ID"))
        rows = layout.source_rows.get(source_id)
        if rows is None or not len(rows):
            continue
        rows = rows[np.isfinite(numeric[rows])]
        for batch_index in np.unique(layout.batch_index_by_row[rows]):
            scoped_rows = rows[layout.batch_index_by_row[rows] == batch_index]
            xs = np.sort(layout.x_by_row[scoped_rows])
            batch = layout.batches[int(batch_index)]
            step = 1.0 / max(len(batch.row_positions), 1)
            breaks = np.flatnonzero(np.diff(xs) > step * 1.5) + 1
            for run in np.split(xs, breaks):
                start = max(float(batch_index), float(run[0] - step * 0.45))
                end = min(float(batch_index + 1), float(run[-1] + step * 0.45))
                segments.append(
                    (
                        start,
                        end,
                        float(getattr(spec, column)),
                        batch.lot_id,
                    )
                )
    return segments


def _figure_width(batch_count: int) -> float:
    return max(16.0, min(30.0, batch_count * 0.45))


def _font_properties(size: float = 10):
    from matplotlib.font_manager import FontProperties

    return FontProperties(family=["Microsoft YaHei", "DejaVu Sans"], size=size)


def make_ft_distribution_figure(
    data: pd.DataFrame,
    specs: pd.DataFrame,
    parameter: str,
    layout: FTChartLayout,
    *,
    focus: bool = True,
    boxplot: bool = False,
):
    """Build an FT-only figure while leaving source data and statistics intact."""

    if layout.row_count != len(data):
        raise ValueError("FT 图表布局与数据行数不一致")
    if not layout.batches:
        raise ValueError("FT 图表没有可用批次")

    numeric = parameter_values(data, parameter)
    relevant_specs, unit, conditions = validate_parameter_contract(
        data, specs, parameter, numeric, layout
    )

    from matplotlib.figure import Figure
    from matplotlib.patches import Patch

    font = _font_properties()
    figure = Figure(
        figsize=(_figure_width(len(layout.batches)), 5), dpi=140, facecolor="white"
    )
    axis = figure.add_subplot(111)
    axis.set_facecolor("white")
    finite = numeric[np.isfinite(numeric)]
    y_range = focused_y_range(numeric, layout.batches) if focus else None
    box_statistics = (
        ft_batch_box_statistics(numeric, layout.batches) if boxplot else ()
    )
    if y_range is not None and boxplot:
        visible_boxes = [box for box in box_statistics if box]
        if visible_boxes:
            low = min(y_range[0], min(float(box["whislo"]) for box in visible_boxes))
            high = max(y_range[1], max(float(box["whishi"]) for box in visible_boxes))
            padding = (
                (high - low) * BOX_FOCUS_PADDING_RATIO
                if high > low
                else max(abs(low) * 0.005, 1e-12)
            )
            y_range = low - padding, high + padding
    if y_range is not None:
        axis.set_ylim(*y_range)

    for index, batch in enumerate(layout.batches):
        values = numeric[batch.row_positions]
        valid = np.isfinite(values)
        color = batch_color(index)
        if valid.any():
            if boxplot:
                box = box_statistics[index]
                axis.bxp(
                    [box],
                    positions=[index + 0.5],
                    widths=0.56,
                    showfliers=False,
                    patch_artist=True,
                    manage_ticks=False,
                    boxprops={
                        "facecolor": color,
                        "edgecolor": color,
                        "alpha": 0.55,
                        "linewidth": 1.2,
                    },
                    medianprops={"color": "#202020", "linewidth": 1.4},
                    whiskerprops={"color": color, "linewidth": 1.1},
                    capprops={"color": color, "linewidth": 1.1},
                )
            else:
                axis.scatter(
                    batch.x_positions[valid],
                    values[valid],
                    s=3,
                    color=color,
                    edgecolors="none",
                    alpha=0.85,
                    rasterized=True,
                )
        else:
            axis.text(
                index + 0.5,
                0.04,
                "无有效值",
                transform=axis.get_xaxis_transform(),
                ha="center",
                color="#777777",
                fontproperties=font,
            )

    if boxplot and not focus and len(finite):
        axis.update_datalim(
            [(0.0, float(finite.min())), (float(len(layout.batches)), float(finite.max()))]
        )
        axis.autoscale_view()

    outside_spec_scopes: dict[tuple[str, float, str], set[str]] = {}
    for column, label in (("Low_Limit", "LSL"), ("High_Limit", "USL")):
        visible_segments: list[tuple[float, float, float, str]] = []
        for start, end, value, scope in _spec_segments(
            relevant_specs, layout, numeric, column
        ):
            scope_label = f" {scope}" if scope else ""
            if y_range is not None and not y_range[0] <= value <= y_range[1]:
                side = "低于显示范围" if value < y_range[0] else "高于显示范围"
                outside_spec_scopes.setdefault((label, value, side), set()).add(scope)
                continue
            visible_segments.append((start, end, value, scope))

        if visible_segments:
            axis.hlines(
                [segment[2] for segment in visible_segments],
                [segment[0] for segment in visible_segments],
                [segment[1] for segment in visible_segments],
                color="#c83e3e",
                linestyle="--",
                linewidth=1.0,
            )
            annotation_segments: dict[
                tuple[float, str], tuple[float, float, float, str]
            ] = {}
            for segment in visible_segments:
                key = (segment[2], segment[3])
                current = annotation_segments.get(key)
                if current is None or segment[1] > current[1]:
                    annotation_segments[key] = segment
            for start, end, value, scope in annotation_segments.values():
                scope_label = f" {scope}" if scope else ""
                axis.annotate(
                    f"{label}{scope_label} {value:g}",
                    xy=(end, value),
                    xytext=(0, 5 if label == "USL" else -5),
                    textcoords="offset points",
                    va="bottom" if label == "USL" else "top",
                    ha="right",
                    color="#b03030",
                    fontproperties=font,
                )

    axis.set_xlim(0, max(len(layout.batches), 1))
    axis.margins(y=0.08)
    centers = np.arange(len(layout.batches), dtype=float) + 0.5
    axis.set_xticks(centers)
    axis.set_xticklabels(
        [batch.lot_id for batch in layout.batches],
        fontproperties=font,
        rotation=(60 if len(layout.batches) > 20 else 35)
        if len(layout.batches) > 10
        or any(len(batch.lot_id) > 18 for batch in layout.batches)
        else 0,
        ha="center",
    )
    axis.set_xlabel(
        "FT 批次（lot_ID）"
        if boxplot
        else "FT 批次内样本展示顺序（按 NUM，非时间轴）",
        fontproperties=font,
    )

    for tick in axis.get_yticklabels():
        tick.set_fontproperties(font)
    parameter_label = _parameter_label(parameter, unit)
    chart_name = "箱体图" if boxplot else "散点图"
    axis.set_title(
        f"{parameter_label} 的{chart_name}",
        fontproperties=_font_properties(15),
        pad=14,
    )
    axis.set_ylabel(parameter_label, fontproperties=font)
    axis.set_axisbelow(True)
    axis.grid(axis="y", color="#eeeeee", linewidth=0.7)
    for boundary in range(1, len(layout.batches)):
        axis.axvline(boundary, color="#eeeeee", linewidth=0.7, zorder=0)
    for spine in axis.spines.values():
        spine.set_color("#aaaaaa")
    axis.tick_params(axis="both", colors="#555555")

    legend_visible = len(layout.batches) <= 20
    if legend_visible:
        axis.legend(
            handles=[
                Patch(color=batch_color(index), label=batch.lot_id)
                for index, batch in enumerate(layout.batches)
            ],
            title="FT 批次",
            prop=font,
            title_fontproperties=font,
            loc="upper left",
            bbox_to_anchor=(1.002, 1.0),
            borderaxespad=0,
        )

    below = above = 0
    if y_range is not None and len(finite):
        below = int(np.count_nonzero(finite < y_range[0]))
        above = int(np.count_nonzero(finite > y_range[1]))
    if boxplot:
        prefix = (
            f"聚焦显示 · 范围外测量值：低于 {below:,} 个，高于 {above:,} 个"
            if y_range is not None
            else f"完整纵轴 · 全部有限测量值 {len(finite):,} 个"
        )
        note = f"{prefix}    |    FT 分组口径：每个完整 lot_ID 一个箱体"
    else:
        note = (
            f"聚焦显示 · 范围外：低于 {below:,} 点，高于 {above:,} 点"
            if y_range is not None
            else f"完整纵轴 · 全量绘制 {len(finite):,} 个有限测量点（不抽样）"
        )
    if relevant_specs is not None and not relevant_specs.empty:
        note += "    |    规格线按 Source_ID 绑定"
    if outside_spec_scopes:
        outside_specs: list[str] = []
        for (label, value, side), scopes in outside_spec_scopes.items():
            named_scopes = sorted(scope for scope in scopes if scope)
            if len(named_scopes) == 1:
                scope_text = f" {named_scopes[0]}"
            elif named_scopes:
                scope_text = f" {len(named_scopes)} 个批次"
            else:
                scope_text = ""
            outside_specs.append(f"{label}{scope_text} {value:g}（{side}）")
        note += "    |    " + "；".join(outside_specs)
    condition_note = ""
    if conditions:
        shown_conditions = "；".join(conditions[:2])
        if len(conditions) > 2:
            shown_conditions += f"；另有 {len(conditions) - 2} 个等价来源条件"
        condition_note = f"测试条件：{shown_conditions}"
    footer_lines = [
        note[index : index + 145] for index in range(0, len(note), 145)
    ]
    if len(footer_lines) > 2:
        footer_lines = footer_lines[:2]
        footer_lines[-1] = footer_lines[-1][:-1] + "…"
    if condition_note:
        if len(condition_note) > 145:
            condition_note = condition_note[:144] + "…"
        footer_lines.append(condition_note)
    for index, footer_line in enumerate(footer_lines):
        y_position = 0.012 + (len(footer_lines) - index - 1) * 0.024
        figure.text(
            0.055,
            y_position,
            footer_line,
            fontproperties=_font_properties(8 if condition_note else 9),
            color="#666666",
        )
    right = 0.86 if legend_visible else 0.99
    bottom = 0.055 + max(0, len(footer_lines) - 1) * 0.025
    figure.tight_layout(pad=1.2, rect=(0, bottom, right, 1))

    render_stats = {
        "valid_count": int(len(finite)),
        "display_count": int(len(finite)),
        "batch_count": int(len(layout.batches)),
        "box_count": int(sum(bool(box) for box in box_statistics)),
        "below_count": below,
        "above_count": above,
        "focus": bool(focus),
        "group_key": "lot_ID",
        "order_key": "NUM",
        "spec_key": "Source_ID",
        "conditions": conditions,
    }
    return figure, render_stats


def _render_png(figure) -> bytes:
    from matplotlib.backends.backend_agg import FigureCanvasAgg

    with _RENDER_LOCK:
        try:
            buffer = BytesIO()
            FigureCanvasAgg(figure).print_png(buffer)
            return buffer.getvalue()
        finally:
            figure.clear()


def render_ft_scatter_png(
    data: pd.DataFrame,
    specs: pd.DataFrame,
    parameter: str,
    layout: FTChartLayout,
    *,
    focus: bool = True,
) -> tuple[bytes, dict]:
    with _RENDER_LOCK:
        figure, stats = make_ft_distribution_figure(
            data, specs, parameter, layout, focus=focus, boxplot=False
        )
        return _render_png(figure), stats


def render_ft_boxplot_png(
    data: pd.DataFrame,
    specs: pd.DataFrame,
    parameter: str,
    layout: FTChartLayout,
    *,
    focus: bool = True,
) -> tuple[bytes, dict]:
    with _RENDER_LOCK:
        figure, stats = make_ft_distribution_figure(
            data, specs, parameter, layout, focus=focus, boxplot=True
        )
        return _render_png(figure), stats


def safe_png_name(parameter: str, chart_name: str) -> str:
    """Create a Windows-safe download name without changing chart identity."""

    cleaned = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "_", str(parameter)).strip(" .")
    cleaned = cleaned or "parameter"
    return f"{cleaned}_{chart_name}.png"
