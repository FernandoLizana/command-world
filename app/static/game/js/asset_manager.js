/**
 * Central asset registry. Scenes must load through this file —
 * do not scatter texture URLs across the rest of the game code.
 */
(function (global) {
  const BASE = "/static/game";

  const BUILDING_TYPES = [
    "command_center",
    "capital",
    "fortress",
    "hospital",
    "city",
    "sanctuary",
    "village",
    "laboratory",
    "lab",
  ];

  const GENERICS = [
    "tower",
    "market",
    "workshop",
    "barracks",
    "datacenter",
    "library",
    "hospital",
    "house",
    "warehouse",
    "laboratory",
    "command_center",
  ];

  const UNITS = [
    "developer",
    "sales",
    "researcher",
    "qa",
    "marketing",
    "infrastructure",
  ];

  const EFFECTS = ["smoke", "flag", "bird", "cloud", "coin", "spark", "alert", "target"];

  const buildings = {};
  BUILDING_TYPES.forEach((name) => {
    for (let lvl = 1; lvl <= 5; lvl += 1) {
      buildings[`${name}_${lvl}`] = `${BASE}/buildings/${name}_${lvl}.png`;
    }
  });
  GENERICS.forEach((name) => {
    buildings[name] = `${BASE}/buildings/${name}.png`;
  });

  const units = {};
  UNITS.forEach((name) => {
    units[name] = `${BASE}/units/${name}.png`;
  });

  const effects = {};
  EFFECTS.forEach((name) => {
    effects[name] = `${BASE}/effects/${name}.png`;
  });

  const ASSETS = {
    tiles: { terrain: `${BASE}/tiles/terrain.png` },
    maps: {
      empire: `${BASE}/maps/empire_map.json`,
      city: `${BASE}/maps/city_map.json`,
    },
    buildings,
    units,
    effects,
  };

  function preload(scene, kind) {
    scene.load.image("terrain", ASSETS.tiles.terrain);
    if (kind === "city") {
      scene.load.tilemapTiledJSON("city_map", ASSETS.maps.city);
    } else {
      scene.load.tilemapTiledJSON("empire_map", ASSETS.maps.empire);
    }
    Object.entries(ASSETS.buildings).forEach(([key, url]) => scene.load.image(key, url));
    Object.entries(ASSETS.units).forEach(([key, url]) =>
      scene.load.spritesheet(key, url, { frameWidth: 16, frameHeight: 24 })
    );
    scene.load.spritesheet("fx_smoke", ASSETS.effects.smoke, { frameWidth: 16, frameHeight: 16 });
    scene.load.spritesheet("fx_flag", ASSETS.effects.flag, { frameWidth: 16, frameHeight: 16 });
    scene.load.spritesheet("fx_bird", ASSETS.effects.bird, { frameWidth: 16, frameHeight: 12 });
    scene.load.image("fx_cloud", ASSETS.effects.cloud);
    scene.load.image("fx_coin", ASSETS.effects.coin);
    scene.load.image("fx_spark", ASSETS.effects.spark);
    scene.load.image("fx_alert", ASSETS.effects.alert);
    scene.load.image("fx_target", ASSETS.effects.target);
  }

  global.DRAssets = { ASSETS, BASE, UNITS, preload };
})(window);
