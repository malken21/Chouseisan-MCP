# Chouseisan MCP

調整さん のイベント作成 管理を行う MCP サーバーです。

## 機能

- イベントの新規作成: タイトル、メモ、候補日程を指定してイベントを作成します。
- イベント情報の取得: 指定されたURLからイベントタイトルと候補日程を取得します。
- 出欠回答の登録: 指定されたURLのイベントに出欠（○、△、×）を登録します。

## インストール

```bash
pip install .
```

## 使い方

Claude Desktop などの MCP クライアントの設定に以下を追加してください：

```json
{
  "mcpServers": {
    "chouseisan": {
      "command": "python",
      "args": ["[リポジトリのパス]/mcp_server.py"]
    }
  }
}
```
