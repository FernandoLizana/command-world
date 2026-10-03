"""Shared constants and display helpers for the empire."""

from __future__ import annotations

PROJECT_STATUSES = ("ACTIVE", "PAUSED", "BLOCKED", "EXPERIMENT", "ARCHIVED")

STATUS_META = {
    "ACTIVE": {"label": "Activo", "color": "#6bcb77", "dot": "🟢"},
    "PAUSED": {"label": "Pausado", "color": "#e8b44c", "dot": "🟡"},
    "BLOCKED": {"label": "Bloqueado", "color": "#e05656", "dot": "🔴"},
    "EXPERIMENT": {"label": "Experimento", "color": "#5b8def", "dot": "🔵"},
    "ARCHIVED": {"label": "Archivado", "color": "#6b7280", "dot": "⚫"},
}

MISSION_TYPES = (
    "DEVELOPMENT",
    "SALES",
    "MARKETING",
    "QA",
    "INFRASTRUCTURE",
    "RESEARCH",
    "ADMINISTRATION",
)

MISSION_TYPE_META = {
    "DEVELOPMENT": {"label": "Desarrollo", "icon": "fa-hammer", "building": "Taller"},
    "SALES": {"label": "Ventas", "icon": "fa-coins", "building": "Mercado"},
    "MARKETING": {"label": "Marketing", "icon": "fa-bullhorn", "building": "Torre"},
    "QA": {"label": "QA", "icon": "fa-shield-halved", "building": "Cuartel"},
    "INFRASTRUCTURE": {"label": "Infraestructura", "icon": "fa-server", "building": "Cuartel"},
    "RESEARCH": {"label": "Investigación", "icon": "fa-flask", "building": "Laboratorio"},
    "ADMINISTRATION": {"label": "Administración", "icon": "fa-scroll", "building": "Archivo"},
}

MISSION_STATUSES = ("OPEN", "IN_PROGRESS", "DONE", "CANCELLED")

WORK_STATES = (
    "idea",
    "todo",
    "planned",
    "active",
    "waiting",
    "review",
    "done",
    "cancelled",
    "archived",
)

WORK_STATE_TO_STATUS = {
    "idea": "OPEN",
    "todo": "OPEN",
    "planned": "OPEN",
    "active": "IN_PROGRESS",
    "waiting": "OPEN",
    "review": "IN_PROGRESS",
    "done": "DONE",
    "cancelled": "CANCELLED",
    "archived": "CANCELLED",
}

SPECIALTY_SPRITE = {
    "DEVELOPMENT": "developer",
    "SALES": "sales",
    "MARKETING": "marketing",
    "QA": "qa",
    "INFRASTRUCTURE": "infrastructure",
    "RESEARCH": "researcher",
    "ADMINISTRATION": "sales",
}

SPECIALTY_ROLE = {
    "DEVELOPMENT": "constructor",
    "SALES": "mercader",
    "MARKETING": "explorador",
    "QA": "guardian",
    "INFRASTRUCTURE": "artesano",
    "RESEARCH": "erudito",
    "ADMINISTRATION": "escriba",
}

CONSTRUCTION_PHASES = (
    "sin_definir",
    "cimientos",
    "estructura",
    "preparacion",
    "apertura",
    "completado",
)

OPPORTUNITY_STATUSES = (
    "LEAD",
    "CONTACTED",
    "MEETING",
    "PROPOSAL",
    "NEGOTIATION",
    "WON",
    "LOST",
)

ISSUE_SEVERITIES = ("LOW", "MEDIUM", "HIGH", "CRITICAL")
ISSUE_STATUSES = ("OPEN", "IN_PROGRESS", "RESOLVED")

TECH_STATUSES = ("LOCKED", "AVAILABLE", "IN_PROGRESS", "COMPLETED")

LEVEL_NAMES = {
    0: "Idea",
    1: "Campamento",
    2: "Aldea / prototipo",
    3: "Pueblo / MVP",
    4: "Ciudad / usuarios",
    5: "Capital / producto estable",
}

BUILDING_TYPES = (
    "capital",
    "fortress",
    "city",
    "village",
    "lab",
    "camp",
    "market",
    "sanctuary",
    "command_center",
    "tower",
    "laboratory",
    "workshop",
    "barracks",
    "datacenter",
    "hospital",
)

DEFAULT_XP_REWARDS = {
    "create_task": 1,
    "complete_task": 5,
    "resolve_bug": 10,
    "add_feature": 15,
    "contact_prospect": 3,
    "sales_meeting": 20,
    "new_client": 100,
    "first_revenue": 200,
    "complete_mission": 25,
    "end_turn": 5,
    "level_up": 50,
}

METRIC_KEYS = (
    "product_score",
    "technology_score",
    "sales_score",
    "marketing_score",
    "finance_score",
    "stability_score",
)

METRIC_LABELS = {
    "product_score": "Producto",
    "technology_score": "Tecnología",
    "sales_score": "Ventas",
    "marketing_score": "Marketing",
    "finance_score": "Finanzas",
    "stability_score": "Estabilidad",
    "momentum": "Momentum",
    "health": "Salud",
}
