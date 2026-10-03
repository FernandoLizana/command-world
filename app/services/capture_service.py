from __future__ import annotations

from datetime import datetime

from app.extensions import db
from app.models import InboxCapture, Mission, MissionObjective, Note, Opportunity, Project
from app.services.event_service import EventService
from app.services.xp_service import XPService


class CaptureService:
    @staticmethod
    def add(text: str) -> InboxCapture:
        text = (text or "").strip()
        if not text:
            raise ValueError("Escribe al menos una frase.")
        row = InboxCapture(text=text, status="open")
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def convert(capture: InboxCapture, kind: str, project_id: int | None) -> InboxCapture:
        if capture.status == "converted" and capture.converted_id:
            return capture
        kind = kind if kind in {"mission", "note", "opportunity", "later"} else "later"
        if kind == "later":
            capture.status = "archived"
            capture.processed_at = datetime.utcnow()
            db.session.commit()
            return capture
        if kind == "mission":
            if not project_id:
                raise ValueError("Elige un proyecto (edificio) para la misión.")
            mission = Mission(
                project_id=project_id,
                title=capture.text[:200],
                description=capture.text,
                status="OPEN",
                origin_capture_id=capture.id,
            )
            db.session.add(mission)
            db.session.flush()
            db.session.add(MissionObjective(mission_id=mission.id, description="Definir el siguiente paso concreto"))
            capture.converted_type = "mission"
            capture.converted_id = mission.id
            XPService.award("create_task", project=db.session.get(Project, project_id), description=mission.title)
        elif kind == "note":
            note = Note(project_id=project_id, title=capture.text[:80], body=capture.text, kind="note")
            db.session.add(note)
            db.session.flush()
            capture.converted_type = "note"
            capture.converted_id = note.id
        elif kind == "opportunity":
            if not project_id:
                raise ValueError("Elige un proyecto para la oportunidad.")
            opp = Opportunity(project_id=project_id, name=capture.text[:200], status="LEAD", notes=capture.text)
            db.session.add(opp)
            db.session.flush()
            capture.converted_type = "opportunity"
            capture.converted_id = opp.id
        capture.status = "converted"
        capture.processed_at = datetime.utcnow()
        EventService.emit("Captura procesada", description=capture.text[:120], kind="info", icon="fa-inbox")
        db.session.commit()
        return capture
