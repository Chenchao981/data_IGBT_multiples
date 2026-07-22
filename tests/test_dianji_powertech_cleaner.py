import tempfile
import unittest
from pathlib import Path

import pandas as pd

from factories.dianji.dc_cleaner import (
    DianjiDCCleaner,
    next_output_path,
    output_product_name,
)
from factories.dianji.powertech_parser import (
    DianjiFormatError,
    parse_dianji_filename,
    parse_powertech_file,
)
from frontend.ft_scatter import load_scatter_bundle


ITEM_NAMES = [
    "CONT_TR", "VF_EX", "SAME", "DVDS_EX", "CONT", "VFSE", "SAME",
    "EAS", "VFSE", "RF-SCANBOX", "CONT_RF", "LCR-RG", "CONT", "VTH",
    "SAME", "VTH", "SAME", "SAME", "VTH", "BVDSS", "BVDSS", "IDSS",
    "IGSS", "IGSS", "IGSS", "IGSS", "RDON", "VFSD", "IDSS", "IGSS",
    "IGSS", "VTH", "DELTA", "DELTA",
]


def _header_row(label, values):
    return "\t".join([label, "", "", *values])


def _make_source(
    directory: Path,
    manufacturing_lot="M000000001-001",
    batch="C000001.00",
    metadata_manufacturing_lot=None,
    metadata_batch=None,
    item_names=None,
    verified_tail_variant=False,
):
    item_names = list(item_names or ITEM_NAMES)
    if verified_tail_variant:
        item_names[28] = "IGSS"
        item_names[30] = "IDSS"
    metadata_manufacturing_lot = metadata_manufacturing_lot or manufacturing_lot
    metadata_batch = metadata_batch or batch
    name = f"TESTPRODUCT-7E00_{manufacturing_lot} {batch} ALL260101000000.xls"
    path = directory / name

    bias1 = [""] * 34
    bias2 = [""] * 34
    bias3 = [""] * 34
    bias1[13] = "ID=250.0uA"  # item 14: skipped placeholder VTH
    bias1[15] = "ID=250.0uA"
    bias1[18] = "ID=1.000mA"
    bias1[19] = "ID=250.0uA"
    bias1[20] = "ID=1.000mA"
    bias1[21] = "VDS=100.0V"
    bias1[22] = "VGS=25.00V"
    bias1[23] = "VGS=-25.00V"
    bias1[24] = "VGS=20.00V"
    bias1[25] = "VGS=-20.00V"
    bias1[26] = "ID=40.00A"
    bias2[26] = "VGS=10.0V"
    bias1[27] = "IS=40.00A"
    bias1[28] = "VDS=90.00V"
    bias1[29] = "VGS=10.00V"
    bias1[30] = "VGS=-10.00V"
    if verified_tail_variant:
        bias1[28] = "VGS=-10.00V"
        bias1[30] = "VDS=90.00V"
    bias1[31] = "ID=250.0uA"
    bias1[32] = "Value=#21"
    bias2[32] = "Value=#20"
    bias1[33] = "Value=#19"
    bias2[33] = "Value=#16"

    units = [""] * 34
    for item_number in (2, 5, 6, 8, 9, 13, 14, 16, 19, 20, 21, 28, 32):
        units[item_number - 1] = "V"
    units[4 - 1] = "mV"
    units[12 - 1] = "R"
    for item_number in (22, 23, 24, 25, 26, 29, 30, 31):
        units[item_number - 1] = "nA"
    units[27 - 1] = "mR"

    full = ["1", "1", "2", *[str(value) for value in range(1, 35)]]
    values = {
        4: 70.011,
        12: 3.5561,
        16: 2.8994,
        19: 3.0475,
        20: 46.331,
        21: 46.346,
        22: 27.601,
        23: 0.4381,
        24: -6.4101,
        25: 0.5237,
        26: -0.9816,
        27: 0.6608,
        28: 0.7555,
        29: 11.819,
        30: 0.099,
        31: -1.3174,
        32: 2.9168,
        33: 0.0152,
        34: 0.1481,
    }
    if verified_tail_variant:
        values[29], values[31] = values[31], values[29]
    for item_number, value in values.items():
        full[item_number + 2] = str(value)

    partial_after_dvds = ["2", "1", "8", "0", "0", "0", "71.25"]
    early_failure = ["3", "1", "8", "0", "0", "0"]
    sentinel = full.copy()
    sentinel[0] = "4"
    sentinel[22 + 2] = "9999"

    min_limits = [""] * 34
    max_limits = [""] * 34
    min_limits[4 - 1] = "60.00mV"
    max_limits[4 - 1] = "85.00mV"
    min_limits[12 - 1] = "2.600R"
    max_limits[12 - 1] = "3.800R"
    max_limits[22 - 1] = "60.00nA"

    lines = [
        "PowerTECH Test System\t\tTester Serial: \tSDTS10191810\t\tStation : \tA",
        f"DataFileName:\t\tD:\\EUIT_Test_Data\\{metadata_manufacturing_lot} {metadata_batch}.plf",
        "TestFileName:\t\tD:\\EUIT_Prgorm_A\\DC 测试程序\\program.ptf",
        "Device:\t\t",
        f"Lot:\t\t{metadata_manufacturing_lot} {metadata_batch}",
        "Operator:\t\t",
        "Description:\t\t",
        _header_row("Item Name", [f"{index} {value}" for index, value in enumerate(item_names, start=1)]),
        _header_row("Bias1", bias1),
        _header_row("Bias2", bias2),
        _header_row("Bias3", bias3),
        "Para",
        _header_row("Min Limit", min_limits),
        _header_row("Max Limit", max_limits),
        "Min Result",
        "Max Result",
        "Average",
        "STD DEV",
        "\t".join(["Serial#", "S#", "Bin#", *units]),
        "\t".join(full),
        "\t".join(partial_after_dvds),
        "\t".join(early_failure),
        "\t".join(sentinel),
    ]
    path.write_text("\r\n".join(lines), encoding="gb18030")
    return path


