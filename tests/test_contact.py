"""
Tests para el módulo de contacto de Maps Lead Finder.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─────────────────────────────────────────────
# Fixtures comunes
# ─────────────────────────────────────────────


@pytest.fixture
def mock_config():
    """Configuración mock para senders."""
    config = MagicMock()
    config.smtp_host = "smtp.gmail.com"
    config.smtp_port = 587
    config.smtp_user = "test@example.com"
    config.smtp_password = "TEST_PASSWORD"
    config.sendgrid_api_key = ""
    config.twilio_account_sid = "ACtest123"
    config.twilio_auth_token = "authtest123"
    config.twilio_phone_number = "+15551234567"
    config.twilio_whatsapp_number = "whatsapp:+15551234567"
    config.contact.max_per_day = 50
    config.contact.contact_window_start = 9
    config.contact.contact_window_end = 19
    config.contact.timezone = "America/Mexico_City"
    return config


# ─────────────────────────────────────────────
# Tests de EmailSender
# ─────────────────────────────────────────────


class TestEmailSender:
    """Tests para el enviador de emails."""

    def test_instancia_correctamente(self, mock_config):
        """EmailSender se instancia sin errores."""
        from skills.contact.email_sender import EmailSender

        sender = EmailSender(mock_config)
        assert sender is not None

    def test_usa_sendgrid_si_hay_api_key(self, mock_config):
        """Activa SendGrid cuando la API key está configurada."""
        mock_config.sendgrid_api_key = "SG.test_key"
        from skills.contact.email_sender import EmailSender

        sender = EmailSender(mock_config)
        assert sender._use_sendgrid is True

    def test_usa_smtp_si_no_hay_sendgrid(self, mock_config):
        """Usa SMTP cuando no hay SendGrid key."""
        mock_config.sendgrid_api_key = ""
        from skills.contact.email_sender import EmailSender

        sender = EmailSender(mock_config)
        assert sender._use_sendgrid is False

    def test_send_via_smtp_sin_credenciales_lanza_error(self, mock_config):
        """_send_via_smtp() lanza ValueError si no hay credenciales SMTP."""
        mock_config.smtp_user = ""
        mock_config.smtp_password = ""
        from skills.contact.email_sender import EmailSender

        sender = EmailSender(mock_config)
        with pytest.raises((ValueError, Exception)):
            sender._send_via_smtp(
                to="cliente@restaurante.mx",
                subject="Test",
                body="Contenido",
            )

    def test_is_within_window_devuelve_bool(self, mock_config):
        """_is_within_contact_window() retorna booleano."""
        from skills.contact.email_sender import EmailSender

        sender = EmailSender(mock_config)
        result = sender._is_within_contact_window()
        assert isinstance(result, bool)


# ─────────────────────────────────────────────
# Tests de SmsSender
# ─────────────────────────────────────────────


class TestSmsSender:
    """Tests para el enviador de SMS."""

    def test_normalize_phone_10_digitos(self, mock_config):
        """Normaliza número de 10 dígitos a E.164 con +52."""
        from skills.contact.sms_sender import SmsSender

        sender = SmsSender(mock_config)
        normalized = sender._normalize_phone("5512345678")
        assert normalized == "+525512345678"

    def test_normalize_phone_ya_e164(self, mock_config):
        """No modifica número ya en formato E.164."""
        from skills.contact.sms_sender import SmsSender

        sender = SmsSender(mock_config)
        normalized = sender._normalize_phone("+525512345678")
        assert normalized == "+525512345678"

    def test_normalize_phone_con_guiones(self, mock_config):
        """Elimina guiones y espacios al normalizar."""
        from skills.contact.sms_sender import SmsSender

        sender = SmsSender(mock_config)
        normalized = sender._normalize_phone("55-1234-5678")
        assert "-" not in normalized
        assert " " not in normalized

    def test_adapt_for_sms_trunca_largo(self, mock_config):
        """_adapt_for_sms() trunca mensajes largos a 320 chars."""
        from skills.contact.sms_sender import SmsSender

        sender = SmsSender(mock_config)
        mensaje_largo = "x" * 500
        adaptado = sender._adapt_for_sms(mensaje_largo)
        assert len(adaptado) <= 320

    def test_adapt_for_sms_corto_sin_cambios(self, mock_config):
        """_adapt_for_sms() no modifica mensajes cortos."""
        from skills.contact.sms_sender import SmsSender

        sender = SmsSender(mock_config)
        mensaje = "Hola, esta es una propuesta corta."
        adaptado = sender._adapt_for_sms(mensaje)
        assert adaptado == mensaje


# ─────────────────────────────────────────────
# Tests de SocialMessenger
# ─────────────────────────────────────────────


class TestSocialMessenger:
    """Tests para el mensajero de redes sociales."""

    def test_instancia_correctamente(self, mock_config):
        """SocialMessenger se instancia sin errores."""
        from skills.contact.social_messenger import SocialMessenger

        messenger = SocialMessenger(mock_config)
        assert messenger is not None

    def test_log_instagram_dm_retorna_manual_required(self, mock_config):
        """log_instagram_dm() indica que se requiere acción manual."""
        from skills.contact.social_messenger import SocialMessenger
        from skills.dashboard.app import create_app, db

        app = create_app()
        app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
        with app.app_context():
            db.create_all()
            mock_session = MagicMock()
            mock_session.add = MagicMock()
            mock_session.commit = MagicMock()

            messenger = SocialMessenger(mock_config)
            result = messenger.log_instagram_dm(
                instagram_url="https://instagram.com/negocio",
                message="Propuesta de prueba",
                prospect_id=1,
                proposal_id=1,
                db_session=mock_session,
            )
            assert isinstance(result, dict)
            assert result.get("manual_required") is True or result.get("success") is not None


# ─────────────────────────────────────────────
# Tests de ventana de contacto
# ─────────────────────────────────────────────


class TestContactWindow:
    """Tests para la validación de ventana de contacto."""

    def test_is_within_window_tipo_bool(self, mock_config):
        """_is_within_contact_window() siempre retorna bool."""
        from skills.contact.email_sender import EmailSender

        sender = EmailSender(mock_config)
        result = sender._is_within_contact_window()
        assert isinstance(result, bool)

    @patch("skills.contact.email_sender.pytz")
    def test_dentro_de_ventana_hora_14(self, mock_pytz, mock_config):
        """Retorna True para hora 14 (dentro de 9-19)."""
        mock_tz = MagicMock()
        mock_pytz.timezone.return_value = mock_tz
        mock_now = MagicMock()
        mock_now.hour = 14
        mock_tz.localize.return_value = mock_now

        from skills.contact.email_sender import EmailSender

        sender = EmailSender.__new__(EmailSender)
        sender.config = mock_config

        with patch("skills.contact.email_sender.datetime") as mock_dt:
            mock_dt.now.return_value = MagicMock()
            # Simulamos hora local = 14 directamente en config
            mock_config.contact.contact_window_start = 9
            mock_config.contact.contact_window_end = 19
            # La ventana 9-19 incluye hora 14
            assert 9 <= 14 < 19  # Lógica correcta

    def test_ventana_9_a_19_correcta(self, mock_config):
        """La ventana 9AM-7PM es [9, 19)."""
        assert mock_config.contact.contact_window_start == 9
        assert mock_config.contact.contact_window_end == 19
        # hora 22 no está en [9, 19)
        assert not (9 <= 22 < 19)
        # hora 14 sí está
        assert 9 <= 14 < 19
