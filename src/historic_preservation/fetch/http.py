"""A polite HTTP client: one request per host per MIN_INTERVAL_S, honest UA, retries."""

import time
from urllib.parse import urlsplit

import httpx

from historic_preservation.config import MIN_INTERVAL_S, USER_AGENT


class PoliteClient:
    def __init__(self, min_interval: float = MIN_INTERVAL_S, retries: int = 5):
        self.min_interval = min_interval
        self.retries = retries
        self._last: dict[str, float] = {}
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=120, follow_redirects=True
        )

    def _wait(self, host: str) -> None:
        elapsed = time.monotonic() - self._last.get(host, 0.0)
        if elapsed < self.min_interval:
            time.sleep(self.min_interval - elapsed)
        self._last[host] = time.monotonic()

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        host = urlsplit(url).netloc
        for attempt in range(self.retries):
            self._wait(host)
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code < 500 and resp.status_code != 429:
                    resp.raise_for_status()
                    return resp
            except httpx.TransportError:
                if attempt == self.retries - 1:
                    raise
            time.sleep(2**attempt * 5)
        resp.raise_for_status()
        return resp

    def get_json(self, url: str, params: dict | None = None) -> dict:
        data = self.get(url, params).json()
        # ArcGIS reports query errors as HTTP 200 with an "error" body.
        if isinstance(data, dict) and "error" in data:
            raise RuntimeError(f"{url}: {data['error']}")
        return data

    def close(self) -> None:
        self._client.close()
