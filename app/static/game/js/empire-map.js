/**
 * Empire map scene — tilemap is the dashboard.
 * Map data (Tiled) is separate from game data (/api/map).
 */
(function () {
  const host = document.getElementById("empire-map");
  if (!host) return;
  host.style.minHeight = host.style.minHeight || "480px";
  if (host.clientHeight < 200) {
    host.style.position = "relative";
    host.style.height = Math.max(window.innerHeight - 90, 480) + "px";
  }
  if (typeof Phaser === "undefined") {
    host.innerHTML =
      "<p style='color:#e8eedc;padding:24px;font-family:Rajdhani,sans-serif'>No se pudo cargar el motor del mapa. Recarga la página.</p>";
    return;
  }
  const boot = host.querySelector(".map-boot");
  if (boot) boot.remove();

  const MAP_URL = host.dataset.mapUrl || "/api/map";
  const STATUS_COLOR = {
    ACTIVE: 0x6bcb77,
    PAUSED: 0xe8b44c,
    BLOCKED: 0xe05656,
    EXPERIMENT: 0x5b8def,
    ARCHIVED: 0x6b7280,
  };

  class EmpireScene extends Phaser.Scene {
    constructor() {
      super("empire");
      this.cities = [];
      this.nodes = [];
      this.editMode = false;
      this.night = false;
      this.selected = null;
      this.visual = { day_night: true, sound: false, fog: true, demo: true };
    }

    preload() {
      window.DRAssets.preload(this, "empire");
      this.load.on("loaderror", (file) => console.warn("asset missing", file && file.key));
    }

    create() {
      try {
        window.DRSprites.createAnims(this);
        this.buildTilemap();
      } catch (err) {
        console.error("tilemap", err);
        this.add.rectangle(400, 300, 800, 600, 0x163024);
        this.add.text(40, 40, "Mapa: error al leer el tilemap. " + err, {
          fontFamily: "Rajdhani",
          fontSize: "16px",
          color: "#e05656",
          wordWrap: { width: 720 },
        });
      }
      this.cameras.main.setRoundPixels(true);
      this.cameras.main.setZoom(1);
      this._wireCamera();
      this._wireUi();
      this.fetchState();
      this.time.addEvent({ delay: 16000, loop: true, callback: () => this.pollEvents() });
      this.scale.refresh();
    }

    buildTilemap() {
      const map = this.make.tilemap({ key: "empire_map" });
      if (!map) throw new Error("empire_map no está en caché");
      const tiles = map.addTilesetImage("terrain", "terrain");
      if (!tiles) throw new Error("tileset terrain no cargó");
      this.map = map;
      this.ground = map.createLayer("ground", tiles, 0, 0);
      this.waterLayer = map.createLayer("water", tiles, 0, 0);
      this.roadLayer = map.createLayer("roads", tiles, 0, 0);
      this.decoLayer = map.createLayer("decoration", tiles, 0, 0);
      this.fogLayer = map.createLayer("fog", tiles, 0, 0);
      if (this.fogLayer) this.fogLayer.setDepth(4);
      this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
      this.cameras.main.centerOn(map.widthInPixels / 2, map.heightInPixels / 2);

      this.nightOverlay = this.add
        .rectangle(0, 0, map.widthInPixels, map.heightInPixels, 0x081018, 0)
        .setOrigin(0)
        .setDepth(20)
        .setBlendMode(Phaser.BlendModes.MULTIPLY);
    }

    _wireCamera() {
      this.input.on("wheel", (_p, _g, _dx, dy) => {
        this.nudgeZoom(dy > 0 ? -0.08 : 0.08);
      });
      this.input.on("pointerdown", (pointer) => {
        this._panning = !this._overCity && !this.editMode;
        this._panStart = { x: pointer.x, y: pointer.y };
      });
      this.input.on("pointerup", () => {
        this._panning = false;
        this._draggingCity = false;
      });
      this.input.on("pointermove", (pointer) => {
        if (!pointer.isDown || this._draggingCity) return;
        if (this.editMode) return;
        if (!this._panning) return;
        this.cameras.main.scrollX -= (pointer.x - pointer.prevPosition.x) / this.cameras.main.zoom;
        this.cameras.main.scrollY -= (pointer.y - pointer.prevPosition.y) / this.cameras.main.zoom;
      });
      if (this.input.keyboard) {
        this.input.keyboard.on("keydown-PLUS", () => this.nudgeZoom(0.12));
        this.input.keyboard.on("keydown-MINUS", () => this.nudgeZoom(-0.12));
        this.input.keyboard.on("keydown-E", () => this.setEditMode(!this.editMode));
        this.input.keyboard.on("keydown-N", () => this.setNight(!this.night));
        this.input.keyboard.on("keydown-C", () => this.centerSelected());
      }
    }

    _wireUi() {
      const bind = (id, fn) => {
        const el = document.getElementById(id);
        if (el) el.addEventListener("click", fn);
      };
      bind("map-zoom-in", () => this.nudgeZoom(0.12));
      bind("map-zoom-out", () => this.nudgeZoom(-0.12));
      bind("map-center", () => this.centerCapital());
      window.DRMap = {
        zoomIn: () => this.nudgeZoom(0.12),
        zoomOut: () => this.nudgeZoom(-0.12),
        center: () => this.centerCapital(),
        edit: (on) => this.setEditMode(on),
        night: (on) => this.setNight(on),
        focus: (slug) => this.focusSlug(slug),
        refresh: () => this.fetchState(),
      };
    }

    nudgeZoom(delta) {
      const cam = this.cameras.main;
      cam.setZoom(Phaser.Math.Clamp(cam.zoom + delta, 0.45, 1.8));
    }

    setEditMode(on) {
      this.editMode = Boolean(on);
      const btn = document.getElementById("map-edit");
      if (btn) btn.classList.toggle("solid", this.editMode);
      const hint = document.getElementById("map-edit-hint");
      if (hint) hint.style.display = this.editMode ? "block" : "none";
      window.DRSound.play("click");
    }

    setNight(on) {
      if (!this.visual.day_night && on) return;
      this.night = Boolean(on);
      const alpha = this.night ? 0.55 : 0;
      if (this.visual.quiet || this.visual.animations === false) {
        this.nightOverlay.setAlpha(alpha);
      } else {
        this.tweens.add({
          targets: this.nightOverlay,
          alpha,
          duration: 600,
        });
      }
      const btn = document.getElementById("map-night");
      if (btn) btn.classList.toggle("solid", this.night);
    }

    setFog(on) {
      if (this.fogLayer) this.fogLayer.setVisible(Boolean(on));
    }

    centerCapital() {
      const cap = this.cities.find((c) => c.building === "capital") || this.cities[0];
      if (cap) this.cameras.main.pan(cap.x, cap.y, 400, "Sine.easeInOut");
    }

    centerSelected() {
      if (this.selected) this.cameras.main.pan(this.selected.x, this.selected.y, 350, "Sine.easeInOut");
      else this.centerCapital();
    }

    focusSlug(slug) {
      const city = this.cities.find((c) => c.slug === slug);
      if (city) {
        this.cameras.main.pan(city.x, city.y, 400, "Sine.easeInOut");
        this.selectCity(city);
      }
    }

    fetchState() {
      fetch(MAP_URL, { credentials: "same-origin" })
        .then((r) => r.json())
        .then((data) => {
          this.visual = Object.assign(this.visual, data.visual || {});
          window.DRSound.setEnabled(Boolean(this.visual.sound) && !this.visual.quiet);
          this.setFog(this.visual.fog !== false && !this.visual.quiet);
          this.cities = data.cities || [];
          if (data.advisor) this.cities = this.cities.concat([data.advisor]);
          this.paintCities();
          if (!this._ambient) {
            if (this.visual.quiet || this.visual.animations === false) {
              this._ambient = true;
              this.centerCapital();
            } else {
              this.spawnAmbient();
              this._ambient = true;
              this.centerCapital();
            }
          }
          const now = data.now || {};
          const nowText = now.project
            ? now.project + (now.mission && now.mission.title ? " · " + now.mission.title : "")
            : now.summary;
          if (window.DRWorld && window.DRWorld.setNow) window.DRWorld.setNow(nowText);
        })
        .catch((err) => {
          console.error("map api", err);
          this.add.text(80, 80, "No se pudo cargar /api/map", {
            fontFamily: "Rajdhani",
            fontSize: "18px",
            color: "#e05656",
          });
        });
    }

    paintCities() {
      this.nodes.forEach((n) => n.destroy());
      this.nodes = this.cities.map((city) => this.makeCity(city));
    }

    makeCity(city) {
      const root = this.add.container(city.x, city.y).setDepth(10);
      const paused = city.status === "PAUSED" || city.status === "ARCHIVED";
      const blocked = city.status === "BLOCKED" || city.critical;
      const upgraded = (city.level || 0) >= 4 && !paused;
      const key = window.DRSprites.buildingTexture(this, city);
      const sprite = this.add.image(0, -8, key).setScale(upgraded ? 1.2 : city.level <= 1 ? 0.92 : 1);
      sprite.setTint(paused ? 0x667788 : window.DRSprites.healthTint(city.health));
      sprite.setAlpha(paused ? 0.42 : blocked ? 0.9 : 1);

      const ringColor = city.kind === "advisor" ? 0xc9a227 : STATUS_COLOR[city.status] || 0x6bcb77;
      const ring = this.add.circle(0, 18, 42, ringColor, city.kind === "advisor" ? 0.16 : 0.08);
      ring.setStrokeStyle(2, ringColor, 0.85);
      const select = this.add.circle(0, 10, 50, 0xc9a227, 0).setStrokeStyle(2, 0xc9a227, 0);
      const hover = this.add.circle(0, 10, 54, 0xe8c547, 0).setStrokeStyle(2, 0xe8c547, 0);

      const name = this.add
        .text(0, 40, (city.name || "").toUpperCase(), {
          fontFamily: "Cinzel, serif",
          fontSize: "11px",
          color: paused ? "#6b7280" : "#e8eedc",
          align: "center",
        })
        .setOrigin(0.5, 0);

      root.add([ring, select, hover, sprite, name]);

      if (blocked || (city.alerts || 0) > 0) {
        const al = this.add.image(26, -36, "fx_alert").setScale(1.2);
        root.add(al);
        this.tweens.add({ targets: al, y: "-=5", duration: 700, yoyo: true, repeat: -1 });
      }
      if ((city.opportunities || 0) > 0 && !paused) {
        const merchant = this.add.sprite(-28, 18, "sales").setScale(1.5);
        if (this.anims.exists("sales-idle")) merchant.play("sales-idle");
        root.add(merchant);
        root.add(this.add.image(-26, -32, "fx_target").setScale(1.1));
      }
      if (!paused && (city.momentum || 0) >= 55 && this.anims.exists("flag")) {
        root.add(this.add.sprite(20, -28, "fx_flag").play("flag"));
      }
      if (!paused && city.status === "ACTIVE" && this.anims.exists("smoke")) {
        root.add(this.add.sprite(-18, -30, "fx_smoke").play("smoke").setAlpha(0.7));
      }
      if (city.kind === "advisor" && this.anims.exists("flag")) {
        root.add(this.add.sprite(18, -30, "fx_flag").play("flag"));
      }

      const hit = this.add.rectangle(0, 0, 88, 110, 0x000000, 0.001);
      hit.setInteractive({ useHandCursor: true, draggable: true });
      root.add(hit);
      root.setData("city", city);
      root.sprite = sprite;
      root.selectGfx = select;
      root.hoverGfx = hover;

      hit.on("pointerover", () => {
        this._overCity = true;
        hover.setStrokeStyle(2, 0xe8c547, 0.95);
        window.DRSound.play("click");
      });
      hit.on("pointerout", () => {
        this._overCity = false;
        hover.setStrokeStyle(2, 0xe8c547, 0);
      });
      hit.on("pointerup", (pointer) => {
        if (pointer.getDuration() < 240 && !this._didDrag) this.selectCity(city, root);
        this._didDrag = false;
      });
      hit.on("dragstart", () => {
        if (!this.editMode) return;
        this._draggingCity = true;
      });
      hit.on("drag", (pointer) => {
        if (!this.editMode) return;
        this._didDrag = true;
        const world = this.cameras.main.getWorldPoint(pointer.x, pointer.y);
        root.x = world.x;
        root.y = world.y;
      });
      hit.on("dragend", () => {
        if (!this.editMode || city.kind === "advisor") return;
        this._draggingCity = false;
        city.x = Math.round(root.x);
        city.y = Math.round(root.y);
        fetch(`/api/projects/${city.id}/position`, {
          method: "POST",
          credentials: "same-origin",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ x: city.x, y: city.y }),
        }).catch((e) => console.error("position", e));
      });

      this.spawnUnits(city, root);
      return root;
    }

    spawnUnits(city, root) {
      if (city.status === "PAUSED" || city.status === "ARCHIVED") return;
      const units = Array.isArray(city.units) && city.units.length
        ? city.units
        : (window.DRSprites.activityRoster(city) || []).map((sprite) => ({ sprite, activity: "idle" }));
      units.forEach((unit, i) => {
        const spriteName = unit.sprite || unit;
        if (!this.textures.exists(spriteName)) return;
        const ang = (i / units.length) * Math.PI * 2;
        const dist = 36 + (i % 3) * 10;
        const npc = this.add
          .sprite(Math.cos(ang) * dist, 20 + Math.sin(ang) * 12, spriteName)
          .setScale(1.4)
          .setDepth(11);
        npc.missionId = unit.mission_id || null;
        const activity = unit.activity || "idle";
        const anim = activity === "work" || activity === "review" ? `${spriteName}-work`
          : activity === "wait" ? `${spriteName}-idle`
          : `${spriteName}-idle`;
        if (this.anims.exists(anim)) npc.play(anim);
        else if (this.anims.exists(`${spriteName}-idle`)) npc.play(`${spriteName}-idle`);
        npc.setInteractive({ useHandCursor: true });
        npc.on("pointerup", () => {
          if (npc.missionId && window.DRWorld && window.DRWorld.openMission) {
            window.DRWorld.openMission(npc.missionId);
          }
        });
        root.add(npc);
        if (this.visual.quiet || this.visual.animations === false) return;
        if (activity === "wait") return;
        const walk = () => {
          if (this.anims.exists(`${spriteName}-walk`)) npc.play(`${spriteName}-walk`);
          this.tweens.add({
            targets: npc,
            x: Math.cos(ang + Math.random()) * dist,
            y: 18 + Math.random() * 16,
            duration: 1800 + Math.random() * 1600,
            onComplete: () => {
              const next = activity === "work" || activity === "review" ? `${spriteName}-work` : `${spriteName}-idle`;
              if (this.anims.exists(next)) npc.play(next);
              this.time.delayedCall(1200 + Math.random() * 1600, walk);
            },
          });
        };
        this.time.delayedCall(400 * i, walk);
      });
    }

    spawnAmbient() {
      if (this.visual.quiet || this.visual.animations === false) return;
      const w = this.map.widthInPixels;
      const h = this.map.heightInPixels;
      for (let i = 0; i < 3; i += 1) {
        const bird = this.add.sprite(80 + i * 400, 80 + i * 60, "fx_bird").setDepth(18).play("bird");
        this.tweens.add({
          targets: bird,
          x: w - 40,
          y: 120 + i * 80,
          duration: 28000 + i * 4000,
          yoyo: true,
          repeat: -1,
        });
      }
      for (let i = 0; i < 2; i += 1) {
        const cloud = this.add.image(200 + i * 700, 90 + i * 40, "fx_cloud").setDepth(19).setAlpha(0.55);
        this.tweens.add({
          targets: cloud,
          x: cloud.x + 400,
          duration: 50000,
          yoyo: true,
          repeat: -1,
        });
      }
      if (this.decoLayer) {
        this.tweens.add({
          targets: this.decoLayer,
          alpha: { from: 0.92, to: 1 },
          duration: 2200,
          yoyo: true,
          repeat: -1,
        });
      }
    }

    demoPulses() {
      this.time.addEvent({
        delay: 9000,
        loop: true,
        callback: () => {
          const city = this.cities[Math.floor(Math.random() * this.cities.length)];
          if (!city) return;
          const msgs = ["+5 XP", "+3 SALES", "MISSION COMPLETE", "+10 QA"];
          this.floatText(city.x, city.y - 50, msgs[Math.floor(Math.random() * msgs.length)], "#e8c547");
        },
      });
    }

    floatText(x, y, msg, color) {
      const t = this.add
        .text(x, y, msg, {
          fontFamily: "Share Tech Mono, monospace",
          fontSize: "13px",
          color: color || "#e8c547",
        })
        .setOrigin(0.5)
        .setDepth(40);
      this.tweens.add({
        targets: t,
        y: y - 28,
        alpha: 0,
        duration: 1600,
        onComplete: () => t.destroy(),
      });
    }

    selectCity(city, node) {
      this.selected = city;
      this.nodes.forEach((n) => n.selectGfx && n.selectGfx.setStrokeStyle(2, 0xc9a227, 0));
      if (node && node.selectGfx) node.selectGfx.setStrokeStyle(2, 0xc9a227, 1);
      if (window.DRWorld && window.DRWorld.openBuilding) window.DRWorld.openBuilding(city);
      window.DRSound.play("click");
    }

    pollEvents() {
      fetch("/api/events?limit=6", { credentials: "same-origin" })
        .then((r) => r.json())
        .then((items) => {
          const latest = items && items[0];
          if (!latest || latest.id === this._lastEvent) return;
          this._lastEvent = latest.id;
          const city = this.cities.find((c) => c.id === latest.project_id);
          if (!city) return;
          const kind = latest.kind || "";
          if (kind === "warning" || kind === "alert") {
            this.floatText(city.x, city.y - 40, "⚠ ALERTA", "#e05656");
            window.DRSound.play("alert");
          } else if (kind === "opportunity") {
            this.floatText(city.x, city.y - 40, "🎯 OPORTUNIDAD", "#6bcb77");
          } else if (kind === "success") {
            this.floatText(city.x, city.y - 40, "+ XP", "#e8c547");
            const coin = this.add.image(city.x, city.y - 20, "fx_coin").setDepth(40);
            this.tweens.add({
              targets: coin,
              y: city.y - 48,
              alpha: 0,
              duration: 900,
              onComplete: () => coin.destroy(),
            });
            window.DRSound.play("mission_complete");
          }
        })
        .catch(() => {});
    }
  }

  const width = Math.max(host.clientWidth || 0, 640);
  const height = Math.max(host.clientHeight || 0, 480);
  const game = new Phaser.Game({
    type: Phaser.AUTO,
    parent: host,
    width,
    height,
    backgroundColor: "#0a120e",
    scene: [EmpireScene],
    banner: false,
    pixelArt: true,
    roundPixels: true,
    scale: { mode: Phaser.Scale.RESIZE, autoCenter: Phaser.Scale.NO_CENTER },
    render: { pixelArt: true, antialias: false },
  });
  window.DR_MAP = game;
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) game.loop.sleep();
    else game.loop.wake();
  });
})();
