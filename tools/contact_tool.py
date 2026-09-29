"""
Orquestación del envío de propuestas (email, SMS, WhatsApp) para el CLI de Maps Lead Finder.
Wrapper sobre skills/contact/ para envío de propuestas desde CLI.
"""

import logging

logger = logging.getLogger(__name__)


def send_proposal(
    proposal_id: int,
    channel: str,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Envía una propuesta por el canal especificado.

    Args:
        proposal_id: ID de la propuesta a enviar.
        channel: Canal de envío ('email', 'sms', 'whatsapp').
        dry_run: Si True, simula el envío sin enviarlo realmente.
        verbose: Si imprimir detalles en consola.

    Returns:
        Diccionario con {success, message}.
    """
    from config import config
    from skills.dashboard.app import Proposal, Prospect, create_app, db

    app = create_app()

    with app.app_context():
        proposal = db.session.get(Proposal, proposal_id)
        if not proposal:
            return {"success": False, "error": f"Propuesta #{proposal_id} no encontrada"}

        prospect = db.session.get(Prospect, proposal.prospect_id)
        if not prospect:
            return {"success": False, "error": "Prospecto no encontrado"}

        if proposal.is_sent:
            return {"success": False, "error": "Esta propuesta ya fue enviada"}

        if dry_run:
            if verbose:
                print(f"\n[DRY-RUN] Se enviaría propuesta #{proposal_id}")
                print(f"  Negocio: {prospect.name}")
                print(f"  Canal: {channel}")
                if channel == "email":
                    print(f"  A: {prospect.email or 'SIN EMAIL'}")
                elif channel in ("sms", "whatsapp"):
                    print(f"  A: {prospect.phone or 'SIN TELÉFONO'}")
            return {
                "success": True,
                "dry_run": True,
                "message": f"Simulación: se enviaría por {channel}",
            }

        # Envío real
        if channel == "email":
            if not prospect.email:
                return {"success": False, "error": "El prospecto no tiene email"}
            from skills.contact.email_sender import EmailSender

            sender = EmailSender(config)
            result = sender.send(
                to_email=prospect.email,
                subject=f"Una propuesta especial para {prospect.name} – {config.agency.name}",
                body=proposal.content,
                prospect_id=prospect.id,
                proposal_id=proposal.id,
                db_session=db.session,
            )

        elif channel == "sms":
            if not prospect.phone:
                return {"success": False, "error": "El prospecto no tiene teléfono"}
            from skills.contact.sms_sender import SmsSender

            sender = SmsSender(config)
            result = sender.send(
                to_phone=prospect.phone,
                message=proposal.content,
                prospect_id=prospect.id,
                proposal_id=proposal.id,
                db_session=db.session,
            )

        elif channel == "whatsapp":
            phone = prospect.whatsapp or prospect.phone
            if not phone:
                return {"success": False, "error": "El prospecto no tiene teléfono/WhatsApp"}
            from skills.contact.social_messenger import SocialMessenger

            sender = SocialMessenger(config)
            result = sender.send_whatsapp(
                to_phone=phone,
                message=proposal.content,
                prospect_id=prospect.id,
                proposal_id=proposal.id,
                db_session=db.session,
            )

        else:
            return {"success": False, "error": f"Canal no soportado: {channel}"}

        if verbose:
            status = "✓" if result.get("success") else "✗"
            print(f"  {status} Propuesta #{proposal_id} → {prospect.name} por {channel}")
            if not result.get("success"):
                print(f"    Error: {result.get('error')}")

        return result


def send_all_ready(
    channel: str = "email",
    limit: int = 50,
    dry_run: bool = False,
    verbose: bool = False,
) -> dict:
    """
    Envía todas las propuestas pendientes de envío.

    Args:
        channel: Canal de envío.
        limit: Máximo de propuestas a enviar.
        dry_run: Si simular sin enviar.
        verbose: Si imprimir progreso.

    Returns:
        Diccionario con {sent, errors, skipped}.
    """
    from skills.dashboard.app import Proposal, create_app

    app = create_app()
    summary = {"sent": 0, "errors": 0, "skipped": 0}

    with app.app_context():
        proposals = Proposal.query.filter_by(is_sent=False).limit(limit).all()

        if not proposals:
            if verbose:
                print("No hay propuestas pendientes de envío.")
            return summary

        if verbose:
            mode = "[DRY-RUN] " if dry_run else ""
            print(f"\n{mode}📤 Enviando {len(proposals)} propuestas por {channel}...")

        for proposal in proposals:
            result = send_proposal(
                proposal_id=proposal.id,
                channel=channel,
                dry_run=dry_run,
                verbose=verbose,
            )
            if result.get("success"):
                summary["sent"] += 1
            else:
                summary["errors"] += 1

    if verbose:
        print(f"\n✅ Completado: {summary['sent']} enviadas, {summary['errors']} errores")

    return summary
