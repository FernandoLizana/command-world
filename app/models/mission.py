from __future__ import annotations

from datetime import datetime

from app.extensions import db
from app.models.constants import MISSION_TYPE_META


class Mission(db.Model):
    __tablename__ = "missions"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    type = db.Column(db.String(40), default="DEVELOPMENT", nullable=False)
    priority = db.Column(db.Integer, default=3, nullable=False)
    status = db.Column(db.String(20), default="OPEN", nullable=False, index=True)
    xp_reward = db.Column(db.Integer, default=5, nullable=False)
    estimated_hours = db.Column(db.Float, default=1.0, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    estimated_minutes = db.Column(db.Integer, nullable=True)
    planned_date = db.Column(db.Date, nullable=True)
    goal_id = db.Column(db.Integer, db.ForeignKey("goals.id"), nullable=True, index=True)
    origin_capture_id = db.Column(db.Integer, nullable=True)
    work_state = db.Column(db.String(20), default="todo", nullable=False, index=True)
    next_action = db.Column(db.String(255), default="")
    done_criteria = db.Column(db.Text, default="")
    queue_position = db.Column(db.Integer, default=0, nullable=False)
    wait_reason = db.Column(db.String(255), default="")
    wait_review_on = db.Column(db.Date, nullable=True)
    version = db.Column(db.Integer, default=1, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    completed_at = db.Column(db.DateTime, nullable=True)
    is_demo = db.Column(db.Boolean, default=False, nullable=False)

    project = db.relationship("Project", back_populates="missions")
    goal = db.relationship("Goal", foreign_keys=[goal_id], backref="missions")
    objectives = db.relationship(
        "MissionObjective",
        back_populates="mission",
        cascade="all, delete-orphan",
        order_by="MissionObjective.position",
    )

    @property
    def type_meta(self) -> dict:
        return MISSION_TYPE_META.get(self.type, MISSION_TYPE_META["DEVELOPMENT"])

    @property
    def progress(self) -> int:
        if not self.objectives:
            return 100 if self.status == "DONE" else 0
        done = sum(1 for o in self.objectives if o.completed)
        return int(100 * done / len(self.objectives))

    def is_blocked(self) -> bool:
        from app.models.evolve import ExternalBlocker, MissionDependency

        if ExternalBlocker.query.filter_by(mission_id=self.id, status="open").first():
            return True
        for dep in self.dependencies:
            other = dep.depends_on
            if other is None or other.status not in {"DONE"}:
                return True
        return False

    def _legacy_work_state(self) -> str:
        return {
            "OPEN": "todo",
            "IN_PROGRESS": "active",
            "DONE": "done",
            "CANCELLED": "cancelled",
        }.get(self.status, "todo")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "project_name": self.project.name if self.project else "",
            "project_slug": self.project.slug if self.project else "",
            "title": self.title,
            "description": self.description,
            "type": self.type,
            "priority": self.priority,
            "status": self.status,
            "xp_reward": self.xp_reward,
            "estimated_hours": self.estimated_hours,
            "progress": self.progress,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "estimated_minutes": self.estimated_minutes,
            "planned_date": self.planned_date.isoformat() if self.planned_date else None,
            "goal_id": self.goal_id,
            "blocked": self.is_blocked(),
            "work_state": self.work_state or self._legacy_work_state(),
            "next_action": self.next_action or "",
            "done_criteria": self.done_criteria or "",
            "queue_position": self.queue_position or 0,
            "wait_reason": self.wait_reason or "",
            "wait_review_on": self.wait_review_on.isoformat() if self.wait_review_on else None,
            "version": self.version or 1,
            "specialty": self.type,
            "objectives": [
                {"id": o.id, "description": o.description, "completed": o.completed}
                for o in self.objectives
            ],
        }


class MissionObjective(db.Model):
    __tablename__ = "mission_objectives"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False)
    description = db.Column(db.String(255), nullable=False)
    completed = db.Column(db.Boolean, default=False, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)

    mission = db.relationship("Mission", back_populates="objectives")
