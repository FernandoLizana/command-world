from __future__ import annotations

import copy
import json
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import Goal, Mission, MissionObjective, Project
from app.models.constants import DEFAULT_XP_REWARDS  # noqa: F401
from app.services.dependency_service import DependencyService
from app.services.event_service import EventService
from app.services.project_service import ProjectService
from app.services.xp_service import XPService

TEMPLATES = [
    {
        "id": "servicio-profesional",
        "name": "Lanzar un servicio profesional",
        "usage": "freelance",
        "goal": "Tener una oferta clara y una primera conversación de venta.",
        "missions": [
            {"title": "Escribir la oferta en una página", "minutes": 90, "deps": []},
            {"title": "Definir precio y alcance", "minutes": 60, "deps": [0]},
            {"title": "Contactar a 5 personas relevantes", "minutes": 60, "deps": [1]},
        ],
    },
    {
        "id": "tienda",
        "name": "Abrir una pequeña tienda o catálogo",
        "usage": "business",
        "goal": "Publicar un catálogo mínimo y un canal de pedido.",
        "missions": [
            {"title": "Listar 5 productos con precio", "minutes": 90, "deps": []},
            {"title": "Elegir canal de venta", "minutes": 45, "deps": []},
            {"title": "Publicar el catálogo", "minutes": 60, "deps": [0, 1]},
        ],
    },
    {
        "id": "app-digital",
        "name": "Crear una app o producto digital",
        "usage": "product",
        "goal": "Una versión usable por una persona real.",
        "missions": [
            {"title": "Describir el problema en 5 frases", "minutes": 40, "deps": []},
            {"title": "Prototipo navegable", "minutes": 180, "deps": [0]},
            {"title": "Probarlo con un usuario", "minutes": 60, "deps": [1]},
        ],
    },
    {
        "id": "encargo-cliente",
        "name": "Gestionar un encargo de un cliente",
        "usage": "freelance",
        "goal": "Entregar el encargo con alcance y fecha claros.",
        "missions": [
            {"title": "Confirmar alcance por escrito", "minutes": 30, "deps": []},
            {"title": "Planificar hitos de entrega", "minutes": 40, "deps": [0]},
            {"title": "Primera entrega parcial", "minutes": 120, "deps": [1]},
        ],
    },
    {
        "id": "campana",
        "name": "Preparar una campaña de contenido",
        "usage": "business",
        "goal": "Publicar una pieza y medir una reacción real.",
        "missions": [
            {"title": "Elegir un mensaje y un canal", "minutes": 30, "deps": []},
            {"title": "Borrador de la pieza", "minutes": 90, "deps": [0]},
            {"title": "Publicar y anotar el resultado", "minutes": 40, "deps": [1]},
        ],
    },
    {
        "id": "aprendizaje",
        "name": "Proyecto personal de aprendizaje",
        "usage": "personal",
        "goal": "Terminar un artefacto pequeño que demuestre lo aprendido.",
        "missions": [
            {"title": "Definir qué quieres poder hacer", "minutes": 25, "deps": []},
            {"title": "Una práctica de 45 minutos", "minutes": 45, "deps": [0]},
            {"title": "Dejar constancia del resultado", "minutes": 20, "deps": [1]},
        ],
    },
]


class TemplateService:
    @staticmethod
    def list() -> list[dict]:
        custom = Path(current_app.instance_path) / "templates"
        items = [copy.deepcopy(t) for t in TEMPLATES]
        if custom.exists():
            for path in custom.glob("*.json"):
                try:
                    items.append(json.loads(path.read_text(encoding="utf-8")))
                except (OSError, json.JSONDecodeError):
                    continue
        return items

    @staticmethod
    def get(template_id: str) -> dict | None:
        return next((t for t in TemplateService.list() if t["id"] == template_id), None)

    @staticmethod
    def instantiate(template_id: str, name: str, selected: list[int] | None = None) -> Project:
        spec = TemplateService.get(template_id)
        if not spec:
            raise ValueError("Plantilla no encontrada.")
        missions_spec = spec["missions"]
        keep = set(selected if selected is not None else range(len(missions_spec)))
        project = ProjectService.create(
            {
                "name": (name or spec["name"]).strip(),
                "description": spec["goal"],
                "status": "ACTIVE",
                "building_type": "city",
            }
        )
        goal = Goal(
            project_id=project.id,
            title=spec["goal"],
            kind="milestone",
            is_primary=True,
            success_criteria=spec["goal"],
            status="active",
        )
        db.session.add(goal)
        db.session.flush()
        created: dict[int, Mission] = {}
        for idx, ms in enumerate(missions_spec):
            if idx not in keep:
                continue
            mission = Mission(
                project_id=project.id,
                title=ms["title"],
                status="OPEN",
                estimated_minutes=ms.get("minutes"),
                goal_id=goal.id,
                description="Estimación orientativa de plantilla; ajústala.",
            )
            db.session.add(mission)
            db.session.flush()
            db.session.add(MissionObjective(mission_id=mission.id, description=ms["title"]))
            created[idx] = mission
        for idx, ms in enumerate(missions_spec):
            if idx not in created:
                continue
            for dep in ms.get("deps") or []:
                if dep in created:
                    DependencyService.add(created[idx].id, created[dep].id)
        XPService.award("create_task", project=project, description=f"Plantilla {spec['name']}")
        EventService.emit(
            f"Proyecto creado — {project.name}",
            description=spec["name"],
            kind="info",
            icon="fa-flag",
            project=project,
        )
        db.session.commit()
        return project
