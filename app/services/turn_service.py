from __future__ import annotations

import json
import logging
from datetime import datetime

from app.extensions import db
from app.models import Empire, Mission, Project, TurnLog
from app.services.event_service import EventService
from app.services.game_service import GameService
from app.services.metrics_service import MetricsService
from app.services.xp_service import XPService

logger = logging.getLogger(__name__)


class TurnService:
    """A turn is a visual day. Ending a turn never blocks further actions."""

    @staticmethod
    def current() -> dict:
        empire = GameService.get_empire()
        last = TurnLog.query.order_by(TurnLog.turn_number.desc()).first()
        missions = (
            Mission.query.filter(Mission.status.in_(["OPEN", "IN_PROGRESS"]))
            .order_by(Mission.priority.asc(), Mission.due_date.asc())
            .limit(3)
            .all()
        )
        return {
            "turn": empire.current_turn,
            "date": datetime.utcnow().strftime("%d %B %Y"),
            "hours": empire.available_hours,
            "priority_missions": [m.to_dict() for m in missions],
            "last_summary": last.summary if last else "",
        }

    @staticmethod
    def end_turn(hours_spent: float = 0) -> TurnLog:
        empire = GameService.get_empire()
        MetricsService.refresh_all()
        xp = XPService.award("end_turn", description=f"Fin de turno {empire.current_turn}")
        empire.xp += xp

        inactivity = EventService.inactivity_scan()
        recommendations = TurnService._recommend()
        summary = TurnService._build_summary(empire, recommendations, inactivity)

        log = TurnLog(
            turn_number=empire.current_turn,
            ended_at=datetime.utcnow(),
            hours_available=empire.available_hours,
            hours_spent=hours_spent,
            xp_gained=xp,
            summary=summary,
            events_json=json.dumps([e.title for e in inactivity], ensure_ascii=False),
            recommendations_json=json.dumps(recommendations, ensure_ascii=False),
        )
        db.session.add(log)

        EventService.emit(
            f"Turno {empire.current_turn} finalizado",
            description=summary,
            kind="turn",
            icon="fa-hourglass-end",
        )

        empire.current_turn += 1
        empire.last_turn_at = datetime.utcnow()
        empire.available_hours = 8.0
        db.session.commit()
        logger.info("Ended turn %s", log.turn_number)
        return log

    @staticmethod
    def _recommend() -> list[str]:
        ranked = (
            Project.query.filter(Project.status.in_(["ACTIVE", "EXPERIMENT", "BLOCKED"]))
            .order_by(Project.priority.asc(), Project.momentum.desc())
            .limit(3)
            .all()
        )
        lines = []
        for p in ranked:
            if p.status == "BLOCKED":
                lines.append(f"Desbloquear {p.name} (momentum {p.momentum}%).")
            elif p.momentum < 30:
                lines.append(f"Reactivar {p.name}: {p.momentum}% momentum.")
            else:
                lines.append(f"Avanzar {p.name} (prioridad {p.priority}, momentum {p.momentum}%).")
        return lines

    @staticmethod
    def _build_summary(empire: Empire, recs: list[str], events) -> str:
        parts = [
            f"Turno {empire.current_turn} cerrado.",
            f"{len(events)} alerta(s) de inactividad.",
        ]
        if recs:
            parts.append("Próximo foco: " + recs[0])
        return " ".join(parts)
