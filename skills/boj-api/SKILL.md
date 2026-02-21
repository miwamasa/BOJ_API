---
name: boj-api
description: |
  日本銀行（日銀）時系列統計データ検索サイトのAPIを活用して、
  金融統計データを取得・分析するスキル。
  コードAPI・階層API・メタデータAPIの3種類を使い分けられる。
  為替レート、金利、マネーストック、短観など幅広い統計データを取得可能。
---

# 日銀 時系列統計データ API スキル

## 概要

日本銀行の時系列統計データ検索サイト（https://www.stat-search.boj.or.jp）が提供するAPIを使って、金融統計データをプログラマブルに取得・分析するスキル。

## APIの種類と使い分け

| API | エンドポイント | 用途 |
|-----|--------------|------|
| コードAPI | `GET /api/v1/getDataCode` | 系列コードを指定してデータを取得 |
| 階層API | `GET /api/v1/getDataLayer` | 階層情報を指定してデータを取得 |
| メタデータAPI | `GET /api/v1/getMetadata` | 系列コードや系列名称などのメタ情報を取得 |

**ベースURL**: `https://www.stat-search.boj.or.jp`

---

## 1. コードAPI

系列コードが既にわかっている場合に使用。最もシンプルで高速。

### エンドポイント
```
GET https://www.stat-search.boj.or.jp/api/v1/getDataCode
```

### パラメータ

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|-----|
| `db` | ✅ | DB名 | `FM01`, `CO`, `PR01` |
| `code` | ✅ | 系列コード（カンマ区切りで複数指定可、同一期種のみ） | `STRDCLUCON,STRDCLUCONH` |
| `format` | - | 出力形式（`json` or `csv`、省略時はJSON） | `json` |
| `lang` | - | 言語（`jp` or `en`、省略時は日本語） | `jp` |
| `startDate` | - | 開始期（省略時は収録開始期） | `202401` |
| `endDate` | - | 終了期（省略時は収録終了期） | `202412` |
| `startPosition` | - | 検索開始位置（ページネーション用） | `1` |

### 日付フォーマット（期種別）

| 期種 | フォーマット | 例 |
|------|------------|-----|
| 暦年・年度 | `YYYY` | `2024` |
| 暦年半期・年度半期 | `YYYYHH`（HH=01 or 02） | `202501`（上期） |
| 四半期 | `YYYYQQ`（QQ=01〜04） | `202402`（第2四半期） |
| 月次・週次・日次 | `YYYYMM` | `202401` |

### 実装例

```python
import requests

def get_boj_data_by_code(codes: list[str], db: str, start_date: str = None, end_date: str = None, lang: str = "jp") -> dict:
    """
    コードAPIでデータを取得する。
    
    Args:
        codes: 系列コードのリスト（全て同じ期種であること）
        db: DB名（例: "FM01", "CO"）
        start_date: 開始期（例: "202401"）
        end_date: 終了期（例: "202412"）
        lang: 言語（"jp" or "en"）
    
    Returns:
        APIレスポンスのdict
    """
    base_url = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
    params = {
        "format": "json",
        "lang": lang,
        "db": db,
        "code": ",".join(codes),
    }
    if start_date:
        params["startDate"] = start_date
    if end_date:
        params["endDate"] = end_date
    
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    return response.json()


def get_boj_data_paginated(codes: list[str], db: str, **kwargs) -> list[dict]:
    """
    ページネーションを考慮してコードAPIで全データを取得する。
    
    1リクエストあたりの上限:
    - 系列数: 250件
    - データ数（系列数×期数）: 60,000件
    
    NEXTPOSITIONが返ってきた場合、自動的に続きを取得する。
    注意: 高頻度アクセスは接続遮断の原因になるため、間隔をあける。
    """
    import time
    all_series = []
    start_position = 1
    
    # 250件ずつのチャンクに分割
    chunk_size = 250
    for i in range(0, len(codes), chunk_size):
        chunk = codes[i:i + chunk_size]
        start_pos = None
        
        while True:
            params = dict(kwargs)
            if start_pos:
                params["startPosition"] = start_pos
            
            data = get_boj_data_by_code(chunk, db, **params)
            
            if data.get("STATUS") != 200:
                raise ValueError(f"API Error: {data.get('MESSAGE')}")
            
            # データを収集
            series_list = data.get("RESULTSET", [])
            all_series.extend(series_list)
            
            # 次のページがあるか確認
            next_pos = data.get("NEXTPOSITION")
            if next_pos is None:
                break
            start_pos = next_pos
            time.sleep(1)  # 高頻度アクセス対策
        
        if i + chunk_size < len(codes):
            time.sleep(1)  # チャンク間の間隔
    
    return all_series
```

