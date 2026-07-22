import json
import tempfile
import unittest
from pathlib import Path

import pandas as pd

from frontend.ft_scatter import (
    build_parameter_figure,
    export_scatter_bundle,
    load_scatter_bundle,
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
            self.assertEqual(figure.layout.legend.orientation, "h")
            self.assertEqual(figure.layout.legend.title.text, "批次")
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


if __name__ == "__main__":
    unittest.main()
