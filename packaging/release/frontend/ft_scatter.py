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
DEFAULT_POINT_LIMIT = 8_000


def _relative_path(target: Path, base: Path) -> str:
    return target.resolve().relative_to(base.resolve()).as_posix()


def export_scatter_bundle(
    data: pd.DataFrame,
    specs: pd.DataFrame,
    output_dir: Path | str,
    *,
    cleaned_file: Path | str,
    factory: str = "日月新（ASE）",
    data_type: str = "DC",
) -> Path:
    """Write a portable scatter bundle and return its manifest path.

    The data table stays wide so one cleaned value is written only once.  Paths
    in the manifest are relative to the run directory, allowing the complete
    output directory to be moved to another computer.
    """
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    cleaned_file = Path(cleaned_file).resolve()

    required = {"NUM", "lot_ID", "Source_ID"}
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(f"散点图数据缺少必要列: {', '.join(sorted(missing))}")
    if data.empty:
        raise ValueError("散点图数据为空")

    parameters = [column for column in data.columns if column not in IDENTIFIER_COLUMNS]
    if not parameters:
        raise ValueError("散点图数据中没有测试参数")

    data_file = output_dir / "ft_scatter_data.csv.gz"
    spec_file = output_dir / "ft_scatter_spec.csv"
    manifest_file = output_dir / "ft_scatter_manifest.json"

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


def prepare_parameter_points(
    data: pd.DataFrame,
    specs: pd.DataFrame,
    parameter: str,
    *,
    point_limit: int = DEFAULT_POINT_LIMIT,
) -> tuple[pd.DataFrame, dict]:
    """Return display points while retaining every out-of-spec observation."""
    if parameter not in data.columns:
        raise KeyError(parameter)

    points = data[["NUM", "lot_ID", "Source_ID", parameter]].copy()
    points[parameter] = pd.to_numeric(points[parameter], errors="coerce")
    points.dropna(subset=[parameter], inplace=True)
    points.sort_values("NUM", kind="stable", inplace=True)

    relevant_specs = specs.loc[specs["Parameter"] == parameter].copy()
    for column in ("Low_Limit", "High_Limit"):
        relevant_specs[column] = pd.to_numeric(relevant_specs[column], errors="coerce")
    limit_lookup = (
        relevant_specs.drop_duplicates("Source_ID", keep="last")
        .set_index("Source_ID")[["Low_Limit", "High_Limit"]]
        .to_dict("index")
    )

    def is_oos(row) -> bool:
        limits = limit_lookup.get(str(row["Source_ID"]), {})
        low = limits.get("Low_Limit")
        high = limits.get("High_Limit")
        value = row[parameter]
        return bool((pd.notna(low) and value < low) or (pd.notna(high) and value > high))

    points["_oos"] = points.apply(is_oos, axis=1)
    oos = points.loc[points["_oos"]]
    in_spec = points.loc[~points["_oos"]]
    allowance = max(point_limit - len(oos), 0)
    sampled = _even_sample(in_spec, allowance)
    displayed = pd.concat([oos, sampled], ignore_index=False).sort_values("NUM", kind="stable")
    stats = {
        "valid_count": int(len(points)),
        "display_count": int(len(displayed)),
        "oos_count": int(len(oos)),
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
    palette = ["#4da3ff", "#20c77a", "#ff9f1c", "#9b59b6", "#f05d5e", "#38bdf8"]

    sources = [str(value) for value in data["Source_ID"].dropna().drop_duplicates()]
    for index, source in enumerate(sources):
        group = displayed.loc[displayed["Source_ID"].astype(str) == source]
        if group.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=group["NUM"],
                y=group[parameter],
                mode="markers",
                name=source,
                marker={"size": 5, "color": palette[index % len(palette)], "opacity": 0.78},
                customdata=group[["lot_ID", "Source_ID", "_oos"]],
                hovertemplate=(
                    "C1=%{x}<br>数值=%{y}<br>Lot=%{customdata[0]}"
                    "<br>来源=%{customdata[1]}<br>超限=%{customdata[2]}<extra></extra>"
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
                segments.append(
                    (float(source_rows["NUM"].min()), float(source_rows["NUM"].max()), spec[column], f"{label} {spec['Source_ID']}")
                )
        for start, end, value, segment_label in segments:
            figure.add_trace(
                go.Scatter(
                    x=[start, end],
                    y=[value, value],
                    mode="lines+text",
                    line={"color": "#ff4d4f", "width": 1.5, "dash": "dash"},
                    text=[None, f"{segment_label} {value:g}"],
                    textposition="top left",
                    textfont={"color": "#ff8080", "size": 11},
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

    figure.update_layout(
        title={"text": parameter_title(specs, parameter), "x": 0.01, "xanchor": "left"},
        paper_bgcolor="#182737",
        plot_bgcolor="#132231",
        font={"color": "#cbd5e1", "size": 12},
        height=560,
        margin={"l": 70, "r": 95, "t": 70, "b": 70},
        legend={"orientation": "v", "x": 1.01, "y": 1},
        hovermode="closest",
    )
    figure.add_annotation(
        text=parameter_limit_summary(specs, parameter),
        x=1,
        y=1.08,
        xref="paper",
        yref="paper",
        xanchor="right",
        yanchor="bottom",
        showarrow=False,
        font={"color": "#ff9393", "size": 11},
    )
    figure.update_xaxes(
        title="C1（测试序号）",
        gridcolor="#2b4255",
        zeroline=False,
        showline=True,
        linecolor="#496174",
    )
    figure.update_yaxes(
        title=parameter,
        gridcolor="#2b4255",
        zeroline=False,
        showline=True,
        linecolor="#496174",
    )
    return figure, stats
