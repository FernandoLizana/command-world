"""Smoke test: imports, seed, routes. Run with venv python."""

from __future__ import annotations

import re
import sys

from app import create_app
from app.ai.service import AIService
from app.models import Project


def csrf(html: bytes) -> str:
    text = html.decode("utf-8", errors="replace")
    m = re.search(r'name="csrf_token"[^>]*value="([^"]+)"', text)
    if not m:
        m = re.search(r'value="([^"]+)"[^>]*name="csrf_token"', text)
    if not m:
        raise SystemExit("csrf token not found")
    return m.group(1)


def main() -> int:
    app = create_app()
    client = app.test_client()
    errors: list[str] = []

    with app.app_context():
        n = Project.query.count()
        print(f"projects={n}")
        ai = AIService.from_app()
        print(f"ai_available={ai.is_available()}")

    login_page = client.get("/login")
    token = csrf(login_page.data)
    logged = client.post(
        "/login",
        data={"username": "admin", "password": "admin", "csrf_token": token},
        follow_redirects=False,
    )
    print(f"login_status={logged.status_code} loc={logged.headers.get('Location')}")
    if logged.status_code not in (302, 303):
        errors.append("login failed")

    routes = [
        "/",
        "/projects",
        "/projects/new",
        "/missions",
        "/council",
        "/tech-tree",
        "/events",
        "/archive",
        "/opportunities",
        "/issues",
        "/settings",
        "/api/projects",
        "/api/map",
        "/api/events",
        "/api/missions",
        "/api/empire/status",
        "/api/advisor/status",
    ]
    for path in routes:
        r = client.get(path)
        ok = r.status_code == 200
        print(f"{r.status_code} {path} bytes={len(r.data)}")
        if not ok:
            errors.append(f"{path} -> {r.status_code}")
        if path == "/" and b"empire-map" not in r.data and b"Phaser" not in r.data:
            # map host must exist
            if b'id="empire-map"' not in r.data:
                errors.append("map container missing")
        if path == "/api/map":
            data = r.get_json() or {}
            cities = data.get("cities") or []
            print(f"  map cities={len(cities)}")
            if len(cities) < 1:
                print("  map empty (new world)")

    if errors:
        print("FAIL")
        for e in errors:
            print(" -", e)
        return 1
    print("OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
