"""Board transitions, WIP slots and mission queues. One source: Mission."""

from __future__ import annotations

from datetime import date, datetime

from app.extensions import db
from app.models import Mission
from app.models.constants import WORK_STATE_TO_STATUS, WORK_STATES
from app.services.event_service import EventService
from app.services.world_service import WorldService

ACTIVE_STATES = {"active", "review"}
ALLOWED = {
    "idea": {"todo", "cancelled"},
    "todo": {"idea", "planned", "active", "waiting", "cancelled"},
    "planned": {"todo", "active", "cancelled"},
    "active": {"waiting", "review", "done", "todo", "cancelled"},
    "waiting": {"todo", "active", "cancelled"},
    "review": {"active", "done", "cancelled"},
    "done": {"todo", "archived"},
    "cancelled": {"todo", "archived"},
    "archived": {"todo"},
}


class BoardError(ValueError):
    pass


class BoardService:
    @staticmethod
    def state_of(mission: Mission) -> str:
        raw = (getattr(mission, "work_state", None) or "").strip()
        if raw in WORK_STATES:
            return raw
        return {
            "OPEN": "todo",
            "IN_PROGRESS": "active",
            "DONE": "done",
            "CANCELLED": "cancelled",
        }.get(mission.status, "todo")

    @staticmethod
    def sync_status(mission: Mission, work_state: str) -> None:
        if work_state == "archived":
            if mission.status != "DONE":
                mission.status = "CANCELLED"
            return
        mission.status = WORK_STATE_TO_STATUS.get(work_state, "OPEN")

    @staticmethod
    def active_count(exclude_id: int | None = None) -> int:
        q = Mission.query.filter(Mission.work_state.in_(tuple(ACTIVE_STATES)))
        if exclude_id:
            q = q.filter(Mission.id != exclude_id)
        return q.count()

    @staticmethod
    def wip_limit() -> int:
        raw = WorldService.prefs().get("wip_limit", 3)
        try:
            return max(1, min(20, int(raw)))
        except (TypeError, ValueError):
            return 3

    @staticmethod
    def ensure_capacity(mission: Mission, to_state: str) -> None:
        if to_state not in ACTIVE_STATES:
            return
        current = BoardService.state_of(mission)
        if current in ACTIVE_STATES:
            return
        limit = BoardService.wip_limit()
        used = BoardService.active_count(exclude_id=mission.id)
        if used >= limit:
            actives = (
                Mission.query.filter(Mission.work_state.in_(tuple(ACTIVE_STATES)))
                .order_by(Mission.priority.asc())
                .limit(12)
                .all()
            )
            names = ", ".join(m.title for m in actives) or "otras órdenes"
            raise BoardError(
                f"Límite de trabajo simultáneo ({limit}). Ahora están activas: {names}. "
                "Termina, pasa a espera o cambia el límite en Ajustes."
            )

    @staticmethod
    def transition(
        mission: Mission,
        to_state: str,
        *,
        version: int | None = None,
        wait_reason: str = "",
        wait_review_on: date | None = None,
        done_criteria: str | None = None,
        next_action: str | None = None,
        commit: bool = True,
        skip_rewards: bool = False,
    ) -> dict:
        if to_state not in WORK_STATES:
            raise BoardError(f"Estado no válido: {to_state}")
        current = BoardService.state_of(mission)
        if version is not None and int(mission.version or 1) != int(version):
            raise BoardError("La tarjeta cambió en otra vista. Recarga antes de moverla.")
        if to_state != current and to_state not in ALLOWED.get(current, set()):
            raise BoardError(f"No se puede pasar de {current} a {to_state}.")
        if to_state == "active" and mission.is_blocked():
            raise BoardError("Hay una dependencia o espera abierta. No se inicia por estar primero en la cola.")
        if to_state == "waiting" and not (wait_reason or mission.wait_reason):
            raise BoardError("Indica el motivo de la espera.")
        BoardService.ensure_capacity(mission, to_state)
        if done_criteria is not None:
            mission.done_criteria = done_criteria
        if next_action is not None:
            mission.next_action = next_action[:255]
        if to_state == "waiting":
            mission.wait_reason = (wait_reason or mission.wait_reason or "")[:255]
            mission.wait_review_on = wait_review_on or mission.wait_review_on
        was_done = current == "done"
        mission.work_state = to_state
        BoardService.sync_status(mission, to_state)
        mission.version = int(mission.version or 1) + 1
        if to_state == "done" and not was_done:
            mission.completed_at = datetime.utcnow()
            for obj in mission.objectives:
                obj.completed = True
        if to_state == "todo" and was_done:
            mission.completed_at = None
        granted = {"xp": 0, "duplicate": False}
        if to_state == "done" and not was_done and not skip_rewards:
            from app.services.reward_service import RewardService

            granted = RewardService.grant_mission_complete(mission)
        EventService.emit(
            f"Orden {to_state}: {mission.title}",
            description=mission.wait_reason if to_state == "waiting" else (mission.next_action or ""),
            kind="success" if to_state == "done" else "info",
            icon="fa-flag" if to_state == "planned" else "fa-scroll",
            project=mission.project,
            commit=False,
        )
        if commit:
            db.session.commit()
        return {"mission": mission.to_dict(), "reward": granted}

    @staticmethod
    def move_project(mission: Mission, project_id: int, *, confirm: bool = False) -> Mission:
        from app.models import Project
        from app.services.coop_service import CoopService

        project = db.session.get(Project, int(project_id))
        if not project:
            raise BoardError("Edificio de destino no existe.")
        CoopService.require_write(project)
        if mission.project_id == project.id:
            return mission
        if mission.goal_id and not confirm:
            raise BoardError("Esta orden está ligada a un objetivo. Confirma la reasignación.")
        mission.project_id = project.id
        if mission.goal_id:
            mission.goal_id = None
        mission.version = int(mission.version or 1) + 1
        db.session.commit()
        return mission

    @staticmethod
    def reorder(project_id: int, ordered_ids: list[int]) -> list[Mission]:
        missions = Mission.query.filter_by(project_id=project_id).all()
        by_id = {m.id: m for m in missions}
        for i, mid in enumerate(ordered_ids):
            row = by_id.get(int(mid))
            if row:
                row.queue_position = i
                row.version = int(row.version or 1) + 1
        db.session.commit()
        return sorted(missions, key=lambda m: (m.queue_position or 0, m.priority or 9, m.id))

    @staticmethod
    def update_card(mission: Mission, payload: dict) -> Mission:
        if payload.get("version") is not None and int(mission.version or 1) != int(payload["version"]):
            raise BoardError("La tarjeta cambió en otra vista. Recarga antes de editarla.")
        if "title" in payload and str(payload["title"]).strip():
            mission.title = str(payload["title"]).strip()[:200]
        if "next_action" in payload:
            mission.next_action = str(payload.get("next_action") or "")[:255]
        if "done_criteria" in payload:
            mission.done_criteria = str(payload.get("done_criteria") or "")
        if "estimated_minutes" in payload:
            raw = payload.get("estimated_minutes")
            mission.estimated_minutes = None if raw in (None, "") else int(raw)
        if payload.get("planned_date"):
            mission.planned_date = date.fromisoformat(str(payload["planned_date"]))
        if "planned_date" in payload and not payload.get("planned_date"):
            mission.planned_date = None
        if payload.get("type"):
            mission.type = str(payload["type"])[:40]
        if payload.get("goal_id") in (None, "", 0):
            if "goal_id" in payload:
                mission.goal_id = None
        elif payload.get("goal_id"):
            mission.goal_id = int(payload["goal_id"])
        mission.version = int(mission.version or 1) + 1
        db.session.commit()
        return mission

    @staticmethod
    def bulk(mission_ids: list[int], to_state: str, extra: dict | None = None) -> dict:
        extra = extra or {}
        applied = []
        rejected = []
        for mid in mission_ids:
            mission = db.session.get(Mission, int(mid))
            if not mission:
                rejected.append({"id": mid, "error": "no encontrada"})
                continue
            try:
                BoardService.transition(
                    mission,
                    to_state,
                    wait_reason=extra.get("wait_reason") or "",
                    commit=False,
                )
                applied.append(mission.id)
            except BoardError as exc:
                rejected.append({"id": mission.id, "title": mission.title, "error": str(exc)})
        db.session.commit()
        return {"applied": applied, "rejected": rejected}

    @staticmethod
    def advance(mission: Mission) -> dict:
        """Continue: start if idle, complete next objective, or finish."""
        state = BoardService.state_of(mission)
        if state == "done":
            return {
                "ok": True,
                "completed_mission": True,
                "already": True,
                "mission": mission.to_dict(),
                "xp": 0,
            }
        if state in {"idea", "todo", "planned", "waiting"}:
            packed = BoardService.transition(mission, "active")
            return {
                "ok": True,
                "completed_mission": False,
                "started": True,
                "mission": packed["mission"],
                "xp": 0,
            }
        nxt = next((o for o in mission.objectives if not o.completed), None)
        if nxt:
            nxt.completed = True
            if state != "active":
                BoardService.ensure_capacity(mission, "active")
                mission.work_state = "active"
                BoardService.sync_status(mission, "active")
            from app.services.reward_service import RewardService

            granted = RewardService.grant(
                f"objective:{nxt.id}:complete",
                kind="xp",
                amount=1,
                source="objective",
                entity_type="objective",
                entity_id=nxt.id,
                project=mission.project,
                description=nxt.description,
            )
            all_done = all(o.completed for o in mission.objectives)
            result = {
                "ok": True,
                "completed_mission": False,
                "step": nxt.description,
                "mission": mission.to_dict(),
                "xp": granted.get("amount") if granted.get("granted") else 0,
            }
            if all_done:
                packed = BoardService.transition(mission, "done", commit=True)
                result["completed_mission"] = True
                result["mission"] = packed["mission"]
                result["xp"] = (result["xp"] or 0) + ((packed.get("reward") or {}).get("amount") or 0)
            else:
                db.session.commit()
            return result
        packed = BoardService.transition(mission, "done")
        return {
            "ok": True,
            "completed_mission": True,
            "step": mission.title,
            "mission": packed["mission"],
            "xp": (packed.get("reward") or {}).get("amount") or 0,
        }

    @staticmethod
    def board_payload(project_id: int | None = None) -> dict:
        q = Mission.query
        if project_id:
            q = q.filter_by(project_id=int(project_id))
        else:
            q = q.filter(Mission.work_state != "archived")
        items = q.order_by(Mission.queue_position.asc(), Mission.priority.asc()).all()
        columns = {state: [] for state in WORK_STATES if state != "archived"}
        for m in items:
            state = BoardService.state_of(m)
            if state == "archived":
                continue
            columns.setdefault(state, []).append(m.to_dict())
        labels = WorldService.prefs().get("column_labels") or {}
        return {
            "columns": columns,
            "labels": {
                "idea": labels.get("idea") or "Idea",
                "todo": labels.get("todo") or "Por hacer",
                "planned": labels.get("planned") or "Planificada",
                "active": labels.get("active") or "En curso",
                "waiting": labels.get("waiting") or "En espera",
                "review": labels.get("review") or "En revisión",
                "done": labels.get("done") or "Terminada",
                "cancelled": labels.get("cancelled") or "Cancelada",
            },
            "wip": {"used": BoardService.active_count(), "limit": BoardService.wip_limit()},
            "queue": BoardService.queues(project_id),
        }

    @staticmethod
    def queues(project_id: int | None = None) -> list[dict]:
        from app.models import Project

        projects = [db.session.get(Project, int(project_id))] if project_id else Project.query.filter(
            Project.status != "ARCHIVED"
        ).all()
        out = []
        for project in projects:
            if not project:
                continue
            missions = sorted(
                [m for m in project.missions if BoardService.state_of(m) not in {"done", "cancelled", "archived"}],
                key=lambda m: (m.queue_position or 0, m.priority or 9, m.id),
            )
            out.append(
                {
                    "project_id": project.id,
                    "name": project.name,
                    "items": [
                        {
                            "id": m.id,
                            "title": m.title,
                            "work_state": BoardService.state_of(m),
                            "estimated_minutes": m.estimated_minutes,
                            "blocked": m.is_blocked(),
                            "next_action": m.next_action or "",
                        }
                        for m in missions
                    ],
                }
            )
        return out
