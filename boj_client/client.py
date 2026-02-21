"""
boj_client.client
=================
日本銀行 時系列統計データ API のメインクライアント。

コードAPI・階層API・メタデータAPIの3つのエンドポイントをサポートし、
ページネーションの自動処理、エラーハンドリング、リトライロジックを内蔵する。

使い方::

    from boj_client import BOJClient

    client = BOJClient()

    # 為替レートを取得（2024年）
    series_list = client.get_by_code(
        db="FM08",
        codes=["FXUSDM"],
        start_date="202401",
        end_date="202412",
    )
    df = series_list[0].to_records()

    # メタデータからキーワード検索
    metas = client.search_metadata(db="FM08", keyword="米ドル")
"""

from __future__ import annotations

import time
import logging
from typing import Optional, Protocol, runtime_checkable

import requests
from requests import Session
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .exceptions import (
    BOJAPIError,
    BOJNetworkError,
    BOJNoDataError,
    BOJParameterError,
)
from .models import Series, SeriesMeta

logger = logging.getLogger(__name__)

_BASE_URL = "https://www.stat-search.boj.or.jp/api/v1"

# API の1リクエストあたりの系列数上限
_MAX_CODES_PER_REQUEST = 250
# ページネーション時のスリープ（高頻度アクセス対策）
_PAGE_SLEEP_SECONDS = 1.0


# ---------------------------------------------------------------------------
# HTTP セッションファクトリ
# ---------------------------------------------------------------------------

