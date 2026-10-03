"""Idempotent ludic rewards. Independent from real money."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from app.extensions import db
from app.models import Empire, Mission, Project
from app.models.rpg import AchievementGrant, RewardLedger, SkillPractice
from app.services.event_service import EventService
from app.services.xp_service import XPService


class RewardService:
    @staticmethod
    def grant(
        key: str,
        *,
        kind: str = "xp",
        amount: int = 0,
        source: str = "",
        entity_type: str = "",
        entity_id: int | None = None,
        project: Project | None = None,
        description: str = "",
        commit: bool = False,
    ) -> dict:
        existing = RewardLedger.query.filter_by(idempotency_key=key).first()
        if existing:
            return {"granted": False, "duplicate": True, "amount": 0, "kind": existing.kind, "key": key}
        row = RewardLedger(
            idempotency_key=key[:180],
            kind=kind,
            amount=int(amount or 0),
            source=source[:80],
            entity_type=entity_type[:40],
            entity_id=entity_id,
        )
        try:
            with db.session.begin_nested():
                db.session.add(row)
                db.session.flush()
        except IntegrityError:
            found = RewardLedger.query.filter_by(idempotency_key=key).first()
            return {
                "granted": False,
                "duplicate": True,
                "amount": 0,
                "kind": found.kind if found else kind,
                "key": key,
            }
        xp = 0
        if kind == "xp" and amount:
            xp = XPService.award(
                source or "complete_task",
                project=project,
                extra_xp=int(amount),
                description=description or key,
            )
            empire = db.session.get(Empire, 1)
            if empire and xp:
                empire.xp = (empire.xp or 0) + xp
        if commit:
            db.session.commit()
        return {"granted": True, "duplicate": False, "amount": xp or amount, "kind": kind, "key": key}

    @staticmethod
    def grant_mission_complete(mission: Mission) -> dict:
        reward = RewardService.grant(
            f"mission:{mission.id}:complete",
            kind="xp",
            amount=int(mission.xp_reward or 5),
            source="complete_task",
            entity_type="mission",
            entity_id=mission.id,
            project=mission.project,
            description=f"Misión: {mission.title}",
        )
        RewardService.maybe_achievements()
        return reward

    @staticmethod
    def totals() -> dict:
        xp = knowledge = coins = 0
        for row in RewardLedger.query.all():
            if row.kind == "xp":
                xp += row.amount or 0
            elif row.kind == "knowledge":
                knowledge += row.amount or 0
            elif row.kind == "coins":
                coins += row.amount or 0
        return {
            "xp": xp,
            "knowledge": knowledge,
            "coins": coins,
            "disclaimer": "Recursos lúdicos. No son dinero, inventario ni una certificación.",
        }

    @staticmethod
    def practice(area: str, minutes: int, note: str = "", source_key: str | None = None) -> dict:
        if source_key:
            dup = SkillPractice.query.filter_by(source_key=source_key).first()
            if dup:
                return {"granted": False, "duplicate": True, "id": dup.id}
        row = SkillPractice(area=(area or "general")[:40], minutes=int(minutes or 0), note=(note or "")[:255], source_key=source_key)
        db.session.add(row)
        granted = RewardService.grant(
            source_key or f"practice:{area}:{row.id or 0}",
            kind="knowledge",
            amount=max(1, int(minutes or 0) // 20),
            source="study",
            entity_type="skill",
        )
        db.session.commit()
        return {"granted": True, "practice_id": row.id, "reward": granted}

    @staticmethod
    def maybe_achievements() -> list[dict]:
        from app.models import WeeklyReview

        created = []
        checks = [
            ("first_delivery", "Primera entrega", Mission.query.filter_by(status="DONE").first() is not None, "Hay una misión terminada."),
            ("first_review", "Primera revisión semanal", WeeklyReview.query.first() is not None, "Se guardó una revisión semanal."),
        ]
        from app.models import Note

        checks.append(
            (
                "project_documented",
                "Proyecto documentado",
                Note.query.first() is not None,
                "Hay al menos una nota o recurso.",
            )
        )
        for code, title, ok, reason in checks:
            if not ok:
                continue
            if AchievementGrant.query.filter_by(code=code).first():
                continue
            row = AchievementGrant(code=code, title=title, reason=reason)
            db.session.add(row)
            try:
                db.session.flush()
            except IntegrityError:
                db.session.rollback()
                continue
            EventService.emit(f"Logro: {title}", description=reason, kind="success", icon="fa-trophy", commit=False)
            created.append(row.to_dict())
        return created

    @staticmethod
    def ledger(limit: int = 40) -> list[dict]:
        rows = RewardLedger.query.order_by(RewardLedger.id.desc()).limit(limit).all()
        return [r.to_dict() for r in rows]
