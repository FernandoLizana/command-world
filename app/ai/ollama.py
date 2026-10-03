"""Ollama HTTP client. Timeouts are mandatory; failures never freeze the web request."""

from __future__ import annotations

import logging
import time

import requests

logger = logging.getLogger(__name__)

_STATUS_TTL = 20.0
_status_cache: dict = {"ts": 0.0, "ok": False, "url": ""}


class OllamaClient:
    def __init__(self, url: str, model: str, timeout: int, enabled: bool) -> None:
        self.url = url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.enabled = enabled

    def available(self) -> bool:
        if not self.enabled:
            return False
        now = time.monotonic()
        if _status_cache["url"] == self.url and now - _status_cache["ts"] < _STATUS_TTL:
            return bool(_status_cache["ok"])
        ok = False
        try:
            response = requests.get(f"{self.url}/api/tags", timeout=0.6)
            ok = response.status_code == 200
        except requests.RequestException:
            ok = False
        _status_cache.update({"ts": now, "ok": ok, "url": self.url})
        if not ok:
            logger.info("Ollama not reachable at %s", self.url)
        return ok

    def generate(self, prompt: str, system: str | None = None) -> str:
        if not self.enabled:
            raise RuntimeError("Ollama disabled")
        payload = {
            "model": self.model,
            "prompt": prompt if not system else f"{system}\n\n{prompt}",
            "stream": False,
            "options": {"temperature": 0.3},
        }
        try:
            response = requests.post(
                f"{self.url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()
            return (data.get("response") or "").strip()
        except requests.Timeout as exc:
            logger.warning("Ollama timeout after %ss", self.timeout)
            raise RuntimeError("Ollama timeout") from exc
        except requests.RequestException as exc:
            logger.warning("Ollama error: %s", exc)
            raise RuntimeError("Ollama unavailable") from exc
