"""Optional project sharing. Individual mode stays implicit owner."""

from __future__ import annotations

from flask_login import current_user

from app.extensions import db
from app.models import Project, User
from app.models.rpg import ProjectMember
from app.services.world_service import WorldService


class CoopError(ValueError):
    pass


class CoopService:
    @staticmethod
    def enabled() -> bool:
        return bool(WorldService.prefs().get("guild_enabled"))

    @staticmethod
    def members(project: Project) -> list[dict]:
        rows = ProjectMember.query.filter_by(project_id=project.id).all()
        out = []
        for row in rows:
            user = db.session.get(User, row.user_id)
            out.append(
                {
                    "user_id": row.user_id,
                    "username": user.username if user else "",
                    "role": row.role,
                }
            )
        if not out:
            owner = current_user if getattr(current_user, "is_authenticated", False) else None
            if owner:
                out.append({"user_id": owner.id, "username": owner.username, "role": "owner", "implicit": True})
        return out

    @staticmethod
    def role_for(project: Project, user: User | None = None) -> str | None:
        user = user or (current_user if getattr(current_user, "is_authenticated", False) else None)
        if user is None:
            return None
        rows = ProjectMember.query.filter_by(project_id=project.id).all()
        if not rows:
            return "owner"
        match = next((r for r in rows if r.user_id == user.id), None)
        return match.role if match else None

    @staticmethod
    def can_read(project: Project, user: User | None = None) -> bool:
        return CoopService.role_for(project, user) in {"owner", "collaborator", "reader"}

    @staticmethod
    def can_write(project: Project, user: User | None = None) -> bool:
        return CoopService.role_for(project, user) in {"owner", "collaborator"}

    @staticmethod
    def require_write(project: Project, user: User | None = None) -> None:
        if not CoopService.can_write(project, user):
            raise CoopError("No tienes permiso de escritura en este proyecto.")

    @staticmethod
    def share(project: Project, username: str, role: str = "collaborator") -> ProjectMember:
        if role not in {"owner", "collaborator", "reader"}:
            raise CoopError("Rol no válido.")
        CoopService.require_write(project)
        user = User.query.filter_by(username=username.strip()).first()
        if not user:
            raise CoopError("Usuario no encontrado. La cooperación usa cuentas reales, no personajes.")
        actor = CoopService.role_for(project)
        if role == "owner" and actor != "owner":
            raise CoopError("Solo el propietario puede otorgar ese rol.")
        existing = ProjectMember.query.filter_by(project_id=project.id, user_id=user.id).first()
        if existing:
            if existing.role == "owner" and actor != "owner":
                raise CoopError("No puedes cambiar el rol del propietario.")
            existing.role = role
            db.session.commit()
            return existing
        if not ProjectMember.query.filter_by(project_id=project.id).first():
            owner = current_user
            if owner and owner.id != user.id:
                db.session.add(ProjectMember(project_id=project.id, user_id=owner.id, role="owner"))
        row = ProjectMember(project_id=project.id, user_id=user.id, role=role)
        db.session.add(row)
        db.session.commit()
        return row
