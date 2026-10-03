"""Agent specializations of AIService. No autonomous side effects."""

from __future__ import annotations

from app.ai import prompts
from app.ai.service import AIService

AGENTS = {
    "counselor": {
        "name": "Consejero",
        "icon": "fa-hat-wizard",
        "role": "Estrategia general",
        "system": prompts.SYSTEM_COUNSELOR,
    },
    "explorer": {
        "name": "Explorador",
        "icon": "fa-user-secret",
        "role": "Ventas / prospectos",
        "system": prompts.SYSTEM_EXPLORER,
    },
    "engineer": {
        "name": "Ingeniero",
        "icon": "fa-hammer",
        "role": "Desarrollo / deuda técnica",
        "system": prompts.SYSTEM_ENGINEER,
    },
    "merchant": {
        "name": "Mercader",
        "icon": "fa-coins",
        "role": "Ventas / ingresos",
        "system": prompts.SYSTEM_MERCHANT,
    },
    "herald": {
        "name": "Heraldo",
        "icon": "fa-bullhorn",
        "role": "Marketing",
        "system": prompts.SYSTEM_HERALD,
    },
    "guard": {
        "name": "Guardia",
        "icon": "fa-shield-halved",
        "role": "QA / infraestructura / seguridad",
        "system": prompts.SYSTEM_GUARD,
    },
}


def ask_agent(agent_key: str, question: str) -> dict:
    spec = AGENTS.get(agent_key, AGENTS["counselor"])
    ai = AIService.from_app()
    result = ai.advise(question, system=spec["system"])
    result["agent"] = spec["name"]
    result["agent_key"] = agent_key
    return result
