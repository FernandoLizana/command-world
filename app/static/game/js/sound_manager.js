/**
 * Sound is prepared but silent unless SOUND_ENABLED / visual.sound is true.
 * Never autoplay ambience.
 */
(function (global) {
  const KEYS = ["click", "mission_complete", "level_up", "alert", "ambience"];

  const SoundManager = {
    enabled: false,
    play(name) {
      if (!this.enabled) return;
      if (!KEYS.includes(name)) return;
      /* Future: scene.sound.play(name). No files shipped yet. */
    },
    setEnabled(value) {
      this.enabled = Boolean(value);
    },
  };

  global.DRSound = SoundManager;
})(window);
