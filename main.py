"""
Punto de entrada principal del CLI para Maps Lead Finder.
Interfaz de línea de comandos construida con Click.

Uso:
    python main.py scrape --lat 19.4326 --lng -99.1332 --radius 5
    python main.py generate --all-pending
    python main.py send --proposal-id 1 --channel email
    python main.py send-batch --all-ready --channel email --dry-run
    python main.py stats
    python main.py init-db
"""

import logging
import sys
from pathlib import Path

import click

# Forzar UTF-8 en Windows para soporte de emojis en la consola
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# Agregar el directorio raíz al path de Python
sys.path.insert(0, str(Path(__file__).parent))


@click.group()
@click.version_option(version="1.0.0", prog_name="Maps Lead Finder")
def cli() -> None:
    """
    Maps Lead Finder – Prospección comercial automatizada con IA.

    \b
    Comandos principales:
      init-db      Inicializa la base de datos SQLite
      scrape       Busca negocios en Google Maps
      enrich       Enriquece prospectos visitando sus sitios web
      generate     Genera propuestas con IA
      send         Envía una propuesta específica
      send-batch   Envío masivo de propuestas pendientes
      stats        Muestra estadísticas del sistema
    """
    # Configurar logging básico al inicio
    logging.basicConfig(
        level=logging.WARNING,  # Solo warnings en CLI (INFO va al archivo de log)
        format="%(levelname)s: %(message)s",
    )


@cli.command("init-db")
def init_db() -> None:
    """Inicializa la base de datos SQLite y crea todas las tablas."""
    click.echo("🗄️  Inicializando base de datos...")
    try:
        from skills.dashboard.app import create_app, db

        app = create_app()
        with app.app_context():
            db.create_all()
            from config import config

            click.echo(f"✅ Base de datos creada en: {config.database_path}")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--lat", default=None, type=float, help="Latitud del centro de búsqueda")
@click.option("--lng", default=None, type=float, help="Longitud del centro de búsqueda")
@click.option("--radius", default=None, type=float, help="Radio de búsqueda en kilómetros")
@click.option("--categories", "-c", multiple=True, help="Categorías a buscar (múltiple permitido)")
@click.option("--enrich/--no-enrich", default=True, help="Visitar sitios web para enriquecer datos")
@click.option("--verbose", "-v", is_flag=True, help="Mostrar progreso detallado")
def scrape(
    lat: float | None,
    lng: float | None,
    radius: float | None,
    categories: tuple[str, ...],
    enrich: bool,
    verbose: bool,
) -> None:
    """
    Busca negocios locales en Google Maps y los guarda en la base de datos.

    \b
    Ejemplos:
      python main.py scrape --lat 19.4326 --lng -99.1332
      python main.py scrape --lat 19.4326 --lng -99.1332 --radius 10
      python main.py scrape -c restaurant -c gym --radius 3
    """
    try:
        from config import config

        # Usar valores por defecto de configuración si no se proporcionaron
        search_lat = lat or config.default_center_lat
        search_lng = lng or config.default_center_lng
        search_radius = radius or config.scraping.default_radius_km
        search_categories = list(categories) if categories else None

        if not verbose:
            click.echo(f"🔍 Buscando negocios (radio: {search_radius} km)...")

        from tools.google_maps_tool import run_scraping

        summary = run_scraping(
            lat=search_lat,
            lng=search_lng,
            radius_km=search_radius,
            categories=search_categories,
            enrich=enrich,
            verbose=verbose,
        )

        if not verbose:
            click.echo(
                f"✅ {summary['found']} encontrados | {summary['new']} nuevos | {summary['duplicates']} duplicados"
            )
            if enrich:
                click.echo(f"   {summary['enriched']} sitios web enriquecidos")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        if verbose:
            import traceback

            traceback.print_exc()
        sys.exit(1)


