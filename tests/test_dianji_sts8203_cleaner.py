import csv
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pandas as pd

from factories.dianji.config import (
    STS8203_EXPECTED_COLUMN_COUNT,
    STS8203_EXPECTED_FIELD_INDEXES,
    STS8203_EXPECTED_SOURCE_UNITS,
)
from factories.dianji.dc_cleaner import DianjiDCCleaner
from factories.dianji.powertech_parser import DianjiFormatError
from factories.dianji.source_registry import (
    SOURCE_FORMATS,
    detect_dianji_source_format,
)
from factories.dianji.sts8203_parser import (
    parse_sts8203_file,
    parse_sts8203_filename,
)


PRODUCT = "NCEAP40T20AGU(M)-7E00"
_UNSET = object()


def _make_source(
    directory: Path,
    *,
    manufacturing_lot: str = "m25081416-001",
    batch: str = "c163464.02",
    metadata_lot: str | None = None,
    metadata_batch: str | None = None,
    source_segment: str | None = None,
    metadata_source_segment: str | None | object = _UNSET,
    changed_field: tuple[int, str] | None = None,
    encoding: str = "utf-8-sig",
    filename_timestamp: str = "2025-09-11 2_30_44",
    metadata_date: str = "2025-09-11",
    beginning_time: str = "2025-09-11 2:30:44",
    ending_time: str = "2025-09-11 2:31:00",
) -> Path:
    metadata_lot = metadata_lot or manufacturing_lot
    metadata_batch = metadata_batch or batch
    if metadata_source_segment is _UNSET:
        metadata_source_segment = source_segment
    filename_segment = f"  {source_segment}" if source_segment else ""
    metadata_segment = (
        f"   {metadata_source_segment}" if metadata_source_segment else ""
    )
    path = directory / (
        f"{PRODUCT}_Lot Id_{manufacturing_lot} {batch}{filename_segment}"
        f"_ALL_{filename_timestamp}.csv"
    )

    header = [f"UNUSED_{index}" for index in range(STS8203_EXPECTED_COLUMN_COUNT)]
    for field, index in STS8203_EXPECTED_FIELD_INDEXES.items():
        header[index] = field
    if changed_field is not None:
        header[changed_field[0]] = changed_field[1]

    units = [""] * STS8203_EXPECTED_COLUMN_COUNT
    units[0] = "Unit"
    for field, unit in STS8203_EXPECTED_SOURCE_UNITS.items():
        units[STS8203_EXPECTED_FIELD_INDEXES[field]] = unit

    low_limits = [""] * STS8203_EXPECTED_COLUMN_COUNT
    high_limits = [""] * STS8203_EXPECTED_COLUMN_COUNT
    low_limits[0] = "LimitL"
    high_limits[0] = "LimitU"
    for field in STS8203_EXPECTED_SOURCE_UNITS:
        index = STS8203_EXPECTED_FIELD_INDEXES[field]
        low_limits[index] = "-1"
        high_limits[index] = "1"
    low_limits[STS8203_EXPECTED_FIELD_INDEXES["DVDS"]] = "75"
    high_limits[STS8203_EXPECTED_FIELD_INDEXES["DVDS"]] = "87"

    full = [""] * STS8203_EXPECTED_COLUMN_COUNT
    full[:6] = ["6", "1", "True", "60", "250", "57"]
    values = {
        "DVDS": "80.5",
        "Zmu_RG2": "3.4",
        "QC_VTH": "3.01",
        "QC_VTH2": "3.16",
        "QC_BVDSS": "45.2",
        "QC_BVDSS1": "45.3",
        "QC_IDSS": "9999",
        "QC_IGSSF2": "0.8",
        "QC_IGSSR2": "-6.1",
        "QC_IGSSF": "0.9",
        "QC_IGSSR": "-1.3",
        "RDSON2": "1.02",
        "QC_VFSD": "0.75",
        "QC_IDSS1": "3.2",
        "QC_IGSSF1": "0.2",
        "QC_IGSSR1": "-0.4",
        "QC_VTH1": "3.02",
        "QC_DELTA_BVDSS": "0.02",
        "QC_DELTA_VTH": "0.15",
    }
    for field, value in values.items():
        full[STS8203_EXPECTED_FIELD_INDEXES[field]] = value

    partial_after_dvds = ["6", "2", "False", "13", "200", "10", "", "", "", "82"]
    early_failure = ["6", "3", "False", "12", "100", "5", "", "", ""]

    buffer = io.StringIO(newline="")
    metadata_lines = [
        "STS8203 StationA",
        f"Date:{metadata_date}",
        "Tester ID:",
        "User:admin",
        f"Program:D:\\EUIT_Prgorm_A\\{PRODUCT}_ALL_M07M08_Ver1.05.pgs",
        "Handler: MultiTaskHandler.dll",
        "Site: All Sites",
        f"Lot Id:{metadata_lot} {metadata_batch}{metadata_segment} ",
        "",
        f"Beginning Time: {beginning_time}",
        f"Ending Time: {ending_time}",
        "",
    ]
    buffer.write("\r\n".join(metadata_lines))
    buffer.write("\r\n")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow([*header, ""])
    writer.writerow([*units, ""])
    writer.writerow([*low_limits, ""])
    writer.writerow([*high_limits, ""])
    writer.writerow([])
    writer.writerow([*full, ""])
    writer.writerow([*partial_after_dvds, ""])
    writer.writerow([*early_failure, ""])
    path.write_text(buffer.getvalue(), encoding=encoding, newline="")
    return path


