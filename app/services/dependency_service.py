from __future__ import annotations

from app.extensions import db
from app.models import Mission, MissionDependency


class DependencyError(ValueError):
    pass


class DependencyService:
    @staticmethod
    def add(mission_id: int, depends_on_id: int) -> MissionDependency:
        if mission_id == depends_on_id:
            raise DependencyError("Una misión no puede depender de sí misma.")
        if DependencyService._creates_cycle(mission_id, depends_on_id):
            raise DependencyError("Esa dependencia formaría un ciclo. Elige otra misión.")
        existing = MissionDependency.query.filter_by(
            mission_id=mission_id, depends_on_id=depends_on_id
        ).first()
        if existing:
            return existing
        row = MissionDependency(mission_id=mission_id, depends_on_id=depends_on_id)
        db.session.add(row)
        db.session.commit()
        return row

    @staticmethod
    def _creates_cycle(mission_id: int, depends_on_id: int) -> bool:
        """True if adding mission depends_on would loop back to mission."""
        seen: set[int] = set()
        stack = [depends_on_id]
        while stack:
            current = stack.pop()
            if current == mission_id:
                return True
            if current in seen:
                continue
            seen.add(current)
            for dep in MissionDependency.query.filter_by(mission_id=current).all():
                stack.append(dep.depends_on_id)
        return False

    @staticmethod
    def blockers_of(mission: Mission) -> list[dict]:
        out = []
        for dep in mission.dependencies:
            other = dep.depends_on
            out.append(
                {
                    "id": other.id if other else None,
                    "title": other.title if other else "?",
                    "done": other.status == "DONE" if other else False,
                    "archived": other.status in {"CANCELLED"} if other else False,
                }
            )
        return out
