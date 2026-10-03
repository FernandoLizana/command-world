"""Board, journal, world extras and cooperation APIs."""

from __future__ import annotations

from datetime import date

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required

from app.extensions import db
from app.models import Mission, Project
from app.models.rpg import (
    AchievementGrant,
    BestiaryCase,
    CampaignChapter,
    ContactCard,
    EvidenceItem,
    JournalEntry,
    Procedure,
    ProjectLink,
    WorkSession,
)
from app.services.board_service import BoardError, BoardService
from app.services.coop_service import CoopError, CoopService
from app.services.journal_service import JournalService
from app.services.reward_service import RewardService
from app.services.rpg_service import RpgService
from app.services.world_service import WorldService

bp = Blueprint("rpg_api", __name__)


def _err(exc, code=400):
    return jsonify({"error": str(exc)}), code


@bp.route("/board")
@login_required
def board_get():
    pid = request.args.get("project_id")
    RpgService.ensure_patrols()
    if pid:
        project = db.session.get(Project, int(pid))
        if not project or not CoopService.can_read(project):
            return _err("Sin acceso a este proyecto.", 403)
    payload = BoardService.board_payload(int(pid) if pid else None)
    readable = {p.id for p in Project.query.all() if CoopService.can_read(p)}
    if not pid:
        for key, cards in list((payload.get("columns") or {}).items()):
            payload["columns"][key] = [c for c in cards if c.get("project_id") in readable]
        payload["queue"] = [q for q in (payload.get("queue") or []) if q.get("project_id") in readable]
    payload["rewards"] = RewardService.totals()
    payload["rally"] = {
        "project_id": WorldService.prefs().get("rally_project_id"),
        "until": WorldService.prefs().get("rally_until"),
    }
    payload["session_mode"] = WorldService.prefs().get("session_mode") or "mixed"
    payload["watch"] = RpgService.watch_alerts()[:8]
    payload["rest"] = (RpgService.rest_on() or None)
    if payload["rest"]:
        payload["rest"] = payload["rest"].to_dict()
    return jsonify(payload)


@bp.route("/board/missions/<int:mission_id>", methods=["POST"])
@login_required
def board_edit(mission_id: int):
    mission = db.session.get(Mission, mission_id)
    if not mission:
        return _err("not found", 404)
    payload = request.get_json(silent=True) or {}
    try:
        CoopService.require_write(mission.project)
        BoardService.update_card(mission, payload)
    except (BoardError, CoopError, ValueError) as exc:
        return _err(exc)
    return jsonify(mission.to_dict())


@bp.route("/board/missions/<int:mission_id>/move", methods=["POST"])
@login_required
def board_move(mission_id: int):
    mission = db.session.get(Mission, mission_id)
    if not mission:
        return _err("not found", 404)
    payload = request.get_json(silent=True) or {}
    to_state = payload.get("work_state") or payload.get("to")
    try:
        CoopService.require_write(mission.project)
        if payload.get("project_id") and int(payload["project_id"]) != mission.project_id:
            BoardService.move_project(mission, int(payload["project_id"]), confirm=bool(payload.get("confirm")))
        if to_state:
            packed = BoardService.transition(
                mission,
                to_state,
                version=payload.get("version"),
                wait_reason=payload.get("wait_reason") or "",
                wait_review_on=date.fromisoformat(payload["wait_review_on"]) if payload.get("wait_review_on") else None,
                done_criteria=payload.get("done_criteria"),
                next_action=payload.get("next_action"),
            )
            return jsonify(packed)
    except (BoardError, CoopError, ValueError, TypeError) as exc:
        return _err(exc)
    return jsonify({"mission": mission.to_dict()})


@bp.route("/board/reorder", methods=["POST"])
@login_required
def board_reorder():
    payload = request.get_json(silent=True) or {}
    try:
        project = db.session.get(Project, int(payload.get("project_id") or 0))
        CoopService.require_write(project)
        items = BoardService.reorder(project.id, payload.get("ordered_ids") or [])
    except (BoardError, CoopError, TypeError, ValueError) as exc:
        return _err(exc)
    return jsonify({"ok": True, "ids": [m.id for m in items]})