---

## 2. 階層API

系列コードがわからない場合や、カテゴリ単位でデータを取得したい場合に使用。

### エンドポイント
```
GET https://www.stat-search.boj.or.jp/api/v1/getDataLayer
```

### パラメータ

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|-----|
| `db` | ✅ | DB名 | `FF`, `MD10` |
| `frequency` | ✅ | 期種 | `M`, `Q`, `D` |
| `layer` | ✅ | 階層情報（カンマ区切り、`*`でワイルドカード） | `1,1,1` or `*` |
| `format` | - | 出力形式 | `json` |
| `lang` | - | 言語 | `jp` |
| `startDate` | - | 開始期 | `202401` |
| `endDate` | - | 終了期 | `202412` |
| `startPosition` | - | 検索開始位置 | `255` |

### 期種の指定値

| 期種 | パラメータ値 |
|------|------------|
| 暦年 | `CY` |
| 年度 | `FY` |
| 暦年半期 | `CH` |
| 年度半期 | `FH` |
| 四半期 | `Q` |
| 月次 | `M` |
| 週次 | `W` |
| 日次 | `D` |

### 制限値（重要）

| 制限 | 上限値 | 超えた場合 |
|------|--------|----------|
| 抽出される系列数 | **1,250件** | エラー（データなし） |
| 1リクエストの系列数 | **250件** | 上限まで出力＋NEXTPOSITIONを返す |
| 1リクエストのデータ数（系列数×期数） | **60,000件** | 上限まで出力＋NEXTPOSITIONを返す |

### 実装例

```python
import requests
import time

def get_boj_data_by_layer(db: str, frequency: str, layer: str, 
                           start_date: str = None, end_date: str = None,
                           lang: str = "jp") -> list[dict]:
    """
    階層APIでデータを取得する（ページネーション対応）。
    
    Args:
        db: DB名（例: "FF", "MD10"）
        frequency: 期種（例: "M", "Q", "D"）
        layer: 階層情報（例: "1,1,1" または "*"）
        start_date: 開始期
        end_date: 終了期
        lang: 言語
    
    Returns:
        系列データのリスト
    
    注意:
        - layerに"*"を使う場合、系列数が1,250件を超えるとエラー
        - 系列数が多い場合は階層を細かく分けてリクエストすること
    """
    base_url = "https://www.stat-search.boj.or.jp/api/v1/getDataLayer"
    all_series = []
    start_position = None
    
    while True:
        params = {
            "format": "json",
            "lang": lang,
            "db": db,
            "frequency": frequency,
            "layer": layer,
        }
        if start_date:
            params["startDate"] = start_date
        if end_date:
            params["endDate"] = end_date
        if start_position:
            params["startPosition"] = start_position
        
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json()
        
        if data.get("STATUS") != 200:
            raise ValueError(f"API Error: {data.get('MESSAGE')}")

        series_list = data.get("RESULTSET", [])
        all_series.extend(series_list)
        
        next_pos = data.get("NEXTPOSITION")
        if next_pos is None:
            break
        start_position = next_pos
        time.sleep(1)  # 高頻度アクセス対策
    
    return all_series
```

---

## 3. メタデータAPI

系列コードや系列名称を調べたい場合に使用。コードAPIや階層APIのパラメータ作成前に活用する。

### エンドポイント
```
GET https://www.stat-search.boj.or.jp/api/v1/getMetadata
```

### パラメータ

| パラメータ | 必須 | 説明 | 例 |
|-----------|------|------|-----|
| `db` | ✅ | DB名 | `FM08`, `PR01` |
| `format` | - | 出力形式 | `csv` |
| `lang` | - | 言語 | `jp` |

### 実装例

