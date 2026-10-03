"""Natural-language journal: capture, propose, apply. Rules first; IA optional."""

from __future__ import annotations

import json
import re
from datetime import date, timedelta

from app.extensions import db
from app.models import Mission, Opportunity, Project, TimeEntry
from app.models.rpg import Decree, JournalEntry
from app.services.board_service import BoardError, BoardService
from app.services.finance_service import FinanceService, parse_cents
from app.services.reward_service import RewardService
from app.services.world_service import WorldService


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def _relative_date(text: str, today: date) -> tuple[date | None, str | None]:
    t = _norm(text)
    if "hoy" in t:
        return today, "hoy"
    if "ayer" in t:
        return today - timedelta(days=1), "ayer"
    if "mañana" in t or "manana" in t:
        return today + timedelta(days=1), "mañana"
    if "próxima semana" in t or "proxima semana" in t:
        return today + timedelta(days=7 - today.weekday()), "la próxima semana"
    weekdays = ["lunes", "martes", "miércoles", "miercoles", "jueves", "viernes", "sábado", "sabado", "domingo"]
    for i, name in enumerate([0, 1, 2, 2, 3, 4, 5, 5, 6]):
        token = weekdays[i]
        if token in t:
            delta = (name - today.weekday()) % 7
            if delta == 0:
                delta = 7
            return today + timedelta(days=delta), token
    return None, None


def _minutes(text: str) -> int | None:
    match = re.search(r"(\d+)\s*(minutos|minuto|min)\b", _norm(text))
    if match:
        return int(match.group(1))
    return None


def _amount(text: str) -> int | None:
    match = re.search(r"(\d+(?:[.,]\d{1,2})?)", text.replace(" ", ""))
    if not match:
        match = re.search(r"(\d+(?:[.,]\d{1,2})?)", text)
    if not match:
        return None
    try:
        return parse_cents(match.group(1).replace(",", "."))
    except ValueError:
        return None


def _find_missions(fragment: str, project_id: int | None = None) -> list[Mission]:
    words = [w for w in re.findall(r"[a-záéíóúñ]{4,}", _norm(fragment)) if w not in {"para", "este", "esta", "como", "cuando"}]
    q = Mission.query
    if project_id:
        q = q.filter_by(project_id=project_id)
    found = []
    for m in q.order_by(Mission.id.desc()).limit(80).all():
        blob = _norm(m.title + " " + (m.description or ""))
        if any(w in blob for w in words):
            found.append(m)
    return found[:5]


