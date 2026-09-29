"""
Límite diario de contactos compartido por todos los canales de envío.

El conteo se hace sobre la tabla ``contacts`` de la base de datos, así que el límite
se respeta aunque cada envío cree un emisor nuevo o se ejecuten varios procesos
(CLI y dashboard) el mismo día.
"""

from datetime import datetime, time
from typing import TYPE_CHECKING

import pytz

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

DEFAULT_TIMEZONE = "America/Mexico_City"


def start_of_today_utc(timezone: str = DEFAULT_TIMEZONE) -> datetime:
    """
    Devuelve la medianoche de hoy en la zona horaria indicada, convertida a UTC naive.

    ``Contact.sent_at`` se guarda con ``datetime.utcnow()`` (UTC sin tzinfo), por eso el
    límite inferior del día se expresa igual para poder compararlo en la consulta.

    Args:
        timezone: Zona horaria IANA que define qué es "hoy" (por defecto, Ciudad de México).

    Returns:
        Fecha y hora UTC sin tzinfo correspondiente a las 00:00 locales de hoy.
    """
    tz = pytz.timezone(timezone)
    today_local = datetime.now(tz).date()
    midnight_local = tz.localize(datetime.combine(today_local, time.min))
    return midnight_local.astimezone(pytz.utc).replace(tzinfo=None)


def sent_today_count(db_session: "Session", channel: str, timezone: str = DEFAULT_TIMEZONE) -> int:
    """
    Cuenta los envíos exitosos de hoy por un canal.

    Args:
        db_session: Sesión de SQLAlchemy.
        channel: Canal a contar ("email", "sms" o "whatsapp").
        timezone: Zona horaria que define el inicio del día.

    Returns:
        Número de registros ``Contact`` con ``status == "enviado"`` en ese canal desde la
        medianoche local de hoy.
    """
    from skills.dashboard.app import Contact

    return (
        db_session.query(Contact)
        .filter(
            Contact.channel == channel,
            Contact.status == "enviado",
            Contact.sent_at >= start_of_today_utc(timezone),
        )
        .count()
    )
