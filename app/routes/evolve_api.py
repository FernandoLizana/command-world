from datetime import date
from flask import Blueprint, jsonify, request, send_file
from flask_login import login_required

from app.extensions import db
from app.models import Goal, InboxCapture, Mission, MoneyMovement, Note, Opportunity, Project
from app.seeds import seed_all
from app.services.backup_service import BackupService
from app.services.capture_service import CaptureService
from app.services.daily_turn_service import DailyTurnService
from app.services.dependency_service import DependencyError, DependencyService
from app.services.finance_service import FinanceService, parse_cents
from app.services.game_service import GameService
from app.services.project_service import ProjectService
from app.services.template_service import TemplateService
from app.services.weekly_review_service import WeeklyReviewService
from app.services.world_service import WorldService

bp = Blueprint("evolve_api", __name__)


@bp.route("/world")
@login_required
def world_get():
    empire = GameService.get_empire()
    needs = WorldService.needs_onboarding()
    prefs = WorldService.prefs()
    open_inbox = InboxCapture.query.filter_by(status="open").count()
    return jsonify(
        {
            "name": empire.name,
            "prefs": prefs,
            "needs_onboarding": needs,
            "inbox_open": open_inbox,
            "capacity": WorldService.weekly_capacity_minutes(),
            "planned_week": WorldService.planned_minutes_this_week(),
            "today": WorldService.today().isoformat(),
            "glossary": {
                "edificio": "proyecto",
                "mision": "tarea",
                "mercader": "oportunidad comercial",
            },
        }
    )


@bp.route("/world", methods=["POST"])
@login_required
def world_save():
    payload = request.get_json(silent=True) or {}
    empire = GameService.get_empire()
    if payload.get("name"):
        empire.name = str(payload["name"]).strip()[:120]
        db.session.commit()
    prefs = WorldService.save(payload.get("prefs") or payload)
    return jsonify({"ok": True, "prefs": prefs, "name": empire.name})


@bp.route("/world/onboarding", methods=["POST"])
@login_required
def onboarding():
    payload = request.get_json(silent=True) or {}
    empire = GameService.get_empire()
    name = (payload.get("name") or "Mi mundo").strip()[:120]
    empire.name = name
    prefs = WorldService.save(
        {
            "usage_type": payload.get("usage_type") or "mix",
            "timezone": payload.get("timezone") or "UTC",
            "currency": (payload.get("currency") or "USD").upper()[:8],
            "week_start": int(payload.get("week_start") or 0),
            "weekly_minutes": (
                int(payload["weekly_minutes"]) if payload.get("weekly_minutes") not in (None, "") else None
            ),
            "language": payload.get("language") or "es",
            "onboarding_done": True,
        }
    )
    path = payload.get("path") or "empty"
    created = None
    if path == "demo" and not Project.query.filter_by(is_demo=True).first():
        seed_all()
        WorldService.save({"demo_loaded": True, "onboarding_done": True})
    elif path not in {"demo", "skip"}:
        first = (payload.get("first_project") or "").strip()
        action = (payload.get("first_action") or "").strip()
        existing = Project.query.filter_by(name=first).first() if first else None
        if first and existing is None:
            created = ProjectService.create({"name": first, "description": payload.get("goal") or "", "status": "ACTIVE"})
            if action:
                m = Mission(project_id=created.id, title=action[:200], status="OPEN", work_state="todo")
                db.session.add(m)
                db.session.commit()
            if payload.get("goal"):
                g = Goal(
                    project_id=created.id,
                    title=str(payload.get("goal"))[:200],
                    kind="milestone",
                    is_primary=True,
                    success_criteria=str(payload.get("goal")),
                )
                db.session.add(g)
                db.session.commit()
        elif existing:
            created = existing
        template_id = payload.get("template_id")
        if template_id and not created:
            created = TemplateService.instantiate(template_id, first or None)
    db.session.commit()
    return jsonify(
        {
            "ok": True,
            "prefs": WorldService.prefs(),
            "project": created.to_map_dict() if created else None,
        }
    )


@bp.route("/today")
@login_required
def today_get():
    current = DailyTurnService.current()
    minutes = int(request.args.get("minutes") or (current or {}).get("minutes") or 30)
    if current and current.get("status") in {"accepted", "active"}:
        return jsonify(current)
    return jsonify(DailyTurnService.suggest(minutes))


@bp.route("/today", methods=["POST"])
@login_required
def today_post():
    payload = request.get_json(silent=True) or {}
    minutes = int(payload.get("minutes") or 30)
    minutes = max(5, min(12 * 60, minutes))
    data = DailyTurnService.suggest(minutes)
    if payload.get("accept"):
        data = DailyTurnService.accept(data.get("id"))
    return jsonify(data)


@bp.route("/inbox")
@login_required
def inbox_list():
    items = InboxCapture.query.filter_by(status="open").order_by(InboxCapture.created_at.desc()).all()
    return jsonify([c.to_dict() for c in items])


