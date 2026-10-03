"""
AIService — abstract advisor layer.

Essential app functions never depend on this.
The AI may only analyze, recommend, summarize, prioritize and explain.
Any future side-effect MUST go through an explicit human approval record.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from flask import current_app

from app.ai.ollama import OllamaClient
from app.ai import prompts
from app.services.recommendation_service import RecommendationService

logger = logging.getLogger(__name__)

ALLOWED_KEYS = (
    "summary",
    "priority_project",
    "recommendations",
    "risks",
    "projects_to_watch",
)

# Hard safety: the model is never given tools. This set documents forbidden intents.
FORBIDDEN_ACTIONS = {
    "delete_project",
    "delete_data",
    "send_email",
    "contact_customer",
    "execute_code",
    "deploy",
    "spend_money",
    "modify_server",
    "external_operation",
}


def _extract_json(text: str) -> dict[str, Any] | None:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?", "", text).strip()
        text = re.sub(r"```$", "", text).strip()
    try:
        data = json.loads(text)
        if isinstance(data, dict):
            return data
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        data = json.loads(match.group(0))
        return data if isinstance(data, dict) else None
    except json.JSONDecodeError:
        return None


def validate_advice(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not payload:
        return None
    summary = str(payload.get("summary") or "").strip()
    recs = payload.get("recommendations") or []
    if not summary and not recs:
        return None
    if not isinstance(recs, list):
        recs = [str(recs)]
    risks = payload.get("risks") or []
    watch = payload.get("projects_to_watch") or []
    return {
        "summary": summary,
        "priority_project": payload.get("priority_project") or None,
        "recommendations": [str(x) for x in recs][:6],
        "risks": [str(x) for x in (risks if isinstance(risks, list) else [risks])][:4],
        "projects_to_watch": [
            str(x) for x in (watch if isinstance(watch, list) else [watch])
        ][:4],
        "source": "ai",
    }


class AIService:
    def __init__(self, client: OllamaClient | None = None) -> None:
        self.client = client

    @classmethod
    def from_app(cls) -> "AIService":
        cfg = current_app.config
        client = OllamaClient(
            url=cfg["OLLAMA_URL"],
            model=cfg["OLLAMA_MODEL"],
            timeout=int(cfg.get("OLLAMA_TIMEOUT", 8)),
            enabled=bool(cfg.get("OLLAMA_ENABLED", True)),
        )
        return cls(client)

    def is_available(self) -> bool:
        if not self.client:
            return False
        return self.client.available()

    def advise(self, question: str, *, system: str | None = None) -> dict[str, Any]:
        fallback = RecommendationService.today()
        fallback["question"] = question
        if not self.is_available():
            fallback["source"] = "rules"
            fallback["ai_status"] = "unavailable"
            return fallback
        context = json.dumps(
            RecommendationService.compact_context(), ensure_ascii=False, indent=2
        )
        prompt = prompts.USER_COUNSEL_TEMPLATE.format(
            question=question.strip() or "¿Qué debería hacer hoy?",
            context=context,
        )
        try:
            raw = self.client.generate(prompt, system=system or prompts.SYSTEM_COUNSELOR)
        except RuntimeError:
            fallback["ai_status"] = "unavailable"
            return fallback
        parsed = validate_advice(_extract_json(raw))
        if not parsed:
            logger.warning("AI returned invalid JSON")
            fallback["ai_status"] = "invalid"
            return fallback
        parsed["ai_status"] = "ok"
        parsed["question"] = question
        parsed["forbidden_note"] = "La IA recomienda. El usuario gobierna."
        return parsed

    def council(self) -> dict[str, Any]:
        return self.advise(prompts.COUNCIL_QUESTION)