@cli.command()
@click.option("--limit", default=50, type=int, help="Máximo de prospectos a enriquecer")
@click.option("--all-prospects", is_flag=True, help="Incluir prospectos ya enriquecidos")
@click.option("--verbose", "-v", is_flag=True)
def enrich(limit: int, all_prospects: bool, verbose: bool) -> None:
    """Visita sitios web de prospectos para extraer emails y redes sociales."""
    try:
        click.echo(f"🌐 Enriqueciendo hasta {limit} prospectos...")
        from tools.enrichment_tool import enrich_prospects

        summary = enrich_prospects(
            limit=limit,
            only_new=not all_prospects,
            verbose=verbose,
        )
        if not verbose:
            click.echo(f"✅ {summary['enriched']} enriquecidos | {summary['errors']} errores")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--prospect-id", type=int, default=None, help="ID de un prospecto específico")
@click.option("--all-pending", is_flag=True, help="Generar para todos sin propuesta")
@click.option("--batch-size", default=10, type=int, help="Número de propuestas a generar")
@click.option("--verbose", "-v", is_flag=True)
def generate(prospect_id: int | None, all_pending: bool, batch_size: int, verbose: bool) -> None:
    """
    Genera propuestas comerciales con IA para prospectos.

    \b
    Ejemplos:
      python main.py generate --prospect-id 42
      python main.py generate --all-pending --batch-size 20
    """
    if not prospect_id and not all_pending:
        raise click.UsageError("Usa --prospect-id N o --all-pending")

    try:
        if prospect_id:
            click.echo(f"✨ Generando propuesta para prospecto #{prospect_id}...")
            from tools.proposal_tool import generate_proposal

            result = generate_proposal(prospect_id, verbose=verbose)
            if result["success"]:
                click.echo(f"✅ Propuesta generada: {result['word_count']} palabras")
            else:
                click.echo(f"❌ {result.get('error')}", err=True)
                sys.exit(1)

        elif all_pending:
            click.echo(
                f"✨ Generando propuestas para prospectos pendientes (lote: {batch_size})..."
            )
            from tools.proposal_tool import generate_all_pending

            summary = generate_all_pending(batch_size=batch_size, verbose=verbose)
            if not verbose:
                click.echo(f"✅ {summary['generated']} generadas | {summary['errors']} errores")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option("--proposal-id", type=int, required=True, help="ID de la propuesta a enviar")
