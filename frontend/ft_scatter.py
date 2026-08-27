#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""FT scatter bundle export, loading, sampling, and Plotly figure helpers."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable

import pandas as pd


IDENTIFIER_COLUMNS = {"NUM", "lot_ID", "Source_ID"}
DEFAULT_POINT_LIMIT = 4_000
DEFAULT_DUPLICATE_LIMIT = 32
LOT_COLORS = [
    "#2563eb",
    "#16a34a",
    "#ea580c",
    "#9333ea",
    "#0891b2",
    "#ca8a04",
    "#475569",
    "#0d9488",
    "#4f46e5",
    "#65a30d",
    "#c026d3",
    "#7c3aed",
    "#0284c7",
    "#15803d",
    "#a16207",
    "#334155",
]


def _relative_path(target: Path, base: Path) -> str:
    return target.resolve().relative_to(base.resolve()).as_posix()


def export_scatter_bundle(
    data: pd.DataFrame,
    specs: pd.DataFrame,
    output_dir: Path | str,
    *,
    cleaned_file: Path | str,
    factory: str = "日月新（Riyuexin）",
    data_type: str = "DC",
    bundle_stem: str = "ft_scatter",
) -> Path:
    """Write a portable scatter bundle and return its manifest path.

    The data table stays wide so one cleaned value is written only once.  Paths
    in the manifest are relative to the run directory, allowing the complete
    output directory to be moved to another computer.
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned_file = Path(cleaned_file).resolve()
    bundle_stem = str(bundle_stem).strip()
    if (
        not bundle_stem
        or bundle_stem in {".", ".."}
        or Path(bundle_stem).name != bundle_stem
    ):
        raise ValueError(f"散点图数据包名称非法: {bundle_stem!r}")

    required = {"NUM", "lot_ID", "Source_ID"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"散点图数据缺少必要列: {', '.join(sorted(missing))}")
    if data.empty:
        raise ValueError("散点图数据为空")

    parameters = [column for column in data.columns if column not in IDENTIFIER_COLUMNS]
    if not parameters:
        raise ValueError("散点图数据中没有测试参数")

    data_file = output_dir / f"{bundle_stem}_data.csv.gz"
    spec_file = output_dir / f"{bundle_stem}_spec.csv"
    manifest_file = output_dir / f"{bundle_stem}_manifest.json"

    data.to_csv(data_file, index=False, encoding="utf-8-sig", compression="gzip")
    specs.to_csv(spec_file, index=False, encoding="utf-8-sig")

    manifest = {
        "schema_version": 1,
        "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "factory": factory,
        "data_type": data_type,
        "cleaned_file": _relative_path(cleaned_file, output_dir),
        "data_file": _relative_path(data_file, output_dir),
        "spec_file": _relative_path(spec_file, output_dir),
        "row_count": int(len(data)),
        "parameters": parameters,
        "sources": [str(value) for value in data["Source_ID"].dropna().drop_duplicates()],
        "lots": [str(value) for value in data["lot_ID"].dropna().drop_duplicates()],
    }
    manifest_file.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return manifest_file


def _resolve_manifest_child(manifest_path: Path, relative_path: str) -> Path:
    base = manifest_path.resolve().parent
    child = (base / relative_path).resolve()
    try:
        child.relative_to(base)
    except ValueError as exc:
        raise ValueError(f"散点图清单包含非法路径: {relative_path}") from exc
    if not child.is_file():
        raise FileNotFoundError(f"散点图文件不存在: {child}")
    return child


def load_scatter_bundle(manifest_path: Path | str) -> tuple[dict, pd.DataFrame, pd.DataFrame]:
    """Load and validate one scatter bundle from its explicit manifest."""
    manifest_path = Path(manifest_path).resolve()
    if not manifest_path.is_file():
        raise FileNotFoundError(f"散点图清单不存在: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("schema_version") != 1:
        raise ValueError("不支持的散点图数据版本")

    data_file = _resolve_manifest_child(manifest_path, manifest["data_file"])
    spec_file = _resolve_manifest_child(manifest_path, manifest["spec_file"])
    data = pd.read_csv(data_file, compression="gzip", low_memory=False)
    specs = pd.read_csv(spec_file, keep_default_na=False)
    for column in ("Low_Limit", "High_Limit"):
        if column in specs.columns:
            specs[column] = pd.to_numeric(specs[column], errors="coerce")

    required = {"NUM", "lot_ID", "Source_ID"}
    if not required.issubset(data.columns):
        raise ValueError("散点图数据列不完整")
    expected_parameters = manifest.get("parameters", [])
    missing_parameters = [name for name in expected_parameters if name not in data.columns]
    if missing_parameters:
        raise ValueError(f"散点图参数列缺失: {', '.join(missing_parameters)}")
    return manifest, data, specs


def _even_sample(frame: pd.DataFrame, count: int) -> pd.DataFrame:
    """Deterministically retain evenly distributed rows from an ordered frame."""
    if count <= 0:
        return frame.iloc[0:0]
    if len(frame) <= count:
        return frame
    positions = [min(int(index * len(frame) / count), len(frame) - 1) for index in range(count)]
    return frame.iloc[positions]


def _stratified_even_sample(
    frame: pd.DataFrame, count: int, *, group_column: str
) -> pd.DataFrame:
    """Sample deterministically per group, retaining every non-empty group."""
    if frame.empty or count <= 0:
        return frame.iloc[0:0]
    if len(frame) <= count:
        return frame

    groups = [group for _, group in frame.groupby(group_column, sort=False, dropna=False)]
    count = min(len(frame), max(count, len(groups)))
    allocations = [1] * len(groups)
    remaining = count - len(groups)
    capacities = [len(group) - 1 for group in groups]
    total_capacity = sum(capacities)
    if remaining > 0 and total_capacity > 0:
        exact_extras = [remaining * capacity / total_capacity for capacity in capacities]
        base_extras = [
            min(capacity, int(extra))
            for capacity, extra in zip(capacities, exact_extras)
        ]
        allocations = [base + extra for base, extra in zip(allocations, base_extras)]
        leftover = remaining - sum(base_extras)
        order = sorted(
            range(len(groups)),
            key=lambda index: (exact_extras[index] - base_extras[index], -index),
            reverse=True,
        )
        for index in order:
            if leftover <= 0:
                break
            if allocations[index] < len(groups[index]):
                allocations[index] += 1
                leftover -= 1

    sampled_groups = [
        _even_sample(group, allocation)
        for group, allocation in zip(groups, allocations)
    ]
    return pd.concat(sampled_groups, ignore_index=False)


def _lot_color(index: int) -> str:
    if index < len(LOT_COLORS):
        return LOT_COLORS[index]
    hue = (211 + (index - len(LOT_COLORS)) * 137.508) % 360
    if hue < 25 or hue > 340:
        hue = (hue + 42) % 360
    return f"hsl({hue:.1f}, 68%, 43%)"


def prepare_parameter_points(
    data: pd.DataFrame,
    specs: pd.DataFrame,
    parameter: str,
    *,
    point_limit: int = DEFAULT_POINT_LIMIT,
    max_duplicate_points: int = DEFAULT_DUPLICATE_LIMIT,
) -> tuple[pd.DataFrame, dict]:
    """Return representative display points while retaining every OOS point.

    In-spec rows with the same lot and exact measurement value are visually
    indistinguishable except for their X position.  Keep evenly distributed
    representatives from each such group before applying a soft display cap.
    The cap may be exceeded to retain every OOS point and at least one
    representative point from each batch.
    """
    if parameter not in data.columns:
        raise KeyError(parameter)

    points = data[["NUM", "lot_ID", "Source_ID", parameter]].copy()
    points[parameter] = pd.to_numeric(points[parameter], errors="coerce")
    points.dropna(subset=[parameter], inplace=True)
    points.sort_values("NUM", kind="stable", inplace=True)

    relevant_specs = specs.loc[specs["Parameter"] == parameter].copy()
    for column in ("Low_Limit", "High_Limit"):
        relevant_specs[column] = pd.to_numeric(relevant_specs[column], errors="coerce")
    limit_table = relevant_specs.drop_duplicates("Source_ID", keep="last").copy()
    limit_table["_source_key"] = limit_table["Source_ID"].astype(str)
    limit_table.set_index("_source_key", inplace=True)
    source_keys = points["Source_ID"].astype(str)
    low_limits = source_keys.map(limit_table["Low_Limit"])
    high_limits = source_keys.map(limit_table["High_Limit"])
    points["_oos"] = (
        (low_limits.notna() & points[parameter].lt(low_limits))
        | (high_limits.notna() & points[parameter].gt(high_limits))
    )
    oos = points.loc[points["_oos"]]
    in_spec = points.loc[~points["_oos"]]
    if max_duplicate_points > 0 and not in_spec.empty:
        groups = in_spec.groupby(["lot_ID", parameter], sort=False, dropna=False)
        group_sizes = groups[parameter].transform("size")
        group_positions = groups.cumcount()
        current_bucket = group_positions.mul(max_duplicate_points).floordiv(group_sizes)
        previous_bucket = (
            group_positions.sub(1).mul(max_duplicate_points).floordiv(group_sizes)
        )
        keep = group_sizes.le(max_duplicate_points) | current_bucket.ne(previous_bucket)
        compact_in_spec = in_spec.loc[keep]
    else:
        compact_in_spec = in_spec
    allowance = max(point_limit - len(oos), 0)
    in_spec_lot_count = compact_in_spec["lot_ID"].nunique(dropna=False)
    sample_count = max(allowance, in_spec_lot_count)
    sampled = _stratified_even_sample(
        compact_in_spec, sample_count, group_column="lot_ID"
    )
    displayed = pd.concat([oos, sampled], ignore_index=False).sort_values("NUM", kind="stable")
    stats = {
        "valid_count": int(len(points)),
        "display_count": int(len(displayed)),
        "oos_count": int(len(oos)),
        "duplicate_reduction_count": int(len(in_spec) - len(compact_in_spec)),
        "point_limit": int(point_limit),
    }
    return displayed, stats


def _first_nonempty(values: Iterable) -> str:
    for value in values:
        text = str(value).strip()
        if text and text.lower() != "nan":
            return text
    return ""


def parameter_title(specs: pd.DataFrame, parameter: str) -> str:
    relevant = specs.loc[specs["Parameter"] == parameter]
    if relevant.empty:
        return parameter
    condition = _first_nonempty(relevant.get("Test_Condition", []))
    return f"{parameter} · {condition}" if condition else parameter


def parameter_limit_summary(specs: pd.DataFrame, parameter: str) -> str:
    """Format distinct source limits, explicitly showing an absent limit as N/A."""
    relevant = specs.loc[specs["Parameter"] == parameter]
    parts = []
    for column, label in (("Low_Limit", "LSL"), ("High_Limit", "USL")):
        values = pd.to_numeric(relevant.get(column, pd.Series(dtype=float)), errors="coerce")
        unique = sorted(set(float(value) for value in values.dropna()))
        display = "/".join(f"{value:g}" for value in unique) if unique else "N/A"
        parts.append(f"{label} {display}")
    return " ｜ ".join(parts)


def build_parameter_figure(
    data: pd.DataFrame,
    specs: pd.DataFrame,
    parameter: str,
    *,
    point_limit: int = DEFAULT_POINT_LIMIT,
):
    """Build one SVG Plotly scatter figure for one FT parameter."""
    import plotly.graph_objects as go

    displayed, stats = prepare_parameter_points(
        data, specs, parameter, point_limit=point_limit
    )
    figure = go.Figure()
    lots = [str(value) for value in data["lot_ID"].dropna().drop_duplicates()]
    for index, lot_id in enumerate(lots):
        group = displayed.loc[displayed["lot_ID"].astype(str) == lot_id]
        if group.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=group["NUM"],
                y=group[parameter],
                mode="markers",
                name=lot_id,
                marker={
                    "size": 7,
                    "color": _lot_color(index),
                    "opacity": 0.82,
                    "line": {"color": "rgba(255,255,255,0.75)", "width": 0.35},
                },
                customdata=group[["_oos"]],
                hovertemplate=(
                    "C1=%{x}<br>数值=%{y}<br>批次=%{fullData.name}"
                    "<br>超限=%{customdata[0]}<extra></extra>"
                ),
            )
        )

    relevant_specs = specs.loc[specs["Parameter"] == parameter].copy()
    for column in ("Low_Limit", "High_Limit"):
        relevant_specs[column] = pd.to_numeric(relevant_specs[column], errors="coerce")

    x_min = float(pd.to_numeric(data["NUM"], errors="coerce").min())
    x_max = float(pd.to_numeric(data["NUM"], errors="coerce").max())
    for column, label in (("Low_Limit", "LSL"), ("High_Limit", "USL")):
        non_null = relevant_specs.dropna(subset=[column])
        unique_limits = non_null[column].drop_duplicates().tolist()
        if len(unique_limits) == 1:
            segments = [(x_min, x_max, unique_limits[0], label)]
        else:
            segments = []
            for _, spec in non_null.drop_duplicates("Source_ID", keep="last").iterrows():
                source_rows = data.loc[data["Source_ID"].astype(str) == str(spec["Source_ID"])]
                if source_rows.empty:
                    continue
                lot_label = str(spec.get("lot_ID", "")).strip() or str(spec["Source_ID"])
                segments.append(
                    (float(source_rows["NUM"].min()), float(source_rows["NUM"].max()), spec[column], f"{label} {lot_label}")
                )
        for start, end, value, segment_label in segments:
            figure.add_trace(
                go.Scatter(
                    x=[start, end],
                    y=[value, value],
                    mode="lines+text",
                    line={"color": "#dc2626", "width": 1.8, "dash": "dash"},
                    text=[None, f"{segment_label} {value:g}"],
                    textposition="top left",
                    textfont={"color": "#b91c1c", "size": 14},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    figure.update_layout(
        title={
            "text": f"<b>{parameter_title(specs, parameter)}</b>",
            "x": 0.01,
            "xanchor": "left",
            "font": {"color": "#172033", "size": 22},
        },
        paper_bgcolor="#ffffff",
        plot_bgcolor="#f8fafc",
        font={
            "color": "#27364a",
            "size": 15,
            "family": "Segoe UI, Microsoft YaHei, sans-serif",
        },
        height=600,
        margin={"l": 82, "r": 178, "t": 108, "b": 82},
        showlegend=True,
        legend={
            "title": {"text": "批次", "font": {"size": 15, "color": "#172033"}},
            "orientation": "v",
            "x": 1.015,
            "y": 1,
            "xanchor": "left",
            "yanchor": "top",
            "font": {"size": 15, "color": "#27364a"},
            "bgcolor": "rgba(255,255,255,0.88)",
            "bordercolor": "#d8e2ec",
            "borderwidth": 1,
            "itemsizing": "constant",
        },
        hoverlabel={
            "bgcolor": "#ffffff",
            "bordercolor": "#2563eb",
            "font": {"color": "#172033", "size": 14},
        },
        modebar={
            "bgcolor": "rgba(255,255,255,0)",
            "color": "#64748b",
            "activecolor": "#2563eb",
        },
        hovermode="closest",
    )
    figure.add_annotation(
        text=parameter_limit_summary(specs, parameter),
        x=1,
        y=1.02,
        xref="paper",
        yref="paper",
        xanchor="right",
        yanchor="bottom",
        showarrow=False,
        font={"color": "#b91c1c", "size": 14},
    )
    figure.update_xaxes(
        title="C1（测试序号）",
        title_font={"size": 17, "color": "#27364a"},
        tickfont={"size": 15, "color": "#334155"},
        gridcolor="#dbe4ee",
        gridwidth=1,
        zeroline=False,
        showline=True,
        linecolor="#94a3b8",
        tickcolor="#94a3b8",
        ticks="outside",
    )
    figure.update_yaxes(
        title="",
        tickfont={"size": 15, "color": "#334155"},
        gridcolor="#dbe4ee",
        gridwidth=1,
        zeroline=False,
        showline=True,
        linecolor="#94a3b8",
        tickcolor="#94a3b8",
        ticks="outside",
    )
    return figure, stats
