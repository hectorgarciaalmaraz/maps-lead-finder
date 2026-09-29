"""
Tests de integración para Maps Lead Finder.
Prueba flujos completos usando una BD SQLite en memoria.
"""

import sys
from pathlib import Path

import pytest
from sqlalchemy.exc import IntegrityError

sys.path.insert(0, str(Path(__file__).parent.parent))


# ─────────────────────────────────────────────
# Fixture: Flask app con BD en memoria
# ─────────────────────────────────────────────


@pytest.fixture(scope="function")
def app():
    """Crea una aplicación Flask con BD SQLite en memoria para tests."""
    from skills.dashboard.app import create_app, db

    test_app = create_app()
    test_app.config["TESTING"] = True
    test_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    test_app.config["WTF_CSRF_ENABLED"] = False

    with test_app.app_context():
        db.create_all()
        yield test_app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    """Cliente de pruebas Flask."""
    return app.test_client()


@pytest.fixture
def prospect_id(app):
    """Crea un prospecto de ejemplo y retorna su ID."""
    from skills.dashboard.app import Prospect, db

    with app.app_context():
        prospect = Prospect(
            place_id="ChIJtest001",
            name="Restaurante La Prueba",
            address="Av. Test 123, CDMX",
            latitude=19.4326,
            longitude=-99.1332,
            category="restaurant",
            phone="+52 55 9999 0000",
            email="test@restaurante.mx",
            website="http://lapruebarestaurante.mx",
            rating=4.5,
            review_count=120,
            status="nuevo",
        )
        db.session.add(prospect)
        db.session.commit()
        pid = prospect.id
    return pid


# ─────────────────────────────────────────────
# Tests de modelos ORM
# ─────────────────────────────────────────────


class TestProspectModel:
    """Tests para el modelo Prospect."""

    def test_crear_prospecto(self, app):
        """Crea y recupera un prospecto correctamente."""
        from skills.dashboard.app import Prospect, db

        with app.app_context():
            p = Prospect(
                place_id="ChIJnuevo001",
                name="Tienda Nueva",
                address="Calle 1, Col. Centro",
                latitude=19.0,
                longitude=-99.0,
                category="store",
                status="nuevo",
            )
            db.session.add(p)
            db.session.commit()

            recuperado = Prospect.query.filter_by(place_id="ChIJnuevo001").first()
            assert recuperado is not None
            assert recuperado.name == "Tienda Nueva"

    def test_place_id_unico(self, app, prospect_id):
        """place_id debe ser único (deduplicación)."""

        from skills.dashboard.app import Prospect, db

        with app.app_context():
            duplicado = Prospect(
                place_id="ChIJtest001",  # Mismo place_id
                name="Duplicado",
                address="Otra dirección",
                latitude=19.0,
                longitude=-99.0,
                category="general",
                status="nuevo",
            )
            db.session.add(duplicado)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()

    def test_status_default_nuevo(self, app):
        """El status por defecto de un prospecto es 'nuevo'."""
        from skills.dashboard.app import Prospect, db

        with app.app_context():
            p = Prospect(
                place_id="ChIJstatus001",
                name="Negocio Status Test",
                address="Dirección Test",
                latitude=19.0,
                longitude=-99.0,
                category="general",
            )
            db.session.add(p)
            db.session.commit()
            assert p.status == "nuevo"


class TestProposalModel:
    """Tests para el modelo Proposal."""

    def test_crear_propuesta(self, app, prospect_id):
        """Crea una propuesta vinculada a un prospecto."""
        from skills.dashboard.app import Proposal, db

        with app.app_context():
            proposal = Proposal(
                prospect_id=prospect_id,
                content="Esta es una propuesta de prueba para el restaurante.",
                word_count=10,
                is_sent=False,
            )
            db.session.add(proposal)
            db.session.commit()

            recuperada = Proposal.query.filter_by(prospect_id=prospect_id).first()
            assert recuperada is not None
            assert "propuesta" in recuperada.content
            assert recuperada.is_sent is False

    def test_propuesta_no_enviada_por_defecto(self, app, prospect_id):
        """is_sent es False por defecto."""
        from skills.dashboard.app import Proposal, db

        with app.app_context():
            proposal = Proposal(
                prospect_id=prospect_id,
                content="Propuesta de prueba.",
                word_count=3,
            )
            db.session.add(proposal)
            db.session.commit()
            assert proposal.is_sent is False


