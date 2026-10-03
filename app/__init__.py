"""DR Command application factory."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from flask import Flask, render_template
from flask_login import current_user

from config import Config
from app.extensions import csrf, db, login_manager, migrate


def create_app(config_class: type = Config) -> Flask:
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="templates",
        static_folder="static",
    )
    app.config.from_object(config_class)
    app.url_map.strict_slashes = False
    Path(app.instance_path).mkdir(parents=True, exist_ok=True)

    _configure_logging(app)
    _init_extensions(app)
    _register_blueprints(app)
    _register_context(app)
    _register_cli(app)
    _register_errors(app)

    with app.app_context():
        from app import models  # noqa: F401
        from app.services.schema_service import ensure_schema

        ensure_schema()
        from app.seeds import _ensure_admin, _ensure_empire
        from app.services.world_service import WorldService

        _ensure_empire()
        _ensure_admin()
        WorldService.sanitize_legacy_demo()
        from app.extensions import db as _db

        _db.session.commit()
        if not app.testing:
            key = str(app.config.get("SECRET_KEY") or "")
            weak = key in {"", "dev-dr-command-change-me", "change-me-in-production"}
            if weak and not app.debug:
                raise RuntimeError("Define SECRET_KEY en .env. Ejecuta: python scripts/setup.py")
            if weak:
                app.logger.warning(
                    "SECRET_KEY de desarrollo. Ejecuta python scripts/setup.py antes de abrir el puerto a la red."
                )

    return app


def _configure_logging(app: Flask) -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    app.logger.setLevel(logging.INFO)


def _init_extensions(app: Flask) -> None:
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)

    from app.models import User

    @login_manager.user_loader
    def load_user(user_id: str):
        return db.session.get(User, int(user_id))


def _register_blueprints(app: Flask) -> None:
    from app.routes.api import bp as api_bp
    from app.routes.auth import bp as auth_bp
    from app.routes.council import bp as council_bp
    from app.routes.evolve_api import bp as evolve_api_bp
    from app.routes.rpg_api import bp as rpg_api_bp
    from app.routes.main import bp as main_bp
    from app.routes.missions import bp as missions_bp
    from app.routes.ops import bp as ops_bp
    from app.routes.projects import bp as projects_bp
    from app.routes.settings import bp as settings_bp
    from app.routes.tech import bp as tech_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(main_bp)
    app.register_blueprint(projects_bp, url_prefix="/projects")
    app.register_blueprint(missions_bp, url_prefix="/missions")
    app.register_blueprint(council_bp, url_prefix="/council")
    app.register_blueprint(tech_bp, url_prefix="/tech-tree")
    app.register_blueprint(ops_bp)
    app.register_blueprint(settings_bp, url_prefix="/settings")
    app.register_blueprint(api_bp, url_prefix="/api")
    app.register_blueprint(evolve_api_bp, url_prefix="/api")
    app.register_blueprint(rpg_api_bp, url_prefix="/api")
    csrf.exempt(api_bp)
    csrf.exempt(evolve_api_bp)
    csrf.exempt(rpg_api_bp)


def _register_context(app: Flask) -> None:
    @app.context_processor
    def inject_globals():
        data = {
            "app_name": app.config.get("APP_NAME", "DR Command"),
            "app_codename": app.config.get("APP_CODENAME", "DR Command"),
            "demo_mode": app.config.get("DEMO_MODE"),
        }
        if current_user.is_authenticated:
            from app.services.game_service import GameService
            from app.services.world_service import WorldService

            data["hud"] = GameService.hud()
            data["world_prefs"] = WorldService.prefs()
        else:
            data["hud"] = None
            data["world_prefs"] = {}
        return data

    @app.template_filter("clp")
    def clp(value):
        try:
            n = int(value or 0)
        except (TypeError, ValueError):
            return "$0"
        return f"${n:,}".replace(",", ".")

    @app.template_filter("bar")
    def bar(value, width: int = 10) -> str:
        try:
            n = max(0, min(100, int(value or 0)))
        except (TypeError, ValueError):
            n = 0
        filled = round(n / 100 * width)
        return "█" * filled + "░" * (width - filled)


def _register_cli(app: Flask) -> None:
    @app.cli.command("seed")
    def seed_command():
        """Load demo data if the empire is empty."""
        from app.seeds import seed_if_empty

        seed_if_empty()
        print("Seed complete.")

    @app.cli.command("reseed")
    def reseed_command():
        """Drop all tables and reload demo data. Destructive."""
        from app.seeds import seed_all

        db.drop_all()
        db.create_all()
        seed_all()
        print("Reseed complete.")


def _register_errors(app: Flask) -> None:
    @app.errorhandler(404)
    def not_found(_e):
        return render_template("command/error.html", code=404, message="Sector no encontrado"), 404

    @app.errorhandler(500)
    def server_error(_e):
        return render_template("command/error.html", code=500, message="Fallo en el centro de mando"), 500
