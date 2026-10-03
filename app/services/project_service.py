from __future__ import annotations

import logging
import re
from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Project
from app.models.constants import PROJECT_STATUSES
from app.services.metrics_service import MetricsService
from app.services.xp_service import XPService

logger = logging.getLogger(__name__)


def slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[áàäâ]", "a", value)
    value = re.sub(r"[éèëê]", "e", value)
    value = re.sub(r"[íìïî]", "i", value)
    value = re.sub(r"[óòöô]", "o", value)
    value = re.sub(r"[úùüû]", "u", value)
    value = re.sub(r"[^a-z0-9]+", "-", value)
    return value.strip("-") or "proyecto"


class ProjectService:
    @staticmethod
    def unique_slug(name: str, exclude_id: int | None = None) -> str:
        base = slugify(name)
        slug = base
        n = 2
        while True:
            q = Project.query.filter_by(slug=slug)
            if exclude_id is not None:
                q = q.filter(Project.id != exclude_id)
            if q.first() is None:
                return slug
            slug = f"{base}-{n}"
            n += 1

    @staticmethod
    def create(data: dict) -> Project:
        project = Project(
            name=data["name"].strip(),
            slug=ProjectService.unique_slug(data.get("slug") or data["name"]),
            description=data.get("description") or "",
            category=data.get("category") or "general",
            status=data.get("status") if data.get("status") in PROJECT_STATUSES else "ACTIVE",
            level=int(data.get("level") or 0),
            health=int(data.get("health") or 70),
            product_score=int(data.get("product_score") or 40),
            technology_score=int(data.get("technology_score") or 40),
            sales_score=int(data.get("sales_score") or 20),
            marketing_score=int(data.get("marketing_score") or 20),
            finance_score=int(data.get("finance_score") or 20),
            stability_score=int(data.get("stability_score") or 50),
            priority=int(data.get("priority") or 3),
            revenue=int(data.get("revenue") or 0),
            monthly_revenue=int(data.get("monthly_revenue") or 0),
            potential_revenue=int(data.get("potential_revenue") or 0),
            hours_invested=int(data.get("hours_invested") or 0),
            map_x=int(data.get("map_x") or 480),
            map_y=int(data.get("map_y") or 320),
            icon=data.get("icon") or "fa-chess-rook",
            building_type=data.get("building_type") or "city",
            color_theme=data.get("color_theme") or "#c9a227",
            last_activity=datetime.utcnow(),
        )
        db.session.add(project)
        db.session.flush()
        MetricsService.refresh_project(project)
        XPService.award("create_task", project=project, description=f"Proyecto fundado: {project.name}")
        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            raise
        logger.info("Created project %s", project.slug)
        return project

    @staticmethod
    def update(project: Project, data: dict) -> Project:
        simple = (
            "name",
            "description",
            "category",
            "icon",
            "building_type",
            "color_theme",
        )
        ints = (
            "level",
            "health",
            "priority",
            "revenue",
            "monthly_revenue",
            "potential_revenue",
            "hours_invested",
            "product_score",
            "technology_score",
            "sales_score",
            "marketing_score",
            "finance_score",
            "stability_score",
            "map_x",
            "map_y",
            "xp",
        )
        for key in simple:
            if key in data and data[key] is not None:
                setattr(project, key, data[key])
        for key in ints:
            if key in data and data[key] not in (None, ""):
                setattr(project, key, int(data[key]))
        if "status" in data and data["status"] in PROJECT_STATUSES:
            project.status = data["status"]
        if "name" in data and data["name"]:
            project.slug = ProjectService.unique_slug(data.get("slug") or data["name"], project.id)
        project.updated_at = datetime.utcnow()
        MetricsService.refresh_project(project)
        db.session.commit()
        return project

    @staticmethod
    def move(project: Project, x: int, y: int) -> Project:
        project.map_x = max(40, min(int(x), 2400))
        project.map_y = max(40, min(int(y), 1600))
        project.updated_at = datetime.utcnow()
        db.session.commit()
        return project

    @staticmethod
    def archive_candidates() -> list[Project]:
        return (
            Project.query.filter(
                or_(
                    Project.status.in_(["PAUSED", "BLOCKED", "ARCHIVED"]),
                    Project.momentum < 20,
                )
            )
            .order_by(Project.momentum.asc())
            .all()
        )
