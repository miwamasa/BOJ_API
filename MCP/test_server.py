"""
boj-mcp server.py の単体テスト
MCP プロトコルを介さず、内部の _fetch ヘルパーと
各ツールハンドラを直接呼び出して動作を検証する。

実行方法:
    pip install pytest pytest-asyncio httpx mcp
    pytest test_server.py -v
"""

import json
import pytest
import pytest_asyncio
import httpx
from unittest.mock import AsyncMock, patch, MagicMock

# テスト対象モジュールをインポート
import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).parent))
import server as srv


# ─── フィクスチャ・共通モック ─────────────────────────────────────────────────

SUCCESS_METADATA = {
    "STATUS": 200,
    "MESSAGE": "正常に終了しました。",
    "RESULTSET": [
        {
            "SERIES_CODE": "FXERM07",
            "NAME_OF_TIME_SERIES_J": "東京市場 ドル・円 スポット 17時時点/月中平均",
            "UNIT_J": "円/ドル",
            "FREQUENCY": "MONTHLY",
            "STARTDATE": "197301",
            "ENDDATE": "202412",
        }
    ],
}

SUCCESS_DATA_CODE = {
    "STATUS": 200,
    "MESSAGE": "正常に終了しました。",
    "NEXTPOSITION": None,
    "RESULTSET": [
        {
            "SERIES_CODE": "FXERM07",
            "NAME_OF_TIME_SERIES_J": "東京市場 ドル・円 スポット 17時時点/月中平均",
            "VALUES": {
                "SURVEY_DATES": [202401, 202402, 202403],
                "VALUES": [148.12, 150.23, 151.34],
            },
        }
    ],
}

ERROR_400 = {
    "STATUS": 400,
    "MESSAGEID": "M181010E",
    "MESSAGE": "パラメータ不正",
}

ERROR_500 = {
    "STATUS": 500,
    "MESSAGEID": "M181020E",
    "MESSAGE": "サーバー内部エラー",
}


def make_mock_response(json_data: dict, status_code: int = 200):
    """httpx.Response モックを生成する"""
    mock_resp = MagicMock(spec=httpx.Response)
    mock_resp.status_code = status_code
    mock_resp.json.return_value = json_data
    mock_resp.raise_for_status = MagicMock()  # 200系はそのまま
    return mock_resp


# ─── _fetch ヘルパーのテスト ──────────────────────────────────────────────────

class TestFetch:
    """_fetch() の正常系・異常系テスト"""

    @pytest.mark.asyncio
    async def test_fetch_success(self):
        """正常レスポンス（STATUS=200）が dict で返ること"""
        mock_resp = make_mock_response(SUCCESS_METADATA)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            result = await srv._fetch("getMetadata", {"db": "FM08"})

        assert result["STATUS"] == 200
        assert len(result["RESULTSET"]) == 1
        assert result["RESULTSET"][0]["SERIES_CODE"] == "FXERM07"

    @pytest.mark.asyncio
    async def test_fetch_status_400_raises_value_error(self):
        """STATUS=400 のとき ValueError が raise されること"""
        mock_resp = make_mock_response(ERROR_400)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(ValueError, match="パラメータエラー"):
                await srv._fetch("getDataCode", {"db": "FM08", "code": "INVALID"})

    @pytest.mark.asyncio
    async def test_fetch_status_500_raises_runtime_error(self):
        """STATUS=500 のとき RuntimeError が raise されること"""
        mock_resp = make_mock_response(ERROR_500)

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_resp):
            with pytest.raises(RuntimeError, match="サーバーエラー"):
                await srv._fetch("getMetadata", {"db": "FM08"})

    @pytest.mark.asyncio
    async def test_fetch_strips_none_params(self):
        """None 値のパラメータが HTTP リクエストに含まれないこと"""
        mock_resp = make_mock_response(SUCCESS_METADATA)
        captured_params = {}

        async def mock_get(url, params=None, **kwargs):
            captured_params.update(params or {})
            return mock_resp

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, side_effect=mock_get):
            await srv._fetch("getMetadata", {"db": "FM08", "startDate": None, "endDate": None})

        assert "startDate" not in captured_params
        assert "endDate" not in captured_params
        assert captured_params["db"] == "FM08"


# ─── boj_get_metadata ツールのテスト ─────────────────────────────────────────

