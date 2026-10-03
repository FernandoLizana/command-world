"""Generate original 32x32 pixel-art tiles, buildings, units and Tiled maps.

Uses only the Python stdlib (PNG via zlib). Re-run:

    python tools/generate_pixel_assets.py
"""

from __future__ import annotations

import json
import math
import random
import struct
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GAME = ROOT / "app" / "static" / "game"
TILE = 32
MAP_W, MAP_H = 80, 52


def chunk(tag: bytes, data: bytes) -> bytes:
    crc = zlib.crc32(tag + data) & 0xFFFFFFFF
    return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)


def save_png(path: Path, w: int, h: int, pixels: list[tuple[int, int, int, int]]) -> None:
    raw = bytearray()
    for y in range(h):
        raw.append(0)
        for x in range(w):
            r, g, b, a = pixels[y * w + x]
            raw.extend((r, g, b, a))
    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(bytes(raw), 9)) + chunk(b"IEND", b"")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(png)


class C:
    def __init__(self, w: int, h: int) -> None:
        self.w, self.h = w, h
        self.p = [(0, 0, 0, 0)] * (w * h)

    def put(self, x: int, y: int, c: tuple[int, int, int, int]) -> None:
        if 0 <= x < self.w and 0 <= y < self.h and c[3] > 0:
            self.p[y * self.w + x] = c

    def rect(self, x: int, y: int, w: int, h: int, c: tuple[int, int, int, int]) -> None:
        for j in range(h):
            for i in range(w):
                self.put(x + i, y + j, c)

    def dither(self, x: int, y: int, w: int, h: int, a, b) -> None:
        for j in range(h):
            for i in range(w):
                self.put(x + i, y + j, a if (i + j) % 2 == 0 else b)

    def pix(self, pts, c) -> None:
        for x, y in pts:
            self.put(x, y, c)

    def blit(self, other: "C", ox: int, oy: int) -> None:
        for y in range(other.h):
            for x in range(other.w):
                self.put(ox + x, oy + y, other.p[y * other.w + x])

    def save(self, path: Path) -> None:
        save_png(path, self.w, self.h, self.p)


# --- palette ---
G1, G2, G3, G4 = (34, 84, 38, 255), (46, 112, 48, 255), (28, 64, 32, 255), (72, 140, 62, 255)
FL = (186, 168, 64, 255)
DIRT, DIRT2 = (110, 84, 58, 255), (138, 106, 70, 255)
ROAD, ROAD_E, ROAD_H = (196, 166, 110, 255), (92, 64, 40, 255), (214, 190, 130, 255)
WAT, WAT2, WAT3, DEEP = (22, 74, 118, 255), (36, 110, 150, 255), (50, 140, 170, 255), (14, 48, 78, 255)
SHORE = (72, 120, 90, 255)
MTN, MTN2, SNOW = (92, 92, 108, 255), (120, 120, 136, 255), (220, 224, 230, 255)
ROCK = (70, 70, 78, 255)
TREE, TREE2, TRUNK = (22, 64, 28, 255), (36, 92, 40, 255), (86, 58, 36, 255)
URBAN, URBAN2 = (78, 82, 90, 255), (110, 114, 122, 255)
TECH, TECH2, CYAN = (32, 72, 74, 255), (48, 104, 108, 255), (94, 234, 212, 255)
FOG = (18, 24, 28, 90)
GOLD, GOLD2 = (201, 162, 39, 255), (232, 197, 71, 255)
PURP = (140, 110, 210, 255)
RED = (200, 70, 70, 255)
SKIN = (220, 180, 140, 255)
HAIR = (40, 32, 28, 255)
OUT = (16, 18, 16, 255)


def grass_tile(variant: int = 0) -> C:
    t = C(TILE, TILE)
    t.rect(0, 0, TILE, TILE, G1)
    for y in range(TILE):
        for x in range(TILE):
            n = (x * 7 + y * 13 + variant * 19) % 11
            if n < 3:
                t.put(x, y, G2)
            elif n == 4:
                t.put(x, y, G3)
    if variant == 2:
        for x, y in ((4, 8), (12, 20), (22, 6), (18, 26), (7, 24)):
            t.put(x, y, FL)
            t.put(x, y - 1, G4)
    if variant == 3:
        t.rect(10, 10, 12, 8, DIRT)
    return t


