"""
Catálogo de servicios de IA que ofrece la agencia (config/services_catalog.yaml).
Carga los 17 servicios desde services_catalog.yaml y provee
selección inteligente según el tipo de negocio prospecto.
"""

import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class ServiceCatalog:
    """
    Catálogo de los 17 servicios de IA de ejemplo definidos en services_catalog.yaml.
    Permite seleccionar los servicios más relevantes para cada tipo de negocio.
    """

    def __init__(self, catalog_path: Path) -> None:
        """
        Args:
            catalog_path: Ruta al archivo services_catalog.yaml.
        """
        self._services: dict[str, dict] = {}
        self._category_mapping: dict[str, str] = {}
        self._load_catalog(catalog_path)

    def _load_catalog(self, path: Path) -> None:
        """Carga el catálogo de servicios desde el archivo YAML."""
        if not path.exists():
            raise FileNotFoundError(f"Catálogo de servicios no encontrado: {path}")

        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        # Indexar servicios por ID
        for service in data.get("services", []):
            self._services[service["id"]] = service

        # Cargar mapeo de categorías
        self._category_mapping = data.get("category_mapping", {})

        logger.info(f"Catálogo cargado: {len(self._services)} servicios")

    def get_services_for_category(
        self, category: str, count: int = 3, has_website: bool = True, has_social_media: bool = True
    ) -> list[dict]:
        """
        Retorna los N servicios más relevantes para una categoría de negocio.

        Usa sistema de puntuación:
        - 10 puntos para S04 cuando el negocio NO tiene sitio web (prioridad máxima)
        - 10 puntos para S17 cuando el negocio NO tiene redes sociales (prioridad máxima)
        - 3 puntos si la categoría está en 'best_for' del servicio
        - 1 punto como relevancia general (todos los servicios aplican a cualquier negocio)

        Args:
            category: Tipo de negocio (restaurant, gym, doctor, etc.)
            count: Número de servicios a retornar.
            has_website: Si el negocio ya tiene sitio web. Si es False, S04 se prioriza.
            has_social_media: Si el negocio tiene Instagram o Facebook. Si es False,
                              S17 (Redes Sociales con IA) se prioriza al máximo.

        Returns:
            Lista de servicios ordenados por relevancia.
        """
        # Normalizar la categoría usando el mapeo
        normalized_category = self._category_mapping.get(category, category)

        # Puntuar cada servicio
        scored_services = []
        for service_id, service in self._services.items():
            best_for = service.get("best_for", [])

            # S04 recibe prioridad máxima cuando el negocio no tiene sitio web
            if service_id == "S04" and not has_website:
                score = 10
            # S17 recibe prioridad máxima cuando el negocio no tiene redes sociales
            elif service_id == "S17" and not has_social_media:
                score = 10
            else:
                score = 3 if normalized_category in best_for else 1

            scored_services.append((score, service_id, service))

        # Ordenar por puntaje descendente (desempate por ID para consistencia)
        scored_services.sort(key=lambda x: (-x[0], x[1]))

        return [service for _, _, service in scored_services[:count]]

    def get_service_by_id(self, service_id: str) -> dict | None:
        """
        Retorna un servicio por su ID (S01-S14).

        Args:
            service_id: ID del servicio (ej: "S01", "S06").

        Returns:
            Diccionario del servicio o None si no existe.
        """
        return self._services.get(service_id)

    def get_all_services(self) -> list[dict]:
        """Retorna todos los servicios del catálogo."""
        return list(self._services.values())

    def format_for_prompt(self, services: list[dict]) -> str:
        """
        Formatea una lista de servicios para incluir en el prompt de Claude.
        Produce texto claro y estructurado para mejor calidad de propuesta.

        Args:
            services: Lista de servicios a formatear.

        Returns:
            Texto formateado con nombre, descripción y beneficio de cada servicio.
        """
        lines = []
        for service in services:
            lines.append(
                f"• {service['name']}: {service['short_description']}. "
                f"Beneficio principal: {service['benefit']}"
            )
        return "\n".join(lines)

    def get_service_ids(self, services: list[dict]) -> list[str]:
        """Extrae los IDs de una lista de servicios."""
        return [s["id"] for s in services]
