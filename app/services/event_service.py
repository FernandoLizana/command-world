from __future__ import annotations

import logging
from datetime import datetime

from app.extensions import db
from app.models import GameEvent, Project

logger = logging.getLogger(__name__)


class EventService:
    @staticmethod
    def emit(
        title: str,
        *,
        description: str = "",
        kind: str = "info",
        icon: str = "fa-flag",
        project: Project | None = None,
        commit: bool = True,
    ) -> GameEvent:
        event = GameEvent(
            title=title,
            description=description,
            kind=kind,
            icon=icon,
            project_id=project.id if project else None,
        )
        db.session.add(event)
        if commit:
            db.session.commit()
        return event

    @staticmethod
    def recent(limit: int = 12) -> list[GameEvent]:
        return GameEvent.query.order_by(GameEvent.created_at.desc()).limit(limit).all()

    @staticmethod
    def inactivity_scan() -> list[GameEvent]:
        created: list[GameEvent] = []
        now = datetime.utcnow()
        for project in Project.query.filter(Project.status.in_(["ACTIVE", "EXPERIMENT"])).all():
            if not project.last_activity:
                continue
            days = (now - project.last_activity).days
            if days < 7:
                continue
            exists = (
                GameEvent.query.filter(
                    GameEvent.project_id == project.id,
                    GameEvent.kind == "warning",
                    GameEvent.title.like("%sin seguimiento%"),
                )
                .order_by(GameEvent.created_at.desc())
                .first()
            )
            if exists and exists.created_at and (now - exists.created_at).days < 3:
                continue
            created.append(
                EventService.emit(
                    f"{project.name} — {days} días sin seguimiento",
                    description="Bajo momentum por inactividad.",
                    kind="warning",
                    icon="fa-triangle-exclamation",
                    project=project,
                    commit=False,
                )
            )
        if created:
            db.session.commit()
        return created
