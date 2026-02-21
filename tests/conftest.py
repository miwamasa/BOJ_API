"""
tests/conftest.py
=================
pytest 共通フィクスチャ・モックファクトリ集。

日銀APIへの実際のHTTPリクエストを行わずにテストするため、
requests.Session をモックに差し替える仕組みを提供する。
"""

from __future__ import annotations

import json
from datetime import date
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from boj_client import BOJClient


# ---------------------------------------------------------------------------
# APIレスポンスのファクトリ関数
# ---------------------------------------------------------------------------

def make_code_response(
    *,
    series: list[dict] | None = None,
    status: int = 200,
    message: str = "正常に終了しました。",
    message_id: str = "M181000I",
    next_position: int | None = None,
) -> dict:
    """コードAPI / 階層APIの正常レスポンスを生成するファクトリ。

    Args:
        series: 系列データのリスト（省略時は空）。
        status: STATUSコード。
        message: MESSAGE フィールド。
        message_id: MESSAGEID フィールド。
        next_position: NEXTPOSITION（ページネーション用）。

    Returns:
        APIレスポンス形式の dict。
    """
    resp: dict[str, Any] = {
        "STATUS": status,
        "MESSAGEID": message_id,
        "MESSAGE": message,
        "DATE": "2024-01-15T09:00:00",
        "NEXTPOSITION": next_position,
        "DATA": {
            "SERIES": series or [],
        },
    }
    return resp


def make_series_dict(
    *,
    code: str = "FXUSDM",
    name_ja: str = "米ドル（月中平均）",
    name_en: str = "USD/JPY (monthly average)",
    unit_ja: str = "円/米ドル",
    frequency: str = "MONTHLY",
    dates: list[str] | None = None,
    values: list[float | None] | None = None,
) -> dict:
    """系列データ dict を生成するファクトリ（APIレスポンスの SERIES[i] 形式）。

    Args:
        code: 系列コード。
        name_ja: 系列名（日本語）。
        name_en: 系列名（英語）。
        unit_ja: 単位。
        frequency: 期種。
        dates: 観測日のリスト（"YYYYMMDD" 形式）。省略時はサンプルを使用。
        values: 観測値リスト。省略時はサンプルを使用。

    Returns:
        APIレスポンス形式の系列データ dict。
    """
    if dates is None:
        dates = ["20240101", "20240201", "20240301"]
    if values is None:
        values = [148.5, 149.7, 150.2]
    return {
        "SERIES_CODE": code,
        "NAME_OF_TIME_SERIES_J": name_ja,
        "NAME_OF_TIME_SERIES": name_en,
        "UNIT_J": unit_ja,
        "UNIT": "",
        "FREQUENCY": frequency,
        "CATEGORY_J": "マーケット関連",
        "LAST_UPDATE": "20240315",
        "SURVEY_DATES": dates,
        "VALUES": values,
    }


def make_metadata_response(*, series: list[dict] | None = None, db: str = "FM08") -> dict:
    """メタデータAPIのレスポンスを生成するファクトリ。"""
    return {
        "STATUS": 200,
        "MESSAGEID": "M181000I",
        "MESSAGE": "正常に終了しました。",
        "DATE": "2024-01-15T09:00:00",
        "NEXTPOSITION": None,
        "DATA": {
            "SERIES": series or [
                {
                    "SERIES_CODE": "FXUSDM",
                    "NAME_OF_TIME_SERIES_J": "米ドル（月中平均）",
                    "NAME_OF_TIME_SERIES": "USD/JPY (monthly average)",
                    "FREQUENCY": "MONTHLY",
                    "START_DATE": "198401",
                    "END_DATE": "202412",
                },
                {
                    "SERIES_CODE": "FXEUROM",
                    "NAME_OF_TIME_SERIES_J": "ユーロ（月中平均）",
                    "NAME_OF_TIME_SERIES": "EUR/JPY (monthly average)",
                    "FREQUENCY": "MONTHLY",
                    "START_DATE": "199901",
                    "END_DATE": "202412",
                },
            ],
        },
    }


# ---------------------------------------------------------------------------
# モックセッション
# ---------------------------------------------------------------------------

class MockSession:
    """requests.Session の最小限モック。

    テストケースごとにレスポンスをキューに積んでおき、
    ``get()`` が呼ばれるたびに先頭から返す。
    """

    def __init__(self, responses: list[dict]) -> None:
        self._responses = list(responses)
        self.requests: list[tuple[str, dict]] = []  # 呼び出し履歴

    def get(self, url: str, params: dict | None = None, **_kwargs) -> MagicMock:
        self.requests.append((url, params or {}))
        if not self._responses:
            raise RuntimeError("MockSession: レスポンスキューが空です。")
        data = self._responses.pop(0)
        resp = MagicMock()
        resp.json.return_value = data
        resp.raise_for_status.return_value = None
        return resp


# ---------------------------------------------------------------------------
# pytest フィクスチャ
# ---------------------------------------------------------------------------

@pytest.fixture
def simple_fx_response() -> dict:
    """シンプルな為替レートAPIレスポンス（ページネーションなし）。"""
    return make_code_response(series=[make_series_dict()])


@pytest.fixture
def no_data_response() -> dict:
    """データなし（M181030I）のAPIレスポンス。"""
    return make_code_response(
        status=200,
        message="該当するデータがありません。",
        message_id="M181030I",
        series=[],
    )


@pytest.fixture
def error_400_response() -> dict:
    """パラメータエラー（400）のAPIレスポンス。"""
    return make_code_response(
        status=400,
        message="入力パラメータに誤りがあります。",
        message_id="M181010E",
        series=[],
    )


@pytest.fixture
def paginated_responses() -> list[dict]:
    """2ページにわたるAPIレスポンスのリスト（ページネーションテスト用）。"""
    page1 = make_code_response(
        series=[make_series_dict(code="FXUSDM")],
        next_position=251,
    )
    page2 = make_code_response(
        series=[make_series_dict(code="FXEUROM", name_ja="ユーロ（月中平均）")],
    )
    return [page1, page2]


@pytest.fixture
def metadata_response() -> dict:
    """標準的なメタデータAPIレスポンス。"""
    return make_metadata_response()