@click.option(
    "--channel",
    type=click.Choice(["email", "sms", "whatsapp"]),
    required=True,
    help="Canal de envío",
)
@click.option("--dry-run", is_flag=True, help="Simular sin enviar realmente")
@click.option("--verbose", "-v", is_flag=True)
def send(proposal_id: int, channel: str, dry_run: bool, verbose: bool) -> None:
    """Envía una propuesta específica por el canal indicado."""
    try:
        mode = " [DRY-RUN]" if dry_run else ""
        click.echo(f"📤{mode} Enviando propuesta #{proposal_id} por {channel}...")

        from tools.contact_tool import send_proposal

        result = send_proposal(
            proposal_id=proposal_id,
            channel=channel,
            dry_run=dry_run,
            verbose=verbose,
        )

        if result.get("success"):
            click.echo(f"✅ {result.get('message', 'Enviado exitosamente')}")
        else:
            click.echo(f"❌ {result.get('error')}", err=True)
            sys.exit(1)

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command("send-batch")
@click.option("--all-ready", is_flag=True, help="Enviar todas las propuestas pendientes")
@click.option(
    "--channel",
    type=click.Choice(["email", "sms", "whatsapp"]),
    default="email",
    show_default=True,
    help="Canal de envío",
)
@click.option("--limit", default=50, type=int, help="Máximo de envíos")
@click.option("--dry-run", is_flag=True, help="Simular sin enviar")
@click.option("--verbose", "-v", is_flag=True)
def send_batch(all_ready: bool, channel: str, limit: int, dry_run: bool, verbose: bool) -> None:
    """
    Envío masivo de propuestas pendientes.

    \b
    Ejemplos:
      python main.py send-batch --all-ready --channel email
      python main.py send-batch --all-ready --channel email --dry-run
    """
    if not all_ready:
        raise click.UsageError("Usa --all-ready para enviar todas las propuestas pendientes")

    try:
        mode = " [DRY-RUN]" if dry_run else ""
        click.echo(f"📤{mode} Enviando propuestas pendientes por {channel}...")

        from tools.contact_tool import send_all_ready

        summary = send_all_ready(
            channel=channel,
            limit=limit,
            dry_run=dry_run,
            verbose=verbose,
        )
        if not verbose:
            click.echo(f"✅ {summary['sent']} enviadas | {summary['errors']} errores")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option(
    "--output",
    "-o",
    default=None,
    help="Nombre del archivo CSV (default: prospectos_YYYY-MM-DD.csv)",
)
@click.option(
    "--sheet-id",
    default=None,
    envvar="GOOGLE_SHEETS_SPREADSHEET_ID",
    help="ID de un Google Sheet existente para escribir directo (ver instrucciones)",
)
@click.option(
    "--only-with-proposals",
    is_flag=True,
    help="Exportar solo prospectos que ya tienen propuesta generada",
)
@click.option(
    "--credentials",
    "-k",
    default=None,
    envvar="GOOGLE_SHEETS_CREDENTIALS_FILE",
    help="Ruta al JSON de credenciales (solo necesario con --sheet-id)",
)
def export(
    output: str | None,
    sheet_id: str | None,
    only_with_proposals: bool,
    credentials: str | None,
) -> None:
    """
    Exporta prospectos a CSV (default) o directamente a un Google Sheet existente.

    Modo CSV (default): genera un archivo local que importas a Google Sheets en 2 clics.
    Modo Sheets (--sheet-id): escribe directo en un Sheet que tú creaste y compartiste.

    \b
    Ejemplos:
      python main.py export
      python main.py export -o restaurantes_marzo.csv
      python main.py export --only-with-proposals
      python main.py export --sheet-id TU_SHEET_ID
    """
    import json as _json
    import os
    from datetime import datetime as _dt

    from skills.dashboard.app import Proposal, Prospect, create_app

    # ── Construir los datos ──────────────────────────────────────────────
    app = create_app()
    with app.app_context():
        query = Prospect.query
        if only_with_proposals:
            query = query.filter(Prospect.proposals.any())
        prospects = query.order_by(Prospect.scraped_at.desc()).all()

        if not prospects:
            click.echo("No hay prospectos en la base de datos.")
            return

        filas = []
        for p in prospects:
            latest = (
                Proposal.query.filter_by(prospect_id=p.id)
                .order_by(Proposal.generated_at.desc())
                .first()
            )
            filas.append(
                {
                    "ID": p.id,
                    "Nombre": p.name,
                    "Categoría": p.category,
                    "Dirección": p.address or "",
                    "Teléfono": p.phone or "",
                    "Email": p.email or "",
                    "WhatsApp": p.whatsapp or "",
                    "Tiene WhatsApp": "Sí" if p.whatsapp else "No",
                    "Link WhatsApp": (
                        f"https://wa.me/{p.whatsapp.lstrip('+')}" if p.whatsapp else ""
                    ),
                    "Sitio Web": p.website or "",
                    "Instagram": p.instagram_url or "",
                    "Facebook": p.facebook_url or "",
                    "Calificación": p.rating or "",
                    "# Reseñas": p.review_count or 0,
                    "Descripción Google": p.editorial_summary or "",
                    "Distancia (km)": round(p.distance_km, 2) if p.distance_km else "",
                    "Estado": p.status,
                    "Mensaje Email": latest.content if latest else "",
                    "Mensaje WhatsApp": latest.content_whatsapp if latest else "",
                    "Guión Llamada": latest.content_phone if latest else "",
                    "Servicios": ", ".join(
                        _json.loads(latest.services_selected)
                        if latest and latest.services_selected
                        else []
                    ),
                }
            )

    con_propuesta = sum(1 for f in filas if f.get("Mensaje Email"))

    # ── Modo: escribir a Google Sheet existente ──────────────────────────
    if sheet_id:
        creds_file = credentials or os.getenv("GOOGLE_SHEETS_CREDENTIALS_FILE")
        if not creds_file or not Path(creds_file).exists():
            click.echo(
                "❌ Necesitas GOOGLE_SHEETS_CREDENTIALS_FILE en .env para usar --sheet-id", err=True
            )
            sys.exit(1)
        try:
            import gspread
            from google.oauth2.service_account import Credentials as GCredentials
        except ImportError:
            click.echo("❌ pip install gspread google-auth", err=True)
            sys.exit(1)
        try:
            scopes = [
                "https://www.googleapis.com/auth/spreadsheets",
                "https://www.googleapis.com/auth/drive",
            ]
            gc = gspread.authorize(
                GCredentials.from_service_account_file(creds_file, scopes=scopes)
            )
            sh = gc.open_by_key(sheet_id)
            ws = sh.sheet1
            ws.clear()
            headers = list(filas[0].keys())
            rows = [[str(f.get(h, "")) for h in headers] for f in filas]
            ws.update([headers] + rows)
            ws.freeze(rows=1)
            ws.format("1:1", {"textFormat": {"bold": True}})
            url = f"https://docs.google.com/spreadsheets/d/{sh.id}"
            click.echo(f"✅ {len(filas)} prospectos → Google Sheet ({con_propuesta} con mensajes)")
            click.echo(f"   {url}")
        except Exception as e:
            click.echo(f"❌ Error escribiendo al Sheet: {e}", err=True)
            sys.exit(1)
        return

    # ── Modo default: exportar a CSV ─────────────────────────────────────
    import csv

    fecha = _dt.now().strftime("%Y-%m-%d")
    archivo = output or f"prospectos_{fecha}.csv"

    try:
        with open(archivo, "w", newline="", encoding="utf-8-sig") as f:
            # utf-8-sig para que Google Sheets y Excel lean acentos correctamente
            writer = csv.DictWriter(f, fieldnames=list(filas[0].keys()))
            writer.writeheader()
            writer.writerows(filas)

        click.echo(f"✅ {len(filas)} prospectos exportados → {archivo}")
        click.echo(
            f"   {con_propuesta} con mensajes generados | {len(filas) - con_propuesta} sin mensaje"
        )
        click.echo("\n   Para subir a Google Sheets:")
        click.echo("   1. Abre sheets.new en tu navegador")
        click.echo(f"   2. Archivo → Importar → Subir → selecciona '{archivo}'")
        click.echo("   3. Separador: coma → Importar datos")
    except Exception as e:
        click.echo(f"❌ Error generando CSV: {e}", err=True)
        sys.exit(1)


