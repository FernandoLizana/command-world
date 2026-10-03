"""Domain tests for the world evolution (F02, F05, F06, F09). Isolated SQLite."""

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


class EvolveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        from app import create_app

        cls.app = create_app(TestConfig)
        cls.client = cls.app.test_client()
        cls.ctx = cls.app.app_context()
        cls.ctx.push()
        cls.client.post(
            "/login",
            data={"username": "admin", "password": "admin"},
            follow_redirects=True,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        from app.extensions import db

        db.session.remove()
        db.engine.dispose()
        cls.ctx.pop()

    def test_onboarding_empty_world(self):
        from app.models import Project

        r = self.client.post(
            "/api/world/onboarding",
            json={
                "name": "Taller Norte",
                "path": "empty",
                "first_project": "Sitio web",
                "first_action": "Escribir la oferta",
                "currency": "CLP",
                "weekly_minutes": 360,
            },
        )
        self.assertEqual(r.status_code, 200)
        count = Project.query.filter_by(name="Sitio web").count()
        self.assertEqual(count, 1)
        r2 = self.client.post(
            "/api/world/onboarding",
            json={"name": "Taller Norte", "path": "empty", "first_project": "Sitio web"},
        )
        self.assertEqual(r2.status_code, 200)
        self.assertEqual(Project.query.filter_by(name="Sitio web").count(), 1)

    def test_partial_payment_100_40(self):
        from app.models import MoneyMovement
        from app.services.finance_service import FinanceService

        parent = FinanceService.add(
            direction="in", amount_cents=10000, concept="Factura-test", status="pending", currency="USD"
        )
        FinanceService.settle_partial(parent, 4000)
        totals = FinanceService.totals()
        usd = totals["currencies"]["USD"]
        self.assertEqual(usd["received"], 4000)
        self.assertEqual(usd["receivable"], 6000)
        self.assertGreaterEqual(MoneyMovement.query.filter_by(concept="Factura-test").count(), 1)

    def test_won_opportunity_does_not_create_money(self):
        from app.extensions import db
        from app.models import MoneyMovement, Opportunity
        from app.services.finance_service import FinanceService
        from app.services.project_service import ProjectService

        p = ProjectService.create({"name": "Cliente A Test", "status": "ACTIVE"})
        opp = Opportunity(project_id=p.id, name="Contrato-test", status="LEAD", estimated_value=50000)
        db.session.add(opp)
        db.session.commit()
        self.assertIsNone(FinanceService.from_won_opportunity(opp, False))
        before = MoneyMovement.query.count()
        mv = FinanceService.from_won_opportunity(opp, True)
        self.assertIsNotNone(mv)
        again = FinanceService.from_won_opportunity(opp, True)
        self.assertEqual(again.id, mv.id)
        self.assertEqual(MoneyMovement.query.count(), before + 1)

    def test_dependency_cycle_rejected(self):
        from app.extensions import db
        from app.models import Mission
        from app.services.dependency_service import DependencyError, DependencyService
        from app.services.project_service import ProjectService

        p = ProjectService.create({"name": "Deps Test", "status": "ACTIVE"})
        a = Mission(project_id=p.id, title="A-test", status="OPEN")
        b = Mission(project_id=p.id, title="B-test", status="OPEN")
        db.session.add_all([a, b])
        db.session.commit()
        DependencyService.add(b.id, a.id)
        with self.assertRaises(DependencyError):
            DependencyService.add(a.id, b.id)

    def test_daily_turn_respects_budget_and_blocks(self):
        from app.extensions import db
        from app.models import Mission
        from app.services.daily_turn_service import DailyTurnService
        from app.services.dependency_service import DependencyService
        from app.services.project_service import ProjectService

        p = ProjectService.create({"name": "Capacidad Test", "status": "ACTIVE"})
        m1 = Mission(project_id=p.id, title="Corta-test", status="OPEN", estimated_minutes=20, priority=1)
        m2 = Mission(project_id=p.id, title="Larga-test", status="OPEN", estimated_minutes=90, priority=2)
        m3 = Mission(project_id=p.id, title="Bloqueada-test", status="OPEN", estimated_minutes=15, priority=1)
        db.session.add_all([m1, m2, m3])
        db.session.commit()
        DependencyService.add(m3.id, m2.id)
        data = DailyTurnService.suggest(30)
        timed = [i["mission_id"] for i in data["items"] if i.get("minutes")]
        self.assertIn(m1.id, timed)
        self.assertNotIn(m2.id, timed)
        self.assertNotIn(m3.id, timed)
        self.assertLessEqual(data["used"], 30)

    def test_capture_convert_idempotent(self):
        from app.extensions import db
        from app.models import InboxCapture, Mission
        from app.services.capture_service import CaptureService
        from app.services.project_service import ProjectService

        p = ProjectService.create({"name": "Inbox Test", "status": "ACTIVE"})
        cap = CaptureService.add("Llamar a Marta")
        CaptureService.convert(cap, "mission", p.id)
        first = db.session.get(InboxCapture, cap.id)
        CaptureService.convert(first, "mission", p.id)
        self.assertEqual(Mission.query.filter_by(origin_capture_id=cap.id).count(), 1)

    def test_week_overload(self):
        from app.extensions import db
        from app.models import Mission
        from app.services.project_service import ProjectService
        from app.services.world_service import WorldService

        WorldService.save({"weekly_minutes": 360})
        p = ProjectService.create({"name": "Carga Test", "status": "ACTIVE"})
        start = WorldService.week_start_date()
        m = Mission(
            project_id=p.id,
            title="Exceso-test",
            status="OPEN",
            estimated_minutes=480,
            planned_date=start,
        )
        db.session.add(m)
        db.session.commit()
        self.assertEqual(WorldService.weekly_capacity_minutes(), 360)
        self.assertGreaterEqual(WorldService.planned_minutes_this_week(), 480)


if __name__ == "__main__":
    unittest.main()