@bp.route("/board/bulk", methods=["POST"])
@login_required
def board_bulk():
    payload = request.get_json(silent=True) or {}
    try:
        for mid in payload.get("mission_ids") or []:
            mission = db.session.get(Mission, int(mid))
            if mission:
                CoopService.require_write(mission.project)
        result = BoardService.bulk(payload.get("mission_ids") or [], payload.get("work_state") or "planned", payload)
    except (BoardError, CoopError) as exc:
        return _err(exc)
    return jsonify(result)


@bp.route("/journal")
@login_required
def journal_list():
    rows = JournalEntry.query.order_by(JournalEntry.id.desc()).limit(30).all()
    return jsonify([r.to_dict() for r in rows])


@bp.route("/journal", methods=["POST"])
@login_required
def journal_add():
    payload = request.get_json(silent=True) or {}
    try:
        row = JournalService.capture(payload.get("text") or "", payload.get("project_id"))
    except ValueError as exc:
        return _err(exc)
    return jsonify(row.to_dict())


@bp.route("/journal/<int:entry_id>/apply", methods=["POST"])
@login_required
def journal_apply(entry_id: int):
    row = db.session.get(JournalEntry, entry_id)
    if not row:
        return _err("not found", 404)
    payload = request.get_json(silent=True) or {}
    try:
        if row.project_id:
            project = db.session.get(Project, row.project_id)
            CoopService.require_write(project)
        JournalService.apply(row, payload.get("accepted"), payload.get("edits") or {})
    except (BoardError, CoopError, ValueError) as exc:
        return _err(exc)
    return jsonify(row.to_dict())


@bp.route("/rewards")
@login_required
def rewards():
    return jsonify({"totals": RewardService.totals(), "ledger": RewardService.ledger(), "achievements": [
        a.to_dict() for a in AchievementGrant.query.all()
    ]})


@bp.route("/world/minimap")
@login_required
def minimap():
    return jsonify(RpgService.minimap())


@bp.route("/world/rally", methods=["POST"])
@login_required
def rally():
    payload = request.get_json(silent=True) or {}
    return jsonify(RpgService.set_rally(payload.get("project_id"), payload.get("until")))


@bp.route("/world/fog", methods=["GET", "POST"])
@login_required
def fog():
    from app.models.rpg import FogQuestion

    if request.method == "GET":
        return jsonify([f.to_dict() for f in FogQuestion.query.order_by(FogQuestion.id.desc()).all()])
    payload = request.get_json(silent=True) or {}
    try:
        row = RpgService.add_fog(payload.get("question") or "", payload.get("project_id"), payload.get("action") or "")
    except ValueError as exc:
        return _err(exc)
    return jsonify(row.to_dict())


