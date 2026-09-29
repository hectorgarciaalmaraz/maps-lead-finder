"""
Módulo de envío de SMS para Maps Lead Finder.
Usa Twilio para enviar mensajes de texto a números de celular.
Los SMS son breves (máx 160 caracteres por segmento).
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
SMS_MAX_CHARS = 320  # Máximo 2 segmentos de SMS


class SmsSender:
    """
    Envía SMS usando la API de Twilio.
    Adapta el texto de la propuesta para mensajes cortos.
    """

    def __init__(self, config: "AppConfig") -> None:
        """
        Args:
            config: Objeto AppConfig con credenciales de Twilio.
        """
        self.config = config

    def send(
        self,
        to_phone: str,
        message: str,
        prospect_id: int,
        proposal_id: int,
        db_session: "Session",
    ) -> dict:
        """
        Envía un SMS con las verificaciones previas requeridas.

        Args:
            to_phone: Número de teléfono del destinatario (formato E.164: +52XXXXXXXXXX).
            message: Texto del mensaje (se truncará a SMS_MAX_CHARS caracteres).
            prospect_id: ID del prospecto.
            proposal_id: ID de la propuesta.
            db_session: Sesión de SQLAlchemy.

        Returns:
            Diccionario con {success: bool, message: str}.
        """
        from skills.dashboard.app import Contact, Proposal, Prospect

        # Normalizar número de teléfono
        phone = self._normalize_phone(to_phone)
        if not phone:
            return {"success": False, "error": f"Número de teléfono inválido: {to_phone}"}

        # Verificación opt-out
        if self._is_opted_out(phone, db_session):
            return {"success": False, "error": "Número en lista de opt-out"}

        # Verificación ventana horaria
        if not self._is_within_contact_window():
            return {"success": False, "error": "Fuera de ventana de contacto (9AM-7PM)"}

        # Verificación límite diario
        if sent_today_count(db_session, "sms") >= self.config.contact.max_contacts_per_day:
            return {"success": False, "error": "Límite diario de SMS alcanzado"}

        # Verificar credenciales de Twilio
        if not self.config.twilio_account_sid or not self.config.twilio_auth_token:
            return {
                "success": False,
                "error": "Credenciales de Twilio no configuradas. Agrega TWILIO_* en .env",
            }

        # Adaptar mensaje para SMS
        sms_text = self._adapt_for_sms(message)

        # Enviar SMS
        error_message = None
        try:
            self._send_twilio_sms(phone, sms_text)
            logger.info(f"SMS enviado a {phone} (prospecto {prospect_id})")

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error enviando SMS a {phone}: {e}")

        # Registrar en la base de datos
        status = "enviado" if not error_message else "fallido"
        contact_record = Contact(
            prospect_id=prospect_id,
            proposal_id=proposal_id,
            channel="sms",
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

        return {"success": True, "message": f"SMS enviado a {phone}"}

    def _send_twilio_sms(self, to: str, body: str) -> None:
        """
        Realiza el envío del SMS usando el SDK de Twilio.
        Lanza excepción si hay error.
        """
        from twilio.rest import Client

        client = Client(self.config.twilio_account_sid, self.config.twilio_auth_token)
        client.messages.create(
            body=body,
            from_=self.config.twilio_phone_number,
            to=to,
        )

    def _adapt_for_sms(self, long_text: str) -> str:
        """
        Adapta el texto largo de una propuesta para caber en un SMS.
        Los SMS tienen un límite de ~160 caracteres por segmento.
        Se usan hasta 2 segmentos (320 caracteres).
        """
        if len(long_text) <= SMS_MAX_CHARS:
            return long_text

        # Extraer la parte más importante de la propuesta
        lines = long_text.strip().split("\n")
        # Tomar las primeras líneas con contenido
        important_lines = [line.strip() for line in lines if line.strip()][:5]
        abbreviated = " ".join(important_lines)

        if len(abbreviated) > SMS_MAX_CHARS:
            abbreviated = abbreviated[: SMS_MAX_CHARS - 3] + "..."

        return abbreviated

    def _normalize_phone(self, phone: str) -> str | None:
        """
        Normaliza el número de teléfono al formato E.164 (+52XXXXXXXXXX).
        Retorna None si el formato es inválido.
        """
        import re

        # Eliminar todos los caracteres no numéricos excepto el '+'
        clean = re.sub(r"[^\d+]", "", phone.strip())

        # Si no tiene código de país, asumir México (+52)
        if clean.startswith("00"):
            clean = "+" + clean[2:]
        elif not clean.startswith("+"):
            if len(clean) == 10:
                clean = "+52" + clean
            elif len(clean) == 12 and clean.startswith("52"):
                clean = "+" + clean

        # Validar longitud mínima
        if len(clean) < 10:
            return None

        return clean

    def _is_opted_out(self, phone: str, db_session) -> bool:
        """Verifica si el número está en la lista de opt-out."""
        from skills.dashboard.app import OptOut

        return db_session.query(OptOut).filter_by(contact_info=phone).first() is not None

    def _is_within_contact_window(self, timezone: str = DEFAULT_TIMEZONE) -> bool:
        """Verifica si la hora actual está dentro de la ventana permitida."""
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
