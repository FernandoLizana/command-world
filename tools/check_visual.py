"""Visual layer smoke checks."""

from __future__ import annotations

import json
import re
from pathlib import Path

from app import create_app
from app.models import Project

GAME = Path("app/static/game")


def main() -> None:
    print("terrain", (GAME / "tiles/terrain.png").stat().st_size)
    print("buildings", len(list((GAME / "buildings").glob("*.png"))))
    print("units", len(list((GAME / "units").glob("*.png"))))
    print("effects", len(list((GAME / "effects").glob("*.png"))))
    tiled = json.loads((GAME / "maps/empire_map.json").read_text(encoding="utf-8"))
    print("map", tiled["width"], "x", tiled["height"], [L["name"] for L in tiled["layers"]])

    app = create_app()
    client = app.test_client()
    with app.app_context():
        for p in Project.query.all():
            print("city", p.slug, p.map_x, p.map_y, p.building_type, "lv", p.level)

    login = client.get("/login")
    token = re.search(
        r'name="csrf_token"[^>]*value="([^"]+)"', login.data.decode("utf-8")
    ).group(1)
    client.post("/login", data={"username": "admin", "password": "admin", "csrf_token": token})

    home = client.get("/")
    html = home.get_data(as_text=True)
    print("MAP_PAGE", home.status_code, "assets" in html, "empire-map.js" in html)
    payload = client.get("/api/map").get_json()
    print("API", len(payload["cities"]), payload.get("visual"))
    first = (payload.get("cities") or [{}])[0]
    if first:
        print("first", first.get("slug"), first.get("x"), first.get("activity"))
        slug = first.get("slug")
        if slug:
            city_page = client.get(f"/projects/{slug}/city")
            print("CITY_PAGE", city_page.status_code, "city-map" in city_page.get_data(as_text=True))
            city_api = client.get(f"/api/projects/{slug}/city").get_json() or {}
            print("CITY_API", [m["key"] for m in city_api.get("modules") or []])
    print("png", client.get("/static/game/tiles/terrain.png").status_code)
    print("json", client.get("/static/game/maps/empire_map.json").status_code)
    print("OK")


if __name__ == "__main__":
    main()
