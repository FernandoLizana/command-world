from __future__ import annotations

import json
from datetime import date, timedelta

from app.extensions import db
from app.models import DailyTurn, Mission, Project
from app.services.world_service import WorldService


def _estimate(mission: Mission) -> int | None:
    if mission.estimated_minutes is not None:
        return int(mission.estimated_minutes)
    return None


class DailyTurnService:
    @staticmethod
    def suggest(minutes: int) -> dict:
        today = WorldService.today()
        existing = DailyTurn.query.filter_by(local_date=today).first()
        if existing and existing.status in {"accepted", "active"} and existing.minutes_budget == minutes:
            return DailyTurnService._view(existing)

        candidates = (
            Mission.query.filter(Mission.status.in_(["OPEN", "IN_PROGRESS"]))
            .order_by(Mission.priority.asc(), Mission.due_date.asc())
            .all()
        )
        picked: list[dict] = []
        used = 0
        seen_projects: set[int] = set()
        skipped = []
        for m in candidates:
            project = m.project
            if project is None or project.status in {"PAUSED", "ARCHIVED"}:
                continue
            if m.is_blocked():
                skipped.append({"id": m.id, "reason": "Bloqueada hasta resolver una dependencia o espera."})
                continue
            est = _estimate(m)
            if est is None:
                item = DailyTurnService._item(m, None, "Sin estimar: no cuenta en el presupuesto.")
                if len(picked) < 3:
                    picked.append(item)
                continue
            if used + est > minutes:
                skipped.append(
                    {
                        "id": m.id,
                        "reason": f"Requiere {est} min y solo quedan {minutes - used} min.",
                    }
                )
                continue
            mode = WorldService.prefs().get("session_mode") or "mixed"
            if mode == "light" and est > 25:
                skipped.append({"id": m.id, "reason": "Modo ligero: esta tarea pide más de 25 min."})
                continue
            if mode == "focus" and project.id in seen_projects:
                continue
            if project.id in seen_projects and len(picked) >= 1:
                # keep critical due dates anyway
                if not (m.due_date and m.due_date <= today + timedelta(days=1)):
                    continue
            reason = DailyTurnService._reason(m, today)
            picked.append(DailyTurnService._item(m, est, reason))
            used += est
            seen_projects.add(project.id)
            if len([p for p in picked if p.get("minutes")]) >= 3:
                break

        payload = {
            "minutes": minutes,
            "used": used,
            "remaining": max(0, minutes - used),
            "items": picked[:3],
            "skipped": skipped[:8],
            "overload_week": DailyTurnService._week_overload(),
            "follow_ups": DailyTurnService._follow_ups(today),
        }
        if existing:
            existing.minutes_budget = minutes
            existing.payload_json = json.dumps(payload, ensure_ascii=False)
            existing.status = "draft"
            db.session.commit()
            turn = existing
        else:
            turn = DailyTurn(
                local_date=today,
                minutes_budget=minutes,
                payload_json=json.dumps(payload, ensure_ascii=False),
                status="draft",
            )
            db.session.add(turn)
            db.session.commit()
        return DailyTurnService._view(turn)

    @staticmethod
    def accept(turn_id: int | None = None) -> dict:
        today = WorldService.today()
        turn = db.session.get(DailyTurn, turn_id) if turn_id else DailyTurn.query.filter_by(local_date=today).first()
        if not turn:
            return {"error": "no turn"}
        turn.status = "accepted"
        db.session.commit()
        return DailyTurnService._view(turn)

    @staticmethod
    def current() -> dict | None:
        turn = DailyTurn.query.filter_by(local_date=WorldService.today()).first()
        if not turn:
            return None
        return DailyTurnService._view(turn)

    @staticmethod
    def _follow_ups(today: date) -> list[dict]:
        from app.models import Opportunity

        out = []
        for o in Opportunity.query.filter(Opportunity.status.notin_(["WON", "LOST"])).all():
            if o.next_action_date and o.next_action_date <= today + timedelta(days=1):
                out.append(
                    {
                        "opportunity_id": o.id,
                        "title": o.next_action or o.name,
                        "project": o.project.name if o.project else "",
                        "reason": "Seguimiento comercial con fecha próxima.",
                        "due_date": o.next_action_date.isoformat(),
                    }
                )
        return out[:3]

    @staticmethod
    def _week_overload() -> dict:
        cap = WorldService.weekly_capacity_minutes()
        planned = WorldService.planned_minutes_this_week()
        if cap is None:
            return {"capacity": None, "planned": planned, "overload": None}
        return {"capacity": cap, "planned": planned, "overload": max(0, planned - cap)}

    @staticmethod
    def _reason(m: Mission, today: date) -> str:
        if m.due_date:
            delta = (m.due_date - today).days
            if delta <= 0:
                return "Vence hoy o ya venció."
            if delta == 1:
                return "Vence mañana y desbloquea trabajo posterior."
            return f"Vence en {delta} días (prioridad {m.priority})."
        if m.priority <= 2:
            return f"Prioridad alta indicada por ti (P{m.priority})."
        return "Siguiente acción abierta de un proyecto activo."

    @staticmethod
    def _item(m: Mission, minutes: int | None, reason: str) -> dict:
        return {
            "mission_id": m.id,
            "title": m.title,
            "project": m.project.name if m.project else "",
            "project_id": m.project_id,
            "minutes": minutes,
            "unestimated": minutes is None,
            "reason": reason,
            "due_date": m.due_date.isoformat() if m.due_date else None,
        }

    @staticmethod
    def _view(turn: DailyTurn) -> dict:
        payload = json.loads(turn.payload_json or "{}")
        return {
            "id": turn.id,
            "date": turn.local_date.isoformat(),
            "status": turn.status,
            **payload,
        }
