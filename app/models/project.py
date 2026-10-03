from __future__ import annotations

from datetime import datetime

from app.extensions import db
from app.models.constants import LEVEL_NAMES, STATUS_META


class Project(db.Model):
    __tablename__ = "projects"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    slug = db.Column(db.String(180), unique=True, nullable=False, index=True)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(80), default="general")
    status = db.Column(db.String(20), default="ACTIVE", nullable=False, index=True)

    level = db.Column(db.Integer, default=0, nullable=False)
    xp = db.Column(db.Integer, default=0, nullable=False)
    health = db.Column(db.Integer, default=70, nullable=False)
    momentum = db.Column(db.Integer, default=50, nullable=False)

    product_score = db.Column(db.Integer, default=40, nullable=False)
    technology_score = db.Column(db.Integer, default=40, nullable=False)
    sales_score = db.Column(db.Integer, default=20, nullable=False)
    marketing_score = db.Column(db.Integer, default=20, nullable=False)
    finance_score = db.Column(db.Integer, default=20, nullable=False)
    stability_score = db.Column(db.Integer, default=50, nullable=False)

    priority = db.Column(db.Integer, default=3, nullable=False)
    revenue = db.Column(db.Integer, default=0, nullable=False)
    monthly_revenue = db.Column(db.Integer, default=0, nullable=False)
    potential_revenue = db.Column(db.Integer, default=0, nullable=False)
    hours_invested = db.Column(db.Integer, default=0, nullable=False)

    last_activity = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    map_x = db.Column(db.Integer, default=400, nullable=False)
    map_y = db.Column(db.Integer, default=300, nullable=False)
    icon = db.Column(db.String(80), default="fa-chess-rook")
    building_type = db.Column(db.String(40), default="city")
    color_theme = db.Column(db.String(20), default="#c9a227")
    is_demo = db.Column(db.Boolean, default=False, nullable=False)

    missions = db.relationship("Mission", back_populates="project", cascade="all, delete-orphan")
    opportunities = db.relationship(
        "Opportunity", back_populates="project", cascade="all, delete-orphan"
    )
    issues = db.relationship("Issue", back_populates="project", cascade="all, delete-orphan")
    events = db.relationship("GameEvent", back_populates="project")
    activities = db.relationship("ActivityLog", back_populates="project")
    level_requirements = db.relationship(
        "LevelRequirement",
        back_populates="project",
        cascade="all, delete-orphan",
        order_by="LevelRequirement.position",
    )

    @property
    def level_name(self) -> str:
        return LEVEL_NAMES.get(self.level, f"Nivel {self.level}")

    @property
    def status_meta(self) -> dict:
        return STATUS_META.get(self.status, STATUS_META["ACTIVE"])

    @property
    def open_issues_count(self) -> int:
        return sum(1 for i in self.issues if i.status != "RESOLVED")

    @property
    def critical_alerts(self) -> int:
        return sum(
            1
            for i in self.issues
            if i.status != "RESOLVED" and i.severity in {"HIGH", "CRITICAL"}
        )

    @property
    def open_missions_count(self) -> int:
        return sum(1 for m in self.missions if m.status in {"OPEN", "IN_PROGRESS"})

    @property
    def open_opportunities_count(self) -> int:
        return sum(1 for o in self.opportunities if o.status not in {"WON", "LOST"})

    def metrics_dict(self) -> dict[str, int]:
        return {
            "product_score": self.product_score,
            "technology_score": self.technology_score,
            "sales_score": self.sales_score,
            "marketing_score": self.marketing_score,
            "finance_score": self.finance_score,
            "stability_score": self.stability_score,
            "momentum": self.momentum,
            "health": self.health,
        }

    def to_map_dict(self) -> dict:
        primary = next((g for g in getattr(self, "goals", []) if g.is_primary), None)
        goal_pct = primary.progress_pct() if primary else None
        if goal_pct is None:
            goal_label = "Pendiente de definir"
            visual_progress = int(
                max(
                    0,
                    min(
                        100,
                        (self.level or 0) * 12
                        + (self.health or 0) * 0.35
                        + (self.momentum or 0) * 0.25,
                    ),
                )
            )
        else:
            goal_label = f"{goal_pct}%"
            visual_progress = goal_pct
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "x": self.map_x,
            "y": self.map_y,
            "building": self.building_type,
            "level": self.level,
            "level_name": self.level_name,
            "health": self.health,
            "momentum": self.momentum,
            "status": self.status,
            "status_label": self.status_meta["label"],
            "color": self.color_theme,
            "icon": self.icon,
            "alerts": self.critical_alerts or self.open_issues_count,
            "missions": self.open_missions_count,
            "opportunities": self.open_opportunities_count,
            "revenue": self.monthly_revenue,
            "priority": self.priority,
            "critical": self.critical_alerts > 0,
            "description": (self.description or "").replace("[DEMO]", "").strip()[:220],
            "xp": self.xp,
            "is_demo": bool(self.is_demo),
            "goal_progress": goal_pct,
            "goal_label": goal_label,
            "blocked": any(m.is_blocked() for m in self.missions if m.status in {"OPEN", "IN_PROGRESS"}),
            "progress": visual_progress,
            "district": self.category or "general",
            "construction": self._construction(),
            "units": self._units(),
            "activity": {
                m.type: sum(1 for x in self.missions if x.type == m.type and x.status in {"OPEN", "IN_PROGRESS"})
                for m in self.missions
                if m.status in {"OPEN", "IN_PROGRESS"}
            },
        }

    def _construction(self) -> dict:
        from app.services.rpg_service import RpgService

        return RpgService.construction_phase(self)

    def _units(self) -> list[dict]:
        from app.services.rpg_service import RpgService

        return RpgService.units_for(self)

    def __repr__(self) -> str:
        return f"<Project {self.slug}>"


class LevelRequirement(db.Model):
    __tablename__ = "level_requirements"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    from_level = db.Column(db.Integer, default=0, nullable=False)
    to_level = db.Column(db.Integer, default=1, nullable=False)
    description = db.Column(db.String(255), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)

    project = db.relationship("Project", back_populates="level_requirements")
