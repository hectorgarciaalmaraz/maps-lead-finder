"""
Modelos de validación Pydantic para el módulo de scraping de Google Maps.
Valida y tipifica los datos crudos de la API antes de guardarlos en la BD.
"""

from datetime import datetime

from pydantic import BaseModel, field_validator


class GooglePlacesResult(BaseModel):
    """Resultado básico de la búsqueda Nearby Search de Google Places."""

    place_id: str
    name: str
    types: list[str] = []
    geometry: dict
    vicinity: str | None = None
    rating: float | None = None
    user_ratings_total: int | None = None
    business_status: str | None = None

    @field_validator("rating")
    @classmethod
    def validar_rating(cls, v: float | None) -> float | None:
        """El rating debe estar entre 0 y 5."""
        if v is not None and not (0.0 <= v <= 5.0):
            return None
        return v


class PlaceDetails(BaseModel):
    """Detalles completos de un lugar de Google Places API."""

    place_id: str
    name: str
    formatted_address: str | None = None
    formatted_phone_number: str | None = None
    international_phone_number: str | None = None
    website: str | None = None
    rating: float | None = None
    user_ratings_total: int | None = None
    opening_hours: dict | None = None
    geometry: dict
    types: list[str] = []
    price_level: int | None = None  # 0-4: gratuito, económico, moderado, caro, muy caro
    editorial_summary: str | None = None  # Descripción de Google del negocio
    review_snippets: list[str] | None = None  # Fragmentos de las mejores reseñas

    @field_validator("website")
    @classmethod
    def validar_website(cls, v: str | None) -> str | None:
        """Normaliza la URL del sitio web."""
        if v and not v.startswith(("http://", "https://")):
            return f"https://{v}"
        return v

    @field_validator("formatted_phone_number", "international_phone_number")
    @classmethod
    def limpiar_telefono(cls, v: str | None) -> str | None:
        """Limpia el número de teléfono de caracteres no deseados."""
        if v:
            return v.strip()
        return v


class ProspectCreate(BaseModel):
    """Esquema para crear un nuevo prospecto en la base de datos."""

    place_id: str
    name: str
    category: str
    address: str | None = None
    phone: str | None = None
    website: str | None = None
    email: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    linkedin_url: str | None = None
    whatsapp: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    rating: float | None = None
    review_count: int | None = None
    hours: dict | None = None
    distance_km: float | None = None
    price_level: int | None = None  # 0-4: gratuito, económico, moderado, caro, muy caro
    editorial_summary: str | None = None  # Descripción de Google del negocio
    review_snippets: list[str] | None = None  # Fragmentos de las mejores reseñas (máx 3)

    @field_validator("email")
    @classmethod
    def validar_email(cls, v: str | None) -> str | None:
        """Valida formato básico de email."""
        if v and "@" not in v:
            return None
        return v.lower().strip() if v else None

    @field_validator("category")
    @classmethod
    def normalizar_categoria(cls, v: str) -> str:
        """Normaliza la categoría a minúsculas."""
        return v.lower().strip()


class ProspectRead(ProspectCreate):
    """Esquema para leer un prospecto de la base de datos."""

    id: int
    scraped_at: datetime | None = None
    enriched_at: datetime | None = None
    status: str = "nuevo"
    notes: str | None = None

    model_config = {"from_attributes": True}


class EnrichmentResult(BaseModel):
    """Resultado del enriquecimiento de datos de un sitio web."""

    prospect_id: int
    email: str | None = None
    facebook_url: str | None = None
    instagram_url: str | None = None
    linkedin_url: str | None = None
    whatsapp: str | None = None
    success: bool = True
    error: str | None = None

    def has_data(self) -> bool:
        """Verifica si se encontró algún dato útil."""
        return any(
            [
                self.email,
                self.facebook_url,
                self.instagram_url,
                self.linkedin_url,
                self.whatsapp,
            ]
        )
