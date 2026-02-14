# Chouseisan MCP

調整さん のイベント作成 管理を行う MCP サーバーです

## 機能

- イベントの新規作成: タイトル、メモ、候補日程を指定してイベントを作成
- イベント情報の取得: 指定されたURLからイベントタイトルと候補日程を取得
- 出欠回答の登録: 指定されたURLのイベントに出欠（○、△、×）を登録

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
