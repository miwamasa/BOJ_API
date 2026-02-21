"""
examples/basic_usage.py
========================
boj_client の基本的な使い方を示すサンプルスクリプト。

このスクリプトは実際の日銀 API にアクセスするため、
インターネット接続が必要です。

実行方法:
    python examples/basic_usage.py
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# プロジェクトルートをパスに追加（examples/ から実行される場合）
project_root = Path(__file__).parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from boj_client import BOJClient
from boj_client.exceptions import BOJClientError, BOJNoDataError

# デバッグ時は logging を設定
logging.basicConfig(level=logging.WARNING)


def example_fx_rates():
    """例1: 為替レート（月次）を取得して表示する。"""
    print("=" * 60)
    print("例1: USD/JPY 為替レート（2024年）")
    print("=" * 60)

    client = BOJClient()

    try:
        series_list = client.get_by_code(
            db="FM08",
            codes=["FXERM07"],         # 米ドル（月中平均、17時時点）
            start_date="202401",
            end_date="202412",
        )
    except BOJNoDataError as e:
        print(f"データが見つかりませんでした: {e}")
        return
    except BOJClientError as e:
        print(f"エラー: {e}")
        return

    for series in series_list:
        print(f"\n系列: {series.name_ja} [{series.code}]")
        print(f"単位: {series.unit_ja}")
        print("-" * 40)
        for sv in series.values:
            val_str = f"{sv.value:.2f}" if sv.value is not None else "N/A"
            print(f"  {sv.observation_date.strftime('%Y-%m')}  {val_str} {series.unit_ja}")

        latest = series.latest_value()
        if latest:
            print(f"\n→ 最新値: {latest.value:.2f} {series.unit_ja} ({latest.observation_date})")


def example_search_metadata():
    """例2: メタデータを検索して系列コードを調べる。"""
    print("\n" + "=" * 60)
    print("例2: FM08 DB で「ドル」を含む系列を検索")
    print("=" * 60)

    client = BOJClient()

    try:
        results = client.search_metadata(db="FM08", keyword="ドル")
    except BOJClientError as e:
        print(f"エラー: {e}")
        return

    print(f"\n{len(results)} 件見つかりました:")
    for meta in results:
        print(f"  [{meta.code}] {meta.name_ja}  ({meta.frequency})")
        if meta.start_date and meta.end_date:
            print(f"    収録期間: {meta.start_date} 〜 {meta.end_date}")


def example_multiple_series():
    """例3: 複数指標の為替レートをまとめて取得する。"""
    print("\n" + "=" * 60)
    print("例3: USD/JPY 複数指標の比較（2024年12月）")
    print("=" * 60)

    client = BOJClient()

    # 注意: 実際の系列コードはメタデータAPIで確認すること
    try:
        series_list = client.get_by_code(
            db="FM08",
            codes=["FXERM06", "FXERM07", "FXERM03", "FXERM05"],  # 月末、月中平均、最高値、最安値
            start_date="202412",
            end_date="202412",
        )
    except BOJNoDataError:
        print("指定期間のデータがありませんでした。")
        return
    except BOJClientError as e:
        print(f"エラー: {e}")
        return

    print("\n指標        12月のレート")
    print("-" * 40)
    for series in series_list:
        latest = series.latest_value()
        if latest:
            name = series.name_ja.replace("東京市場　ドル・円　スポット　", "")
            print(f"{name:<20} {latest.value:>8.2f} {series.unit_ja}")


def example_to_pandas():
    """例4: pandas DataFrame に変換する。"""
    print("\n" + "=" * 60)
    print("例4: pandas DataFrame への変換")
    print("=" * 60)

    try:
        import pandas as pd
    except ImportError:
        print("pandas が未インストールのためスキップします。")
        return

    client = BOJClient()

    try:
        series_list = client.get_by_code(
            db="FM08",
            codes=["FXERM07"],  # 米ドル（月中平均、17時時点）
            start_date="202301",
            end_date="202412",
        )
    except BOJClientError as e:
        print(f"エラー: {e}")
        return

    records = []
    for series in series_list:
        records.extend(series.to_records())

    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.dropna(subset=["value"]).sort_values("date")

    print(f"\n取得件数: {len(df)} 行")
    print(df.head(5).to_string(index=False))
    print(f"\n統計:")
    print(df["value"].describe().to_string())


if __name__ == "__main__":
    example_search_metadata()
    example_fx_rates()
    example_multiple_series()
    example_to_pandas()
