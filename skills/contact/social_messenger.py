"""
Módulo de mensajería en redes sociales para Maps Lead Finder.
Implementa envío de WhatsApp vía Twilio (productivo).
Instagram DM y LinkedIn Message son stubs que requieren configuración manual
(no tienen APIs públicas de envío de mensajes directos para terceros).
"""

import logging
from datetime import datetime
from typing import TYPE_CHECKING

import pytz

from skills.contact.limits import sent_today_count

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from config import AppConfig

logger = logging.getLogger(__name__)

DEFAULT_TIMEZONE = "America/Mexico_City"


class SocialMessenger:
    """
    Envía mensajes por canales de redes sociales.
    WhatsApp: automatizado vía Twilio WhatsApp Business.
    Instagram/LinkedIn: stubs para seguimiento manual.
    """

    def __init__(self, config: "AppConfig") -> None:
        """
        Args:
            config: Objeto AppConfig con credenciales de Twilio y redes sociales.
        """
        self.config = config

    def send_whatsapp(
        self,
        to_phone: str,
        message: str,
        prospect_id: int,
        proposal_id: int,
        db_session: "Session",
    ) -> dict:
        """
        Envía un mensaje de WhatsApp usando Twilio WhatsApp Business API.

        Nota: Requiere que el número de Twilio esté habilitado para WhatsApp Business.
        Los mensajes de primer contacto deben usar plantillas aprobadas por WhatsApp.

        Args:
            to_phone: Número de WhatsApp del destinatario (formato E.164).
            message: Texto del mensaje.
            prospect_id: ID del prospecto.
            proposal_id: ID de la propuesta.
            db_session: Sesión de SQLAlchemy.

        Returns:
            Diccionario con {success: bool, message: str}.
        """
        from skills.dashboard.app import Contact, Proposal, Prospect

        # Normalizar teléfono
        phone = self._normalize_phone(to_phone)
        if not phone:
            return {"success": False, "error": f"Número inválido: {to_phone}"}

        # Verificaciones
        if self._is_opted_out(phone, db_session):
            return {"success": False, "error": "Número en lista de opt-out"}

        if not self._is_within_contact_window():
            return {"success": False, "error": "Fuera de ventana de contacto (9AM-7PM)"}

        if sent_today_count(db_session, "whatsapp") >= self.config.contact.max_contacts_per_day:
            return {"success": False, "error": "Límite diario de mensajes alcanzado"}

        if not self.config.twilio_account_sid:
            return {"success": False, "error": "Credenciales de Twilio no configuradas"}

        # Adaptar mensaje (WhatsApp permite mensajes más largos que SMS)
        whatsapp_text = self._add_optout_footer(message)

        error_message = None
        try:
            self._send_twilio_whatsapp(phone, whatsapp_text)
            logger.info(f"WhatsApp enviado a {phone} (prospecto {prospect_id})")

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error enviando WhatsApp a {phone}: {e}")

        # Registrar en BD
        status = "enviado" if not error_message else "fallido"
        contact_record = Contact(
            prospect_id=prospect_id,
            proposal_id=proposal_id,
            channel="whatsapp",
            recipient=phone,
            status=status,
            sent_at=datetime.utcnow() if not error_message else None,
            error_message=error_message,
        )
        db_session.add(contact_record)

        if not error_message:
            prospect = db_session.get(Prospect, prospect_id)
            if prospect:
                prospect.status = "contactado"
            proposal = db_session.get(Proposal, proposal_id)
            if proposal:
                proposal.is_sent = True

        db_session.commit()

        if error_message:
            return {"success": False, "error": error_message}

        return {"success": True, "message": f"WhatsApp enviado a {phone}"}

    def log_instagram_dm(
        self,
        instagram_url: str,
        message: str,
        prospect_id: int,
        proposal_id: int,
        db_session: "Session",
    ) -> dict:
        """
        Registra un Instagram DM como pendiente de envío manual.

        NOTA: Instagram no permite envío automatizado de DMs a través de su API
        pública para cuentas que no son socios oficiales de Meta.
        Este método registra el contacto como 'pendiente' para seguimiento manual.

        Args:
            instagram_url: URL del perfil de Instagram del prospecto.
            message: Texto del mensaje a enviar manualmente.
            prospect_id: ID del prospecto.
            proposal_id: ID de la propuesta.
            db_session: Sesión de SQLAlchemy.

        Returns:
            Diccionario con {success: bool, message: str, manual_required: bool}.
        """
        from skills.dashboard.app import Contact

        logger.info(
            f"Instagram DM registrado para envío manual: {instagram_url} "
            f"(prospecto {prospect_id})"
        )

        # Registrar como pendiente de acción manual
        contact_record = Contact(
            prospect_id=prospect_id,
            proposal_id=proposal_id,
            channel="social",
            recipient=instagram_url,
            status="pendiente",
            error_message="Requiere envío manual. Instagram no permite DMs automatizados.",
        )
        db_session.add(contact_record)
        db_session.commit()

        return {
            "success": True,
            "manual_required": True,
            "message": (
                f"Instagram DM registrado para envío manual.\n"
                f"Perfil: {instagram_url}\n"
                f"Por favor envía el mensaje manualmente desde tu cuenta de Instagram."
            ),
        }

    def log_linkedin_message(
        self,
        linkedin_url: str,
        message: str,
        prospect_id: int,
        proposal_id: int,
        db_session: "Session",
    ) -> dict:
        """
        Registra un mensaje de LinkedIn como pendiente de envío manual.

        NOTA: La API de LinkedIn no permite envío de mensajes directos a perfiles
        que no son conexiones de primer grado. Requiere acción manual.
        """
        from skills.dashboard.app import Contact

        logger.info(
            f"LinkedIn mensaje registrado para envío manual: {linkedin_url} "
            f"(prospecto {prospect_id})"
        )

        contact_record = Contact(
            prospect_id=prospect_id,
            proposal_id=proposal_id,
            channel="social",
            recipient=linkedin_url,
            status="pendiente",
            error_message="Requiere envío manual. LinkedIn requiere conexión previa para DMs.",
        )
        db_session.add(contact_record)
        db_session.commit()

        return {
            "success": True,
            "manual_required": True,
            "message": f"LinkedIn mensaje registrado para envío manual: {linkedin_url}",
        }

    def _send_twilio_whatsapp(self, to: str, body: str) -> None:
        """
        Envía WhatsApp usando Twilio.
        El número de Twilio debe estar configurado para WhatsApp Business.
        """
        from twilio.rest import Client

        client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)

        # Twilio WhatsApp requiere el prefijo 'whatsapp:' en los números
        from_whatsapp = f"whatsapp:{self.config.twilio_phone_number}"
        to_whatsapp = f"whatsapp:{to}"

        client.messages.create(
            body=body,
            from_=from_whatsapp,
            to=to_whatsapp,
        )

    def _normalize_phone(self, phone: str) -> str | None:
        """Normaliza número al formato E.164."""
        import re

        clean = re.sub(r"[^\d+]", "", phone.strip())

        if clean.startswith("00"):
            clean = "+" + clean[2:]
        elif not clean.startswith("+"):
            if len(clean) == 10:
                clean = "+52" + clean
            elif len(clean) == 12 and clean.startswith("52"):
                clean = "+" + clean

        return clean if len(clean) >= 10 else None

    def _is_opted_out(self, phone: str, db_session) -> bool:
        """Verifica opt-out por número de teléfono."""
        from skills.dashboard.app import OptOut

        return db_session.query(OptOut).filter_by(contact_info=phone).first() is not None

    def _is_within_contact_window(self, timezone: str = DEFAULT_TIMEZONE) -> bool:
        """Verifica ventana horaria de contacto."""
        try:
            tz = pytz.timezone(timezone)
            hora_local = datetime.now(tz).hour
            return (
                self.config.contact.contact_window_start
                <= hora_local
                < self.config.contact.contact_window_end
            )
        except Exception:
            return True

    def _add_optout_footer(self, message: str) -> str:
        """Agrega instrucciones de baja al mensaje de WhatsApp."""
        footer = "\n\n_Responde 'STOP' para no recibir más mensajes._"
        return message + footer
