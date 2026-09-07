import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from frontend.ft_scatter import (
    build_parameter_figure,
    export_scatter_bundle,
    load_scatter_bundle,
    load_scatter_manifest,
    parameter_limit_summary,
    prepare_parameter_points,
)


class FTScatterBundleTests(unittest.TestCase):
    def test_bundle_is_portable_and_all_oos_points_are_retained(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir) / "FA59-3997_001"
            output_dir.mkdir()
            cleaned_file = output_dir / "FA59-3997_001.xlsx"
            cleaned_file.touch()
            data = pd.DataFrame(
                {
                    "NUM": range(1, 21),
                    "lot_ID": ["LOT-A"] * 10 + ["LOT-B"] * 10,
                    "Source_ID": ["NCT1"] * 10 + ["NCT2"] * 10,
                    "VTH(V)": [0.5, 1.5, 1.6, 1.7, 1.8, 1.9, 2.0, 2.1, 2.2, 2.8] * 2,
                }
            )
            specs = pd.DataFrame(
                {
                    "Source_ID": ["NCT1", "NCT2"],
                    "Parameter": ["VTH(V)", "VTH(V)"],
                    "Low_Limit": [1.3, 1.3],
                    "High_Limit": [2.2, 2.2],
                    "Test_Condition": ["ID=250uA", "ID=250uA"],
                }
            )

            manifest_path = export_scatter_bundle(
                data, specs, output_dir, cleaned_file=cleaned_file
            )
            raw_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(raw_manifest["data_file"], "ft_scatter_data.csv.gz")
            self.assertEqual(raw_manifest["cleaned_file"], "FA59-3997_001.xlsx")
            self.assertEqual(
                raw_manifest["group_contract"],
                {
                    "batch_key": "lot_ID",
                    "sample_order_key": "NUM",
                    "spec_key": "Source_ID",
                    "box_group_keys": ["lot_ID"],
                    "subgroup_key": None,
                },
            )

            named_manifest = export_scatter_bundle(
                data,
                specs,
                output_dir,
                cleaned_file=cleaned_file,
                bundle_stem="electric_ft_scatter",
            )
            self.assertEqual(
                named_manifest.name, "electric_ft_scatter_manifest.json"
            )
            self.assertEqual(raw_manifest["lots"], ["LOT-A", "LOT-B"])

            manifest, loaded_data, loaded_specs = load_scatter_bundle(manifest_path)
            displayed, stats = prepare_parameter_points(
                loaded_data, loaded_specs, "VTH(V)", point_limit=8
            )
            self.assertEqual(manifest["parameters"], ["VTH(V)"])
            self.assertEqual(stats["oos_count"], 4)
            self.assertEqual(stats["display_count"], 8)
            self.assertEqual(int(displayed["_oos"].sum()), 4)

            figure, _ = build_parameter_figure(
                loaded_data, loaded_specs, "VTH(V)", point_limit=8
            )
            self.assertEqual(figure.layout.xaxis.title.text, "C1（测试序号）")
            self.assertEqual(figure.layout.yaxis.title.text, "")
            self.assertIn("ID=250uA", figure.layout.title.text)
            self.assertEqual(figure.layout.annotations[0].text, "LSL 1.3 ｜ USL 2.2")
            marker_traces = [trace for trace in figure.data if trace.mode == "markers"]
            self.assertEqual([trace.name for trace in marker_traces], ["LOT-A", "LOT-B"])
            self.assertEqual([trace.marker.size for trace in marker_traces], [7, 7])
            self.assertNotEqual(marker_traces[0].marker.color, marker_traces[1].marker.color)
            self.assertEqual(figure.layout.legend.orientation, "v")
            self.assertGreater(figure.layout.legend.x, 1)
            self.assertEqual(figure.layout.legend.title.text, "批次")
            self.assertEqual(figure.layout.legend.font.size, 15)
            self.assertEqual(figure.layout.title.font.size, 22)
            self.assertEqual(figure.layout.font.size, 15)
            self.assertEqual(figure.layout.xaxis.tickfont.size, 15)
            self.assertEqual(figure.layout.yaxis.tickfont.size, 15)
            self.assertEqual(figure.layout.paper_bgcolor, "#ffffff")
            self.assertEqual(figure.layout.plot_bgcolor, "#f8fafc")
            self.assertEqual(figure.layout.annotations[0].font.size, 14)
            self.assertGreaterEqual(len(figure.data), 4)

            no_lsl = specs.copy()
            no_lsl["Low_Limit"] = ""
            self.assertEqual(
                parameter_limit_summary(no_lsl, "VTH(V)"), "LSL N/A ｜ USL 2.2"
            )

    def test_repeated_in_spec_values_are_compacted_but_oos_values_are_not(self):
        data = pd.DataFrame(
            {
                "NUM": range(1, 104),
                "lot_ID": ["LOT-A"] * 103,
                "Source_ID": ["NCT1"] * 103,
                "VTH(V)": [1.5] * 100 + [0.5, 2.5, 3.0],
            }
        )
        specs = pd.DataFrame(
            {
                "Source_ID": ["NCT1"],
                "Parameter": ["VTH(V)"],
                "Low_Limit": [1.3],
                "High_Limit": [2.2],
            }
        )
        displayed, stats = prepare_parameter_points(
            data,
            specs,
            "VTH(V)",
            point_limit=100,
            max_duplicate_points=5,
        )
        self.assertEqual(stats["duplicate_reduction_count"], 95)
        self.assertEqual(stats["oos_count"], 3)
        self.assertEqual(stats["display_count"], 8)
        self.assertEqual(int(displayed["_oos"].sum()), 3)

    def test_small_lot_is_retained_by_stratified_sampling(self):
        data = pd.DataFrame(
            {
                "NUM": range(1, 5_002),
                "lot_ID": ["LOT-A"] * 5_000 + ["LOT-B"],
                "Source_ID": ["NCT1"] * 5_000 + ["NCT2"],
                "P": [float(value) for value in range(5_000)] + [2_500.5],
            }
        )
        specs = pd.DataFrame(
            {
                "Source_ID": ["NCT1", "NCT2"],
                "Parameter": ["P", "P"],
                "Low_Limit": [None, None],
                "High_Limit": [None, None],
            }
        )

        displayed, stats = prepare_parameter_points(data, specs, "P", point_limit=4_000)

        self.assertEqual(stats["display_count"], 4_000)
        self.assertEqual(displayed["lot_ID"].drop_duplicates().tolist(), ["LOT-A", "LOT-B"])
        self.assertEqual(int(displayed["lot_ID"].eq("LOT-B").sum()), 1)

    def test_seventeen_lots_have_distinct_scatter_colors_and_legend_entries(self):
        lots = [f"LOT-{index}" for index in range(17)]
        data = pd.DataFrame(
            {
                "NUM": range(1, 18),
                "lot_ID": lots,
                "Source_ID": [f"NCT-{index}" for index in range(17)],
                "P": [float(index) for index in range(17)],
            }
        )
        specs = pd.DataFrame(
            {
                "Source_ID": data["Source_ID"],
                "Parameter": ["P"] * 17,
                "Low_Limit": [None] * 17,
                "High_Limit": [None] * 17,
            }
        )

        figure, _ = build_parameter_figure(data, specs, "P")
        marker_traces = [trace for trace in figure.data if trace.mode == "markers"]

        self.assertEqual([trace.name for trace in marker_traces], lots)
        self.assertEqual(len({trace.marker.color for trace in marker_traces}), 17)

    def test_bundle_round_trip_preserves_numeric_looking_identities(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            cleaned_file = output_dir / "cleaned.xlsx"
            cleaned_file.touch()
            data = pd.DataFrame(
                {
                    "NUM": [1, 2],
                    "lot_ID": ["001", "1"],
                    "Source_ID": ["0007", "7"],
                    "P": [1.0, 2.0],
                }
            )
            specs = pd.DataFrame(
                {
                    "Source_ID": ["0007", "7"],
                    "lot_ID": ["001", "1"],
                    "Parameter": ["P", "P"],
                    "Low_Limit": [0.0, 0.0],
                    "High_Limit": [3.0, 3.0],
                }
            )
            manifest_path = export_scatter_bundle(
                data, specs, output_dir, cleaned_file=cleaned_file
            )
            _, loaded_data, loaded_specs = load_scatter_bundle(manifest_path)

            self.assertEqual(loaded_data["lot_ID"].tolist(), ["001", "1"])
            self.assertEqual(loaded_data["Source_ID"].tolist(), ["0007", "7"])
            self.assertEqual(loaded_specs["Source_ID"].tolist(), ["0007", "7"])
            self.assertEqual(loaded_specs["lot_ID"].tolist(), ["001", "1"])

    def test_present_but_damaged_group_contract_does_not_use_legacy_fallback(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            manifest_path = Path(temp_dir) / "manifest.json"
            manifest_path.write_text(
                json.dumps({"schema_version": 1, "group_contract": {}}),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "分组契约"):
                load_scatter_manifest(manifest_path)

    def test_export_rejects_source_identity_reused_across_lots(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            cleaned_file = output_dir / "cleaned.xlsx"
            cleaned_file.touch()
            data = pd.DataFrame(
                {
                    "NUM": [1, 2],
                    "lot_ID": ["LOT-A", "LOT-B"],
                    "Source_ID": ["SAME", "SAME"],
                    "P": [1.0, 2.0],
                }
            )
            with self.assertRaisesRegex(ValueError, "唯一对应"):
                export_scatter_bundle(
                    data,
                    pd.DataFrame(),
                    output_dir,
                    cleaned_file=cleaned_file,
                )

    def test_bundle_load_rejects_invalid_nonempty_spec_limit(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            output_dir = Path(temp_dir)
            cleaned_file = output_dir / "cleaned.xlsx"
            cleaned_file.touch()
            data = pd.DataFrame(
                {
                    "NUM": [1],
                    "lot_ID": ["LOT-A"],
                    "Source_ID": ["A"],
                    "P": [1.0],
                }
            )
            specs = pd.DataFrame(
                {
                    "Source_ID": ["A"],
                    "lot_ID": ["LOT-A"],
                    "Parameter": ["P"],
                    "Low_Limit": ["abc"],
                    "High_Limit": [2.0],
                }
            )
            manifest_path = export_scatter_bundle(
                data, specs, output_dir, cleaned_file=cleaned_file
            )
            with self.assertRaisesRegex(
                ValueError, r"Low_Limit 不是有限数字.*Source_ID=A"
            ):
                load_scatter_bundle(manifest_path)


if __name__ == "__main__":
    unittest.main()