def dirt_tile() -> C:
    t = C(TILE, TILE)
    t.rect(0, 0, TILE, TILE, DIRT)
    t.dither(2, 2, 28, 28, DIRT, DIRT2)
    return t


def road_tile(kind: str) -> C:
    t = grass_tile(1)
    if kind in {"h", "x", "c"}:
        t.rect(0, 11, 32, 10, ROAD_E)
        t.rect(0, 12, 32, 8, ROAD)
        t.rect(0, 15, 32, 2, ROAD_H)
    if kind in {"v", "x", "c"}:
        t.rect(11, 0, 10, 32, ROAD_E)
        t.rect(12, 0, 8, 32, ROAD)
        t.rect(15, 0, 2, 32, ROAD_H)
    if kind == "c":
        t.rect(11, 11, 10, 10, ROAD)
    return t


def water_tile(frame: int = 0) -> C:
    t = C(TILE, TILE)
    t.rect(0, 0, TILE, TILE, WAT if frame == 0 else WAT2)
    for i in range(0, 32, 4):
        y = 6 + ((i + frame * 4) % 12)
        t.rect(i, y, 3, 1, WAT3)
        t.rect((i + 10) % 32, (y + 9) % 28 + 2, 4, 1, DEEP)
    return t


def shore_tile() -> C:
    t = grass_tile(0)
    t.rect(0, 18, 32, 14, WAT)
    t.rect(0, 16, 32, 3, SHORE)
    return t


