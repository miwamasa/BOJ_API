# boj-client

日本銀行（日銀）[時系列統計データ検索サイト](https://www.stat-search.boj.or.jp) API の Python クライアントライブラリです。

為替レート・金利・マネーストック・短観など、日銀が公開する幅広い金融統計データをシンプルなAPIで取得できます。

---

## 特徴

- **3種類のAPIに対応** — コードAPI・階層API・メタデータAPI
- **ページネーション自動処理** — 250件超のデータも自動で分割取得
- **リトライ機能** — 一時的なサーバーエラー（500/503）を自動リトライ
- **型安全なデータモデル** — `Series`, `SeriesValue`, `SeriesMeta` の dataclass
- **pandas 連携** — `series.to_records()` で DataFrame 変換が簡単
- **テスト容易性** — `session` 引数でHTTPモックを差し込み可能

---

## インストール

### 方法1: editable mode でインストール（推奨）

プロジェクトを開発モードでインストールすると、PYTHONPATH を気にせず使えます：

```bash
# プロジェクトルートで実行
pip install -e .

# 開発用パッケージも一緒にインストールする場合
pip install -e ".[dev]"

# pandas との連携も使う場合
pip install pandas
```

### 方法2: パッケージのインストールなしで使用

examples/basic_usage.py には自動的にパスを追加するコードが含まれているため、
インストールなしでも直接実行できます：

```bash
# 必要なパッケージのみインストール
pip install requests

# サンプルスクリプトを直接実行
python3 examples/basic_usage.py
```

---

## クイックスタート

### サンプルコードの実行

```bash
# インストール後（方法1）
python3 examples/basic_usage.py

# インストールなし（方法2）でも同じく実行可能
python3 examples/basic_usage.py
```

### Python コードでの使用

```python
# pip install -e . でインストール済みの場合
from boj_client import BOJClient

client = BOJClient()

# 1. 系列コードを知っている場合 → コードAPI
series = client.get_by_code(
    db="FM08",            # 外国為替市況DB
    codes=["FXUSDM"],     # 米ドル（月中平均）
    start_date="202401",  # 開始期: 2024年1月
    end_date="202412",    # 終了期: 2024年12月
)

for sv in series[0].values:
    print(f"{sv.observation_date}  {sv.value} 円/ドル")

# 最新値だけ取得
latest = series[0].latest_value()
print(f"最新: {latest.value} 円/ドル ({latest.observation_date})")
```

---

## 系列コードの調べ方

系列コードが不明な場合は、**メタデータ検索**を使います。

```python
# キーワードで検索
metas = client.search_metadata(db="FM08", keyword="米ドル")
for m in metas:
    print(f"[{m.code}] {m.name_ja}  収録: {m.start_date} 〜 {m.end_date}")
```

---

## pandas への変換

```python
import pandas as pd

records = []
for s in series:
    records.extend(s.to_records())

df = pd.DataFrame(records)
df["date"] = pd.to_datetime(df["date"])
df = df.dropna(subset=["value"]).sort_values("date")
print(df.describe())
```

---

## APIの種類と使い分け

| メソッド | 対応API | 使いどころ |
|---------|---------|-----------|
| `get_by_code()` | コードAPI | 系列コードがわかっている場合 |
| `get_by_layer()` | 階層API | カテゴリ単位でまとめて取得したい場合 |
| `get_metadata()` | メタデータAPI | 系列コードを調べたい場合 |
| `search_metadata()` | メタデータAPI | キーワードで系列を検索したい場合 |

---

## 主要DBリファレンス

| DB名 | 内容 |
|------|------|
| `FM08` | 外国為替市況（USD/JPY など） |
| `FM09` | 実効為替レート |
| `FM01` | 無担保コールO/N物レート |
| `IR01` | 基準割引率・基準貸付利率 |
| `IR04` | 貸出約定平均金利 |
| `MD01` | マネタリーベース |
| `MD02` | マネーストック |
| `PR01` | 企業物価指数（CGPI） |
| `CO` | 短観 |

---

## エラーハンドリング

```python
from boj_client.exceptions import BOJClientError, BOJNoDataError, BOJAPIError

try:
    series = client.get_by_code(db="FM08", codes=["FXUSDM"])
except BOJNoDataError:
    print("該当データなし")
except BOJAPIError as e:
    print(f"APIエラー {e.status}: {e.message}")
except BOJClientError as e:
    print(f"その他エラー: {e}")
```

### 例外クラス一覧

| 例外 | 発生条件 |
|------|---------|
| `BOJClientError` | 全例外の基底クラス |
| `BOJAPIError` | APIが400/500/503を返した場合 |
| `BOJParameterError` | 引数バリデーション失敗（クライアント側） |
| `BOJNoDataError` | 正常終了だが該当データなし |
| `BOJNetworkError` | タイムアウト・接続失敗・JSONパース失敗 |

---

## テスト実行

```bash
# 開発用パッケージをインストール（初回のみ）
pip install -e ".[dev]"

# テスト実行（プロジェクトルートから）
pytest tests/ --cov=boj_client -v

# カバレッジ詳細レポート付き
pytest tests/ --cov=boj_client --cov-report=term-missing -v
```

**Note:** `pip install -e .` でインストール済みの場合、`PYTHONPATH=.` は不要です。

### 現在のテスト結果

- **56個のテスト全てPASS** ✅
- **コードカバレッジ: 97%** ✅

---

## プロジェクト構造

```
boj/                         ← プロジェクトルート
│
├── boj_client/              ← ライブラリ本体
│   ├── __init__.py          ← パッケージ初期化
│   ├── client.py            ← BOJClient クラス
│   ├── models.py            ← データモデル（Series, SeriesValue, SeriesMeta）
│   └── exceptions.py        ← 例外クラス
│
├── tests/                   ← テスト群
│   ├── conftest.py          ← pytest設定とフィクスチャ
│   ├── test_client.py       ← クライアントのテスト
│   ├── test_models.py       ← モデルのテスト
│   └── test_exceptions.py  ← 例外のテスト
│
├── examples/
│   └── basic_usage.py       ← 実行サンプル
│
├── pyproject.toml           ← プロジェクト設定
└── README.md                ← このファイル
```

---

## トラブルシューティング

### 400エラー: "指定した系列コードは存在しません"

**原因:** 系列コードが間違っているか、廃止された系列を指定しています。

**解決方法:**

1. **メタデータAPIで正しい系列コードを確認**
```python
client = BOJClient()
results = client.search_metadata(db="FM08", keyword="ドル")
for meta in results[:10]:
    print(f"{meta.code}: {meta.name_ja}")
```

2. **具体例: USD/JPY為替レート（月次）**
   - ❌ 間違い: `FXUSDM`, `FXUSD`（存在しない）
   - ✅ 正しい: `FXERM07`（東京市場 ドル・円 スポット 17時時点/月中平均）
   - ✅ 正しい: `FXERM06`（東京市場 ドル・円 スポット 17時時点/月末）

3. **よくある間違い**
   - 系列コードは時代とともに変更・廃止されます
   - 必ずメタデータAPIで最新の系列コードを確認してください
   - Web UIで見つけたコードが必ずしもAPIで使えるとは限りません

### エラー: `KeyError: 'date'` or `'int' object has no attribute 'strip'`

**原因:** APIレスポンス構造が想定と異なります。

**解決方法:** 本プロジェクトでは既に修正済みです。以下の点に注意：
- レスポンスは `RESULTSET` 配列（`DATA.SERIES` ではない）
- `VALUES` は入れ子構造: `VALUES.SURVEY_DATES` と `VALUES.VALUES`
- 日付は整数で返される（例: `20240104`）

---

## 注意事項

1. **高頻度アクセス禁止** — 短時間の大量リクエストで接続遮断の可能性があります。ページネーション間は自動で1秒スリープします。
2. **同一期種の制約** — コードAPIでは全系列コードが同一期種でなければなりません。
3. **系列数上限** — 階層APIは1,250件超の系列を含む条件を指定するとエラーになります。
4. **データ更新** — 原則として毎日8:50頃に更新されます。

---

## ライセンス

MIT License
