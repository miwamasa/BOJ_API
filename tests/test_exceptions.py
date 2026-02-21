"""
tests/test_exceptions.py
========================
boj_client.exceptions モジュールのユニットテスト。

各例外クラスの属性・継承関係・メッセージ形式を検証する。
"""

from __future__ import annotations

import pytest

from boj_client.exceptions import (
    BOJAPIError,
    BOJClientError,
    BOJNetworkError,
    BOJNoDataError,
    BOJParameterError,
)


class TestExceptionHierarchy:
    """全例外が BOJClientError を継承していることを確認する。"""

    def test_BOJAPIErrorはBOJClientErrorのサブクラス(self):
        assert issubclass(BOJAPIError, BOJClientError)

    def test_BOJParameterErrorはBOJClientErrorのサブクラス(self):
        assert issubclass(BOJParameterError, BOJClientError)

    def test_BOJNetworkErrorはBOJClientErrorのサブクラス(self):
        assert issubclass(BOJNetworkError, BOJClientError)

    def test_BOJNoDataErrorはBOJClientErrorのサブクラス(self):
        assert issubclass(BOJNoDataError, BOJClientError)

    def test_全例外をBOJClientErrorで一括捕捉できる(self):
        exceptions = [
            BOJAPIError(400, "M181010E", "パラメータエラー"),
            BOJParameterError("dbが空です"),
            BOJNetworkError("接続失敗"),
            BOJNoDataError("データなし"),
        ]
        for exc in exceptions:
            with pytest.raises(BOJClientError):
                raise exc


class TestBOJAPIError:
    def test_属性が正しく設定される(self):
        exc = BOJAPIError(status=400, message_id="M181010E", message="パラメータエラー")
        assert exc.status == 400
        assert exc.message_id == "M181010E"
        assert exc.message == "パラメータエラー"

    def test_メッセージにstatusとidとmessageが含まれる(self):
        exc = BOJAPIError(status=500, message_id="M181500E", message="サーバーエラー")
        msg = str(exc)
        assert "500" in msg
        assert "M181500E" in msg
        assert "サーバーエラー" in msg


class TestBOJNetworkError:
    def test_original例外を保持できる(self):
        original = ConnectionError("タイムアウト")
        exc = BOJNetworkError("接続失敗", original=original)
        assert exc.original is original

    def test_originalなしでも生成できる(self):
        exc = BOJNetworkError("接続失敗")
        assert exc.original is None
