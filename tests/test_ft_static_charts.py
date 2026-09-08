import struct
import os
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd
from matplotlib.collections import LineCollection, PathCollection
from PIL import Image
from streamlit.testing.v1 import AppTest

from frontend.ft_scatter import export_scatter_bundle
from frontend.ft_static_charts import (
    batch_color,
    focused_y_range,
    ft_batch_box_statistics,
    make_ft_distribution_figure,
    parameter_values,
    prepare_ft_chart_layout,
    render_ft_boxplot_png,
    render_ft_scatter_png,
    safe_png_name,
    validate_y_limits,
)


def _specs(source_ids, *, low=None, high=None, units=None):
    size = len(source_ids)
    return pd.DataFrame(
        {
            "Source_ID": source_ids,
            "Parameter": ["P"] * size,
            "Unit": units if units is not None else ["V"] * size,
            "Low_Limit": low if low is not None else [None] * size,
            "High_Limit": high if high is not None else [None] * size,
            "Test_Condition": ["ID=250uA"] * size,
        }
    )


class FTStaticChartContractTests(unittest.TestCase):
    def test_manual_y_limits_are_exact_and_preserve_box_statistics(self):
        data = pd.DataFrame({"NUM": range(1, 6), "lot_ID": ["A"] * 5,
                             "Source_ID": ["S"] * 5, "P": [-10., 1., 2., 3., 100.]})
        original = data.copy(deep=True)
        layout = prepare_ft_chart_layout(data)
        specs = _specs(["S"], low=[-20.], high=[200.])
        for boxplot in (False, True):
            automatic, auto_stats = make_ft_distribution_figure(
                data, specs, "P", layout, boxplot=boxplot, focus=False
            )
            for focus in (False, True):
                manual, stats = make_ft_distribution_figure(
                    data, specs, "P", layout, boxplot=boxplot, focus=focus, y_limits=(1., 3.)
                )
                try:
                    self.assertEqual(manual.axes[0].get_ylim(), (1., 3.))
                    self.assertEqual(stats["below_count"], 1)
                    self.assertEqual(stats["above_count"], 1)
                    self.assertEqual(stats["valid_count"], auto_stats["valid_count"])
                    self.assertEqual(stats["box_count"], auto_stats["box_count"])
                    self.assertTrue(any("自定义 Y 轴" in text.get_text() for text in manual.texts))
                    if boxplot:
                        for old, new in zip(automatic.axes[0].lines, manual.axes[0].lines):
                            np.testing.assert_array_equal(old.get_ydata(), new.get_ydata())
                finally:
                    manual.clear()
            automatic.clear()
        for renderer in (render_ft_scatter_png, render_ft_boxplot_png):
            png, stats = renderer(data, specs, "P", layout, y_limits=(-1e-6, 5e-6))
            self.assertTrue(png.startswith(b"\x89PNG"))
            self.assertEqual(stats["y_limits"], (-1e-6, 5e-6))
        pd.testing.assert_frame_equal(data, original)

    def test_manual_y_limits_reject_invalid_bounds(self):
        self.assertEqual(validate_y_limits(("-1e-6", "2.5e-6")), (-1e-6, 2.5e-6))
        for bounds in (("", "2"), ("abc", 2), (1, 1), (2, 1), (np.nan, 1), (0, np.inf)):
            with self.subTest(bounds=bounds), self.assertRaises(ValueError):
                validate_y_limits(bounds)

    def test_layout_uses_only_complete_lot_and_num_order(self):
        data = pd.DataFrame(
            {
                "NUM": [3, 1, 2, 2, 1],
                "lot_ID": ["LOT-A", "LOT-A", "LOT-A", "LOT-B", "LOT-B"],
                "Source_ID": ["A-1", "A-1", "A-2", "B-1", "B-1"],
                # Deliberately present to prove the FT layout never reads it.
                "Wafer_ID": ["01", "02", "02", "01", "02"],
                "P": [3.0, 1.0, 2.0, 20.0, 10.0],
            }
        )
        layout = prepare_ft_chart_layout(data)

        self.assertEqual([batch.lot_id for batch in layout.batches], ["LOT-A", "LOT-B"])
        self.assertEqual(layout.batches[0].row_positions.tolist(), [1, 2, 0])
        self.assertEqual(layout.batches[1].row_positions.tolist(), [4, 3])
        self.assertEqual(set(layout.source_rows), {"A-1", "A-2", "B-1"})

        figure, stats = make_ft_distribution_figure(
            data, _specs(["A-1", "A-2", "B-1"]), "P", layout, boxplot=True
        )
        try:
            self.assertEqual(stats["group_key"], "lot_ID")
            self.assertEqual(stats["order_key"], "NUM")
            self.assertEqual(stats["spec_key"], "Source_ID")
            self.assertEqual(stats["box_count"], 2)
            self.assertEqual(
                [tick.get_text() for tick in figure.axes[0].get_xticklabels()],
                ["LOT-A", "LOT-B"],
            )
            self.assertNotIn("Wafer", figure.axes[0].get_xlabel())
        finally:
            figure.clear()

    def test_same_lot_multiple_sources_remain_one_box(self):
        data = pd.DataFrame(
            {
                "NUM": [1, 2, 3, 4],
                "lot_ID": ["LOT-A"] * 4,
                "Source_ID": ["A-1", "A-1", "A-2", "A-2"],
                "P": [1.0, 2.0, 3.0, 100.0],
            }
        )
        original = data.copy(deep=True)
        layout = prepare_ft_chart_layout(data)
        numeric = parameter_values(data, "P")
        boxes = ft_batch_box_statistics(numeric, layout.batches)

        self.assertEqual(len(boxes), 1)
        self.assertEqual(
            boxes[0],
            {
                "q1": 1.75,
                "med": 2.5,
                "q3": 27.25,
                "whislo": 1.0,
                "whishi": 3.0,
                "fliers": [],
            },
        )
        pd.testing.assert_frame_equal(data, original)

    def test_scatter_draws_every_finite_value_and_keeps_missing_positions(self):
        data = pd.DataFrame(
            {
                "NUM": [1, 2, 3, 4, 1],
                "lot_ID": ["LOT-A"] * 4 + ["LOT-B"],
                "Source_ID": ["A"] * 4 + ["B"],
                "P": [1.0, np.nan, 2.0, np.inf, 8.0],
            }
        )
        layout = prepare_ft_chart_layout(data)
        figure, stats = make_ft_distribution_figure(
            data, _specs(["A", "B"]), "P", layout
        )
        try:
            paths = [
                collection
                for collection in figure.axes[0].collections
                if isinstance(collection, PathCollection)
            ]
            offsets = [collection.get_offsets() for collection in paths]
            self.assertEqual(sum(len(group) for group in offsets), 3)
            self.assertEqual(stats["valid_count"], 3)
            self.assertEqual(stats["display_count"], 3)
            self.assertTrue(np.allclose(offsets[0][:, 0], [0.125, 0.625]))
        finally:
            figure.clear()

    def test_boxplot_handles_single_constant_and_empty_batches(self):
        data = pd.DataFrame(
            {
                "NUM": [1] + list(range(1, 26)) + [1, 2],
                "lot_ID": ["LOT-SINGLE"] + ["LOT-CONSTANT"] * 25 + ["LOT-EMPTY"] * 2,
                "Source_ID": ["S"] + ["C"] * 25 + ["E"] * 2,
                "P": [5.0] + [5.0] * 25 + [np.nan, np.nan],
            }
        )
        layout = prepare_ft_chart_layout(data)
        figure, stats = make_ft_distribution_figure(
            data, _specs(["S", "C", "E"]), "P", layout, boxplot=True
        )
        try:
            self.assertEqual(stats["box_count"], 2)
            self.assertEqual(stats["valid_count"], 26)
            self.assertEqual(
                [tick.get_text() for tick in figure.axes[0].get_xticklabels()],
                ["LOT-SINGLE", "LOT-CONSTANT", "LOT-EMPTY"],
            )
            self.assertTrue(any(text.get_text() == "无有效值" for text in figure.axes[0].texts))
            low, high = figure.axes[0].get_ylim()
            self.assertLess(low, 5.0)
            self.assertGreater(high, 5.0)
        finally:
            figure.clear()

    def test_focus_is_per_batch_and_only_changes_viewport(self):
        batch_a = [130.0] * 99 + [0.0]
        batch_b = [150.0] * 5
        data = pd.DataFrame(
            {
                "NUM": list(range(1, 101)) + list(range(1, 6)),
                "lot_ID": ["LOT-A"] * 100 + ["LOT-B"] * 5,
                "Source_ID": ["A"] * 100 + ["B"] * 5,
                "P": batch_a + batch_b,
            }
        )
        original = data.copy(deep=True)
        layout = prepare_ft_chart_layout(data)
        expected_range = focused_y_range(parameter_values(data, "P"), layout.batches)
        self.assertIsNotNone(expected_range)
        self.assertGreater(expected_range[0], 0.0)
        self.assertGreater(expected_range[1], 150.0)

        focused, focused_stats = make_ft_distribution_figure(
            data, _specs(["A", "B"]), "P", layout, focus=True
        )
        full, full_stats = make_ft_distribution_figure(
            data, _specs(["A", "B"]), "P", layout, focus=False
        )
        try:
            self.assertEqual(focused_stats["valid_count"], full_stats["valid_count"])
            self.assertEqual(focused_stats["display_count"], full_stats["display_count"])
            self.assertEqual(focused_stats["below_count"], 1)
            self.assertEqual(full_stats["below_count"], 0)
            self.assertLess(focused.axes[0].get_ylim()[0], 130.0)
            self.assertLessEqual(full.axes[0].get_ylim()[0], 0.0)
            pd.testing.assert_frame_equal(data, original)
        finally:
            focused.clear()
            full.clear()

    def test_source_specific_limits_are_not_promoted_to_one_batch_limit(self):
        data = pd.DataFrame(
            {
                "NUM": [1, 2, 3, 4],
                "lot_ID": ["LOT-A"] * 4,
                "Source_ID": ["A-1", "A-1", "A-2", "A-2"],
                "P": [10.0, 11.0, 12.0, 13.0],
            }
        )
        specs = _specs(
            ["A-1", "A-2"], low=[9.0, 10.0], high=[12.0, 14.0]
        )
        figure, _ = make_ft_distribution_figure(
            data, specs, "P", prepare_ft_chart_layout(data), focus=False
        )
        try:
            labels = [text.get_text() for text in figure.axes[0].texts]
            self.assertIn("LSL LOT-A 9", labels)
            self.assertIn("LSL LOT-A 10", labels)
            self.assertIn("USL LOT-A 12", labels)
            self.assertIn("USL LOT-A 14", labels)
        finally:
            figure.clear()

    def test_blank_identities_and_invalid_num_fail_closed(self):
        base = pd.DataFrame(
            {
                "NUM": [1, 2],
                "lot_ID": ["LOT-A", "LOT-A"],
                "Source_ID": ["A", "A"],
                "P": [1.0, 2.0],
            }
        )
        for column, value, message in (
            ("lot_ID", " ", "空批次"),
            ("Source_ID", "", "空来源"),
            ("NUM", "not-a-number", "NUM"),
            ("NUM", np.inf, "NUM"),
        ):
            damaged = base.copy()
            damaged[column] = damaged[column].astype(object)
            damaged.loc[1, column] = value
            with self.subTest(column=column, value=value):
                with self.assertRaisesRegex(ValueError, message):
                    prepare_ft_chart_layout(damaged)

    def test_measured_source_requires_an_exact_spec_binding(self):
        data = pd.DataFrame(
            {
                "NUM": [1, 2],
                "lot_ID": ["LOT-A", "LOT-B"],
                "Source_ID": ["A", "B"],
                "P": [1.0, 2.0],
            }
        )
        layout = prepare_ft_chart_layout(data)
        with self.assertRaisesRegex(ValueError, "缺少规格"):
            make_ft_distribution_figure(data, _specs(["A"]), "P", layout)

        wrong_lot = _specs(["A", "B"])
        wrong_lot["lot_ID"] = ["LOT-X", "LOT-B"]
        with self.assertRaisesRegex(ValueError, "绑定不一致"):
            make_ft_distribution_figure(data, wrong_lot, "P", layout)

    def test_source_id_cannot_span_multiple_lots_for_one_parameter(self):
        data = pd.DataFrame(
            {
                "NUM": [1, 2],
                "lot_ID": ["LOT-A", "LOT-B"],
                "Source_ID": ["SAME", "SAME"],
                "P": [1.0, 2.0],
            }
        )
        with self.assertRaisesRegex(ValueError, "Source_ID 跨多个 lot_ID"):
            make_ft_distribution_figure(
                data, _specs(["SAME"]), "P", prepare_ft_chart_layout(data)
            )

    def test_blank_and_known_units_are_incompatible(self):
        data = pd.DataFrame(
            {
                "NUM": [1, 2],
                "lot_ID": ["LOT-A", "LOT-B"],
                "Source_ID": ["A", "B"],
                "P": [1.0, 2.0],
            }
        )
        with self.assertRaisesRegex(ValueError, "空单位"):
            make_ft_distribution_figure(
                data,
                _specs(["A", "B"], units=["", "V"]),
                "P",
                prepare_ft_chart_layout(data),
            )

    def test_invalid_nonempty_spec_limits_fail_but_one_sided_spec_is_valid(self):
        data = pd.DataFrame(
            {
                "NUM": [1],
                "lot_ID": ["LOT-A"],
                "Source_ID": ["A"],
                "P": [1.0],
            }
        )
        layout = prepare_ft_chart_layout(data)
        one_sided = _specs(["A"], low=[""], high=[2.0])
        figure, _ = make_ft_distribution_figure(
            data, one_sided, "P", layout, focus=False
        )
        figure.clear()

        for invalid_value in ("abc", np.inf, -np.inf):
            damaged = _specs(["A"], low=[invalid_value], high=[2.0])
            with self.subTest(value=invalid_value):
                with self.assertRaisesRegex(
                    ValueError, r"Low_Limit 不是有限数字.*Source_ID=A"
                ):
                    make_ft_distribution_figure(data, damaged, "P", layout)

    def test_only_verified_value_references_make_conditions_equivalent(self):
        data = pd.DataFrame(
            {
                "NUM": [1, 2],
                "lot_ID": ["LOT-A", "LOT-A"],
                "Source_ID": ["A", "B"],
                "P": [1.0, 2.0],
            }
        )
        specs = _specs(["A", "B"])
        specs["Parameter"] = ["DELTA BV", "DELTA BV"]
        specs["Test_Condition"] = ["Bias1=Value=#28", "Bias1=Value=#21"]
        figure, stats = make_ft_distribution_figure(
            data.rename(columns={"P": "DELTA BV"}),
            specs,
            "DELTA BV",
            prepare_ft_chart_layout(data.rename(columns={"P": "DELTA BV"})),
        )
        try:
            self.assertEqual(
                stats["conditions"], ("Bias1=Value=#28", "Bias1=Value=#21")
            )
            self.assertTrue(
                any("测试条件：Bias1=Value=#28" in text.get_text() for text in figure.texts)
            )
        finally:
            figure.clear()

        specs["Parameter"] = ["P", "P"]
        specs["Test_Condition"] = ["Bias1=Value=#28", "Bias1=Value=#21"]
        with self.assertRaisesRegex(ValueError, "不兼容测试条件"):
            make_ft_distribution_figure(
                data, specs, "P", prepare_ft_chart_layout(data)
            )

        specs["Test_Condition"] = ["ID=250uA", "ID=1mA"]
        with self.assertRaisesRegex(ValueError, "不兼容测试条件"):
            make_ft_distribution_figure(
                data, specs, "P", prepare_ft_chart_layout(data)
            )

        specs["Test_Condition"] = ["", "ID=250uA"]
        with self.assertRaisesRegex(ValueError, "空测试条件"):
            make_ft_distribution_figure(
                data, specs, "P", prepare_ft_chart_layout(data)
            )

    def test_source_specific_spec_lines_do_not_bridge_noncontiguous_runs(self):
        row_count = 2_000
        data = pd.DataFrame(
            {
                "NUM": range(1, row_count + 1),
                "lot_ID": ["LOT-A"] * row_count,
                "Source_ID": ["A", "B"] * (row_count // 2),
                "P": np.linspace(1.0, 4.0, row_count),
            }
        )
        specs = _specs(["A", "B"], low=[0.0, 0.5], high=[5.0, 5.5])
        figure, _ = make_ft_distribution_figure(
            data, specs, "P", prepare_ft_chart_layout(data), focus=False
        )
        try:
            labels = [text.get_text() for text in figure.axes[0].texts]
            self.assertEqual(labels.count("LSL LOT-A 0"), 1)
            self.assertEqual(labels.count("LSL LOT-A 0.5"), 1)
            self.assertEqual(labels.count("USL LOT-A 5"), 1)
            self.assertEqual(labels.count("USL LOT-A 5.5"), 1)
            self.assertLessEqual(len(figure.axes[0].collections), 3)
            limit_lines = [
                collection
                for collection in figure.axes[0].collections
                if isinstance(collection, LineCollection)
            ]
            self.assertEqual([len(line.get_segments()) for line in limit_lines], [2_000, 2_000])
            self.assertLess(
                max(
                    segment[1][0] - segment[0][0]
                    for line in limit_lines
                    for segment in line.get_segments()
                ),
                0.001,
            )
        finally:
            figure.clear()

    def test_incompatible_units_fail_closed(self):
        data = pd.DataFrame(
            {
                "NUM": [1, 2],
                "lot_ID": ["LOT-A", "LOT-B"],
                "Source_ID": ["A", "B"],
                "P": [1.0, 2.0],
            }
        )
        with self.assertRaisesRegex(ValueError, "不兼容单位"):
            make_ft_distribution_figure(
                data,
                _specs(["A", "B"], units=["V", "mV"]),
                "P",
                prepare_ft_chart_layout(data),
            )

    def test_png_is_white_static_2240_by_700_and_modes_are_independent(self):
        data = pd.DataFrame(
            {
                "NUM": [1, 2, 3],
                "lot_ID": ["LOT-A"] * 3,
                "Source_ID": ["A"] * 3,
                "P": [1.0, 2.0, 3.0],
            }
        )
        layout = prepare_ft_chart_layout(data)
        specs = _specs(["A"], low=[0.0], high=[4.0])
        scatter_png, scatter_stats = render_ft_scatter_png(
            data, specs, "P", layout, focus=False
        )
        box_png, box_stats = render_ft_boxplot_png(
            data, specs, "P", layout, focus=True
        )

        self.assertEqual(scatter_png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(box_png[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", scatter_png[16:24]), (2240, 700))
        self.assertEqual(Image.open(BytesIO(scatter_png)).convert("RGB").getpixel((0, 0)), (255, 255, 255))
        self.assertNotEqual(scatter_png, box_png)
        self.assertEqual(scatter_stats["display_count"], 3)
        self.assertFalse(scatter_stats["focus"])
        self.assertEqual(box_stats["box_count"], 1)
        self.assertTrue(box_stats["focus"])

    def test_batch_colors_expand_without_repeating_and_filename_is_safe(self):
        self.assertEqual(len({batch_color(index) for index in range(43)}), 43)
        self.assertEqual(safe_png_name('IDSS:nA/1', "散点图"), "IDSS_nA_1_散点图.png")

    def test_page_is_lazy_static_and_keeps_range_controls_independent(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            cleaned = root / "clean.xlsx"
            cleaned.touch()
            data = pd.DataFrame(
                {
                    "NUM": [1, 2, 1, 2],
                    "lot_ID": ["LOT-A", "LOT-A", "LOT-B", "LOT-B"],
                    "Source_ID": ["A", "A", "B", "B"],
                    "P": [1.0, 2.0, 3.0, 4.0],
                }
            )
            manifest = export_scatter_bundle(
                data,
                _specs(["A", "B"], low=[0.0, 0.0], high=[5.0, 5.0]),
                root,
                cleaned_file=cleaned,
            )
            app_path = Path(__file__).resolve().parents[1] / "frontend" / "ft_scatter_app.py"
            with patch.dict(os.environ, {"FT_SCATTER_MANIFEST": str(manifest)}):
                app = AppTest.from_file(str(app_path)).run(timeout=30)
                self.assertFalse(list(app.exception))
                self.assertEqual(len(app.get("imgs")), 0)
                self.assertEqual(len(app.info), 0)
                self.assertEqual(
                    [checkbox.label for checkbox in app.checkbox],
                    ["散点图显示完整纵轴范围", "箱体图显示完整纵轴范围"],
                )

                self.assertEqual(app.multiselect[0].value, [])
                self.assertFalse(any("default value" in warning.value for warning in app.warning))
                app.button(key="ft_render").click().run(timeout=30)
                self.assertEqual(len(app.get("imgs")), 0)
                app.button(key="ft_select_all").click().run(timeout=30)
                self.assertEqual(app.multiselect[0].value, ["P"])
                self.assertEqual(len(app.get("imgs")), 0)
                app.button(key="ft_render").click().run(timeout=30)
                self.assertFalse(list(app.exception))
                self.assertEqual(len(app.get("imgs")), 1)
                self.assertEqual(len(app.get("download_button")), 1)

                self.assertEqual(len(app.expander), 0)
                self.assertEqual(app.button[2].label, "应用自定义并绘制")
                self.assertEqual(app.button[3].label, "恢复自动范围")
                self.assertEqual(len(app.checkbox), 2)
                self.assertEqual(len(app.get("form")[0].get("column")), 7)
                self.assertEqual([field.label for field in app.text_input], ["Y 轴最小值", "Y 轴最大值"])
                self.assertFalse(any("每个参数一张静态图片" in c.value for c in app.caption))
                self.assertFalse(any("勾选后填写上下限" in c.value for c in app.caption))

                app.checkbox[0].set_value(True).run(timeout=30)
                self.assertTrue(app.checkbox[0].value)
                self.assertFalse(app.checkbox[1].value)
                app.radio[0].set_value("箱体图").run(timeout=30)
                self.assertFalse(list(app.exception))
                self.assertEqual(len(app.get("imgs")), 1)
                self.assertTrue(app.checkbox[0].value)
                self.assertFalse(app.checkbox[1].value)
                self.assertEqual(len(app.expander), 0)
                self.assertFalse(any("每个完整 lot_ID 一个箱体" in c.value for c in app.caption))

                app.radio[0].set_value("散点图").run(timeout=30)
                self.assertFalse(list(app.exception))
                self.assertTrue(any("缓存复用" in caption.value for caption in app.caption))

                app.text_input[0].set_value("1.5")
                app.text_input[1].set_value("3.5")
                app.button[2].click().run(timeout=30)
                self.assertFalse(list(app.exception))
                self.assertTrue(any("自定义 Y 轴：1.5 ～ 3.5" in c.value for c in app.caption))
                self.assertEqual(len(app.get("download_button")), 1)

                app.radio[0].set_value("箱体图").run(timeout=30)
                self.assertTrue(any("自动 Y 轴" in c.value for c in app.caption))
                app.text_input[0].set_value("-1")
                app.text_input[1].set_value("10")
                app.button[2].click().run(timeout=30)
                self.assertTrue(any("自定义 Y 轴：-1 ～ 10" in c.value for c in app.caption))
                app.radio[0].set_value("散点图").run(timeout=30)
                self.assertTrue(any("自定义 Y 轴：1.5 ～ 3.5" in c.value for c in app.caption))

                app.text_input[0].set_value("4")
                app.button[2].click().run(timeout=30)
                self.assertTrue(any("最小值必须小于最大值" in w.value for w in app.warning))
                self.assertEqual(len(app.get("imgs")), 0)
                self.assertEqual(len(app.get("download_button")), 0)
                app.button[3].click().run(timeout=30)
                self.assertEqual(len(app.get("imgs")), 1)
                self.assertTrue(any("自动 Y 轴" in c.value for c in app.caption))

                # Applying a blank bound must not silently keep the old image.
                app.text_input[0].set_value("")
                app.button[2].click().run(timeout=30)
                self.assertEqual(len(app.get("imgs")), 0)
                self.assertTrue(list(app.warning))
                app.button[3].click().run(timeout=30)
                self.assertEqual(len(app.get("imgs")), 1)

                # A second parameter must not inherit P's custom axis.
                data["Q"] = data["P"] * 100
                expanded_specs = pd.concat([
                    _specs(["A", "B"]),
                    _specs(["A", "B"]).assign(Parameter="Q"),
                ], ignore_index=True)
                export_scatter_bundle(data, expanded_specs, root, cleaned_file=cleaned)
                app.run(timeout=30)
                self.assertEqual(app.multiselect[0].value, [])
                app.button(key="ft_select_all").click().run(timeout=30)
                self.assertEqual(app.multiselect[0].value, ["P", "Q"])
                app.multiselect[0].set_value(["Q"]).run(timeout=30)
                self.assertEqual(app.multiselect[0].value, ["Q"])
                app.multiselect[0].set_value([]).run(timeout=30)
                self.assertEqual(app.multiselect[0].value, [])
                app.multiselect[0].set_value(["P", "Q"]).run(timeout=30)
                app.button(key="ft_render").click().run(timeout=30)
                app.text_input[0].set_value("1")
                app.text_input[1].set_value("4")
                app.button[2].click().run(timeout=30)
                self.assertFalse(list(app.exception))
                self.assertEqual(len(app.get("imgs")), 2)
                self.assertEqual(len(app.checkbox), 2)
                self.assertTrue(any("自定义 Y 轴：1 ～ 4" in c.value for c in app.caption))
                self.assertTrue(any("自动 Y 轴" in c.value for c in app.caption))


if __name__ == "__main__":
    unittest.main()
