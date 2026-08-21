# Chouseisan MCP

調整さん のイベント作成 管理をする MCP サーバー

## 機能

- イベントの新規作成: タイトル、メモ、候補日程を指定してイベントを作成
- イベント情報の取得: 指定されたURLからイベントタイトル、候補日程・集計、および各回答者の出欠情報（○、△、×）やコメントを取得
- 出欠回答の登録: 指定されたURLのイベントに出欠（○、△、×）を登録
- 柔軟な通信方式: 標準入出力 (stdio) に加え、Streamable HTTP (MCP) 経由での通信にも対応
- MCP プロトコルバージョン: `2024-11-05` 〜 `2026-07-28`（最新）まで対応 (公式 Python SDK `mcp` v2 系に準拠)
- ポータブルな設定: ポート番号や通信モードを引数、本サーバー専用の環境変数、または `.env` ファイルで自由に設定可能

## インストール

```bash
uv sync
uv run playwright install chromium
```

## 使い方

Claude Desktop などの MCP クライアントの設定に以下を追加してください。

`[リポジトリのパス]` は実際のリポジトリの絶対パスに置き換えてください。

```json
{
  "mcpServers": {
    "chouseisan": {
      "command": "uv",
      "args": [
        "--directory",
        "[リポジトリのパス]",
        "run",
        "python",
        "src/main.py"
      ]
    }
  }
}
```

### Streamable HTTP (MCP) モードでの利用

本サーバーは **Streamable HTTP (MCP)** 通信 (`/mcp` エンドポイント) をサポートしています。

```bash
uv run python src/main.py --transport http --port 8000
```

MCP クライアント（Claude Code / Claude Desktop 等）の設定例:

```json
{
  "mcpServers": {
    "chouseisan": {
      "type": "http",
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

### 設定項目 (環境変数 / .env)

以下の環境変数を設定または `.env` ファイルに記述することで、動作をカスタマイズできます。

- `MCP_TRANSPORT` / `TRANSPORT`: 通信モード (`stdio`, `http`, または `mcp`)。デフォルトは `stdio`
- `PORT`: 待機ポート番号 (HTTP モード時)。デフォルトは `8000`
- `HOST`: バインドIPアドレス (HTTP モード時)。デフォルトは `0.0.0.0`
- `HEADLESS`: ヘッドレスブラウザ動作 (`true` / `false`)。デフォルトは `true`
- `LOG_LEVEL`: ログレベル (`DEBUG`, `INFO`, `WARN`, `ERROR`)。デフォルトは `INFO`
- `MCP_DISABLE_DNS_REBINDING_PROTECTION`: DNS Rebinding Protection を無効化 (`1` で無効化)。コンテナ環境等、Host ヘッダーが `127.0.0.1`/`localhost` 以外になる構成で利用する場合に設定してください。デフォルトは無効化しない
