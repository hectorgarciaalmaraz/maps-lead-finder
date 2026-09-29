"""
Orquestación de la búsqueda en Google Places para el CLI de Maps Lead Finder.
Wrapper sobre skills/scraping/ con interfaz simple para scripts y CLI.
"""

import logging

logger = logging.getLogger(__name__)


def run_scraping(
    lat: float,
    lng: float,
    radius_km: float,
    categories: list | None = None,
    enrich: bool = True,
    verbose: bool = False,
) -> dict:
    """
    Ejecuta el scraping completo de Google Maps y retorna un resumen.

    Args:
        lat: Latitud del centro de búsqueda.
        lng: Longitud del centro de búsqueda.
        radius_km: Radio de búsqueda en kilómetros.
        categories: Categorías a buscar (None = todas las configuradas).
        enrich: Si visitar sitios web para enriquecer datos.
        verbose: Si imprimir progreso en consola.

    Returns:
        Diccionario con {found, new, duplicates, enriched, errors}.
    """
    from config import config
    from skills.dashboard.app import Prospect, create_app, db
    from skills.scraping.data_enrichment import DataEnricher
    from skills.scraping.google_maps import GoogleMapsScraper

    if verbose:
        print("\n🔍 Iniciando búsqueda...")
        print(f"   Centro: {lat}, {lng}")
        print(f"   Radio: {radius_km} km")
        if categories:
            print(f"   Categorías: {', '.join(categories)}")
        print()

    app = create_app()
    summary = {"found": 0, "new": 0, "duplicates": 0, "enriched": 0, "errors": 0}

    with app.app_context():
        # Scraper de Google Maps
        def status_update(**kwargs) -> None:
            """Imprime la categoría en curso cuando el modo verbose está activo."""
            if verbose and "current_category" in kwargs:
                cat = kwargs["current_category"]
                done = kwargs.get("categories_done", 0)
                total = kwargs.get("categories_total", 1)
                print(f"  [{done}/{total}] Buscando: {cat}")

        scraper = GoogleMapsScraper(
            api_key=config.google_maps_api_key,
            db_session=db.session,
            config=config.scraping,
            status_callback=status_update,
        )

        prospects, new_count, dup_count = scraper.search_and_save(
            lat=lat, lng=lng, radius_km=radius_km, categories=categories
        )

        summary["found"] = len(prospects)
        summary["new"] = new_count
        summary["duplicates"] = dup_count

        if verbose:
            print(f"\n✓ {len(prospects)} negocios encontrados, {new_count} nuevos guardados")

        # Enriquecimiento de datos
        if enrich and new_count > 0:
            if verbose:
                print("\n🌐 Enriqueciendo datos con sitios web...")

            enricher = DataEnricher(timeout=config.scraping.enrich_timeout_seconds)
            to_enrich = (
                Prospect.query.filter(
                    Prospect.website.isnot(None),
                    Prospect.enriched_at.is_(None),
                )
                .limit(50)
                .all()
            )

            for prospect in to_enrich:
                try:
                    result = enricher.enrich_prospect(prospect.id, prospect.website)
                    if result.has_data():
                        if result.email and not prospect.email:
                            prospect.email = result.email
                        if result.facebook_url and not prospect.facebook_url:
                            prospect.facebook_url = result.facebook_url
                        if result.instagram_url and not prospect.instagram_url:
                            prospect.instagram_url = result.instagram_url
                        if result.whatsapp and not prospect.whatsapp:
                            prospect.whatsapp = result.whatsapp

                        from datetime import datetime

                        prospect.enriched_at = datetime.utcnow()
                        db.session.commit()
                        summary["enriched"] += 1

                        if verbose:
                            print(f"  ✓ {prospect.name} – datos enriquecidos")

                except Exception as e:
                    summary["errors"] += 1
                    logger.warning(f"Error enriqueciendo {prospect.name}: {e}")

            if verbose:
                print(f"\n✓ {summary['enriched']} prospectos enriquecidos")

    return summary
