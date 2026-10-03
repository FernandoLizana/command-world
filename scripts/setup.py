#!/usr/bin/env python3
"""
Instalación portable de DR Command.

Funciona en Windows, macOS y Linux con Python 3.11+.
No pide tokens ni cuentas externas.

Uso (desde la raíz del proyecto):

    python scripts/setup.py
"""

from __future__ import annotations

import os
import secrets
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENV = ROOT / ".venv"
ENV_FILE = ROOT / ".env"
ENV_EXAMPLE = ROOT / ".env.example"
REQUIREMENTS = ROOT / "requirements.txt"
MIN_PY = (3, 11)


def venv_python() -> Path:
    if os.name == "nt":
        return VENV / "Scripts" / "python.exe"
    return VENV / "bin" / "python"


def fail(msg: str) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def run(args: list[str]) -> None:
    print(">", " ".join(str(a) for a in args))
    subprocess.check_call(args, cwd=ROOT)


def ensure_python() -> None:
    if sys.version_info < MIN_PY:
        fail(
            f"Se necesita Python {MIN_PY[0]}.{MIN_PY[1]} o superior. "
            f"Esta máquina tiene {sys.version_info.major}.{sys.version_info.minor}."
        )
    print(f"Python {sys.version.split()[0]} — OK")


def ensure_venv() -> Path:
    py = venv_python()
    if not py.exists():
        print("Creando entorno virtual .venv …")
        run([sys.executable, "-m", "venv", str(VENV)])
    else:
        print("Entorno virtual ya existe — OK")
    return py


def ensure_env() -> None:
    if ENV_FILE.exists():
        print(".env ya existe — no se sobrescribe")
        return
    if not ENV_EXAMPLE.exists():
        fail("Falta .env.example")
    shutil.copy(ENV_EXAMPLE, ENV_FILE)
    key = secrets.token_hex(32)
    text = ENV_FILE.read_text(encoding="utf-8")
    text = text.replace("SECRET_KEY=change-me-in-production", f"SECRET_KEY={key}")
    ENV_FILE.write_text(text, encoding="utf-8")
    print(".env creado con una SECRET_KEY nueva (archivo local, no se sube a git)")


def install(py: Path) -> None:
    run([str(py), "-m", "pip", "install", "--upgrade", "pip"])
    run([str(py), "-m", "pip", "install", "-r", str(REQUIREMENTS)])


def ensure_instance() -> None:
    (ROOT / "instance").mkdir(exist_ok=True)
    print("Carpeta instance/ — OK")


def main() -> None:
    os.chdir(ROOT)
    print("=== DR Command — instalación portable ===")
    ensure_python()
    py = ensure_venv()
    ensure_env()
    ensure_instance()
    install(py)
    print()
    print("Listo. No hace falta cuenta, token ni internet para usarlo.")
    print("Arranca así:")
    if os.name == "nt":
        print(r"  .venv\Scripts\python app.py")
    else:
        print("  .venv/bin/python app.py")
    print()
    print("Luego abre http://127.0.0.1:5000")
    print("Usuario inicial: admin / admin  (cámbialos en .env)")
    print("El primer arranque abre un mundo vacío. La demo es opcional.")


if __name__ == "__main__":
    main()
