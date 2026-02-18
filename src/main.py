from mcp.server.fastmcp import FastMCP
import logging
import json
import argparse
import os
import uvicorn
from dotenv import load_dotenv
from chouseisan.client import ChouseisanClient, ChouseisanError

# ロギングの設定
# タイムスタンプ、ロガー名、ログレベル、メッセージを含むフォーマットを設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler() # 標準出力に出力
    ]
)
logger = logging.getLogger("mcp-chouseisan")

# FastMCP インスタンスの作成
mcp = FastMCP("Chouseisan")
client = ChouseisanClient()

@mcp.tool()
async def create_event(title: str, memo: str = "", dates: str = "") -> str:
    """
    調整さんのイベントを新規作成します。
    
    Args:
        title: イベント名
        memo: イベントの補足説明（メモ）
        dates: 候補日程（改行区切りで入力。例: "3/1(土)\n3/2(日)"）
    
    Returns:
        作成されたイベントのURL
    """
    logger.info(f"Tool create_event called: {title}")
    try:
        url = await client.create_event(title, memo, dates)
        return f"イベントを作成しました: {url}"
    except ChouseisanError as e:
        logger.error(f"Chouseisan error in create_event: {e}")
        return f"エラー: イベントの作成に失敗しました。詳細: {str(e)}"
    except Exception as e:
        logger.exception("Unexpected error in create_event")
        return f"エラー: 予期せぬエラーが発生しました。{str(e)}"

@mcp.tool()
async def get_event_info(url: str) -> str:
    """
    調整さんのイベント情報（タイトル、候補日程）を取得します。
    
    Args:
        url: 取得対象の調整さんベントURL
    
    Returns:
        イベント情報のサマリー
    """
    logger.info(f"Tool get_event_info called for: {url}")
    try:
        info = await client.get_event_info(url)
        dates_str = "\n".join(info.get("dates", []))
        return f"イベント名: {info['title']}\nURL: {info['url']}\n候補日程:\n{dates_str}"
    except ChouseisanError as e:
        logger.error(f"Chouseisan error in get_event_info: {e}")
        return f"エラー: 情報の取得に失敗しました。詳細: {str(e)}"
    except Exception as e:
        logger.exception("Unexpected error in get_event_info")
        return f"エラー: 予期せぬエラーが発生しました。{str(e)}"

@mcp.tool()
async def add_response(url: str, name: str, comment: str = "", availability_json: str = "[]") -> str:
    """
    調整さんのイベントに出欠回答を登録します。
    
    Args:
        url: 回答対象の調整さんイベントURL
        name: 回答者の名前
        comment: コメント
        availability_json: 各日程に対する回答のリストを JSON 文字列形式で指定。
                          (2: ○, 1: △, 0: ×)
                          例: "[2, 1, 0]" （1番目○、2番目△、3番目×）
    
    Returns:
        登録結果のメッセージ
    """
    logger.info(f"Tool add_response called for {name} on {url}")
    try:
        try:
            availability = json.loads(availability_json)
            if not isinstance(availability, list):
                return "エラー: availability_json はリスト形式である必要があります。"
        except json.JSONDecodeError:
            return "エラー: availability_json の形式が正しくありません。"

        success = await client.add_response(url, name, comment, availability)
        if success:
            return f"{name} さんの出欠を登録しました。"
        else:
            return "出欠の登録に失敗しました。"
    except ChouseisanError as e:
        logger.error(f"Chouseisan error in add_response: {e}")
        return f"エラー: 出欠の登録に失敗しました。詳細: {str(e)}"
    except Exception as e:
        logger.exception("Unexpected error in add_response")
        return f"エラー: 予期せぬ例外が発生しました。{str(e)}"

if __name__ == "__main__":
    # .envファイルの読み込み
    load_dotenv()

    parser = argparse.ArgumentParser(description="調整さん MCP サーバー")
    parser.add_argument("--port", type=int, default=int(os.environ.get("CHOUSEISAN_PORT", 8000)), help="待機ポート番号 (SSE 転送モード時のみ有効)")
    parser.add_argument("--transport", type=str, default=os.environ.get("CHOUSEISAN_TRANSPORT", "stdio"), choices=["stdio", "sse"], help="通信モード (stdio または sse)")
    args = parser.parse_args()

    if args.transport == "sse":
        # SSEの場合はuvicornを使用して起動
        logger.info(f"Starting SSE server on port {args.port}")
        uvicorn.run(mcp.sse_app, host="0.0.0.0", port=args.port)
    else:
        # デフォルトは標準入出力 (stdio)
        mcp.run(transport="stdio")
