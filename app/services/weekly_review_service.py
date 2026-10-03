from __future__ import annotations

import json
from datetime import datetime, timedelta

from app.extensions import db
from app.models import ExternalBlocker, Goal, Mission, Opportunity, TimeEntry, WeeklyReview
from app.services.finance_service import FinanceService
from app.services.world_service import WorldService


class WeeklyReviewService:
    @staticmethod
    def draft() -> dict:
        start = WorldService.week_start_date()
        end = start + timedelta(days=7)
        start_dt = datetime.combine(start, datetime.min.time())
        end_dt = datetime.combine(end, datetime.min.time())
        done = [
            {"id": m.id, "title": m.title, "project_id": m.project_id}
            for m in Mission.query.filter(Mission.status == "DONE").all()
            if m.completed_at and start_dt <= m.completed_at < end_dt
        ]
        goals = [
            g.to_dict()
            for g in Goal.query.filter(Goal.status == "done").all()
            if g.updated_at and start_dt <= g.updated_at < end_dt
        ]
        logged = sum(
            t.minutes
            for t in TimeEntry.query.filter(TimeEntry.local_date >= start, TimeEntry.local_date < end).all()
        )
        stale = [
            {"id": o.id, "name": o.name, "project_id": o.project_id}
            for o in Opportunity.query.filter(Opportunity.status.notin_(["WON", "LOST"])).all()
            if not o.next_action_date or o.next_action_date < WorldService.today()
        ]
        blockers = [
            {"id": b.id, "reason": b.reason, "mission_id": b.mission_id}
            for b in ExternalBlocker.query.filter_by(status="open").all()
        ]
        existing = WeeklyReview.query.filter_by(week_start=start).first()
        saved = json.loads(existing.body_json) if existing and existing.body_json else {}
        return {
            "week_start": start.isoformat(),
            "week_end": end.isoformat(),
            "missions_done": done,
            "goals_done": goals,
            "planned_minutes": WorldService.planned_minutes_this_week(),
            "logged_minutes": logged,
            "capacity": WorldService.weekly_capacity_minutes(),
            "money": FinanceService.totals(),
            "blockers": blockers,
            "stale_opportunities": stale,
            "notes": saved.get("notes") or {},
            "saved_id": existing.id if existing else None,
        }

    @staticmethod
    def save(notes: dict, plan_next: dict | None = None) -> dict:
        start = WorldService.week_start_date()
        draft = WeeklyReviewService.draft()
        body = {**draft, "notes": notes}
        row = WeeklyReview.query.filter_by(week_start=start).first()
        if row is None:
            row = WeeklyReview(week_start=start)
            db.session.add(row)
        row.body_json = json.dumps(body, ensure_ascii=False, default=str)
        row.plan_next_json = json.dumps(plan_next or {}, ensure_ascii=False)
        db.session.commit()
        return WeeklyReviewService.draft()
