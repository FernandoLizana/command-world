"""Board, journal, WIP and reward rules for G01–G60."""

from __future__ import annotations

import unittest

from sqlalchemy.pool import StaticPool

from config import Config


class TestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-not-for-production"
    WTF_CSRF_ENABLED = False
    DEMO_MODE = False
    OLLAMA_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }


class GamificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from app import create_app

        cls.app = create_app(TestConfig)
        cls.client = cls.app.test_client()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        cls.client.post("/login", data={"username": "admin", "password": "admin"}, follow_redirects=True)

    @classmethod
    def tearDownClass(cls) -> None:
        from app.extensions import db

        db.session.remove()
        db.engine.dispose()
        cls.ctx.pop()

    def _project(self, name: str = "Tienda Test"):
        from app.services.project_service import ProjectService

        return ProjectService.create({"name": name, "status": "ACTIVE"})

    def test_invalid_transition_and_waiting_reason(self):
        from app.extensions import db
        from app.models import Mission
        from app.services.board_service import BoardError, BoardService

        p = self._project("Estados Test")
        m = Mission(project_id=p.id, title="Foto catálogo", status="OPEN", work_state="todo")
        db.session.add(m)
        db.session.commit()
        with self.assertRaises(BoardError):
            BoardService.transition(m, "done")
        with self.assertRaises(BoardError):
            BoardService.transition(m, "waiting")
        BoardService.transition(m, "active")
        BoardService.transition(m, "waiting", wait_reason="Cliente no responde")
        self.assertEqual(BoardService.state_of(m), "waiting")
        self.assertEqual(m.status, "OPEN")

    def test_wip_limit_blocks_fourth_active(self):
        from app.extensions import db
        from app.models import Mission
        from app.services.board_service import BoardError, BoardService
        from app.services.world_service import WorldService

        WorldService.save({"wip_limit": 3})
        for old in Mission.query.filter(Mission.work_state.in_(["active", "review"])).all():
            old.work_state = "todo"
            old.status = "OPEN"
        db.session.commit()
        p = self._project("WIP Test")
        rows = []
        for i in range(4):
            m = Mission(project_id=p.id, title=f"Tarea WIP {i}", status="OPEN", work_state="todo")
            db.session.add(m)
            rows.append(m)
        db.session.commit()
        for m in rows[:3]:
            BoardService.transition(m, "active")
        with self.assertRaises(BoardError):
            BoardService.transition(rows[3], "active")
        self.assertEqual(BoardService.active_count(), 3)

    def test_complete_reward_is_idempotent(self):
        from app.extensions import db
        from app.models import Mission
        from app.models.rpg import RewardLedger
        from app.services.board_service import BoardService

        p = self._project("XP Test")
        m = Mission(project_id=p.id, title="Entregar pedido", status="OPEN", work_state="todo", xp_reward=9)
        db.session.add(m)
        db.session.commit()
        BoardService.transition(m, "active")
        BoardService.transition(m, "done")
        first = RewardLedger.query.filter_by(idempotency_key=f"mission:{m.id}:complete").count()
        BoardService.advance(m)
        BoardService.transition(m, "todo")
        BoardService.transition(m, "active")
        BoardService.transition(m, "done")
        self.assertEqual(RewardLedger.query.filter_by(idempotency_key=f"mission:{m.id}:complete").count(), first)
        self.assertEqual(first, 1)

    def test_journal_negation_and_future_pay(self):
        from app.models import MoneyMovement
        from app.services.journal_service import JournalService

        p = self._project("Bitácora Test")
        keep = JournalService.interpret("Todavía no terminé la página de contacto")
        types = [a["type"] for a in keep["actions"]]
        self.assertIn("keep_pending", types)
        self.assertNotIn("complete", types)
        pay = JournalService.interpret("Me pagarán 100 cuando entregue")
        self.assertEqual(pay["actions"][0]["type"], "expect_payment")
        entry = JournalService.capture("Me pagarán 100 cuando entregue", p.id)
        JournalService.apply(entry, ["a1"])
        pending = MoneyMovement.query.filter_by(status="pending", project_id=p.id).all()
        self.assertTrue(pending)
        self.assertFalse(any(m.status == "settled" and m.project_id == p.id and "pagarán" in (m.concept or "").lower() for m in MoneyMovement.query.all()))

    def test_blocked_queue_does_not_start(self):
        from app.extensions import db
        from app.models import Mission
        from app.services.board_service import BoardError, BoardService
        from app.services.dependency_service import DependencyService

        p = self._project("Cola Test")
        a = Mission(project_id=p.id, title="A", status="OPEN", work_state="todo")
        b = Mission(project_id=p.id, title="B", status="OPEN", work_state="todo")
        db.session.add_all([a, b])
        db.session.commit()
        DependencyService.add(b.id, a.id)
        with self.assertRaises(BoardError):
            BoardService.transition(b, "active")

    def test_session_stop_does_not_complete(self):
        from app.extensions import db
        from app.models import Mission
        from app.services.rpg_service import RpgService

        p = self._project("Sesión Test")
        m = Mission(project_id=p.id, title="Concentración", status="OPEN", work_state="todo")
        db.session.add(m)
        db.session.commit()
        session = RpgService.start_session(m.id, p.id)
        RpgService.stop_session(session.id, summary="Avance", minutes=20)
        db.session.refresh(m)
        self.assertNotEqual(m.status, "DONE")
        self.assertNotEqual(m.work_state, "done")

    def test_scenario_does_not_change_world(self):
        from app.extensions import db
        from app.models import Mission
        from app.services.rpg_service import RpgService
        from app.services.world_service import WorldService

        p = self._project("Sim Test")
        m = Mission(project_id=p.id, title="Inmutable", status="OPEN", work_state="todo", estimated_minutes=120)
        db.session.add(m)
        db.session.commit()
        WorldService.save({"weekly_minutes": 360})
        row = RpgService.simulate("Menos horas", 30)
        RpgService.discard_scenario(row.id)
        db.session.refresh(m)
        self.assertEqual(m.work_state, "todo")
        self.assertEqual(WorldService.prefs().get("weekly_minutes"), 360)

    def test_guild_third_user_denied(self):
        from app.extensions import db
        from app.models import User
        from app.services.coop_service import CoopService

        p = self._project("Gremio Test")
        other = User(username="colab1", email="colab1@example.test", display_name="Colab")
        other.set_password("secret")
        stranger = User(username="extra1", email="extra1@example.test")
        stranger.set_password("secret")
        db.session.add_all([other, stranger])
        db.session.commit()
        with self.client:
            self.assertEqual(self.client.get("/api/world").status_code, 200)
            CoopService.share(p, "colab1", "collaborator")
            self.assertTrue(CoopService.can_read(p, other))
            self.assertFalse(CoopService.can_read(p, stranger))
            self.assertFalse(CoopService.can_write(p, stranger))


if __name__ == "__main__":
    unittest.main()
