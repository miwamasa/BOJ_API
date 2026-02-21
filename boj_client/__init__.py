"""BOJ (Bank of Japan) Client Library

A Python library for accessing Bank of Japan's Time-Series Data API.
"""

from boj_client.client import BOJClient
from boj_client.models import Series, SeriesValue, SeriesMeta
from boj_client.exceptions import (
    BOJClientError,
    BOJAPIError,
    BOJParameterError,
    BOJNetworkError,
    BOJNoDataError,
)

__version__ = "0.1.0"
__all__ = [
    "BOJClient",
    "Series",
    "SeriesValue",
    "SeriesMeta",
    "BOJClientError",
    "BOJAPIError",
    "BOJParameterError",
    "BOJNetworkError",
    "BOJNoDataError",
]
