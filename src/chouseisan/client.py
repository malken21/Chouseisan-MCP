import requests
from bs4 import BeautifulSoup
import re
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import unquote

# ロギングの設定
logger = logging.getLogger(__name__)

class ChouseisanError(Exception):
    """調整さんクライアントの基底例外"""
    pass

class NetworkError(ChouseisanError):
    """ネットワーク関連の例外"""
    pass

class ScrapingError(ChouseisanError):
    """スクレイピング関連の例外"""
    pass

class ChouseisanClient:
    BASE_URL = "https://chouseisan.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })

    def _get_csrf_token(self, soup: BeautifulSoup) -> str:
        """HTMLからCSRFトークンを抽出する"""
        vue_tag = soup.find("create-new-event-form")
        if vue_tag and vue_tag.has_attr(":csrf"):
            return vue_tag[":csrf"].strip("'").strip('"')
        
        # フォールバック: scriptタグ内などの検索
        token_match = re.search(r'\"csrfToken\"\s*:\s*\"([^"]+)\"', str(soup))
        if token_match:
            return token_match.group(1)
        
        return ""

    def create_event(self, title: str, memo: str = "", dates: str = "") -> str:
        """
        イベントを作成し、生成されたURLを返す。
        """
        logger.info(f"Creating event: {title}")
        try:
            # CSRFトークンの取得
            res = self.session.get(self.BASE_URL)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "lxml")
            _token = self._get_csrf_token(soup)

            create_url = f"{self.BASE_URL}/schedule/newEvent/create"
            headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
                "Referer": self.BASE_URL
            }
            
            payload = {
                "_token": _token,
                "name": title,
                "comment": memo,
                "kouho": dates,
                "add_suffix": True
            }
            
            response = self.session.post(create_url, json=payload, headers=headers)
            if response.status_code != 200:
                logger.error(f"Failed to create event: {response.status_code} {response.text}")
                raise NetworkError(f"Failed to create event: {response.status_code}")

            # レスポンスHTMLからURLを抽出
            soup_res = BeautifulSoup(response.text, "lxml")
            url_input = soup_res.find("input", class_="new-event-url-input")
            if url_input:
                url = url_input["value"]
                logger.info(f"Event created successfully: {url}")
                return url
            
            # フォールバック: aタグから
            a_tag = soup_res.find("a", href=re.compile(r"/s\?h="))
            if a_tag:
                url = a_tag["href"]
                logger.info(f"Event created successfully (fallback): {url}")
                return url
                
            raise ScrapingError("Created event URL not found in response.")

        except requests.RequestException as e:
            logger.exception("Network error during event creation")
            raise NetworkError(f"Network error: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error during event creation")
            raise ChouseisanError(f"Unexpected error: {str(e)}")

    def get_event_info(self, event_url: str) -> Dict[str, Any]:
        """
        イベント情報を取得する。
        """
        logger.info(f"Fetching event info from: {event_url}")
        try:
            res = self.session.get(event_url)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "lxml")
            
            # タイトルの取得
            title_tag = soup.find("h1")
            title = title_tag.get_text(strip=True) if title_tag else "Unknown"
            
            # 候補日程の抽出
            dates = []
            table = soup.find("table", id="attendance-table")
            if table:
                header_th = table.find_all("th", class_="valign-middle")
                # 最初の2つは「名前」「コメント」なのでそれ以降
                for th in header_th[2:]:
                    dates.append(th.get_text(strip=True))

            # テーブルがない場合、window.Chouseisan オブジェクトから抽出を試みる
            if not dates:
                logger.debug("Attendance table not found, attempting fallback from JS.")
                m = re.search(r'window\.Chouseisan\s*=\s*(\{.*?\});', res.text, re.S)
                if m:
                    try:
                        # JSONとしてパースを試みる（不完全な場合が多いので正規表現も併用）
                        js_content = m.group(1)
                        kouho_match = re.search(r'\"kouho\"\s*:\s*\"(.*?)\"', js_content)
                        if kouho_match:
                            kouho_str = kouho_match.group(1).replace("\\n", "\n").replace("\\r", "").replace('\\/', '/')
                            dates = [d.strip() for d in kouho_str.split("\n") if d.strip()]
                    except Exception as e:
                        logger.warning(f"Fallback JS parse failed: {e}")

            return {
                "title": title,
                "dates": dates,
                "url": event_url
            }

        except requests.RequestException as e:
            logger.exception("Network error during fetching event info")
            raise NetworkError(f"Network error: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error during fetching event info")
            raise ChouseisanError(f"Unexpected error: {str(e)}")

    def add_response(self, event_url: str, name: str, comment: str = "", availability: Optional[List[int]] = None) -> bool:
        """
        出欠を登録する。
        availability はリストで各日程に対する 2 (○), 1 (△), 0 (×) を指定。
        """
        if availability is None:
            availability = []

        logger.info(f"Adding response for {name} to: {event_url}")
        try:
            match = re.search(r"h=([a-z0-9]+)", event_url)
            if not match:
                raise ChouseisanError("Invalid event URL: hash not found")
            event_hash = match.group(1)

            res = self.session.get(event_url)
            res.raise_for_status()
            soup = BeautifulSoup(res.text, "lxml")
            
            store_url = f"{self.BASE_URL}/schedule/List/addRes"
            
            xsrf_token = self.session.cookies.get("XSRF-TOKEN")
            if xsrf_token:
                xsrf_token = unquote(xsrf_token)

            _token = self._get_csrf_token(soup)

            payload = {
                "_token": _token,
                "event_id": event_hash,
                "name": name,
                "comment": comment,
            }
            for i, val in enumerate(availability):
                payload[f"q[{i}]"] = val

            headers = {
                "X-Requested-With": "XMLHttpRequest",
                "Accept": "application/json",
                "Referer": event_url,
                "X-CSRF-TOKEN": _token,
                "X-XSRF-TOKEN": xsrf_token if xsrf_token else ""
            }
            
            response = self.session.post(store_url, data=payload, headers=headers)
            if response.status_code == 200:
                logger.info(f"Response added successfully for {name}")
                return True
            else:
                logger.error(f"Failed to add response: {response.status_code} {response.text}")
                raise NetworkError(f"Failed to add response: {response.status_code}")

        except requests.RequestException as e:
            logger.exception("Network error during adding response")
            raise NetworkError(f"Network error: {str(e)}")
        except Exception as e:
            logger.exception("Unexpected error during adding response")
            raise ChouseisanError(f"Unexpected error: {str(e)}")

if __name__ == "__main__":
    # 基本的なロギング設定（単体実行用）
    logging.basicConfig(level=logging.INFO)
    pass
