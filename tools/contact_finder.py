"""
Herramienta de búsqueda extendida de emails y normalización de teléfonos para WhatsApp.

find_missing_emails(): visita sitios web con múltiples rutas para encontrar emails faltantes.
populate_whatsapp_from_phone(): normaliza teléfonos a E.164 (+52XXXXXXXXXX) y los copia
    al campo whatsapp cuando este está vacío.

Nota sobre WhatsApp: no existe API pública para verificar si un número está registrado en
WhatsApp sin autenticación. La validación real ocurre al intentar enviar — si falla,
el número no tiene cuenta activa. Lo que sí podemos garantizar es el formato correcto.
"""

import logging
import re
import time
from datetime import datetime
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# ── Rutas de contacto comunes en sitios mexicanos ─────────────────────────────
CONTACT_PATHS = [
    "/contacto",
    "/contact",
    "/contact-us",
    "/contactanos",
    "/contactenos",
    "/nosotros",
    "/about",
    "/about-us",
    "/quienes-somos",
    "/quien-somos",
    "/equipo",
    "/team",
    "/informacion",
]


def _normalize_mx_phone(raw: str) -> str | None:
    """
    Convierte un teléfono mexicano a formato E.164 (+52XXXXXXXXXX).

    Acepta formatos como:
      (55) 1234-5678 → +5255123456789
      55 1234 5678   → +5255123456789
      +52 55 1234 5678 → +5255123456789
      5212345678     → +5212345678 (si ya tiene 10 dígitos sin código país)
    """
    if not raw:
        return None

    digits = re.sub(r"[^\d]", "", raw)

    # Ya tiene código de país (52) → 12 dígitos totales
    if len(digits) == 12 and digits.startswith("52"):
        return f"+{digits}"

    # 10 dígitos locales → agregar +52
    if len(digits) == 10:
        return f"+52{digits}"

    # 11 dígitos con "1" de más al inicio (formato antiguo México)
    if len(digits) == 11 and digits.startswith("1"):
        return f"+52{digits[1:]}"

    return None  # formato irreconocible


def _find_email_in_page(enricher, url: str, base_url: str) -> str | None:
    """
    Descarga una URL y extrae el primer email válido encontrado.
    Retorna None si robots.txt no permite la URL, si no accede o si no encuentra email.
    """
    if enricher.respect_robots and not enricher._is_allowed_by_robots(url):
        logger.debug(f"robots.txt no permite {url}")
        return None
    html = enricher._fetch_page(url)
    if not html:
        return None
    contacts = enricher._extract_contacts(html, base_url)
    return contacts.get("email")


