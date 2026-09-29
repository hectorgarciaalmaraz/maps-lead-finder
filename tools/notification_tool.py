"""
Notificaciones al operador para Maps Lead Finder.
Envía alertas al creador/encargado del proyecto cuando se requiere su atención.
Nota: ningún módulo llama todavía a estas funciones.
"""

import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from config import AppConfig

logger = logging.getLogger(__name__)


def notify_creator(
    message_type: str,
    detail: str,
    urgency: str = "media",
    config: "AppConfig | None" = None,
) -> dict:
    """
    Notifica al creador/encargado del proyecto cuando se requiere su atención.

    Args:
        message_type: Tipo de notificación: 'Información faltante', 'Error', 'Decisión requerida'.
        detail: Descripción específica de lo que se necesita.
        urgency: Nivel de urgencia: 'alta', 'media', 'baja'.
        config: Objeto AppConfig. Si None, se carga desde el módulo config.

    Returns:
        Diccionario con {success, channels_used}.
    """
    if config is None:
        from config import config as app_config

        config = app_config

    if not config.creator_email:
        logger.warning("No se pudo notificar al creador: CREATOR_EMAIL no configurado")
        return {"success": False, "error": "CREATOR_EMAIL no configurado"}

    subject = f"[Maps Lead Finder] - Acción requerida: {message_type}"

    body = f"""Hola {config.creator_name},

El sistema de prospección Maps Lead Finder requiere tu atención:

TIPO: {message_type}
URGENCIA: {urgency.upper()}
FECHA: {datetime.now().strftime('%d/%m/%Y %H:%M')}

DETALLE:
{detail}

Por favor responde a este email o accede al dashboard para resolver esta situación.
Dashboard: http://localhost:5000

-- Sistema Maps Lead Finder
"""

    channels_used = []
    success = False

    # Enviar email de notificación al creador
    try:
        if config.smtp_user and config.smtp_password:
            msg = MIMEText(body, "plain", "utf-8")
            msg["Subject"] = subject
            msg["From"] = f"Maps Lead Finder <{config.smtp_user}>"
            msg["To"] = config.creator_email

            with smtplib.SMTP(config.smtp_host, config.smtp_port) as smtp:
                smtp.starttls()
                smtp.login(config.smtp_user, config.smtp_password)
                smtp.sendmail(config.smtp_user, config.creator_email, msg.as_string())

            channels_used.append("email")
            success = True
            logger.info(f"Notificación enviada al creador por email: {message_type}")
        else:
            logger.warning("SMTP no configurado, no se puede enviar notificación por email")

    except Exception as e:
        logger.error(f"Error enviando notificación por email al creador: {e}")

    # Para urgencia alta, intentar también por SMS
    if urgency == "alta" and config.creator_phone and config.twilio_account_sid:
        try:
            from twilio.rest import Client

            client = Client(config.twilio_account_sid, config.twilio_auth_token)
            sms_body = (
                f"[Maps Lead Finder] URGENTE: {message_type}. {detail[:100]}. Revisa tu email."
            )
            client.messages.create(
                body=sms_body,
                from_=config.twilio_phone_number,
                to=config.creator_phone,
            )
            channels_used.append("sms")
            logger.info("Notificación urgente enviada al creador por SMS")
        except Exception as e:
            logger.error(f"Error enviando SMS de notificación: {e}")

    # Siempre loguear la notificación
    logger.warning(f"[NOTIFICACIÓN AL CREADOR] {message_type} ({urgency}): {detail}")

    return {"success": success, "channels_used": channels_used}


def notify_missing_config(missing_fields: list) -> dict:
    """
    Notifica al creador que faltan campos de configuración.

    Args:
        missing_fields: Lista de variables de entorno o campos faltantes.

    Returns:
        Resultado de la notificación.
    """
    detail = (
        "Los siguientes campos de configuración no están establecidos:\n"
        + "\n".join(f"  - {field}" for field in missing_fields)
        + "\n\nPor favor actualiza el archivo .env con estos valores."
    )

    return notify_creator(
        message_type="Información faltante",
        detail=detail,
        urgency="media",
    )


def notify_critical_error(error_description: str, error_trace: str | None = None) -> dict:
    """
    Notifica al creador sobre un error crítico del sistema.

    Args:
        error_description: Descripción del error.
        error_trace: Stack trace opcional para diagnóstico.

    Returns:
        Resultado de la notificación.
    """
    detail = error_description
    if error_trace:
        detail += f"\n\nDetalle técnico:\n{error_trace[:500]}"

    return notify_creator(
        message_type="Error crítico del sistema",
        detail=detail,
        urgency="alta",
    )
