from __future__ import annotations

import argparse
import functools
import logging
import os
from typing import Any, Callable, Coroutine

import uvicorn
from dotenv import load_dotenv

from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from chouseisan.client import (
    ChouseisanClient,
    ChouseisanError,
    parse_availability_list,
)

# 環境変数の読み込みおよびロガー初期化
load_dotenv()

log_level_str = os.environ.get("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    level=log_level,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger("chouseisan-mcp")

# DNS Rebinding Protection 設定
_disable_dns_rebinding_protection = os.environ.get("MCP_DISABLE_DNS_REBINDING_PROTECTION") == "1"
_transport_security = (
    TransportSecuritySettings(enable_dns_rebinding_protection=False)
    if _disable_dns_rebinding_protection
    else None
)

mcp = MCPServer(
    "Chouseisan",
    instructions="調整さん (chouseisan.com) のイベント作成・管理・出欠登録を行う MCP サーバー",
)
client = ChouseisanClient()


def handle_tool_errors(
    error_prefix: str,
) -> Callable[..., Callable[..., Coroutine[Any, Any, dict[str, Any]]]]:
    """MCPツールの例外ハンドリングおよびレスポンス生成を一元化するデコレータ"""
    def decorator(
        func: Callable[..., Coroutine[Any, Any, dict[str, Any]]]
    ) -> Callable[..., Coroutine[Any, Any, dict[str, Any]]]:
        @functools.wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> dict[str, Any]:
            try:
                return await func(*args, **kwargs)
            except ChouseisanError as e:
                logger.error(f"Chouseisan client error in {func.__name__}: {e}")
                return {
                    "success": False,
                    "error": f"{error_prefix}: {str(e)}",
                }
            except Exception as e:
                logger.exception(f"Unexpected error in {func.__name__}")
                return {
                    "success": False,
                    "error": f"予期せぬエラーが発生しました: {str(e)}",
                }
        return wrapper
    return decorator


@mcp.tool()
@handle_tool_errors("イベントの作成に失敗しました")
async def create_event(title: str, memo: str = "", dates: str = "") -> dict[str, Any]:
    """
    調整さんの日程調整イベントを新規作成します。

    Args:
        title: イベント名・タイトル (例: "プロジェクト打ち合わせ")
        memo: イベントの補足説明・メモ (例: "オンライン開催。アジェンダは後日連絡")
        dates: 候補日程 (改行区切りで指定。例: "3/1(土) 19:00-\n3/2(日) 15:00-\n3/3(月) 20:00-")

    Returns:
        dict[str, Any]: 作成結果 (success: bool, url: str, message: str)
    """
    logger.info(f"Tool create_event invoked for title='{title}'")
    url = await client.create_event(title=title, memo=memo, dates=dates)
    return {
        "success": True,
        "url": url,
        "message": "イベントを作成しました。",
    }


@mcp.tool()
@handle_tool_errors("情報の取得に失敗しました")
async def get_event_info(url: str) -> dict[str, Any]:
    """
    調整さんイベントの登録情報（イベント名、候補日程・集計、各回答者の出欠情報○△×・コメント）を取得します。

    Args:
        url: 取得対象の調整さんイベントURL (例: "https://chouseisan.com/s?h=...")

    Returns:
        dict[str, Any]: イベント情報
            - success (bool): 取得成功フラグ
            - title (str): イベントタイトル
            - url (str): イベントURL
            - dates (list[str]): 候補日程一覧
            - summary (dict[str, dict[str, int]]): 日程別集計人数 {"日程": {"ok": 0, "tri": 0, "ng": 0}}
            - participants (list[dict[str, Any]]): 各回答者の情報 [{"name": str, "comment": str, "availability": {"日程": "○"}}]
    """
    logger.info(f"Tool get_event_info invoked for url='{url}'")
    info = await client.fetch_event_info(event_url=url)
    result = info.to_dict()
    result["success"] = True
    return result


@mcp.tool()
@handle_tool_errors("出欠の登録に失敗しました")
async def add_response(
    url: str,
    name: str,
    comment: str = "",
    availability: list[int | str] | str = "",
) -> dict[str, Any]:
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
        dict[str, Any]: 出欠登録結果 (success: bool, message: str)
    """
    logger.info(f"Tool add_response invoked for name='{name}', url='{url}'")
    parsed_avail = parse_availability_list(availability)
    success = await client.add_response(
        event_url=url,
        name=name,
        comment=comment,
        availability=parsed_avail,
    )
    if success:
        return {
            "success": True,
            "message": f"'{name}' さんの出欠回答を正常に登録しました。",
        }
    return {
        "success": False,
        "error": "出欠の登録に失敗しました。",
    }


def main() -> None:
    """CLI引数の解析およびMCPサーバー起動"""
    default_host = os.environ.get("HOST", "0.0.0.0")
    default_port = int(os.environ.get("PORT", "8000"))
    default_transport = (
        os.environ.get("MCP_TRANSPORT") or os.environ.get("TRANSPORT") or "stdio"
    ).lower()

    parser = argparse.ArgumentParser(description="調整さん MCP サーバー")
    parser.add_argument("--host", type=str, default=default_host, help="バインドIPアドレス (HTTP 転送モード時)")
    parser.add_argument("--port", type=int, default=default_port, help="待機ポート番号 (HTTP 転送モード時)")
    parser.add_argument(
        "--transport",
        type=str,
        default=default_transport,
        choices=["stdio", "http", "mcp"],
        help="通信モード (stdio, http, または mcp)",
    )
    args = parser.parse_args()

    if args.transport in ["http", "mcp"]:
        logger.info(f"Starting Chouseisan MCP Streamable HTTP Server on {args.host}:{args.port}")
        app = mcp.streamable_http_app(transport_security=_transport_security, host=args.host)
        uvicorn.run(app, host=args.host, port=args.port)
    else:
        logger.info("Starting Chouseisan MCP Server in STDIO mode")
        mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
