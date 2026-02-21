# boj-mcp — 日銀 時系列統計データ API の MCP サーバー

Claude Desktop から日本銀行の時系列統計データ API に直接アクセスできるようにする MCP サーバー。

---

## 提供ツール

| ツール名 | 説明 |
|---------|------|
| `boj_get_metadata` | DB内の系列一覧・メタ情報を取得（系列コード調査に使う） |
| `boj_get_data_code` | 系列コード指定でデータを取得 |
| `boj_get_data_layer` | 階層（カテゴリ）指定でデータをまとめて取得 |

---

## セットアップ

### 1. 依存パッケージをインストール

```bash
pip install mcp httpx
```

### 2. Claude Desktop の設定ファイルを編集

設定ファイルの場所:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

以下を追記（パスは実際の場所に変更）:

```json
{
  "mcpServers": {
    "boj-api": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/boj-mcp/server.py"]
    }
  }
}
```

### 3. Claude Desktop を再起動

再起動後、チャット画面の🔧アイコンに `boj-api` が表示されれば完了。

---

## 使い方の例（Claude へのプロンプト）

```
FM08（外国為替）のメタ情報を取得して、ドル円の月次データを2024年1月から12月まで見せて。
```

```
短観（CO）の直近3期分の業況判断DIを取得して。
```

---

## テスト

```bash
pip install pytest pytest-asyncio
pytest test_server.py -v
```

---

## 注意事項

- 短時間に大量リクエストすると接続遮断される（日銀ポリシー）。連続取得時は間隔を空けること。
- 系列コードは `boj_get_metadata` で確認してから `boj_get_data_code` を使うのが確実。
- コードAPI（`boj_get_data_code`）は同一リクエスト内の系列を全て同じ期種にすること。
