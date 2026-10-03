"""RPG/RTS persistence. Projections of work, not parallel task tables."""

from __future__ import annotations

import json
from datetime import date, datetime

from app.extensions import db


class RewardLedger(db.Model):
    __tablename__ = "reward_ledger"
    __table_args__ = (db.UniqueConstraint("idempotency_key", name="uq_reward_key"),)

    id = db.Column(db.Integer, primary_key=True)
    idempotency_key = db.Column(db.String(180), nullable=False)
    kind = db.Column(db.String(20), default="xp", nullable=False)
    amount = db.Column(db.Integer, default=0, nullable=False)
    source = db.Column(db.String(80), default="")
    entity_type = db.Column(db.String(40), default="")
    entity_id = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "key": self.idempotency_key,
            "kind": self.kind,
            "amount": self.amount,
            "source": self.source,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class JournalEntry(db.Model):
    __tablename__ = "journal_entries"

    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default="open", nullable=False)
    proposal_json = db.Column(db.Text, default="{}")
    applied_json = db.Column(db.Text, default="{}")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "text": self.text,
            "status": self.status,
            "proposal": json.loads(self.proposal_json or "{}"),
            "applied": json.loads(self.applied_json or "{}"),
            "project_id": self.project_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class RestPeriod(db.Model):
    __tablename__ = "rest_periods"

    id = db.Column(db.Integer, primary_key=True)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date, nullable=False)
    note = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "starts_on": self.starts_on.isoformat(),
            "ends_on": self.ends_on.isoformat(),
            "note": self.note or "",
        }


class WorkSession(db.Model):
    __tablename__ = "work_sessions"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=True, index=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    ended_at = db.Column(db.DateTime, nullable=True)
    minutes = db.Column(db.Integer, default=0, nullable=False)
    summary = db.Column(db.Text, default="")
    leftover = db.Column(db.Text, default="")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "project_id": self.project_id,
            "status": self.status,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "minutes": self.minutes,
            "summary": self.summary or "",
            "leftover": self.leftover or "",
        }


class FogQuestion(db.Model):
    __tablename__ = "fog_questions"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True, index=True)
    question = db.Column(db.String(255), nullable=False)
    action = db.Column(db.String(255), default="")
    status = db.Column(db.String(20), default="open", nullable=False)
    answer = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    resolved_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "question": self.question,
            "action": self.action or "",
            "status": self.status,
            "answer": self.answer or "",
        }


class Decree(db.Model):
    __tablename__ = "decrees"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    reason = db.Column(db.Text, default="")
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    status = db.Column(db.String(20), default="active", nullable=False)
    review_on = db.Column(db.Date, nullable=True)
    applied_json = db.Column(db.Text, default="{}")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "reason": self.reason or "",
            "project_id": self.project_id,
            "status": self.status,
            "review_on": self.review_on.isoformat() if self.review_on else None,
            "applied": json.loads(self.applied_json or "{}"),
        }


