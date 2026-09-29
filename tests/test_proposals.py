"""
Tests para el módulo de generación de propuestas de Maps Lead Finder.
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# Ruta al catálogo de servicios
CATALOG_PATH = Path(__file__).parent.parent / "config" / "services_catalog.yaml"


# ─────────────────────────────────────────────
# Tests de ServiceCatalog
# ─────────────────────────────────────────────


class TestServiceCatalog:
    """Tests para el catálogo de servicios de IA."""

    @pytest.fixture
    def catalog(self):
        """Carga el catálogo real desde el YAML."""
        from skills.proposals.service_catalog import ServiceCatalog

        return ServiceCatalog(CATALOG_PATH)

    def test_carga_servicios(self, catalog):
        """Verifica que el catálogo carga servicios."""
        assert len(catalog._services) > 0

    def test_servicios_tienen_campos_requeridos(self, catalog):
        """Cada servicio debe tener name y short_description."""
        for svc_id, svc in catalog._services.items():
            assert "name" in svc, f"Servicio {svc_id} sin 'name'"
            assert "short_description" in svc, f"Servicio {svc_id} sin 'short_description'"

    def test_get_services_for_restaurante(self, catalog):
        """Retorna servicios relevantes para restaurantes."""
        services = catalog.get_services_for_category("restaurant", count=3)
        assert len(services) > 0
        assert len(services) <= 3

    def test_get_services_retorna_lista_de_dicts(self, catalog):
        """get_services_for_category() retorna lista de dicts."""
        services = catalog.get_services_for_category("gym", count=3)
        assert isinstance(services, list)
        for svc in services:
            assert isinstance(svc, dict)

    def test_get_services_for_categoria_desconocida(self, catalog):
        """Retorna servicios para categoría desconocida (score 1 para todos)."""
        services = catalog.get_services_for_category("categoria_inexistente_xyz", count=3)
        assert isinstance(services, list)

    def test_format_for_prompt_retorna_texto(self, catalog):
        """format_for_prompt() retorna texto no vacío."""
        services = catalog.get_services_for_category("restaurant", count=3)
        if services:
            text = catalog.format_for_prompt(services)
            assert isinstance(text, str)
            assert len(text) > 0

    def test_servicios_ids_formato_correcto(self, catalog):
        """Los IDs de servicios deben tener formato S01-S14."""
        for svc_id in catalog._services.keys():
            assert svc_id.startswith("S"), f"ID incorrecto: {svc_id}"


# ─────────────────────────────────────────────
# Tests de ProposalGenerator
# ─────────────────────────────────────────────


class TestProposalGenerator:
    """Tests para el generador de propuestas con IA."""

    @pytest.fixture
    def mock_proposals_config(self):
        """ProposalsConfig mock."""
        cfg = MagicMock()
        cfg.model = "claude-haiku-4-5-20251001"
        cfg.max_tokens = 400
        cfg.max_words = 200
        cfg.min_words = 150
        cfg.services_per_proposal = 3
        return cfg

    @pytest.fixture
    def mock_agency(self):
        """AgencyContactInfo mock."""
        j = MagicMock()
        j.phone = "[TELEFONO_AGENCIA]"
        j.email = "[EMAIL_AGENCIA]"
        j.facebook = ""
        j.instagram = ""
        j.linkedin = ""
        return j

    @pytest.fixture
    def mock_catalog(self):
        """ServiceCatalog mock."""
        cat = MagicMock()
        cat.get_services_for_category.return_value = [
            {"id": "S01", "name": "Chatbot IA", "short_description": "Bot de respuestas"}
        ]
        cat.format_for_prompt.return_value = "• S01 - Chatbot IA: Bot de respuestas"
        cat.get_service_ids.return_value = ["S01"]
        return cat

    @pytest.fixture
    def sample_prospect_orm(self):
        """Objeto ORM mock de un prospecto."""
        p = MagicMock()
        p.name = "Restaurante La Prueba"
        p.category = "restaurant"
        p.address = "Av. Reforma 123, CDMX"
        p.rating = 4.2
        p.review_count = 87
        p.id = 1
        return p

    def test_truncate_respeta_limite(self, mock_proposals_config, mock_agency, mock_catalog):
        """_truncate_to_limit() debe respetar el límite de palabras."""
        from skills.proposals.generator import ProposalGenerator

        gen = ProposalGenerator.__new__(ProposalGenerator)
        gen.config = mock_proposals_config
        gen.agency = mock_agency
        gen.catalog = mock_catalog

        texto_largo = " ".join(["palabra"] * 250)
        resultado = gen._truncate_to_limit(texto_largo, max_words=200)
        palabras = resultado.split()
        assert len(palabras) <= 200

    def test_truncate_texto_corto_sin_cambios(
        self, mock_proposals_config, mock_agency, mock_catalog
    ):
        """_truncate_to_limit() no modifica texto dentro del límite."""
        from skills.proposals.generator import ProposalGenerator

        gen = ProposalGenerator.__new__(ProposalGenerator)
        gen.config = mock_proposals_config

        texto_corto = "Esta es una propuesta corta con pocas palabras."
        resultado = gen._truncate_to_limit(texto_corto, max_words=200)
        assert resultado == texto_corto

    @patch("skills.proposals.generator.anthropic")
    def test_generate_llama_api_y_retorna_tupla(
        self, mock_anthropic, mock_proposals_config, mock_agency, mock_catalog, sample_prospect_orm
    ):
        """generate() llama a la API y retorna tupla (email, whatsapp, servicios, palabras)."""
        mock_proposals_config.temperature = 0.7
        texto_generado = " ".join(["Propuesta"] * 170)
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text=texto_generado)]
        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_response
        mock_anthropic.Anthropic.return_value = mock_client

        from skills.proposals.generator import ProposalGenerator

        gen = ProposalGenerator(
            api_key="sk-ant-test",
            config=mock_proposals_config,
            catalog=mock_catalog,
            agency=mock_agency,
        )
        result = gen.generate(sample_prospect_orm)

        assert isinstance(result, tuple)
        assert len(result) == 4
        email_text, whatsapp_text, servicios, word_count = result
        assert isinstance(email_text, str)
        assert isinstance(whatsapp_text, str)
        assert isinstance(servicios, list)
        assert isinstance(word_count, int)

    @patch("skills.proposals.generator.anthropic")
    def test_generate_levanta_error_api(
        self, mock_anthropic, mock_proposals_config, mock_agency, mock_catalog, sample_prospect_orm
    ):
        """generate() levanta RuntimeError en errores de API."""
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = Exception("API Error")
        mock_anthropic.Anthropic.return_value = mock_client

        from skills.proposals.generator import ProposalGenerator

        gen = ProposalGenerator(
            api_key="sk-ant-test",
            config=mock_proposals_config,
            catalog=mock_catalog,
            agency=mock_agency,
        )
        with pytest.raises((RuntimeError, Exception)):
            gen.generate(sample_prospect_orm)

    def test_format_contact_info_con_placeholders(
        self, mock_proposals_config, mock_agency, mock_catalog
    ):
        """_format_contact_info() incluye datos de la agencia (o placeholders)."""
        from skills.proposals.generator import ProposalGenerator

        gen = ProposalGenerator.__new__(ProposalGenerator)
        gen.agency = mock_agency
        gen.config = mock_proposals_config

        contacto = gen._format_contact_info()
        assert isinstance(contacto, str)
        assert len(contacto) > 0


# ─────────────────────────────────────────────
# Tests de templates
# ─────────────────────────────────────────────


class TestProposalTemplates:
    """Tests para las plantillas de propuestas."""

    @pytest.mark.parametrize(
        "categoria",
        [
            "restaurante",
            "tienda_retail",
            "consultorio",
            "gimnasio",
            "salon_belleza",
            "generico",
        ],
    )
    def test_template_existe(self, categoria):
        """Verifica que cada plantilla de categoría existe."""
        template_path = (
            Path(__file__).parent.parent / "skills" / "proposals" / "templates" / f"{categoria}.md"
        )
        assert template_path.exists(), f"Plantilla no encontrada: {template_path}"

    @pytest.mark.parametrize(
        "categoria",
        [
            "restaurante",
            "tienda_retail",
            "consultorio",
            "gimnasio",
            "salon_belleza",
            "generico",
        ],
    )
    def test_template_tiene_frontmatter(self, categoria):
        """Verifica que las plantillas tienen frontmatter YAML."""
        template_path = (
            Path(__file__).parent.parent / "skills" / "proposals" / "templates" / f"{categoria}.md"
        )
        content = template_path.read_text(encoding="utf-8")
        assert content.startswith("---"), f"Sin frontmatter YAML: {categoria}"
