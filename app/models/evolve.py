from __future__ import annotations

from datetime import date, datetime

from app.extensions import db


class Goal(db.Model):
    __tablename__ = "goals"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, default="")
    kind = db.Column(db.String(20), default="milestone", nullable=False)
    status = db.Column(db.String(20), default="active", nullable=False)
    is_primary = db.Column(db.Boolean, default=False, nullable=False)
    due_date = db.Column(db.Date, nullable=True)
    success_criteria = db.Column(db.Text, default="")
    unit = db.Column(db.String(40), default="")
    start_value = db.Column(db.Integer, default=0, nullable=False)
    target_value = db.Column(db.Integer, default=0, nullable=False)
    current_value = db.Column(db.Integer, default=0, nullable=False)
    direction = db.Column(db.String(10), default="up", nullable=False)
    source = db.Column(db.String(40), default="manual")
    evidence = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_demo = db.Column(db.Boolean, default=False, nullable=False)

    project = db.relationship("Project", backref="goals")

    def progress_pct(self) -> int | None:
        if self.kind != "numeric":
            if self.status == "done":
                return 100
            if not (self.success_criteria or "").strip():
                return None
            return 0
        span = abs((self.target_value or 0) - (self.start_value or 0))
        if span <= 0:
            return None
        if self.direction == "down":
            moved = (self.start_value or 0) - (self.current_value or 0)
        else:
            moved = (self.current_value or 0) - (self.start_value or 0)
        return max(0, min(100, int(100 * moved / span)))

    @property
    def progress_label(self) -> str:
        pct = self.progress_pct()
        return "Pendiente de definir" if pct is None else f"{pct}%"

    def to_dict(self) -> dict:
        pct = self.progress_pct()
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "kind": self.kind,
            "status": self.status,
            "is_primary": self.is_primary,
            "due_date": self.due_date.isoformat() if self.due_date else None,
            "progress": pct,
            "progress_label": self.progress_label,
            "unit": self.unit,
            "current_value": self.current_value,
            "target_value": self.target_value,
            "success_criteria": self.success_criteria,
        }


class MissionDependency(db.Model):
    __tablename__ = "mission_dependencies"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False, index=True)
    depends_on_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    mission = db.relationship("Mission", foreign_keys=[mission_id], backref="dependencies")
    depends_on = db.relationship("Mission", foreign_keys=[depends_on_id], backref="dependents")


class ExternalBlocker(db.Model):
    __tablename__ = "external_blockers"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    reason = db.Column(db.String(255), nullable=False)
    kind = db.Column(db.String(40), default="wait")
    status = db.Column(db.String(20), default="open", nullable=False)
    review_on = db.Column(db.Date, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)


class InboxCapture(db.Model):
    __tablename__ = "inbox_captures"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="open", nullable=False)
    converted_type = db.Column(db.String(20), default="")
    converted_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    processed_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status,
            "converted_type": self.converted_type,
            "converted_id": self.converted_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Note(db.Model):
    __tablename__ = "notes"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    title = db.Column(db.String(200), default="")
    body = db.Column(db.Text, default="")
    kind = db.Column(db.String(20), default="note")
    url = db.Column(db.String(500), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "body": self.body,
            "kind": self.kind,
            "url": self.url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class MoneyMovement(db.Model):
    """amount_cents is the minor unit of currency. Do not use float for totals."""

    __tablename__ = "money_movements"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunities.id"), nullable=True)
    parent_id = db.Column(db.Integer, db.ForeignKey("money_movements.id"), nullable=True)
    direction = db.Column(db.String(10), nullable=False)
    status = db.Column(db.String(20), default="pending", nullable=False)
    concept = db.Column(db.String(200), nullable=False)
    category = db.Column(db.String(80), default="general")
    amount_cents = db.Column(db.Integer, nullable=False)
    currency = db.Column(db.String(8), default="USD", nullable=False)
    occurred_on = db.Column(db.Date, default=date.today, nullable=False)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    is_demo = db.Column(db.Boolean, default=False, nullable=False)

    parent = db.relationship("MoneyMovement", remote_side="MoneyMovement.id", backref="parts")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "direction": self.direction,
            "status": self.status,
            "concept": self.concept,
            "amount_cents": self.amount_cents,
            "currency": self.currency,
            "occurred_on": self.occurred_on.isoformat() if self.occurred_on else None,
        }


class DailyTurn(db.Model):
    __tablename__ = "daily_turns"

    id = db.Column(db.Integer, primary_key=True)
    local_date = db.Column(db.Date, nullable=False, unique=True, index=True)
    minutes_budget = db.Column(db.Integer, nullable=False)
    payload_json = db.Column(db.Text, default="[]")
    status = db.Column(db.String(20), default="draft", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WeeklyReview(db.Model):
    __tablename__ = "weekly_reviews"

    id = db.Column(db.Integer, primary_key=True)
    week_start = db.Column(db.Date, nullable=False, unique=True, index=True)
    body_json = db.Column(db.Text, default="{}")
    plan_next_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class TimeEntry(db.Model):
    __tablename__ = "time_entries"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    minutes = db.Column(db.Integer, nullable=False)
    local_date = db.Column(db.Date, nullable=False)
    note = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