def find_missing_emails(verbose: bool = True, limit: int = 400) -> dict:
    """
    Busca emails para todos los prospectos con sitio web que aún no tienen email.

    Estrategia más amplia que el enriquecimiento inicial:
    1. Visita página principal + página de contacto detectada automáticamente
    2. Si no encuentra, prueba rutas de contacto comunes (/contacto, /nosotros, etc.)
    3. Respeta robots.txt en cada URL (principal, contacto y rutas comunes)
    4. Timeout aumentado a 12 segundos por sitio

    Args:
        verbose: Imprimir progreso en consola.
        limit: Máximo de prospectos a procesar en esta ejecución.

    Returns:
        Diccionario con {found, not_found, errors}.
    """
    from concurrent.futures import ThreadPoolExecutor
    from concurrent.futures import TimeoutError as FuturesTimeoutError

    from skills.dashboard.app import Prospect, create_app, db
    from skills.scraping.data_enrichment import DataEnricher

    app = create_app()
    summary = {"found": 0, "not_found": 0, "errors": 0}

    with app.app_context():
        prospects = (
            Prospect.query.filter(Prospect.website.isnot(None), Prospect.website != "")
            .filter(Prospect.email.is_(None))
            .limit(limit)
            .all()
        )

        if not prospects:
            if verbose:
                print("Todos los prospectos con sitio web ya tienen email registrado.")
            return summary

        total = len(prospects)
        if verbose:
            print(f"\n\U0001f4e7 Buscando emails para {total} prospectos (busqueda extendida)...")

        # Respeta robots.txt en cada URL que visita
        enricher = DataEnricher(timeout=12, respect_robots=True)
        hard_timeout = 30  # segundos maximos por prospecto (incluyendo paginas extra)

        for i, prospect in enumerate(prospects, 1):
            if verbose:
                label = prospect.name[:40] if prospect.name else "?"
                print(f"  [{i}/{total}] {label}...", end=" ", flush=True)

            email_found = None

            try:
                # El cierre usa `prospect` de esta misma iteración: se ejecuta y se espera
                # (future.result) antes de pasar al siguiente prospecto.
                def _search_all_pages():
                    """Busca en pagina principal + pagina de contacto detectada."""
                    result = enricher.enrich_prospect(prospect.id, prospect.website)
                    if result.email:
                        return result.email

                    # Intentar rutas de contacto comunes directamente
                    parsed = urlparse(prospect.website)
                    base = f"{parsed.scheme}://{parsed.netloc}"
                    for path in CONTACT_PATHS:
                        url = base + path
                        email = _find_email_in_page(enricher, url, base)
                        if email:
                            return email
                        time.sleep(0.3)

                    return None

                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(_search_all_pages)
                    email_found = future.result(timeout=hard_timeout)

            except FuturesTimeoutError:
                summary["errors"] += 1
                if verbose:
                    print(f"\u2717 Timeout ({hard_timeout}s)")
                prospect.enriched_at = datetime.utcnow()
                db.session.commit()
                continue
            except Exception as e:
                summary["errors"] += 1
                if verbose:
                    print(f"\u2717 Error: {e}")
                continue

            if email_found:
                prospect.email = email_found
                prospect.enriched_at = datetime.utcnow()
                summary["found"] += 1
                if verbose:
                    print(f"\u2713 {email_found}")
            else:
                prospect.enriched_at = datetime.utcnow()
                summary["not_found"] += 1
                if verbose:
                    print("\u2014 no encontrado")

            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                logger.warning(f"Error guardando email de {prospect.name}: {e}")

            time.sleep(0.5)  # pausa cortés entre sitios

    if verbose:
        print(
            f"\n\u2705 Busqueda completada: {summary['found']} emails encontrados | "
            f"{summary['not_found']} sin email | {summary['errors']} errores"
        )

    return summary


def populate_whatsapp_from_phone(verbose: bool = True) -> dict:
    """
    Normaliza todos los teléfonos a formato E.164 (+52XXXXXXXXXX) y copia al campo
    whatsapp para los prospectos que no tienen WhatsApp registrado.

    IMPORTANTE: esto no verifica que el número esté registrado en WhatsApp.
    La validación real ocurre al intentar enviar — un envío fallido indica que
    el número no tiene cuenta activa de WhatsApp.

    Returns:
        Diccionario con {normalized_phones, whatsapp_populated, invalid_phones}.
    """
    from skills.dashboard.app import Prospect, create_app, db

    app = create_app()
    summary = {"normalized_phones": 0, "whatsapp_populated": 0, "invalid_phones": 0}

    with app.app_context():
        prospects = Prospect.query.filter(Prospect.phone.isnot(None)).all()
        total = len(prospects)

        if verbose:
            print(f"\n\U0001f4f1 Normalizando telefonos de {total} prospectos...")

        for prospect in prospects:
            normalized = _normalize_mx_phone(prospect.phone)

            if normalized:
                # Normalizar telefono almacenado
                if prospect.phone != normalized:
                    prospect.phone = normalized
                    summary["normalized_phones"] += 1

                # Poblar whatsapp si esta vacio
                if not prospect.whatsapp:
                    prospect.whatsapp = normalized
                    summary["whatsapp_populated"] += 1
            else:
                summary["invalid_phones"] += 1
                if verbose:
                    logger.debug(f"Telefono no normalizable: {prospect.phone} ({prospect.name})")

        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error guardando normalizacion de telefonos: {e}")
            raise

    if verbose:
        print(
            f"\u2705 Telefonos normalizados: {summary['normalized_phones']} | "
            f"WhatsApp nuevo: {summary['whatsapp_populated']} | "
            f"Formato invalido: {summary['invalid_phones']}"
        )

    return summary
