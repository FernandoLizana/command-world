from __future__ import annotations

from datetime import datetime

from app.extensions import db


class GameEvent(db.Model):
    __tablename__ = "game_events"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    kind = db.Column(db.String(40), default="info", nullable=False)
    icon = db.Column(db.String(40), default="fa-flag")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)
    is_demo = db.Column(db.Boolean, default=False, nullable=False)

    project = db.relationship("Project", back_populates="events")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else None,
            "title": self.title,
            "description": self.description,
            "kind": self.kind,
            "icon": self.icon,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ActivityLog(db.Model):
    __tablename__ = "activity_logs"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    action_type = db.Column(db.String(60), nullable=False, index=True)
    description = db.Column(db.String(255), default="")
    xp = db.Column(db.Integer, default=0, nullable=False)
    metadata_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False, index=True)

    project = db.relationship("Project", back_populates="activities")


class Opportunity(db.Model):
    __tablename__ = "opportunities"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    name = db.Column(db.String(200), nullable=False)
    company = db.Column(db.String(160), default="")
    contact_name = db.Column(db.String(160), default="")
    estimated_value = db.Column(db.Integer, default=0, nullable=False)
    probability = db.Column(db.Integer, default=20, nullable=False)
    status = db.Column(db.String(20), default="LEAD", nullable=False, index=True)
    source = db.Column(db.String(80), default="")
    next_action = db.Column(db.String(255), default="")
    next_action_date = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, default="")
    currency = db.Column(db.String(8), default="USD")
    product = db.Column(db.String(160), default="")
    converted_movement_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_demo = db.Column(db.Boolean, default=False, nullable=False)

    project = db.relationship("Project", back_populates="opportunities")

    @property
    def weighted_value(self) -> int:
        return int(self.estimated_value * (self.probability / 100))


class Issue(db.Model):
    __tablename__ = "issues"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    severity = db.Column(db.String(20), default="MEDIUM", nullable=False)
    status = db.Column(db.String(20), default="OPEN", nullable=False, index=True)
    type = db.Column(db.String(40), default="general")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)
    is_demo = db.Column(db.Boolean, default=False, nullable=False)

    project = db.relationship("Project", back_populates="issues")
