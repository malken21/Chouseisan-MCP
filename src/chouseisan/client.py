from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Sequence

from chouseisan.models import (
    AvailabilityStatus,
    DateSummary,
    EventInfo,
    Participant,
)

logger = logging.getLogger(__name__)


class ChouseisanError(Exception):
    """調整さんクライアントの基底例外クラス"""
    pass


class NetworkError(ChouseisanError):
    """ネットワーク通信エラー"""
    pass


class ScrapingError(ChouseisanError):
    """スクレイピングエラー"""
    pass


def parse_availability_status(val: Any) -> int:
    """
    多様な出欠入力値を内部数値 (2: ○, 1: △, 0: ×) に変換します。
    後方互換性のため int (2, 1, 0) を返却します。
    """
    return int(AvailabilityStatus.from_value(val))


def parse_availability_list(input_val: Sequence[Any] | str | None) -> list[int]:
    """
    文字列、JSON文字列、またはリストを出欠数値のリスト [2, 1, 0, ...] に変換します。

    Args:
        input_val: リスト、JSON文字列 (" [2, 1, 0] ")、またはカンマ/スペース区切り文字列

    Returns:
        list[int]: 各日程に対する出欠数値リスト (2: ○, 1: △, 0: ×)
    """
    if input_val is None:
        return []

    if isinstance(input_val, str):
        s = input_val.strip()
        if not s:
            return []

        # JSON形式のリスト解釈
        if s.startswith("[") and s.endswith("]"):
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    return [parse_availability_status(x) for x in parsed]
            except json.JSONDecodeError:
                pass

        # カンマまたは空白区切り
        delimiter = "," if "," in s else " "
        parts = [p.strip() for p in s.split(delimiter) if p.strip()]
        return [parse_availability_status(p) for p in parts]

    if isinstance(input_val, (list, tuple)):
        return [parse_availability_status(x) for x in input_val]

    return []


def format_event_info(info: dict[str, Any] | EventInfo) -> str:
    """
    イベント情報（辞書または EventInfo）を整形されたテキスト文字列に変換します。
    """
    if isinstance(info, EventInfo):
        return info.format_text()

    # dict の場合、EventInfo を構築して整形
    summary_dict: dict[str, DateSummary] = {}
    for d, s in info.get("summary", {}).items():
        if isinstance(s, dict):
            summary_dict[d] = DateSummary(
                ok=s.get("ok", 0),
                tri=s.get("tri", 0),
                ng=s.get("ng", 0),
            )

    participants_list: list[Participant] = []
    for p in info.get("participants", []):
        if isinstance(p, dict):
            participants_list.append(
                Participant(
                    name=p.get("name", "名無し"),
                    comment=p.get("comment", ""),
                    availability=p.get("availability", {}),
                )
            )

    event_obj = EventInfo(
        title=info.get("title", ""),
        url=info.get("url", ""),
        dates=info.get("dates", []),
        summary=summary_dict,
        participants=participants_list,
    )
    return event_obj.format_text()


