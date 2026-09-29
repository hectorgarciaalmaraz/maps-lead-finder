"""
Módulo de envío de emails para Maps Lead Finder.
Soporta SMTP (Gmail, etc.) y SendGrid como alternativa.
Respeta la ventana horaria de contacto y el límite diario de envíos.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

import pytz

from skills.contact.limits import sent_today_count

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

    from config import AppConfig

logger = logging.getLogger(__name__)

# Zona horaria por defecto para verificar ventana horaria (México)
DEFAULT_TIMEZONE = "America/Mexico_City"


class EmailSender:
    """
    Envía emails de propuesta a negocios prospecto.
    Implementa verificaciones de opt-out, ventana horaria y límite diario.
    """

    def __init__(self, config: "AppConfig") -> None:
        """
        Args:
            config: Objeto AppConfig con credenciales SMTP/SendGrid.
        """
        self.config = config
        self._use_sendgrid = bool(config.sendgrid_api_key)

    def send(
        self,
        to_email: str,
        subject: str,
        body: str,
        prospect_id: int,
        proposal_id: int,
        db_session: "Session",
    ) -> dict:
        """
        Envía un email con todas las verificaciones previas.

        Verificaciones:
        1. Opt-out: El destinatario no solicitó baja
        2. Ventana horaria: 9 AM - 7 PM hora local
        3. Límite diario: Máximo 50 emails por día

        Args:
            to_email: Dirección de email del destinatario.
            subject: Asunto del email.
            body: Cuerpo del email (texto plano).
            prospect_id: ID del prospecto en la base de datos.
            proposal_id: ID de la propuesta enviada.
            db_session: Sesión de SQLAlchemy para registrar el envío.

        Returns:
            Diccionario con {success: bool, message: str}.
        """
        from skills.dashboard.app import Contact, Proposal, Prospect

        # Verificación 1: Opt-out
        if self._is_opted_out(to_email, db_session):
            logger.info(f"Email {to_email} está en la lista de opt-out. No se envía.")
            return {"success": False, "error": "Destinatario en lista de opt-out"}

        # Verificación 2: Ventana horaria
        if not self._is_within_contact_window():
            return {
                "success": False,
                "error": (
                    f"Fuera de la ventana de contacto "
                    f"({self.config.contact.contact_window_start}:00 - "
                    f"{self.config.contact.contact_window_end}:00)"
                ),
            }

        # Verificación 3: Límite diario
        if sent_today_count(db_session, "email") >= self.config.contact.max_contacts_per_day:
            return {
                "success": False,
                "error": f"Límite diario de {self.config.contact.max_contacts_per_day} emails alcanzado",
            }

        # Agregar pie de opt-out al email
        body_with_optout = self._add_optout_footer(body, to_email)

        # Intentar envío
        error_message = None
        try:
            if self._use_sendgrid:
                self._send_via_sendgrid(to_email, subject, body_with_optout)
            else:
                self._send_via_smtp(to_email, subject, body_with_optout)
            logger.info(f"Email enviado exitosamente a {to_email} (prospecto {prospect_id})")

        except Exception as e:
            error_message = str(e)
            logger.error(f"Error enviando email a {to_email}: {e}")

        # Registrar intento en la base de datos
        status = "enviado" if not error_message else "fallido"
        contact_record = Contact(
            prospect_id=prospect_id,
            proposal_id=proposal_id,
            channel="email",
            recipient=to_email,
            status=status,
            sent_at=datetime.utcnow() if not error_message else None,
            error_message=error_message,
        )
        db_session.add(contact_record)

        # Actualizar status del prospecto si fue exitoso
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

        return {"success": True, "message": f"Email enviado a {to_email}"}

    def _send_via_smtp(self, to: str, subject: str, body: str) -> None:
        """
        Envía email usando SMTP con TLS (compatible con Gmail y otros proveedores).
        Lanza excepción si hay error.
        """
        if not self.config.smtp_user or not self.config.smtp_password:
            raise ValueError(
                "Credenciales SMTP no configuradas. Verifica SMTP_USER y SMTP_PASSWORD en .env"
            )

        mensaje = MIMEMultipart("alternative")
        mensaje["Subject"] = subject
        mensaje["From"] = f"{self._sender_name()} <{self.config.smtp_user}>"
        mensaje["To"] = to

        # Agregar cuerpo en texto plano
        parte_texto = MIMEText(body, "plain", "utf-8")
        mensaje.attach(parte_texto)

        with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as servidor:
            servidor.ehlo()
            servidor.starttls()
            servidor.login(self.config.smtp_user, self.config.smtp_password)
            servidor.sendmail(self.config.smtp_user, to, mensaje.as_string())

    def _send_via_sendgrid(self, to: str, subject: str, body: str) -> None:
        """
        Envía email usando la API de SendGrid.
        Lanza excepción si hay error.
        """
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail

        if not self.config.sendgrid_api_key:
            raise ValueError("SENDGRID_API_KEY no configurada")

        message = Mail(
            from_email=(self.config.smtp_user or "noreply@example.com", self._sender_name()),
            to_emails=to,
            subject=subject,
            plain_text_content=body,
        )

        sg = SendGridAPIClient(self.config.sendgrid_api_key)
        response = sg.send(message)

        if response.status_code not in (200, 202):
            raise RuntimeError(f"SendGrid retornó código: {response.status_code}")

    def _sender_name(self) -> str:
        """Nombre visible del remitente: AGENCY_NAME si está configurado, si no el del sistema."""
        name = getattr(getattr(self.config, "agency", None), "name", None)
        if isinstance(name, str) and name and "[" not in name:
            return name
        return "Maps Lead Finder"

    def _is_opted_out(self, email: str, db_session) -> bool:
        """Verifica si el email está en la lista de opt-out."""
        from skills.dashboard.app import OptOut

        return db_session.query(OptOut).filter_by(contact_info=email.lower()).first() is not None

    def _is_within_contact_window(self, timezone: str = DEFAULT_TIMEZONE) -> bool:
        """
        Verifica si la hora actual está dentro de la ventana de contacto permitida.
        Por defecto: 9 AM - 7 PM hora de México.
        """
        try:
            tz = pytz.timezone(timezone)
            hora_local = datetime.now(tz).hour
            return (
                self.config.contact.contact_window_start
                <= hora_local
                < self.config.contact.contact_window_end
            )
        except Exception:
            return True  # Si hay error de zona horaria, permitir el envío

    def _add_optout_footer(self, body: str, email: str) -> str:
        """Agrega instrucciones de baja al final del mensaje."""
        footer = (
            "\n\n---\n"
            "Si no deseas recibir más información de nuestra parte, "
            "responde este email con el asunto 'BAJA' y te eliminaremos "
            "inmediatamente de nuestra lista de contactos."
        )
        return body + footer
