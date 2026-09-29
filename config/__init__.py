"""
Módulo de configuración centralizada para Maps Lead Finder.
Carga variables de entorno desde .env y configuración desde settings.yaml.
Todos los módulos del sistema importan el objeto 'config' desde aquí.
"""

import os
from dataclasses import dataclass
from pathlib import Path

import yaml
from dotenv import load_dotenv

# ─── Rutas del proyecto ───────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).parent.parent
SETTINGS_FILE: Path = PROJECT_ROOT / "config" / "settings.yaml"
SERVICES_FILE: Path = PROJECT_ROOT / "config" / "services_catalog.yaml"

# Buscar .env: primero en config/, luego en la raíz
_env_candidates = [
    PROJECT_ROOT / "config" / ".env",
    PROJECT_ROOT / ".env",
]
ENV_FILE: Path = next((p for p in _env_candidates if p.exists()), _env_candidates[0])

if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
else:
    load_dotenv(PROJECT_ROOT / "config" / ".env.example")


# ─── Dataclasses de configuración ─────────────────────────────────────────────


@dataclass
class ScrapingConfig:
    """Configuración del módulo de scraping de Google Maps."""

    default_radius_km: float
    rate_limit_delay_seconds: float
    max_results_per_category: int
    enrich_websites: bool
    enrich_timeout_seconds: int
    categories: list


@dataclass
class ProposalsConfig:
    """Configuración del generador de propuestas con IA."""

    model: str
    max_tokens: int
    min_words: int
    max_words: int
    services_per_proposal: int
    temperature: float


@dataclass
class ContactConfig:
    """Configuración del sistema de contacto automatizado."""

    max_contacts_per_day: int
    contact_window_start: int
    contact_window_end: int
    channels_priority: list
    retry_failed_after_hours: int


@dataclass
class AgencyContactInfo:
    """Nombre y datos de contacto de la agencia que envía las propuestas."""

    phone: str
    email: str
    website: str
    facebook: str
    instagram: str
    linkedin: str
    name: str = "[NOMBRE_AGENCIA]"


@dataclass
class AppConfig:
    """Configuración completa de la aplicación."""

    # APIs externas
    google_maps_api_key: str
    anthropic_api_key: str

    # Identidad de la agencia (nombre y datos de contacto usados en las propuestas)
    agency: AgencyContactInfo

    # Datos del creador/encargado para notificaciones
    creator_name: str
    creator_phone: str
    creator_email: str
    creator_preferred_contact: str

    # Configuración SMTP
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str

    # SendGrid (opcional)
    sendgrid_api_key: str | None

    # Twilio
    twilio_account_sid: str
    twilio_auth_token: str
    twilio_phone_number: str

    # Sub-configuraciones desde YAML
    scraping: ScrapingConfig
    proposals: ProposalsConfig
    contact: ContactConfig

    # Base de datos
    database_path: Path

    # Geo - valores por defecto
    default_center_lat: float
    default_center_lng: float


def _get_env(key: str, default: str | None = None, required: bool = False) -> str | None:
    """
    Obtiene una variable de entorno.
    Si es requerida y no existe, lanza ValueError con mensaje descriptivo.
    """
    value = os.environ.get(key, default)
    if required and not value:
        raise ValueError(
            f"\n[Maps Lead Finder] Variable de entorno requerida no encontrada: {key}\n"
            f"Por favor copia config/.env.example a .env y completa los valores.\n"
            f"Ruta esperada: {ENV_FILE}"
        )
    return value


