# Chouseisan MCP

調整さん のイベント作成 管理を行う MCP サーバーです。

## 機能

- イベントの新規作成: タイトル、メモ、候補日程を指定してイベントを作成
- イベント情報の取得: 指定されたURLからイベントタイトルと候補日程を取得
- 出欠回答の登録: 指定されたURLのイベントに出欠（○、△、×）を登録
- 柔軟な通信方式: 標準入出力 (stdio) に加え、HTTP (SSE) 経由での通信にも対応
- ポータブルな設定: ポート番号や通信モードを引数、本サーバー専用の環境変数、または `.env` ファイルで自由に設定可能

## インストール

```bash
uv venv
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

### HTTP (SSE) モードでの利用

本サーバーは **HTTP (Server-Sent Events)** による通信もサポートしています。外部から HTTP 経由で MCP サーバーにアクセスしたい場合は、まずサーバーを起動します。

```bash
uv run python src/main.py --transport sse --port 8000
```

その後、MCP クライアント（Claude Desktop 等）の設定に以下を追加してください。

```json
{
  "mcpServers": {
    "chouseisan": {
      "url": "http://localhost:8000/sse"
    }
  }
}
```

### 設定項目 (環境変数 / .env)

以下の環境変数を設定または `.env` ファイルに記述することで、動作をカスタマイズできます。

- **`CHOUSEISAN_TRANSPORT`**: 通信モード (`stdio` または `sse`)。デフォルトは `stdio`。
- **`CHOUSEISAN_PORT`**: 待機ポート番号 (SSE モード時のみ有効)。デフォルトは `8000`。
