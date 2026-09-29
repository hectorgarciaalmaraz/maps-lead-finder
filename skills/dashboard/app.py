"""
Dashboard web de Maps Lead Finder.
Factory de la aplicación Flask con modelos ORM (SQLAlchemy) y todas las rutas.
Este archivo es el núcleo de la capa de datos — todos los módulos importan 'db' desde aquí.
"""

import json
import logging
import os
import secrets
import threading
from datetime import date, datetime
from pathlib import Path

import pandas as pd
from flask import Flask, jsonify, redirect, render_template, request, send_file, url_for
from flask.typing import ResponseReturnValue
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

logger = logging.getLogger(__name__)

# ─── Instancia de la base de datos (importar en otros módulos) ─────────────────
db = SQLAlchemy()

# Estado global del scraping en curso (thread-safe)
_scraping_status: dict = {
    "running": False,
    "total_found": 0,
    "new_saved": 0,
    "categories_done": 0,
    "categories_total": 0,
    "current_category": "",
    "errors": [],
    "started_at": None,
    "finished_at": None,
}
_scraping_lock = threading.Lock()


# ─── Modelos ORM ──────────────────────────────────────────────────────────────


class Prospect(db.Model):
    """Negocio local extraído de Google Maps."""

    __tablename__ = "prospects"

    id = Column(Integer, primary_key=True, autoincrement=True)
    place_id = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)
    category = Column(String(100), nullable=False, index=True)
    address = Column(Text)
    phone = Column(String(50))
    website = Column(String(500))
    email = Column(String(255))
    facebook_url = Column(String(500))
    instagram_url = Column(String(500))
    linkedin_url = Column(String(500))
    whatsapp = Column(String(50))
    latitude = Column(Float)
    longitude = Column(Float)
    rating = Column(Float)
    review_count = Column(Integer)
    hours = Column(Text)  # JSON string con horarios
    distance_km = Column(Float)
    price_level = Column(Integer)  # 0-4: gratis/económico/moderado/caro/muy caro
    editorial_summary = Column(Text)  # Descripción editorial de Google
    review_snippets = Column(Text)  # JSON array con fragmentos de reseñas (máx 3)
    scraped_at = Column(DateTime, default=datetime.utcnow)
    enriched_at = Column(DateTime)
    status = Column(String(50), default="nuevo", index=True)
    notes = Column(Text)

    # Relaciones
    proposals = relationship("Proposal", back_populates="prospect", cascade="all, delete-orphan")
    contacts = relationship("Contact", back_populates="prospect", cascade="all, delete-orphan")

    def to_dict(self) -> dict:
        """Convierte el modelo a diccionario para respuestas JSON."""
        return {
            "id": self.id,
            "place_id": self.place_id,
            "name": self.name,
            "category": self.category,
            "address": self.address,
            "phone": self.phone,
            "website": self.website,
            "email": self.email,
            "facebook_url": self.facebook_url,
            "instagram_url": self.instagram_url,
            "linkedin_url": self.linkedin_url,
            "whatsapp": self.whatsapp,
            "latitude": self.latitude,
            "longitude": self.longitude,
            "rating": self.rating,
            "review_count": self.review_count,
            "hours": json.loads(self.hours) if self.hours else None,
            "distance_km": self.distance_km,
            "price_level": self.price_level,
            "editorial_summary": self.editorial_summary,
            "review_snippets": json.loads(self.review_snippets) if self.review_snippets else None,
            "scraped_at": self.scraped_at.isoformat() if self.scraped_at else None,
            "enriched_at": self.enriched_at.isoformat() if self.enriched_at else None,
            "status": self.status,
            "notes": self.notes,
            "has_proposal": len(self.proposals) > 0,
            "proposals_count": len(self.proposals),
            "contacts_count": len(self.contacts),
        }

    def __repr__(self) -> str:
        return f"<Prospect {self.id}: {self.name} ({self.category})>"