@cli.command("find-emails")
@click.option(
    "--limit", default=400, show_default=True, type=int, help="Máximo de prospectos a procesar."
)
@click.option("--verbose", "-v", is_flag=True, default=True, show_default=True)
def find_emails(limit: int, verbose: bool) -> None:
    """
    Busca emails faltantes visitando sitios web con estrategia extendida.

    \b
    Procesa solo prospectos que tienen sitio web pero aún no tienen email.
    Prueba página principal + página de contacto detectada + rutas comunes
    (/contacto, /nosotros, /about, etc.).
    """
    click.echo(f"\n📧 Iniciando búsqueda extendida de emails (máx. {limit} prospectos)...")
    try:
        from tools.contact_finder import find_missing_emails

        summary = find_missing_emails(verbose=verbose, limit=limit)
        click.echo(
            f"\n✅ {summary['found']} emails nuevos | "
            f"{summary['not_found']} sin email | {summary['errors']} errores"
        )
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command("fix-whatsapp")
@click.option("--verbose", "-v", is_flag=True, default=True, show_default=True)
def fix_whatsapp(verbose: bool) -> None:
    """
    Normaliza teléfonos a formato E.164 (+52XXXXXXXXXX) y los copia
    al campo WhatsApp donde este está vacío.
    """
    click.echo("\n📱 Normalizando teléfonos y poblando campo WhatsApp...")
    try:
        from tools.contact_finder import populate_whatsapp_from_phone

        summary = populate_whatsapp_from_phone(verbose=verbose)
        click.echo(
            f"\n✅ Teléfonos normalizados: {summary['normalized_phones']} | "
            f"WhatsApp nuevos: {summary['whatsapp_populated']} | "
            f"Formato inválido: {summary['invalid_phones']}"
        )
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command("generate-local")
@click.option(
    "--batch-size", default=796, show_default=True, help="Máximo de prospectos a procesar."
)
def generate_local(batch_size: int) -> None:
    """Genera propuestas de email y WhatsApp sin API externa (generador local)."""
    click.echo(f"\n📝 Generando propuestas locales (máx. {batch_size})...")
    try:
        from tools.local_proposal_generator import generate_all_local

        summary = generate_all_local(batch_size=batch_size, verbose=True)
        click.echo(
            f"\n✅ {summary['generated']} propuestas generadas | "
            f"{summary['errors']} errores | {summary['skipped']} saltados"
        )
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command("regenerate")
@click.option("--verbose", "-v", is_flag=True, default=True, show_default=True)
def regenerate(verbose: bool) -> None:
    """Elimina TODAS las propuestas y las regenera con los templates actualizados."""
    click.echo("\n⚠️  Esto eliminará todas las propuestas existentes y las regenerará.")
    if not click.confirm("¿Continuar?"):
        click.echo("Operación cancelada.")
        return
    try:
        from tools.local_proposal_generator import regenerate_all

        summary = regenerate_all(verbose=verbose)
        click.echo(
            f"\n✅ {summary['deleted']} eliminadas → {summary['generated']} regeneradas "
            f"| {summary['errors']} errores"
        )
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command("update-whatsapp")
def update_whatsapp() -> None:
    """Actualiza los mensajes de WhatsApp de todas las propuestas existentes."""
    click.echo("\n📱 Actualizando mensajes de WhatsApp...")
    try:
        from tools.local_proposal_generator import update_whatsapp_messages

        summary = update_whatsapp_messages(verbose=True)
        click.echo(f"\n✅ {summary['updated']} mensajes actualizados | {summary['errors']} errores")
    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


@cli.command()
def stats() -> None:
    """Muestra estadísticas del sistema de prospección."""
    try:
        from skills.dashboard.app import Contact, Proposal, Prospect, create_app

        app = create_app()

        with app.app_context():
            total_prospects = Prospect.query.count()
            total_proposals = Proposal.query.count()
            total_sent = Contact.query.filter_by(status="enviado").count()
            total_responses = Contact.query.filter_by(status="respondido").count()

            click.echo("\n" + "=" * 50)
            click.echo("  MAPS LEAD FINDER – ESTADÍSTICAS")
            click.echo("=" * 50)
            click.echo(f"  Prospectos total:       {total_prospects:>6}")
            click.echo(f"  Propuestas generadas:   {total_proposals:>6}")
            click.echo(f"  Mensajes enviados:      {total_sent:>6}")
            click.echo(f"  Respuestas recibidas:   {total_responses:>6}")

            if total_sent > 0:
                rate = total_responses / total_sent * 100
                click.echo(f"  Tasa de conversión:     {rate:>5.1f}%")

            click.echo("=" * 50 + "\n")

    except Exception as e:
        click.echo(f"❌ Error: {e}", err=True)
        sys.exit(1)


if __name__ == "__main__":
    cli()
