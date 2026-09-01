import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from factories.dianji.dc_cleaner import (
    DianjiDCCleaner,
    _resolve_output_parameter_schema,
)
from factories.dianji.models import DianjiFormatError, FileIdentity
from frontend.ft_scatter import load_scatter_bundle
from shared.pat_engine import RawPatGroup, build_spooled_raw_pat


def _data_frame(batch: str, **parameters) -> pd.DataFrame:
    frame = pd.DataFrame({"批次": [batch] * len(next(iter(parameters.values()))), **parameters})
    return frame


def _specs(path: Path, batch: str, parameters: tuple[str, ...]) -> pd.DataFrame:
    return pd.DataFrame.from_records(
        [
            {
                "Source_ID": path.stem,
                "lot_ID": batch,
                "Parameter": parameter,
                "Unit": "V",
                "Low_Limit": None,
                "High_Limit": None,
                "Low_Limit_Raw": "",
                "High_Limit_Raw": "",
                "Test_Condition": "",
                "Limit_Order_Normalized": False,
                "Source_File": path.name,
            }
            for parameter in parameters
        ]
    )


def _parsed_source(
    path: Path,
    batch: str,
    frame: pd.DataFrame,
    *,
    parameter_keys,
    source_format: str = "PowerTECH",
):
    frame.attrs["parameter_keys"] = parameter_keys
    parameters = tuple(column for column in frame.columns if column != "批次")
    return SimpleNamespace(
        path=path,
        identity=FileIdentity(
            product="TESTPRODUCT-7E00",
            manufacturing_lot="M000000001-001",
            batch=batch,
            test_tag="ALL260101000000",
        ),
        metadata_lot=f"M000000001-001 {batch}",
        lot_identity_warning=None,
        data=frame,
        specs=_specs(path, batch, parameters),
        source_rows=len(frame),
        kept_rows=len(frame),
        invalid_marker_counts={},
        source_format=source_format,
        parameter_keys=parameter_keys,
    )


class DianjiDynamicSchemaTests(unittest.TestCase):
    def test_powertech_cleaner_merges_nested_prefix_and_fills_missing_tail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first_path = root / "first.xls"
            second_path = root / "second.xls"
            first = _parsed_source(
                first_path,
                "C000001.00",
                _data_frame("C000001.00", A=[1.0, 2.0]),
                parameter_keys=("A|Bias=1|Unit=V",),
            )
            second = _parsed_source(
                second_path,
                "C000002.00",
                _data_frame(
                    "C000002.00",
                    A=[3.0, 4.0],
                    B=[30.0, 40.0],
                ),
                parameter_keys=(
                    "A|Bias=1|Unit=V",
                    "B|Bias=2|Unit=V",
                ),
            )
            cleaner = DianjiDCCleaner(root / "unused", root / "output")

            with patch.object(
                cleaner, "scan_source_files", return_value=[first_path, second_path]
            ), patch(
                "factories.dianji.dc_cleaner.parse_dianji_source_file",
                side_effect=[first, second],
            ):
                self.assertTrue(cleaner.process_all())

            result = pd.read_excel(cleaner.last_output_file, sheet_name="RAW")
            self.assertEqual(list(result.columns), ["NUM", "批次", "A", "B"])
            self.assertEqual(result["A"].tolist(), [1.0, 2.0, 3.0, 4.0])
            self.assertTrue(result.loc[:1, "B"].isna().all())
            self.assertEqual(result.loc[2:, "B"].tolist(), [30.0, 40.0])

            manifest, scatter_data, _scatter_specs = load_scatter_bundle(
                cleaner.last_scatter_manifest
            )
            self.assertEqual(manifest["parameters"], ["A", "B"])
            self.assertTrue(scatter_data.loc[:1, "B"].isna().all())

    def test_powertech_rejects_nonprefix_or_semantic_conflict(self):
        first_path = Path("first.xls")
        second_path = Path("second.xls")
        cases = (
            (
                _parsed_source(
                    first_path,
                    "C000001.00",
                    _data_frame("C000001.00", A=[1.0], B=[2.0]),
                    parameter_keys=("A|Bias=1", "B|Bias=2"),
                ),
                _parsed_source(
                    second_path,
                    "C000002.00",
                    _data_frame("C000002.00", A=[3.0], C=[4.0]),
                    parameter_keys=("A|Bias=1", "C|Bias=3"),
                ),
            ),
            (
                _parsed_source(
                    first_path,
                    "C000001.00",
                    _data_frame("C000001.00", A=[1.0]),
                    parameter_keys=("A|Bias=1|Unit=V",),
                ),
                _parsed_source(
                    second_path,
                    "C000002.00",
                    _data_frame("C000002.00", A=[2.0]),
                    parameter_keys=("A|Bias=2|Unit=V",),
                ),
            ),
        )
        for parsed_files in cases:
            with self.subTest(keys=[item.parameter_keys for item in parsed_files]):
                with self.assertRaisesRegex(
                    DianjiFormatError, "不是严格的右侧追加兼容关系"
                ):
                    _resolve_output_parameter_schema(
                        list(parsed_files), "PowerTECH"
                    )

    def test_non_powertech_formats_remain_exact(self):
        first = _parsed_source(
            Path("first.csv"),
            "C000001.00",
            _data_frame("C000001.00", A=[1.0]),
            parameter_keys=("A",),
            source_format="STS8203 CSV",
        )
        second = _parsed_source(
            Path("second.csv"),
            "C000002.00",
            _data_frame("C000002.00", A=[2.0], B=[3.0]),
            parameter_keys=("A", "B"),
            source_format="STS8203 CSV",
        )

        with self.assertRaisesRegex(DianjiFormatError, "参数结构不一致"):
            _resolve_output_parameter_schema(
                [first, second], "STS8203 CSV"
            )


