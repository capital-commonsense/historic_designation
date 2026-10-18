"""A polite HTTP client: one request per host per MIN_INTERVAL_S, honest UA, retries."""

import time
from urllib.parse import urlsplit

import httpx

from historic_preservation.config import MIN_INTERVAL_S, USER_AGENT


# Hosts that ask for a slower pace than the default.
HOST_INTERVALS = {"www.courtlistener.com": 5.0}


class PoliteClient:
    def __init__(self, min_interval: float = MIN_INTERVAL_S, retries: int = 5):
        self.min_interval = min_interval
        self.retries = retries
        self._last: dict[str, float] = {}
        self._client = httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=120, follow_redirects=True
        )

    def _wait(self, host: str) -> None:
        interval = max(self.min_interval, HOST_INTERVALS.get(host, 0.0))
        elapsed = time.monotonic() - self._last.get(host, 0.0)
        if elapsed < interval:
            time.sleep(interval - elapsed)
        self._last[host] = time.monotonic()

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        host = urlsplit(url).netloc
        for attempt in range(self.retries):
            self._wait(host)
            delay = 2**attempt * 5
            try:
                resp = self._client.get(url, params=params)
                if resp.status_code < 500 and resp.status_code != 429:
                    resp.raise_for_status()
                    return resp
                if resp.headers.get("Retry-After", "").isdigit():
                    delay = max(delay, int(resp.headers["Retry-After"]))
            except httpx.TransportError:
                if attempt == self.retries - 1:
                    raise
            time.sleep(delay)
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
