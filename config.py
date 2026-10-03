"""Application configuration. SQLite by default, PostgreSQL-ready via DATABASE_URL."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://") :]
    return url


class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-dr-command-change-me")
    _default_db = f"sqlite:///{(BASE_DIR / 'instance' / 'empire.db').as_posix()}"
    _raw_db = os.getenv("DATABASE_URL", _default_db)
    if _raw_db.startswith("sqlite:///instance/"):
        _raw_db = f"sqlite:///{(BASE_DIR / 'instance' / 'empire.db').as_posix()}"
    SQLALCHEMY_DATABASE_URI = _normalize_database_url(_raw_db)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True}

    DEMO_MODE = _as_bool(os.getenv("DEMO_MODE"), default=False)
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "admin")
    ADMIN_PASSWORD = os.getenv("ADMIN_PASSWORD", "admin")
    ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "commander@localhost")
    APP_NAME = "DR Command"
    APP_CODENAME = "DR Command"

    OLLAMA_ENABLED = _as_bool(os.getenv("OLLAMA_ENABLED"), default=True)
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434").rstrip("/")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")
    OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "8"))
    SOUND_ENABLED = _as_bool(os.getenv("SOUND_ENABLED"), default=False)

    WTF_CSRF_TIME_LIMIT = None
