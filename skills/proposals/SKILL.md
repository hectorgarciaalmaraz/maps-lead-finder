---
name: proposal-generator
version: "1.0.0"
description: "Genera propuestas comerciales personalizadas de 150-200 palabras usando Claude AI"
author: "Hector Garcia Almaraz"
tags: [ai, proposals, anthropic, marketing, personalization]
dependencies:
  - anthropic>=0.40.0
  - PyYAML>=6.0.0
inputs:
  - name: prospect
    type: object
    required: true
    description: "Objeto Prospect con name, category, address, rating, review_count"
outputs:
  - name: proposal_text
    type: str
    description: "Texto de la propuesta generada (150-200 palabras)"
  - name: service_ids
    type: "list[str]"
    description: "IDs de los servicios incluidos en la propuesta (ej: ['S02', 'S06'])"
  - name: word_count
    type: int
    description: "Conteo de palabras de la propuesta generada"
env_required:
  - ANTHROPIC_API_KEY
---

# Skill: Proposal Generator

## Descripción

Esta skill genera propuestas comerciales personalizadas usando la API de Anthropic (Claude).
Las propuestas son breves (150-200 palabras), adaptadas al tipo de negocio, y mencionan
2-3 servicios específicos del catálogo de la agencia que son más relevantes
para ese tipo de negocio.

## Archivos del módulo

| Archivo | Propósito |
|---------|-----------|
| `generator.py` | Clase `ProposalGenerator` que llama a la API de Anthropic |
| `service_catalog.py` | Clase `ServiceCatalog` con los 17 servicios de ejemplo de `config/services_catalog.yaml` |
| `templates/` | Plantillas Markdown por tipo de negocio |

## Uso desde CLI

```bash
# Generar propuesta para un prospecto específico
python main.py generate --prospect-id 1

# Generar propuestas para todos los prospectos sin propuesta
python main.py generate --all-pending

# Generar en lotes de 10
python main.py generate --all-pending --batch-size 10
```

## Uso desde Python

```python
from pathlib import Path
from skills.proposals.generator import ProposalGenerator
from skills.proposals.service_catalog import ServiceCatalog
from config import config

catalog = ServiceCatalog(Path("config/services_catalog.yaml"))
generator = ProposalGenerator(
    api_key=config.anthropic_api_key,
    config=config.proposals,
    catalog=catalog,
    agency=config.agency,
)

# prospect es un objeto Prospect de SQLAlchemy
text, service_ids, word_count = generator.generate(prospect)
print(f"Propuesta ({word_count} palabras):\n{text}")
```

## Plantillas disponibles

| Plantilla | Categorías cubiertas |
|-----------|---------------------|
| `restaurante.md` | restaurant, cafe, bar, bakery |
| `tienda_retail.md` | store, clothing_store, electronics_store |
| `consultorio.md` | doctor, dentist, hospital |
| `gimnasio.md` | gym, health, fitness |
| `salon_belleza.md` | beauty_salon, hair_care, spa |
| `generico.md` | Todos los demás tipos de negocio |

## Reglas de negocio críticas

- **Máximo 200 palabras**: El generador valida el conteo y trunca si es necesario.
- **Tono**: Siempre cálido, profesional y accesible. Sin jerga técnica.
- **Personalización**: Siempre menciona el nombre del negocio específicamente.
- **Servicios**: Siempre entre 2-3 servicios del catálogo (configurable en settings.yaml).
- **Placeholders**: Si el nombre o los datos de contacto de la agencia no están configurados,
  se usan placeholders `[NOMBRE_AGENCIA]`, `[TELEFONO_AGENCIA]`, `[EMAIL_AGENCIA]`, `[REDES_AGENCIA]`.

## Notas

- El modelo de IA configurado por defecto es `claude-haiku-4-5-20251001` (rápido y económico).
- Costo aproximado por propuesta: ~$0.001-0.003 USD.
- Las propuestas se almacenan en la tabla `proposals` de la base de datos SQLite.
