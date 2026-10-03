"""World extras: sessions, rest, fog, watch, chronicle, scenarios, patrols."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from app.extensions import db
from app.models import ExternalBlocker, Mission, MoneyMovement, Note, Opportunity, Project, TimeEntry
from app.models.constants import SPECIALTY_ROLE, SPECIALTY_SPRITE
from app.models.rpg import (
    BestiaryCase,
    CampaignChapter,
    ContactCard,
    CosmeticClaim,
    EvidenceItem,
    FogQuestion,
    Procedure,
    ProductionRecord,
    ProjectLink,
    RecurringItem,
    RestPeriod,
    Scenario,
    WorkSession,
)
from app.services.board_service import BoardService
from app.services.reward_service import RewardService
from app.services.world_service import WorldService


class RpgService:
    @staticmethod
    def construction_phase(project: Project) -> dict:
        primary = next((g for g in getattr(project, "goals", []) if g.is_primary), None)
        pct = primary.progress_pct() if primary else None
        if pct is None:
            return {"phase": "sin_definir", "label": "Pendiente de definir", "progress": None}
        if pct >= 100:
            phase, label = "completado", "Apertura completa"
        elif pct >= 75:
            phase, label = "apertura", "Apertura"
        elif pct >= 50:
            phase, label = "preparacion", "Preparación"
        elif pct >= 25:
            phase, label = "estructura", "Estructura"
        else:
            phase, label = "cimientos", "Cimientos"
        return {"phase": phase, "label": label, "progress": pct}

    @staticmethod
    def units_for(project: Project) -> list[dict]:
        units = []
        for m in project.missions:
            state = BoardService.state_of(m)
            if state not in {"active", "review", "waiting", "planned"}:
                continue
            activity = {"active": "work", "review": "review", "waiting": "wait", "planned": "idle"}[state]
            units.append(
                {
                    "mission_id": m.id,
                    "title": m.title,
                    "specialty": m.type,
                    "role": SPECIALTY_ROLE.get(m.type, "constructor"),
                    "sprite": SPECIALTY_SPRITE.get(m.type, "developer"),
                    "activity": activity,
                    "work_state": state,
                }
            )
        return units[:8]

    @staticmethod
    def specialties() -> list[dict]:
        return [
            {"type": key, "sprite": sprite, "role": SPECIALTY_ROLE.get(key, key), "required": False}
            for key, sprite in SPECIALTY_SPRITE.items()
        ]

    @staticmethod
    def start_session(mission_id: int | None, project_id: int | None = None) -> WorkSession:
        open_row = WorkSession.query.filter_by(status="active").first()
        if open_row:
            return open_row
        row = WorkSession(mission_id=mission_id, project_id=project_id, status="active")
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def stop_session(session_id: int, summary: str = "", leftover: str = "", minutes: int | None = None) -> WorkSession:
        row = db.session.get(WorkSession, session_id)
        if not row:
            raise ValueError("Sesión no encontrada.")
        row.status = "done"
        row.ended_at = datetime.utcnow()
        if minutes is None and row.started_at:
            minutes = max(1, int((row.ended_at - row.started_at).total_seconds() // 60))
            if minutes > 12 * 60:
                minutes = 0
                leftover = leftover or "La sesión quedó abierta demasiado tiempo; corrige los minutos."
        row.minutes = int(minutes or 0)
        row.summary = summary or ""
        row.leftover = leftover or ""
        if row.minutes and row.mission_id:
            db.session.add(
                TimeEntry(
                    mission_id=row.mission_id,
                    project_id=row.project_id,
                    minutes=row.minutes,
                    local_date=WorldService.today(),
                    note=(summary or "Sesión de concentración")[:255],
                )
            )
        db.session.commit()
        return row

    @staticmethod
    def rest_on(day: date | None = None) -> RestPeriod | None:
        day = day or WorldService.today()
        return RestPeriod.query.filter(RestPeriod.starts_on <= day, RestPeriod.ends_on >= day).first()

    @staticmethod
    def add_rest(starts_on: date, ends_on: date, note: str = "") -> RestPeriod:
        row = RestPeriod(starts_on=starts_on, ends_on=ends_on, note=note[:255])
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def watch_alerts() -> list[dict]:
        today = WorldService.today()
        alerts = []
        rest = RpgService.rest_on(today)
        if rest:
            alerts.append(
                {
                    "rule": "rest",
                    "title": "Periodo de descanso",
                    "detail": rest.note or f"Hasta {rest.ends_on.isoformat()}",
                    "action": "Los recordatorios de capacidad se reducen; no se pierden logros.",
                }
            )
        for m in Mission.query.filter_by(work_state="waiting").all():
            if m.wait_review_on and m.wait_review_on <= today:
                alerts.append(
                    {
                        "rule": "wait_review",
                        "title": f"Seguimiento: {m.title}",
                        "detail": m.wait_reason or "Espera externa",
                        "mission_id": m.id,
                        "action": "Registrar si llegó respuesta; no se asume desbloqueo.",
                    }
                )
        for b in ExternalBlocker.query.filter_by(status="open").all():
            if b.review_on and b.review_on <= today:
                alerts.append(
                    {
                        "rule": "blocker",
                        "title": b.reason,
                        "mission_id": b.mission_id,
                        "action": "Revisar el bloqueo.",
                    }
                )
        for o in Opportunity.query.filter(Opportunity.status.notin_(["WON", "LOST"])).all():
            if o.next_action_date and o.next_action_date <= today:
                alerts.append(
                    {
                        "rule": "opportunity_follow",
                        "title": o.name,
                        "detail": o.next_action or "Seguimiento comercial",
                        "action": "Abrir la oportunidad; no hay cobro automático.",
                    }
                )
        stale = datetime.utcnow() - timedelta(days=10)
        for m in Mission.query.filter(Mission.work_state.in_(["todo", "planned", "active"])).all():
            if m.created_at and m.created_at < stale and not m.planned_date:
                alerts.append(
                    {
                        "rule": "stale_task",
                        "title": m.title,
                        "mission_id": m.id,
                        "action": "Replanificar, esperar o archivar.",
                    }
                )
        for mv in MoneyMovement.query.filter_by(status="pending", direction="in").all():
            alerts.append(
                {
                    "rule": "receivable",
                    "title": mv.concept,
                    "detail": f"{mv.amount_cents / 100:.2f} {mv.currency} pendiente",
                    "action": "Registrar cobro parcial o total cuando ocurra.",
                }
            )
        return alerts[:20]

    @staticmethod
    def minimap() -> dict:
        cities = []
        for p in Project.query.filter(Project.status != "ARCHIVED").all():
            cities.append(
                {
                    "id": p.id,
                    "name": p.name,
                    "x": p.map_x,
                    "y": p.map_y,
                    "district": p.category or "general",
                    "blocked": any(m.is_blocked() for m in p.missions if m.status in {"OPEN", "IN_PROGRESS"}),
                    "due": any(m.due_date and m.due_date <= WorldService.today() for m in p.missions if m.status != "DONE"),
                    "active": any(BoardService.state_of(m) in {"active", "review"} for m in p.missions),
                    "rally": WorldService.prefs().get("rally_project_id") == p.id,
                }
            )
        return {"cities": cities, "alerts": RpgService.watch_alerts()[:6]}

    @staticmethod
    def set_rally(project_id: int | None, until: str | None = None) -> dict:
        WorldService.save({"rally_project_id": project_id, "rally_until": until})
        return {"rally_project_id": project_id, "rally_until": until}

    @staticmethod
    def ensure_patrols() -> list[dict]:
        today = WorldService.today()
        week = WorldService.week_start_date().isoformat()
        wanted = [
            ("backup", "weekly", "Patrulla de respaldo", week),
            ("review", "weekly", "Patrulla de revisión", week),
        ]
        created = []
        for kind, cadence, title, period in wanted:
            exists = RecurringItem.query.filter_by(kind=kind, period_key=period, anchor_id=0).first()
            if exists:
                created.append(exists.to_dict())
                continue
            row = RecurringItem(
                kind=kind,
                title=title,
                cadence=cadence,
                anchor_id=0,
                period_key=period,
                due_on=today,
            )
            db.session.add(row)
            db.session.commit()
            created.append(row.to_dict())
        return created

    @staticmethod
    def complete_patrol(item_id: int, result: str = "") -> RecurringItem:
        row = db.session.get(RecurringItem, item_id)
        if not row:
            raise ValueError("Patrulla no encontrada.")
        row.status = "done"
        row.result = result[:500]
        db.session.commit()
        return row

    @staticmethod
    def add_fog(question: str, project_id: int | None = None, action: str = "") -> FogQuestion:
        row = FogQuestion(question=question[:255], project_id=project_id, action=action[:255])
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def clear_fog(fog_id: int, answer: str) -> FogQuestion:
        row = db.session.get(FogQuestion, fog_id)
        if not row:
            raise ValueError("Pregunta no encontrada.")
        row.status = "answered"
        row.answer = answer
        row.resolved_at = datetime.utcnow()
        db.session.commit()
        return row

    @staticmethod
    def simulate(title: str, weekly_minutes: int | None) -> Scenario:
        planned = WorldService.planned_minutes_this_week()
        cap = weekly_minutes if weekly_minutes is not None else WorldService.weekly_capacity_minutes()
        unknown = Mission.query.filter(
            Mission.status.in_(["OPEN", "IN_PROGRESS"]), Mission.estimated_minutes.is_(None)
        ).count()
        result = {
            "planned": planned,
            "capacity": cap,
            "overload": (planned - cap) if cap is not None else None,
            "unknown_estimates": unknown,
            "note": "Escenario de solo lectura. Nada se aplica al mundo.",
        }
        row = Scenario(
            title=title[:160] or "Escenario",
            patch_json=json.dumps({"weekly_minutes": weekly_minutes}),
            result_json=json.dumps(result, ensure_ascii=False),
            status="draft",
        )
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def discard_scenario(scenario_id: int) -> Scenario:
        row = db.session.get(Scenario, scenario_id)
        if not row:
            raise ValueError("Escenario no encontrado.")
        row.status = "discarded"
        db.session.commit()
        return row

    @staticmethod
    def chronicle(limit: int = 40) -> list[dict]:
        from app.models import GameEvent

        events = GameEvent.query.order_by(GameEvent.created_at.asc()).limit(limit).all()
        return [
            {
                **e.to_dict(),
                "readonly": True,
                "replays_do_not_write": True,
            }
            for e in events
        ]

    @staticmethod
    def advisors() -> dict:
        from app.services.daily_turn_service import DailyTurnService
        from app.services.finance_service import FinanceService

        money = FinanceService.totals()
        today = DailyTurnService.current() or {"items": [], "used": 0, "minutes": 30, "source": "none"}
        fog = FogQuestion.query.filter_by(status="open").all()
        notes = Note.query.order_by(Note.id.desc()).limit(5).all()
        return {
            "treasurer": {
                "summary": money.get("disclaimer"),
                "totals": money.get("currencies"),
                "source": "money_movements",
            },
            "captain": {
                "summary": f"Turno con {today.get('used')} min de {today.get('minutes')}.",
                "items": today.get("items"),
                "source": "daily_turn",
            },
            "librarian": {
                "summary": f"{Note.query.count()} recursos en almacén.",
                "items": [n.to_dict() for n in notes],
                "source": "notes",
            },
            "cartographer": {
                "summary": f"{FogQuestion.query.filter_by(status='open').count()} zonas de niebla abiertas.",
                "fog": [f.to_dict() for f in fog],
                "source": "fog_questions",
            },
            "ai": False,
        }

    @staticmethod
    def skill(name: str, payload: dict | None = None) -> dict:
        payload = payload or {}
        if name == "concentrate":
            session = RpgService.start_session(payload.get("mission_id"), payload.get("project_id"))
            return {"effect": "Sesión de concentración iniciada. El temporizador no completa la misión.", "session": session.to_dict()}
        if name == "clarity":
            mission = db.session.get(Mission, int(payload.get("mission_id") or 0))
            if not mission:
                raise ValueError("Elige una misión para partir.")
            parts = [p.strip() for p in (mission.title.replace(" y ", ",").split(",")) if p.strip()]
            return {
                "effect": "Propuesta de división. Nada se crea hasta que confirmes.",
                "parts": parts[:5] or [mission.title],
                "mission_id": mission.id,
            }
        if name == "reorganize":
            return {
                "effect": "Sugerencia de cola por prioridad. No reordena hasta confirmar.",
                "queues": BoardService.queues(),
            }
        raise ValueError("Habilidad desconocida.")

    @staticmethod
    def add_production(mission_id: int, quantity: int, unit: str = "", note: str = "", key: str | None = None) -> ProductionRecord:
        if key and ProductionRecord.query.filter_by(source_key=key).first():
            return ProductionRecord.query.filter_by(source_key=key).first()
        rec = ProductionRecord(
            mission_id=mission_id,
            quantity=int(quantity),
            unit=unit[:40],
            note=note[:255],
            source_key=key,
        )
        db.session.add(rec)
        mission = db.session.get(Mission, mission_id)
        if mission and mission.goal_id:
            from app.models import Goal

            goal = db.session.get(Goal, mission.goal_id)
            if goal and goal.kind == "numeric":
                goal.current_value = (goal.current_value or 0) + int(quantity)
        db.session.commit()
        return rec

    @staticmethod
    def claim_cosmetic(code: str, title: str) -> dict:
        existing = CosmeticClaim.query.filter_by(code=code).first()
        if existing:
            return {"duplicate": True, "claim": {"code": existing.code, "title": existing.title, "status": existing.status}}
        row = CosmeticClaim(code=code[:80], title=title[:160], status="claimed")
        db.session.add(row)
        db.session.commit()
        return {"duplicate": False, "claim": {"code": row.code, "title": row.title, "status": row.status}}
