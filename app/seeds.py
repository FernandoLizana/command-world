"""
Demo / first-run seed.

All generated records set is_demo=True where the column exists so they stay
identifiable and editable. Running seed twice is a no-op if projects exist.
"""

from __future__ import annotations

import json
import logging
from datetime import date, datetime, timedelta

from flask import current_app

from app.extensions import db
from app.models import (
    ActivityLog,
    CouncilDecision,
    Empire,
    GameEvent,
    GameSetting,
    Issue,
    LevelRequirement,
    Mission,
    MissionObjective,
    Opportunity,
    Project,
    Technology,
    TurnLog,
    User,
)
from app.models.constants import DEFAULT_XP_REWARDS
from app.services.metrics_service import MetricsService

logger = logging.getLogger(__name__)

NOW = datetime.utcnow()


def seed_if_empty() -> None:
    if Project.query.first() is not None:
        return
    logger.info("Empty world detected — loading generic demo seed")
    seed_all()


DEMO_MAP_POSITIONS = {
    "taller-norte": (1296, 768),
    "fortaleza-datos": (1664, 1152),
    "laboratorio-atlas": (1856, 1408),
    "casa-cuidado": (704, 1216),
    "mercado-abierto": (416, 512),
    "taller-comunitario": (2144, 416),
}


def seed_all() -> None:
    _ensure_admin()
    _ensure_empire()
    _ensure_settings()
    projects = _seed_projects()
    _seed_requirements(projects)
    _seed_missions(projects)
    _seed_opportunities(projects)
    _seed_issues(projects)
    _seed_events(projects)
    _seed_tech_tree()
    _seed_turn()
    MetricsService.refresh_all()
    db.session.commit()
    logger.info("Demo seed complete: %s projects", len(projects))


def _ensure_admin() -> User:
    username = current_app.config["ADMIN_USERNAME"]
    user = User.query.filter_by(username=username).first()
    if user:
        return user
    user = User(
        username=username,
        email=current_app.config["ADMIN_EMAIL"],
        display_name="Comandante",
        is_admin=True,
    )
    user.set_password(current_app.config["ADMIN_PASSWORD"])
    db.session.add(user)
    db.session.flush()
    return user


def _ensure_empire() -> Empire:
    empire = db.session.get(Empire, 1)
    if empire:
        return empire
    empire = Empire(
        id=1,
        name="Mi mundo",
        money=0,
        available_hours=8,
        level=1,
        xp=0,
        current_turn=1,
        last_turn_at=NOW - timedelta(hours=8),
    )
    db.session.add(empire)
    db.session.flush()
    return empire


def _ensure_settings() -> None:
    if not GameSetting.get("xp_rewards"):
        db.session.add(
            GameSetting(key="xp_rewards", value=json.dumps(DEFAULT_XP_REWARDS))
        )
    if not GameSetting.get("seed_version"):
        db.session.add(GameSetting(key="seed_version", value="demo-1"))
    if not GameSetting.get("demo_notice"):
        db.session.add(
            GameSetting(
                key="demo_notice",
                value="Datos de demostración. Edítalos o bórralos cuando quieras.",
            )
        )


