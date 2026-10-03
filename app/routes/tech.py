from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.extensions import db
from app.models import Technology
from app.models.constants import TECH_STATUSES
from app.services.event_service import EventService
from app.services.xp_service import XPService

bp = Blueprint("tech", __name__)


@bp.route("/", strict_slashes=False)
@login_required
def tree():
    techs = Technology.query.order_by(Technology.category, Technology.position).all()
    grouped: dict[str, list[Technology]] = {}
    for t in techs:
        grouped.setdefault(t.category, []).append(t)
    return render_template("command/tech_tree.html", grouped=grouped, statuses=TECH_STATUSES)


@bp.route("/<int:tech_id>/status", methods=["POST"])
@login_required
def set_status(tech_id: int):
    tech = db.session.get(Technology, tech_id)
    status = request.form.get("status")
    if tech and status in TECH_STATUSES:
        tech.status = status
        if status == "COMPLETED":
            tech.progress = 100
            XPService.award("add_feature", description=f"Tecnología: {tech.name}", extra_xp=tech.xp_reward)
            EventService.emit(
                f"Tecnología completada: {tech.name}",
                kind="success",
                icon="fa-microchip",
                commit=False,
            )
        db.session.commit()
        flash(f"{tech.name} → {status}", "success")
    return redirect(url_for("tech.tree"))
