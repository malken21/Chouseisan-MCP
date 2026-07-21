import unittest
from chouseisan.client import parse_availability_status, parse_availability_list

class TestChouseisanClientUtils(unittest.TestCase):
    def test_parse_availability_status(self):
        # 数値入力のテスト
        self.assertEqual(parse_availability_status(2), 2)
        self.assertEqual(parse_availability_status(1), 1)
        self.assertEqual(parse_availability_status(0), 0)
        self.assertEqual(parse_availability_status(99), 0)

        # 記号入力のテスト
        self.assertEqual(parse_availability_status("○"), 2)
        self.assertEqual(parse_availability_status("△"), 1)
        self.assertEqual(parse_availability_status("×"), 0)
        self.assertEqual(parse_availability_status("o"), 2)
        self.assertEqual(parse_availability_status("x"), 0)

        # キーワード入力のテスト
        self.assertEqual(parse_availability_status("ok"), 2)
        self.assertEqual(parse_availability_status("maybe"), 1)
        self.assertEqual(parse_availability_status("ng"), 0)
        self.assertEqual(parse_availability_status("参加"), 2)
        self.assertEqual(parse_availability_status("不参加"), 0)

    def test_parse_availability_list(self):
        # 数値リスト
        self.assertEqual(parse_availability_list([2, 1, 0]), [2, 1, 0])
        # 記号リスト
        self.assertEqual(parse_availability_list(["○", "△", "×"]), [2, 1, 0])
        # 混在リスト
        self.assertEqual(parse_availability_list(["2", 1, "NG"]), [2, 1, 0])

        # JSON文字列のパース
        self.assertEqual(parse_availability_list("[2, 1, 0]"), [2, 1, 0])
        self.assertEqual(parse_availability_list('["○", "△", "×"]'), [2, 1, 0])

        # カンマ・スペース区切り文字列
        self.assertEqual(parse_availability_list("○, △, ×"), [2, 1, 0])
        self.assertEqual(parse_availability_list("2 1 0"), [2, 1, 0])

        # 境界値・無効値
        self.assertEqual(parse_availability_list(None), [])
        self.assertEqual(parse_availability_list(""), [])

if __name__ == "__main__":
    unittest.main()
