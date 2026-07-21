import logging
import json
import os
from typing import List, Dict, Any, Optional, Union, TYPE_CHECKING

if TYPE_CHECKING:
    from playwright.async_api import Page, Browser

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
    
    Args:
        val: 数値 (0,1,2) や記号 (○, △, ×), 文字列 ("2", "1", "0", "OK", "NG", "MAYBE" など)
    
    Returns:
        int: 2 (○), 1 (△), 0 (×)
    """
    if isinstance(val, int):
        if val in (0, 1, 2):
            return val
        return 0

    s = str(val).strip().lower()
    if s in ("2", "○", "o", "ok", "maru", "yes", "true", "出席", "参加"):
        return 2
    if s in ("1", "△", "tri", "triangle", "maybe", "sankaku", "未定", "どちらでも"):
        return 1
    if s in ("0", "×", "x", "ng", "batsu", "no", "false", "欠席", "不参加"):
        return 0
    
    try:
        n = int(s)
        if n in (0, 1, 2):
            return n
    except ValueError:
        pass
    
    return 0

def parse_availability_list(input_val: Union[List[Any], str, None]) -> List[int]:
    """
    文字列、JSON文字列、またはリストを出欠数値のリスト [2, 1, 0, ...] に変換します。
    
    Args:
        input_val: リスト、JSON文字列 (" [2, 1, 0] "), またはカンマ・スペース区切り文字列
        
    Returns:
        List[int]: 各日程に対する出欠数値リスト
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
        # カンマ区切りまたは空白区切り文字列解釈
        delimiter = "," if "," in s else " "
        parts = [p.strip() for p in s.split(delimiter) if p.strip()]
        if parts:
            return [parse_availability_status(p) for p in parts]
        return []

    if isinstance(input_val, (list, tuple)):
        return [parse_availability_status(x) for x in input_val]

    return []

