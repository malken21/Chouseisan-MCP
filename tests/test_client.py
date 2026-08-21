from __future__ import annotations

import unittest
from chouseisan.models import (
    AvailabilityStatus,
    DateSummary,
    EventInfo,
    Participant,
)
from chouseisan.client import (
    parse_availability_status,
    parse_availability_list,
    format_event_info,
)


class TestAvailabilityStatus(unittest.TestCase):
    def test_enum_properties(self):
        self.assertEqual(AvailabilityStatus.OK.symbol, "○")
        self.assertEqual(AvailabilityStatus.TRIANGLE.symbol, "△")
        self.assertEqual(AvailabilityStatus.NG.symbol, "×")

        self.assertEqual(AvailabilityStatus.OK.button_class, "oax-0")
        self.assertEqual(AvailabilityStatus.TRIANGLE.button_class, "oax-1")
        self.assertEqual(AvailabilityStatus.NG.button_class, "oax-2")

    def test_from_value_various_inputs(self):
        # 数値
        self.assertEqual(AvailabilityStatus.from_value(2), AvailabilityStatus.OK)
        self.assertEqual(AvailabilityStatus.from_value(1), AvailabilityStatus.TRIANGLE)
        self.assertEqual(AvailabilityStatus.from_value(0), AvailabilityStatus.NG)
        self.assertEqual(AvailabilityStatus.from_value(99), AvailabilityStatus.NG)

        # 記号
        self.assertEqual(AvailabilityStatus.from_value("○"), AvailabilityStatus.OK)
        self.assertEqual(AvailabilityStatus.from_value("◯"), AvailabilityStatus.OK)
        self.assertEqual(AvailabilityStatus.from_value("△"), AvailabilityStatus.TRIANGLE)
        self.assertEqual(AvailabilityStatus.from_value("×"), AvailabilityStatus.NG)
        self.assertEqual(AvailabilityStatus.from_value("x"), AvailabilityStatus.NG)

        # テキスト
        self.assertEqual(AvailabilityStatus.from_value("OK"), AvailabilityStatus.OK)
        self.assertEqual(AvailabilityStatus.from_value("参加"), AvailabilityStatus.OK)
        self.assertEqual(AvailabilityStatus.from_value("maybe"), AvailabilityStatus.TRIANGLE)
        self.assertEqual(AvailabilityStatus.from_value("未定"), AvailabilityStatus.TRIANGLE)
        self.assertEqual(AvailabilityStatus.from_value("ng"), AvailabilityStatus.NG)
        self.assertEqual(AvailabilityStatus.from_value("不参加"), AvailabilityStatus.NG)


class TestChouseisanClientUtils(unittest.TestCase):
    def test_parse_availability_status(self):
        self.assertEqual(parse_availability_status(2), 2)
        self.assertEqual(parse_availability_status(1), 1)
        self.assertEqual(parse_availability_status(0), 0)
        self.assertEqual(parse_availability_status("○"), 2)
        self.assertEqual(parse_availability_status("△"), 1)
        self.assertEqual(parse_availability_status("×"), 0)
        self.assertEqual(parse_availability_status("ok"), 2)
        self.assertEqual(parse_availability_status("ng"), 0)

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
        self.assertEqual(parse_availability_list("   "), [])
        self.assertEqual(parse_availability_list("invalid json ["), [0, 0, 0])

    def test_format_event_info_dict(self):
        # 辞書型入力のフォーマット
        info_dict = {
            "title": "打ち合わせ",
            "dates": ["9/1 19:00", "9/2 20:00"],
            "url": "https://chouseisan.com/s?h=456",
            "summary": {
                "9/1 19:00": {"ok": 1, "tri": 0, "ng": 1},
                "9/2 20:00": {"ok": 2, "tri": 0, "ng": 0},
            },
            "participants": [
                {
                    "name": "ユーザーA",
                    "comment": "よろしくお願いします",
                    "availability": {"9/1 19:00": "○", "9/2 20:00": "○"},
                },
            ],
        }
        res = format_event_info(info_dict)
        self.assertIn("■ イベント名: 打ち合わせ", res)
        self.assertIn("9/1 19:00 (○: 1, △: 0, ×: 1)", res)
        self.assertIn("■ 回答者一覧 (1名):", res)
        self.assertIn("ユーザーA:", res)
        self.assertIn("コメント: よろしくお願いします", res)

    def test_format_event_info_dataclass(self):
        # EventInfo 型入力のフォーマット
        event = EventInfo(
            title="歓迎会",
            url="https://chouseisan.com/s?h=789",
            dates=["10/1 18:00"],
            summary={"10/1 18:00": DateSummary(ok=3, tri=1, ng=0)},
            participants=[
                Participant(name="Alice", comment="乾杯!", availability={"10/1 18:00": "○"}),
            ],
        )
        res = format_event_info(event)
        self.assertIn("■ イベント名: 歓迎会", res)
        self.assertIn("10/1 18:00 (○: 3, △: 1, ×: 0)", res)
        self.assertIn("Alice:", res)

        # to_dict メソッド検証
        d = event.to_dict()
        self.assertEqual(d["title"], "歓迎会")
        self.assertEqual(d["summary"]["10/1 18:00"]["ok"], 3)
        self.assertEqual(len(d["participants"]), 1)
        self.assertEqual(d["participants"][0]["name"], "Alice")


if __name__ == "__main__":
    unittest.main()