class DianjiFilenameTests(unittest.TestCase):
    def test_extracts_user_defined_product_and_batch(self):
        identity = parse_dianji_filename(
            "TESTPRODUCT-7E00_m000000001-001 c000001.00 ALL260101000000.xls"
        )
        self.assertEqual(identity.product, "TESTPRODUCT-7E00")
        self.assertEqual(identity.manufacturing_lot, "M000000001-001")
        self.assertEqual(identity.batch, "C000001.00")

    def test_accepts_verified_powertech_filename_variants(self):
        cases = (
            (
                "TESTPRODUCT-7E00_M260422047-001 C203133.03260428110238.xls",
                "M260422047-001", "C203133.03", "260428110238",
            ),
            (
                "TESTPRODUCT-7E00_m260422048-004 c203133。00 dc260429183009.xls",
                "M260422048-004", "C203133.00", "DC260429183009",
            ),
            (
                "TESTPRODUCT-7E00_R251225027-001 C152722,00 ALL260102090022.xls",
                "R251225027-001", "C152722.00", "ALL260102090022",
            ),
            (
                "TESTPRODUCT-7E00_m260604005-001 fa65-5405 ALL260705044541.xls",
                "M260604005-001", "FA65-5405", "ALL260705044541",
            ),
        )
        for filename, manufacturing_lot, batch, test_tag in cases:
            with self.subTest(filename=filename):
                identity = parse_dianji_filename(filename)
                self.assertEqual(identity.manufacturing_lot, manufacturing_lot)
                self.assertEqual(identity.batch, batch)
                self.assertEqual(identity.test_tag, test_tag)

    def test_rejects_unverified_batch_pattern(self):
        with self.assertRaisesRegex(DianjiFormatError, "电基文件名不符合"):
            parse_dianji_filename(
                "TESTPRODUCT-7E00_M260604005-001 FB65-5405 ALL260705044541.xls"
            )