class ChouseisanClient:
    """調整さん (chouseisan.com) を操作するための高信頼クライアントクラス"""
    BASE_URL = "https://chouseisan.com"

    def __init__(self, headless: Optional[bool] = None, timeout: int = 15000):
        if headless is None:
            headless_env = os.environ.get("HEADLESS", "true").lower()
            self.headless = headless_env in ("true", "1", "yes")
        else:
            self.headless = headless
        self.timeout = timeout

    async def create_event(self, title: str, memo: str = "", dates: str = "") -> str:
        """
        新しい調整さんイベントを作成します。

        Args:
            title (str): イベントのタイトル
            memo (str, optional): イベントのメモ（説明文）
            dates (str, optional): 候補日程（改行区切り）

        Returns:
            str: 作成されたイベントのURL

        Raises:
            ChouseisanError: イベント作成に失敗した場合
        """
        if not title or not title.strip():
            raise ChouseisanError("イベントタイトルは必須です。")

        logger.info(f"Creating Chouseisan event: '{title}'")
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page()
                page.set_default_timeout(self.timeout)
                
                await page.goto(self.BASE_URL, wait_until="domcontentloaded")
                
                await page.fill('input[name="name"]', title)
                await page.fill('textarea[name="comment"]', memo)
                await page.fill('textarea[name="kouho"]', dates)
                
                # 送信ボタンクリック
                btn_locator = page.locator('#createBtn, #create_event_submit_btn, button:has-text("出欠表をつくる")').first
                if await btn_locator.count() > 0:
                    await btn_locator.click()
                else:
                    raise ScrapingError("イベント作成ボタンが見つかりませんでした。")
                
                # 作成完了後のURL取得
                try:
                    await page.wait_for_selector('input.new-event-url-input', timeout=self.timeout)
                    url = await page.input_value('input.new-event-url-input')
                except Exception:
                    # リダイレクト後のURLフォールバック
                    if "s?h=" in page.url:
                        url = page.url
                    else:
                        await page.wait_for_url("**/s?h=*", timeout=5000)
                        url = page.url

                if not url or "chouseisan.com" not in url:
                    raise ScrapingError(f"無効なイベントURLが生成されました: {url}")

                logger.info(f"Event created successfully: {url}")
                return url
            except Exception as e:
                logger.exception("Failed to create event")
                if isinstance(e, ChouseisanError):
                    raise
                raise ChouseisanError(f"イベントの作成に失敗しました: {e}") from e
            finally:
                await browser.close()

    async def get_event_info(self, event_url: str) -> Dict[str, Any]:
        """
        イベント情報（タイトル、候補日程一覧、URL）を取得します。

        Args:
            event_url (str): イベントのURL

        Returns:
            Dict[str, Any]: イベント情報を含む辞書
                - title: イベントタイトル
                - dates: 候補日程のリスト
                - url: イベントURL

        Raises:
            ChouseisanError: イベント情報の取得に失敗した場合
        """
        if not event_url or not event_url.startswith("http"):
            raise ChouseisanError(f"無効なURLフォーマットです: {event_url}")

        logger.info(f"Fetching event info: {event_url}")
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page()
                page.set_default_timeout(self.timeout)
                await page.goto(event_url, wait_until="domcontentloaded")
                
                # タイトル取得
                title = ""
                if await page.locator('h1').count() > 0:
                    title = (await page.locator('h1').inner_text()).strip()
                elif await page.locator('.event-name').count() > 0:
                    title = (await page.locator('.event-name').inner_text()).strip()
                
                # 日程リスト取得
                dates: List[str] = []
                nittei_locator = page.locator('#nittei tr td:first-child')
                nittei_count = await nittei_locator.count()
                
                if nittei_count > 0:
                    for i in range(nittei_count):
                        td_text = (await nittei_locator.nth(i).inner_text()).strip()
                        if td_text and td_text != "日程":
                            dates.append(td_text)

                if not dates:
                    # フォールバックセレクタ
                    th_locator = page.locator('#attendance-table th.valign-middle')
                    th_count = await th_locator.count()
                    if th_count > 2:
                        for i in range(2, th_count):
                            text = (await th_locator.nth(i).inner_text()).strip()
                            if text:
                                dates.append(text)
                
                logger.info(f"Retrieved event '{title}' with {len(dates)} candidate dates.")
                return {
                    "title": title,
                    "dates": dates,
                    "url": event_url
                }
            except Exception as e:
                logger.exception(f"Failed to fetch event info for {event_url}")
                if isinstance(e, ChouseisanError):
                    raise
                raise ChouseisanError(f"イベント情報の取得に失敗しました: {e}") from e
            finally:
                await browser.close()

    async def add_response(
        self,
        event_url: str,
        name: str,
        comment: str = "",
        availability: Optional[Union[List[Any], str]] = None
    ) -> bool:
        """
        イベントに出欠回答を追加・更新します。

        Args:
            event_url (str): イベントのURL
            name (str): 回答者の名前
            comment (str, optional): コメント（ひとこと）
            availability (Optional[Union[List[Any], str]], optional):
                各日程の出欠回答。
                リスト ([2, 1, 0] や ["○", "△", "×"]), または JSON文字列/カンマ区切り文字列

        Returns:
            bool: 登録に成功した場合は True

        Raises:
            ChouseisanError: 出欠登録に失敗した場合
        """
        if not event_url or not event_url.startswith("http"):
            raise ChouseisanError(f"無効なURLフォーマットです: {event_url}")
        if not name or not name.strip():
            raise ChouseisanError("回答者名は必須です。")

        avail_list = parse_availability_list(availability)
        logger.info(f"Adding response for '{name}' to {event_url} (availability: {avail_list})")

        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            try:
                page = await browser.new_page()
                page.set_default_timeout(self.timeout)
                await page.goto(event_url, wait_until="domcontentloaded")
                
                # "出欠を入力する" ボタンをクリック
                add_btn = page.locator('#add_btn, button:has-text("出欠を入力する")').first
                if await add_btn.count() > 0:
                    await add_btn.click()
                else:
                    raise ScrapingError("出欠入力ボタンが見つかりませんでした。")
                
                # フォーム待機
                await page.wait_for_selector('input[name="name"]', timeout=self.timeout)
                
                # 名前およびコメント入力
                await page.fill('input[name="name"]', name)
                
                if await page.locator('input[name="hitokoto"]').count() > 0:
                    await page.fill('input[name="hitokoto"]', comment)

                # 出欠の入力 (2: ○, 1: △, 0: ×)
                # ボタンクラス対応: 2 -> .oax-0, 1 -> .oax-1, 0 -> .oax-2
                button_class_map = {2: "oax-0", 1: "oax-1", 0: "oax-2"}
                
                for i, status in enumerate(avail_list):
                    field_name = f"kouho{i+1}"
                    if await page.locator(f'input[name="{field_name}"]').count() > 0:
                        btn_class = button_class_map.get(status, "oax-2")
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
                if await save_btn.count() > 0:
                    await save_btn.click()
                else:
                    raise ScrapingError("保存ボタンが見つかりませんでした。")
                
                await page.wait_for_load_state("domcontentloaded")
                logger.info(f"Successfully registered availability for '{name}'")
                return True
            except Exception as e:
                logger.exception("Failed to add response")
                if isinstance(e, ChouseisanError):
                    raise
                raise ChouseisanError(f"出欠の登録に失敗しました: {e}") from e
            finally:
                await browser.close()