class Proposal(db.Model):
    """Propuesta comercial generada con IA para un prospecto."""

    __tablename__ = "proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)  # Versión email (formal, 150-200 palabras)
    content_whatsapp = Column(Text)  # Versión WhatsApp (casual, 60-100 palabras)
    content_phone = Column(Text)  # Guión para llamada telefónica
    services_selected = Column(Text)  # JSON array de IDs: ["S01", "S06"]
    template_used = Column(String(100))
    word_count = Column(Integer)
    word_count_whatsapp = Column(Integer)
    generated_at = Column(DateTime, default=datetime.utcnow)
    edited_at = Column(DateTime)
    is_sent = Column(Boolean, default=False)

    # Relaciones
    prospect = relationship("Prospect", back_populates="proposals")
    contacts = relationship("Contact", back_populates="proposal")

    def to_dict(self) -> dict:
        """Serializa el registro a un diccionario apto para JSON (fechas en ISO 8601)."""
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "content": self.content,
            "content_whatsapp": self.content_whatsapp,
            "services_selected": (
                json.loads(self.services_selected) if self.services_selected else []
            ),
            "template_used": self.template_used,
            "word_count": self.word_count,
            "word_count_whatsapp": self.word_count_whatsapp,
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "edited_at": self.edited_at.isoformat() if self.edited_at else None,
            "is_sent": self.is_sent,
        }

    def __repr__(self) -> str:
        return f"<Proposal {self.id} para Prospect {self.prospect_id}>"


class Contact(db.Model):
    """Registro de cada intento de contacto realizado."""

    __tablename__ = "contacts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    prospect_id = Column(Integer, ForeignKey("prospects.id"), nullable=False, index=True)
    proposal_id = Column(Integer, ForeignKey("proposals.id"))
    channel = Column(String(50), nullable=False)  # email, sms, whatsapp, social
    recipient = Column(String(255))  # email o teléfono usado
    status = Column(String(50), default="pendiente")  # pendiente, enviado, fallido, respondido
    sent_at = Column(DateTime)
    error_message = Column(Text)
    response_received = Column(Text)
    response_at = Column(DateTime)

    # Relaciones
    prospect = relationship("Prospect", back_populates="contacts")
    proposal = relationship("Proposal", back_populates="contacts")

    def to_dict(self) -> dict:
        """Serializa el registro a un diccionario apto para JSON (fechas en ISO 8601)."""
        return {
            "id": self.id,
            "prospect_id": self.prospect_id,
            "proposal_id": self.proposal_id,
            "channel": self.channel,
            "recipient": self.recipient,
            "status": self.status,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "error_message": self.error_message,
            "response_received": self.response_received,
            "response_at": self.response_at.isoformat() if self.response_at else None,
        }


class OptOut(db.Model):
    """Registro de contactos que solicitaron no recibir más mensajes."""

    __tablename__ = "opt_outs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    contact_info = Column(String(255), unique=True, nullable=False, index=True)
    opted_out_at = Column(DateTime, default=datetime.utcnow)
    reason = Column(Text)

    def __repr__(self) -> str:
        return f"<OptOut {self.contact_info}>"


class AppConfigModel(db.Model):
    """Configuración editable en tiempo de ejecución desde el dashboard."""

    __tablename__ = "app_config"

    key = Column(String(100), primary_key=True)
    value = Column(Text)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self) -> str:
        return f"<AppConfig {self.key}={self.value}>"


# ─── Factory de la aplicación Flask ──────────────────────────────────────────


def create_app(config_override: dict | None = None) -> Flask:
    """
    Crea y configura la aplicación Flask.
    Inicializa la base de datos y registra todas las rutas del dashboard.
    """
    # Calcular ruta de templates relativa a este archivo
    templates_dir = Path(__file__).parent.parent.parent / "templates"

    app = Flask(__name__, template_folder=str(templates_dir))

    # Importar configuración del sistema
    try:
        from config import config as app_cfg

        db_path = str(app_cfg.database_path) if app_cfg else "data/prospects.db"
        secret_key = os.environ.get("FLASK_SECRET_KEY") or secrets.token_hex(32)
    except Exception:
        db_path = "data/prospects.db"
        secret_key = secrets.token_hex(32)

    # Asegurar que el directorio de datos existe
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    app.config.update(
        {
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{db_path}",
            "SQLALCHEMY_TRACK_MODIFICATIONS": False,
            "SECRET_KEY": secret_key,
            "JSON_SORT_KEYS": False,
        }
    )

    if config_override:
        app.config.update(config_override)

    # Inicializar SQLAlchemy
    db.init_app(app)

    with app.app_context():
        db.create_all()
        logger.info(f"Base de datos inicializada en: {db_path}")

    # Registrar rutas
    _register_routes(app)

    return app


