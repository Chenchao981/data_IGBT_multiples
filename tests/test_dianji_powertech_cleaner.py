import tempfile
import unittest
from pathlib import Path
import re

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
DJ8_PRODUCT = "NCEAP020N10LL(M)-7E00"


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
    compact_layout=False,
):
    if compact_layout:
        verified_tail_variant = True
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
    bias1[14] = "M#=14"
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
    if compact_layout:
        lines = _to_compact_32_layout(lines)
    path.write_text("\r\n".join(lines), encoding="gb18030")
    return path


def _make_dj8_source(
    directory: Path,
    *,
    copy_suffix="(1)",
    data_batch="C207458.07",
    data_test_tag="DC260716024650",
    test_product=DJ8_PRODUCT,
    test_program=None,
):
    manufacturing_lot = "M260616003-001"
    batch = "C207458.07"
    test_tag = "DC260716024650"
    legacy = _make_source(
        directory,
        manufacturing_lot=manufacturing_lot,
        batch=batch,
    )
    lines = legacy.read_text(encoding="gb18030").splitlines()
    lines[1] = (
        "DataFileName:\t\tD:\\DC数据\\"
        f"{manufacturing_lot} {data_batch} {data_test_tag}.plf"
    )
    test_program = test_program or (
        f"{test_product}_ALL_M08M09_Ver1.07_20260520.ptf"
    )
    lines[2] = (
        "TestFileName:\t\tD:\\PowerTECH\\Programs\\"
        f"{test_program}"
    )
    path = directory / f"{manufacturing_lot} {batch} {test_tag}{copy_suffix}.xls"
    path.write_text("\r\n".join(lines), encoding="gb18030")
    legacy.unlink()
    return path


def _to_compact_32_layout(lines):
    """Remove verified SAME Items 17-18 and renumber later test Items."""
    shaped_rows = {
        "Item Name", "Bias1", "Bias2", "Bias3", "Min Limit", "Max Limit",
        "Serial#",
    }
    reference_map = {19: 17, 20: 18, 21: 19}
    compact = []
    for line in lines:
        fields = line.split("\t")
        if len(fields) > 20 and (fields[0] in shaped_rows or fields[0].isdigit()):
            del fields[19:21]
            if fields[0] == "Item Name":
                for item_number, index in enumerate(range(3, len(fields)), start=1):
                    _old_number, base_name = fields[index].split(" ", 1)
                    fields[index] = f"{item_number} {base_name}"
            elif fields[0] in {"Bias1", "Bias2", "Bias3"}:
                fields = [
                    re.sub(
                        r"#(\d+)",
                        lambda match: f"#{reference_map.get(int(match.group(1)), int(match.group(1)))}",
                        value,
                    )
                    for value in fields
                ]
        compact.append("\t".join(fields))
    return compact


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
            (
                "TESTPRODUCT-7E00_M260310017-001 C190388.00 DC M08260327032511.xls",
                "M260310017-001", "C190388.00", "DC M08260327032511",
            ),
            (
                "TESTPRODUCT-7E00_m260323017-001c192810.00260415041728.xls",
                "M260323017-001", "C192810.00", "260415041728",
            ),
            (
                "TESTPRODUCT-7E00_m260325005-006-A-A c192811.00260419014419.xls",
                "M260325005-006-A-A", "C192811.00", "260419014419",
            ),
        )
        for filename, manufacturing_lot, batch, test_tag in cases:
            with self.subTest(filename=filename):
                identity = parse_dianji_filename(filename)
                self.assertEqual(identity.manufacturing_lot, manufacturing_lot)
                self.assertEqual(identity.batch, batch)
                self.assertEqual(identity.test_tag, test_tag)

    def test_accepts_dj1_e_batch_and_copy_suffix(self):
        identity = parse_dianji_filename(
            "NCEP039N10M-M_M250528015-023 E002413.00 "
            "ALL250609023222(1).xls"
        )

        self.assertEqual(identity.product, "NCEP039N10M-M")
        self.assertEqual(identity.manufacturing_lot, "M250528015-023")
        self.assertEqual(identity.batch, "E002413.00")
        self.assertEqual(identity.test_tag, "ALL250609023222")
        self.assertEqual(identity.source_segment, "copy-1")

    def test_rejects_unverified_batch_pattern(self):
        with self.assertRaisesRegex(DianjiFormatError, "电基文件名不符合"):
            parse_dianji_filename(
                "TESTPRODUCT-7E00_M260604005-001 FB65-5405 ALL260705044541.xls"
            )

    def test_rejects_unverified_dj6_like_filename_variants(self):
        cases = (
            "TESTPRODUCT-7E00_M260310017-001-B-B C190388.00260327032511.xls",
            "TESTPRODUCT-7E00_M260310017-001 C190388.00 DC M09260327032511.xls",
        )
        for filename in cases:
            with self.subTest(filename=filename), self.assertRaisesRegex(
                DianjiFormatError, "电基文件名不符合"
            ):
                parse_dianji_filename(filename)


