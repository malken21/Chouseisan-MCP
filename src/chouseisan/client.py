
from playwright.async_api import async_playwright
import logging
from typing import List, Dict, Any, Optional

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

class ChouseisanClient:
    """調整さん (chouseisan.com) を操作するためのクライアントクラス"""
    BASE_URL = "https://chouseisan.com"

    def __init__(self):
        pass

    async def create_event(self, title: str, memo: str = "", dates: str = "") -> str:
        """
        新しいイベントを作成します。

        Args:
            title (str): イベントのタイトル
            memo (str, optional): イベントのメモ（説明文）. Defaults to "".
            dates (str, optional): 候補日程（改行区切り）. Defaults to "".

        Returns:
            str: 作成されたイベントのURL

        Raises:
            ChouseisanError: イベント作成に失敗した場合
        """
        logger.info(f"Creating event: {title}")
        logger.debug("Entering create_event")
        async with async_playwright() as p:
            logger.debug("Launched playwright")
            browser = await p.chromium.launch(headless=True)
            logger.debug("Launched browser")
            page = await browser.new_page()
            try:
                await page.goto(self.BASE_URL)
                logger.debug("Navigated to base url")
                
                await page.fill('input[name="name"]', title)
                await page.fill('textarea[name="comment"]', memo)
                await page.fill('textarea[name="kouho"]', dates)
                logger.debug("Filled form")
                
                # イベント作成ボタンをクリック
                # 複数のセレクタ候補からボタンを探す
                btn = (await page.locator('#createBtn, #create_event_submit_btn, button:has-text("出欠表をつくる")').all())[0]
                if await btn.count() > 0 or True: # .all() は要素のリストを返すが、ロジック上の分岐として残す
                    btn_locator = page.locator('#createBtn, #create_event_submit_btn, button:has-text("出欠表をつくる")').first
                    if await btn_locator.count() > 0:
                        btn_text = await btn_locator.inner_text()
                        logger.debug(f"Clicking button: {btn_text}")
                        await btn_locator.click()
                    else:
                        raise ChouseisanError("Submit button not found")
                
                logger.debug("Clicked submit")
                
                # 作成完了後のURL入力を待機
                try:
                    logger.debug("Waiting for url input")
                    await page.wait_for_selector('input.new-event-url-input', timeout=10000)
                    url = await page.input_value('input.new-event-url-input')
                    logger.debug(f"Found url {url}")
                except Exception as e:
                    logger.debug(f"Wait failed {e}, trying fallback")
                    # 直接リダイレクトされた場合のフォールバック
                    if "s?h=" in page.url:
                         url = page.url
                    else:
                         # URLの変化を待機
                         await page.wait_for_url("**/s?h=*", timeout=5000)
                         url = page.url

                logger.info(f"Event created successfully: {url}")
                return url
            except Exception as e:
                logger.exception("Error creating event")
                raise ChouseisanError(f"Error creating event: {e}")
            finally:
                logger.debug("Closing browser")
                await browser.close()


    async def get_event_info(self, event_url: str) -> Dict[str, Any]:
        """
        イベント情報を取得します。

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
        logger.info(f"Fetching event info from: {event_url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(event_url)
                
                # タイトル取得
                logger.debug("Getting title")
                title = await page.locator('h1').inner_text()
                logger.debug(f"Title: {title}")
                
                # 日程取得
                dates = []
                
                logger.debug("Getting dates locator")
                # #nittei テーブルの最初のセル（日程列）を取得
                nittei_locator = page.locator('#nittei tr td:first-child')
                nittei_count = await nittei_locator.count()
                logger.debug(f"Nittei count: {nittei_count}")
                
                if nittei_count > 0:
                    for i in range(nittei_count):
                        td = nittei_locator.nth(i)
                        text = await td.inner_text()
                        if text.strip() == "日程": # ヘッダー行をスキップ
                            continue
                        dates.append(text)
                
                # 日程が見つからない場合、古いセレクタ（出欠表のヘッダー）を試行
                if not dates:
                    th_locator = page.locator('#attendance-table th.valign-middle')
                    th_count = await th_locator.count()
                    if th_count > 2:
                        for i in range(2, th_count):
                             th = th_locator.nth(i)
                             dates.append(await th.inner_text())
                
                logger.info(f"Found {len(dates)} dates")
                return {
                    "title": title,
                    "dates": dates,
                    "url": event_url
                }
            except Exception as e:
                logger.exception("Error getting event info")
                raise ChouseisanError(f"Error getting event info: {e}")
            finally:
                await browser.close()

    async def add_response(self, event_url: str, name: str, comment: str = "", availability: Optional[List[int]] = None) -> bool:
        """
        イベントに出欠回答を追加します。

        Args:
            event_url (str): イベントのURL
            name (str): 回答者の名前
            comment (str, optional): コメント. Defaults to "".
            availability (Optional[List[int]], optional): 各日程に対する回答のリスト (2: ○, 1: △, 0: ×). Defaults to None.

        Returns:
            bool: 登録に成功した場合は True

        Raises:
            ChouseisanError: 出欠登録に失敗した場合
        """
        if availability is None:
            availability = []
            
        logger.info(f"Adding response for {name} to: {event_url}")
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(event_url)
                
                # "出欠を入力する" ボタンをクリック
                await page.click('#add_btn')
                
                # フォームが表示されるのを待機
                await page.wait_for_selector('input[name="name"]', timeout=5000)
                
                # 名前を入力
                await page.fill('input[name="name"]', name)
                
                # コメント (hitokoto) を入力
                if await page.locator('input[name="hitokoto"]').count() > 0:
                    await page.fill('input[name="hitokoto"]', comment)
                else:
                    logger.warning("Comment field 'hitokoto' not found, skipping.")
                
                # 出欠を入力 (2: ○, 1: △, 0: ×)
                # ボタンクラス: .oax-0 (O), .oax-1 (Tri), .oax-2 (X)
                button_class_map = {2: "oax-0", 1: "oax-1", 0: "oax-2"}
                
                for i, status in enumerate(availability):
                    field_name = f"kouho{i+1}"
                    # check if hidden input exists
                    if await page.locator(f'input[name="{field_name}"]').count() > 0:
                        button_class = button_class_map.get(status, "oax-2") # 未知の値は×とする
                        
                        # 隠しフィールドに対応するボタンをクリック
                        await page.evaluate(f'''() => {{
                            const hiddenInput = document.querySelector('input[name="{field_name}"]');
                            if (hiddenInput) {{
                                const parent = hiddenInput.parentElement;
                                const button = parent.querySelector('.{button_class}');
                                if (button) {{
                                    button.click();
                                }}
                            }}
                        }}''')
                        # クリック処理のために少し待機
                        await page.wait_for_timeout(100)
                    else:
                        logger.warning(f"Availability field {field_name} not found.")

                # 保存ボタンをクリック
                await page.click('#memUpdBtn')
                
                # 完了を待機
                await page.wait_for_load_state("domcontentloaded")
                
                return True
            except Exception as e:
                logger.exception("Error adding response")
                raise ChouseisanError(f"Error adding response: {e}")
            finally:
                await browser.close()
