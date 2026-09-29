"""
Módulo de scraping de Google Maps para Maps Lead Finder.
Usa la API oficial de Google Places (Nearby Search + Place Details)
para extraer datos completos de negocios locales en un radio configurable.
"""

import json
import logging
import math
import time
from collections.abc import Callable
from datetime import datetime
from typing import TYPE_CHECKING

import googlemaps

from config import ScrapingConfig
from skills.scraping.validators import ProspectCreate

if TYPE_CHECKING:
    from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# Campos a solicitar en la llamada a Place Details (controla el costo de la API)
PLACE_DETAIL_FIELDS = [
    "place_id",
    "name",
    "formatted_address",
    "formatted_phone_number",
    "international_phone_number",
    "website",
    "rating",
    "user_ratings_total",
    "opening_hours",
    "geometry",
    "type",
    "price_level",  # Nivel de precios 0-4
    "editorial_summary",  # Descripción editorial de Google
    "reviews",  # Reseñas recientes (máx 5, tomamos los 3 mejores)
]


class RateLimiter:
    """
    Limitador de velocidad simple para respetar los límites de la API de Google Maps.
    Garantiza un tiempo mínimo de espera entre llamadas consecutivas.
    """

    def __init__(self, delay_seconds: float) -> None:
        self.delay = delay_seconds
        self._last_call_time: float = 0.0

    def wait(self) -> None:
        """Espera el tiempo necesario para respetar el rate limit."""
        elapsed = time.monotonic() - self._last_call_time
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)
        self._last_call_time = time.monotonic()