# ─── Rutas del Dashboard ──────────────────────────────────────────────────────


def _register_routes(app: Flask) -> None:
    """Registra todas las rutas del dashboard web."""

    # ── Vistas HTML ─────────────────────────────────────────────────────────

    @app.route("/")
    def index() -> ResponseReturnValue:
        """Página principal - redirige al listado de prospectos."""
        return redirect(url_for("prospects_list"))

    @app.route("/prospects")
    def prospects_list() -> ResponseReturnValue:
        """Vista principal de prospectos con filtros."""
        return render_template("prospects.html")

    @app.route("/prospects/<int:prospect_id>")
    def prospect_detail(prospect_id: int) -> ResponseReturnValue:
        """Vista detallada de un prospecto."""
        prospect = db.session.get(Prospect, prospect_id)
        if not prospect:
            return render_template("404.html"), 404
        return render_template("prospect_detail.html", prospect=prospect)

    @app.route("/stats")
    def stats_view() -> ResponseReturnValue:
        """Vista de estadísticas y métricas."""
        return render_template("stats.html")

    @app.route("/config")
    def config_view() -> ResponseReturnValue:
        """Vista de configuración del sistema."""
        return render_template("config.html")

    @app.route("/search")
    def search_view() -> ResponseReturnValue:
        """Vista para iniciar una búsqueda en Google Maps."""
        return render_template("search.html")

    # ── API: Prospectos ──────────────────────────────────────────────────────

    @app.route("/api/prospects", methods=["GET"])
    def api_prospects() -> ResponseReturnValue:
        """Lista prospectos con filtros opcionales."""
        query = Prospect.query

        # Filtros
        category = request.args.get("category")
        if category:
            query = query.filter(Prospect.category == category)

        status = request.args.get("status")
        if status:
            query = query.filter(Prospect.status == status)

        min_rating = request.args.get("min_rating", type=float)
        if min_rating:
            query = query.filter(Prospect.rating >= min_rating)

        max_distance = request.args.get("max_distance", type=float)
        if max_distance:
            query = query.filter(Prospect.distance_km <= max_distance)

        search = request.args.get("search", "").strip()
        if search:
            query = query.filter(Prospect.name.ilike(f"%{search}%"))

        has_email = request.args.get("has_email")
        if has_email == "true":
            query = query.filter(Prospect.email.isnot(None), Prospect.email != "")

        # Paginación
        page = request.args.get("page", 1, type=int)
        per_page = request.args.get("per_page", 25, type=int)

        pagination = query.order_by(Prospect.scraped_at.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )

        return jsonify(
            {
                "prospects": [p.to_dict() for p in pagination.items],
                "total": pagination.total,
                "pages": pagination.pages,
                "current_page": pagination.page,
                "per_page": per_page,
            }
        )

    @app.route("/api/prospects/<int:prospect_id>", methods=["GET"])
    def api_prospect_detail(prospect_id: int) -> ResponseReturnValue:
        """Detalle completo de un prospecto."""
        prospect = db.session.get(Prospect, prospect_id)
        if not prospect:
            return jsonify({"error": "Prospecto no encontrado"}), 404
        data = prospect.to_dict()
        data["proposals"] = [p.to_dict() for p in prospect.proposals]
        data["contacts"] = [c.to_dict() for c in prospect.contacts]
        return jsonify(data)

    @app.route("/api/prospects/<int:prospect_id>", methods=["PATCH"])
    def api_update_prospect(prospect_id: int) -> ResponseReturnValue:
        """Actualiza campos de un prospecto (notas, status)."""
        prospect = db.session.get(Prospect, prospect_id)
        if not prospect:
            return jsonify({"error": "Prospecto no encontrado"}), 404

        data = request.get_json()
        allowed_fields = {"notes", "status", "email", "phone"}
        for field_name, value in data.items():
            if field_name in allowed_fields:
                setattr(prospect, field_name, value)

        db.session.commit()
        return jsonify({"success": True, "prospect": prospect.to_dict()})

    @app.route("/api/prospects/categories", methods=["GET"])
    def api_categories() -> ResponseReturnValue:
        """Lista todas las categorías únicas de prospectos."""
        from sqlalchemy import func

        categories = (
            db.session.query(Prospect.category, func.count(Prospect.id).label("count"))
            .group_by(Prospect.category)
            .all()
        )

        return jsonify([{"category": c, "count": n} for c, n in categories])

    # ── API: Propuestas ──────────────────────────────────────────────────────

    @app.route("/api/prospects/<int:prospect_id>/generate-proposal", methods=["POST"])
    def api_generate_proposal(prospect_id: int) -> ResponseReturnValue:
        """Genera una propuesta de IA para un prospecto."""
        prospect = db.session.get(Prospect, prospect_id)
        if not prospect:
            return jsonify({"error": "Prospecto no encontrado"}), 404

        try:
            from config import config as app_cfg
            from skills.proposals.generator import ProposalGenerator
            from skills.proposals.service_catalog import ServiceCatalog

            catalog = ServiceCatalog(
                Path(__file__).parent.parent.parent / "config" / "services_catalog.yaml"
            )
            generator = ProposalGenerator(
                api_key=app_cfg.anthropic_api_key,
                config=app_cfg.proposals,
                catalog=catalog,
                agency=app_cfg.agency,
            )

            content, service_ids, word_count = generator.generate(prospect)

            proposal = Proposal(
                prospect_id=prospect.id,
                content=content,
                services_selected=json.dumps(service_ids),
                template_used=prospect.category,
                word_count=word_count,
            )
            db.session.add(proposal)
            prospect.status = "propuesta_generada"
            db.session.commit()

            return jsonify({"success": True, "proposal": proposal.to_dict()})

        except Exception as e:
            logger.error(f"Error generando propuesta para prospecto {prospect_id}: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/proposals/<int:proposal_id>", methods=["PUT"])
    def api_update_proposal(proposal_id: int) -> ResponseReturnValue:
        """Actualiza el contenido de una propuesta (edición manual)."""
        proposal = db.session.get(Proposal, proposal_id)
        if not proposal:
            return jsonify({"error": "Propuesta no encontrada"}), 404

        data = request.get_json()
        if "content" in data:
            proposal.content = data["content"]
            proposal.word_count = len(data["content"].split())
            proposal.edited_at = datetime.utcnow()
            db.session.commit()

        return jsonify({"success": True, "proposal": proposal.to_dict()})

    @app.route("/api/proposals/<int:proposal_id>/send", methods=["POST"])
    def api_send_proposal(proposal_id: int) -> ResponseReturnValue:
        """Envía una propuesta por el canal especificado."""
        proposal = db.session.get(Proposal, proposal_id)
        if not proposal:
            return jsonify({"error": "Propuesta no encontrada"}), 404

        data = request.get_json()
        channel = data.get("channel", "email")

        try:
            result = _send_proposal_via_channel(proposal, channel)
            return jsonify(result)
        except Exception as e:
            logger.error(f"Error enviando propuesta {proposal_id} por {channel}: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/batch/generate", methods=["POST"])
    def api_batch_generate() -> ResponseReturnValue:
        """Genera propuestas para múltiples prospectos."""
        data = request.get_json()
        prospect_ids = data.get("prospect_ids", [])
        if not prospect_ids:
            # Si no se especifican, tomar todos sin propuesta
            prospects = Prospect.query.filter(~Prospect.proposals.any()).all()
            prospect_ids = [p.id for p in prospects]

        results = {"generated": 0, "errors": 0, "details": []}

        for pid in prospect_ids:
            try:
                # Reutilizar endpoint de generación individual
                with app.test_request_context():
                    prospect = db.session.get(Prospect, pid)
                    if prospect:
                        from config import config as app_cfg
                        from skills.proposals.generator import ProposalGenerator
                        from skills.proposals.service_catalog import ServiceCatalog

                        catalog = ServiceCatalog(
                            Path(__file__).parent.parent.parent / "config" / "services_catalog.yaml"
                        )
                        generator = ProposalGenerator(
                            api_key=app_cfg.anthropic_api_key,
                            config=app_cfg.proposals,
                            catalog=catalog,
                            agency=app_cfg.agency,
                        )
                        content, service_ids, word_count = generator.generate(prospect)
                        proposal = Proposal(
                            prospect_id=prospect.id,
                            content=content,
                            services_selected=json.dumps(service_ids),
                            template_used=prospect.category,
                            word_count=word_count,
                        )
                        db.session.add(proposal)
                        prospect.status = "propuesta_generada"
                        db.session.commit()
                        results["generated"] += 1
                        results["details"].append({"prospect_id": pid, "status": "ok"})

            except Exception as e:
                results["errors"] += 1
                results["details"].append(
                    {"prospect_id": pid, "status": "error", "message": str(e)}
                )

        return jsonify(results)

    @app.route("/api/batch/send", methods=["POST"])
    def api_batch_send() -> ResponseReturnValue:
        """Envía propuestas pendientes por lote."""
        data = request.get_json()
        channel = data.get("channel", "email")
        proposal_ids = data.get("proposal_ids", [])

        if not proposal_ids:
            proposals = Proposal.query.filter_by(is_sent=False).limit(50).all()
            proposal_ids = [p.id for p in proposals]

        results = {"sent": 0, "errors": 0, "details": []}

        for pid in proposal_ids:
            proposal = db.session.get(Proposal, pid)
            if proposal and not proposal.is_sent:
                try:
                    result = _send_proposal_via_channel(proposal, channel)
                    if result.get("success"):
                        results["sent"] += 1
                    else:
                        results["errors"] += 1
                    results["details"].append({"proposal_id": pid, **result})
                except Exception as e:
                    results["errors"] += 1
                    results["details"].append(
                        {"proposal_id": pid, "status": "error", "message": str(e)}
                    )

        return jsonify(results)

    # ── API: Estadísticas ────────────────────────────────────────────────────

    @app.route("/api/stats", methods=["GET"])
    def api_stats() -> ResponseReturnValue:
        """Estadísticas generales del sistema."""
        from sqlalchemy import func

        total_prospects = Prospect.query.count()
        total_proposals = Proposal.query.count()
        total_sent = Contact.query.filter_by(status="enviado").count()
        total_responses = Contact.query.filter_by(status="respondido").count()

        # Por categoría
        by_category = (
            db.session.query(Prospect.category, func.count(Prospect.id))
            .group_by(Prospect.category)
            .all()
        )

        # Por status
        by_status = (
            db.session.query(Prospect.status, func.count(Prospect.id))
            .group_by(Prospect.status)
            .all()
        )

        # Tasa de conversión
        conversion_rate = (total_responses / total_sent * 100) if total_sent > 0 else 0

        return jsonify(
            {
                "total_prospects": total_prospects,
                "total_proposals": total_proposals,
                "total_sent": total_sent,
                "total_responses": total_responses,
                "conversion_rate": round(conversion_rate, 2),
                "by_category": [{"category": c, "count": n} for c, n in by_category],
                "by_status": [{"status": s, "count": n} for s, n in by_status],
            }
        )

    # ── API: Exportación ─────────────────────────────────────────────────────

    @app.route("/api/export/csv", methods=["GET"])
    def api_export_csv() -> ResponseReturnValue:
        """Exporta todos los prospectos a CSV."""
        import io

        prospects = Prospect.query.all()
        data = [p.to_dict() for p in prospects]
        df = pd.DataFrame(data)
        df = df.drop(columns=["hours"], errors="ignore")

        output = io.StringIO()
        df.to_csv(output, index=False, encoding="utf-8")
        output.seek(0)

        from flask import Response

        return Response(
            output.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=prospectos.csv"},
        )

    @app.route("/api/export/excel", methods=["GET"])
    def api_export_excel() -> ResponseReturnValue:
        """Exporta todos los prospectos a Excel."""
        prospects = Prospect.query.all()
        data = [p.to_dict() for p in prospects]
        df = pd.DataFrame(data)
        df = df.drop(columns=["hours"], errors="ignore")

        # Directorio de exports
        exports_dir = Path(__file__).parent.parent.parent / "data" / "exports"
        exports_dir.mkdir(parents=True, exist_ok=True)
        filename = exports_dir / f"prospectos_{date.today().strftime('%Y%m%d')}.xlsx"

        df.to_excel(filename, index=False, sheet_name="Prospectos")
        return send_file(str(filename), as_attachment=True)

    # ── API: Configuración ───────────────────────────────────────────────────

    @app.route("/api/config", methods=["GET"])
    def api_config_get() -> ResponseReturnValue:
        """Retorna la configuración de la agencia guardada desde el dashboard (no la usan los generadores)."""
        configs = {c.key: c.value for c in AppConfigModel.query.all()}
        return jsonify(configs)

    @app.route("/api/config", methods=["PUT"])
    def api_config_put() -> ResponseReturnValue:
        """Guarda la configuración de la agencia editada en el dashboard (no la usan los generadores)."""
        data = request.get_json()
        for key, value in data.items():
            existing = db.session.get(AppConfigModel, key)
            if existing:
                existing.value = str(value)
                existing.updated_at = datetime.utcnow()
            else:
                db.session.add(AppConfigModel(key=key, value=str(value)))

        db.session.commit()
        return jsonify({"success": True})

    # ── API: Búsqueda (Scraping) ─────────────────────────────────────────────

    @app.route("/api/search", methods=["POST"])
    def api_trigger_search() -> ResponseReturnValue:
        """Inicia una búsqueda en Google Maps en background."""
        global _scraping_status

        with _scraping_lock:
            if _scraping_status["running"]:
                return jsonify({"error": "Ya hay una búsqueda en curso"}), 409

        data = request.get_json()
        lat = data.get("lat")
        lng = data.get("lng")
        radius_km = data.get("radius_km", 5.0)
        categories = data.get("categories")
        enrich = data.get("enrich", True)

        if not lat or not lng:
            return jsonify({"error": "Se requieren lat y lng"}), 400

        # Iniciar scraping en background
        thread = threading.Thread(
            target=_run_scraping_background,
            args=(app, lat, lng, radius_km, categories, enrich),
            daemon=True,
        )
        thread.start()

        return jsonify({"success": True, "message": "Búsqueda iniciada en segundo plano"})

    @app.route("/api/search/status", methods=["GET"])
    def api_search_status() -> ResponseReturnValue:
        """Retorna el estado actual del scraping en curso."""
        with _scraping_lock:
            return jsonify(dict(_scraping_status))

    # ── API: Opt-out ─────────────────────────────────────────────────────────

    @app.route("/api/optout", methods=["POST"])
    def api_optout() -> ResponseReturnValue:
        """Registra un opt-out de un contacto."""
        data = request.get_json()
        contact_info = data.get("contact_info", "").strip()
        if not contact_info:
            return jsonify({"error": "Se requiere contact_info"}), 400

        existing = db.session.get(OptOut, contact_info)
        if not existing:
            db.session.add(OptOut(contact_info=contact_info, reason=data.get("reason")))
            db.session.commit()

        return jsonify({"success": True, "message": "Opt-out registrado correctamente"})