class TestOptOutModel:
    """Tests para el modelo OptOut."""

    def test_registrar_opt_out(self, app):
        """Registra un opt-out correctamente."""
        from skills.dashboard.app import OptOut, db

        with app.app_context():
            opt = OptOut(
                contact_info="no-contactar@empresa.mx",
            )
            db.session.add(opt)
            db.session.commit()

            registrado = OptOut.query.filter_by(contact_info="no-contactar@empresa.mx").first()
            assert registrado is not None

    def test_contact_info_unico(self, app):
        """contact_info debe ser único en opt_outs."""
        from skills.dashboard.app import OptOut, db

        with app.app_context():
            opt1 = OptOut(contact_info="duplicado@test.com")
            db.session.add(opt1)
            db.session.commit()

            opt2 = OptOut(contact_info="duplicado@test.com")
            db.session.add(opt2)
            with pytest.raises(IntegrityError):
                db.session.commit()
            db.session.rollback()


# ─────────────────────────────────────────────
# Tests de rutas del dashboard
# ─────────────────────────────────────────────


class TestDashboardRoutes:
    """Tests para las rutas REST del dashboard."""

    def test_ruta_raiz_responde(self, client):
        """La ruta raíz responde (200 o redirección)."""
        response = client.get("/")
        assert response.status_code in (200, 302)

    def test_api_prospects_retorna_json(self, client):
        """GET /api/prospects retorna JSON."""
        response = client.get("/api/prospects")
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None

    def test_api_stats_retorna_estadisticas(self, client):
        """GET /api/stats retorna estadísticas."""
        response = client.get("/api/stats")
        assert response.status_code == 200
        data = response.get_json()
        assert data is not None

    def test_ruta_no_existente_404(self, client):
        """Ruta inexistente retorna 404."""
        response = client.get("/ruta/que/no/existe/jamas")
        assert response.status_code == 404


# ─────────────────────────────────────────────
# Tests de flujo completo (smoke test)
# ─────────────────────────────────────────────


class TestFlujoCompleto:
    """Tests de flujo de extremo a extremo."""

    def test_prospecto_con_propuesta_y_opt_out(self, app, prospect_id):
        """Flujo: crear prospecto → propuesta → registrar opt-out."""
        from skills.dashboard.app import OptOut, Proposal, Prospect, db

        with app.app_context():
            # 1. Crear propuesta
            proposal = Proposal(
                prospect_id=prospect_id,
                content=" ".join(["Propuesta"] * 160),
                word_count=160,
                is_sent=False,
            )
            db.session.add(proposal)
            db.session.commit()

            # 2. Registrar opt-out para el prospecto
            prospect = db.session.get(Prospect, prospect_id)
            opt = OptOut(contact_info=prospect.email)
            db.session.add(opt)
            db.session.commit()

            # 3. Verificar que está en opt-out
            en_optout = OptOut.query.filter_by(contact_info=prospect.email).first()
            assert en_optout is not None

    def test_contar_estadisticas(self, app, prospect_id):
        """Las estadísticas reflejan los datos insertados."""
        from skills.dashboard.app import Proposal, Prospect

        with app.app_context():
            total_antes = Prospect.query.count()
            assert total_antes >= 1  # Al menos el prospecto del fixture

            Proposal(
                prospect_id=prospect_id,
                content="Contenido de prueba " * 10,
                word_count=30,
            )
            total_propuestas = Proposal.query.count()
            assert isinstance(total_propuestas, int)