def _build_session(timeout: int, max_retries: int) -> Session:
    """リトライ設定済みの requests.Session を生成する。

    503 / 500 などの一時的なサーバーエラーに対して自動リトライを行う。

    Args:
        timeout: タイムアウト秒数。
        max_retries: リトライ回数。

    Returns:
        設定済みの Session オブジェクト。
    """
    session = Session()
    retry = Retry(
        total=max_retries,
        backoff_factor=2.0,
        status_forcelist={500, 503},
        allowed_methods={"GET"},
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update({
        "Accept-Encoding": "gzip",  # 転送量削減
        "User-Agent": "boj-client/1.0 (python-requests)",
    })
    return session


# ---------------------------------------------------------------------------
# テスト差し替え用プロトコル
# ---------------------------------------------------------------------------

@runtime_checkable
class _HttpGettable(Protocol):
    """テスト時に Session をモックに差し替えるためのプロトコル。"""
    def get(self, url: str, params: dict | None = None, **kwargs) -> requests.Response:
        ...


# ---------------------------------------------------------------------------
# メインクライアント
# ---------------------------------------------------------------------------

class BOJClient:
    """日銀 時系列統計データ API クライアント。

    Args:
        timeout: HTTPリクエストのタイムアウト秒数（デフォルト: 30）。
        max_retries: 一時的なサーバーエラー時のリトライ回数（デフォルト: 3）。
        lang: レスポンスの言語（"jp" または "en"、デフォルト: "jp"）。
        session: カスタム HTTP セッション（主にテスト用）。None の場合は自動生成。
        page_sleep: ページネーション間のスリープ秒数（デフォルト: 1.0）。

    Examples:
        >>> client = BOJClient()
        >>> series = client.get_by_code(db="FM08", codes=["FXUSDM"], start_date="202401")
        >>> print(series[0].name_ja)
        米ドル（月中平均）
    """

    def __init__(
        self,
        *,
        timeout: int = 30,
        max_retries: int = 3,
        lang: str = "jp",
        session: _HttpGettable | None = None,
        page_sleep: float = _PAGE_SLEEP_SECONDS,
    ) -> None:
        if lang not in ("jp", "en"):
            raise BOJParameterError(f"lang は 'jp' または 'en' を指定してください: {lang!r}")
        self.lang = lang
        self.timeout = timeout
        self.page_sleep = page_sleep
        self._session: _HttpGettable = session or _build_session(timeout, max_retries)

    # ------------------------------------------------------------------
    # パブリックAPI
    # ------------------------------------------------------------------

    def get_by_code(
        self,
        *,
        db: str,
        codes: list[str],
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Series]:
        """コードAPIを使って系列データを取得する。

        同一期種の系列コードをリストで指定する。250件を超える場合は
        自動的に複数リクエストに分割する。

        Args:
            db: DB名（例: "FM08", "IR01"）。
            codes: 系列コードのリスト。全て同一期種である必要がある。
            start_date: 取得開始期（例: "202401"）。省略時は収録開始期から。
            end_date: 取得終了期（例: "202412"）。省略時は収録終了期まで。

        Returns:
            Series オブジェクトのリスト（引数 codes と同順とは限らない）。

        Raises:
            BOJParameterError: db や codes が空の場合。
            BOJAPIError: APIがエラーステータスを返した場合。
            BOJNoDataError: 正常終了したが該当データが存在しない場合。
            BOJNetworkError: ネットワークエラーが発生した場合。

        Examples:
            >>> client = BOJClient()
            >>> series = client.get_by_code(
            ...     db="FM08",
            ...     codes=["FXUSDM", "FXEUROM"],
            ...     start_date="202401",
            ...     end_date="202412",
            ... )
        """
        if not db:
            raise BOJParameterError("db は必須です。")
        if not codes:
            raise BOJParameterError("codes は1件以上指定してください。")

        all_series: list[Series] = []
        for i in range(0, len(codes), _MAX_CODES_PER_REQUEST):
            chunk = codes[i : i + _MAX_CODES_PER_REQUEST]
            all_series.extend(
                self._fetch_code_paginated(
                    db=db,
                    codes=chunk,
                    start_date=start_date,
                    end_date=end_date,
                )
            )
            if i + _MAX_CODES_PER_REQUEST < len(codes):
                time.sleep(self.page_sleep)
        return all_series

    def get_by_layer(
        self,
        *,
        db: str,
        frequency: str,
        layer: str,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> list[Series]:
        """階層APIを使って系列データを取得する。

        系列コードがわからない場合や、カテゴリ単位でまとめて取得したい場合に使う。

        Args:
            db: DB名。
            frequency: 期種（"D"=日次, "M"=月次, "Q"=四半期, "CY"=暦年 等）。
            layer: 階層情報（カンマ区切り or "\\*"）。例: "1,1,1"。
            start_date: 取得開始期。
            end_date: 取得終了期。

        Returns:
            Series オブジェクトのリスト。

        Raises:
            BOJParameterError: 必須パラメータが空の場合。
            BOJAPIError: APIがエラーを返した場合（系列数1,250件超えを含む）。
            BOJNoDataError: 該当データが存在しない場合。
            BOJNetworkError: ネットワークエラーの場合。
        """
        if not db or not frequency or not layer:
            raise BOJParameterError("db, frequency, layer は全て必須です。")

        url = f"{_BASE_URL}/getDataLayer"
        base_params: dict[str, str] = {
            "format": "json",
            "lang": self.lang,
            "db": db,
            "frequency": frequency,
            "layer": layer,
        }
        if start_date:
            base_params["startDate"] = start_date
        if end_date:
            base_params["endDate"] = end_date

        return self._fetch_all_pages(url, base_params)

    def get_metadata(self, *, db: str) -> list[SeriesMeta]:
        """メタデータAPIで指定DBの全系列メタ情報を取得する。

        系列コードの調査や、収録期間の確認に使う。

        Args:
            db: DB名（例: "FM08"）。

        Returns:
            SeriesMeta オブジェクトのリスト。

        Raises:
            BOJParameterError: db が空の場合。
            BOJAPIError: APIエラーの場合。
            BOJNetworkError: ネットワークエラーの場合。
        """
        if not db:
            raise BOJParameterError("db は必須です。")

        url = f"{_BASE_URL}/getMetadata"
        params = {"format": "json", "lang": self.lang, "db": db}
        raw = self._get(url, params)
        self._check_status(raw)

        series_list = raw.get("DATA", {}).get("SERIES", [])
        return [SeriesMeta.from_api_dict(s, db=db) for s in series_list]

    def search_metadata(self, *, db: str, keyword: str) -> list[SeriesMeta]:
        """メタデータをキーワードで絞り込み検索する。

        ``get_metadata`` を内部で呼び出し、系列名に keyword を含むものだけを返す。

        Args:
            db: DB名。
            keyword: 系列名（日本語または英語）に含まれる検索文字列。

        Returns:
            マッチした SeriesMeta のリスト。
        """
        metas = self.get_metadata(db=db)
        lower_kw = keyword.lower()
        return [
            m for m in metas
            if lower_kw in m.name_ja.lower() or lower_kw in m.name_en.lower()
        ]

    # ------------------------------------------------------------------
    # 内部メソッド
    # ------------------------------------------------------------------

    def _fetch_code_paginated(
        self,
        *,
        db: str,
        codes: list[str],
        start_date: str | None,
        end_date: str | None,
    ) -> list[Series]:
        """コードAPIをページネーション付きで呼び出す（内部用）。"""
        url = f"{_BASE_URL}/getDataCode"
        base_params: dict[str, str] = {
            "format": "json",
            "lang": self.lang,
            "db": db,
            "code": ",".join(codes),
        }
        if start_date:
            base_params["startDate"] = start_date
        if end_date:
            base_params["endDate"] = end_date

        return self._fetch_all_pages(url, base_params)

    def _fetch_all_pages(self, url: str, base_params: dict[str, str]) -> list[Series]:
        """ページネーションを自動処理して全データを返す（内部用）。

        NEXTPOSITION が返ってくる限りリクエストを繰り返す。
        """
        all_series: list[Series] = []
        params = dict(base_params)

        while True:
            raw = self._get(url, params)
            self._check_status(raw)

            for s in raw.get("RESULTSET", []):
                all_series.append(Series.from_api_dict(s))

            next_pos = raw.get("NEXTPOSITION")
            if next_pos is None:
                break
            params["startPosition"] = str(next_pos)
            logger.debug("ページネーション: NEXTPOSITION=%s", next_pos)
            time.sleep(self.page_sleep)

        return all_series

    def _get(self, url: str, params: dict) -> dict:
        """HTTPリクエストを実行してJSONをdictで返す（内部用）。

        Raises:
            BOJNetworkError: 接続失敗・タイムアウト・不正JSONの場合。
        """
        logger.debug("GET %s params=%s", url, params)
        try:
            resp = self._session.get(url, params=params, timeout=self.timeout)
            resp.raise_for_status()
            return resp.json()
        except requests.exceptions.JSONDecodeError as exc:
            raise BOJNetworkError("レスポンスのJSONパースに失敗しました。", exc) from exc
        except requests.exceptions.RequestException as exc:
            raise BOJNetworkError(f"HTTPリクエストに失敗しました: {exc}", exc) from exc

    @staticmethod
    def _check_status(data: dict) -> None:
        """APIレスポンスのSTATUSをチェックし、エラーなら例外を送出する。

        Raises:
            BOJNoDataError: 正常終了だが該当データなし（MESSAGEID=M181030I）。
            BOJAPIError: STATUS が 200 以外の場合。
        """
        status = data.get("STATUS")
        message_id = data.get("MESSAGEID", "")
        message = data.get("MESSAGE", "Unknown error")

        if status == 200:
            if message_id == "M181030I":
                raise BOJNoDataError(
                    f"該当するデータが存在しません: {message}"
                )
            return

        raise BOJAPIError(
            status=status or 0,
            message_id=message_id,
            message=message,
        )