class PowerTechParserTests(unittest.TestCase):
    def test_accepts_dj8_metadata_identity_with_optional_copy_suffix(self):
        for copy_suffix, source_segment in (("", None), ("(1)", "copy-1"), ("(27)", "copy-27")):
            with self.subTest(copy_suffix=copy_suffix), tempfile.TemporaryDirectory() as temp:
                parsed = parse_powertech_file(
                    _make_dj8_source(Path(temp), copy_suffix=copy_suffix)
                )

            self.assertEqual(parsed.identity.product, DJ8_PRODUCT)
            self.assertEqual(parsed.identity.manufacturing_lot, "M260616003-001")
            self.assertEqual(parsed.identity.batch, "C207458.07")
            self.assertEqual(parsed.identity.test_tag, "DC260716024650")
            self.assertEqual(parsed.identity.source_segment, source_segment)
            self.assertEqual(parsed.source_rows, 4)
            self.assertEqual(parsed.kept_rows, 3)

    def test_accepts_verified_m08m15_metadata_program(self):
        program = f"{DJ8_PRODUCT}_ALL_M08M15_Ver1.07_20260520.ptf"
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_powertech_file(
                _make_dj8_source(
                    Path(temp),
                    copy_suffix="",
                    test_program=program,
                )
            )

        self.assertEqual(parsed.identity.product, DJ8_PRODUCT)
        self.assertEqual(parsed.identity.manufacturing_lot, "M260616003-001")
        self.assertEqual(parsed.identity.batch, "C207458.07")
        self.assertEqual(parsed.identity.test_tag, "DC260716024650")
        self.assertIsNone(parsed.identity.source_segment)
        self.assertEqual(parsed.source_rows, 4)
        self.assertEqual(parsed.kept_rows, 3)

    def test_rejects_dj8_metadata_identity_conflicts(self):
        cases = (
            ({"data_batch": "C207459.07"}, "DataFileName 身份不一致"),
            ({"data_test_tag": "DC260716024651"}, "DataFileName 身份不一致"),
            ({"test_product": "UNKNOWN-7E00"}, "TestFileName 产品/程序未经验证"),
            (
                {"test_program": f"{DJ8_PRODUCT}_UNREVIEWED.ptf"},
                "TestFileName 产品/程序未经验证",
            ),
            (
                {
                    "test_program":
                        f"{DJ8_PRODUCT}_ALL_M08M16_Ver1.07_20260520.ptf"
                },
                "TestFileName 产品/程序未经验证",
            ),
            ({"copy_suffix": "(copy)"}, "电基文件名不符合"),
        )
        for options, message in cases:
            with self.subTest(options=options), tempfile.TemporaryDirectory() as temp:
                source = _make_dj8_source(Path(temp), **options)
                with self.assertRaisesRegex(DianjiFormatError, message):
                    parse_powertech_file(source)

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

    def test_accepts_verified_compact_32_item_layout_with_stable_output(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_powertech_file(
                _make_source(Path(temp), compact_layout=True)
            )

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
        self.assertEqual(parsed.data.loc[0, "ISGS10(nA)"], -1.3174)
        self.assertEqual(parsed.data.loc[0, "IGSS10(nA)"], 0.099)
        self.assertEqual(parsed.data.loc[0, "IDSS90(nA)"], 11.819)
        self.assertEqual(parsed.data.loc[0, "DELTA BV"], 0.0152)
        self.assertEqual(parsed.data.loc[0, "DELTA VTH"], 0.1481)

    def test_standard_34_and_compact_32_share_semantic_parameter_keys(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            standard_dir = root / "standard"
            compact_dir = root / "compact"
            standard_dir.mkdir()
            compact_dir.mkdir()
            standard = parse_powertech_file(_make_source(standard_dir))
            compact = parse_powertech_file(
                _make_source(compact_dir, compact_layout=True)
            )

        self.assertEqual(standard.parameter_keys, compact.parameter_keys)
        self.assertEqual(
            standard.data.attrs["parameter_keys"], standard.parameter_keys
        )
        self.assertEqual(
            compact.data.attrs["parameter_keys"], compact.parameter_keys
        )

    def test_accepts_verified_a_a_lot_suffix_in_filename_and_metadata(self):
        with tempfile.TemporaryDirectory() as temp:
            parsed = parse_powertech_file(
                _make_source(
                    Path(temp),
                    manufacturing_lot="M000000001-006-A-A",
                )
            )

        self.assertEqual(
            parsed.identity.manufacturing_lot,
            "M000000001-006-A-A",
        )
        self.assertIsNone(parsed.lot_identity_warning)

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
            with self.assertRaisesRegex(DianjiFormatError, "DELTA Item #34"):
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