# ─── Helpers internos ─────────────────────────────────────────────────────────


def _send_proposal_via_channel(proposal: Proposal, channel: str) -> dict:
    """Despacha el envío de una propuesta al módulo de contacto correspondiente."""
    from config import config as app_cfg

    prospect = proposal.prospect

    if channel == "email":
        if not prospect.email:
            return {"success": False, "error": "El prospecto no tiene email"}
        from skills.contact.email_sender import EmailSender

        sender = EmailSender(app_cfg)
        return sender.send(
            to_email=prospect.email,
            subject=f"Una propuesta especial para {prospect.name} – {app_cfg.agency.name}",
            body=proposal.content,
            prospect_id=prospect.id,
            proposal_id=proposal.id,
            db_session=db.session,
        )

    elif channel == "sms":
        if not prospect.phone:
            return {"success": False, "error": "El prospecto no tiene teléfono"}
        from skills.contact.sms_sender import SmsSender

        sender = SmsSender(app_cfg)
        return sender.send(
            to_phone=prospect.phone,
            message=proposal.content,
            prospect_id=prospect.id,
            proposal_id=proposal.id,
            db_session=db.session,
        )

    elif channel == "whatsapp":
        phone = prospect.whatsapp or prospect.phone
        if not phone:
            return {"success": False, "error": "El prospecto no tiene teléfono/WhatsApp"}
        from skills.contact.social_messenger import SocialMessenger

        sender = SocialMessenger(app_cfg)
        return sender.send_whatsapp(
            to_phone=phone,
            message=proposal.content,
            prospect_id=prospect.id,
            proposal_id=proposal.id,
            db_session=db.session,
        )

    else:
        return {"success": False, "error": f"Canal no soportado: {channel}"}


