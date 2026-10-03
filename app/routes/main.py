from flask import Blueprint, render_template
from flask_login import login_required

from app.services.game_service import GameService

bp = Blueprint("main", __name__)


@bp.route("/")
@login_required
def map_view():
    return render_template("command/map.html", world=True, hud=GameService.hud())


@bp.route("/turn/end", methods=["POST"])
@login_required
def end_turn():
    from flask import flash, redirect, request, url_for

    from app.services.turn_service import TurnService

    log = TurnService.end_turn()
    flash(f"Turno {log.turn_number} cerrado.", "success")
    return redirect(request.referrer or url_for("main.map_view"))