def mountain_tile(peak: bool = False) -> C:
    t = grass_tile(0)
    t.rect(4, 18, 24, 12, MTN)
    for x in range(8, 24):
        h = 14 - abs(x - 16)
        for y in range(18 - h, 18):
            t.put(x, y, MTN2 if y > 18 - h // 2 else MTN)
    if peak:
        t.rect(14, 4, 6, 4, SNOW)
        t.put(16, 3, SNOW)
    t.rect(6, 26, 20, 4, ROCK)
    return t


def tree_tile(dense: bool = False) -> C:
    t = grass_tile(1)
    t.rect(14, 20, 4, 10, TRUNK)
    t.rect(8, 10, 16, 14, TREE)
    t.rect(10, 6, 12, 8, TREE2)
    if dense:
        t.rect(2, 14, 10, 10, TREE)
        t.rect(20, 16, 10, 10, TREE2)
        t.rect(6, 22, 3, 8, TRUNK)
    t.put(12, 8, G4)
    return t


def urban_tile() -> C:
    t = C(TILE, TILE)
    t.rect(0, 0, TILE, TILE, URBAN)
    t.dither(0, 0, TILE, TILE, URBAN, URBAN2)
    t.rect(4, 4, 10, 10, (50, 54, 60, 255))
    t.rect(18, 8, 8, 16, (60, 64, 72, 255))
    t.put(7, 7, GOLD)
    return t


def tech_tile() -> C:
    t = C(TILE, TILE)
    t.rect(0, 0, TILE, TILE, TECH)
    t.rect(2, 2, 28, 28, TECH2)
    t.rect(6, 6, 20, 4, CYAN)
    t.rect(14, 4, 4, 20, (20, 40, 44, 255))
    t.put(8, 16, CYAN)
    t.put(24, 20, GOLD)
    return t


def fog_tile() -> C:
    t = C(TILE, TILE)
    t.rect(0, 0, TILE, TILE, FOG)
    for i in range(0, 32, 5):
        t.rect(i, (i * 3) % 32, 4, 4, (30, 40, 48, 70))
    return t


def bush_tile() -> C:
    t = grass_tile(0)
    t.rect(6, 16, 20, 10, TREE)
    t.rect(10, 12, 12, 8, TREE2)
    return t


def sand_tile() -> C:
    t = C(TILE, TILE)
    t.rect(0, 0, TILE, TILE, (168, 148, 96, 255))
    t.dither(0, 0, 32, 32, (168, 148, 96, 255), (186, 166, 110, 255))
    return t


TILE_FNS = [
    lambda: grass_tile(0),
    lambda: grass_tile(1),
    lambda: grass_tile(2),
    dirt_tile,
    sand_tile,
    lambda: road_tile("h"),
    lambda: road_tile("v"),
    lambda: road_tile("x"),
    lambda: road_tile("c"),
    lambda: water_tile(0),
    lambda: water_tile(1),
    shore_tile,
    lambda: mountain_tile(False),
    lambda: mountain_tile(True),
    lambda: tree_tile(False),
    lambda: tree_tile(True),
    urban_tile,
    tech_tile,
    fog_tile,
    bush_tile,
    lambda: grass_tile(3),
    lambda: road_tile("h"),
    lambda: water_tile(0),
    lambda: tree_tile(True),
]

TILE_NAMES = [
    "grass_a", "grass_b", "grass_flower", "dirt", "sand",
    "road_h", "road_v", "road_x", "road_c",
    "water_a", "water_b", "shore",
    "mountain", "mountain_peak", "tree", "forest",
    "urban", "tech", "fog", "bush",
    "grass_patch", "road_h2", "water_a2", "forest2",
]


def build_tileset() -> Path:
    cols = 8
    rows = math.ceil(len(TILE_FNS) / cols)
    sheet = C(cols * TILE, rows * TILE)
    for i, fn in enumerate(TILE_FNS):
        sheet.blit(fn(), (i % cols) * TILE, (i // cols) * TILE)
    path = GAME / "tiles" / "terrain.png"
    sheet.save(path)
    return path


# --- buildings 64x80 ---
BW, BH = 64, 80


def _outline(c: C, color=OUT) -> None:
    copy = c.p[:]
    for y in range(c.h):
        for x in range(c.w):
            if copy[y * c.w + x][3] == 0:
                for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    nx, ny = x + dx, y + dy
                    if 0 <= nx < c.w and 0 <= ny < c.h and copy[ny * c.w + nx][3] > 0:
                        c.put(x, y, color)
                        break


def building_command(level: int) -> C:
    c = C(BW, BH)
    base = 18 + min(level, 5) * 4
    c.rect(8, 50, 48, 18, (90, 74, 48, 255))
    c.rect(12, 38, 40, 16, (120, 96, 58, 255))
    c.rect(28, 58, 8, 10, (40, 28, 16, 255))
    if level >= 1:
        c.rect(16, 22, 14, 20, (140, 110, 60, 255))
        c.rect(18, 10, 10, 14, GOLD)
        c.rect(20, 4, 6, 8, GOLD2)
    if level >= 2:
        c.rect(36, 18, 14, 24, (130, 100, 55, 255))
        c.rect(40, 8, 6, 12, GOLD)
    if level >= 3:
        c.rect(6, 44, 8, 24, (80, 64, 40, 255))
        c.rect(50, 44, 8, 24, (80, 64, 40, 255))
    if level >= 4:
        c.rect(22, 30, 20, 10, (160, 130, 70, 255))
        for i in range(3):
            c.put(24 + i * 6, 32, (80, 180, 220, 255))
    if level >= 5:
        c.rect(30, 0, 4, 10, GOLD)
        c.rect(28, 0, 8, 3, RED)
        c.rect(10, 48, 4, 4, GOLD2)
        c.rect(50, 48, 4, 4, GOLD2)
    _outline(c)
    return c


def building_fortress(level: int) -> C:
    c = C(BW, BH)
    c.rect(10, 48, 44, 20, TECH)
    c.rect(14, 36, 36, 16, TECH2)
    c.rect(30, 20, 4, 18, (20, 30, 34, 255))
    c.rect(28, 8, 8, 14, CYAN)
    if level >= 2:
        c.rect(8, 28, 10, 36, (40, 60, 66, 255))
        c.rect(46, 28, 10, 36, (40, 60, 66, 255))
    if level >= 3:
        c.rect(18, 24, 28, 8, (20, 40, 44, 255))
        for i in range(4):
            c.rect(20 + i * 7, 26, 4, 4, CYAN if i % 2 == 0 else GOLD)
    if level >= 4:
        c.rect(22, 12, 6, 10, CYAN)
        c.rect(36, 10, 6, 12, CYAN)
    if level >= 5:
        c.rect(4, 40, 6, 28, TECH2)
        c.rect(54, 40, 6, 28, TECH2)
        c.put(32, 6, GOLD2)
    _outline(c)
    return c


def building_hospital(level: int) -> C:
    c = C(BW, BH)
    c.rect(12, 42, 40, 24, (220, 220, 210, 255))
    c.rect(16, 28, 32, 16, (236, 236, 228, 255))
    c.rect(28, 14, 8, 16, (200, 80, 80, 255))
    c.rect(24, 18, 16, 6, (200, 80, 80, 255))
    c.rect(8, 58, 12, 10, TREE2)
    c.rect(46, 58, 12, 10, TREE2)
    if level >= 2:
        c.rect(6, 46, 10, 20, (210, 210, 200, 255))
    if level >= 3:
        c.rect(48, 46, 10, 20, (210, 210, 200, 255))
    if level >= 4:
        c.rect(20, 36, 6, 6, (120, 180, 200, 255))
        c.rect(38, 36, 6, 6, (120, 180, 200, 255))
    if level >= 5:
        c.rect(24, 8, 16, 8, (236, 236, 228, 255))
    _outline(c)
    return c


def building_sanctuary(level: int) -> C:
    c = C(BW, BH)
    c.rect(18, 48, 28, 20, (70, 50, 110, 255))
    for r, col in ((18, (90, 70, 140, 255)), (12, PURP), (7, (200, 180, 255, 255))):
        c.rect(32 - r, 40 - r, r * 2, r * 2, col)
    c.rect(30, 8, 4, 16, GOLD)
    if level >= 2:
        c.rect(10, 50, 8, 18, (60, 40, 100, 255))
        c.rect(46, 50, 8, 18, (60, 40, 100, 255))
    if level >= 3:
        c.rect(22, 30, 20, 6, GOLD2)
    if level >= 4:
        c.put(20, 22, GOLD)
        c.put(44, 22, GOLD)
    if level >= 5:
        c.rect(28, 2, 8, 6, (240, 230, 255, 255))
    _outline(c)
    return c


def building_village(level: int) -> C:
    c = C(BW, BH)
    def house(x, y, roof, wall):
        c.rect(x, y + 10, 16, 12, wall)
        c.rect(x + 2, y, 12, 12, roof)
        c.rect(x + 6, y + 14, 4, 8, (40, 28, 16, 255))
    house(8, 48, (180, 70, 60, 255), (210, 190, 150, 255))
    house(28, 44, (60, 110, 160, 255), (220, 210, 180, 255))
    if level >= 2:
        house(42, 50, (70, 140, 80, 255), (200, 185, 150, 255))
    if level >= 3:
        house(18, 32, (160, 100, 50, 255), (230, 220, 190, 255))
    if level >= 4:
        c.rect(4, 62, 56, 6, ROAD)
    if level >= 5:
        c.rect(30, 20, 6, 14, (80, 80, 90, 255))
        c.rect(28, 16, 10, 6, GOLD)
    _outline(c)
    return c


def building_lab(level: int) -> C:
    c = C(BW, BH)
    c.rect(14, 46, 36, 22, (40, 70, 64, 255))
    c.rect(18, 30, 28, 18, (70, 160, 130, 255))
    c.rect(26, 12, 12, 20, (160, 230, 190, 255))
    c.rect(30, 4, 4, 10, CYAN)
    if level >= 2:
        c.rect(8, 40, 10, 28, (36, 60, 56, 255))
    if level >= 3:
        c.rect(46, 38, 10, 30, (36, 60, 56, 255))
        c.rect(48, 20, 6, 18, (120, 220, 180, 255))
    if level >= 4:
        for i in range(3):
            c.rect(20 + i * 8, 34, 5, 5, CYAN)
    if level >= 5:
        c.rect(22, 8, 20, 6, GOLD)
    _outline(c)
    return c


def building_generic(kind: str, accent) -> C:
    c = C(48, 48)
    c.rect(8, 24, 32, 18, (70, 70, 78, 255))
    c.rect(12, 12, 24, 16, accent)
    if kind == "tower":
        c.rect(20, 2, 8, 18, accent)
    elif kind == "market":
        c.rect(10, 18, 28, 8, GOLD)
        c.rect(14, 28, 6, 10, (80, 50, 20, 255))
    elif kind == "workshop":
        c.rect(16, 8, 16, 10, DIRT2)
        c.put(22, 10, GOLD)
    elif kind == "barracks":
        c.rect(10, 10, 28, 12, (80, 90, 70, 255))
    elif kind == "datacenter":
        c.rect(14, 8, 20, 16, TECH2)
        c.rect(16, 10, 4, 4, CYAN)
        c.rect(28, 10, 4, 4, CYAN)
    elif kind == "library":
        c.rect(14, 8, 20, 16, (120, 90, 50, 255))
    elif kind == "hospital":
        c.rect(20, 6, 8, 14, RED)
        c.rect(16, 10, 16, 6, RED)
    elif kind == "house":
        c.rect(14, 14, 20, 16, (210, 190, 150, 255))
        c.rect(16, 6, 16, 12, (160, 70, 50, 255))
    elif kind == "warehouse":
        c.rect(8, 16, 32, 20, (90, 80, 60, 255))
    elif kind == "laboratory":
        c.rect(16, 6, 16, 16, (90, 200, 160, 255))
    else:
        c.rect(18, 6, 12, 14, GOLD)
    _outline(c)
    return c


BUILDING_FNS = {
    "command_center": building_command,
    "capital": building_command,
    "fortress": building_fortress,
    "hospital": building_hospital,
    "city": building_hospital,
    "sanctuary": building_sanctuary,
    "village": building_village,
    "laboratory": building_lab,
    "lab": building_lab,
}


def build_buildings() -> None:
    out = GAME / "buildings"
    for name, fn in BUILDING_FNS.items():
        for lvl in range(1, 6):
            fn(lvl).save(out / f"{name}_{lvl}.png")
            fn(lvl).save(out / f"{name}_lvl_{lvl}.png")
    generics = {
        "tower": PURP,
        "market": GOLD,
        "workshop": DIRT2,
        "barracks": (90, 110, 70, 255),
        "datacenter": CYAN,
        "library": (140, 110, 60, 255),
        "hospital": RED,
        "house": (210, 180, 140, 255),
        "warehouse": (100, 90, 70, 255),
        "laboratory": (80, 180, 140, 255),
        "command_center": GOLD,
    }
    for name, col in generics.items():
        building_generic(name, col).save(out / f"{name}.png")


# --- units 16x24 x 8 frames ---
UW, UH, FRAMES = 16, 24, 8


def unit_sheet(shirt, pants, accent) -> C:
    sheet = C(UW * FRAMES, UH)
    for f in range(FRAMES):
        u = C(UW, UH)
        bob = 1 if f in (1, 6) else 0
        step = 0 if f < 2 else (f - 2) % 4
        work = f >= 6
        u.rect(6, 3 + bob, 4, 4, SKIN)
        u.rect(6, 2 + bob, 4, 2, HAIR)
        u.rect(5, 7 + bob, 6, 7, shirt)
        u.rect(5, 14 + bob, 6, 5, pants)
        lx = 5 - (1 if step in (1, 2) else 0)
        rx = 9 + (1 if step in (0, 3) else 0)
        u.rect(lx, 19 + bob, 3, 4, pants)
        u.rect(rx, 19 + bob, 3, 4, pants)
        arm = 4 if work else 5
        u.rect(3, arm + bob, 2, 6, shirt)
        u.rect(11, (3 if work else 7) + bob, 2, 6, shirt)
        if accent:
            u.rect(7, 8 + bob, 2, 2, accent)
        sheet.blit(u, f * UW, 0)
    return sheet


def build_units() -> None:
    specs = {
        "developer": (CYAN, (40, 50, 70, 255), GOLD),
        "sales": (GOLD, (50, 40, 30, 255), RED),
        "researcher": (PURP, (40, 40, 60, 255), CYAN),
        "qa": ((200, 80, 80, 255), (50, 50, 50, 255), GOLD),
        "marketing": ((230, 140, 50, 255), (60, 40, 30, 255), GOLD2),
        "infrastructure": ((140, 150, 160, 255), (40, 40, 48, 255), CYAN),
    }
    for name, cols in specs.items():
        unit_sheet(*cols).save(GAME / "units" / f"{name}.png")


def build_effects() -> None:
    smoke = C(16 * 4, 16)
    for f in range(4):
        s = C(16, 16)
        r = 3 + f
        s.rect(8 - r, 10 - f * 2, r * 2, r, (180, 180, 180, 80 + f * 20))
        smoke.blit(s, f * 16, 0)
    smoke.save(GAME / "effects" / "smoke.png")

    flag = C(16 * 2, 16)
    for f in range(2):
        fl = C(16, 16)
        fl.rect(2, 2, 2, 14, (80, 60, 30, 255))
        ox = 1 if f else 0
        fl.rect(4, 2 + ox, 10, 7, GOLD)
        flag.blit(fl, f * 16, 0)
    flag.save(GAME / "effects" / "flag.png")

    bird = C(16 * 2, 12)
    for f in range(2):
        b = C(16, 12)
        b.rect(6, 5, 5, 2, (30, 30, 36, 255))
        if f == 0:
            b.rect(3, 4, 4, 1, (30, 30, 36, 255))
            b.rect(10, 4, 4, 1, (30, 30, 36, 255))
        else:
            b.rect(3, 6, 4, 1, (30, 30, 36, 255))
            b.rect(10, 6, 4, 1, (30, 30, 36, 255))
        bird.blit(b, f * 16, 0)
    bird.save(GAME / "effects" / "bird.png")

    cloud = C(64, 24)
    cloud.rect(8, 8, 40, 10, (220, 230, 240, 90))
    cloud.rect(16, 4, 24, 8, (230, 236, 246, 100))
    cloud.save(GAME / "effects" / "cloud.png")

    coin = C(12, 12)
    coin.rect(3, 3, 6, 6, GOLD2)
    coin.rect(4, 4, 4, 4, GOLD)
    coin.save(GAME / "effects" / "coin.png")

    spark = C(12, 12)
    spark.rect(5, 1, 2, 10, GOLD2)
    spark.rect(1, 5, 10, 2, GOLD2)
    spark.save(GAME / "effects" / "spark.png")

    alert = C(16, 16)
    alert.rect(7, 2, 2, 10, RED)
    alert.rect(7, 13, 2, 2, RED)
    alert.save(GAME / "effects" / "alert.png")

    target = C(16, 16)
    target.rect(2, 7, 12, 2, (90, 180, 90, 255))
    target.rect(7, 2, 2, 12, (90, 180, 90, 255))
    target.save(GAME / "effects" / "target.png")


# --- Tiled map ---
# GIDs are 1-based indexes into TILE_FNS
GID = {n: i + 1 for i, n in enumerate(TILE_NAMES)}


def noise(x: int, y: int, seed: int = 11) -> float:
    n = (x * 374761 + y * 668265 + seed * 127) & 0x7FFFFFFF
    n = (n << 13) ^ n
    return ((n * (n * n * 15731 + 789221) + 1376312589) & 0x7FFFFFFF) / 0x7FFFFFFF


def generate_grids():
    ground = [[GID["grass_a"] for _ in range(MAP_W)] for _ in range(MAP_H)]
    water = [[0 for _ in range(MAP_W)] for _ in range(MAP_H)]
    roads = [[0 for _ in range(MAP_W)] for _ in range(MAP_H)]
    deco = [[0 for _ in range(MAP_W)] for _ in range(MAP_H)]
    fog = [[0 for _ in range(MAP_W)] for _ in range(MAP_H)]

    for y in range(MAP_H):
        for x in range(MAP_W):
            n = noise(x, y)
            n2 = noise(x + 40, y + 9, 3)
            if n > 0.66:
                ground[y][x] = GID["grass_b"]
            if n2 > 0.82:
                ground[y][x] = GID["grass_flower"]
            if y < 7 or (y < 11 and abs(x - 40) < 18 and n > 0.4):
                ground[y][x] = GID["mountain_peak"] if y < 3 else GID["mountain"]
            if y < 5 and 20 < x < 60:
                deco[y][x] = GID["mountain_peak"] if x % 5 == 0 else 0

    # river
    for x in range(MAP_W):
        cy = int(16 + 6 * math.sin(x / 9.0) + x / 18)
        for t in range(-2, 3):
            yy = cy + t
            if 0 <= yy < MAP_H:
                water[yy][x] = GID["water_b"] if (x + yy) % 2 else GID["water_a"]
                ground[yy][x] = GID["shore"] if abs(t) == 2 else GID["dirt"]
                if abs(t) < 2:
                    ground[yy][x] = GID["water_a"]

    # forests
    patches = [(18, 20, 8), (28, 14, 6), (60, 18, 7), (10, 28, 5), (70, 30, 5)]
    for px, py, r in patches:
        for y in range(py - r, py + r):
            for x in range(px - r, px + r):
                if 0 <= x < MAP_W and 0 <= y < MAP_H and (x - px) ** 2 + (y - py) ** 2 < r * r:
                    if water[y][x] == 0 and ground[y][x] not in {GID["mountain"], GID["mountain_peak"]}:
                        deco[y][x] = GID["forest"] if noise(x, y, 8) > 0.45 else GID["tree"]
                        if noise(x, y, 2) > 0.7:
                            deco[y][x] = GID["bush"]

    # urban / tech zones
    def stamp(cx, cy, r, gid):
        for y in range(cy - r, cy + r):
            for x in range(cx - r, cx + r):
                if 0 <= x < MAP_W and 0 <= y < MAP_H and water[y][x] == 0:
                    if (x - cx) ** 2 + (y - cy) ** 2 < r * r and noise(x, y, 5) > 0.25:
                        ground[y][x] = gid

    stamp(40, 24, 6, GID["urban"])  # capital
    stamp(52, 36, 5, GID["tech"])  # fortress
    stamp(58, 44, 4, GID["tech"])  # laboratory
    stamp(22, 38, 4, GID["grass_flower"])  # gardens
    stamp(13, 16, 4, GID["sand"])  # market
    stamp(67, 13, 4, GID["grass_b"])  # village

    cities = {
        "capital": (40, 24),
        "fortress": (52, 36),
        "lab": (58, 44),
        "city": (22, 38),
        "market": (13, 16),
        "village": (67, 13),
    }
    cap = cities["capital"]

    def carve_road(a, b):
        x, y = a
        tx, ty = b
        while x != tx:
            x += 1 if tx > x else -1
            if water[y][x]:
                continue
            roads[y][x] = GID["road_h"]
            ground[y][x] = GID["dirt"]
        while y != ty:
            y += 1 if ty > y else -1
            if 0 <= y < MAP_H and not water[y][x]:
                roads[y][x] = GID["road_x"] if roads[y][x] else GID["road_v"]
                ground[y][x] = GID["dirt"]

    for key, pos in cities.items():
        if key != "capital":
            mid = (pos[0], cap[1]) if abs(pos[0] - cap[0]) > 4 else (cap[0], pos[1])
            carve_road(cap, mid)
            carve_road(mid, pos)
        roads[pos[1]][pos[0]] = GID["road_c"]

    # fog corners — conceptual unexplored ideas / markets
    for y in range(MAP_H):
        for x in range(MAP_W):
            edge = x < 3 or x > MAP_W - 4 or y > MAP_H - 4
            corner = (x < 8 and y > MAP_H - 10) or (x > MAP_W - 10 and y < 8)
            if (edge or corner) and water[y][x] == 0 and ground[y][x] not in {GID["mountain"], GID["mountain_peak"]}:
                if noise(x, y, 21) > 0.55:
                    fog[y][x] = GID["fog"]

    return ground, water, roads, deco, fog, cities


def layer(name: int, lid: int, grid, opacity: float = 1) -> dict:
    data = [v for row in grid for v in row]
    return {
        "id": lid,
        "name": name,
        "type": "tilelayer",
        "width": MAP_W,
        "height": MAP_H,
        "data": data,
        "opacity": opacity,
        "visible": True,
        "x": 0,
        "y": 0,
    }


def write_empire_map() -> None:
    ground, water, roads, deco, fog, cities = generate_grids()
    tileset = {
        "columns": 8,
        "firstgid": 1,
        "image": "../tiles/terrain.png",
        "imageheight": 96,
        "imagewidth": 256,
        "margin": 0,
        "name": "terrain",
        "spacing": 0,
        "tilecount": 24,
        "tileheight": 32,
        "tilewidth": 32,
        "tiles": [
            {
                "id": 9,
                "animation": [
                    {"duration": 420, "tileid": 9},
                    {"duration": 420, "tileid": 10},
                ],
            }
        ],
    }
    objects = []
    oid = 1
    regions = [
        ("CENTRAL", 40, 22, 380, 280),
        ("TECH VALLEY", 54, 40, 420, 300),
        ("SOCIAL VALLEY", 22, 36, 360, 260),
        ("MARKET DISTRICT", 13, 15, 300, 220),
        ("NORTH RANGE", 40, 4, 900, 160),
    ]
    for name, tx, ty, w, h in regions:
        objects.append(
            {
                "id": oid,
                "name": name,
                "type": "region",
                "x": tx * TILE - w / 2,
                "y": ty * TILE - 40,
                "width": w,
                "height": h,
                "visible": True,
            }
        )
        oid += 1
    for i, (tx, ty) in enumerate([(12, 10), (50, 8), (70, 22), (30, 30)]):
        objects.append(
            {
                "id": oid,
                "name": f"tree_{i}",
                "type": "tree",
                "x": tx * TILE,
                "y": ty * TILE,
                "width": 32,
                "height": 32,
                "visible": True,
            }
        )
        oid += 1
    objects.append(
        {
            "id": oid,
            "name": "unexplored_markets",
            "type": "fog",
            "x": 32,
            "y": (MAP_H - 8) * TILE,
            "width": 8 * TILE,
            "height": 7 * TILE,
            "visible": True,
        }
    )

    tiled = {
        "compressionlevel": -1,
        "height": MAP_H,
        "width": MAP_W,
        "tilewidth": TILE,
        "tileheight": TILE,
        "infinite": False,
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "tiledversion": "1.10.2",
        "type": "map",
        "version": "1.10",
        "nextlayerid": 8,
        "nextobjectid": oid + 2,
        "tilesets": [tileset],
        "layers": [
            layer("ground", 1, ground),
            layer("water", 2, water),
            layer("roads", 3, roads),
            layer("decoration", 4, deco),
            layer("fog", 5, fog, 0.55),
            {
                "id": 6,
                "name": "zones",
                "type": "objectgroup",
                "draworder": "topdown",
                "objects": objects,
                "opacity": 1,
                "visible": True,
                "x": 0,
                "y": 0,
            },
        ],
        "properties": [
            {"name": "note", "type": "string", "value": "Map data only. Projects come from /api/map."}
        ],
    }
    path = GAME / "maps" / "empire_map.json"
    path.write_text(json.dumps(tiled), encoding="utf-8")

    # tiny inner-city plaza
    cw, ch = 28, 20
    g = [[GID["urban"] if 6 < x < 22 and 4 < y < 16 else GID["grass_b"] for x in range(cw)] for y in range(ch)]
    r = [[0] * cw for _ in range(ch)]
    for x in range(cw):
        r[10][x] = GID["road_h"]
    for y in range(ch):
        r[y][14] = GID["road_v"]
    r[10][14] = GID["road_x"]
    city = {
        "compressionlevel": -1,
        "height": ch,
        "width": cw,
        "tilewidth": TILE,
        "tileheight": TILE,
        "infinite": False,
        "orientation": "orthogonal",
        "renderorder": "right-down",
        "tiledversion": "1.10.2",
        "type": "map",
        "version": "1.10",
        "nextlayerid": 4,
        "nextobjectid": 1,
        "tilesets": [tileset],
        "layers": [layer("ground", 1, g), layer("roads", 2, r)],
    }
    (GAME / "maps" / "city_map.json").write_text(json.dumps(city), encoding="utf-8")

    tsx = f'''<?xml version="1.0" encoding="UTF-8"?>
<tileset version="1.10" tiledversion="1.10.2" name="terrain" tilewidth="32" tileheight="32" tilecount="24" columns="8">
 <image source="../tiles/terrain.png" width="256" height="96"/>
 <tile id="9"><animation><frame tileid="9" duration="420"/><frame tileid="10" duration="420"/></animation></tile>
</tileset>
'''
    (GAME / "tiles" / "terrain.tsx").write_text(tsx, encoding="utf-8")


def main() -> None:
    print("tileset", build_tileset())
    build_buildings()
    build_units()
    build_effects()
    write_empire_map()
    print("assets ready in", GAME)


if __name__ == "__main__":
    main()
