---
name: google-maps-scraping
version: "1.0.0"
description: "Extrae datos de negocios locales de Google Maps usando la API de Google Places"
author: "Hector Garcia Almaraz"
tags: [scraping, google-maps, prospecting, data-collection]
dependencies:
  - googlemaps>=4.10.0
  - pydantic>=2.10.0
  - requests>=2.32.0
  - beautifulsoup4>=4.12.0
inputs:
  - name: lat
    type: float
    required: true
    description: "Latitud del centro de búsqueda"
  - name: lng
    type: float
    required: true
    description: "Longitud del centro de búsqueda"
  - name: radius_km
    type: float
    required: false
    default: 5.0
    description: "Radio de búsqueda en kilómetros (configurable por CLI o settings.yaml)"
  - name: categories
    type: "list[str]"
    required: false
    default: null
    description: "Categorías de Google Places a buscar. Si es null, usa las configuradas en settings.yaml"
  - name: enrich
    type: bool
    required: false
    default: true
    description: "Si es true, visita los sitios web para extraer emails y redes sociales"
outputs:
  - name: total_found
    type: int
    description: "Total de negocios encontrados en la búsqueda"
  - name: new_saved
    type: int
    description: "Nuevos prospectos guardados en la base de datos"
  - name: duplicates
    type: int
    description: "Prospectos duplicados omitidos (ya existían)"
env_required:
  - GOOGLE_MAPS_API_KEY
---

# Skill: Google Maps Scraping

## Descripción

Esta skill extrae datos completos de negocios locales usando la API de Google Places.
Realiza una búsqueda por radio (Nearby Search) seguida de una llamada a Place Details
por cada negocio para obtener información completa. Opcionalmente, visita los sitios
web de los negocios para enriquecer los datos con emails y redes sociales.

## Archivos del módulo

| Archivo | Propósito |
|---------|-----------|
| `google_maps.py` | Clase principal `GoogleMapsScraper` con lógica de búsqueda y paginación |
| `data_enrichment.py` | Clase `DataEnricher` para extraer contactos de sitios web |
| `validators.py` | Modelos Pydantic para validar respuestas de la API |

## Uso desde CLI

```bash
# Búsqueda básica con radio de 5km (valor por defecto)
python main.py scrape --lat 19.4326 --lng -99.1332

# Búsqueda con radio personalizado
python main.py scrape --lat 19.4326 --lng -99.1332 --radius 10

# Solo ciertas categorías
python main.py scrape --lat 19.4326 --lng -99.1332 --radius 3 -c restaurant -c gym

# Sin enriquecimiento de sitios web (más rápido)
python main.py scrape --lat 19.4326 --lng -99.1332 --no-enrich
```

## Uso desde Python

```python
from skills.scraping.google_maps import GoogleMapsScraper
from config import config

# El db_session viene del contexto de Flask
scraper = GoogleMapsScraper(
    api_key=config.google_maps_api_key,
    db_session=db.session,
    config=config.scraping,
)

prospects, new_count, dup_count = scraper.search_and_save(
    lat=19.4326,
    lng=-99.1332,
    radius_km=5.0,
)

print(f"Encontrados: {len(prospects)}, Nuevos: {new_count}, Duplicados: {dup_count}")
```

## Ejemplos de configuración de radio

```yaml
# config/settings.yaml
scraping:
  default_radius_km: 5    # Radio por defecto: 5 km
```

```bash
# CLI - radio personalizado
python main.py scrape --radius 15  # Búsqueda en 15 km
```

## Notas importantes

- **Costo de API**: Cada llamada a Place Details cuesta ~$0.017 USD.
  Con 60 resultados por categoría × 14 categorías = ~840 llamadas ≈ $14.28 USD por búsqueda completa.
  Se recomienda buscar solo las categorías relevantes para tu negocio.

- **Rate limiting**: El scraper espera 1.5 segundos entre llamadas (configurable en `settings.yaml`).
  Google requiere además 2.5 segundos antes de usar el `next_page_token` para la siguiente página.

- **Deduplicación**: Los negocios se identifican por su `place_id` de Google.
  Si ya existe en la base de datos, se omite sin error.

- **Enriquecimiento**: El módulo `DataEnricher` visita el sitio web del negocio para
  extraer emails y redes sociales que Google Maps no siempre proporciona.
  Respeta `robots.txt` y usa delays corteses entre requests.

- **Categorías disponibles**: restaurant, store, gym, beauty_salon, doctor, dentist,
  lawyer, accounting, real_estate_agency, car_dealer, hotel, veterinary_care, pharmacy, school