def load_config() -> AppConfig:
    """
    Carga y valida la configuración completa de la aplicación.
    Lee .env para secretos y settings.yaml para parámetros no sensibles.
    """
    # Cargar configuración YAML
    with open(SETTINGS_FILE, encoding="utf-8") as f:
        settings = yaml.safe_load(f)

    scraping_cfg = settings["scraping"]
    proposals_cfg = settings["proposals"]
    contact_cfg = settings["contact"]
    db_cfg = settings["database"]

    # Construir el objeto de configuración
    return AppConfig(
        # APIs (placeholders aceptados, no required=True para facilitar onboarding)
        google_maps_api_key=_get_env("GOOGLE_MAPS_API_KEY", "YOUR_GOOGLE_MAPS_API_KEY"),
        anthropic_api_key=_get_env("ANTHROPIC_API_KEY", "YOUR_ANTHROPIC_API_KEY"),
        # Identidad de la agencia
        agency=AgencyContactInfo(
            phone=_get_env("AGENCY_PHONE", "[TELEFONO_AGENCIA]"),
            email=_get_env("AGENCY_EMAIL", "[EMAIL_AGENCIA]"),
            website=_get_env("AGENCY_WEBSITE", "[WEB_AGENCIA]"),
            facebook=_get_env("AGENCY_FACEBOOK", "[FACEBOOK_AGENCIA]"),
            instagram=_get_env("AGENCY_INSTAGRAM", "[INSTAGRAM_AGENCIA]"),
            linkedin=_get_env("AGENCY_LINKEDIN", "[LINKEDIN_AGENCIA]"),
            name=_get_env("AGENCY_NAME", "[NOMBRE_AGENCIA]"),
        ),
        # Datos del creador
        creator_name=_get_env("CREATOR_NAME", "Encargado"),
        creator_phone=_get_env("CREATOR_PHONE", ""),
        creator_email=_get_env("CREATOR_EMAIL", ""),
        creator_preferred_contact=_get_env("CREATOR_PREFERRED_CONTACT", "email"),
        # SMTP
        smtp_host=_get_env("SMTP_HOST", "smtp.gmail.com"),
        smtp_port=int(_get_env("SMTP_PORT", "587")),
        smtp_user=_get_env("SMTP_USER", ""),
        smtp_password=_get_env("SMTP_PASSWORD", ""),
        # SendGrid (opcional)
        sendgrid_api_key=_get_env("SENDGRID_API_KEY") or None,
        # Twilio
        twilio_account_sid=_get_env("TWILIO_ACCOUNT_SID", ""),
        twilio_auth_token=_get_env("TWILIO_AUTH_TOKEN", ""),
        twilio_phone_number=_get_env("TWILIO_PHONE_NUMBER", ""),
        # Sub-configuraciones YAML
        scraping=ScrapingConfig(
            default_radius_km=scraping_cfg["default_radius_km"],
            rate_limit_delay_seconds=scraping_cfg["rate_limit_delay_seconds"],
            max_results_per_category=scraping_cfg["max_results_per_category"],
            enrich_websites=scraping_cfg["enrich_websites"],
            enrich_timeout_seconds=scraping_cfg["enrich_timeout_seconds"],
            categories=scraping_cfg["categories"],
        ),
        proposals=ProposalsConfig(
            model=proposals_cfg["model"],
            max_tokens=proposals_cfg["max_tokens"],
            min_words=proposals_cfg["min_words"],
            max_words=proposals_cfg["max_words"],
            services_per_proposal=proposals_cfg["services_per_proposal"],
            temperature=proposals_cfg["temperature"],
        ),
        contact=ContactConfig(
            max_contacts_per_day=contact_cfg["max_contacts_per_day"],
            contact_window_start=contact_cfg["contact_window_start"],
            contact_window_end=contact_cfg["contact_window_end"],
            channels_priority=contact_cfg["channels_priority"],
            retry_failed_after_hours=contact_cfg["retry_failed_after_hours"],
        ),
        # Base de datos
        database_path=PROJECT_ROOT / db_cfg["path"],
        # Geo defaults
        default_center_lat=float(_get_env("DEFAULT_CENTER_LAT", "19.4326")),
        default_center_lng=float(_get_env("DEFAULT_CENTER_LNG", "-99.1332")),
    )


def setup_logging(config: "AppConfig") -> None:
    """Configura el sistema de logging con archivo rotativo."""
    import logging.handlers

    log_cfg = yaml.safe_load(open(SETTINGS_FILE, encoding="utf-8"))["logging"]
    log_file = PROJECT_ROOT / log_cfg["file"]
    log_file.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter(log_cfg["format"])

    # Handler de archivo rotativo
    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=log_cfg["max_bytes"],
        backupCount=log_cfg["backup_count"],
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    # Handler de consola
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    # Configurar logger raíz
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_cfg["level"]))
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)


# ─── Singleton de configuración (importar desde aquí en todos los módulos) ─────
try:
    config = load_config()
except Exception as e:
    # En caso de error de configuración, usar valores por defecto mínimos
    import warnings

    warnings.warn(
        f"[Maps Lead Finder] Error al cargar configuración: {e}\nUsando valores por defecto.",
        stacklevel=2,
    )
    config = None
