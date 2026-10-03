import json

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import GameSetting
from app.models.constants import DEFAULT_XP_REWARDS
from app.services.backup_service import BackupService
from app.services.game_service import GameService
from app.services.world_service import WorldService

bp = Blueprint("settings", __name__)


@bp.route("/", methods=["GET", "POST"], strict_slashes=False)
@login_required
def view():
    empire = GameService.get_empire()
    xp = GameSetting.xp_rewards()
    if request.method == "POST":
        GameService.update_resources(
            {
                "name": request.form.get("name"),
                "money": request.form.get("money"),
                "available_hours": request.form.get("available_hours"),
                "level": request.form.get("level"),
            }
        )
        updated = {}
        for key in DEFAULT_XP_REWARDS:
            raw = request.form.get(f"xp_{key}")
            if raw not in (None, ""):
                try:
                    updated[key] = int(raw)
                except ValueError:
                    updated[key] = DEFAULT_XP_REWARDS[key]
        GameSetting.set("xp_rewards", json.dumps({**xp, **updated}))
        for key in ("day_night", "fog", "sound_enabled"):
            GameSetting.set(key, "true" if request.form.get(key) else "false")
        weekly = request.form.get("weekly_minutes")
        WorldService.save(
            {
                "timezone": request.form.get("timezone") or "UTC",
                "currency": (request.form.get("currency") or "USD").upper()[:8],
                "usage_type": request.form.get("usage_type") or "mix",
                "gamification": request.form.get("gamification") or "balanced",
                "weekly_minutes": int(weekly) if weekly not in (None, "") else None,
                "wip_limit": int(request.form.get("wip_limit") or 3),
                "xp_enabled": bool(request.form.get("xp_enabled")),
                "animations": bool(request.form.get("animations")),
                "session_mode": request.form.get("session_mode") or "mixed",
            }
        )
        flash("Órdenes del imperio actualizadas.", "success")
        return redirect(url_for("settings.view"))
    visual = {
        "day_night": (GameSetting.get("day_night", "true") or "true") != "false",
        "fog": (GameSetting.get("fog", "true") or "true") != "false",
        "sound_enabled": (GameSetting.get("sound_enabled", "false") or "false") == "true",
    }
    return render_template(
        "command/settings.html",
        empire=empire,
        xp=xp,
        visual=visual,
        world=WorldService.prefs(),
        last_backup=BackupService.last_ok(),
    )
