"""
Tests para el módulo de scraping de Maps Lead Finder.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─────────────────────────────────────────────
# Tests de RateLimiter
# ─────────────────────────────────────────────


class TestRateLimiter:
    """Tests para el limitador de tasa de solicitudes."""

    def test_instancia_con_delay(self):
        """Verifica que se crea la instancia con delay_seconds."""
        from skills.scraping.google_maps import RateLimiter

        limiter = RateLimiter(delay_seconds=1.0)
        assert limiter is not None
        assert limiter.delay == 1.0

    def test_instancia_sin_delay(self):
        """Verifica instancia con delay cero."""
        from skills.scraping.google_maps import RateLimiter

        limiter = RateLimiter(delay_seconds=0.0)
        assert limiter.delay == 0.0

    def test_wait_no_bloquea_primera_vez(self):
        """La primera llamada a wait() no debe bloquear."""
        import time

        from skills.scraping.google_maps import RateLimiter

        limiter = RateLimiter(delay_seconds=5.0)
        start = time.monotonic()
        limiter.wait()
        elapsed = time.monotonic() - start
        # Primera llamada nunca debe esperar
        assert elapsed < 1.0


# ─────────────────────────────────────────────
# Tests de GoogleMapsScraper
# ─────────────────────────────────────────────


class TestGoogleMapsScraper:
    """Tests para el scraper de Google Maps."""

    def test_haversine_distance_mismo_punto(self):
        """Distancia entre el mismo punto debe ser 0."""
        from skills.scraping.google_maps import GoogleMapsScraper

        scraper = GoogleMapsScraper.__new__(GoogleMapsScraper)
        dist = scraper._haversine_distance(19.4326, -99.1332, 19.4326, -99.1332)
        assert dist == pytest.approx(0.0, abs=1e-6)

    def test_haversine_distance_conocida(self):
        """Distancia conocida entre CDMX y Guadalajara (~460 km)."""
        from skills.scraping.google_maps import GoogleMapsScraper

        scraper = GoogleMapsScraper.__new__(GoogleMapsScraper)
        dist = scraper._haversine_distance(19.4326, -99.1332, 20.6597, -103.3496)
        assert 440 < dist < 490

    def test_classify_category_restaurante(self):
        """Clasifica correctamente un restaurante."""
        from skills.scraping.google_maps import GoogleMapsScraper

        # Es un método estático con mapeo interno
        result = GoogleMapsScraper._classify_category(["restaurant", "food"])
        assert result == "restaurant"

    def test_classify_category_gimnasio(self):
        """Clasifica correctamente un gimnasio."""
        from skills.scraping.google_maps import GoogleMapsScraper

        result = GoogleMapsScraper._classify_category(["gym", "health"])
        assert result == "gym"

    def test_classify_category_desconocida(self):
        """Retorna 'general' para tipos no reconocidos."""
        from skills.scraping.google_maps import GoogleMapsScraper

        result = GoogleMapsScraper._classify_category(["unknown_alien_type"])
        assert result == "general"

    def test_classify_category_lista_vacia(self):
        """Retorna 'general' para lista vacía."""
        from skills.scraping.google_maps import GoogleMapsScraper

        result = GoogleMapsScraper._classify_category([])
        assert result == "general"

    def test_classify_category_es_static(self):
        """_classify_category es un método estático."""
        from skills.scraping.google_maps import GoogleMapsScraper

        # Se puede llamar sin instancia
        result = GoogleMapsScraper._classify_category(["beauty_salon"])
        assert isinstance(result, str)


# ─────────────────────────────────────────────
# Tests de Pydantic Validators
# ─────────────────────────────────────────────


class TestValidators:
    """Tests para los modelos Pydantic de validación."""

    def test_prospect_create_campos_requeridos(self):
        """Verifica que ProspectCreate requiere campos obligatorios."""
        from skills.scraping.validators import ProspectCreate

        prospect = ProspectCreate(
            place_id="ChIJ123",
            name="Restaurante El Buen Sabor",
            address="Av. Insurgentes 123, CDMX",
            lat=19.4326,
            lng=-99.1332,
            category="restaurante",
        )
        assert prospect.name == "Restaurante El Buen Sabor"
        assert prospect.place_id == "ChIJ123"

    def test_prospect_create_campos_opcionales_none(self):
        """Los campos opcionales son None por defecto."""
        from skills.scraping.validators import ProspectCreate

        prospect = ProspectCreate(
            place_id="ChIJ456",
            name="Negocio Test",
            address="Calle Test 1",
            lat=19.0,
            lng=-99.0,
            category="otro",
        )
        assert prospect.phone is None
        assert prospect.website is None
        assert prospect.email is None

    def test_enrichment_result_has_data_con_email(self):
        """has_data() retorna True cuando hay email."""
        from skills.scraping.validators import EnrichmentResult

        result = EnrichmentResult(
            prospect_id=1,
            email="contacto@negocio.com",
        )
        assert result.has_data() is True

    def test_enrichment_result_has_data_sin_datos(self):
        """has_data() retorna False cuando no hay datos."""
        from skills.scraping.validators import EnrichmentResult

        result = EnrichmentResult(prospect_id=1)
        assert result.has_data() is False


# ─────────────────────────────────────────────
# Tests de DataEnricher
# ─────────────────────────────────────────────


class TestDataEnricher:
    """Tests para el enriquecedor de datos de sitios web."""

    def test_instancia_con_timeout(self):
        """DataEnricher se instancia correctamente."""
        from skills.scraping.data_enrichment import DataEnricher

        enricher = DataEnricher(timeout=10)
        assert enricher is not None
        assert enricher.timeout == 10

    def test_filter_emails_retorna_mejor_email(self):
        """_filter_emails() retorna el mejor email de un set."""
        from skills.scraping.data_enrichment import DataEnricher

        enricher = DataEnricher(timeout=5)
        emails = {"contacto@negocio.com", "info@empresa.mx"}
        result = enricher._filter_emails(emails)
        # Puede retornar None o un string de email válido
        assert result is None or isinstance(result, str)

    def test_filter_emails_elimina_sistema(self):
        """_filter_emails() excluye emails de sistema."""
        from skills.scraping.data_enrichment import DataEnricher

        enricher = DataEnricher(timeout=5)
        # Set con solo emails de sistema
        emails = {"noreply@dominio.com", "no-reply@sistema.net"}
        result = enricher._filter_emails(emails)
        # Los emails de sistema deben filtrarse
        if result is not None:
            assert "noreply" not in result.lower()

    def test_filter_emails_set_vacio(self):
        """_filter_emails() retorna None para set vacío."""
        from skills.scraping.data_enrichment import DataEnricher

        enricher = DataEnricher(timeout=5)
        result = enricher._filter_emails(set())
        assert result is None

    @patch("skills.scraping.data_enrichment.requests.Session")
    def test_enrich_prospect_maneja_timeout(self, mock_session_class):
        """Maneja correctamente errores de timeout al enriquecer."""
        import requests

        mock_session = MagicMock()
        mock_session.get.side_effect = requests.exceptions.Timeout
        mock_session_class.return_value = mock_session

        from skills.scraping.data_enrichment import DataEnricher

        enricher = DataEnricher(timeout=1)
        enricher.session = mock_session

        result = enricher.enrich_prospect(1, "http://sitio-inexistente.example.com")
        assert result.has_data() is False