def _seed_projects() -> dict[str, Project]:
    specs = [
        dict(
            name="Taller Norte",
            slug="taller-norte",
            description="[DEMO] Estudio de servicios profesionales. Oferta, clientes y entregas. Dato ficticio editable.",
            category="freelance",
            status="ACTIVE",
            level=3,
            xp=420,
            health=78,
            product_score=70,
            technology_score=55,
            sales_score=62,
            marketing_score=48,
            finance_score=44,
            stability_score=72,
            priority=1,
            revenue=0,
            monthly_revenue=0,
            potential_revenue=400000,
            hours_invested=180,
            last_activity=NOW - timedelta(hours=6),
            map_x=1296,
            map_y=768,
            icon="fa-briefcase",
            building_type="capital",
            color_theme="#c9a227",
        ),
        dict(
            name="Fortaleza de datos",
            slug="fortaleza-datos",
            description="[DEMO] Producto digital de monitoreo. Dato ficticio editable.",
            category="saas",
            status="ACTIVE",
            level=3,
            xp=640,
            health=82,
            product_score=82,
            technology_score=91,
            sales_score=41,
            marketing_score=32,
            finance_score=38,
            stability_score=74,
            priority=1,
            revenue=0,
            monthly_revenue=0,
            potential_revenue=900000,
            hours_invested=320,
            last_activity=NOW - timedelta(hours=18),
            map_x=1664,
            map_y=1152,
            icon="fa-satellite-dish",
            building_type="fortress",
            color_theme="#5eead4",
        ),
        dict(
            name="Casa Cuidado",
            slug="casa-cuidado",
            description="[DEMO] Proyecto de servicio a personas. Dato ficticio editable.",
            category="services",
            status="ACTIVE",
            level=2,
            xp=210,
            health=65,
            product_score=58,
            technology_score=54,
            sales_score=28,
            marketing_score=36,
            finance_score=22,
            stability_score=48,
            priority=3,
            revenue=0,
            monthly_revenue=0,
            potential_revenue=500000,
            hours_invested=90,
            last_activity=NOW - timedelta(days=8),
            map_x=704,
            map_y=1216,
            icon="fa-heart-pulse",
            building_type="city",
            color_theme="#e8b44c",
        ),
        dict(
            name="Mercado abierto",
            slug="mercado-abierto",
            description="[DEMO] Catálogo y canal de pedidos. Dato ficticio editable.",
            category="commerce",
            status="EXPERIMENT",
            level=2,
            xp=175,
            health=58,
            product_score=46,
            technology_score=50,
            sales_score=24,
            marketing_score=40,
            finance_score=18,
            stability_score=42,
            priority=4,
            revenue=0,
            monthly_revenue=0,
            potential_revenue=350000,
            hours_invested=70,
            last_activity=NOW - timedelta(days=5),
            map_x=416,
            map_y=512,
            icon="fa-store",
            building_type="sanctuary",
            color_theme="#a78bfa",
        ),
        dict(
            name="Taller comunitario",
            slug="taller-comunitario",
            description="[DEMO] Proyecto personal en pausa consciente. Dato ficticio editable.",
            category="personal",
            status="PAUSED",
            level=1,
            xp=80,
            health=40,
            product_score=30,
            technology_score=28,
            sales_score=10,
            marketing_score=22,
            finance_score=8,
            stability_score=35,
            priority=5,
            revenue=0,
            monthly_revenue=0,
            potential_revenue=0,
            hours_invested=40,
            last_activity=NOW - timedelta(days=21),
            map_x=2144,
            map_y=416,
            icon="fa-handshake-angle",
            building_type="village",
            color_theme="#60a5fa",
        ),
        dict(
            name="Laboratorio Atlas",
            slug="laboratorio-atlas",
            description="[DEMO] App o producto digital en prototipo. Dato ficticio editable.",
            category="product",
            status="EXPERIMENT",
            level=2,
            xp=260,
            health=71,
            product_score=62,
            technology_score=78,
            sales_score=18,
            marketing_score=20,
            finance_score=15,
            stability_score=60,
            priority=2,
            revenue=0,
            monthly_revenue=0,
            potential_revenue=600000,
            hours_invested=120,
            last_activity=NOW - timedelta(days=2),
            map_x=1856,
            map_y=1408,
            icon="fa-flask",
            building_type="lab",
            color_theme="#34d399",
        ),
    ]
    out: dict[str, Project] = {}
    for spec in specs:
        spec["is_demo"] = True
        project = Project(**spec)
        db.session.add(project)
        db.session.flush()
        out[project.slug] = project
    return out


def _seed_requirements(projects: dict[str, Project]) -> None:
    z = projects["fortaleza-datos"]
    items = [
        (3, 4, "MVP publicado", True, 0),
        (3, 4, "Entorno de producción", True, 1),
        (3, 4, "QA automatizado básico", True, 2),
        (3, 4, "Landing comercial", True, 3),
        (3, 4, "Primer cliente pago", False, 4),
        (3, 4, "Ingresos recurrentes definidos", False, 5),
    ]
    for from_l, to_l, desc, done, pos in items:
        db.session.add(
            LevelRequirement(
                project_id=z.id,
                from_level=from_l,
                to_level=to_l,
                description=desc,
                completed=done,
                position=pos,
            )
        )
    mm = projects["casa-cuidado"]
    for i, (desc, done) in enumerate(
        [
            ("Prototipo usable", True),
            ("Tres conversaciones de piloto", False),
            ("Modelo de cobro definido", False),
        ]
    ):
        db.session.add(
            LevelRequirement(
                project_id=mm.id,
                from_level=2,
                to_level=3,
                description=desc,
                completed=done,
                position=i,
            )
        )


def _mission(project: Project, **kwargs) -> Mission:
    kwargs.setdefault("is_demo", True)
    m = Mission(project_id=project.id, **kwargs)
    db.session.add(m)
    db.session.flush()
    return m


def _objectives(mission: Mission, items: list[tuple[str, bool]]) -> None:
    for i, (text, done) in enumerate(items):
        db.session.add(
            MissionObjective(mission_id=mission.id, description=text, completed=done, position=i)
        )


