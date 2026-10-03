/**
 * Sprite lookup, level fallbacks and Phaser animation registration.
 */
(function (global) {
  const TYPE_ALIAS = {
    capital: "command_center",
    city: "hospital",
    lab: "laboratory",
    camp: "village",
    market: "sanctuary",
    tech_fortress: "fortress",
  };

  function clampLevel(level) {
    const n = Number(level) || 1;
    return Math.max(1, Math.min(5, n));
  }

  function buildingTexture(scene, city) {
    const raw = city.building || "capital";
    const kind = TYPE_ALIAS[raw] || raw;
    const lvl = clampLevel(city.level);
    const candidates = [
      `${kind}_${lvl}`,
      `${kind}_lvl_${lvl}`,
      `${raw}_${lvl}`,
      `${raw}_lvl_${lvl}`,
      kind,
      raw,
      "command_center_1",
    ];
    for (let i = 0; i < candidates.length; i += 1) {
      if (scene.textures.exists(candidates[i])) return candidates[i];
    }
    return "command_center_1";
  }

  function createAnims(scene) {
    const units = (global.DRAssets && global.DRAssets.UNITS) || [];
    units.forEach((name) => {
      if (!scene.textures.exists(name)) return;
      if (!scene.anims.exists(`${name}-idle`)) {
        scene.anims.create({
          key: `${name}-idle`,
          frames: scene.anims.generateFrameNumbers(name, { start: 0, end: 1 }),
          frameRate: 3,
          repeat: -1,
        });
      }
      if (!scene.anims.exists(`${name}-walk`)) {
        scene.anims.create({
          key: `${name}-walk`,
          frames: scene.anims.generateFrameNumbers(name, { start: 2, end: 5 }),
          frameRate: 8,
          repeat: -1,
        });
      }
      if (!scene.anims.exists(`${name}-work`)) {
        scene.anims.create({
          key: `${name}-work`,
          frames: scene.anims.generateFrameNumbers(name, { start: 6, end: 7 }),
          frameRate: 4,
          repeat: -1,
        });
      }
    });
    if (scene.textures.exists("fx_smoke") && !scene.anims.exists("smoke")) {
      scene.anims.create({
        key: "smoke",
        frames: scene.anims.generateFrameNumbers("fx_smoke", { start: 0, end: 3 }),
        frameRate: 4,
        repeat: -1,
      });
    }
    if (scene.textures.exists("fx_flag") && !scene.anims.exists("flag")) {
      scene.anims.create({
        key: "flag",
        frames: scene.anims.generateFrameNumbers("fx_flag", { start: 0, end: 1 }),
        frameRate: 4,
        repeat: -1,
      });
    }
    if (scene.textures.exists("fx_bird") && !scene.anims.exists("bird")) {
      scene.anims.create({
        key: "bird",
        frames: scene.anims.generateFrameNumbers("fx_bird", { start: 0, end: 1 }),
        frameRate: 6,
        repeat: -1,
      });
    }
  }

  function unitForMission(type) {
    const map = {
      DEVELOPMENT: "developer",
      SALES: "sales",
      MARKETING: "marketing",
      QA: "qa",
      INFRASTRUCTURE: "infrastructure",
      RESEARCH: "researcher",
      ADMINISTRATION: "sales",
    };
    return map[type] || "developer";
  }

  function activityRoster(city) {
    const roster = [];
    const activity = city.activity || {};
    Object.keys(activity).forEach((kind) => {
      const n = Math.min(3, Number(activity[kind]) || 0);
      for (let i = 0; i < n; i += 1) roster.push(unitForMission(kind));
    });
    if (city.critical) roster.push("qa");
    if ((city.opportunities || 0) > 0) roster.push("sales");
    if (!roster.length && (city.momentum || 0) > 20) roster.push("developer");
    if (city.status === "PAUSED" || city.status === "ARCHIVED") return [];
    const want = Math.max(1, Math.min(3, 1 + Math.round((city.momentum || 0) / 40)));
    if (city.status === "BLOCKED") return ["qa"].slice(0, want);
    while (roster.length < want) roster.push(roster[0] || "developer");
    return roster.slice(0, 3);
  }

  function healthTint(health) {
    if (health > 75) return 0xffffff;
    if (health > 50) return 0xfff0c8;
    if (health > 25) return 0xe8c8a0;
    return 0xd09090;
  }

  global.DRSprites = {
    buildingTexture,
    createAnims,
    unitForMission,
    activityRoster,
    healthTint,
    clampLevel,
    TYPE_ALIAS,
  };
})(window);
