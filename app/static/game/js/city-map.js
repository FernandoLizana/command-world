/**
 * Inner city view — modules as generic buildings on a small Tiled plaza.
 */
(function () {
  const host = document.getElementById("city-map");
  if (!host || typeof Phaser === "undefined") return;

  const DATA_URL = host.dataset.cityUrl;

  class CityScene extends Phaser.Scene {
    constructor() {
      super("city");
    }

    preload() {
      window.DRAssets.preload(this, "city");
    }

    create() {
      window.DRSprites.createAnims(this);
      const map = this.make.tilemap({ key: "city_map" });
      const tiles = map.addTilesetImage("terrain", "terrain");
      map.createLayer("ground", tiles, 0, 0);
      map.createLayer("roads", tiles, 0, 0);
      this.cameras.main.setBounds(0, 0, map.widthInPixels, map.heightInPixels);
      this.cameras.main.centerOn(map.widthInPixels / 2, map.heightInPixels / 2);
      this.cameras.main.setZoom(1.15);
      this.cameras.main.setRoundPixels(true);

      this.input.on("pointermove", (pointer) => {
        if (!pointer.isDown) return;
        this.cameras.main.scrollX -= (pointer.x - pointer.prevPosition.x) / this.cameras.main.zoom;
        this.cameras.main.scrollY -= (pointer.y - pointer.prevPosition.y) / this.cameras.main.zoom;
      });
      this.input.on("wheel", (_p, _g, _dx, dy) => {
        this.cameras.main.setZoom(Phaser.Math.Clamp(this.cameras.main.zoom - dy * 0.001, 0.8, 2));
      });

      fetch(DATA_URL, { credentials: "same-origin" })
        .then((r) => r.json())
        .then((data) => this.placeModules(data))
        .catch((err) => console.error("city api", err));
    }

    placeModules(data) {
      const project = data.project || {};
      (data.modules || []).forEach((mod) => {
        const tex = this.textures.exists(mod.building) ? mod.building : "workshop";
        const img = this.add.image(mod.x, mod.y, tex).setInteractive({ useHandCursor: true });
        this.add
          .text(mod.x, mod.y + 28, (mod.label || mod.key).toUpperCase(), {
            fontFamily: "Cinzel, serif",
            fontSize: "11px",
            color: "#e8eedc",
          })
          .setOrigin(0.5, 0);
        img.on("pointerup", () => {
          const box = document.getElementById("module-info");
          if (box) box.textContent = `${mod.label}: ${mod.hint || ""}`;
        });
        if ((project.momentum || 0) > 40) {
          const unit = window.DRSprites.unitForMission(mod.mission_type || "DEVELOPMENT");
          if (this.textures.exists(unit)) {
            const npc = this.add.sprite(mod.x + 22, mod.y + 16, unit).setScale(1.5);
            npc.play(`${unit}-walk`);
            this.tweens.add({
              targets: npc,
              x: mod.x - 18,
              duration: 2400,
              yoyo: true,
              repeat: -1,
            });
          }
        }
      });
      this.add.text(24, 16, (project.name || "CIUDAD").toUpperCase(), {
        fontFamily: "Cinzel, serif",
        fontSize: "18px",
        color: "#c9a227",
      });
    }
  }

  new Phaser.Game({
    type: Phaser.AUTO,
    parent: host,
    width: host.clientWidth || 800,
    height: host.clientHeight || 560,
    backgroundColor: "#0a120e",
    scene: [CityScene],
    banner: false,
    pixelArt: true,
    scale: { mode: Phaser.Scale.RESIZE },
    render: { pixelArt: true, antialias: false },
  });
})();
