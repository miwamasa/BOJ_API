"""
boj_client.exceptions
=====================
日銀API クライアントで使用するカスタム例外クラス群。

HTTPエラー、APIエラー、バリデーションエラーを明確に区別することで、
呼び出し側での適切なエラーハンドリングを支援する。
"""


class BOJClientError(Exception):
    """boj_client パッケージの基底例外クラス。

    全ての boj_client 例外はこのクラスを継承するため、
    ``except BOJClientError`` で一括捕捉が可能。
    """


class BOJAPIError(BOJClientError):
    """日銀 API が非200ステータスを返した場合の例外。

    Attributes:
        status (int): APIレスポンスの STATUS コード（400 / 500 / 503 等）。
        message_id (str): API が返す MESSAGEID（例: "M181010E"）。
        message (str): API が返す MESSAGE（日本語エラー文）。
    """

    def __init__(self, status: int, message_id: str, message: str) -> None:
        self.status = status
        self.message_id = message_id
        self.message = message
        super().__init__(
            f"BOJ API エラー [STATUS={status}, ID={message_id}]: {message}"
        )


class BOJParameterError(BOJClientError):
    """パラメータのバリデーションエラー（クライアント側でのチェック失敗）。

    APIにリクエストを送る前に検出できるパラメータ不正を表す。
    例: 異なる期種の系列コードを混在させた場合など。
    """


class BOJNetworkError(BOJClientError):
    """ネットワーク層のエラー（タイムアウト・接続失敗など）。

    Attributes:
        original (Exception): 元の例外オブジェクト。
    """

    def __init__(self, message: str, original: Exception | None = None) -> None:
        self.original = original
        super().__init__(message)


class BOJNoDataError(BOJClientError):
    """APIは正常終了したが、該当するデータが存在しない場合の例外。

    MESSAGE_ID が ``M181030I`` の場合に送出される。
    """