def _seed_missions(projects: dict[str, Project]) -> None:
    z = projects["fortaleza-datos"]
    m = _mission(
        z,
        title="Conseguir primer cliente pago",
        description="[DEMO] Cerrar el primer contrato del producto de datos.",
        type="SALES",
        priority=1,
        status="IN_PROGRESS",
        xp_reward=500,
        estimated_hours=12,
        due_date=date.today() + timedelta(days=14),
    )
    _objectives(
        m,
        [
            ("Preparar demo estable", True),
            ("Landing lista", True),
            ("Contactar 30 prospectos", False),
            ("Conseguir reunión", False),
            ("Cerrar contrato", False),
        ],
    )
    _mission(
        z,
        title="Observabilidad de errores en producción",
        type="QA",
        priority=2,
        status="OPEN",
        xp_reward=40,
        estimated_hours=6,
        description="[DEMO] Pipeline de alertas.",
    )
    mm = projects["casa-cuidado"]
    _mission(
        mm,
        title="Llamar a 5 residencias para piloto",
        type="SALES",
        priority=2,
        status="OPEN",
        xp_reward=25,
        estimated_hours=3,
        description="[DEMO] Reactivar pipeline.",
    )
    dr = projects["taller-norte"]
    m = _mission(
        dr,
        title="Cerrar el plan de la semana",
        type="ADMINISTRATION",
        priority=2,
        status="OPEN",
        xp_reward=15,
        estimated_hours=2,
        description="[DEMO] Ritual de mando.",
    )
    _objectives(m, [("Revisar métricas", False), ("Asignar horas de la semana", False)])
    lab = projects["laboratorio-atlas"]
    _mission(
        lab,
        title="Documento de tesis del laboratorio",
        type="RESEARCH",
        priority=2,
        status="IN_PROGRESS",
        xp_reward=35,
        estimated_hours=8,
        description="[DEMO] Alcance del prototipo.",
    )
    tea = projects["taller-comunitario"]
    _mission(
        tea,
        title="Pausar con criterio (no abandonar)",
        type="ADMINISTRATION",
        priority=4,
        status="DONE",
        xp_reward=10,
        estimated_hours=1,
        completed_at=NOW - timedelta(days=20),
        description="[DEMO] Misión cerrada de ejemplo.",
    )
    db.session.add(
        ActivityLog(
            project_id=tea.id,
            action_type="complete_task",
            description="Misión demo completada",
            xp=10,
        )
    )


def _seed_opportunities(projects: dict[str, Project]) -> None:
    z = projects["fortaleza-datos"]
    rows = [
        dict(
            name="Observabilidad para operador regional",
            company="Andes Connect",
            contact_name="Paula Rivas",
            estimated_value=480000,
            probability=40,
            status="MEETING",
            source="red",
            next_action="Enviar demo grabada",
            next_action_date=date.today() + timedelta(days=2),
            notes="[DEMO]",
        ),
        dict(
            name="QA continuo pyme software",
            company="NorteDev",
            contact_name="Luis Mora",
            estimated_value=180000,
            probability=25,
            status="LEAD",
            source="inbound",
            next_action="Primer correo",
            next_action_date=date.today() + timedelta(days=1),
            notes="[DEMO]",
        ),
        dict(
            name="Piloto hospitalario",
            company="Clínica del Valle",
            estimated_value=0,
            probability=15,
            status="CONTACTED",
            source="introducción",
            notes="[DEMO] Encaja mejor en Casa Cuidado; mal clasificado a propósito.",
        ),
    ]
    for row in rows:
        row["project_id"] = z.id
        row["is_demo"] = True
        db.session.add(Opportunity(**row))
    db.session.add(
        Opportunity(
            project_id=projects["casa-cuidado"].id,
            name="Piloto 3 residencias",
            company="Red Cuidar",
            estimated_value=240000,
            probability=20,
            status="LEAD",
            notes="[DEMO]",
            is_demo=True,
        )
    )
    db.session.add(
        Opportunity(
            project_id=projects["taller-norte"].id,
            name="Alianza de marca corporativa",
            company="Partner local",
            estimated_value=900000,
            probability=30,
            status="PROPOSAL",
            notes="[DEMO]",
            is_demo=True,
        )
    )


def _seed_issues(projects: dict[str, Project]) -> None:
    db.session.add(
        Issue(
            project_id=projects["fortaleza-datos"].id,
            title="Onboarding demasiado técnico para el comprador",
            description="[DEMO] Frena el cierre comercial.",
            severity="HIGH",
            status="OPEN",
            type="product",
            is_demo=True,
        )
    )
    db.session.add(
        Issue(
            project_id=projects["fortaleza-datos"].id,
            title="Falta caso de éxito público",
            description="[DEMO]",
            severity="MEDIUM",
            status="OPEN",
            type="marketing",
            is_demo=True,
        )
    )
    db.session.add(
        Issue(
            project_id=projects["casa-cuidado"].id,
            title="7+ días sin seguimiento comercial",
            description="[DEMO] Riesgo de abandono.",
            severity="HIGH",
            status="OPEN",
            type="sales",
            is_demo=True,
        )
    )
    db.session.add(
        Issue(
            project_id=projects["taller-comunitario"].id,
            title="Proyecto congelado sin fecha de revisión",
            description="[DEMO]",
            severity="MEDIUM",
            status="OPEN",
            type="strategy",
            is_demo=True,
        )
    )