class PowerTechParserTests(unittest.TestCase):
    def test_matches_reference_columns_and_keeps_partial_rows_after_dvds(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_powertech_file(_make_source(Path(temp)))

        self.assertEqual(parsed.source_rows, 4)
        self.assertEqual(parsed.kept_rows, 3)
        self.assertEqual(
            list(parsed.data.columns),
            [
                "批次", "DVDS(mV)", "Rg(R)", "VTH1(V)", "VTH2(V)",
                "BVDSS1(V)", "BVDSS2(V)", "IDSS100(nA)", "IGSS25(nA)",
                "ISGS25(nA)", "IGSS20(nA)", "ISGS20(nA)", "RDON10(mR)",
                "VFSD(V)", "ISGS10(nA)", "IGSS10(nA)", "IDSS90(nA)",
                "VTH3(V)", "DELTA BV", "DELTA VTH",
            ],
        )
        self.assertAlmostEqual(
            parsed.data.loc[0, "VTH2(V)"] - parsed.data.loc[0, "VTH1(V)"],
            0.1481,
            places=8,
        )
        self.assertEqual(parsed.data.loc[0, "DELTA VTH"], 0.1481)
        self.assertTrue(pd.isna(parsed.data.loc[1, "Rg(R)"]))
        self.assertTrue(pd.isna(parsed.data.loc[2, "IDSS100(nA)"]))
        self.assertEqual(parsed.invalid_marker_counts, {"IDSS100(nA)": 1})
        self.assertEqual(parsed.data["批次"].unique().tolist(), ["C000001.00"])
        vth_spec = parsed.specs.loc[
            parsed.specs["Parameter"] == "VTH1(V)"
        ].iloc[0]
        self.assertIn("ID=250.0uA", vth_spec["Test_Condition"])
        dvds_spec = parsed.specs.loc[
            parsed.specs["Parameter"] == "DVDS(mV)"
        ].iloc[0]
        self.assertEqual(float(dvds_spec["Low_Limit"]), 60.0)
        self.assertEqual(float(dvds_spec["High_Limit"]), 85.0)

    def test_accepts_verified_item_29_31_variant_with_stable_output_order(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_powertech_file(
                _make_source(Path(temp), verified_tail_variant=True)
            )

        columns = list(parsed.data.columns)
        self.assertLess(columns.index("ISGS10(nA)"), columns.index("IGSS10(nA)"))
        self.assertLess(columns.index("IGSS10(nA)"), columns.index("IDSS90(nA)"))
        self.assertEqual(parsed.data.loc[0, "ISGS10(nA)"], -1.3174)
        self.assertEqual(parsed.data.loc[0, "IGSS10(nA)"], 0.099)
        self.assertEqual(parsed.data.loc[0, "IDSS90(nA)"], 11.819)

    def test_allows_stale_lot_piece_suffix_when_main_lot_and_batch_match(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_powertech_file(
                _make_source(
                    Path(temp),
                    manufacturing_lot="M000000001-004",
                    metadata_manufacturing_lot="M000000001-003",
                )
            )

        self.assertEqual(parsed.identity.manufacturing_lot, "M000000001-004")
        self.assertEqual(parsed.metadata_lot, "M000000001-003 C000001.00")
        self.assertIn("Lot 片号后缀未刷新", parsed.lot_identity_warning)

    def test_normalizes_batch_punctuation_without_identity_warning(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_powertech_file(
                _make_source(
                    Path(temp),
                    manufacturing_lot="R251225027-001",
                    batch="C152722,00",
                    metadata_batch="C152722,00",
                )
            )

        self.assertEqual(parsed.identity.batch, "C152722.00")
        self.assertIsNone(parsed.lot_identity_warning)
        self.assertEqual(parsed.data["批次"].unique().tolist(), ["C152722.00"])

    def test_accepts_verified_fa_batch_in_filename_and_lot_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_powertech_file(
                _make_source(
                    Path(temp),
                    manufacturing_lot="m260604005-001",
                    batch="fa65-5405",
                )
            )

        self.assertEqual(parsed.identity.manufacturing_lot, "M260604005-001")
        self.assertEqual(parsed.identity.batch, "FA65-5405")
        self.assertIsNone(parsed.lot_identity_warning)
        self.assertEqual(parsed.data["批次"].unique().tolist(), ["FA65-5405"])

    def test_rejects_lot_mismatch_outside_piece_suffix(self):
        cases = (
            {
                "metadata_manufacturing_lot": "M000000002-003",
                "message": "filename=M000000001-004 C000001.00",
            },
            {
                "metadata_manufacturing_lot": "M000000001-003",
                "metadata_batch": "C000002.00",
                "message": "Lot=M000000001-003 C000002.00",
            },
        )
        for case in cases:
            with self.subTest(case=case), tempfile.TemporaryDirectory() as temp:
                source_options = dict(case)
                message = source_options.pop("message")
                path = _make_source(
                    Path(temp), manufacturing_lot="M000000001-004", **source_options
                )
                with self.assertRaisesRegex(DianjiFormatError, message):
                    parse_powertech_file(path)

    def test_rejects_changed_item_layout_instead_of_misaligning_columns(self):
        with tempfile.TemporaryDirectory() as temp:
            changed = ITEM_NAMES.copy()
            changed[15] = "BVDSS"  # item 16 must be VTH
            path = _make_source(Path(temp), item_names=changed)
            with self.assertRaisesRegex(DianjiFormatError, "Item #16"):
                parse_powertech_file(path)

    def test_rejects_real_binary_xls(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "TESTPRODUCT-7E00_M000000001-001 C000001.00 ALL260101000000.xls"
            path.write_bytes(b"\xd0\xcf\x11\xe0binary")
            with self.assertRaisesRegex(DianjiFormatError, "PowerTECH"):
                parse_powertech_file(path)


class DianjiCleanerTests(unittest.TestCase):
    def test_merges_batches_and_writes_reference_raw_workbook(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            output_dir = root / "output"
            input_dir.mkdir()
            _make_source(input_dir)
            _make_source(
                input_dir,
                manufacturing_lot="M000000002-001",
                batch="C000002.00",
                verified_tail_variant=True,
            )
            cleaner = DianjiDCCleaner(input_dir, output_dir)

            self.assertTrue(cleaner.process_all())

            self.assertEqual(cleaner.last_output_file.name, "TESTPRODUCT-7E00 DJ PAT.xlsx")
            self.assertEqual(cleaner.last_output_file.parent.name, "TESTPRODUCT_001")
            result = pd.read_excel(cleaner.last_output_file, sheet_name="RAW")
            self.assertEqual(result.shape, (6, 21))
            self.assertEqual(result["NUM"].tolist(), list(range(1, 7)))
            self.assertEqual(result["批次"].value_counts().to_dict(), {"C000001.00": 3, "C000002.00": 3})
            self.assertEqual(cleaner.last_run_summary["source_rows"], 8)
            self.assertEqual(cleaner.last_run_summary["dropped_before_dvds"], 2)
            self.assertTrue(cleaner.last_scatter_manifest.is_file())
            self.assertEqual(
                cleaner.last_scatter_manifest.parent,
                cleaner.last_output_file.parent,
            )
            manifest, data, specs = load_scatter_bundle(
                cleaner.last_scatter_manifest
            )
            self.assertEqual(manifest["factory"], "电基")
            self.assertEqual(manifest["data_type"], "FT-ALL")
            self.assertEqual(len(data), 6)
            self.assertEqual(data["Source_ID"].nunique(), 2)
            self.assertEqual(
                specs.loc[specs["Parameter"] == "DVDS(mV)", "High_Limit"]
                .dropna()
                .unique()
                .tolist(),
                [85.0],
            )

    def test_reports_tolerated_stale_lot_piece_suffix(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            input_dir = root / "input"
            input_dir.mkdir()
            _make_source(
                input_dir,
                manufacturing_lot="M000000001-004",
                metadata_manufacturing_lot="M000000001-003",
            )
            cleaner = DianjiDCCleaner(input_dir, root / "output")

            with self.assertLogs("factories.dianji.dc_cleaner", level="WARNING") as logs:
                self.assertTrue(cleaner.process_all())

            self.assertIn("Lot 片号后缀未刷新", "\n".join(logs.output))
            self.assertEqual(len(cleaner.last_run_summary["identity_warnings"]), 1)

    def test_output_product_name_removes_only_trailing_package_code(self):
        self.assertEqual(
            output_product_name("NCEAP016N85LL(M)-3E00"),
            "NCEAP016N85LL(M)",
        )
        self.assertEqual(output_product_name("PRODUCT"), "PRODUCT")

    def test_next_output_path_uses_product_folder_sequence(self):
        with tempfile.TemporaryDirectory() as temp:
            output_dir = Path(temp)
            product = "NCEAP016N85LL(M)-3E00"
            first = next_output_path(output_dir, product)
            self.assertEqual(first.parent.name, "NCEAP016N85LL(M)_001")
            self.assertEqual(first.name, f"{product} DJ PAT.xlsx")
            first.touch()
            second = next_output_path(output_dir, product)
            self.assertEqual(second.parent.name, "NCEAP016N85LL(M)_002")
            self.assertEqual(second.name, f"{product} DJ PAT.xlsx")


if __name__ == "__main__":
    unittest.main()