class SkillPractice(db.Model):
    __tablename__ = "skill_practice"

    id = db.Column(db.Integer, primary_key=True)
    area = db.Column(db.String(40), nullable=False, index=True)
    minutes = db.Column(db.Integer, default=0, nullable=False)
    note = db.Column(db.String(255), default="")
    source_key = db.Column(db.String(160), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class AchievementGrant(db.Model):
    __tablename__ = "achievement_grants"
    __table_args__ = (db.UniqueConstraint("code", name="uq_achievement_code"),)

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    reason = db.Column(db.String(255), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "code": self.code,
            "title": self.title,
            "reason": self.reason or "",
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class ProjectMember(db.Model):
    __tablename__ = "project_members"
    __table_args__ = (db.UniqueConstraint("project_id", "user_id", name="uq_project_member"),)

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False, index=True)
    role = db.Column(db.String(20), default="collaborator", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Scenario(db.Model):
    __tablename__ = "scenarios"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(160), nullable=False)
    patch_json = db.Column(db.Text, default="{}")
    result_json = db.Column(db.Text, default="{}")
    status = db.Column(db.String(20), default="draft", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "patch": json.loads(self.patch_json or "{}"),
            "result": json.loads(self.result_json or "{}"),
            "status": self.status,
        }


class RecurringItem(db.Model):
    __tablename__ = "recurring_items"
    __table_args__ = (db.UniqueConstraint("kind", "anchor_id", "period_key", name="uq_recurring_period"),)

    id = db.Column(db.Integer, primary_key=True)
    kind = db.Column(db.String(30), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    cadence = db.Column(db.String(20), default="weekly")
    anchor_id = db.Column(db.Integer, nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    period_key = db.Column(db.String(40), nullable=False)
    status = db.Column(db.String(20), default="open", nullable=False)
    due_on = db.Column(db.Date, nullable=True)
    result = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "kind": self.kind,
            "title": self.title,
            "cadence": self.cadence,
            "period_key": self.period_key,
            "status": self.status,
            "due_on": self.due_on.isoformat() if self.due_on else None,
            "result": self.result or "",
        }


class ProductionRecord(db.Model):
    __tablename__ = "production_records"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=True)
    goal_id = db.Column(db.Integer, db.ForeignKey("goals.id"), nullable=True)
    quantity = db.Column(db.Integer, default=0, nullable=False)
    unit = db.Column(db.String(40), default="")
    note = db.Column(db.String(255), default="")
    source_key = db.Column(db.String(160), unique=True, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "goal_id": self.goal_id,
            "quantity": self.quantity,
            "unit": self.unit or "",
            "note": self.note or "",
        }


class ContactCard(db.Model):
    __tablename__ = "contact_cards"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(160), nullable=False)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    opportunity_id = db.Column(db.Integer, db.ForeignKey("opportunities.id"), nullable=True)
    role = db.Column(db.String(80), default="")
    last_touch = db.Column(db.Date, nullable=True)
    notes = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "project_id": self.project_id,
            "opportunity_id": self.opportunity_id,
            "role": self.role or "",
            "last_touch": self.last_touch.isoformat() if self.last_touch else None,
            "notes": self.notes or "",
        }


class ProjectLink(db.Model):
    __tablename__ = "project_links"

    id = db.Column(db.Integer, primary_key=True)
    from_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    to_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False)
    kind = db.Column(db.String(40), default="related")
    note = db.Column(db.String(255), default="")

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "from_id": self.from_id,
            "to_id": self.to_id,
            "kind": self.kind,
            "note": self.note or "",
        }


class Procedure(db.Model):
    __tablename__ = "procedures"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    steps_json = db.Column(db.Text, default="[]")
    resource_note_id = db.Column(db.Integer, db.ForeignKey("notes.id"), nullable=True)
    version = db.Column(db.Integer, default=1, nullable=False)
    origin = db.Column(db.String(120), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "steps": json.loads(self.steps_json or "[]"),
            "resource_note_id": self.resource_note_id,
            "version": self.version,
            "origin": self.origin or "",
        }


class BestiaryCase(db.Model):
    __tablename__ = "bestiary_cases"

    id = db.Column(db.Integer, primary_key=True)
    category = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    tried = db.Column(db.Text, default="")
    useful = db.Column(db.Text, default="")
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "title": self.title,
            "tried": self.tried or "",
            "useful": self.useful or "",
            "mission_id": self.mission_id,
        }


class CampaignChapter(db.Model):
    __tablename__ = "campaign_chapters"

    id = db.Column(db.Integer, primary_key=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=False, index=True)
    title = db.Column(db.String(200), nullable=False)
    body = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="open", nullable=False)
    predecessor_id = db.Column(db.Integer, db.ForeignKey("campaign_chapters.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "project_id": self.project_id,
            "title": self.title,
            "body": self.body or "",
            "status": self.status,
            "predecessor_id": self.predecessor_id,
        }


class EvidenceItem(db.Model):
    __tablename__ = "evidence_items"

    id = db.Column(db.Integer, primary_key=True)
    mission_id = db.Column(db.Integer, db.ForeignKey("missions.id"), nullable=True)
    project_id = db.Column(db.Integer, db.ForeignKey("projects.id"), nullable=True)
    kind = db.Column(db.String(20), default="note")
    title = db.Column(db.String(200), default="")
    body = db.Column(db.Text, default="")
    url = db.Column(db.String(500), default="")
    stored_name = db.Column(db.String(200), default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "mission_id": self.mission_id,
            "project_id": self.project_id,
            "kind": self.kind,
            "title": self.title or "",
            "body": self.body or "",
            "url": self.url or "",
            "stored_name": self.stored_name or "",
        }


class CosmeticClaim(db.Model):
    __tablename__ = "cosmetic_claims"
    __table_args__ = (db.UniqueConstraint("code", name="uq_cosmetic_code"),)

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(80), nullable=False)
    title = db.Column(db.String(160), nullable=False)
    status = db.Column(db.String(20), default="chosen", nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
