"""
boj_client.models
=================
日銀 API のレスポンスを表すデータモデル群。

Python の dataclass を使用し、型安全にデータを扱えるようにする。
APIの生JSONをそのまま扱うのではなく、明示的な型で保持することで
IDEの補完やバグの早期発見を助ける。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from typing import Optional


# ---------------------------------------------------------------------------
# 系列データ
# ---------------------------------------------------------------------------

@dataclass
class SeriesValue:
    """単一の観測値（日付＋値のペア）。

    Attributes:
        observation_date: 観測日（日次・月次・四半期・年次を問わず date 型で統一）。
        value: 観測値。欠損値は None。
    """
    observation_date: date
    value: Optional[float]


@dataclass
class Series:
    """一つの時系列データ系列全体。

    Attributes:
        code: 系列コード（例: "FXUSDM"）。
        name_ja: 系列名（日本語）。
        name_en: 系列名（英語）。空文字の場合あり。
        unit_ja: 単位（日本語、例: "円/米ドル"）。
        unit_en: 単位（英語）。
        frequency: 期種（"DAILY", "MONTHLY", "QUARTERLY", "ANNUAL" 等）。
        category_ja: カテゴリ（日本語）。
        last_update: 最終更新日。
        values: 観測値のリスト（日付順）。
    """
    code: str
    name_ja: str
    name_en: str
    unit_ja: str
    unit_en: str
    frequency: str
    category_ja: str
    last_update: Optional[date]
    values: list[SeriesValue] = field(default_factory=list)

    @classmethod
    def from_api_dict(cls, data: dict) -> "Series":
        """APIレスポンスの SERIES 要素から Series オブジェクトを生成する。

        Args:
            data: APIレスポンスの SERIES[i] に相当する dict。

        Returns:
            Series インスタンス。
        """
        values_obj = data.get("VALUES", {})
        dates: list[str] = values_obj.get("SURVEY_DATES", [])
        raw_values: list = values_obj.get("VALUES", [])

        values = []
        for d_str, v in zip(dates, raw_values):
            try:
                obs_date = _parse_api_date(d_str)
            except ValueError:
                obs_date = None  # type: ignore[assignment]
            values.append(SeriesValue(
                observation_date=obs_date,
                value=float(v) if v is not None else None,
            ))

        last_update_str = data.get("LAST_UPDATE", "")
        try:
            last_update = _parse_api_date(last_update_str) if last_update_str else None
        except ValueError:
            last_update = None

        return cls(
            code=data.get("SERIES_CODE", ""),
            name_ja=data.get("NAME_OF_TIME_SERIES_J", ""),
            name_en=data.get("NAME_OF_TIME_SERIES", ""),
            unit_ja=data.get("UNIT_J", ""),
            unit_en=data.get("UNIT", ""),
            frequency=data.get("FREQUENCY", ""),
            category_ja=data.get("CATEGORY_J", ""),
            last_update=last_update,
            values=values,
        )

    def to_records(self) -> list[dict]:
        """観測値をレコードのリストに変換する（pandas DataFrame 作成に便利）。

        Returns:
            [{"date": date, "value": float | None, "code": str, "name": str}, ...] 形式のリスト。
        """
        return [
            {
                "date": sv.observation_date,
                "value": sv.value,
                "code": self.code,
                "name": self.name_ja,
                "unit": self.unit_ja,
            }
            for sv in self.values
        ]

    def latest_value(self) -> Optional[SeriesValue]:
        """欠損でない最新の観測値を返す。データがなければ None。"""
        non_null = [sv for sv in self.values if sv.value is not None]
        return non_null[-1] if non_null else None


# ---------------------------------------------------------------------------
# メタデータ
# ---------------------------------------------------------------------------

@dataclass
class SeriesMeta:
    """系列のメタ情報（コードと名称のペア）。

    Attributes:
        code: 系列コード。
        name_ja: 系列名（日本語）。
        name_en: 系列名（英語）。
        db: DB名。
        frequency: 期種。
        start_date: 収録開始日。
        end_date: 収録終了日。
    """
    code: str
    name_ja: str
    name_en: str
    db: str
    frequency: str
    start_date: Optional[date]
    end_date: Optional[date]

    @classmethod
    def from_api_dict(cls, data: dict, db: str = "") -> "SeriesMeta":
        """APIレスポンスのメタデータ要素から SeriesMeta オブジェクトを生成する。"""
        def _safe_date(s: str) -> Optional[date]:
            try:
                return _parse_api_date(s) if s else None
            except ValueError:
                return None

        return cls(
            code=data.get("SERIES_CODE", ""),
            name_ja=data.get("NAME_OF_TIME_SERIES_J", ""),
            name_en=data.get("NAME_OF_TIME_SERIES", ""),
            db=db,
            frequency=data.get("FREQUENCY", ""),
            start_date=_safe_date(data.get("START_DATE", "")),
            end_date=_safe_date(data.get("END_DATE", "")),
        )


# ---------------------------------------------------------------------------
# ユーティリティ
# ---------------------------------------------------------------------------

def _parse_api_date(date_str: str | int) -> date:
    """日銀 API の日付文字列/整数を date オブジェクトに変換する。

    対応フォーマット:
        - YYYYMMDD（日次）
        - YYYYMM（月次・四半期の場合は月初）
        - YYYY（年次・年度は1月1日として扱う）

    Args:
        date_str: APIが返す日付文字列または整数。

    Returns:
        date オブジェクト。

    Raises:
        ValueError: フォーマットが対応外の場合。
    """
    s = str(date_str).strip()
    if len(s) == 8:
        return date(int(s[:4]), int(s[4:6]), int(s[6:8]))
    elif len(s) == 6:
        return date(int(s[:4]), int(s[4:6]), 1)
    elif len(s) == 4:
        return date(int(s), 1, 1)
    else:
        raise ValueError(f"対応外の日付フォーマット: {date_str!r}")
