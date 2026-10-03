from flask import Blueprint, render_template
from flask_login import login_required

from app.models import GameEvent, Issue, Opportunity, Project
from app.services.recommendation_service import RecommendationService

bp = Blueprint("ops", __name__)


@bp.route("/events")
@login_required
def events():
    from flask import redirect, request, url_for

    if not request.args.get("full"):
        return redirect(url_for("main.map_view") + "#historial")
    items = GameEvent.query.order_by(GameEvent.created_at.desc()).limit(80).all()
    return render_template("command/events.html", events=items)


@bp.route("/archive")
@login_required
def archive():
    parked = (
        Project.query.filter(Project.status.in_(["PAUSED", "BLOCKED", "ARCHIVED"]))
        .order_by(Project.updated_at.desc())
        .all()
    )
    freeze = RecommendationService.freeze_candidates()
    neglected = (
        Project.query.filter(Project.status.in_(["ACTIVE", "EXPERIMENT"]))
        .order_by(Project.momentum.asc())
        .limit(4)
        .all()
    )
    return render_template(
        "command/archive.html",
        parked=parked,
        freeze=freeze,
        neglected=neglected,
    )


@bp.route("/opportunities")
@login_required
def opportunities():
    items = Opportunity.query.order_by(Opportunity.created_at.desc()).all()
    return render_template("command/opportunities.html", opportunities=items)


@bp.route("/issues")
@login_required
def issues():
    items = Issue.query.order_by(Issue.created_at.desc()).all()
    return render_template("command/issues.html", issues=items)