```python
import requests

def get_boj_metadata(db: str, lang: str = "jp") -> dict:
    """
    メタデータAPIでDB内の系列情報を取得する。
    
    系列コードを調べたい場合や、収録期間を確認したい場合に使う。
    
    Args:
        db: DB名（例: "FM08"）
        lang: 言語（"jp" or "en"）
    
    Returns:
        メタ情報のdict
    """
    base_url = "https://www.stat-search.boj.or.jp/api/v1/getMetadata"
    params = {
        "format": "json",
        "lang": lang,
        "db": db,
    }
    
    response = requests.get(base_url, params=params)
    response.raise_for_status()
    return response.json()


def search_series_by_keyword(db: str, keyword: str, lang: str = "jp") -> list[dict]:
    """
    メタデータからキーワードで系列を検索する。
    
    Args:
        db: DB名
        keyword: 検索キーワード（系列名称に含まれる文字）
        lang: 言語
    
    Returns:
        マッチした系列のリスト（SERIES_CODE, NAME等を含む）
    """
    metadata = get_boj_metadata(db, lang)
    name_key = "NAME_OF_TIME_SERIES_J" if lang == "jp" else "NAME_OF_TIME_SERIES"

    results = []
    for series in metadata.get("RESULTSET", []):
        name = series.get(name_key, "")
        if keyword in name:
            results.append(series)

    return results
```

---

## 主要DB名リファレンス

### 金利関連
| DB名 | 名称 |
|------|------|
| `IR01` | 基準割引率および基準貸付利率（公定歩合） |
| `IR02` | 預金種類別店頭表示金利の平均年利率等 |
| `IR03` | 定期預金の預入期間別平均金利 |
| `IR04` | 貸出約定平均金利 |

### マーケット関連
| DB名 | 名称 |
|------|------|
| `FM01` | 無担保コールO/N物レート（毎営業日） |
| `FM02` | 短期金融市場金利 |
| `FM08` | 外国為替市況 |
| `FM09` | 実効為替レート |

### 預金・マネー・貸出
| DB名 | 名称 |
|------|------|
| `MD01` | マネタリーベース |
| `MD02` | マネーストック |
| `MD10` | 預金者別預金 |
| `MD11` | 預金・現金・貸出金 |
| `LA01` | 貸出先別貸出金 |

### 物価
| DB名 | 名称 |
|------|------|
| `PR01` | 企業物価指数（CGPI） |
| `PR02` | 企業向けサービス価格指数（SPPI） |

### その他
| DB名 | 名称 |
|------|------|
| `CO` | 短観（日銀短期経済観測調査） |
| `FF` | 資金循環 |
| `BP01` | 国際収支統計 |
| `BS01` | 日本銀行勘定 |
| `PF01` | 財政資金収支 |
| `BIS` | BIS国際資金取引統計 |

---

## レスポンス構造（JSON）

**重要:** APIレスポンスは `RESULTSET` という配列で返され、各系列の値は `VALUES` オブジェクトの中にネストされています。

```json
{
  "STATUS": 200,
  "MESSAGEID": "M181000I",
  "MESSAGE": "正常に終了しました。",
  "DATE": "2024-01-15T09:00:00+09:00",
  "PARAMETER": {
    "FORMAT": "JSON",
    "LANG": "JP",
    "DB": "FM01",
    "STARTDATE": "202401",
    "ENDDATE": "202412",
    "STARTPOSITION": ""
  },
  "NEXTPOSITION": null,
  "RESULTSET": [
    {
      "SERIES_CODE": "STRDCLUCON",
      "NAME_OF_TIME_SERIES_J": "無担保コールO/N物レート（加重平均）",
      "UNIT_J": "％",
      "FREQUENCY": "DAILY",
      "CATEGORY_J": "マーケット関連",
      "LAST_UPDATE": 20240115,
      "VALUES": {
        "SURVEY_DATES": [20240104, 20240105, 20240106],
        "VALUES": [0.076, 0.077, 0.078]
      }
    }
  ]
}
```

