from datetime import datetime

from flask import Blueprint, jsonify, request
from flask_login import login_required

from app.ai.agents import ask_agent
from app.extensions import db
from app.models import GameEvent, Mission, MissionObjective, Project
from app.services.recommendation_service import RecommendationService
from app.services.event_service import EventService
from app.services.game_service import GameService
from app.services.metrics_service import MetricsService
from app.services.project_service import ProjectService
from app.services.turn_service import TurnService
from app.services.xp_service import XPService

bp = Blueprint("api", __name__)


@bp.route("/projects")
@login_required
def projects():
    items = Project.query.order_by(Project.priority.asc()).all()
    return jsonify([p.to_map_dict() | {"description": p.description, "slug": p.slug} for p in items])


@bp.route("/projects/<int:project_id>")
@login_required
def project_detail(project_id: int):
    project = Project.query.get_or_404(project_id)
    data = project.to_map_dict()
    data.update(
        {
            "description": project.description,
            "xp": project.xp,
            "metrics": project.metrics_dict(),
            "hours_invested": project.hours_invested,
            "last_activity": project.last_activity.isoformat() if project.last_activity else None,
        }
    )
    return jsonify(data)


@bp.route("/projects/<int:project_id>/position", methods=["PATCH", "POST"])
@login_required
def move_project(project_id: int):
    project = Project.query.get_or_404(project_id)
    payload = request.get_json(silent=True) or {}
    x = payload.get("x", request.form.get("x"))
    y = payload.get("y", request.form.get("y"))
    if x is None or y is None:
        return jsonify({"error": "x and y required"}), 400
    ProjectService.move(project, int(x), int(y))
    return jsonify({"ok": True, "id": project.id, "x": project.map_x, "y": project.map_y})


@bp.route("/projects/<slug>/city")
@login_required
def project_city(slug: str):
    project = Project.query.filter_by(slug=slug).first_or_404()
    return jsonify(GameService.city_payload(project))


@bp.route("/map")
@login_required
def map_data():
    return jsonify(GameService.map_payload())


@bp.route("/events")
@login_required
def events():
    limit = min(int(request.args.get("limit", 20)), 100)
    items = GameEvent.query.order_by(GameEvent.created_at.desc()).limit(limit).all()
    return jsonify([e.to_dict() for e in items])


@bp.route("/missions")
@login_required
def missions():
    q = Mission.query.filter(Mission.status.in_(["OPEN", "IN_PROGRESS"]))
    project_id = request.args.get("project_id")
    if project_id:
        q = q.filter_by(project_id=int(project_id))
    items = q.order_by(Mission.priority.asc()).all()
    return jsonify([m.to_dict() for m in items])


@bp.route("/missions/<int:mission_id>/continue", methods=["POST"])
@login_required
def continue_mission(mission_id: int):
    mission = db.session.get(Mission, mission_id)
    if not mission:
        return jsonify({"error": "not found"}), 404
    from app.services.board_service import BoardError, BoardService
    from app.services.coop_service import CoopError, CoopService

    try:
        CoopService.require_write(mission.project)
        result = BoardService.advance(mission)
    except BoardError as exc:
        return jsonify({"error": str(exc), "mission": mission.to_dict()}), 400
    except CoopError as exc:
        return jsonify({"error": str(exc), "mission": mission.to_dict()}), 403
    return jsonify(result)


@bp.route("/empire/status")
@login_required
def empire_status():
    return jsonify(GameService.hud())


@bp.route("/turns/end", methods=["POST"])
@login_required
def end_turn():
    log = TurnService.end_turn()
    return jsonify({"ok": True, "turn": log.turn_number, "summary": log.summary})


@bp.route("/advisor/status")
@login_required
def advisor_status():
    return jsonify({"available": True, "source": "rules"})


@bp.route("/advisor/brief", methods=["GET", "POST"])
@login_required
def advisor_brief():
    payload = request.get_json(silent=True) or {}
    question = payload.get("question") or request.args.get("q") or "¿Qué hago ahora?"
    return jsonify(RecommendationService.narrate(question))


@bp.route("/advisor/ask", methods=["POST"])
@login_required
def advisor_ask():
    payload = request.get_json(silent=True) or {}
    question = payload.get("question") or "¿Qué hago ahora?"
    agent = payload.get("agent") or "counselor"
    use_model = bool(payload.get("ollama"))
    if not use_model:
        return jsonify(RecommendationService.narrate(question))
    result = ask_agent(agent, question)
    if not result.get("answer"):
        spoken = RecommendationService.narrate(question)
        result["answer"] = result.get("summary") or spoken["answer"]
        result.setdefault("create_mission", spoken.get("create_mission"))
        result.setdefault("suggested_mission", spoken.get("suggested_mission"))
    return jsonify(result)


@bp.route("/missions/from-advice", methods=["POST"])
@login_required
def mission_from_advice():
    payload = request.get_json(silent=True) or {}
    project = None
    if payload.get("project_id"):
        project = db.session.get(Project, int(payload["project_id"]))
    elif payload.get("project_slug"):
        project = Project.query.filter_by(slug=payload["project_slug"]).first()
    elif payload.get("project_name"):
        project = Project.query.filter_by(name=payload["project_name"]).first()
    if project is None:
        brief = RecommendationService.narrate()
        pid = (brief.get("create_mission") or {}).get("project_id") or brief.get("priority_project_id")
        if pid:
            project = db.session.get(Project, int(pid))
    if project is None:
        return jsonify({"error": "no project"}), 400
    title = (payload.get("title") or f"Avanzar {project.name}").strip()[:200]
    existing = Mission.query.filter_by(project_id=project.id, title=title).filter(
        Mission.status.in_(["OPEN", "IN_PROGRESS"])
    ).first()
    if existing:
        return jsonify({"ok": True, "mission": existing.to_dict(), "created": False})
    mission = Mission(
        project_id=project.id,
        title=title,
        description=payload.get("description") or "Misión sugerida desde el Centro de Mando IA.",
        type=payload.get("type") or "DEVELOPMENT",
        priority=int(payload.get("priority") or project.priority or 2),
        xp_reward=int(payload.get("xp_reward") or 8),
        status="OPEN",
        work_state="todo",
    )
    db.session.add(mission)
    db.session.flush()
    objectives = payload.get("objectives") or ["Definir el siguiente paso concreto", "Ejecutarlo", "Verificar el resultado"]
    for i, line in enumerate(objectives):
        text = str(line).strip()
        if text:
            db.session.add(MissionObjective(mission_id=mission.id, description=text, position=i))
    XPService.award("create_task", project=project, description=f"Misión: {title}")
    EventService.emit(
        f"Nueva misión en {project.name}",
        description=title,
        kind="info",
        icon="fa-scroll",
        project=project,
        commit=False,
    )
    db.session.commit()
    return jsonify({"ok": True, "mission": mission.to_dict(), "created": True})