@bp.route("/inbox", methods=["POST"])
@login_required
def inbox_add():
    payload = request.get_json(silent=True) or {}
    try:
        row = CaptureService.add(payload.get("text") or "")
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(row.to_dict())


@bp.route("/inbox/<int:capture_id>/convert", methods=["POST"])
@login_required
def inbox_convert(capture_id: int):
    row = db.session.get(InboxCapture, capture_id)
    if not row:
        return jsonify({"error": "not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        CaptureService.convert(row, payload.get("kind") or "later", payload.get("project_id"))
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(row.to_dict())


@bp.route("/money")
@login_required
def money_get():
    project_id = request.args.get("project_id")
    pid = int(project_id) if project_id else None
    q = MoneyMovement.query.order_by(MoneyMovement.occurred_on.desc()).limit(80)
    if pid:
        q = q.filter_by(project_id=pid)
    return jsonify({"totals": FinanceService.totals(pid), "items": [m.to_dict() for m in q.all()]})


@bp.route("/money", methods=["POST"])
@login_required
def money_add():
    payload = request.get_json(silent=True) or {}
    try:
        cents = parse_cents(payload.get("amount") or 0)
        row = FinanceService.add(
            direction=payload.get("direction") or "in",
            amount_cents=cents,
            concept=payload.get("concept") or "Movimiento",
            currency=payload.get("currency"),
            status=payload.get("status") or "settled",
            project_id=payload.get("project_id"),
            occurred_on=date.fromisoformat(payload["occurred_on"]) if payload.get("occurred_on") else None,
            category=payload.get("category") or "general",
        )
    except (ValueError, TypeError) as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(row.to_dict())


@bp.route("/money/<int:movement_id>/partial", methods=["POST"])
@login_required
def money_partial(movement_id: int):
    parent = db.session.get(MoneyMovement, movement_id)
    if not parent:
        return jsonify({"error": "not found"}), 404
    payload = request.get_json(silent=True) or {}
    try:
        cents = parse_cents(payload.get("amount") or 0)
        row = FinanceService.settle_partial(parent, cents)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"settled": row.to_dict(), "totals": FinanceService.totals(parent.project_id)})


@bp.route("/opportunities/<int:opp_id>/won", methods=["POST"])
@login_required
def opp_won(opp_id: int):
    opp = db.session.get(Opportunity, opp_id)
    if not opp:
        return jsonify({"error": "not found"}), 404
    payload = request.get_json(silent=True) or {}
    opp.status = "WON"
    db.session.commit()
    mv = FinanceService.from_won_opportunity(opp, bool(payload.get("create_receivable")))
    return jsonify({"ok": True, "opportunity_id": opp.id, "movement": mv.to_dict() if mv else None})


@bp.route("/templates")
@login_required
def templates():
    return jsonify(TemplateService.list())


