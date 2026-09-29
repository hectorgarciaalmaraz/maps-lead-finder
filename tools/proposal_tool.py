"""
Orquestación de la generación de propuestas con Claude para el CLI de Maps Lead Finder.
Wrapper sobre skills/proposals/ para uso desde CLI y scripts.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def generate_proposal(prospect_id: int, verbose: bool = False) -> dict:
    """
    Genera una propuesta de IA para un prospecto específico.

    Args:
        prospect_id: ID del prospecto en la base de datos.
        verbose: Si imprimir el resultado en consola.

    Returns:
        Diccionario con {success, prospect_name, word_count, service_ids, proposal_id}.
    """
    from config import config
    from skills.dashboard.app import Proposal, Prospect, create_app, db
    from skills.proposals.generator import ProposalGenerator
    from skills.proposals.service_catalog import ServiceCatalog

    app = create_app()

    with app.app_context():
        prospect = db.session.get(Prospect, prospect_id)
        if not prospect:
            return {"success": False, "error": f"Prospecto #{prospect_id} no encontrado"}

        catalog = ServiceCatalog(Path(__file__).parent.parent / "config" / "services_catalog.yaml")
        generator = ProposalGenerator(
            api_key=config.anthropic_api_key,
            config=config.proposals,
            catalog=catalog,
            agency=config.agency,
        )

        email_text, whatsapp_text, service_ids, word_count = generator.generate(prospect)
        wc_whatsapp = len(whatsapp_text.split())

        proposal = Proposal(
            prospect_id=prospect.id,
            content=email_text,
            content_whatsapp=whatsapp_text,
            services_selected=json.dumps(service_ids),
            template_used=prospect.category,
            word_count=word_count,
            word_count_whatsapp=wc_whatsapp,
        )
        db.session.add(proposal)
        prospect.status = "propuesta_generada"
        db.session.commit()

        if verbose:
            print(f"\n✨ Propuestas generadas para: {prospect.name}")
            print(f"   Servicios: {', '.join(service_ids)}")
            print(f"\n── EMAIL ({word_count} palabras) ──────────────────────────────")
            print(email_text)
            print(f"\n── WHATSAPP ({wc_whatsapp} palabras) ─────────────────────────")
            print(whatsapp_text)
            print()

        return {
            "success": True,
            "prospect_name": prospect.name,
            "proposal_id": proposal.id,
            "word_count": word_count,
            "word_count_whatsapp": wc_whatsapp,
            "service_ids": service_ids,
        }


def generate_all_pending(batch_size: int = 10, verbose: bool = False) -> dict:
    """
    Genera propuestas para todos los prospectos sin propuesta.

    Args:
        batch_size: Cuántos prospectos procesar a la vez.
        verbose: Si imprimir progreso.

    Returns:
        Diccionario con {generated, errors, skipped}.
    """
    from skills.dashboard.app import Prospect, create_app

    app = create_app()
    summary = {"generated": 0, "errors": 0, "skipped": 0}

    with app.app_context():
        prospects_without_proposal = (
            Prospect.query.filter(~Prospect.proposals.any()).limit(batch_size).all()
        )

        if not prospects_without_proposal:
            if verbose:
                print("No hay prospectos sin propuesta.")
            return summary

        if verbose:
            print(f"\n📝 Generando propuestas para {len(prospects_without_proposal)} prospectos...")

        for i, prospect in enumerate(prospects_without_proposal, 1):
            if verbose:
                print(f"  [{i}/{len(prospects_without_proposal)}] {prospect.name}...", end=" ")
            try:
                result = generate_proposal(prospect.id, verbose=False)
                if result["success"]:
                    summary["generated"] += 1
                    if verbose:
                        print(f"✓ ({result['word_count']} palabras)")
                else:
                    summary["errors"] += 1
                    if verbose:
                        print(f"✗ {result.get('error', 'error desconocido')}")
            except Exception as e:
                summary["errors"] += 1
                if verbose:
                    print(f"✗ Error: {e}")

    if verbose:
        print(f"\n✅ Completado: {summary['generated']} generadas, {summary['errors']} errores")

    return summary