class GoogleMapsScraper:
    """
    Raspador de Google Maps que usa la API de Google Places.
    Busca negocios cercanos por categoría y radio, y guarda en SQLite.
    """

    # Pausa mínima requerida por Google antes de usar next_page_token
    NEXT_PAGE_TOKEN_DELAY = 2.5

    def __init__(
        self,
        api_key: str,
        db_session: "Session",
        config: ScrapingConfig,
        status_callback: Callable | None = None,
    ) -> None:
        """
        Args:
            api_key: API Key de Google Maps / Google Places.
            db_session: Sesión de SQLAlchemy para guardar resultados.
            config: Objeto ScrapingConfig con parámetros de búsqueda.
            status_callback: Función opcional para reportar progreso al dashboard.
        """
        self.client = googlemaps.Client(key=api_key)
        self.db = db_session
        self.config = config
        self.status_callback = status_callback
        self.rate_limiter = RateLimiter(config.rate_limit_delay_seconds)

    def search_and_save(
        self,
        lat: float,
        lng: float,
        radius_km: float,
        categories: list | None = None,
    ) -> tuple[list[ProspectCreate], int, int]:
        """
        Busca negocios en el radio especificado y los guarda en la base de datos.

        Args:
            lat: Latitud del centro de búsqueda.
            lng: Longitud del centro de búsqueda.
            radius_km: Radio de búsqueda en kilómetros.
            categories: Lista de categorías a buscar. Si None, usa las configuradas.

        Returns:
            Tupla (prospectos, nuevos_guardados, duplicados_omitidos).
        """
        search_categories = categories or self.config.categories
        radius_meters = int(radius_km * 1000)

        logger.info(
            f"Iniciando búsqueda: lat={lat}, lng={lng}, radio={radius_km}km, "
            f"categorías={len(search_categories)}"
        )

        all_prospects: list[ProspectCreate] = []
        total_categories = len(search_categories)

        for i, category in enumerate(search_categories):
            logger.info(f"Buscando categoría {i+1}/{total_categories}: {category}")

            if self.status_callback:
                self.status_callback(
                    categories_done=i,
                    categories_total=total_categories,
                    current_category=category,
                )

            try:
                category_prospects = self._search_category(
                    lat=lat,
                    lng=lng,
                    radius_meters=radius_meters,
                    category=category,
                    center_lat=lat,
                    center_lng=lng,
                )
                all_prospects.extend(category_prospects)
                logger.info(f"  → {len(category_prospects)} negocios encontrados en '{category}'")

            except googlemaps.exceptions.ApiError as e:
                logger.error(f"Error de API de Google Maps para categoría '{category}': {e}")
                if self.status_callback:
                    self.status_callback(errors=[str(e)])
            except Exception as e:
                logger.error(f"Error inesperado en categoría '{category}': {e}")

        # Guardar en base de datos con deduplicación
        new_count, dup_count = self._save_prospects(all_prospects)

        if self.status_callback:
            self.status_callback(
                total_found=len(all_prospects),
                new_saved=new_count,
                categories_done=total_categories,
            )

        logger.info(
            f"Búsqueda completada: {len(all_prospects)} encontrados, "
            f"{new_count} nuevos, {dup_count} duplicados"
        )

        return all_prospects, new_count, dup_count

    def _search_category(
        self,
        lat: float,
        lng: float,
        radius_meters: int,
        category: str,
        center_lat: float,
        center_lng: float,
    ) -> list[ProspectCreate]:
        """
        Busca todos los negocios de una categoría específica con paginación.

        Google Places devuelve máx 20 resultados por página y hasta 3 páginas (60 total).
        Se usa next_page_token para obtener las páginas siguientes.
        """
        prospects: list[ProspectCreate] = []
        page_count = 0
        next_page_token = None

        while page_count < 3:  # Máximo 3 páginas (60 resultados por categoría)
            self.rate_limiter.wait()

            try:
                if next_page_token:
                    # Google requiere un delay antes de usar el page_token
                    time.sleep(self.NEXT_PAGE_TOKEN_DELAY)
                    results = self.client.places_nearby(
                        location=(lat, lng),
                        page_token=next_page_token,
                        language="es",
                    )
                else:
                    results = self.client.places_nearby(
                        location=(lat, lng),
                        radius=radius_meters,
                        type=category,
                        language="es",
                    )

                if results.get("status") == "ZERO_RESULTS":
                    break

                for place in results.get("results", []):
                    self.rate_limiter.wait()

                    try:
                        prospect = self._place_to_prospect(place, center_lat, center_lng)
                        if prospect:
                            prospects.append(prospect)
                    except Exception as e:
                        logger.warning(
                            f"Error procesando lugar {place.get('name', 'desconocido')}: {e}"
                        )

                next_page_token = results.get("next_page_token")
                page_count += 1

                if not next_page_token:
                    break

            except Exception as e:
                logger.error(f"Error en búsqueda paginada para '{category}': {e}")
                break

        return prospects

    def _place_to_prospect(
        self,
        place: dict,
        center_lat: float,
        center_lng: float,
    ) -> ProspectCreate | None:
        """
        Convierte un resultado de Google Places a un modelo ProspectCreate.
        Hace una llamada adicional a Place Details para obtener datos completos.
        """
        place_id = place.get("place_id")
        if not place_id:
            return None

        # Obtener detalles completos del lugar
        try:
            details_response = self.client.place(
                place_id=place_id,
                fields=PLACE_DETAIL_FIELDS,
                language="es",
            )
            details = details_response.get("result", {})
        except Exception as e:
            logger.warning(f"No se pudieron obtener detalles de {place_id}: {e}")
            details = place  # Usar datos básicos si falla Place Details

        # Extraer coordenadas
        geometry = details.get("geometry", place.get("geometry", {}))
        location = geometry.get("location", {})
        place_lat = location.get("lat")
        place_lng = location.get("lng")

        # Calcular distancia al centro
        distance_km = None
        if place_lat and place_lng and center_lat and center_lng:
            distance_km = self._haversine_distance(center_lat, center_lng, place_lat, place_lng)

        # Determinar categoría principal ("type" en singular es el campo correcto de la API)
        types = details.get("type", details.get("types", place.get("types", ["general"])))
        category = self._classify_category(types)

        # Extraer horario de operación
        opening_hours = details.get("opening_hours")
        hours_dict = None
        if opening_hours:
            hours_dict = {
                "weekday_text": opening_hours.get("weekday_text", []),
                "open_now": opening_hours.get("open_now"),
            }

        # Extraer nivel de precios (0=gratis, 1=económico, 2=moderado, 3=caro, 4=muy caro)
        price_level = details.get("price_level")

        # Extraer descripción editorial de Google (disponible en algunos negocios)
        editorial_raw = details.get("editorial_summary", {})
        editorial_summary = (
            editorial_raw.get("overview") if isinstance(editorial_raw, dict) else None
        )

        # Extraer fragmentos de las mejores reseñas (máx 3, solo texto significativo)
        review_snippets: list[str] = []
        for review in details.get("reviews", [])[:3]:
            text = review.get("text", "").strip()
            if text and len(text) > 20:  # Ignorar reseñas muy cortas
                # Truncar reseñas muy largas para no inflar el prompt
                review_snippets.append(text[:200])

        # Priorizar teléfono internacional
        phone = (
            details.get("international_phone_number")
            or details.get("formatted_phone_number")
            or place.get("formatted_phone_number")
        )

        try:
            return ProspectCreate(
                place_id=place_id,
                name=details.get("name", place.get("name", "")),
                category=category,
                address=details.get("formatted_address", place.get("vicinity")),
                phone=phone,
                website=details.get("website"),
                latitude=place_lat,
                longitude=place_lng,
                rating=details.get("rating", place.get("rating")),
                review_count=details.get("user_ratings_total", place.get("user_ratings_total")),
                hours=hours_dict,
                distance_km=distance_km,
                price_level=price_level,
                editorial_summary=editorial_summary,
                review_snippets=review_snippets if review_snippets else None,
            )
        except Exception as e:
            logger.warning(f"Error creando ProspectCreate para {place_id}: {e}")
            return None

    def _save_prospects(self, prospects: list[ProspectCreate]) -> tuple[int, int]:
        """
        Guarda prospectos en la base de datos con deduplicación por place_id.

        Returns:
            Tupla (nuevos_guardados, duplicados_omitidos).
        """
        from skills.dashboard.app import Prospect

        new_count = 0
        dup_count = 0

        for prospect_data in prospects:
            # Verificar si ya existe por place_id (clave única)
            existing = self.db.query(Prospect).filter_by(place_id=prospect_data.place_id).first()

            if existing:
                dup_count += 1
                continue

            # Crear nuevo registro
            new_prospect = Prospect(
                place_id=prospect_data.place_id,
                name=prospect_data.name,
                category=prospect_data.category,
                address=prospect_data.address,
                phone=prospect_data.phone,
                website=prospect_data.website,
                email=prospect_data.email,
                latitude=prospect_data.latitude,
                longitude=prospect_data.longitude,
                rating=prospect_data.rating,
                review_count=prospect_data.review_count,
                hours=(
                    json.dumps(prospect_data.hours, ensure_ascii=False)
                    if prospect_data.hours
                    else None
                ),
                distance_km=prospect_data.distance_km,
                scraped_at=datetime.utcnow(),
                price_level=prospect_data.price_level,
                editorial_summary=prospect_data.editorial_summary,
                review_snippets=(
                    json.dumps(prospect_data.review_snippets, ensure_ascii=False)
                    if prospect_data.review_snippets
                    else None
                ),
            )

            self.db.add(new_prospect)
            new_count += 1

        try:
            self.db.commit()
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error al guardar prospectos en la BD: {e}")
            raise

        return new_count, dup_count

    @staticmethod
    def _haversine_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
        """
        Calcula la distancia en kilómetros entre dos puntos GPS
        usando la fórmula de Haversine.
        """
        R = 6371.0  # Radio de la Tierra en km

        phi1 = math.radians(lat1)
        phi2 = math.radians(lat2)
        delta_phi = math.radians(lat2 - lat1)
        delta_lambda = math.radians(lng2 - lng1)

        a = (
            math.sin(delta_phi / 2) ** 2
            + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
        )
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return round(R * c, 3)

    @staticmethod
    def _classify_category(types: list[str]) -> str:
        """
        Mapea los tipos de Google Places a las categorías internas del sistema.
        Si no hay coincidencia directa, retorna 'general'.
        """
        # Mapeo de tipos de Google a categorías del sistema (orden de prioridad)
        type_mapping = {
            "restaurant": "restaurant",
            "food": "restaurant",
            "meal_takeaway": "restaurant",
            "meal_delivery": "restaurant",
            "cafe": "restaurant",
            "bar": "restaurant",
            "bakery": "restaurant",
            "gym": "gym",
            "health": "gym",
            "beauty_salon": "beauty_salon",
            "hair_care": "beauty_salon",
            "spa": "beauty_salon",
            "doctor": "doctor",
            "hospital": "doctor",
            "physiotherapist": "doctor",
            "dentist": "dentist",
            "lawyer": "lawyer",
            "legal": "lawyer",
            "accounting": "accounting",
            "finance": "accounting",
            "real_estate_agency": "real_estate_agency",
            "car_dealer": "car_dealer",
            "car_repair": "car_dealer",
            "hotel": "hotel",
            "lodging": "hotel",
            "veterinary_care": "veterinary_care",
            "pharmacy": "pharmacy",
            "drugstore": "pharmacy",
            "school": "school",
            "university": "school",
            "secondary_school": "school",
            "primary_school": "school",
            "store": "store",
            "clothing_store": "store",
            "electronics_store": "store",
            "furniture_store": "store",
            "home_goods_store": "store",
            "grocery_or_supermarket": "store",
            "supermarket": "store",
            "convenience_store": "store",
        }

        for place_type in types:
            if place_type in type_mapping:
                return type_mapping[place_type]

        return "general"
