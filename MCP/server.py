"""
日本銀行 時系列統計データ API - MCP サーバー
https://www.stat-search.boj.or.jp

提供ツール:
  - boj_get_metadata   : DB内の系列一覧・メタ情報を取得
  - boj_get_data_code  : 系列コード指定でデータを取得
  - boj_get_data_layer : 階層指定でデータを取得
"""

import asyncio
import time
import json
from typing import Any

import httpx
from mcp.server import Server, NotificationOptions
from mcp.server.models import InitializationOptions
from mcp.server.stdio import stdio_server
from mcp.types import (
    Tool,
    TextContent,
    INVALID_PARAMS,
    INTERNAL_ERROR,
)
from pydantic import AnyUrl

# ─── 定数 ────────────────────────────────────────────────────────────────────
BASE_URL = "https://www.stat-search.boj.or.jp/api/v1"
DEFAULT_LANG = "jp"
REQUEST_INTERVAL = 1.0  # 高頻度アクセス対策（秒）

# ─── サーバー初期化 ───────────────────────────────────────────────────────────
app = Server("boj-api")

# ─── ヘルパー ─────────────────────────────────────────────────────────────────

async def _fetch(endpoint: str, params: dict) -> dict:
    """
    日銀APIへHTTP GETリクエストを送る。
    エラー時は例外を raise する。
    """
    params = {k: v for k, v in params.items() if v is not None}
    params.setdefault("format", "json")
    params.setdefault("lang", DEFAULT_LANG)

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(f"{BASE_URL}/{endpoint}", params=params)
        response.raise_for_status()
        data = response.json()

    status = data.get("STATUS")
    if status == 400:
        raise ValueError(f"パラメータエラー [{data.get('MESSAGEID')}]: {data.get('MESSAGE')}")
    if status in (500, 503):
        raise RuntimeError(f"サーバーエラー [{data.get('MESSAGEID')}]: {data.get('MESSAGE')}")

    return data


def _to_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)


# ─── ツール定義 ───────────────────────────────────────────────────────────────

@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="boj_get_metadata",
            description=(
                "日銀統計DBのメタ情報（系列コード・名称・頻度・収録期間・単位）を取得する。\n"
                "系列コードが不明なときや、DB内にどんなデータがあるか調べるときに使う。\n\n"
                "主要DBコード例:\n"
                "  FM01=無担保コールO/N, FM08=外国為替, FM09=実効為替レート\n"
                "  MD01=マネタリーベース, MD02=マネーストック\n"
                "  IR01=基準貸付利率, IR04=貸出約定平均金利\n"
                "  PR01=企業物価(CGPI), PR02=企業向けサービス価格(SPPI)\n"
                "  CO=短観, FF=資金循環, BP01=国際収支, BIS=BIS統計"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "db": {
                        "type": "string",
                        "description": "DBコード（例: 'FM08', 'CO', 'MD02'）",
                    },
                    "lang": {
                        "type": "string",
                        "enum": ["jp", "en"],
                        "description": "言語（デフォルト: jp）",
                        "default": "jp",
                    },
                },
                "required": ["db"],
            },
        ),
        Tool(
            name="boj_get_data_code",
            description=(
                "系列コードを指定して時系列データを取得する（コードAPI）。\n"
                "系列コードが分かっている場合はこちらを優先。\n"
                "同一リクエスト内の系列は全て同じ期種（日次/月次/四半期など）であること。\n\n"
                "ページネーション: レスポンスに NEXTPOSITION が含まれる場合は\n"
                "start_position に渡して続きを取得できる。"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "db": {
                        "type": "string",
                        "description": "DBコード（例: 'FM08', 'CO'）",
                    },
                    "codes": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "系列コードのリスト（最大250件・同一期種）",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "開始期 (例: 月次='202401', 四半期='202401', 年='2024')",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "終了期（省略時は最新期まで）",
                    },
                    "lang": {
                        "type": "string",
                        "enum": ["jp", "en"],
                        "default": "jp",
                    },
                    "start_position": {
                        "type": "integer",
                        "description": "ページネーション用開始位置（NEXTPOSITIONの値を渡す）",
                    },
                },
                "required": ["db", "codes"],
            },
        ),
        Tool(
            name="boj_get_data_layer",
            description=(
                "階層（カテゴリ）を指定して時系列データを取得する（階層API）。\n"
                "系列コードが不明で、カテゴリ単位でまとめて取得したい場合に使う。\n\n"
                "制限: 抽出系列数が1,250件を超えるとエラー。\n"
                "layer='*' は全件取得だが件数超過に注意。\n\n"
                "frequency値: CY=暦年, FY=年度, Q=四半期, M=月次, W=週次, D=日次"
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "db": {
                        "type": "string",
                        "description": "DBコード",
                    },
                    "frequency": {
                        "type": "string",
                        "enum": ["CY", "FY", "CH", "FH", "Q", "M", "W", "D"],
                        "description": "期種",
                    },
                    "layer": {
                        "type": "string",
                        "description": "階層情報（例: '1,1,1' または '*'）",
                    },
                    "start_date": {
                        "type": "string",
                        "description": "開始期",
                    },
                    "end_date": {
                        "type": "string",
                        "description": "終了期",
                    },
                    "lang": {
                        "type": "string",
                        "enum": ["jp", "en"],
                        "default": "jp",
                    },
                    "start_position": {
                        "type": "integer",
                        "description": "ページネーション用開始位置",
                    },
                },
                "required": ["db", "frequency", "layer"],
            },
        ),
    ]