**注意点:**
- レスポンスのルート直下に `RESULTSET` 配列がある（`DATA.SERIES` ではない）
- `VALUES` は入れ子構造で、`SURVEY_DATES` と `VALUES` を含むオブジェクト
- 日付は整数で返される（例: `20240104`）
- `LAST_UPDATE` も整数
```

---

## エラーハンドリング

```python
def handle_boj_response(response_data: dict) -> dict:
    """
    日銀APIのレスポンスを処理し、エラーがあれば例外を発生させる。
    
    STATUSコード:
    - 200: 正常終了
    - 400: パラメータエラー（ユーザーの入力ミス）
    - 500: サーバー内部エラー（時間をおいて再試行）
    - 503: DBアクセスエラー（時間をおいて再試行）
    """
    status = response_data.get("STATUS")
    message = response_data.get("MESSAGE", "Unknown error")
    message_id = response_data.get("MESSAGEID", "")
    
    if status == 200:
        if message_id == "M181030I":
            # 正常終了だが該当データなし
            print(f"警告: {message}")
        return response_data
    elif status == 400:
        raise ValueError(f"パラメータエラー [{message_id}]: {message}")
    elif status in (500, 503):
        raise RuntimeError(f"サーバーエラー [{message_id}]: {message} - 時間をおいて再試行してください")
    else:
        raise RuntimeError(f"不明なエラー: STATUS={status}, {message}")
```

---

## 使用例：為替レートの取得

```python
import requests
import pandas as pd

def get_usd_jpy_rate(start_date: str, end_date: str) -> pd.DataFrame:
    """
    USD/JPYの為替レート（月中平均）を取得してDataFrameで返す。

    FM08（外国為替市況）DBの系列コードはメタデータAPIで確認すること。
    代表的な系列: FXERM07（東京市場 ドル・円 スポット 17時時点/月中平均）
    """
    url = "https://www.stat-search.boj.or.jp/api/v1/getDataCode"
    params = {
        "format": "json",
        "lang": "jp",
        "db": "FM08",
        "code": "FXERM07",  # 月中平均レート（月次データ）
        "startDate": start_date,
        "endDate": end_date,
    }

    resp = requests.get(url, params=params)
    resp.raise_for_status()
    data = resp.json()

    if data["STATUS"] != 200:
        raise ValueError(data["MESSAGE"])

    series = data["RESULTSET"][0]
    values_obj = series["VALUES"]

    df = pd.DataFrame({
        "date": values_obj["SURVEY_DATES"],
        "rate": values_obj["VALUES"],
        "unit": series.get("UNIT_J", ""),
    })
    # 日付は整数で返されるので文字列に変換してからパース
    df["date"] = pd.to_datetime(df["date"].astype(str), format="%Y%m%d")
    df["rate"] = pd.to_numeric(df["rate"], errors="coerce")
    return df.dropna(subset=["rate"])
```

---

## 注意事項

1. **高頻度アクセス禁止**: 短時間に大量リクエストすると接続遮断される。ループ処理では必ず`time.sleep(1)`以上の間隔をあける。

2. **同一期種の制約**: コードAPIでは、全ての系列コードが同じ期種（日次・月次・四半期など）でなければならない。期種が混在する場合は複数回に分けてリクエスト。

3. **文字制限**: パラメータ値に `< > " ! | \ ; '` および全角文字は使用不可。

4. **系列コードにDB名を付けない**: `IR01'MADR1Z@D`ではなく`MADR1Z@D`のみを指定。

5. **gzip対応**: HTTPヘッダーに`Accept-Encoding: gzip`を付けると転送量を削減できる。

6. **NEXTPOSITION の確認**: レスポンスに`NEXTPOSITION`が含まれる場合は全データが取得できていない。`startPosition`パラメータで続きを取得すること。

7. **データ更新時刻**: 原則として毎日8:50頃に更新される（遅延の可能性あり）。

8. **欠損値**: データがない場合は`null`が返る（CSVでは空白）。

9. **系列コードの確認**: 系列コードは時代とともに変更・廃止される場合があります。必ずメタデータAPIで最新の系列コードを確認してください。
   - 例: `FXUSDM`（存在しない） → `FXERM07`（東京市場 ドル・円 月中平均）が正しい

10. **日付型の注意**: `SURVEY_DATES` や `LAST_UPDATE` は整数（例: `20240104`）で返されます。文字列として扱う場合は `str()` で変換が必要です。
