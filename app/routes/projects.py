from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.ai.service import AIService
from app.extensions import db
from app.game.levels import pending_requirements, try_level_up
from app.models import Note, Project
from app.models.constants import (
    BUILDING_TYPES,
    METRIC_LABELS,
    PROJECT_STATUSES,
    STATUS_META,
)
from app.services.event_service import EventService
from app.services.finance_service import FinanceService
from app.services.metrics_service import MetricsService
from app.services.project_service import ProjectService

bp = Blueprint("projects", __name__)


@bp.route("/", strict_slashes=False)
@login_required
def list_projects():
    status = request.args.get("status")
    q = Project.query
    if status:
        q = q.filter_by(status=status)
    projects = q.order_by(Project.priority.asc(), Project.name.asc()).all()
    return render_template(
        "command/projects.html",
        projects=projects,
        statuses=PROJECT_STATUSES,
        status_meta=STATUS_META,
        filter_status=status,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def create_project():
    if request.method == "POST":
        name = (request.form.get("name") or "").strip()
        if not name:
            flash("El territorio necesita un nombre.", "warning")
            return redirect(url_for("projects.create_project"))
        project = ProjectService.create(request.form)
        EventService.emit(
            f"Nueva ciudad: {project.name}",
            kind="success",
            icon="fa-flag",
            project=project,
        )
        flash(f"{project.name} ha sido fundada.", "success")
        return redirect(url_for("projects.detail", slug=project.slug))
    return render_template(
        "command/project_form.html",
        project=None,
        statuses=PROJECT_STATUSES,
        building_types=BUILDING_TYPES,
    )


@bp.route("/<slug>")
@login_required
def detail(slug: str):
    project = Project.query.filter_by(slug=slug).first_or_404()
    bars = MetricsService.metric_bars(project)
    recs = pending_requirements(project)
    advice = None
    try:
        ai = AIService.from_app()
        if ai.is_available():
            advice = ai.advise(
                f"Recomendación breve para el proyecto {project.name} en las próximas 3 horas."
            )
        else:
            advice = {
                "summary": f"Consejero no disponible. Momentum {project.momentum}%. "
                f"{project.open_missions_count} misiones abiertas.",
                "recommendations": [],
                "source": "rules",
                "ai_status": "unavailable",
            }
    except Exception:
        advice = {"summary": "Consejero temporalmente no disponible.", "ai_status": "unavailable"}
    return render_template(
        "command/project.html",
        project=project,
        bars=bars,
        requirements=recs,
        metric_labels=METRIC_LABELS,
        advice=advice,
        missions=sorted(project.missions, key=lambda m: (m.status == "DONE", m.priority)),
        opportunities=project.opportunities,
        issues=project.issues,
        events=sorted(project.events, key=lambda e: e.created_at, reverse=True)[:8],
        goals=project.goals,
        notes=Note.query.filter_by(project_id=project.id).order_by(Note.created_at.desc()).all(),
        money=FinanceService.totals(project.id),
    )


@bp.route("/<slug>/city")
@login_required
def city(slug: str):
    project = Project.query.filter_by(slug=slug).first_or_404()
    from app.services.game_service import GameService

    payload = GameService.city_payload(project)
    return render_template("command/city.html", project=project, modules=payload["modules"])


@bp.route("/<slug>/edit", methods=["GET", "POST"])
@login_required
def edit(slug: str):
    project = Project.query.filter_by(slug=slug).first_or_404()
    if request.method == "POST":
        ProjectService.update(project, request.form)
        flash("Territorio actualizado.", "success")
        return redirect(url_for("projects.detail", slug=project.slug))
    return render_template(
        "command/project_form.html",
        project=project,
        statuses=PROJECT_STATUSES,
        building_types=BUILDING_TYPES,
    )


@bp.route("/<slug>/level-up", methods=["POST"])
@login_required
def level_up(slug: str):
    project = Project.query.filter_by(slug=slug).first_or_404()
    if try_level_up(project):
        flash(f"{project.name} evoluciona a nivel {project.level}.", "success")
    else:
        flash("Aún faltan requisitos para evolucionar.", "warning")
    return redirect(url_for("projects.detail", slug=project.slug))


@bp.route("/<slug>/requirements/<int:req_id>/toggle", methods=["POST"])
@login_required
def toggle_requirement(slug: str, req_id: int):
    project = Project.query.filter_by(slug=slug).first_or_404()
    req = next((r for r in project.level_requirements if r.id == req_id), None)
    if req:
        req.completed = not req.completed
        db.session.commit()
    return redirect(url_for("projects.detail", slug=project.slug))
