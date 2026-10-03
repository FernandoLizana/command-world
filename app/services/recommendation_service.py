from __future__ import annotations

from datetime import datetime

from app.models import Mission, Project
from app.services.game_service import GameService


class RecommendationService:
    """Deterministic advisor used when Ollama is down, and as a baseline."""

    @staticmethod
    def freeze_candidates() -> list[dict]:
        now = datetime.utcnow()
        out = []
        for p in Project.query.filter(Project.status.in_(["ACTIVE", "EXPERIMENT", "PAUSED"])).all():
            days = (now - p.last_activity).days if p.last_activity else 99
            open_missions = p.open_missions_count
            open_opps = p.open_opportunities_count
            if p.momentum < 25 and days >= 10 and open_missions == 0 and open_opps == 0:
                out.append(
                    {
                        "project": p.name,
                        "slug": p.slug,
                        "reason": f"Momentum {p.momentum}%, {days} días sin actividad, sin misiones ni oportunidades.",
                    }
                )
        return out

    @staticmethod
    def today(hours: float | None = None) -> dict:
        empire = GameService.hud()
        hours = hours if hours is not None else empire["available_hours"]
        active = Project.query.filter(Project.status.in_(["ACTIVE", "EXPERIMENT"])).all()
        blocked = [p for p in active if p.status == "BLOCKED" or p.critical_alerts]
        commercial = sorted(
            active,
            key=lambda p: (p.sales_score + p.open_opportunities_count * 8, p.potential_revenue),
            reverse=True,
        )
        neglected = sorted(
            active,
            key=lambda p: (p.momentum, p.last_activity or datetime(2000, 1, 1)),
        )
        priority = sorted(active, key=lambda p: (p.priority, -p.momentum))

        focus = priority[0] if priority else None
        abandoned = neglected[0] if neglected else None
        best_commercial = commercial[0] if commercial else None

        missions = (
            Mission.query.filter(Mission.status.in_(["OPEN", "IN_PROGRESS"]))
            .order_by(Mission.priority.asc())
            .limit(5)
            .all()
        )

        recs = []
        if focus:
            recs.append(
                f"Invertir las próximas {int(hours) or 3} h en {focus.name} "
                f"(prioridad {focus.priority}, momentum {focus.momentum}%)."
            )
        if best_commercial and best_commercial.open_opportunities_count:
            recs.append(
                f"{best_commercial.name} tiene la mejor pista comercial "
                f"({best_commercial.open_opportunities_count} oportunidades, ventas {best_commercial.sales_score})."
            )
        if abandoned and abandoned.momentum < 35:
            recs.append(
                f"{abandoned.name} es el más abandonado (momentum {abandoned.momentum}%). "
                "O reactívalo 1 hora, o congélalo conscientemente."
            )
        for p in blocked[:2]:
            recs.append(f"Atender bloqueos en {p.name} ({p.critical_alerts} alertas).")

        freeze = RecommendationService.freeze_candidates()
        suggested = [m.to_dict() for m in missions]
        return {
            "summary": recs[0] if recs else "No hay proyectos activos. Funda el primer territorio.",
            "priority_project": focus.name if focus else None,
            "priority_project_id": focus.id if focus else None,
            "priority_slug": focus.slug if focus else None,
            "recommendations": recs[:6],
            "risks": [f"{p.name}: {p.critical_alerts} alertas" for p in blocked],
            "projects_to_watch": [p.name for p in neglected[:3]],
            "freeze_candidates": freeze,
            "suggested_missions": suggested,
            "source": "rules",
        }

    @staticmethod
    def narrate(question: str | None = None) -> dict:
        """Concrete one-screen advice. Never calls the language model."""
        data = RecommendationService.today()
        q = (question or "").strip().lower()
        focus_name = data.get("priority_project")
        missions = data.get("suggested_missions") or []
        top = missions[0] if missions else None
        blocked = data.get("risks") or []
        recs = data.get("recommendations") or []

        commercial = next((r for r in recs if "pista comercial" in r or "oportunidad" in r), None)
        create = None
        if top:
            create = {
                "project_id": top.get("project_id"),
                "project_name": top.get("project_name"),
                "title": top.get("title"),
            }
        elif data.get("priority_project_id"):
            create = {
                "project_id": data["priority_project_id"],
                "project_name": focus_name,
                "title": f"Avanzar {focus_name}",
            }

        if any(k in q for k in ("dinero", "venta", "ingreso", "cobr", "cash")):
            answer = commercial or (
                f"{focus_name} es el territorio con más palanca comercial ahora."
                if focus_name
                else "No hay pistas comerciales abiertas."
            )
            if top and top.get("type") == "SALES":
                answer += f" Siguiente paso: {top['title']}."
            else:
                answer += " Recomiendo una misión de venta corta."
        elif any(k in q for k in ("bloque", "alerta", "problema", "bug")):
            if blocked:
                answer = "Hay bloqueos: " + "; ".join(blocked[:3]) + ". Atiéndelos antes de expandir."
            else:
                answer = "Nada crítico está bloqueado. Sigue la misión de mayor prioridad."
        elif any(k in q for k in ("turno", "hoy", "minutos", "capacidad")):
            from app.services.daily_turn_service import DailyTurnService

            turn = DailyTurnService.suggest(30)
            items = turn.get("items") or []
            if items:
                answer = "Turno de 30 min (reglas locales, no IA): " + "; ".join(
                    f"{i['title']} ({i.get('reason')})" for i in items
                )
            else:
                answer = "Ninguna misión cabe en 30 minutos. Sube el presupuesto o divide una tarea."
        elif any(k in q for k in ("resumen", "estado de los proyecto", "cómo van")):
            answer = data.get("summary") or "No hay proyectos activos."
            extra = data.get("recommendations") or []
            if extra:
                answer += " " + " ".join(extra[:3])
        elif any(k in q for k in ("seguimiento", "borrador", "correo", "mensaje")):
            answer = (
                "Borrador para copiar: Hola, retomo nuestra conversación. "
                "¿Sigues interesado en avanzar? Puedo proponerte un siguiente paso concreto esta semana. "
                "La IA no envía este texto; edítalo tú."
            )
        elif any(k in q for k in ("divide", "pasos", "partir")):
            if top:
                answer = (
                    f"Hechos: misión abierta «{top['title']}». Propuesta (reglas, no modelo): "
                    "1) definir el resultado mínimo, 2) ejecutar un bloque de 25 min, 3) anotar evidencia. "
                    "Nada se crea hasta que pulses Crear misión."
                )
            else:
                answer = "No hay una misión abierta para partir. Crea primero un paso concreto."
        elif any(k in q for k in ("prioriz", "cuál", "cual", "qué proyecto", "que proyecto")):
            answer = (
                f"{focus_name} tiene la mejor relación entre progreso y potencial."
                if focus_name
                else "No hay un territorio claro para priorizar."
            )
            if top:
                answer += f" Recomiendo completar: {top['title']}."
        else:
            if top:
                answer = (
                    f"Ahora: {top['project_name']}. {data['summary']} "
                    f"Misión lista: {top['title']}. ¿Crear o continuar esa misión?"
                )
            else:
                answer = data.get("summary") or "Observa el mapa y elige un edificio con alerta."

        return {
            **data,
            "question": question or "¿Qué hago ahora?",
            "answer": answer.strip(),
            "suggested_mission": top,
            "create_mission": create,
            "ai_status": "rules",
        }

    @staticmethod
    def compact_context(limit_projects: int = 8) -> dict:
        """Short context for the AI. Never dump the whole database."""
        hud = GameService.hud()
        projects = []
        for p in Project.query.order_by(Project.priority.asc()).limit(limit_projects).all():
            open_issues = [
                {"title": i.title, "severity": i.severity}
                for i in p.issues
                if i.status != "RESOLVED"
            ][:3]
            opps = [
                {"name": o.name, "status": o.status, "value": o.estimated_value}
                for o in p.opportunities
                if o.status not in {"WON", "LOST"}
            ][:3]
            missions = [
                {"title": m.title, "type": m.type, "status": m.status}
                for m in p.missions
                if m.status in {"OPEN", "IN_PROGRESS"}
            ][:4]
            days = (datetime.utcnow() - p.last_activity).days if p.last_activity else None
            projects.append(
                {
                    "name": p.name,
                    "status": p.status,
                    "level": p.level,
                    "health": p.health,
                    "momentum": p.momentum,
                    "priority": p.priority,
                    "scores": {
                        "product": p.product_score,
                        "tech": p.technology_score,
                        "sales": p.sales_score,
                        "marketing": p.marketing_score,
                        "finance": p.finance_score,
                        "stability": p.stability_score,
                    },
                    "monthly_revenue": p.monthly_revenue,
                    "potential_revenue": p.potential_revenue,
                    "days_since_activity": days,
                    "issues": open_issues,
                    "opportunities": opps,
                    "missions": missions,
                }
            )
        return {"empire": hud, "projects": projects}
