from __future__ import annotations

import json
import logging
import shutil
import sqlite3
import tempfile
from datetime import datetime
from pathlib import Path

from flask import current_app

from app.extensions import db
from app.models import (
    Goal,
    InboxCapture,
    Issue,
    Mission,
    MissionObjective,
    MoneyMovement,
    Note,
    Opportunity,
    Project,
)
from app.models.empire import GameSetting
from app.models.rpg import JournalEntry, RewardLedger
from app.services.world_service import WorldService

logger = logging.getLogger(__name__)
EXPORT_VERSION = 1


class BackupService:
    @staticmethod
    def data_dir() -> Path:
        root = Path(current_app.instance_path)
        (root / "backups").mkdir(parents=True, exist_ok=True)
        (root / "files").mkdir(parents=True, exist_ok=True)
        return root

    @staticmethod
    def sqlite_path() -> Path:
        uri = current_app.config["SQLALCHEMY_DATABASE_URI"]
        if uri.startswith("sqlite:///"):
            return Path(uri.replace("sqlite:///", "", 1))
        raise RuntimeError("Backup SQLite only in this version")

    @staticmethod
    def snapshot_sqlite() -> Path:
        src = BackupService.sqlite_path()
        dest = BackupService.data_dir() / "backups" / f"empire-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.db"
        dest.parent.mkdir(parents=True, exist_ok=True)
        src_conn = sqlite3.connect(src)
        try:
            dest_conn = sqlite3.connect(dest)
            try:
                src_conn.backup(dest_conn)
            finally:
                dest_conn.close()
        finally:
            src_conn.close()
        stamp = BackupService.data_dir() / "backups" / "last-ok.txt"
        stamp.write_text(f"{datetime.utcnow().isoformat()}Z\n{dest}", encoding="utf-8")
        return dest

    @staticmethod
    def export_json() -> dict:
        prefs = WorldService.prefs()
        return {
            "version": EXPORT_VERSION,
            "exported_at": datetime.utcnow().isoformat() + "Z",
            "world": prefs,
            "projects": [
                {
                    **p.to_map_dict(),
                    "description": p.description,
                    "is_demo": p.is_demo,
                }
                for p in Project.query.all()
            ],
            "missions": [m.to_dict() for m in Mission.query.all()],
            "goals": [g.to_dict() for g in Goal.query.all()],
            "opportunities": [
                {
                    "id": o.id,
                    "project_id": o.project_id,
                    "name": o.name,
                    "status": o.status,
                    "estimated_value": o.estimated_value,
                    "next_action": o.next_action,
                    "next_action_date": o.next_action_date.isoformat() if o.next_action_date else None,
                    "is_demo": o.is_demo,
                }
                for o in Opportunity.query.all()
            ],
            "money": [m.to_dict() for m in MoneyMovement.query.all()],
            "captures": [c.to_dict() for c in InboxCapture.query.all()],
            "notes": [n.to_dict() for n in Note.query.all()],
            "journal": [j.to_dict() for j in JournalEntry.query.all()],
            "rewards": [r.to_dict() for r in RewardLedger.query.all()],
            "issues": [
                {"id": i.id, "project_id": i.project_id, "title": i.title, "status": i.status, "severity": i.severity}
                for i in Issue.query.all()
            ],
        }

    @staticmethod
    def write_export() -> Path:
        payload = BackupService.export_json()
        path = BackupService.data_dir() / "backups" / f"export-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.json"
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    @staticmethod
    def last_ok() -> str | None:
        stamp = BackupService.data_dir() / "backups" / "last-ok.txt"
        if stamp.exists():
            return stamp.read_text(encoding="utf-8").splitlines()[0]
        return None

    @staticmethod
    def _csv_cell(value) -> str:
        text = "" if value is None else str(value)
        if text[:1] in {"=", "+", "-", "@"}:
            text = "'" + text
        return text

    @staticmethod
    def write_csv(kind: str) -> Path:
        import csv

        kind = kind if kind in {"projects", "missions", "opportunities", "money"} else "missions"
        path = BackupService.data_dir() / "backups" / f"{kind}-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}.csv"
        path.parent.mkdir(parents=True, exist_ok=True)
        rows: list[list]
        if kind == "projects":
            header = ["id", "name", "status", "priority"]
            rows = [[p.id, p.name, p.status, p.priority] for p in Project.query.all()]
        elif kind == "opportunities":
            header = ["id", "project_id", "name", "status", "estimated_value", "currency"]
            rows = [
                [o.id, o.project_id, o.name, o.status, o.estimated_value, getattr(o, "currency", "")]
                for o in Opportunity.query.all()
            ]
        elif kind == "money":
            header = ["id", "project_id", "direction", "status", "concept", "amount_cents", "currency"]
            rows = [
                [m.id, m.project_id, m.direction, m.status, m.concept, m.amount_cents, m.currency]
                for m in MoneyMovement.query.all()
            ]
        else:
            header = ["id", "project_id", "title", "status", "priority", "estimated_minutes"]
            rows = [
                [m.id, m.project_id, m.title, m.status, m.priority, m.estimated_minutes]
                for m in Mission.query.all()
            ]
        with path.open("w", encoding="utf-8", newline="") as fh:
            writer = csv.writer(fh)
            writer.writerow(header)
            for row in rows:
                writer.writerow([BackupService._csv_cell(c) for c in row])
        return path

    @staticmethod
    def restore_upload(upload) -> dict:
        name = (upload.filename or "restore.bin").lower()
        tmp = BackupService.data_dir() / "backups" / f"incoming-{datetime.utcnow().strftime('%Y%m%d-%H%M%S')}"
        tmp.parent.mkdir(parents=True, exist_ok=True)
        upload.save(tmp)
        if name.endswith(".json"):
            payload = json.loads(tmp.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or "version" not in payload:
                tmp.unlink(missing_ok=True)
                raise ValueError("El JSON no es una exportación de DR Command.")
            preview = {
                "kind": "json",
                "projects": len(payload.get("projects") or []),
                "missions": len(payload.get("missions") or []),
                "apply": False,
                "note": "Vista previa. La importación completa se aplica desde una copia SQLite para no mezclar IDs a medias.",
            }
            return preview
        if not name.endswith(".db"):
            tmp.unlink(missing_ok=True)
            raise ValueError("Usa un archivo .db de copia o un .json de exportación.")
        try:
            probe = sqlite3.connect(tmp)
            probe.execute("SELECT name FROM sqlite_master LIMIT 1").fetchone()
            probe.close()
        except sqlite3.Error as exc:
            tmp.unlink(missing_ok=True)
            raise ValueError("La copia está dañada y no se aplicó.") from exc
        safety = BackupService.snapshot_sqlite()
        dest = BackupService.sqlite_path()
        db.session.remove()
        db.engine.dispose()
        shutil.copyfile(tmp, dest)
        return {"kind": "sqlite", "restored": tmp.name, "previous": safety.name}
