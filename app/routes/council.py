from datetime import datetime

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

from app.ai.agents import AGENTS, ask_agent
from app.ai.service import AIService
from app.extensions import db
from app.models import CouncilDecision
from app.services.event_service import EventService
from app.services.recommendation_service import RecommendationService

bp = Blueprint("council", __name__)


@bp.route("/", strict_slashes=False)
@login_required
def view():
    if not request.args.get("full"):
        return redirect(url_for("main.map_view") + "#ia")
    ai = AIService.from_app()
    available = ai.is_available()
    question = request.args.get("q") or ""
    advice = ai.advise(question) if question else ai.council()
    history = (
        CouncilDecision.query.order_by(CouncilDecision.created_at.desc()).limit(8).all()
    )
    freeze = RecommendationService.freeze_candidates()
    return render_template(
        "command/council.html",
        advice=advice,
        ai_available=available,
        agents=AGENTS,
        history=history,
        freeze=freeze,
        question=question,
    )


@bp.route("/ask", methods=["POST"])
@login_required
def ask():
    question = (request.form.get("question") or "").strip()
    agent = request.form.get("agent") or "counselor"
    result = ask_agent(agent, question or "¿Qué debería hacer hoy?")
    history = (
        CouncilDecision.query.order_by(CouncilDecision.created_at.desc()).limit(8).all()
    )
    return render_template(
        "command/council.html",
        advice=result,
        ai_available=AIService.from_app().is_available(),
        agents=AGENTS,
        history=history,
        freeze=RecommendationService.freeze_candidates(),
        question=question,
        selected_agent=agent,
    )


@bp.route("/decide", methods=["POST"])
@login_required
def decide():
    decision = request.form.get("decision") or "accepted"
    notes = request.form.get("notes") or ""
    summary = request.form.get("summary") or ""
    payload = request.form.get("payload") or "{}"
    if decision not in {"accepted", "modified", "rejected"}:
        decision = "accepted"
    row = CouncilDecision(
        summary=summary,
        payload_json=payload,
        decision=decision,
        user_notes=notes,
        decided_at=datetime.utcnow(),
    )
    db.session.add(row)
    EventService.emit(
        f"Consejo de guerra: {decision}",
        description=summary[:180],
        kind="council",
        icon="fa-landmark",
        commit=False,
    )
    db.session.commit()
    labels = {
        "accepted": "Decisión registrada. Ninguna automatización externa se ejecutó.",
        "modified": "Modificación anotada. Tú sigues al mando.",
        "rejected": "Recomendación rechazada.",
    }
    flash(labels[decision], "info")
    return redirect(url_for("council.view"))
