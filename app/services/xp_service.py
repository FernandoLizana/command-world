from __future__ import annotations

import logging
from datetime import datetime, timedelta

from app.extensions import db
from app.models import ActivityLog, GameSetting, Project

logger = logging.getLogger(__name__)


class XPService:
    """Configurable XP awards. Values live in game_settings.xp_rewards."""

    @staticmethod
    def reward_for(action: str) -> int:
        return int(GameSetting.xp_rewards().get(action, 0))

    @staticmethod
    def award(
        action: str,
        *,
        project: Project | None = None,
        description: str = "",
        extra_xp: int | None = None,
        metadata: str = "{}",
    ) -> int:
        from app.services.world_service import WorldService

        prefs = WorldService.prefs()
        if prefs.get("xp_enabled") is False:
            xp = 0
        else:
            xp = extra_xp if extra_xp is not None else XPService.reward_for(action)
        if description:
            dup = ActivityLog.query.filter_by(
                action_type=action, description=description or action, xp=xp
            ).order_by(ActivityLog.id.desc()).first()
            if dup and (datetime.utcnow() - (dup.created_at or datetime.utcnow())) < timedelta(seconds=4):
                return 0
        if project is not None:
            project.xp = (project.xp or 0) + xp
            project.last_activity = datetime.utcnow()
            project.updated_at = datetime.utcnow()
        log = ActivityLog(
            project_id=project.id if project else None,
            action_type=action,
            description=description or action,
            xp=xp,
            metadata_json=metadata,
        )
        db.session.add(log)
        logger.info("XP %+d via %s (%s)", xp, action, description)
        return xp