class ChouseisanClient:
    """調整さん (chouseisan.com) を操作するための非同期クライアントクラス"""

    BASE_URL = "https://chouseisan.com"

    def __init__(self, headless: bool | None = None, timeout: int = 15000) -> None:
        if headless is None:
            headless_env = os.environ.get("HEADLESS", "true").lower()
            self.headless = headless_env in ("true", "1", "yes")
        else:
            self.headless = headless
        self.timeout = timeout
        self._playwright: Any = None
        self._browser: Any = None

    async def __aenter__(self) -> ChouseisanClient:
        """非同期コンテキストマネージャによるブラウザ再利用の開始"""
        from playwright.async_api import async_playwright
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(headless=self.headless)
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """非同期コンテキストマネージャ終了時のリソース解放"""
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None

    @asynccontextmanager
    async def _page_session(self) -> AsyncIterator[Any]:
        """
        単一操作用の Page インスタンスを提供する非同期コンテキストマネージャ。
        クライアント自体のコンテキスト外で呼ばれた場合は都度起動・解放を行う。
        """
        if self._browser:
            # 既存セッションの再利用
            page = await self._browser.new_page()
            page.set_default_timeout(self.timeout)
            try:
                yield page
            finally:
                await page.close()
        else:
            # 一時セッションの起動
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=self.headless)
                try:
                    page = await browser.new_page()
                    page.set_default_timeout(self.timeout)
                    yield page
                finally:
                    await browser.close()

    async def create_event(self, title: str, memo: str = "", dates: str = "") -> str:
        """
        新しい調整さんイベントを作成します。

        Args:
            title: イベントタイトル
            memo: イベントの補足説明・メモ
            dates: 候補日程（改行区切り）

        Returns:
            str: 作成されたイベントURL
        """
        if not title or not title.strip():
            raise ChouseisanError("イベントタイトルは必須です。")

        logger.info(f"Creating Chouseisan event: '{title}'")
        try:
            async with self._page_session() as page:
                await page.goto(self.BASE_URL, wait_until="domcontentloaded")

                await page.fill('input[name="name"]', title)
                await page.fill('textarea[name="comment"]', memo)
                await page.fill('textarea[name="kouho"]', dates)

                # 送信ボタンクリック
                btn_locator = page.locator(
                    '#createBtn, #create_event_submit_btn, button:has-text("出欠表をつくる")'
                ).first
                if await btn_locator.count() == 0:
                    raise ScrapingError("イベント作成ボタンが見つかりませんでした。")
                await btn_locator.click()

                # 作成完了後のURL取得
                try:
                    await page.wait_for_selector('input.new-event-url-input', timeout=self.timeout)
                    url = await page.input_value('input.new-event-url-input')
                except Exception:
                    if "s?h=" in page.url:
                        url = page.url
                    else:
                        await page.wait_for_url("**/s?h=*", timeout=5000)
                        url = page.url

                if not url or "chouseisan.com" not in url:
                    raise ScrapingError(f"無効なイベントURLが生成されました: {url}")

                logger.info(f"Event created successfully: {url}")
                return url
        except ChouseisanError:
            raise
        except Exception as e:
            logger.exception("Failed to create event")
            raise ChouseisanError(f"イベントの作成に失敗しました: {e}") from e

    async def get_event_info(self, event_url: str) -> dict[str, Any]:
        """
        イベント情報（タイトル、候補日程一覧、集計、各回答者の出欠情報、URL）を取得します。

        Args:
            event_url: イベントのURL

        Returns:
            dict[str, Any]: イベント情報辞書 (EventInfo.to_dict 準拠)
        """
        event_info_obj = await self.fetch_event_info(event_url)
        return event_info_obj.to_dict()

    async def fetch_event_info(self, event_url: str) -> EventInfo:
        """
        イベント情報を取得し、型安全な EventInfo オブジェクトとして返却します。
        """
        if not event_url or not event_url.startswith("http"):
            raise ChouseisanError(f"無効なURLフォーマットです: {event_url}")

        logger.info(f"Fetching event info: {event_url}")
        try:
            async with self._page_session() as page:
                await page.goto(event_url, wait_until="domcontentloaded")

                # タイトル取得
                title = ""
                if await page.locator('h1').count() > 0:
                    title = (await page.locator('h1').inner_text()).strip()
                elif await page.locator('.event-name').count() > 0:
                    title = (await page.locator('.event-name').inner_text()).strip()

                # 出欠表テーブル(#nittei)の構造化データ抽出
                table_data = await page.evaluate('''() => {
                    const table = document.querySelector('#nittei');
                    if (!table) return null;

                    const rows = Array.from(table.querySelectorAll('tr'));
                    if (rows.length === 0) return null;

                    const getText = (el) => (el && el.textContent ? el.textContent.trim() : '');

                    // 1行目: ヘッダー (日程, ◯, △, ×, member_0, member_1, ...)
                    const headerRow = rows[0];
                    const headerCells = Array.from(headerRow.children);
                    const memberNames = [];
                    for (let i = 4; i < headerCells.length; i++) {
                        memberNames.push(getText(headerCells[i]));
                    }

                    // コメント行と日程行を分類
                    let commentRow = null;
                    const dateRows = [];
                    for (let i = 1; i < rows.length; i++) {
                        const row = rows[i];
                        const firstCellText = row.children[0] ? getText(row.children[0]) : '';
                        if (row.classList.contains('comment') || firstCellText === 'コメント') {
                            commentRow = row;
                        } else {
                            dateRows.push(row);
                        }
                    }

                    // コメント抽出
                    const comments = [];
                    if (commentRow) {
                        const commentCells = Array.from(commentRow.children);
                        for (let i = 4; i < commentCells.length; i++) {
                            comments.push(getText(commentCells[i]));
                        }
                    }
                    while (comments.length < memberNames.length) {
                        comments.push('');
                    }

                    // 日程・集計・回答抽出
                    const dates = [];
                    const summary = {};
                    const memberResponses = memberNames.map(() => []);

                    for (const row of dateRows) {
                        const cells = Array.from(row.children);
                        if (cells.length === 0) continue;
                        const dateText = cells[0] ? getText(cells[0]) : '';
                        if (!dateText || dateText === '日程') continue;
                        dates.push(dateText);

                        const parseCount = (cell) => {
                            if (!cell) return 0;
                            const match = getText(cell).match(/(\\d+)/);
                            return match ? parseInt(match[1], 10) : 0;
                        };
                        const okCount = cells[1] ? parseCount(cells[1]) : 0;
                        const triCount = cells[2] ? parseCount(cells[2]) : 0;
                        const ngCount = cells[3] ? parseCount(cells[3]) : 0;
                        summary[dateText] = { ok: okCount, tri: triCount, ng: ngCount };

                        for (let m = 0; m < memberNames.length; m++) {
                            const cell = cells[4 + m];
                            let status = '-';
                            if (cell) {
                                const img = cell.querySelector('img');
                                if (img) {
                                    const src = img.getAttribute('src') || '';
                                    const alt = (img.getAttribute('alt') || '').trim();
                                    if (src.includes('mark-ok') || alt.endsWith('まる') || alt.endsWith('○') || alt.endsWith('OK') || alt.endsWith('ok')) {
                                        status = '○';
                                    } else if (src.includes('mark-tri') || alt.endsWith('さんかく') || alt.endsWith('△') || alt.endsWith('TRI') || alt.endsWith('tri')) {
                                        status = '△';
                                    } else if (src.includes('mark-x') || alt.endsWith('ばつ') || alt.endsWith('×') || alt.endsWith('NG') || alt.endsWith('ng')) {
                                        status = '×';
                                    }
                                } else {
                                    const text = getText(cell);
                                    if (text === '○' || text === '◯' || text === '2') status = '○';
                                    else if (text === '△' || text === '1') status = '△';
                                    else if (text === '×' || text === '0') status = '×';
                                }
                            }
                            memberResponses[m].push(status);
                        }
                    }

                    const participants = memberNames.map((name, idx) => {
                        const availDict = {};
                        dates.forEach((d, dIdx) => {
                            availDict[d] = memberResponses[idx][dIdx] || '-';
                        });
                        return {
                            name: name,
                            comment: comments[idx] || '',
                            availability: availDict
                        };
                    });

                    return {
                        dates: dates,
                        summary: summary,
                        participants: participants
                    };
                }''')

                dates: list[str] = []
                summary_map: dict[str, DateSummary] = {}
                participants: list[Participant] = []

                if table_data:
                    dates = table_data.get("dates", [])
                    raw_summary = table_data.get("summary", {})
                    for d, s in raw_summary.items():
                        summary_map[d] = DateSummary(
                            ok=s.get("ok", 0),
                            tri=s.get("tri", 0),
                            ng=s.get("ng", 0),
                        )
                    for p in table_data.get("participants", []):
                        participants.append(
                            Participant(
                                name=p.get("name", "名無し"),
                                comment=p.get("comment", ""),
                                availability=p.get("availability", {}),
                            )
                        )

                if not dates:
                    # フォールバックセレクタ
                    nittei_locator = page.locator('#nittei tr td:first-child')
                    nittei_count = await nittei_locator.count()
                    if nittei_count > 0:
                        for i in range(nittei_count):
                            td_text = (await nittei_locator.nth(i).inner_text()).strip()
                            if td_text and td_text != "日程":
                                dates.append(td_text)

                if not dates:
                    th_locator = page.locator('#attendance-table th.valign-middle')
                    th_count = await th_locator.count()
                    if th_count > 2:
                        for i in range(2, th_count):
                            text = (await th_locator.nth(i).inner_text()).strip()
                            if text:
                                dates.append(text)

                logger.info(
                    f"Retrieved event '{title}' with {len(dates)} dates and {len(participants)} participants."
                )
                return EventInfo(
                    title=title,
                    url=event_url,
                    dates=dates,
                    summary=summary_map,
                    participants=participants,
                )
        except ChouseisanError:
            raise
        except Exception as e:
            logger.exception(f"Failed to fetch event info for {event_url}")
            raise ChouseisanError(f"イベント情報の取得に失敗しました: {e}") from e

    async def add_response(
        self,
        event_url: str,
        name: str,
        comment: str = "",
        availability: Sequence[Any] | str | None = None,
    ) -> bool:
        """
        イベントに出欠回答を追加・更新します。

        Args:
            event_url: イベントのURL
            name: 回答者の名前
            comment: コメント（ひとこと）
            availability: 各日程の出欠回答 (リスト、JSON文字列、カンマ区切り文字列)

        Returns:
            bool: 登録成功フラグ
        """
        if not event_url or not event_url.startswith("http"):
            raise ChouseisanError(f"無効なURLフォーマットです: {event_url}")
        if not name or not name.strip():
            raise ChouseisanError("回答者名は必須です。")

        avail_statuses = [
            AvailabilityStatus.from_value(x)
            for x in parse_availability_list(availability)
        ]
        logger.info(
            f"Adding response for '{name}' to {event_url} (availability: {[int(s) for s in avail_statuses]})"
        )

        try:
            async with self._page_session() as page:
                await page.goto(event_url, wait_until="domcontentloaded")

                # "出欠を入力する" ボタンをクリック
                add_btn = page.locator('#add_btn, button:has-text("出欠を入力する")').first
                if await add_btn.count() == 0:
                    raise ScrapingError("出欠入力ボタンが見つかりませんでした。")
                await add_btn.click()

                # フォーム待機
                await page.wait_for_selector('input[name="name"]', timeout=self.timeout)

                # 名前およびコメント入力
                await page.fill('input[name="name"]', name)

                if await page.locator('input[name="hitokoto"]').count() > 0:
                    await page.fill('input[name="hitokoto"]', comment)

                # 各日程の出欠選択
                for i, status in enumerate(avail_statuses):
                    field_name = f"kouho{i+1}"
                    if await page.locator(f'input[name="{field_name}"]').count() > 0:
                        btn_class = status.button_class
                        await page.evaluate(f'''() => {{
                            const input = document.querySelector('input[name="{field_name}"]');
                            if (input && input.parentElement) {{
                                const btn = input.parentElement.querySelector('.{btn_class}');
                                if (btn) btn.click();
                            }}
                        }}''')
                        await page.wait_for_timeout(50)

                # 保存ボタンをクリック
                save_btn = page.locator('#memUpdBtn, input[value="入力する"], button:has-text("入力する")').first
                if await save_btn.count() == 0:
                    raise ScrapingError("保存ボタンが見つかりませんでした。")
                await save_btn.click()

                await page.wait_for_load_state("domcontentloaded")
                logger.info(f"Successfully registered availability for '{name}'")
                return True
        except ChouseisanError:
            raise
        except Exception as e:
            logger.exception("Failed to add response")
            raise ChouseisanError(f"出欠の登録に失敗しました: {e}") from e
