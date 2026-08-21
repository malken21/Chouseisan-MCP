from __future__ import annotations

from dataclasses import dataclass, field
from enum import IntEnum
from typing import Any


class AvailabilityStatus(IntEnum):
    """出欠ステータスを表す列挙型"""
    NG = 0
    TRIANGLE = 1
    OK = 2

    @property
    def symbol(self) -> str:
        """表示用記号を取得"""
        mapping = {
            AvailabilityStatus.OK: "○",
            AvailabilityStatus.TRIANGLE: "△",
            AvailabilityStatus.NG: "×",
        }
        return mapping[self]

    @property
    def button_class(self) -> str:
        """HTMLフォーム上の対応ボタンスタイルクラス名を取得"""
        mapping = {
            AvailabilityStatus.OK: "oax-0",
            AvailabilityStatus.TRIANGLE: "oax-1",
            AvailabilityStatus.NG: "oax-2",
        }
        return mapping[self]

    @classmethod
    def from_value(cls, val: Any) -> AvailabilityStatus:
        """
        多様な入力表現 (数値, 記号, 日本語/英語テキスト) を安全に出欠ステータスへ変換。
        判別不能な場合はデフォルトで NG (0) を返却。
        """
        if isinstance(val, AvailabilityStatus):
            return val
        if isinstance(val, int):
            return cls(val) if val in cls._value2member_map_ else cls.NG

        normalized = str(val).strip().lower()
        mapping = {
            # OK (2)
            "2": cls.OK,
            "○": cls.OK,
            "◯": cls.OK,
            "o": cls.OK,
            "ok": cls.OK,
            "maru": cls.OK,
            "yes": cls.OK,
            "true": cls.OK,
            "参加": cls.OK,
            "出席": cls.OK,
            # TRIANGLE (1)
            "1": cls.TRIANGLE,
            "△": cls.TRIANGLE,
            "▲": cls.TRIANGLE,
            "tri": cls.TRIANGLE,
            "triangle": cls.TRIANGLE,
            "maybe": cls.TRIANGLE,
            "sankaku": cls.TRIANGLE,
            "未定": cls.TRIANGLE,
            "どちらでも": cls.TRIANGLE,
            # NG (0)
            "0": cls.NG,
            "×": cls.NG,
            "x": cls.NG,
            "ng": cls.NG,
            "batsu": cls.NG,
            "no": cls.NG,
            "false": cls.NG,
            "不参加": cls.NG,
            "欠席": cls.NG,
        }
        if normalized in mapping:
            return mapping[normalized]

        try:
            num = int(normalized)
            return cls(num) if num in cls._value2member_map_ else cls.NG
        except ValueError:
            return cls.NG


@dataclass(slots=True)
class DateSummary:
    """各候補日程の集計データ"""
    ok: int = 0
    tri: int = 0
    ng: int = 0

    def to_dict(self) -> dict[str, int]:
        return {"ok": self.ok, "tri": self.tri, "ng": self.ng}


@dataclass(slots=True)
class Participant:
    """参加者の出欠回答データ"""
    name: str
    comment: str = ""
    availability: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "comment": self.comment,
            "availability": self.availability,
        }


@dataclass(slots=True)
class EventInfo:
    """調整さんイベントの全体情報データ"""
    title: str = ""
    url: str = ""
    dates: list[str] = field(default_factory=list)
    summary: dict[str, DateSummary] = field(default_factory=dict)
    participants: list[Participant] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "dates": list(self.dates),
            "summary": {d: s.to_dict() if isinstance(s, DateSummary) else s for d, s in self.summary.items()},
            "participants": [p.to_dict() if isinstance(p, Participant) else p for p in self.participants],
        }

    def format_text(self) -> str:
        """可読性の高いサマリー文字列を生成"""
        if self.dates:
            dates_lines: list[str] = []
            for d in self.dates:
                if d in self.summary:
                    s = self.summary[d]
                    ok = s.ok if isinstance(s, DateSummary) else s.get("ok", 0)
                    tri = s.tri if isinstance(s, DateSummary) else s.get("tri", 0)
                    ng = s.ng if isinstance(s, DateSummary) else s.get("ng", 0)
                    dates_lines.append(f"  - {d} (○: {ok}, △: {tri}, ×: {ng})")
                else:
                    dates_lines.append(f"  - {d}")
            dates_str = "\n".join(dates_lines)
        else:
            dates_str = "  (候補日程が見つかりませんでした)"

        if self.participants:
            part_lines = [f"■ 回答者一覧 ({len(self.participants)}名):"]
            for p in self.participants:
                name = p.name if isinstance(p, Participant) else p.get("name", "名無し")
                comment = p.comment if isinstance(p, Participant) else p.get("comment", "")
                avail = p.availability if isinstance(p, Participant) else p.get("availability", {})

                part_lines.append(f"  - {name}:")
                for d in self.dates:
                    status = avail.get(d, "-")
                    part_lines.append(f"    - {d}: {status}")
                if comment:
                    part_lines.append(f"    - コメント: {comment}")
            participants_str = "\n".join(part_lines)
        else:
            participants_str = "■ 回答者一覧:\n  (回答者はまだいません)"

        return (
            f"■ イベント名: {self.title}\n"
            f"■ URL: {self.url}\n"
            f"■ 候補日程・集計:\n{dates_str}\n"
            f"{participants_str}"
        )
