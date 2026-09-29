"""
Punto de entrada para el dashboard web de Maps Lead Finder.
Inicia el servidor Flask en modo de desarrollo o producción.

Uso:
    python dashboard.py
    python dashboard.py --port 8080
    python dashboard.py --host 0.0.0.0 --port 5000
"""

import os
import sys
from pathlib import Path

import click

# Forzar UTF-8 en Windows para soporte de emojis en la consola
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Agregar el directorio raíz al path de Python
sys.path.insert(0, str(Path(__file__).parent))


@click.command()
@click.option("--host", default=None, help="Host del servidor (default: 127.0.0.1)")
@click.option("--port", default=None, type=int, help="Puerto del servidor (default: 5000)")
@click.option("--debug", is_flag=True, help="Ejecutar en modo debug")
def main(host: str | None, port: int | None, debug: bool) -> None:
    """
    Inicia el dashboard web de Maps Lead Finder.
    Abre tu navegador en http://localhost:5000 después de iniciarlo.
    """
    try:
        from config import config, setup_logging

        setup_logging(config)

        dashboard_cfg = {}
        try:
            import yaml

            with open(Path(__file__).parent / "config" / "settings.yaml", encoding="utf-8") as f:
                settings = yaml.safe_load(f)
            dashboard_cfg = settings.get("dashboard", {})
        except Exception:
            pass

        server_host = host or dashboard_cfg.get("host", "127.0.0.1")
        server_port = port or dashboard_cfg.get("port", 5000)
        server_debug = debug or (os.environ.get("FLASK_DEBUG", "false").lower() == "true")

        from skills.dashboard.app import create_app

        app = create_app()

        print("\n🚀 Maps Lead Finder Dashboard")
        print(f"   Abre en: http://{server_host}:{server_port}")
        print("   Presiona Ctrl+C para detener\n")

        app.run(
            host=server_host,
            port=server_port,
            debug=server_debug,
        )

    except ImportError as e:
        print(f"❌ Error de importación: {e}")
        print("   Asegúrate de haber instalado las dependencias: pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Error al iniciar el dashboard: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
