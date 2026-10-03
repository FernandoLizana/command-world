"""Download Phaser locally so the map does not depend on a CDN."""

from __future__ import annotations

import urllib.request
from pathlib import Path

DEST = Path(__file__).resolve().parents[1] / "app" / "static" / "game" / "js" / "phaser.min.js"
URLS = [
    "https://cdn.jsdelivr.net/npm/phaser@3.80.1/dist/phaser.min.js",
    "https://unpkg.com/phaser@3.80.1/dist/phaser.min.js",
]


def main() -> None:
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists() and DEST.stat().st_size > 100000:
        print("already have", DEST, DEST.stat().st_size)
        return
    last_err = None
    for url in URLS:
        try:
            print("fetch", url)
            urllib.request.urlretrieve(url, DEST)
            print("saved", DEST, DEST.stat().st_size)
            return
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            print("fail", url, exc)
    raise SystemExit(f"could not download Phaser: {last_err}")


if __name__ == "__main__":
    main()