def _run_scraping_background(
    app: Flask,
    lat: float,
    lng: float,
    radius_km: float,
    categories: list | None,
    enrich: bool,
) -> None:
    """Ejecuta el scraping de Google Maps en un hilo de fondo."""
    global _scraping_status

    with _scraping_lock:
        _scraping_status.update(
            {
                "running": True,
                "total_found": 0,
                "new_saved": 0,
                "categories_done": 0,
                "categories_total": len(categories) if categories else 14,
                "current_category": "",
                "errors": [],
                "started_at": datetime.utcnow().isoformat(),
                "finished_at": None,
            }
        )

    with app.app_context():
        try:
            from config import config as app_cfg
            from skills.scraping.data_enrichment import DataEnricher
            from skills.scraping.google_maps import GoogleMapsScraper

            scraper = GoogleMapsScraper(
                api_key=app_cfg.google_maps_api_key,
                db_session=db.session,
                config=app_cfg.scraping,
                status_callback=_update_scraping_status,
            )

            prospects, new_count, dup_count = scraper.search_and_save(
                lat=lat, lng=lng, radius_km=radius_km, categories=categories
            )

            if enrich:
                enricher = DataEnricher(timeout=app_cfg.scraping.enrich_timeout_seconds)
                to_enrich = (
                    Prospect.query.filter(
                        Prospect.website.isnot(None),
                        Prospect.enriched_at.is_(None),
                    )
                    .limit(50)
                    .all()
                )

                for prospect in to_enrich:
                    try:
                        enriched = enricher.enrich_prospect(prospect.id, prospect.website)
                        for field_name, value in enriched.items():
                            if value and not getattr(prospect, field_name):
                                setattr(prospect, field_name, value)
                        prospect.enriched_at = datetime.utcnow()
                        db.session.commit()
                    except Exception as e:
                        logger.warning(f"Error enriqueciendo prospecto {prospect.id}: {e}")

        except Exception as e:
            logger.error(f"Error en scraping background: {e}")
            with _scraping_lock:
                _scraping_status["errors"].append(str(e))

        finally:
            with _scraping_lock:
                _scraping_status["running"] = False
                _scraping_status["finished_at"] = datetime.utcnow().isoformat()


def _update_scraping_status(**kwargs) -> None:
    """Callback para actualizar el estado del scraping desde el scraper."""
    with _scraping_lock:
        _scraping_status.update(kwargs)
