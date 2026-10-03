"""
Level progression is requirement-driven, not a hidden formula.

    0 Idea
    1 Campamento
    2 Aldea / prototipo
    3 Pueblo / MVP
    4 Ciudad / usuarios-clientes
    5 Capital / producto estable rentable

A project may advance when every LevelRequirement for from_level == current level
is marked completed. XP is awarded separately and does not auto-promote.
"""

from __future__ import annotations

from app.extensions import db
from app.models import LevelRequirement, Project
from app.models.constants import LEVEL_NAMES
from app.services.event_service import EventService
from app.services.xp_service import XPService


def can_level_up(project: Project) -> bool:
    reqs = [r for r in project.level_requirements if r.from_level == project.level]
    if not reqs:
        return False
    return all(r.completed for r in reqs)


def pending_requirements(project: Project) -> list[LevelRequirement]:
    return [r for r in project.level_requirements if r.from_level == project.level]


def try_level_up(project: Project) -> bool:
    if project.level >= 5 or not can_level_up(project):
        return False
    project.level += 1
    XPService.award(
        "level_up",
        project=project,
        description=f"{project.name} evoluciona a {LEVEL_NAMES.get(project.level, project.level)}",
    )
    EventService.emit(
        f"{project.name} subió a nivel {project.level}",
        description=LEVEL_NAMES.get(project.level, ""),
        kind="success",
        icon="fa-trophy",
        project=project,
        commit=False,
    )
    db.session.commit()
    return True
