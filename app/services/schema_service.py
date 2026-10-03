"""Additive SQLite-safe schema patches. Never drop user tables."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from app.extensions import db

logger = logging.getLogger(__name__)

MISSION_COLUMNS = {
    "estimated_minutes": "INTEGER",
    "planned_date": "DATE",
    "goal_id": "INTEGER",
    "origin_capture_id": "INTEGER",
    "work_state": "VARCHAR(20) DEFAULT 'todo'",
    "next_action": "VARCHAR(255) DEFAULT ''",
    "done_criteria": "TEXT DEFAULT ''",
    "queue_position": "INTEGER DEFAULT 0",
    "wait_reason": "VARCHAR(255) DEFAULT ''",
    "wait_review_on": "DATE",
    "version": "INTEGER DEFAULT 1",
}

OPPORTUNITY_COLUMNS = {
    "currency": "VARCHAR(8) DEFAULT 'USD'",
    "product": "VARCHAR(160) DEFAULT ''",
    "converted_movement_id": "INTEGER",
}


def ensure_schema() -> None:
    db.create_all()
    insp = inspect(db.engine)
    tables = set(insp.get_table_names())
    if "missions" in tables:
        _add_missing("missions", MISSION_COLUMNS, insp)
    if "opportunities" in tables:
        _add_missing("opportunities", OPPORTUNITY_COLUMNS, insp)
    if "missions" in tables:
        _backfill_work_state()


def _add_missing(table: str, wanted: dict[str, str], insp) -> None:
    have = {c["name"] for c in insp.get_columns(table)}
    with db.engine.begin() as conn:
        for name, ddl in wanted.items():
            if name in have:
                continue
            conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}"))
            logger.info("Added column %s.%s", table, name)


def _backfill_work_state() -> None:
    with db.engine.begin() as conn:
        conn.execute(
            text(
                """
                UPDATE missions SET work_state = CASE status
                    WHEN 'IN_PROGRESS' THEN 'active'
                    WHEN 'DONE' THEN 'done'
                    WHEN 'CANCELLED' THEN 'cancelled'
                    ELSE 'todo'
                END
                WHERE work_state IS NULL OR work_state = ''
                   OR (work_state = 'todo' AND status IN ('IN_PROGRESS', 'DONE', 'CANCELLED'))
                """
            )
        )