@bp.route("/world/fog/<int:fog_id>/answer", methods=["POST"])
@login_required
def fog_answer(fog_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        row = RpgService.clear_fog(fog_id, payload.get("answer") or "")
    except ValueError as exc:
        return _err(exc)
    return jsonify(row.to_dict())


@bp.route("/sessions", methods=["GET", "POST"])
@login_required
def sessions():
    if request.method == "GET":
        open_row = WorkSession.query.filter_by(status="active").first()
        return jsonify({"current": open_row.to_dict() if open_row else None})
    payload = request.get_json(silent=True) or {}
    row = RpgService.start_session(payload.get("mission_id"), payload.get("project_id"))
    return jsonify(row.to_dict())


@bp.route("/sessions/<int:session_id>/stop", methods=["POST"])
@login_required
def session_stop(session_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        row = RpgService.stop_session(
            session_id,
            payload.get("summary") or "",
            payload.get("leftover") or "",
            payload.get("minutes"),
        )
    except ValueError as exc:
        return _err(exc)
    return jsonify({"session": row.to_dict(), "completed_mission": False})


@bp.route("/rest", methods=["GET", "POST"])
@login_required
def rest():
    if request.method == "GET":
        from app.models.rpg import RestPeriod

        return jsonify([r.to_dict() for r in RestPeriod.query.order_by(RestPeriod.id.desc()).all()])
    payload = request.get_json(silent=True) or {}
    try:
        row = RpgService.add_rest(
            date.fromisoformat(payload["starts_on"]),
            date.fromisoformat(payload["ends_on"]),
            payload.get("note") or "",
        )
    except (KeyError, ValueError) as exc:
        return _err(exc)
    return jsonify(row.to_dict())


@bp.route("/advisors")
@login_required
def advisors():
    return jsonify(RpgService.advisors())


@bp.route("/skills/<name>", methods=["POST"])
@login_required
def skills(name: str):
    try:
        return jsonify(RpgService.skill(name, request.get_json(silent=True) or {}))
    except ValueError as exc:
        return _err(exc)


@bp.route("/patrols")
@login_required
def patrols():
    return jsonify(RpgService.ensure_patrols())


@bp.route("/patrols/<int:item_id>/complete", methods=["POST"])
@login_required
def patrol_complete(item_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        row = RpgService.complete_patrol(item_id, payload.get("result") or "")
    except ValueError as exc:
        return _err(exc)
    return jsonify(row.to_dict())


@bp.route("/chronicle")
@login_required
def chronicle():
    return jsonify({"readonly": True, "events": RpgService.chronicle(int(request.args.get("limit") or 40))})


@bp.route("/scenarios", methods=["POST"])
@login_required
def scenarios():
    payload = request.get_json(silent=True) or {}
    row = RpgService.simulate(payload.get("title") or "Escenario", payload.get("weekly_minutes"))
    return jsonify(row.to_dict())


@bp.route("/scenarios/<int:sid>/discard", methods=["POST"])
@login_required
def scenario_discard(sid: int):
    try:
        row = RpgService.discard_scenario(sid)
    except ValueError as exc:
        return _err(exc)
    return jsonify(row.to_dict())


@bp.route("/guild/share", methods=["POST"])
@login_required
def guild_share():
    payload = request.get_json(silent=True) or {}
    project = db.session.get(Project, int(payload.get("project_id") or 0))
    if not project:
        return _err("proyecto requerido")
    WorldService.save({"guild_enabled": True})
    try:
        row = CoopService.share(project, payload.get("username") or "", payload.get("role") or "collaborator")
    except CoopError as exc:
        return _err(exc)
    return jsonify({"ok": True, "members": CoopService.members(project), "id": row.id})


@bp.route("/guild/<int:project_id>")
@login_required
def guild_get(project_id: int):
    project = db.session.get(Project, project_id)
    if not project:
        return _err("not found", 404)
    if not CoopService.can_read(project):
        return _err("Sin acceso a este proyecto.", 403)
    return jsonify({"members": CoopService.members(project)})


@bp.route("/production", methods=["POST"])
@login_required
def production():
    payload = request.get_json(silent=True) or {}
    try:
        mission = db.session.get(Mission, int(payload.get("mission_id") or 0))
        if not mission:
            return _err("misión requerida")
        CoopService.require_write(mission.project)
        rec = RpgService.add_production(
            mission.id,
            int(payload.get("quantity") or 0),
            payload.get("unit") or "",
            payload.get("note") or "",
            payload.get("key"),
        )
    except (TypeError, ValueError, CoopError) as exc:
        return _err(exc)
    return jsonify(rec.to_dict())


@bp.route("/evidence", methods=["POST"])
@login_required
def evidence():
    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") or "").strip()
    if url and not url.lower().startswith(("http://", "https://", "mailto:")):
        return _err("El enlace solo admite http, https o mailto.")
    row = EvidenceItem(
        mission_id=payload.get("mission_id"),
        project_id=payload.get("project_id"),
        kind=payload.get("kind") or "note",
        title=(payload.get("title") or "")[:200],
        body=payload.get("body") or "",
        url=url[:500],
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict())


@bp.route("/contacts", methods=["GET", "POST"])
@login_required
def contacts():
    if request.method == "GET":
        return jsonify([c.to_dict() for c in ContactCard.query.order_by(ContactCard.id.desc()).all()])
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    if not name:
        return _err("Nombre requerido. No se inventan contactos.")
    row = ContactCard(
        name=name[:160],
        project_id=payload.get("project_id"),
        opportunity_id=payload.get("opportunity_id"),
        role=payload.get("role") or "",
        notes=payload.get("notes") or "",
        last_touch=WorldService.today(),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict())


@bp.route("/links", methods=["POST"])
@login_required
def links():
    payload = request.get_json(silent=True) or {}
    if int(payload.get("from_id") or 0) == int(payload.get("to_id") or 0):
        return _err("Un camino necesita dos edificios distintos.")
    row = ProjectLink(
        from_id=int(payload["from_id"]),
        to_id=int(payload["to_id"]),
        kind=payload.get("kind") or "related",
        note=payload.get("note") or "",
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict())


@bp.route("/procedures", methods=["GET", "POST"])
@login_required
def procedures():
    if request.method == "GET":
        return jsonify([p.to_dict() for p in Procedure.query.all()])
    payload = request.get_json(silent=True) or {}
    import json

    row = Procedure(
        title=(payload.get("title") or "Procedimiento")[:200],
        steps_json=json.dumps(payload.get("steps") or [], ensure_ascii=False),
        resource_note_id=payload.get("resource_note_id"),
        origin=payload.get("origin") or "",
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict())


@bp.route("/procedures/<int:pid>/use", methods=["POST"])
@login_required
def procedure_use(pid: int):
    proc = db.session.get(Procedure, pid)
    if not proc:
        return _err("not found", 404)
    payload = request.get_json(silent=True) or {}
    project = db.session.get(Project, int(payload.get("project_id") or 0))
    if not project:
        return _err("proyecto requerido")
    try:
        CoopService.require_write(project)
    except CoopError as exc:
        return _err(exc, 403)
    created = []
    for i, step in enumerate(proc.to_dict().get("steps") or []):
        title = (step if isinstance(step, str) else step.get("title") or "Paso")[:200]
        m = Mission(project_id=project.id, title=title, status="OPEN", work_state="todo", origin_capture_id=None)
        db.session.add(m)
        created.append(title)
    db.session.commit()
    return jsonify({"ok": True, "created": created, "version": proc.version})


@bp.route("/bestiary", methods=["GET", "POST"])
@login_required
def bestiary():
    if request.method == "GET":
        return jsonify([b.to_dict() for b in BestiaryCase.query.order_by(BestiaryCase.id.desc()).all()])
    payload = request.get_json(silent=True) or {}
    row = BestiaryCase(
        category=(payload.get("category") or "informacion_insuficiente")[:80],
        title=(payload.get("title") or "Obstáculo")[:200],
        tried=payload.get("tried") or "",
        useful=payload.get("useful") or "",
        mission_id=payload.get("mission_id"),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict())


@bp.route("/chapters", methods=["POST"])
@login_required
def chapters():
    payload = request.get_json(silent=True) or {}
    project = db.session.get(Project, int(payload.get("project_id") or 0))
    if not project:
        return _err("proyecto requerido")
    try:
        CoopService.require_write(project)
    except CoopError as exc:
        return _err(exc, 403)
    row = CampaignChapter(
        project_id=project.id,
        title=(payload.get("title") or "Capítulo")[:200],
        body=payload.get("body") or "",
        predecessor_id=payload.get("predecessor_id"),
    )
    db.session.add(row)
    db.session.commit()
    return jsonify(row.to_dict())


@bp.route("/cosmetics", methods=["POST"])
@login_required
def cosmetics():
    payload = request.get_json(silent=True) or {}
    return jsonify(RpgService.claim_cosmetic(payload.get("code") or "banner", payload.get("title") or "Estandarte"))


@bp.route("/commander", methods=["POST"])
@login_required
def commander():
    payload = request.get_json(silent=True) or {}
    prefs = WorldService.save(
        {
            "commander_name": (payload.get("name") or current_user.display_name or "")[:80],
            "commander_class": payload.get("class_name") or "mixed",
            "avatar": payload.get("avatar") or "default",
        }
    )
    return jsonify(
        {
            "name": prefs.get("commander_name"),
            "class_name": prefs.get("commander_class"),
            "avatar": prefs.get("avatar"),
            "stats_unchanged": True,
        }
    )
