"""
Tests del límite diario persistido en BD, del respeto a robots.txt y del manejo de SSL.
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent))


@pytest.fixture(scope="function")
def app():
    """Aplicación Flask con BD SQLite en memoria."""
    from skills.dashboard.app import create_app, db

    test_app = create_app()
    test_app.config["TESTING"] = True
    test_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


def _add_prospect(db, Prospect):
    prospect = Prospect(place_id="ChIJlimit001", name="Negocio Límite", category="store")
    db.session.add(prospect)
    db.session.commit()
    return prospect


class TestSentTodayCount:
    """sent_today_count() cuenta solo envíos exitosos de hoy y del canal pedido."""

    def test_cuenta_solo_enviados_de_hoy_por_canal(self, app):
        from skills.contact.limits import sent_today_count, start_of_today_utc
        from skills.dashboard.app import Contact, Prospect, db

        prospect = _add_prospect(db, Prospect)
        today = start_of_today_utc() + timedelta(minutes=5)
        yesterday = start_of_today_utc() - timedelta(minutes=5)
        rows = [
            ("email", "enviado", today),
            ("email", "enviado", today),
            ("email", "fallido", None),
            ("email", "enviado", yesterday),
            ("sms", "enviado", today),
        ]
        for channel, status, sent_at in rows:
            db.session.add(
                Contact(prospect_id=prospect.id, channel=channel, status=status, sent_at=sent_at)
            )
        db.session.commit()

        assert sent_today_count(db.session, "email") == 2
        assert sent_today_count(db.session, "sms") == 1
        assert sent_today_count(db.session, "whatsapp") == 0

    def test_email_sender_bloquea_al_llegar_al_limite(self, app, monkeypatch):
        from skills.contact.email_sender import EmailSender
        from skills.contact.limits import start_of_today_utc
        from skills.dashboard.app import Contact, Prospect, db

        prospect = _add_prospect(db, Prospect)
        for _ in range(2):
            db.session.add(
                Contact(
                    prospect_id=prospect.id,
                    channel="email",
                    status="enviado",
                    sent_at=start_of_today_utc() + timedelta(hours=1),
                )
            )
        db.session.commit()

        config = MagicMock()
        config.sendgrid_api_key = ""
        config.contact.max_contacts_per_day = 2
        sender = EmailSender(config)
        monkeypatch.setattr(sender, "_is_within_contact_window", lambda *a, **k: True)
        smtp = MagicMock()
        monkeypatch.setattr(sender, "_send_via_smtp", smtp)

        result = sender.send(
            to_email="nuevo@example.com",
            subject="Hola",
            body="Texto",
            prospect_id=prospect.id,
            proposal_id=None,
            db_session=db.session,
        )

        assert result["success"] is False
        assert "Límite diario" in result["error"]
        smtp.assert_not_called()

    def test_inicio_del_dia_es_anterior_a_ahora(self):
        from skills.contact.limits import start_of_today_utc

        start = start_of_today_utc()
        assert start <= datetime.utcnow()
        assert datetime.utcnow() - start < timedelta(days=1, hours=1)


class TestRobotsAndSsl:
    """La búsqueda de emails respeta robots.txt y nunca desactiva la verificación SSL."""

    def test_find_email_in_page_respeta_robots(self):
        from tools.contact_finder import _find_email_in_page

        enricher = MagicMock()
        enricher.respect_robots = True
        enricher._is_allowed_by_robots.return_value = False

        assert (
            _find_email_in_page(
                enricher, "https://negocio.example/contacto", "https://negocio.example"
            )
            is None
        )
        enricher._fetch_page.assert_not_called()

    def test_find_email_in_page_visita_si_robots_permite(self):
        from tools.contact_finder import _find_email_in_page

        enricher = MagicMock()
        enricher.respect_robots = True
        enricher._is_allowed_by_robots.return_value = True
        enricher._fetch_page.return_value = "<html>contacto@negocio.example</html>"
        enricher._extract_contacts.return_value = {"email": "contacto@negocio.example"}

        assert (
            _find_email_in_page(
                enricher, "https://negocio.example/contacto", "https://negocio.example"
            )
            == "contacto@negocio.example"
        )

    def test_fetch_page_omite_sitios_con_ssl_invalido(self, monkeypatch):
        from skills.scraping.data_enrichment import DataEnricher

        enricher = DataEnricher(timeout=1)
        calls = []

        def fake_get(url, **kwargs):
            calls.append(kwargs)
            raise requests.exceptions.SSLError("certificado inválido")

        monkeypatch.setattr(enricher.session, "get", fake_get)

        assert enricher._fetch_page("https://ssl-roto.example") is None
        assert len(calls) == 1
        assert all(kwargs.get("verify", True) is not False for kwargs in calls)