# ─── ツール実行 ───────────────────────────────────────────────────────────────

@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:

    try:
        if name == "boj_get_metadata":
            db = arguments.get("db")
            if not db:
                return [TextContent(type="text", text="エラー: db は必須です。")]
            data = await _fetch("getMetadata", {
                "db": db,
                "lang": arguments.get("lang", DEFAULT_LANG),
            })
            return [TextContent(type="text", text=_to_text(data))]

        elif name == "boj_get_data_code":
            db = arguments.get("db")
            codes = arguments.get("codes", [])
            if not db or not codes:
                return [TextContent(type="text", text="エラー: db と codes は必須です。")]
            params = {
                "db": db,
                "code": ",".join(codes),
                "lang": arguments.get("lang", DEFAULT_LANG),
                "startDate": arguments.get("start_date"),
                "endDate": arguments.get("end_date"),
                "startPosition": arguments.get("start_position"),
            }
            data = await _fetch("getDataCode", params)
            return [TextContent(type="text", text=_to_text(data))]

        elif name == "boj_get_data_layer":
            db = arguments.get("db")
            frequency = arguments.get("frequency")
            layer = arguments.get("layer")
            if not all([db, frequency, layer]):
                return [TextContent(type="text", text="エラー: db, frequency, layer は必須です。")]
            params = {
                "db": db,
                "frequency": frequency,
                "layer": layer,
                "lang": arguments.get("lang", DEFAULT_LANG),
                "startDate": arguments.get("start_date"),
                "endDate": arguments.get("end_date"),
                "startPosition": arguments.get("start_position"),
            }
            data = await _fetch("getDataLayer", params)
            return [TextContent(type="text", text=_to_text(data))]

        else:
            return [TextContent(type="text", text=f"未知のツール: {name}")]

    except ValueError as e:
        return [TextContent(type="text", text=f"パラメータエラー: {e}")]
    except httpx.HTTPStatusError as e:
        return [TextContent(type="text", text=f"HTTPエラー {e.response.status_code}: {e}")]
    except Exception as e:
        return [TextContent(type="text", text=f"エラー: {e}")]


# ─── エントリポイント ──────────────────────────────────────────────────────────

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="boj-api",
                server_version="0.1.0",
                capabilities=app.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