class STS8203FilenameTests(unittest.TestCase):
    def test_extracts_verified_identity(self):
        identity = parse_sts8203_filename(
            f"{PRODUCT}_Lot Id_m25081416-001 c163464.02"
            "_ALL_2025-09-11 2_30_44.csv"
        )
        self.assertEqual(identity.product, PRODUCT)
        self.assertEqual(identity.manufacturing_lot, "M25081416-001")
        self.assertEqual(identity.batch, "C163464.02")
        self.assertEqual(identity.test_tag, "ALL20250911023044")
        self.assertIsNone(identity.source_segment)

    def test_accepts_verified_dj5_lot_and_segment_variants(self):
        segmented = parse_sts8203_filename(
            f"{PRODUCT}_Lot Id_M250619006-001 C159126.03  2"
            "_ALL_2025-07-07 0_07_35.csv"
        )
        self.assertEqual(segmented.manufacturing_lot, "M250619006-001")
        self.assertEqual(segmented.batch, "C159126.03")
        self.assertEqual(segmented.source_segment, "2")

        suffixed = parse_sts8203_filename(
            f"{PRODUCT}_Lot Id_m250710015-002-a c163464.00"
            "_ALL_2025-08-25 9_32_13.csv"
        )
        self.assertEqual(suffixed.manufacturing_lot, "M250710015-002-A")
        self.assertIsNone(suffixed.source_segment)

    def test_rejects_unreviewed_segment_and_lot_suffix(self):
        with self.assertRaisesRegex(DianjiFormatError, "分段号未经验证"):
            parse_sts8203_filename(
                f"{PRODUCT}_Lot Id_M250619006-001 C159126.03  3"
                "_ALL_2025-07-07 0_07_35.csv"
            )
        with self.assertRaisesRegex(DianjiFormatError, "后缀未经验证"):
            parse_sts8203_filename(
                f"{PRODUCT}_Lot Id_M250710015-002-b C163464.00"
                "_ALL_2025-08-25 9_32_13.csv"
            )


