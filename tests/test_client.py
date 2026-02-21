"""
tests/test_client.py
====================
BOJClient クラスのユニットテスト。

実際のHTTPリクエストは行わず、MockSession でレスポンスを差し替えることで
ネットワーク不要なテストを実現する。
"""

from __future__ import annotations

import pytest
from datetime import date
from unittest.mock import MagicMock, patch

from boj_client import BOJClient
from boj_client.exceptions import (
    BOJAPIError,
    BOJNetworkError,
    BOJNoDataError,
    BOJParameterError,
)
from conftest import (
    MockSession,
    make_code_response,
    make_metadata_response,
    make_series_dict,
)


# ---------------------------------------------------------------------------
# BOJClient の初期化テスト
# ---------------------------------------------------------------------------

class TestBOJClientInit:
    def test_デフォルト設定で初期化できる(self):
        client = BOJClient()
        assert client.lang == "jp"
        assert client.timeout == 30

    def test_カスタム設定で初期化できる(self):
        client = BOJClient(timeout=60, lang="en", page_sleep=2.0)
        assert client.timeout == 60
        assert client.lang == "en"
        assert client.page_sleep == 2.0

    def test_不正なlangで例外(self):
        with pytest.raises(BOJParameterError, match="lang"):
            BOJClient(lang="zh")

    def test_カスタムセッションを注入できる(self):
        mock = MagicMock()
        client = BOJClient(session=mock)
        assert client._session is mock


# ---------------------------------------------------------------------------
# get_by_code テスト
# ---------------------------------------------------------------------------

class TestGetByCode:
    def _make_client(self, responses: list[dict]) -> BOJClient:
        return BOJClient(session=MockSession(responses), page_sleep=0)

    def test_正常な1系列を取得できる(self, simple_fx_response):
        client = self._make_client([simple_fx_response])
        series = client.get_by_code(db="FM08", codes=["FXUSDM"])

        assert len(series) == 1
        assert series[0].code == "FXUSDM"
        assert len(series[0].values) == 3
        assert series[0].values[0].value == pytest.approx(148.5)

    def test_開始終了日付が正しく渡される(self, simple_fx_response):
        session = MockSession([simple_fx_response])
        client = BOJClient(session=session, page_sleep=0)
        client.get_by_code(
            db="FM08",
            codes=["FXUSDM"],
            start_date="202401",
            end_date="202412",
        )
        _, params = session.requests[0]
        assert params["startDate"] == "202401"
        assert params["endDate"] == "202412"
        assert params["db"] == "FM08"
        assert params["code"] == "FXUSDM"

    def test_複数コードはカンマ区切りで送信される(self, simple_fx_response):
        session = MockSession([simple_fx_response])
        client = BOJClient(session=session, page_sleep=0)
        client.get_by_code(db="FM08", codes=["FXUSDM", "FXEUROM"])
        _, params = session.requests[0]
        assert "FXUSDM" in params["code"]
        assert "FXEUROM" in params["code"]

    def test_ページネーションで全データを取得できる(self, paginated_responses):
        client = self._make_client(paginated_responses)
        series = client.get_by_code(db="FM08", codes=["FXUSDM"])
        # 2ページ分なので2系列
        assert len(series) == 2
        codes = {s.code for s in series}
        assert "FXUSDM" in codes
        assert "FXEUROM" in codes

    def test_ページネーション時に2リクエスト送信される(self, paginated_responses):
        session = MockSession(paginated_responses)
        client = BOJClient(session=session, page_sleep=0)
        client.get_by_code(db="FM08", codes=["FXUSDM"])
        assert len(session.requests) == 2
        # 2回目のリクエストに startPosition が含まれる
        _, p2 = session.requests[1]
        assert "startPosition" in p2
        assert p2["startPosition"] == "251"

    def test_250件超えのコードを自動分割する(self):
        """251件のコードを指定した場合、リクエストが2回に分割される。"""
        resp1 = make_code_response(series=[make_series_dict(code="CODE1")])
        resp2 = make_code_response(series=[make_series_dict(code="CODE2")])
        session = MockSession([resp1, resp2])
        client = BOJClient(session=session, page_sleep=0)

        codes = [f"CODE{i}" for i in range(251)]
        series = client.get_by_code(db="FM08", codes=codes)

        assert len(session.requests) == 2
        assert len(series) == 2

    # -- エラーケース --

    def test_dbが空で例外(self):
        client = self._make_client([])
        with pytest.raises(BOJParameterError, match="db"):
            client.get_by_code(db="", codes=["FXUSDM"])

    def test_codesが空で例外(self):
        client = self._make_client([])
        with pytest.raises(BOJParameterError, match="codes"):
            client.get_by_code(db="FM08", codes=[])

    def test_データなし(self, no_data_response):
        client = BOJClient(session=MockSession([no_data_response]), page_sleep=0)
        with pytest.raises(BOJNoDataError):
            client.get_by_code(db="FM08", codes=["FXUSDM"])

    def test_400エラーでBOJAPIError(self, error_400_response):
        client = self._make_client([error_400_response])
        with pytest.raises(BOJAPIError) as exc_info:
            client.get_by_code(db="FM08", codes=["INVALID"])
        assert exc_info.value.status == 400

    def test_ネットワークエラーでBOJNetworkError(self):
        import requests as req

        session = MagicMock()
        session.get.side_effect = req.exceptions.ConnectionError("接続失敗")
        client = BOJClient(session=session, page_sleep=0)

        with pytest.raises(BOJNetworkError, match="HTTPリクエストに失敗"):
            client.get_by_code(db="FM08", codes=["FXUSDM"])

    def test_不正JSONでBOJNetworkError(self):
        import requests as req

        resp = MagicMock()
        resp.raise_for_status.return_value = None
        resp.json.side_effect = req.exceptions.JSONDecodeError("error", "", 0)

        session = MagicMock()
        session.get.return_value = resp
        client = BOJClient(session=session, page_sleep=0)

        with pytest.raises(BOJNetworkError, match="JSON"):
            client.get_by_code(db="FM08", codes=["FXUSDM"])