class RawPatDynamicSchemaTests(unittest.TestCase):
    def test_nested_prefix_counts_only_files_that_contain_the_parameter(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            short_path = root / "short.xls"
            long_path = root / "long.xls"
            frames = {
                short_path: _data_frame("C1", A=[1.0, 2.0]),
                long_path: _data_frame("C2", A=[3.0, 4.0], B=[30.0, 40.0]),
            }
            frames[short_path].attrs["parameter_keys"] = ("A|Bias=1",)
            frames[long_path].attrs["parameter_keys"] = (
                "A|Bias=1",
                "B|Bias=2",
            )

            for files in ((short_path, long_path), (long_path, short_path)):
                with self.subTest(files=[path.name for path in files]):
                    result = build_spooled_raw_pat(
                        (
                            RawPatGroup(
                                "FT-ALL",
                                files,
                                lambda path: frames[path].copy(deep=False),
                                schema_mode="nested_prefix",
                            ),
                        ),
                        spool_dir=root,
                        progress_interval=0,
                        factory_label="电基",
                    )
                    stats = result.iloc[1:].set_index("统计量")
                    self.assertEqual(stats.index.tolist(), ["A", "B"])
                    self.assertEqual(int(stats.loc["A", "总计数"]), 4)
                    self.assertEqual(int(stats.loc["B", "总计数"]), 2)
                    self.assertEqual(float(stats.loc["B", "均值"]), 35.0)

    def test_raw_pat_default_exact_and_semantic_conflicts_still_fail(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first_path = root / "first.xls"
            second_path = root / "second.xls"
            first = _data_frame("C1", A=[1.0])
            appended = _data_frame("C2", A=[2.0], B=[3.0])

            with self.assertRaisesRegex(ValueError, "参数结构不一致"):
                build_spooled_raw_pat(
                    (
                        RawPatGroup(
                            "default-exact",
                            (first_path, second_path),
                            lambda path: first if path == first_path else appended,
                        ),
                    ),
                    spool_dir=root,
                    progress_interval=0,
                )

            changed_bias = _data_frame("C2", A=[2.0])
            first.attrs["parameter_keys"] = ("A|Bias=1",)
            changed_bias.attrs["parameter_keys"] = ("A|Bias=2",)
            with self.assertRaisesRegex(ValueError, "不是严格的右侧追加"):
                build_spooled_raw_pat(
                    (
                        RawPatGroup(
                            "semantic-conflict",
                            (first_path, second_path),
                            lambda path: (
                                first if path == first_path else changed_bias
                            ),
                            schema_mode="nested_prefix",
                        ),
                    ),
                    spool_dir=root,
                    progress_interval=0,
                )


if __name__ == "__main__":
    unittest.main()
