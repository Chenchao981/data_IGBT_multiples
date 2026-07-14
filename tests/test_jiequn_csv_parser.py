import unittest

from factories.jiequn.csv_parser import _dedupe_param_columns


class DedupeParamColumnsTests(unittest.TestCase):
    def test_repeated_rdon_columns_are_preserved_in_source_order(self):
        columns, names = _dedupe_param_columns(
            [0, 1, 22, 23, 48, 49],
            [
                "Serial",
                "Bin",
                "RDON20(mR)",
                "RDON20(mR)",
                "RDON20(mR)",
                "RDON20(mR)",
            ],
        )

        self.assertEqual(columns, [0, 1, 22, 23, 48, 49])
        self.assertEqual(
            names,
            [
                "Serial",
                "Bin",
                "RDON20-1(mR)",
                "RDON20-2(mR)",
                "RDON20-3(mR)",
                "RDON20-4(mR)",
            ],
        )

    def test_unique_parameter_name_is_unchanged(self):
        columns, names = _dedupe_param_columns(
            [0, 1, 22],
            ["Serial", "Bin", "RDON20(mR)"],
        )

        self.assertEqual(columns, [0, 1, 22])
        self.assertEqual(names, ["Serial", "Bin", "RDON20(mR)"])


if __name__ == "__main__":
    unittest.main()
