from __future__ import annotations

import logging

from flask import current_app

from app.extensions import db
from app.models import Empire, GameSetting, Issue, Opportunity, Project
from app.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)


class GameService:
    @staticmethod
    def get_empire() -> Empire:
        empire = db.session.get(Empire, 1)
        if empire is None:
            empire = Empire(id=1)
            db.session.add(empire)
            db.session.commit()
        return empire

    @staticmethod
    def hud() -> dict:
        empire = GameService.get_empire()
        projects = Project.query.all()
        active = sum(1 for p in projects if p.status in {"ACTIVE", "EXPERIMENT"})
        opportunities = Opportunity.query.filter(Opportunity.status.notin_(["WON", "LOST"])).count()
        alerts = Issue.query.filter(
            Issue.status != "RESOLVED", Issue.severity.in_(["HIGH", "CRITICAL"])
        ).count()
        return {
            "name": empire.name,
            "money": empire.money,
            "available_hours": empire.available_hours,
            "projects_active": active,
            "projects_total": len(projects),
            "opportunities": opportunities,
            "alerts": alerts,
            "level": empire.level,
            "xp": empire.xp,
            "turn": empire.current_turn,
        }

    @staticmethod
    def visual_settings() -> dict:
        def flag(key: str, default: str) -> bool:
            raw = GameSetting.get(key, default)
            return str(raw).lower() not in {"0", "false", "off", "no"}

        from app.services.world_service import WorldService

        prefs = WorldService.prefs()
        quiet = prefs.get("gamification") == "quiet"
        return {
            "day_night": flag("day_night", "true") and not quiet,
            "fog": flag("fog", "true") and not quiet,
            "sound": (str(GameSetting.get("sound_enabled", "false")).lower() in {"1", "true", "on", "yes"}
            or bool(current_app.config.get("SOUND_ENABLED")))
            and prefs.get("gamification") != "quiet",
            "demo": bool(current_app.config.get("DEMO_MODE")),
            "quiet": quiet,
            "gamification": prefs.get("gamification") or "balanced",
            "animations": False if quiet else prefs.get("animations", True),
        }

    @staticmethod
    def map_payload() -> dict:
        MetricsService.refresh_all()
        db.session.commit()
        from app.services.recommendation_service import RecommendationService

        projects = Project.query.filter(Project.status != "ARCHIVED").all()
        cities = [p.to_map_dict() for p in projects]
        capital = next((c for c in cities if c.get("building") == "capital"), cities[0] if cities else None)
        advisor = {
            "id": "command",
            "slug": "centro-ia",
            "name": "Centro de Mando IA",
            "kind": "advisor",
            "building": "command_center",
            "x": (capital["x"] + 176) if capital else 1472,
            "y": (capital["y"] - 96) if capital else 672,
            "level": 5,
            "level_name": "Asesor",
            "health": 100,
            "momentum": 80,
            "status": "ACTIVE",
            "status_label": "Asesor",
            "color": "#c9a227",
            "alerts": 0,
            "missions": 0,
            "opportunities": 0,
            "priority": 0,
            "critical": False,
            "progress": 100,
            "description": "Pregunta qué hacer ahora. La IA recomienda. Tú decides.",
            "activity": {"ADMINISTRATION": 1},
        }
        now = RecommendationService.narrate("¿Qué hago ahora?")
        return {
            "empire": GameService.hud(),
            "cities": cities,
            "advisor": advisor,
            "now": {
                "summary": now.get("answer") or now.get("summary"),
                "project": now.get("priority_project"),
                "slug": now.get("priority_slug"),
                "mission": now.get("suggested_mission"),
            },
            "visual": GameService.visual_settings(),
            "regions": [],
        }

    @staticmethod
    def city_payload(project: Project) -> dict:
        modules = [
            {
                "key": "core",
                "label": "Core",
                "building": "command_center",
                "x": 448,
                "y": 300,
                "hint": "Centro de mando del proyecto",
                "mission_type": "ADMINISTRATION",
            }
        ]
        if project.technology_score >= 25 or any(
            m.type == "DEVELOPMENT" and m.status != "DONE" for m in project.missions
        ):
            modules.append(
                {
                    "key": "development",
                    "label": "Development",
                    "building": "workshop",
                    "x": 300,
                    "y": 220,
                    "hint": "Taller — producto y código",
                    "mission_type": "DEVELOPMENT",
                }
            )
        if project.sales_score >= 20 or project.open_opportunities_count:
            modules.append(
                {
                    "key": "sales",
                    "label": "Sales",
                    "building": "market",
                    "x": 600,
                    "y": 220,
                    "hint": "Mercado — pipeline comercial",
                    "mission_type": "SALES",
                }
            )
        if project.stability_score >= 30 or any(m.type == "QA" for m in project.missions):
            modules.append(
                {
                    "key": "qa",
                    "label": "QA",
                    "building": "barracks",
                    "x": 300,
                    "y": 400,
                    "hint": "Cuartel — calidad y estabilidad",
                    "mission_type": "QA",
                }
            )
        if project.technology_score >= 50 or project.category in {"saas", "lab"}:
            modules.append(
                {
                    "key": "monitoring",
                    "label": "Monitoring",
                    "building": "datacenter",
                    "x": 600,
                    "y": 400,
                    "hint": "Datos e infraestructura",
                    "mission_type": "INFRASTRUCTURE",
                }
            )
        if project.category in {"lab"} or any(m.type == "RESEARCH" for m in project.missions):
            modules.append(
                {
                    "key": "rnd",
                    "label": "R&D",
                    "building": "laboratory",
                    "x": 450,
                    "y": 430,
                    "hint": "Laboratorio de innovación",
                    "mission_type": "RESEARCH",
                }
            )
        if project.marketing_score >= 25:
            modules.append(
                {
                    "key": "marketing",
                    "label": "Marketing",
                    "building": "tower",
                    "x": 450,
                    "y": 180,
                    "hint": "Torre — mensaje y canales",
                    "mission_type": "MARKETING",
                }
            )
        if project.category in {"healthtech"}:
            modules.append(
                {
                    "key": "care",
                    "label": "Cuidado",
                    "building": "hospital",
                    "x": 200,
                    "y": 300,
                    "hint": "Centro de cuidado",
                    "mission_type": "RESEARCH",
                }
            )
        return {"project": project.to_map_dict(), "modules": modules}

    @staticmethod
    def update_resources(data: dict) -> Empire:
        empire = GameService.get_empire()
        if "name" in data and data["name"]:
            empire.name = data["name"]
        if "money" in data and data["money"] not in (None, ""):
            empire.money = int(data["money"])
        if "available_hours" in data and data["available_hours"] not in (None, ""):
            empire.available_hours = float(data["available_hours"])
        if "level" in data and data["level"] not in (None, ""):
            empire.level = int(data["level"])
        db.session.commit()
        return empire
