from datetime import date, datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import Mission, MissionObjective, Project
from app.models.constants import MISSION_STATUSES, MISSION_TYPES
from app.services.event_service import EventService
from app.services.metrics_service import MetricsService
from app.services.xp_service import XPService

bp = Blueprint("missions", __name__)


@bp.route("/", strict_slashes=False)
@login_required
def list_missions():
    if not request.args.get("full"):
        return redirect(url_for("main.map_view") + "#misiones")
    status = request.args.get("status")
    q = Mission.query
    if status:
        q = q.filter_by(status=status)
    else:
        q = q.filter(Mission.status.in_(["OPEN", "IN_PROGRESS"]))
    missions = q.order_by(Mission.priority.asc(), Mission.created_at.desc()).all()
    projects = Project.query.order_by(Project.name).all()
    return render_template(
        "command/missions.html",
        missions=missions,
        projects=projects,
        types=MISSION_TYPES,
        statuses=MISSION_STATUSES,
        filter_status=status,
    )


@bp.route("/new", methods=["POST"])
@login_required
def create_mission():
    title = (request.form.get("title") or "").strip()
    project_id = request.form.get("project_id")
    if not title or not project_id:
        flash("Misión incompleta.", "warning")
        return redirect(url_for("missions.list_missions"))
    project = db.session.get(Project, int(project_id))
    if not project:
        flash("Territorio no encontrado.", "danger")
        return redirect(url_for("missions.list_missions"))
    mission = Mission(
        project_id=project.id,
        title=title,
        description=request.form.get("description") or "",
        type=request.form.get("type") or "DEVELOPMENT",
        priority=int(request.form.get("priority") or 3),
        xp_reward=int(request.form.get("xp_reward") or 5),
        estimated_hours=float(request.form.get("estimated_hours") or 1),
        due_date=_parse_date(request.form.get("due_date")),
        status="OPEN",
    )
    db.session.add(mission)
    db.session.flush()
    raw_obj = request.form.get("objectives") or ""
    for i, line in enumerate(raw_obj.splitlines()):
        line = line.strip()
        if line:
            db.session.add(
                MissionObjective(mission_id=mission.id, description=line, completed=False, position=i)
            )
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
    flash("Misión desplegada.", "success")
    return redirect(request.form.get("next") or url_for("missions.list_missions"))


@bp.route("/<int:mission_id>/complete", methods=["POST"])
@login_required
def complete(mission_id: int):
    mission = db.session.get(Mission, mission_id)
    if not mission:
        flash("Misión no encontrada.", "danger")
        return redirect(url_for("missions.list_missions"))
    mission.status = "DONE"
    mission.completed_at = datetime.utcnow()
    for obj in mission.objectives:
        obj.completed = True
    XPService.award(
        "complete_task",
        project=mission.project,
        description=f"Misión completada: {mission.title}",
        extra_xp=mission.xp_reward or XPService.reward_for("complete_task"),
    )
    EventService.emit(
        f"Misión completada — {mission.project.name}",
        description=mission.title,
        kind="success",
        icon="fa-trophy",
        project=mission.project,
        commit=False,
    )
    MetricsService.refresh_project(mission.project)
    db.session.commit()
    flash("Misión cumplida.", "success")
    return redirect(request.referrer or url_for("missions.list_missions"))


@bp.route("/<int:mission_id>/objectives/<int:obj_id>/toggle", methods=["POST"])
@login_required
def toggle_objective(mission_id: int, obj_id: int):
    obj = db.session.get(MissionObjective, obj_id)
    if obj and obj.mission_id == mission_id:
        obj.completed = not obj.completed
        if obj.mission.objectives and all(o.completed for o in obj.mission.objectives):
            obj.mission.status = "IN_PROGRESS"
        db.session.commit()
    return redirect(request.referrer or url_for("missions.list_missions"))


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None
