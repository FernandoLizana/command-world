"""
Momentum formula (intentionally simple and documented).

Momentum answers: "is this project actually moving right now?"

    score = 0.30 * recency
          + 0.25 * mission_pace
          + 0.20 * commercial
          + 0.15 * technical
          + 0.10 * health
          - blockers

Each component is 0–100. The result is clamped to 0–100.

recency
    Days since last_activity.
    0–1d → 100 | 2–3d → 80 | 4–7d → 55 | 8–14d → 30 | 15–30d → 12 | 30+ → 4

mission_pace
    Completed missions in the last 14 days: min(100, count * 22)

commercial
    Open opportunities (not WON/LOST) * 12, plus WON in last 30 days * 20, capped at 100

technical
    Completed DEVELOPMENT / QA / INFRASTRUCTURE missions in last 14 days * 25, capped

health
    Uses the stored health metric (stability of the operation)

blockers
    BLOCKED status: −25
    Each CRITICAL open issue: −18
    Each HIGH open issue: −8
    Each OPEN issue beyond 3: −3
"""

from __future__ import annotations

from datetime import datetime, timedelta

from app.models import Issue, Mission, Opportunity, Project
from app.models.constants import METRIC_KEYS, METRIC_LABELS


def _days_since(when: datetime | None) -> float:
    if when is None:
        return 999
    return max(0.0, (datetime.utcnow() - when).total_seconds() / 86400)


def recency_score(project: Project) -> int:
    days = _days_since(project.last_activity)
    if days <= 1:
        return 100
    if days <= 3:
        return 80
    if days <= 7:
        return 55
    if days <= 14:
        return 30
    if days <= 30:
        return 12
    return 4


def mission_pace_score(project: Project, since: datetime) -> int:
    count = sum(
        1
        for m in project.missions
        if m.status == "DONE" and m.completed_at and m.completed_at >= since
    )
    return min(100, count * 22)


def commercial_score(project: Project, since: datetime) -> int:
    open_opps = sum(1 for o in project.opportunities if o.status not in {"WON", "LOST"})
    recent_wins = sum(
        1
        for o in project.opportunities
        if o.status == "WON" and o.created_at and o.created_at >= since
    )
    return min(100, open_opps * 12 + recent_wins * 20 + min(30, (project.sales_score or 0) // 4))


def technical_score(project: Project, since: datetime) -> int:
    count = sum(
        1
        for m in project.missions
        if m.status == "DONE"
        and m.completed_at
        and m.completed_at >= since
        and m.type in {"DEVELOPMENT", "QA", "INFRASTRUCTURE"}
    )
    return min(100, count * 25 + min(40, (project.technology_score or 0) // 3))


def blocker_penalty(project: Project) -> int:
    penalty = 0
    if project.status == "BLOCKED":
        penalty += 25
    open_issues = [i for i in project.issues if i.status != "RESOLVED"]
    for issue in open_issues:
        if issue.severity == "CRITICAL":
            penalty += 18
        elif issue.severity == "HIGH":
            penalty += 8
    extra = max(0, len(open_issues) - 3)
    penalty += extra * 3
    return penalty


class MetricsService:
    @staticmethod
    def compute_momentum(project: Project) -> int:
        now = datetime.utcnow()
        two_weeks = now - timedelta(days=14)
        thirty = now - timedelta(days=30)
        raw = (
            0.30 * recency_score(project)
            + 0.25 * mission_pace_score(project, two_weeks)
            + 0.20 * commercial_score(project, thirty)
            + 0.15 * technical_score(project, two_weeks)
            + 0.10 * max(0, min(100, project.health or 0))
            - blocker_penalty(project)
        )
        return int(max(0, min(100, round(raw))))

    @staticmethod
    def refresh_project(project: Project) -> int:
        project.momentum = MetricsService.compute_momentum(project)
        return project.momentum

    @staticmethod
    def refresh_all() -> None:
        for project in Project.query.all():
            MetricsService.refresh_project(project)

    @staticmethod
    def metric_bars(project: Project) -> list[dict]:
        bars = []
        for key in METRIC_KEYS:
            value = int(getattr(project, key, 0) or 0)
            bars.append(
                {
                    "key": key,
                    "label": METRIC_LABELS[key],
                    "value": value,
                }
            )
        bars.append({"key": "momentum", "label": "Momentum", "value": project.momentum})
        bars.append({"key": "health", "label": "Salud", "value": project.health})
        return bars
