#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Streamlit entry for FT static scatter and box charts."""

from __future__ import annotations

import os
from hashlib import sha256
from pathlib import Path
from time import perf_counter

import streamlit as st

from frontend.ft_scatter import (
    load_scatter_bundle,
    load_scatter_manifest,
    scatter_bundle_signature,
)
from frontend.ft_static_charts import (
    prepare_ft_chart_layout,
    render_ft_boxplot_png,
    render_ft_scatter_png,
    safe_png_name,
    validate_y_limits,
)


def _manifest_argument() -> str:
    try:
        value = st.query_params.get("manifest", "")
        if isinstance(value, list):
            value = value[-1] if value else ""
    except AttributeError:
        value = st.experimental_get_query_params().get("manifest", [""])[-1]
    return str(value or os.environ.get("FT_SCATTER_MANIFEST", "")).strip()


@st.cache_resource(show_spinner=False, max_entries=1)
def _load_chart_data(manifest_path: str, bundle_signature: tuple):
    del bundle_signature
    manifest, data, specs = load_scatter_bundle(Path(manifest_path))
    layout = prepare_ft_chart_layout(data)
    return manifest, data, specs, layout


st.set_page_config(page_title="FT 参数图表", page_icon="📊", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: #f3f6fa; color: #1f2937; }
      .block-container { max-width: 1900px; padding: 1.25rem 1.3rem 3rem; }
      h1, h2, h3 { color:#172033; }
      .chart-summary { color:#52657a; font-size:1.05rem; margin-bottom:1rem; }
      [data-testid="stImage"] { background:#ffffff; border:1px solid #d8e2ec;
        border-radius:14px; padding:10px; margin-bottom:8px;
        box-shadow:0 4px 14px rgba(30, 64, 99, 0.08); }
      [data-testid="stCaptionContainer"] { color:#52657a; font-size:0.98rem; }
      [data-testid="stCaptionContainer"] p { font-size:0.98rem; }
      [data-testid="stForm"] { border:0; padding:0; }
      [data-testid="stForm"] [data-testid="stHorizontalBlock"] { align-items:center; }
    </style>
    """,
    unsafe_allow_html=True,
)

manifest_argument = _manifest_argument()
if not manifest_argument:
    st.error("没有指定 FT 图表数据清单。请从 FT 数据清洗工具点击“散点图 / 箱体图”。")
    st.stop()

manifest_path = Path(manifest_argument).resolve()
try:
    manifest = load_scatter_manifest(manifest_path)
    bundle_signature = scatter_bundle_signature(manifest_path, manifest)
except Exception as exc:
    st.error(f"FT 图表清单读取失败：{exc}")
    st.stop()

parameters = list(manifest.get("parameters", []))
if not parameters:
    st.error("当前清洗结果没有可显示的测试参数。")
    st.stop()

st.title(f"{manifest.get('factory', 'FT')} {manifest.get('data_type', '')} 参数图表")
st.markdown(
    f"<div class='chart-summary'>数据行数：{int(manifest.get('row_count', 0)):,} "
    f"｜ 来源文件：{len(manifest.get('sources', []))} "
    f"｜ 批次：{len(manifest.get('lots', []))} ｜ 参数：{len(parameters)}</div>",
    unsafe_allow_html=True,
)
st.info(
    "FT 分组保持不变：完整 lot_ID 是批次与箱体分组；NUM 仅表示批次内样本展示顺序；"
    "Source_ID 仅用于来源追溯和规格绑定。不会生成或套用 Wafer_ID。"
)

st.subheader("图表筛选")
selected_parameters = st.multiselect(
    "选择参数",
    parameters,
    default=parameters,
    help="可一次选择多个参数；点击“绘制图形”后逐参数生成静态 PNG。",
)
control_left, control_middle, control_right = st.columns([1.0, 1.15, 1.15])
with control_left:
    chart_type = st.radio(
        "图表类型", ["散点图", "箱体图"], horizontal=True, key="ft_chart_type"
    )
with control_middle:
    scatter_full_range = st.checkbox(
        "散点图显示完整纵轴范围",
        value=False,
        key="ft_scatter_full_y_range",
        help="只改变散点图视窗；全部有限测量值始终参与绘制。",
    )
with control_right:
    box_full_range = st.checkbox(
        "箱体图显示完整纵轴范围",
        value=False,
        key="ft_boxplot_full_y_range",
        help="只改变箱体图视窗；Q1、中位数、Q3 和箱须始终使用该批次全部有限值。",
    )

selection_signature = (
    str(manifest_path),
    bundle_signature,
    tuple(selected_parameters),
)
if st.button("绘制图形", type="primary", use_container_width=True):
    st.session_state["ft_chart_render_signature"] = selection_signature

if not selected_parameters:
    st.warning("请至少选择一个参数。")
    st.stop()

if st.session_state.get("ft_chart_render_signature") != selection_signature:
    st.caption("首次打开或筛选变化后不会沿用旧图，请点击“绘制图形”。")
    st.stop()

load_start = perf_counter()
try:
    _, data, specs, layout = _load_chart_data(
        str(manifest_path), selection_signature[1]
    )
except Exception as exc:
    st.error(f"FT 图表数据读取失败：{exc}")
    st.stop()
load_elapsed = perf_counter() - load_start

st.subheader(chart_type)

render_total = 0.0
png_total = 0
cache_scope = (str(manifest_path), bundle_signature, "ft-static-v2.22.0")
if st.session_state.get("ft_png_cache_scope") != cache_scope:
    st.session_state["ft_png_cache_scope"] = cache_scope
    st.session_state["ft_png_cache"] = {}
png_cache = st.session_state.setdefault("ft_png_cache", {})
if st.session_state.get("ft_y_settings_scope") != bundle_signature:
    st.session_state["ft_y_settings_scope"] = bundle_signature
    st.session_state["ft_y_settings"] = {}
y_settings = st.session_state.setdefault("ft_y_settings", {})
for parameter in selected_parameters:
    try:
        setting_key = (chart_type, parameter)
        saved = y_settings.get(setting_key, (False, "", ""))
        widget_key = sha256(repr((bundle_signature, setting_key)).encode()).hexdigest()
        if len(selected_parameters) > 1:
            st.markdown(f"**{parameter}**")
        with st.form(f"y_range_{widget_key}"):
            enabled_column, lower_label, lower_column, upper_label, upper_column, apply_column = st.columns(
                [1.5, 0.85, 1.5, 0.85, 1.5, 1.8]
            )
            with enabled_column:
                custom_enabled = st.checkbox("自定义 Y 轴范围", value=saved[0])
            with lower_label:
                st.markdown("Y 轴最小值")
            with lower_column:
                lower_text = st.text_input(
                    "Y 轴最小值", value=saved[1], placeholder="输入数值", label_visibility="collapsed"
                )
            with upper_label:
                st.markdown("Y 轴最大值")
            with upper_column:
                upper_text = st.text_input(
                    "Y 轴最大值", value=saved[2], placeholder="输入数值", label_visibility="collapsed"
                )
            with apply_column:
                submitted = st.form_submit_button("应用自定义并绘制", type="primary", use_container_width=True)
            if submitted:
                saved = (custom_enabled, lower_text, upper_text)
                y_settings[setting_key] = saved
        y_limits = validate_y_limits((saved[1], saved[2])) if saved[0] else None
        focus = not (scatter_full_range if chart_type == "散点图" else box_full_range)
        cache_key = (chart_type, parameter, focus, y_limits)
        cached = cache_key in png_cache
        if cached:
            png, stats = png_cache[cache_key]
            render_elapsed = 0.0
        else:
            render_start = perf_counter()
            if chart_type == "散点图":
                png, stats = render_ft_scatter_png(
                    data,
                    specs,
                    parameter,
                    layout,
                    focus=focus,
                    y_limits=y_limits,
                )
            else:
                png, stats = render_ft_boxplot_png(
                    data,
                    specs,
                    parameter,
                    layout,
                    focus=focus,
                    y_limits=y_limits,
                )
            render_elapsed = perf_counter() - render_start
            if len(png_cache) >= 64:
                png_cache.pop(next(iter(png_cache)))
            png_cache[cache_key] = (png, stats)
        render_total += render_elapsed
        png_total += len(png)
        st.image(png, use_column_width=True)
        conditions = stats.get("conditions", ())
        condition_text = (
            " ｜ 测试条件：" + "；".join(conditions[:3])
            if conditions
            else ""
        )
        if len(conditions) > 3:
            condition_text += f"；另有 {len(conditions) - 3} 种"
        chart_detail = (
            f"箱体 {stats['box_count']:,} 个"
            if chart_type == "箱体图"
            else f"绘制点 {stats['display_count']:,} 个"
        )
        st.caption(
            f"有效值 {stats['valid_count']:,} ｜ {chart_detail} ｜ 批次 {stats['batch_count']:,} "
            f"｜ {'自定义' if y_limits is not None else '自动'} Y 轴："
            f"{stats['y_limits'][0]:g} ～ {stats['y_limits'][1]:g} "
            f"｜ {'缓存复用' if cached else f'生成 {render_elapsed:.3f} 秒'} "
            f"｜ PNG {len(png) / 1024:.1f} KiB"
            f"{condition_text}"
        )
        st.download_button(
            f"下载 {parameter} {chart_type} PNG",
            data=png,
            file_name=safe_png_name(parameter, chart_type),
            mime="image/png",
            key=f"download_{chart_type}_{parameter}",
        )
    except Exception as exc:
        st.warning(f"{parameter} {chart_type}生成失败：{exc}")

st.caption(
    f"数据读取/索引准备：{load_elapsed:.3f} 秒 ｜ 图片生成：{render_total:.3f} 秒 "
    f"｜ PNG 合计：{png_total / 1024 / 1024:.2f} MiB ｜ 不生成临时图形文件"
)