class JournalService:
    @staticmethod
    def interpret(text: str, project_id: int | None = None) -> dict:
        raw = (text or "").strip()
        if not raw:
            raise ValueError("Escribe qué hiciste, qué intentas o qué decidiste.")
        today = WorldService.today()
        when, when_expr = _relative_date(raw, today)
        clauses = re.split(r"[.;\n]+|\s+y\s+", raw)
        clauses = [c.strip() for c in clauses if c.strip()]
        actions = []
        for i, clause in enumerate(clauses):
            actions.append(JournalService._clause(clause, i, project_id, when, when_expr))
        return {
            "original": raw,
            "effective_date": when.isoformat() if when else today.isoformat(),
            "date_expression": when_expr,
            "source": "rules",
            "actions": actions,
        }

    @staticmethod
    def _clause(clause: str, index: int, project_id: int | None, when: date | None, when_expr: str | None) -> dict:
        t = _norm(clause)
        action_id = f"a{index+1}"
        missions = _find_missions(clause, project_id)
        mission = missions[0] if len(missions) == 1 else None
        candidates = [{"id": m.id, "title": m.title, "project_id": m.project_id} for m in missions]
        missing = []
        if not mission and missions:
            missing.append("Hay varias misiones posibles; elige una.")
        base = {
            "id": action_id,
            "text": clause,
            "status": "ready" if mission or "pag" in t or "decid" in t else "needs_info",
            "mission_id": mission.id if mission else None,
            "candidates": candidates,
            "effective_date": when.isoformat() if when else None,
            "date_expression": when_expr,
            "fields": {},
        }
        if re.search(r"\bno\b|\btodavía no\b|\bainda no\b|\baún no\b|\baun no\b", t) and re.search(
            r"termin|comple|entreg", t
        ):
            base.update({"type": "keep_pending", "label": "Mantener pendiente (no es un resultado)"})
            if not mission:
                missing.append("Indica qué misión sigue pendiente.")
            base["missing"] = missing
            base["status"] = "ready" if mission else "needs_info"
            return base
        if re.search(r"si (aprueb|confirm|acept|me confirman)", t) and "pagar" not in t:
            base.update({"type": "condition", "label": "Condición o idea, sin gasto ni cobro"})
            base["status"] = "ready"
            return base
        if "me pagarán" in t or "me pagaran" in t or "me deberán" in t or "me deberan" in t:
            cents = _amount(clause)
            base.update(
                {
                    "type": "expect_payment",
                    "label": "Cuenta por cobrar (no es dinero recibido)",
                    "fields": {"amount_cents": cents, "status": "pending", "direction": "in"},
                }
            )
            if cents is None:
                missing.append("Falta el importe.")
            base["missing"] = missing
            base["status"] = "ready" if cents else "needs_info"
            return base
        if re.search(r"recib[ií]|cobr[eé]|me pagaron", t):
            cents = _amount(clause)
            base.update(
                {
                    "type": "receive_money",
                    "label": "Cobro efectivo o parcial",
                    "fields": {"amount_cents": cents, "status": "settled", "direction": "in"},
                }
            )
            if cents is None:
                missing.append("Falta el importe cobrado.")
            base["missing"] = missing
            base["status"] = "ready" if cents else "needs_info"
            return base
        if re.search(r"envi[eé].*(cotiz|propuest)", t) or "envié una cotización" in t:
            base.update({"type": "quote_sent", "label": "Cotización enviada (declaración del usuario)"})
            opps = Opportunity.query.filter(Opportunity.status.notin_(["WON", "LOST"])).all()
            if len(opps) == 1:
                base["fields"] = {"opportunity_id": opps[0].id, "name": opps[0].name}
                base["status"] = "ready"
            else:
                base["fields"] = {"opportunities": [{"id": o.id, "name": o.name} for o in opps[:8]]}
                missing.append("Selecciona la oportunidad o cotización.")
                base["status"] = "needs_info"
            if when:
                base["fields"]["follow_on"] = when.isoformat()
            base["missing"] = missing
            return base
        if re.search(r"decid[ií].*paus", t) or re.search(r"pausar este proyecto", t):
            base.update({"type": "decree_pause", "label": "Decreto: pausar proyecto"})
            if project_id:
                base["fields"] = {"project_id": project_id}
                base["status"] = "ready"
            else:
                missing.append("Indica qué proyecto pausar.")
                base["status"] = "needs_info"
            base["missing"] = missing
            return base
        if re.search(r"estudi[eé]|aprend[ií]", t):
            mins = _minutes(clause)
            base.update(
                {
                    "type": "study",
                    "label": "Práctica registrada (no certifica dominio)",
                    "fields": {"minutes": mins, "keep_example": "guard" in t or "ejemplo" in t},
                }
            )
            if mins is None:
                missing.append("Indica los minutos estudiados.")
            base["missing"] = missing
            base["status"] = "ready" if mins else "needs_info"
            return base
        if re.search(r"termin[eé]|complet[eé]|entregu[eé]", t):
            qty = re.search(r"(\d+)\s*(fotos|productos|piezas|unidades|informes)", t)
            base.update(
                {
                    "type": "complete",
                    "label": "Proponer completar un resultado",
                    "fields": {
                        "quantity": int(qty.group(1)) if qty else None,
                        "unit": qty.group(2) if qty else None,
                    },
                }
            )
            if not mission:
                missing.append("Vincula la misión concreta a terminar.")
            base["missing"] = missing
            base["status"] = "ready" if mission else "needs_info"
            return base
        if re.search(r"avanc[eé]|trabaj[eé]", t) or _minutes(clause):
            mins = _minutes(clause)
            base.update(
                {
                    "type": "log_time",
                    "label": "Registrar tiempo, resultado pendiente",
                    "fields": {"minutes": mins},
                }
            )
            if mins is None:
                missing.append("Indica los minutos.")
            if not mission:
                missing.append("Vincula la misión.")
            base["missing"] = missing
            base["status"] = "ready" if mins and mission else "needs_info"
            return base
        if re.search(r"voy a|planeo|preparar[eé]|mañana", t):
            base.update({"type": "plan", "label": "Intención: planificar, sin trabajo realizado"})
            base["status"] = "ready"
            return base
        base.update({"type": "note", "label": "Nota; clasifica a mano si hace falta"})
        base["status"] = "ready"
        return base

    @staticmethod
    def capture(text: str, project_id: int | None = None) -> JournalEntry:
        proposal = JournalService.interpret(text, project_id)
        row = JournalEntry(
            text=text.strip(),
            status="open",
            proposal_json=json.dumps(proposal, ensure_ascii=False),
            project_id=project_id,
        )
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def apply(entry: JournalEntry, accepted_ids: list[str] | None = None, edits: dict | None = None) -> JournalEntry:
        proposal = json.loads(entry.proposal_json or "{}")
        edits = edits or {}
        want = set(accepted_ids or [a["id"] for a in proposal.get("actions") or [] if a.get("status") == "ready"])
        applied = json.loads(entry.applied_json or "{}")
        results = list(applied.get("results") or [])
        for action in proposal.get("actions") or []:
            aid = action.get("id")
            if aid not in want:
                action["status"] = "discarded" if aid not in {(r.get("id") for r in results)} else action.get("status")
                continue
            if any(r.get("id") == aid and r.get("ok") for r in results):
                continue
            patch = edits.get(aid) or {}
            action.update({k: v for k, v in patch.items() if k in {"mission_id", "fields", "type"}})
            try:
                detail = JournalService._apply_one(action, entry)
                action["status"] = "applied"
                results.append({"id": aid, "ok": True, "detail": detail})
            except (BoardError, ValueError) as exc:
                action["status"] = "needs_info"
                results.append({"id": aid, "ok": False, "error": str(exc)})
        entry.proposal_json = json.dumps(proposal, ensure_ascii=False)
        entry.applied_json = json.dumps({"results": results}, ensure_ascii=False)
        if all(a.get("status") in {"applied", "discarded"} for a in proposal.get("actions") or []):
            entry.status = "applied"
        elif any(a.get("status") == "applied" for a in proposal.get("actions") or []):
            entry.status = "partial"
        db.session.commit()
        return entry

    @staticmethod
    def _apply_one(action: dict, entry: JournalEntry) -> dict:
        kind = action.get("type")
        mission = db.session.get(Mission, int(action["mission_id"])) if action.get("mission_id") else None
        today = WorldService.today()
        if kind == "keep_pending":
            return {"kept_pending": True, "mission_id": mission.id if mission else None}
        if kind == "condition":
            return {"recorded_condition": action.get("text")}
        if kind == "plan":
            if mission and BoardService.state_of(mission) in {"idea", "todo"}:
                when = action.get("effective_date")
                if when:
                    mission.planned_date = date.fromisoformat(when)
                BoardService.transition(mission, "planned", commit=True)
                return {"mission_id": mission.id, "work_state": "planned"}
            if not mission:
                projects = Project.query.filter(Project.status == "ACTIVE").all()
                if len(projects) != 1 and not entry.project_id:
                    raise ValueError("Indica el proyecto para crear la misión planificada.")
                project = db.session.get(Project, entry.project_id) if entry.project_id else projects[0]
                mission = Mission(
                    project_id=project.id,
                    title=(action.get("text") or "Acción planificada")[:200],
                    status="OPEN",
                    work_state="planned",
                    planned_date=date.fromisoformat(action["effective_date"]) if action.get("effective_date") else None,
                    next_action=action.get("text") or "",
                )
                db.session.add(mission)
                db.session.commit()
                return {"mission_id": mission.id, "created": True, "work_state": "planned"}
            return {"mission_id": mission.id}
        if kind == "log_time":
            if not mission:
                raise ValueError("Vincula la misión para registrar tiempo.")
            minutes = int((action.get("fields") or {}).get("minutes") or 0)
            if minutes <= 0:
                raise ValueError("Minutos requeridos.")
            row = TimeEntry(
                mission_id=mission.id,
                project_id=mission.project_id,
                minutes=minutes,
                local_date=today,
                note=(action.get("text") or "")[:255],
            )
            db.session.add(row)
            db.session.commit()
            return {"time_entry_id": row.id, "minutes": minutes, "completed": False}
        if kind == "complete":
            if not mission:
                raise ValueError("Vincula la misión a completar.")
            packed = BoardService.transition(mission, "done")
            fields = action.get("fields") or {}
            if fields.get("quantity"):
                from app.models.rpg import ProductionRecord

                rec = ProductionRecord(
                    mission_id=mission.id,
                    quantity=int(fields["quantity"]),
                    unit=str(fields.get("unit") or ""),
                    note=action.get("text") or "",
                    source_key=f"journal:{entry.id}:{action.get('id')}",
                )
                db.session.add(rec)
                db.session.commit()
            return {"mission_id": mission.id, "completed": True, "reward": packed.get("reward")}
        if kind == "expect_payment":
            cents = int((action.get("fields") or {}).get("amount_cents") or 0)
            if cents <= 0:
                raise ValueError("Importe requerido.")
            mv = FinanceService.add(
                direction="in",
                amount_cents=cents,
                concept=(action.get("text") or "Cuenta por cobrar")[:200],
                status="pending",
                project_id=entry.project_id or (mission.project_id if mission else None),
            )
            return {"movement_id": mv.id, "status": "pending", "settled": False}
        if kind == "receive_money":
            cents = int((action.get("fields") or {}).get("amount_cents") or 0)
            if cents <= 0:
                raise ValueError("Importe requerido.")
            from app.models import MoneyMovement

            q = MoneyMovement.query.filter_by(direction="in", status="pending")
            pid = entry.project_id or (mission.project_id if mission else None)
            mid = (action.get("fields") or {}).get("movement_id")
            if mid:
                q = q.filter_by(id=int(mid))
            elif pid:
                q = q.filter_by(project_id=int(pid))
            else:
                q = q.filter_by(id=0)
            pending = q.order_by(MoneyMovement.id.desc()).first()
            if pending and cents < pending.amount_cents:
                row = FinanceService.settle_partial(pending, cents)
                return {"movement_id": row.id, "parent_id": pending.id, "status": "settled"}
            mv = FinanceService.add(
                direction="in",
                amount_cents=cents,
                concept=(action.get("text") or "Cobro")[:200],
                status="settled",
                project_id=entry.project_id,
            )
            return {"movement_id": mv.id, "status": "settled"}
        if kind == "quote_sent":
            oid = (action.get("fields") or {}).get("opportunity_id")
            opp = db.session.get(Opportunity, int(oid)) if oid else None
            if not opp:
                raise ValueError("Selecciona la oportunidad.")
            opp.status = "PROPOSAL"
            follow = (action.get("fields") or {}).get("follow_on") or action.get("effective_date")
            if follow:
                opp.next_action_date = date.fromisoformat(follow)
                opp.next_action = "Consultar respuesta"
            db.session.commit()
            return {"opportunity_id": opp.id, "status": opp.status, "money": False}
        if kind == "decree_pause":
            pid = int((action.get("fields") or {}).get("project_id") or entry.project_id or 0)
            project = db.session.get(Project, pid)
            if not project:
                raise ValueError("Proyecto requerido.")
            project.status = "PAUSED"
            decree = Decree(title=f"Pausa {project.name}", reason=action.get("text") or "", project_id=project.id)
            db.session.add(decree)
            db.session.commit()
            return {"project_id": project.id, "status": "PAUSED", "decree_id": decree.id}
        if kind == "study":
            mins = int((action.get("fields") or {}).get("minutes") or 0)
            result = RewardService.practice(
                "learning",
                mins,
                action.get("text") or "",
                source_key=f"journal:{entry.id}:{action.get('id')}",
            )
            if (action.get("fields") or {}).get("keep_example"):
                from app.models import Note

                note = Note(
                    project_id=entry.project_id,
                    title="Ejemplo de estudio",
                    body=action.get("text") or "",
                    kind="example",
                )
                db.session.add(note)
                db.session.commit()
                result["note_id"] = note.id
            return result
        from app.models import Note

        note = Note(project_id=entry.project_id, title="Bitácora", body=action.get("text") or "", kind="journal")
        db.session.add(note)
        db.session.commit()
        return {"note_id": note.id}