@bp.route("/templates/<template_id>/apply", methods=["POST"])
@login_required
def apply_template(template_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        project = TemplateService.instantiate(
            template_id, payload.get("name") or "", payload.get("selected")
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(project.to_map_dict())


@bp.route("/goals")
@login_required
def goals():
    q = Goal.query
    if request.args.get("project_id"):
        q = q.filter_by(project_id=int(request.args["project_id"]))
    return jsonify([g.to_dict() for g in q.all()])


@bp.route("/goals", methods=["POST"])
@login_required
def goal_add():
    payload = request.get_json(silent=True) or {}
    project = db.session.get(Project, int(payload.get("project_id") or 0))
    if not project:
        return jsonify({"error": "proyecto requerido"}), 400
    if payload.get("is_primary"):
        Goal.query.filter_by(project_id=project.id, is_primary=True).update({"is_primary": False})
    goal = Goal(
        project_id=project.id,
        title=(payload.get("title") or "Meta").strip()[:200],
        kind=payload.get("kind") or "milestone",
        is_primary=bool(payload.get("is_primary")),
        success_criteria=payload.get("success_criteria") or "",
        unit=payload.get("unit") or "",
        start_value=int(payload.get("start_value") or 0),
        target_value=int(payload.get("target_value") or 0),
        current_value=int(payload.get("current_value") or payload.get("start_value") or 0),
        due_date=date.fromisoformat(payload["due_date"]) if payload.get("due_date") else None,
    )
    db.session.add(goal)
    db.session.commit()
    return jsonify(goal.to_dict())


@bp.route("/missions/<int:mission_id>/depend", methods=["POST"])
@login_required
def mission_depend(mission_id: int):
    payload = request.get_json(silent=True) or {}
    try:
        DependencyService.add(mission_id, int(payload.get("depends_on_id")))
    except (DependencyError, TypeError, ValueError) as exc:
        return jsonify({"error": str(exc)}), 400
    mission = db.session.get(Mission, mission_id)
    return jsonify({"ok": True, "blocked": mission.is_blocked() if mission else None})


@bp.route("/backup/snapshot", methods=["POST"])
@login_required
def backup_snapshot():
    path = BackupService.snapshot_sqlite()
    BackupService.write_export()
    return jsonify({"ok": True, "file": path.name, "last_ok": BackupService.last_ok()})


@bp.route("/backup/export")
@login_required
def backup_export():
    path = BackupService.write_export()
    return send_file(path, as_attachment=True, download_name=path.name)


@bp.route("/search")
@login_required
def search():
    q = (request.args.get("q") or "").strip().lower()
    if len(q) < 2:
        return jsonify([])
    hits = []
    for p in Project.query.all():
        if q in (p.name or "").lower() or q in (p.description or "").lower():
            hits.append({"type": "project", "id": p.id, "title": p.name, "slug": p.slug})
    for m in Mission.query.filter(Mission.status.in_(["OPEN", "IN_PROGRESS"])).all():
        if q in (m.title or "").lower():
            hits.append({"type": "mission", "id": m.id, "title": m.title, "project_id": m.project_id})
    for o in Opportunity.query.filter(Opportunity.status.notin_(["WON", "LOST"])).all():
        if q in (o.name or "").lower():
            hits.append({"type": "opportunity", "id": o.id, "title": o.name, "project_id": o.project_id})
    for n in Note.query.all():
        blob = ((n.title or "") + " " + (n.body or "")).lower()
        if q in blob:
            hits.append({"type": "note", "id": n.id, "title": n.title or n.body[:80], "project_id": n.project_id})
    return jsonify(hits[:20])


PIPELINE = ["LEAD", "CONTACTED", "TALK", "PROPOSAL", "NEGOTIATION", "WON", "LOST"]


@bp.route("/opportunities/<int:opp_id>/stage", methods=["POST"])
@login_required
def opp_stage(opp_id: int):
    opp = db.session.get(Opportunity, opp_id)
    if not opp:
        return jsonify({"error": "not found"}), 404
    payload = request.get_json(silent=True) or {}
    stage = (payload.get("status") or "").upper()
    if stage not in PIPELINE:
        return jsonify({"error": "Etapa no válida.", "allowed": PIPELINE}), 400
    opp.status = stage
    if payload.get("next_action") is not None:
        opp.next_action = str(payload.get("next_action"))[:255]
    if payload.get("lost_reason"):
        opp.notes = (opp.notes or "") + "\nPerdida: " + str(payload["lost_reason"])[:200]
    db.session.commit()
    movement = None
    if stage == "WON":
        movement = FinanceService.from_won_opportunity(opp, bool(payload.get("create_receivable")))
    return jsonify({"ok": True, "status": opp.status, "movement": movement.to_dict() if movement else None})


@bp.route("/week")
@login_required
def week_get():
    return jsonify(WeeklyReviewService.draft())


@bp.route("/week", methods=["POST"])
@login_required
def week_save():
    payload = request.get_json(silent=True) or {}
    notes = {
        "worked": payload.get("worked") or "",
        "learned": payload.get("learned") or "",
        "change": payload.get("change") or "",
    }
    return jsonify(WeeklyReviewService.save(notes, payload.get("plan_next")))


@bp.route("/notes", methods=["GET", "POST"])
@login_required
def notes():
    if request.method == "GET":
        q = Note.query
        if request.args.get("project_id"):
            q = q.filter_by(project_id=int(request.args["project_id"]))
        return jsonify([n.to_dict() for n in q.order_by(Note.created_at.desc()).all()])
    payload = request.get_json(silent=True) or {}
    url = (payload.get("url") or "").strip()
    if url and not url.lower().startswith(("http://", "https://", "mailto:")):
        return jsonify({"error": "El enlace solo admite http, https o mailto."}), 400
    note = Note(
        project_id=payload.get("project_id"),
        title=(payload.get("title") or "")[:200],
        body=payload.get("body") or "",
        kind=payload.get("kind") or "note",
        url=url[:500],
    )
    db.session.add(note)
    db.session.commit()
    return jsonify(note.to_dict())


@bp.route("/blockers", methods=["POST"])
@login_required
def blocker_add():
    from app.models import ExternalBlocker

    payload = request.get_json(silent=True) or {}
    reason = (payload.get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "Indica el motivo del bloqueo."}), 400
    row = ExternalBlocker(
        mission_id=payload.get("mission_id"),
        project_id=payload.get("project_id"),
        reason=reason[:255],
        kind=payload.get("kind") or "wait",
        review_on=date.fromisoformat(payload["review_on"]) if payload.get("review_on") else None,
    )
    db.session.add(row)
    db.session.commit()
    return jsonify({"id": row.id, "reason": row.reason, "status": row.status})


@bp.route("/export/csv")
@login_required
def export_csv():
    kind = request.args.get("kind") or "missions"
    path = BackupService.write_csv(kind)
    return send_file(path, as_attachment=True, download_name=path.name)


@bp.route("/backup/restore", methods=["POST"])
@login_required
def backup_restore():
    up = request.files.get("file")
    if not up:
        return jsonify({"error": "Adjunta un archivo .db o .json"}), 400
    try:
        info = BackupService.restore_upload(up)
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify({"ok": True, **info})