# ---------------------------------------------------------------------------
# get_by_layer テスト
# ---------------------------------------------------------------------------

class TestGetByLayer:
    def _make_client(self, responses: list[dict]) -> BOJClient:
        return BOJClient(session=MockSession(responses), page_sleep=0)

    def test_正常なレスポンスを取得できる(self, simple_fx_response):
        client = self._make_client([simple_fx_response])
        series = client.get_by_layer(db="FM08", frequency="M", layer="1,1")
        assert len(series) == 1

    def test_パラメータが正しく送信される(self, simple_fx_response):
        session = MockSession([simple_fx_response])
        client = BOJClient(session=session, page_sleep=0)
        client.get_by_layer(
            db="FF", frequency="Q", layer="1,*",
            start_date="202301", end_date="202312",
        )
        _, params = session.requests[0]
        assert params["db"] == "FF"
        assert params["frequency"] == "Q"
        assert params["layer"] == "1,*"
        assert params["startDate"] == "202301"

    def test_dbが空で例外(self):
        client = self._make_client([])
        with pytest.raises(BOJParameterError):
            client.get_by_layer(db="", frequency="M", layer="*")

    def test_frequencyが空で例外(self):
        client = self._make_client([])
        with pytest.raises(BOJParameterError):
            client.get_by_layer(db="FM08", frequency="", layer="*")

    def test_layerが空で例外(self):
        client = self._make_client([])
        with pytest.raises(BOJParameterError):
            client.get_by_layer(db="FM08", frequency="M", layer="")


# ---------------------------------------------------------------------------
# get_metadata / search_metadata テスト
# ---------------------------------------------------------------------------

class TestGetMetadata:
    def _make_client(self, responses: list[dict]) -> BOJClient:
        return BOJClient(session=MockSession(responses), page_sleep=0)

    def test_メタデータを取得できる(self, metadata_response):
        client = self._make_client([metadata_response])
        metas = client.get_metadata(db="FM08")
        assert len(metas) == 2
        assert metas[0].code == "FXUSDM"
        assert metas[0].db == "FM08"

    def test_dbが空で例外(self):
        client = self._make_client([])
        with pytest.raises(BOJParameterError, match="db"):
            client.get_metadata(db="")

    def test_DBの名前がメタに引き継がれる(self, metadata_response):
        client = self._make_client([metadata_response])
        metas = client.get_metadata(db="FM08")
        assert all(m.db == "FM08" for m in metas)


class TestSearchMetadata:
    def _make_client(self, responses: list[dict]) -> BOJClient:
        return BOJClient(session=MockSession(responses), page_sleep=0)

    def test_日本語キーワードで絞り込める(self, metadata_response):
        client = self._make_client([metadata_response])
        results = client.search_metadata(db="FM08", keyword="米ドル")
        assert len(results) == 1
        assert results[0].code == "FXUSDM"

    def test_英語キーワードで絞り込める(self, metadata_response):
        client = self._make_client([metadata_response])
        results = client.search_metadata(db="FM08", keyword="EUR/JPY")
        assert len(results) == 1
        assert results[0].code == "FXEUROM"

    def test_大文字小文字を無視する(self, metadata_response):
        client = self._make_client([metadata_response])
        results = client.search_metadata(db="FM08", keyword="eur/jpy")
        assert len(results) == 1

    def test_マッチしない場合は空リスト(self, metadata_response):
        client = self._make_client([metadata_response])
        results = client.search_metadata(db="FM08", keyword="存在しないキーワード")
        assert results == []


# ---------------------------------------------------------------------------
# lang パラメータのテスト
# ---------------------------------------------------------------------------

class TestLangParameter:
    def test_英語レスポンスのリクエストを送れる(self, simple_fx_response):
        session = MockSession([simple_fx_response])
        client = BOJClient(session=session, lang="en", page_sleep=0)
        client.get_by_code(db="FM08", codes=["FXUSDM"])
        _, params = session.requests[0]
        assert params["lang"] == "en"

    def test_日本語レスポンスがデフォルト(self, simple_fx_response):
        session = MockSession([simple_fx_response])
        client = BOJClient(session=session, page_sleep=0)
        client.get_by_code(db="FM08", codes=["FXUSDM"])
        _, params = session.requests[0]
        assert params["lang"] == "jp"
