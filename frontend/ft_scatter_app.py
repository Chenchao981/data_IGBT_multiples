#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""Streamlit entry for FT parameter scatter charts."""

from __future__ import annotations

import os
from pathlib import Path

import streamlit as st

from frontend.ft_scatter import build_parameter_figure, load_scatter_bundle


def _manifest_argument() -> str:
    try:
        value = st.query_params.get("manifest", "")
        if isinstance(value, list):
            value = value[-1] if value else ""
    except AttributeError:
        value = st.experimental_get_query_params().get("manifest", [""])[-1]
    return str(value or os.environ.get("FT_SCATTER_MANIFEST", "")).strip()


st.set_page_config(page_title="FT 参数散点图", page_icon="📊", layout="wide")
st.markdown(
    """
    <style>
      .stApp { background: #f3f6fa; color: #1f2937; }
      .block-container { max-width: 1600px; padding: 1.25rem 1.3rem 3rem; }
      [data-testid="stPlotlyChart"] { background:#ffffff; border:1px solid #d8e2ec;
        border-radius:14px; padding:10px; margin-bottom:18px;
        box-shadow:0 4px 14px rgba(30, 64, 99, 0.08); }
      h1 { color:#172033; font-size:2rem !important; }
      .scatter-summary { color:#52657a; font-size:1.05rem; margin-bottom:1rem; }
      [data-testid="stCaptionContainer"] { color:#52657a; font-size:0.98rem; }
      [data-testid="stCaptionContainer"] p { font-size:0.98rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

manifest_argument = _manifest_argument()
if not manifest_argument:
    st.error("没有指定散点图数据清单。请从 FT 数据清洗工具点击“FT 散点图”。")
    st.stop()

try:
    manifest, data, specs = load_scatter_bundle(Path(manifest_argument))
except Exception as exc:
    st.error(f"散点图数据读取失败：{exc}")
    st.stop()

st.title(f"{manifest.get('factory', 'FT')} {manifest.get('data_type', '')} 参数散点图")
st.markdown(
    f"<div class='scatter-summary'>数据行数：{len(data):,} ｜ 来源文件：{len(manifest.get('sources', []))} "
    f"｜ 批次：{data['lot_ID'].nunique()} ｜ 参数：{len(manifest.get('parameters', []))}</div>",
    unsafe_allow_html=True,
)

if not manifest.get("parameters", []):
    st.error("当前清洗结果没有可显示的测试参数。")
    st.stop()

for parameter in manifest.get("parameters", []):
    try:
        figure, stats = build_parameter_figure(data, specs, parameter)
        st.plotly_chart(
            figure,
            use_container_width=True,
            config={"displaylogo": False, "scrollZoom": True, "responsive": True},
            key=f"ft_scatter_{parameter}",
        )
        st.caption(
            f"有效点 {stats['valid_count']:,} ｜ 实际绘制 {stats['display_count']:,} "
            f"｜ 重复点优化 {stats['duplicate_reduction_count']:,} "
            f"｜ 超限点 {stats['oos_count']:,}（全部保留）"
        )
    except Exception as exc:
        st.warning(f"{parameter} 生成失败：{exc}")