class STS8203ParserTests(unittest.TestCase):
    def test_maps_final_qc_group_to_existing_dianji_raw_contract(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_sts8203_file(_make_source(Path(temp)))

        self.assertEqual(parsed.source_rows, 3)
        self.assertEqual(parsed.kept_rows, 2)
        self.assertEqual(
            list(parsed.data.columns),
            [
                "批次", "DVDS(mV)", "Rg(R)", "VTH1(V)", "VTH2(V)",
                "BVDSS1(V)", "BVDSS2(V)", "IDSS40(nA)", "IGSS25(nA)",
                "ISGS25(nA)", "IGSS20(nA)", "ISGS20(nA)", "RDON10(mR)",
                "VFSD(V)", "ISGS10(nA)", "IGSS10(nA)", "IDSS35(nA)",
                "VTH3(V)", "DELTA BV", "DELTA VTH",
            ],
        )
        self.assertEqual(parsed.data["批次"].unique().tolist(), ["C163464.02"])
        self.assertAlmostEqual(parsed.data.loc[0, "DVDS(mV)"], 80.5)
        self.assertAlmostEqual(parsed.data.loc[0, "ISGS25(nA)"], -6.1)
        self.assertAlmostEqual(parsed.data.loc[0, "RDON10(mR)"], 1.02)
        self.assertTrue(pd.isna(parsed.data.loc[0, "IDSS40(nA)"]))
        self.assertTrue(pd.isna(parsed.data.loc[1, "Rg(R)"]))
        self.assertEqual(parsed.invalid_marker_counts, {"IDSS40(nA)": 1})
        dvds_spec = parsed.specs.loc[
            parsed.specs["Parameter"] == "DVDS(mV)"
        ].iloc[0]
        self.assertEqual(float(dvds_spec["Low_Limit"]), 75.0)
        self.assertEqual(float(dvds_spec["High_Limit"]), 87.0)

    def test_rejects_filename_lot_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            path = _make_source(Path(temp), metadata_batch="C163465.02")
            with self.assertRaisesRegex(DianjiFormatError, "Lot Id 元数据不一致"):
                parse_sts8203_file(path)

    def test_accepts_matching_segment_and_rejects_metadata_segment_mismatch(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            parsed = parse_sts8203_file(
                _make_source(
                    root,
                    manufacturing_lot="M250619006-001",
                    batch="C159126.03",
                    source_segment="2",
                )
            )
            self.assertEqual(parsed.identity.source_segment, "2")

        with tempfile.TemporaryDirectory() as temp:
            path = _make_source(
                Path(temp),
                manufacturing_lot="M250619006-001",
                batch="C159126.03",
                source_segment="2",
                metadata_source_segment=None,
            )
            with self.assertRaisesRegex(DianjiFormatError, "Lot Id 元数据不一致"):
                parse_sts8203_file(path)

    def test_accepts_cross_midnight_date_as_ending_date(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_sts8203_file(
                _make_source(
                    Path(temp),
                    filename_timestamp="2025-09-11 23_30_44",
                    metadata_date="2025-09-12",
                    beginning_time="2025-09-11 23:30:44",
                    ending_time="2025-09-12 0:30:00",
                )
            )
        self.assertEqual(parsed.kept_rows, 2)

    def test_rejects_date_that_is_not_ending_date(self):
        with tempfile.TemporaryDirectory() as temp:
            path = _make_source(
                Path(temp),
                metadata_date="2025-09-12",
                ending_time="2025-09-11 2:31:00",
            )
            with self.assertRaisesRegex(DianjiFormatError, "Date 与 Ending Time"):
                parse_sts8203_file(path)

    def test_rejects_changed_qc_schema(self):
        with tempfile.TemporaryDirectory() as temp:
            index = STS8203_EXPECTED_FIELD_INDEXES["QC_VTH"]
            path = _make_source(
                Path(temp),
                changed_field=(index, "QC_VTH_CHANGED"),
            )
            with self.assertRaisesRegex(DianjiFormatError, "QC_VTH"):
                parse_sts8203_file(path)

    def test_accepts_utf8_without_bom_like_real_dj4_source(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_sts8203_file(
                _make_source(Path(temp), encoding="utf-8")
            )
        self.assertEqual(parsed.kept_rows, 2)

    def test_rejects_unreviewed_product_mapping(self):
        with tempfile.TemporaryDirectory() as temp:
            path = _make_source(Path(temp))
            unsupported = path.with_name(path.name.replace(PRODUCT, "UNREVIEWED"))
            path.rename(unsupported)
            with self.assertRaisesRegex(DianjiFormatError, "尚未验证"):
                parse_sts8203_file(unsupported)


class STS8203CleanerTests(unittest.TestCase):
    def test_rejects_mixed_powertech_and_sts8203_sources(self):
        parsed = [
            SimpleNamespace(
                source_format="PowerTECH",
                lot_identity_warning=None,
                source_rows=1,
                kept_rows=1,
                identity=SimpleNamespace(batch="C000001.00"),
            ),
            SimpleNamespace(
                source_format="STS8203 CSV",
                lot_identity_warning=None,
                source_rows=1,
                kept_rows=1,
                identity=SimpleNamespace(batch="C000002.00"),
            ),
        ]
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            cleaner = DianjiDCCleaner(root, root / "output")
            with (
                patch.object(
                    cleaner,
                    "scan_source_files",
                    return_value=[root / "a.xls", root / "b.csv"],
                ),
                patch(
                    "factories.dianji.dc_cleaner.parse_dianji_source_file",
                    side_effect=parsed,
                ),
                self.assertRaisesRegex(DianjiFormatError, "一种电基源格式"),
            ):
                cleaner.process_all()

    def test_writes_same_raw_contract_in_product_run_folder(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            input_dir.mkdir()
            _make_source(input_dir)
            cleaner = DianjiDCCleaner(input_dir, root / "output")

            self.assertTrue(cleaner.process_all())

            self.assertEqual(
                cleaner.last_output_file.parent.name,
                "NCEAP40T20AGU(M)_001",
            )
            self.assertEqual(
                cleaner.last_output_file.name,
                f"{PRODUCT} DJ PAT.xlsx",
            )
            result = pd.read_excel(cleaner.last_output_file, sheet_name="RAW")
            self.assertEqual(result.shape, (2, 21))
            self.assertEqual(result["NUM"].tolist(), [1, 2])
            self.assertEqual(
                cleaner.last_run_summary["source_formats"],
                {"STS8203 CSV": 1},
            )
            self.assertEqual(cleaner.last_run_summary["source_rows"], 3)
            self.assertEqual(cleaner.last_run_summary["kept_rows"], 2)
            self.assertTrue(cleaner.last_scatter_manifest.is_file())
            self.assertEqual(
                cleaner.last_scatter_manifest.parent,
                cleaner.last_output_file.parent,
            )


class DianjiSourceRegistryTests(unittest.TestCase):
    def test_registry_keeps_each_format_in_its_own_parser_module(self):
        handlers = {handler.key: handler for handler in SOURCE_FORMATS}
        self.assertEqual(
            handlers["powertech_text"].parser.__module__,
            "factories.dianji.powertech_parser",
        )
        self.assertEqual(
            handlers["sts8203_csv"].parser.__module__,
            "factories.dianji.sts8203_parser",
        )

    def test_detects_registered_format_by_extension_and_signature(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            sts_path = _make_source(root)
            powertech_path = root / "source.xls"
            powertech_path.write_bytes(b"PowerTECH Test System\tStation")
            unknown_path = root / "unknown.csv"
            unknown_path.write_text("ordinary,csv\n", encoding="utf-8")

            self.assertEqual(
                detect_dianji_source_format(sts_path).key,
                "sts8203_csv",
            )
            self.assertEqual(
                detect_dianji_source_format(powertech_path).key,
                "powertech_text",
            )
            with self.assertRaisesRegex(DianjiFormatError, "无法识别"):
                detect_dianji_source_format(unknown_path)


if __name__ == "__main__":
    unittest.main()
