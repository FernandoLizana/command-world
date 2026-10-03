from __future__ import annotations

import json
from datetime import datetime

from app.extensions import db
from app.models.constants import DEFAULT_XP_REWARDS


class Empire(db.Model):
    """Singleton row that stores empire-wide resources."""

    __tablename__ = "empire"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), default="Mi mundo")
    money = db.Column(db.Integer, default=0, nullable=False)
    available_hours = db.Column(db.Float, default=8.0, nullable=False)
    level = db.Column(db.Integer, default=1, nullable=False)
    xp = db.Column(db.Integer, default=0, nullable=False)
    current_turn = db.Column(db.Integer, default=1, nullable=False)
    last_turn_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class GameSetting(db.Model):
    __tablename__ = "game_settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False)
    value = db.Column(db.Text, default="")
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    @staticmethod
    def get(key: str, default: str | None = None) -> str | None:
        row = GameSetting.query.filter_by(key=key).first()
        if not row:
            return default
        return row.value

    @staticmethod
    def set(key: str, value: str) -> None:
        row = GameSetting.query.filter_by(key=key).first()
        if row is None:
            row = GameSetting(key=key, value=value)
            db.session.add(row)
        else:
            row.value = value
        db.session.commit()

    @staticmethod
    def xp_rewards() -> dict[str, int]:
        raw = GameSetting.get("xp_rewards")
        if not raw:
            return dict(DEFAULT_XP_REWARDS)
        try:
            data = json.loads(raw)
            merged = dict(DEFAULT_XP_REWARDS)
            merged.update({k: int(v) for k, v in data.items()})
            return merged
        except (json.JSONDecodeError, TypeError, ValueError):
            return dict(DEFAULT_XP_REWARDS)


class TurnLog(db.Model):
    __tablename__ = "turn_logs"

    id = db.Column(db.Integer, primary_key=True)
    turn_number = db.Column(db.Integer, nullable=False, index=True)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    hours_available = db.Column(db.Float, default=0)
    hours_spent = db.Column(db.Float, default=0)
    xp_gained = db.Column(db.Integer, default=0)
    summary = db.Column(db.Text, default="")
    events_json = db.Column(db.Text, default="[]")
    recommendations_json = db.Column(db.Text, default="[]")


class CouncilDecision(db.Model):
    __tablename__ = "council_decisions"

    id = db.Column(db.Integer, primary_key=True)
    summary = db.Column(db.Text, nullable=False)
    payload_json = db.Column(db.Text, default="{}")
    decision = db.Column(db.String(20), default="pending")  # pending/accepted/modified/rejected
    user_notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    decided_at = db.Column(db.DateTime, nullable=True)


class Technology(db.Model):
    __tablename__ = "technologies"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    description = db.Column(db.Text, default="")
    category = db.Column(db.String(80), default="general")
    status = db.Column(db.String(20), default="LOCKED", nullable=False)
    progress = db.Column(db.Integer, default=0, nullable=False)
    parent_id = db.Column(db.Integer, db.ForeignKey("technologies.id"), nullable=True)
    requirements = db.Column(db.Text, default="")
    xp_reward = db.Column(db.Integer, default=25, nullable=False)
    position = db.Column(db.Integer, default=0, nullable=False)

    parent = db.relationship("Technology", remote_side="Technology.id", backref="children")
