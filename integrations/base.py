"""
Future integrations live here. Nothing is connected yet.

Rule: an integration may read or propose. It must NEVER mutate production
systems, send mail, or spend money without an explicit human approval record.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class Integration(ABC):
    key: str
    label: str
    description: str

    def enabled(self) -> bool:
        return False

    @abstractmethod
    def status(self) -> dict[str, Any]:
        ...

    def pull(self) -> list[dict[str, Any]]:
        return []


class GitHubIntegration(Integration):
    key = "github"
    label = "GitHub / Git"
    description = "Actividad de repositorios y deploys (futuro)."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class GmailIntegration(Integration):
    key = "gmail"
    label = "Gmail"
    description = "Lectura de hilos comerciales (futuro). Nunca envía solo."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class CalendarIntegration(Integration):
    key = "google_calendar"
    label = "Google Calendar"
    description = "Reuniones y carga semanal (futuro)."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class CRMIntegration(Integration):
    key = "crm"
    label = "CRM"
    description = "Sincronizar oportunidades (futuro)."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class ObservabilityIntegration(Integration):
    key = "observability"
    label = "Observabilidad"
    description = "Salud de monitoreo y QA (futuro)."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class ServersIntegration(Integration):
    key = "servers"
    label = "Servidores"
    description = "Inventario y estado (futuro). Sin acciones de deploy."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class MonitoringIntegration(Integration):
    key = "monitoring"
    label = "Monitoreo"
    description = "Alertas operativas (futuro)."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class ProspectsIntegration(Integration):
    key = "prospects"
    label = "Prospectos"
    description = "Fuentes de leads (futuro)."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class TendersIntegration(Integration):
    key = "tenders"
    label = "Licitaciones"
    description = "Radar de licitaciones (futuro)."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class SalesIntegration(Integration):
    key = "sales"
    label = "Ventas"
    description = "Cierres e ingresos (futuro)."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


class DomainsIntegration(Integration):
    key = "domains"
    label = "Dominios propios"
    description = "Inventario de dominios (futuro)."

    def status(self) -> dict[str, Any]:
        return {"key": self.key, "ready": False}


REGISTRY: list[type[Integration]] = [
    GitHubIntegration,
    GmailIntegration,
    CalendarIntegration,
    CRMIntegration,
    ObservabilityIntegration,
    ServersIntegration,
    MonitoringIntegration,
    ProspectsIntegration,
    TendersIntegration,
    SalesIntegration,
    DomainsIntegration,
]


def catalog() -> list[dict[str, Any]]:
    out = []
    for cls in REGISTRY:
        inst = cls()
        out.append(
            {
                "key": inst.key,
                "label": inst.label,
                "description": inst.description,
                "enabled": inst.enabled(),
                "status": inst.status(),
            }
        )
    return out
