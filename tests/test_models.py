"""
tests/test_models.py
====================
boj_client.models モジュールのユニットテスト。

Series・SeriesMeta・SeriesValue の正しい生成・変換を検証する。
"""

from __future__ import annotations

import pytest
from datetime import date

from boj_client.models import Series, SeriesMeta, SeriesValue, _parse_api_date
from conftest import make_series_dict


class TestParseApiDate:
    """_parse_api_date ユーティリティ関数のテスト。"""

    def test_yyyymmdd_日次(self):
        assert _parse_api_date("20240115") == date(2024, 1, 15)

    def test_yyyymm_月次(self):
        assert _parse_api_date("202401") == date(2024, 1, 1)

    def test_yyyy_年次(self):
        assert _parse_api_date("2024") == date(2024, 1, 1)

    def test_不正フォーマットで例外(self):
        with pytest.raises(ValueError, match="対応外"):
            _parse_api_date("2024-01-15")  # ハイフン区切りは非対応

    def test_空文字で例外(self):
        with pytest.raises(ValueError):
            _parse_api_date("")


class TestSeriesFromApiDict:
    """Series.from_api_dict のテスト。"""

    def test_正常な系列データを変換できる(self):
        data = make_series_dict(
            code="FXUSDM",
            name_ja="米ドル（月中平均）",
            dates=["20240101", "20240201", "20240301"],
            values=[148.5, 149.7, 150.2],
        )
        series = Series.from_api_dict(data)

        assert series.code == "FXUSDM"
        assert series.name_ja == "米ドル（月中平均）"
        assert series.unit_ja == "円/米ドル"
        assert series.frequency == "MONTHLY"
        assert len(series.values) == 3
        assert series.values[0].observation_date == date(2024, 1, 1)
        assert series.values[0].value == pytest.approx(148.5)

    def test_欠損値はNoneになる(self):
        data = make_series_dict(
            dates=["20240101", "20240201"],
            values=[148.5, None],
        )
        series = Series.from_api_dict(data)

        assert series.values[1].value is None

    def test_値が全てNullでも空リストにならない(self):
        data = make_series_dict(
            dates=["20240101"],
            values=[None],
        )
        series = Series.from_api_dict(data)
        assert len(series.values) == 1
        assert series.values[0].value is None

    def test_空データでも例外が発生しない(self):
        series = Series.from_api_dict({})
        assert series.code == ""
        assert series.values == []

    def test_日付と値の件数が一致しない場合はzipで短い方に揃う(self):
        data = make_series_dict(
            dates=["20240101", "20240201"],
            values=[148.5],  # 1件少ない
        )
        series = Series.from_api_dict(data)
        assert len(series.values) == 1


class TestSeriesLatestValue:
    """Series.latest_value メソッドのテスト。"""

    def test_最新の非null値を返す(self):
        data = make_series_dict(
            dates=["20240101", "20240201", "20240301"],
            values=[148.5, 149.7, None],
        )
        series = Series.from_api_dict(data)
        latest = series.latest_value()

        assert latest is not None
        assert latest.value == pytest.approx(149.7)
        assert latest.observation_date == date(2024, 2, 1)

    def test_全てNullの場合はNoneを返す(self):
        data = make_series_dict(
            dates=["20240101"],
            values=[None],
        )
        series = Series.from_api_dict(data)
        assert series.latest_value() is None

    def test_値が空の場合はNoneを返す(self):
        series = Series.from_api_dict({})
        assert series.latest_value() is None


class TestSeriesToRecords:
    """Series.to_records メソッドのテスト。"""

    def test_レコードのキーが正しい(self):
        data = make_series_dict(
            code="FXUSDM",
            dates=["20240101"],
            values=[148.5],
        )
        records = Series.from_api_dict(data).to_records()

        assert len(records) == 1
        assert set(records[0].keys()) == {"date", "value", "code", "name", "unit"}
        assert records[0]["code"] == "FXUSDM"
        assert records[0]["value"] == pytest.approx(148.5)
        assert records[0]["date"] == date(2024, 1, 1)

    def test_複数レコードが正しい順序で返る(self):
        data = make_series_dict(
            dates=["20240101", "20240201"],
            values=[148.5, 149.7],
        )
        records = Series.from_api_dict(data).to_records()
        assert records[0]["date"] == date(2024, 1, 1)
        assert records[1]["date"] == date(2024, 2, 1)


class TestSeriesMetaFromApiDict:
    """SeriesMeta.from_api_dict のテスト。"""

    def test_正常なメタデータを変換できる(self):
        data = {
            "SERIES_CODE": "FXUSDM",
            "NAME_OF_TIME_SERIES_J": "米ドル（月中平均）",
            "NAME_OF_TIME_SERIES": "USD/JPY (monthly average)",
            "FREQUENCY": "MONTHLY",
            "START_DATE": "198401",
            "END_DATE": "202412",
        }
        meta = SeriesMeta.from_api_dict(data, db="FM08")

        assert meta.code == "FXUSDM"
        assert meta.db == "FM08"
        assert meta.start_date == date(1984, 1, 1)
        assert meta.end_date == date(2024, 12, 1)

    def test_日付が空でもNoneになる(self):
        data = {
            "SERIES_CODE": "TEST",
            "NAME_OF_TIME_SERIES_J": "テスト",
            "FREQUENCY": "M",
            "START_DATE": "",
            "END_DATE": "",
        }
        meta = SeriesMeta.from_api_dict(data)
        assert meta.start_date is None
        assert meta.end_date is None
