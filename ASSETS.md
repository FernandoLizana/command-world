# Inventario de sprites — DR Command

Pixel art original generado con `python tools/generate_pixel_assets.py`
(stdlib only, sin copiar assets de otros juegos).

Regenerar:

```bash
python tools/generate_pixel_assets.py
```

Los proyectos **no** se guardan en el tilemap. El mapa es terreno y decoración.
Las ciudades salen de `GET /api/map`.

## TILES — `static/game/tiles/terrain.png` (32×32, 8 columnas)

| id | gid | nombre |
| --- | --- | --- |
| 0 | 1 | grass_a |
| 1 | 2 | grass_b |
| 2 | 3 | grass_flower |
| 3 | 4 | dirt |
| 4 | 5 | sand |
| 5 | 6 | road_h |
| 6 | 7 | road_v |
| 7 | 8 | road_x |
| 8 | 9 | road_c |
| 9 | 10 | water_a (animado con water_b) |
| 10 | 11 | water_b |
| 11 | 12 | shore |
| 12 | 13 | mountain |
| 13 | 14 | mountain_peak |
| 14 | 15 | tree |
| 15 | 16 | forest |
| 16 | 17 | urban |
| 17 | 18 | tech |
| 18 | 19 | fog |
| 19 | 20 | bush |
| 20–23 | | variantes |

Tileset Tiled: `static/game/tiles/terrain.tsx`

## MAPAS

- `static/game/maps/empire_map.json` — imperio (Tiled JSON)
- `static/game/maps/city_map.json` — plaza interna

Capas imperio: `ground`, `water`, `roads`, `decoration`, `fog`, `zones` (objetos).

## BUILDINGS — `static/game/buildings/`

Niveles 1–5 (fallback al tipo genérico si falta un archivo):

- `command_center` / `capital` — centro de mando
- `fortress` — producto o fortaleza técnica
- `hospital` / `city` — servicio o ciudad
- `sanctuary` — mercado o espacio comunitario
- `village` — proyecto pequeño o en pausa
- `laboratory` / `lab` — prototipo o investigación

Genéricos (mini ciudad): `tower`, `market`, `workshop`, `barracks`, `datacenter`, `library`, `house`, `warehouse`

Convención: `{tipo}_{nivel}.png` y `{tipo}_lvl_{nivel}.png`

## UNITS — `static/game/units/` spritesheet 16×24 × 8 frames

Frames: idle_1, idle_2, walk_1–4, work_1, work_2

- `developer.png`
- `sales.png`
- `researcher.png`
- `qa.png`
- `marketing.png`
- `infrastructure.png`

## EFFECTS — `static/game/effects/`

`smoke` `flag` `bird` `cloud` `coin` `spark` `alert` `target`

## SONIDO (preparado, no se reproduce)

`click` `mission_complete` `level_up` `alert` `ambience`

`SOUND_ENABLED=false` por defecto. `DRSound` no autoplay.

## Editar el mapa con Tiled

1. Instala [Tiled](https://www.mapeditor.org/).
2. Abre `app/static/game/maps/empire_map.json`.
3. El tileset apunta a `../tiles/terrain.png`.
4. Edita solo terreno / caminos / árboles / niebla.
5. No pongas métricas de negocio en el JSON.
6. Guarda. Recarga el navegador.

Posiciones de ciudad: se guardan en `POST /api/projects/<id>/position`.
La edición visual del mapa (arrastrar edificios) queda en la API; el HUD
principal ya no muestra ese modo para no saturar la pantalla.
