from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.extensions import db
from app.models import Empire, GameSetting, Project
from app.services.game_service import GameService

logger = logging.getLogger(__name__)

DEFAULT_WORLD = {
    "version": 1,
    "onboarding_done": False,
    "usage_type": "mix",
    "language": "es",
    "timezone": "UTC",
    "week_start": 0,
    "currency": "USD",
    "weekly_minutes": None,
    "capacity": {"0": 60, "1": 60, "2": 60, "3": 60, "4": 60, "5": 0, "6": 0},
    "rest_days": [5, 6],
    "gamification": "balanced",
    "animations": True,
    "xp_enabled": True,
    "quiet_hours": None,
    "demo_loaded": False,
    "tour_done": False,
    "wip_limit": 3,
    "session_mode": "mixed",
    "rally_project_id": None,
    "rally_until": None,
    "guild_enabled": False,
    "commander_name": "",
    "commander_class": "mixed",
    "avatar": "default",
    "column_labels": {},
    "daily_minutes": 30,
}


class WorldService:
    @staticmethod
    def prefs() -> dict:
        raw = GameSetting.get("world")
        data = dict(DEFAULT_WORLD)
        if raw:
            try:
                data.update(json.loads(raw))
            except (json.JSONDecodeError, TypeError):
                pass
        return data

    @staticmethod
    def save(patch: dict) -> dict:
        data = WorldService.prefs()
        data.update({k: v for k, v in patch.items() if k in DEFAULT_WORLD or k in patch})
        GameSetting.set("world", json.dumps(data, ensure_ascii=False))
        return data

    @staticmethod
    def today() -> date:
        tz_name = WorldService.prefs().get("timezone") or "UTC"
        try:
            tz = ZoneInfo(tz_name)
            return datetime.now(tz).date()
        except Exception:
            logger.warning("zona horaria %s no disponible; se usa UTC", tz_name)
            return datetime.now(timezone.utc).date()

    @staticmethod
    def needs_onboarding() -> bool:
        data = WorldService.prefs()
        if data.get("onboarding_done"):
            return False
        if Project.query.first() is not None:
            WorldService.save({"onboarding_done": True})
            return False
        return True

    @staticmethod
    def ensure_empire() -> Empire:
        empire = GameService.get_empire()
        WorldService.sanitize_legacy_demo()
        return empire

    @staticmethod
    def sanitize_legacy_demo() -> None:
        """Hook for local databases. Does not encode any third-party brand names."""
        return

    @staticmethod
    def weekly_capacity_minutes() -> int | None:
        data = WorldService.prefs()
        if data.get("weekly_minutes") is not None:
            return int(data["weekly_minutes"])
        cap = data.get("capacity") or {}
        total = sum(int(cap.get(str(i), cap.get(i, 0)) or 0) for i in range(7))
        if not total:
            return None
        try:
            from app.models.rpg import RestPeriod

            today = WorldService.today()
            rest = RestPeriod.query.filter(RestPeriod.starts_on <= today, RestPeriod.ends_on >= today).first()
            if rest:
                return max(0, int(total * 0.25))
        except Exception:
            pass
        return total

    @staticmethod
    def planned_minutes_this_week() -> int:
        from app.models import Mission

        start = WorldService.week_start_date()
        end = start + timedelta(days=7)
        total = 0
        for m in Mission.query.filter(Mission.status.in_(["OPEN", "IN_PROGRESS"])).all():
            if m.planned_date and start <= m.planned_date < end:
                if m.estimated_minutes is None:
                    continue
                total += int(m.estimated_minutes)
        return total

    @staticmethod
    def week_start_date() -> date:
        today = WorldService.today()
        start_weekday = int(WorldService.prefs().get("week_start") or 0)
        delta = (today.weekday() - start_weekday) % 7
        return today - timedelta(days=delta)
