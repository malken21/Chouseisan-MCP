from __future__ import annotations

import logging
import json
import argparse
import os
from typing import List, Union, Any, Optional
import uvicorn
from dotenv import load_dotenv

from chouseisan.client import ChouseisanClient, ChouseisanError, parse_availability_list

# 環境変数・ロギングの初期設定
load_dotenv()

log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger("chouseisan-mcp")

from mcp.server.fastmcp import FastMCP

# FastMCP インスタンスの作成
mcp = FastMCP("Chouseisan", description="調整さん (chouseisan.com) のイベント作成・管理・出欠登録を行う MCP サーバー")
client = ChouseisanClient()

@mcp.tool()
async def create_event(title: str, memo: str = "", dates: str = "") -> str:
    """
    調整さんの日程調整イベントを新規作成します。

    Args:
        title: イベント名・タイトル (例: "プロジェクト打ち合わせ")
        memo: イベントの補足説明・メモ (例: "オンライン開催。アジェンダは後日連絡")
        dates: 候補日程 (改行区切りで指定。例: "3/1(土) 19:00-\n3/2(日) 15:00-\n3/3(月) 20:00-")

    Returns:
        作成された調整さんイベントのURLおよび完了メッセージ
    """
    logger.info(f"Tool create_event invoked for title='{title}'")
    try:
        url = await client.create_event(title=title, memo=memo, dates=dates)
        return f"イベントを作成しました。\nURL: {url}"
    except ChouseisanError as e:
        logger.error(f"Chouseisan client error in create_event: {e}")
        return f"エラー: イベントの作成に失敗しました。詳細: {str(e)}"
    except Exception as e:
        logger.exception("Unexpected error in create_event")
        return f"エラー: 予期せぬエラーが発生しました。詳細: {str(e)}"

@mcp.tool()
async def get_event_info(url: str) -> str:
    """
    調整さんイベントの登録情報（イベント名、候補日程一覧）を取得します。

    Args:
        url: 取得対象の調整さんイベントURL (例: "https://chouseisan.com/s?h=...")

    Returns:
        イベント名、URL、および候補日程一覧のフォーマットテキスト
    """
    logger.info(f"Tool get_event_info invoked for url='{url}'")
    try:
        info = await client.get_event_info(url=url)
        dates_list = info.get("dates", [])
        if dates_list:
            dates_str = "\n".join(f"  - {d}" for d in dates_list)
        else:
            dates_str = "  (候補日程が見つかりませんでした)"

        return f"■ イベント名: {info['title']}\n■ URL: {info['url']}\n■ 候補日程:\n{dates_str}"
    except ChouseisanError as e:
        logger.error(f"Chouseisan client error in get_event_info: {e}")
        return f"エラー: 情報の取得に失敗しました。詳細: {str(e)}"
    except Exception as e:
        logger.exception("Unexpected error in get_event_info")
        return f"エラー: 予期せぬエラーが発生しました。詳細: {str(e)}"

@mcp.tool()
async def add_response(
    url: str,
    name: str,
    comment: str = "",
    availability: Union[List[Union[int, str]], str] = []
) -> str:
    """
    調整さんイベントに出欠回答を登録・更新します。

    Args:
        url: 回答対象の調整さんイベントURL (例: "https://chouseisan.com/s?h=...")
        name: 回答者の名前 (例: "山田太郎")
        comment: コメント・ひとことメッセージ (例: "遅れる可能性があります")
        availability: 各日程に対する出欠回答リスト。
                      数値 (2: ○, 1: △, 0: ×) や 記号 ("○", "△", "×"),
                      または JSON 文字列 '[2, 1, 0]' や カンマ区切り '○, △, ×' の形式で指定可能。
                      例: ["○", "△", "×"] または [2, 1, 0]

    Returns:
        出欠登録の結果メッセージ
    """
    logger.info(f"Tool add_response invoked for name='{name}', url='{url}'")
    try:
        parsed_avail = parse_availability_list(availability)
        success = await client.add_response(
            event_url=url,
            name=name,
            comment=comment,
            availability=parsed_avail
        )
        if success:
            return f"'{name}' さんの出欠回答を正常に登録しました。"
        else:
            return "エラー: 出欠の登録に失敗しました。"
    except ChouseisanError as e:
        logger.error(f"Chouseisan client error in add_response: {e}")
        return f"エラー: 出欠の登録に失敗しました。詳細: {str(e)}"
    except Exception as e:
        logger.exception("Unexpected error in add_response")
        return f"エラー: 予期せぬ例外が発生しました。詳細: {str(e)}"

if __name__ == "__main__":
    default_host = os.environ.get("HOST", "0.0.0.0")
    default_port = int(os.environ.get("PORT", "8000"))
    default_transport = os.environ.get("TRANSPORT", "stdio").lower()

    parser = argparse.ArgumentParser(description="調整さん MCP サーバー")
    parser.add_argument("--host", type=str, default=default_host, help="バインドIPアドレス (SSE 転送モード時)")
    parser.add_argument("--port", type=int, default=default_port, help="待機ポート番号 (SSE 転送モード時)")
    parser.add_argument("--transport", type=str, default=default_transport, choices=["stdio", "sse"], help="通信モード (stdio または sse)")
    args = parser.parse_args()

    if args.transport == "sse":
        logger.info(f"Starting Chouseisan MCP SSE Server on {args.host}:{args.port}")
        uvicorn.run(mcp.sse_app, host=args.host, port=args.port)
    else:
        logger.info("Starting Chouseisan MCP Server in STDIO mode")
        mcp.run(transport="stdio")
