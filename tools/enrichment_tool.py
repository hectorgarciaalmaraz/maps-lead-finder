"""
Orquestación del enriquecimiento de prospectos (visita de sitios web) para el CLI de Maps Lead Finder.
Wrapper sobre skills/scraping/data_enrichment.py para uso desde CLI.
"""

import logging
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError
from datetime import datetime

logger = logging.getLogger(__name__)


def enrich_prospects(
    limit: int = 50,
    only_new: bool = True,
    verbose: bool = False,
) -> dict:
    """
    Enriquece prospectos visitando sus sitios web para obtener emails y redes sociales.

    Args:
        limit: Máximo de prospectos a enriquecer.
        only_new: Si True, solo enriquece los que no han sido enriquecidos antes.
        verbose: Si imprimir progreso.

    Returns:
        Diccionario con {enriched, skipped, errors}.
    """
    from config import config
    from skills.dashboard.app import Prospect, create_app, db
    from skills.scraping.data_enrichment import DataEnricher

    app = create_app()
    summary = {"enriched": 0, "skipped": 0, "errors": 0}

    with app.app_context():
        query = Prospect.query.filter(Prospect.website.isnot(None))
        if only_new:
            query = query.filter(Prospect.enriched_at.is_(None))

        prospects = query.limit(limit).all()

        if not prospects:
            if verbose:
                print("No hay prospectos con sitio web pendientes de enriquecimiento.")
            return summary

        if verbose:
            print(f"\n🌐 Enriqueciendo {len(prospects)} prospectos...")

        enricher = DataEnricher(timeout=config.scraping.enrich_timeout_seconds)
        # Timeout duro por sitio: el doble del timeout de red para dar margen
        hard_timeout = config.scraping.enrich_timeout_seconds * 2 + 2

        for i, prospect in enumerate(prospects, 1):
            if verbose:
                print(f"  [{i}/{len(prospects)}] {prospect.name}...", end=" ", flush=True)

            try:
                # Ejecutar en thread con timeout duro para que ningún sitio bloquee el proceso
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(
                        enricher.enrich_prospect, prospect.id, prospect.website
                    )
                    result = future.result(timeout=hard_timeout)

                if result.has_data():
                    # Actualizar solo los campos vacíos
                    if result.email and not prospect.email:
                        prospect.email = result.email
                    if result.facebook_url and not prospect.facebook_url:
                        prospect.facebook_url = result.facebook_url
                    if result.instagram_url and not prospect.instagram_url:
                        prospect.instagram_url = result.instagram_url
                    if result.linkedin_url and not prospect.linkedin_url:
                        prospect.linkedin_url = result.linkedin_url
                    if result.whatsapp and not prospect.whatsapp:
                        prospect.whatsapp = result.whatsapp

                    prospect.enriched_at = datetime.utcnow()
                    db.session.commit()
                    summary["enriched"] += 1

                    if verbose:
                        extras = [
                            k
                            for k, v in {
                                "email": result.email,
                                "fb": result.facebook_url,
                                "ig": result.instagram_url,
                                "wa": result.whatsapp,
                            }.items()
                            if v
                        ]
                        print(f"✓ ({', '.join(extras)})" if extras else "✓ (sin datos nuevos)")

                else:
                    prospect.enriched_at = datetime.utcnow()  # Marcar como intentado
                    db.session.commit()
                    summary["skipped"] += 1
                    if verbose:
                        print("— sin datos nuevos")

            except FuturesTimeoutError:
                summary["errors"] += 1
                prospect.enriched_at = datetime.utcnow()  # Marcar como intentado para no repetir
                db.session.commit()
                if verbose:
                    print(f"✗ Timeout ({hard_timeout}s) — saltado")
            except Exception as e:
                summary["errors"] += 1
                logger.warning(f"Error enriqueciendo {prospect.name}: {e}")
                if verbose:
                    print(f"✗ Error: {e}")

    if verbose:
        print(f"\n✅ Completado: {summary['enriched']} enriquecidos, {summary['errors']} errores")

    return summary
