"""
Configuración de instalación para Maps Lead Finder.

Instalación en modo editable (desde la raíz del repositorio):
    pip install -e .

Expone dos comandos:
    maps-lead-finder            → CLI (equivale a `python main.py`)
    maps-lead-finder-dashboard  → dashboard web (equivale a `python dashboard.py`)

Las plantillas HTML (templates/) y los YAML de config/ se leen desde el repositorio,
por eso se recomienda la instalación editable.
"""

from pathlib import Path

from setuptools import find_packages, setup

_REQUIREMENTS = [
    line.strip()
    for line in (Path(__file__).parent / "requirements.txt")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip() and not line.startswith("#") and not line.startswith("pytest")
]

setup(
    name="maps-lead-finder",
    version="1.0.0",
    description=(
        "Prospección de negocios locales: Google Places → propuestas con Claude → "
        "envío por email, SMS y WhatsApp con controles de opt-out"
    ),
    author="Hector Garcia Almaraz",
    license="MIT",
    packages=find_packages(exclude=["tests", "tests.*"]),
    py_modules=["main", "dashboard"],
    python_requires=">=3.10",
    install_requires=_REQUIREMENTS,
    entry_points={
        "console_scripts": [
            "maps-lead-finder=main:cli",
            "maps-lead-finder-dashboard=dashboard:main",
        ],
    },
)