class TestBojGetMetadata:
    """boj_get_metadata ツールハンドラのテスト"""

    @pytest.mark.asyncio
    async def test_returns_json_text(self):
        """正常系: JSON テキストが TextContent で返ること"""
        with patch.object(srv, "_fetch", new_callable=AsyncMock, return_value=SUCCESS_METADATA):
            result = await srv.call_tool("boj_get_metadata", {"db": "FM08"})

        assert len(result) == 1
        assert result[0].type == "text"
        parsed = json.loads(result[0].text)
        assert parsed["STATUS"] == 200

    @pytest.mark.asyncio
    async def test_missing_db_returns_error_text(self):
        """db 省略時にエラーメッセージが返ること（例外が外に出ないこと）"""
        result = await srv.call_tool("boj_get_metadata", {})

        assert len(result) == 1
        assert "エラー" in result[0].text

    @pytest.mark.asyncio
    async def test_api_400_returns_error_text(self):
        """APIが400を返したときエラーテキストが返ること"""
        with patch.object(srv, "_fetch", new_callable=AsyncMock, side_effect=ValueError("パラメータエラー")):
            result = await srv.call_tool("boj_get_metadata", {"db": "INVALID"})

        assert "パラメータエラー" in result[0].text


# ─── boj_get_data_code ツールのテスト ────────────────────────────────────────

class TestBojGetDataCode:
    """boj_get_data_code ツールハンドラのテスト"""

    @pytest.mark.asyncio
    async def test_single_code_success(self):
        """系列コード1件の正常取得"""
        with patch.object(srv, "_fetch", new_callable=AsyncMock, return_value=SUCCESS_DATA_CODE):
            result = await srv.call_tool(
                "boj_get_data_code",
                {"db": "FM08", "codes": ["FXERM07"], "start_date": "202401", "end_date": "202403"},
            )

        parsed = json.loads(result[0].text)
        assert parsed["STATUS"] == 200
        series = parsed["RESULTSET"][0]
        assert series["SERIES_CODE"] == "FXERM07"
        assert len(series["VALUES"]["VALUES"]) == 3

    @pytest.mark.asyncio
    async def test_multiple_codes_joined(self):
        """複数コードがカンマ結合でAPIに渡ること"""
        captured = {}

        async def mock_fetch(endpoint, params):
            captured.update(params)
            return SUCCESS_DATA_CODE

        with patch.object(srv, "_fetch", new_callable=AsyncMock, side_effect=mock_fetch):
            await srv.call_tool(
                "boj_get_data_code",
                {"db": "FM08", "codes": ["FXERM07", "FXERM08"]},
            )

        assert captured["code"] == "FXERM07,FXERM08"

    @pytest.mark.asyncio
    async def test_missing_codes_returns_error(self):
        """codes 省略時にエラーが返ること"""
        result = await srv.call_tool("boj_get_data_code", {"db": "FM08"})
        assert "エラー" in result[0].text

    @pytest.mark.asyncio
    async def test_pagination_param_passed(self):
        """start_position が startPosition としてAPIに渡ること"""
        captured = {}

        async def mock_fetch(endpoint, params):
            captured.update(params)
            return SUCCESS_DATA_CODE

        with patch.object(srv, "_fetch", new_callable=AsyncMock, side_effect=mock_fetch):
            await srv.call_tool(
                "boj_get_data_code",
                {"db": "FM08", "codes": ["FXERM07"], "start_position": 251},
            )

        assert captured.get("startPosition") == 251


# ─── boj_get_data_layer ツールのテスト ───────────────────────────────────────

class TestBojGetDataLayer:
    """boj_get_data_layer ツールハンドラのテスト"""

    @pytest.mark.asyncio
    async def test_success(self):
        """正常系: 階層指定でデータが返ること"""
        layer_data = {**SUCCESS_DATA_CODE, "PARAMETER": {"LAYER": "1,1,1", "FREQUENCY": "M"}}

        with patch.object(srv, "_fetch", new_callable=AsyncMock, return_value=layer_data):
            result = await srv.call_tool(
                "boj_get_data_layer",
                {"db": "FM08", "frequency": "M", "layer": "1,1,1"},
            )

        parsed = json.loads(result[0].text)
        assert parsed["STATUS"] == 200

    @pytest.mark.asyncio
    async def test_missing_frequency_returns_error(self):
        """frequency 省略時にエラーが返ること"""
        result = await srv.call_tool(
            "boj_get_data_layer",
            {"db": "FM08", "layer": "1,1,1"},
        )
        assert "エラー" in result[0].text

    @pytest.mark.asyncio
    async def test_correct_endpoint_called(self):
        """getDataLayer エンドポイントが呼ばれること"""
        captured = {}

        async def mock_fetch(endpoint, params):
            captured["endpoint"] = endpoint
            return SUCCESS_DATA_CODE

        with patch.object(srv, "_fetch", new_callable=AsyncMock, side_effect=mock_fetch):
            await srv.call_tool(
                "boj_get_data_layer",
                {"db": "CO", "frequency": "Q", "layer": "*"},
            )

        assert captured["endpoint"] == "getDataLayer"


# ─── 未知のツール名テスト ─────────────────────────────────────────────────────

class TestUnknownTool:
    @pytest.mark.asyncio
    async def test_unknown_tool_returns_message(self):
        """未登録ツール名のときにメッセージが返ること"""
        result = await srv.call_tool("unknown_tool", {})
        assert "未知のツール" in result[0].text