def _seed_events(projects: dict[str, Project]) -> None:
    rows = [
        (projects["fortaleza-datos"], "Nuevo posible prospecto", "Andes Connect pidió demo.", "opportunity", "fa-fire", 1),
        (projects["casa-cuidado"], "7 días sin seguimiento", "Nadie tocó el frente comercial.", "warning", "fa-triangle-exclamation", 2),
        (projects["taller-norte"], "Objetivo de marca cumplido", "Sitio corporativo estable.", "success", "fa-trophy", 4),
        (projects["laboratorio-atlas"], "Avance de laboratorio", "Documento de alcance al 40%.", "info", "fa-flask", 2),
        (projects["mercado-abierto"], "Experimento activo", "Marketplace aún en hipótesis.", "info", "fa-flask", 3),
        (None, "Turno anterior cerrado", "[DEMO] Resumen de ayer: foco en Fortaleza de datos.", "turn", "fa-hourglass-end", 1),
    ]
    for project, title, desc, kind, icon, days_ago in rows:
        db.session.add(
            GameEvent(
                project_id=project.id if project else None,
                title=title,
                description=desc,
                kind=kind,
                icon=icon,
                created_at=NOW - timedelta(days=days_ago),
                is_demo=True,
            )
        )


def _seed_tech_tree() -> None:
    def tech(**kwargs) -> Technology:
        t = Technology(**kwargs)
        db.session.add(t)
        db.session.flush()
        return t

    mvp = tech(
        name="MVP",
        category="PRODUCTO",
        status="COMPLETED",
        progress=100,
        description="Producto mínimo usable.",
        position=0,
        xp_reward=20,
    )
    saas = tech(
        name="SaaS",
        category="PRODUCTO",
        status="IN_PROGRESS",
        progress=55,
        parent_id=mvp.id,
        description="Cobro recurrente y cuentas.",
        position=1,
        xp_reward=40,
    )
    tech(
        name="Multiempresa",
        category="PRODUCTO",
        status="LOCKED",
        progress=0,
        parent_id=saas.id,
        description="Aislamiento por organización.",
        position=2,
        xp_reward=60,
    )
    crm = tech(
        name="CRM",
        category="VENTAS",
        status="AVAILABLE",
        progress=10,
        description="Pipeline único de oportunidades.",
        position=0,
        xp_reward=25,
    )
    emailing = tech(
        name="Emailing",
        category="VENTAS",
        status="LOCKED",
        progress=0,
        parent_id=crm.id,
        description="Secuencias de seguimiento.",
        position=1,
        xp_reward=25,
    )
    tech(
        name="Multicanal",
        category="VENTAS",
        status="LOCKED",
        progress=0,
        parent_id=emailing.id,
        description="WhatsApp, mail y llamadas unificadas.",
        position=2,
        xp_reward=40,
    )
    ollama = tech(
        name="Ollama",
        category="IA",
        status="COMPLETED",
        progress=100,
        description="Capa local de inferencia.",
        position=0,
        xp_reward=30,
    )
    rag = tech(
        name="RAG",
        category="IA",
        status="AVAILABLE",
        progress=0,
        parent_id=ollama.id,
        description="Contexto con documentos propios.",
        position=1,
        xp_reward=50,
    )
    tech(
        name="Agentes",
        category="IA",
        status="LOCKED",
        progress=0,
        parent_id=rag.id,
        description="Especialistas con aprobación humana.",
        position=2,
        xp_reward=80,
    )


def _seed_turn() -> None:
    db.session.add(
        TurnLog(
            turn_number=185,
            started_at=NOW - timedelta(days=1, hours=10),
            ended_at=NOW - timedelta(hours=8),
            hours_available=8,
            hours_spent=5,
            xp_gained=5,
            summary="[DEMO] Foco en Fortaleza de datos. Casa Cuidado quedó en silencio.",
            events_json='["Casa Cuidado sin seguimiento"]',
            recommendations_json='["Cerrar demo Fortaleza de datos","Llamar a tres contactos de Casa Cuidado"]',
        )
    )
    db.session.add(
        CouncilDecision(
            summary="[DEMO] Dedicar esta semana más recursos a Fortaleza de datos.",
            payload_json=json.dumps(
                {
                    "priority_project": "Fortaleza de datos",
                    "recommendations": [
                        "Alta madurez técnica",
                        "Potencial comercial",
                        "Varias oportunidades abiertas",
                    ],
                },
                ensure_ascii=False,
            ),
            decision="pending",
        )
    )
