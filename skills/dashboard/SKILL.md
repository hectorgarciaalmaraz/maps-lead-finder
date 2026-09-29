---
name: dashboard
version: "1.0.0"
description: "Panel web de control para gestionar prospectos, propuestas y envíos"
author: "Hector Garcia Almaraz"
tags: [dashboard, flask, web, management]
dependencies:
  - flask>=3.1.0
  - flask-sqlalchemy>=3.1.0
  - pandas>=2.0.0
  - openpyxl>=3.1.0
inputs:
  - name: host
    type: str
    required: false
    default: "127.0.0.1"
    description: "Host donde correr el dashboard"
  - name: port
    type: int
    required: false
    default: 5000
    description: "Puerto del dashboard"
outputs:
  - name: url
    type: str
    description: "URL donde está disponible el dashboard"
env_required:
  - FLASK_SECRET_KEY
---

# Skill: Dashboard Web

## Descripción

Panel de control web construido con Flask que permite gestionar todo el pipeline
de prospección desde una interfaz visual. Incluye visualización de prospectos,
editor de propuestas, envío de mensajes y estadísticas.

## Archivos del módulo

| Archivo | Propósito |
|---------|-----------|
| `app.py` | Flask factory + modelos ORM + todas las rutas del dashboard |

## Cómo iniciar el dashboard

```bash
python dashboard.py
# Abrir: http://localhost:5000
```

## Rutas disponibles

### Vistas HTML
| Ruta | Descripción |
|------|-------------|
| `/` | Redirige a la lista de prospectos |
| `/prospects` | Lista de prospectos con filtros |
| `/prospects/<id>` | Detalle de un prospecto |
| `/stats` | Estadísticas y métricas |
| `/config` | Configuración del sistema |
| `/search` | Iniciar búsqueda en Google Maps |

### API REST (JSON)
| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/prospects` | Lista prospectos (filtros: category, status, min_rating, search) |
| GET | `/api/prospects/<id>` | Detalle completo de un prospecto |
| PATCH | `/api/prospects/<id>` | Actualizar notas o status |
| POST | `/api/prospects/<id>/generate-proposal` | Generar propuesta con IA |
| PUT | `/api/proposals/<id>` | Editar propuesta manualmente |
| POST | `/api/proposals/<id>/send` | Enviar propuesta por canal |
| POST | `/api/batch/generate` | Generar propuestas en lote |
| POST | `/api/batch/send` | Enviar propuestas en lote |
| GET | `/api/stats` | Estadísticas del sistema |
| GET | `/api/export/csv` | Exportar prospectos a CSV |
| GET | `/api/export/excel` | Exportar prospectos a Excel |
| GET/PUT | `/api/config` | Datos de la agencia (se guardan en BD; los generadores usan el .env) |
| POST | `/api/search` | Iniciar scraping en background |
| GET | `/api/search/status` | Estado del scraping actual |
| POST | `/api/optout` | Registrar opt-out |

## Funcionalidades del dashboard

- **Prospectos**: Ver, filtrar y buscar por nombre, categoría, calificación, distancia
- **Propuestas**: Ver, editar antes de enviar, historial de versiones
- **Envío**: Individual o por lotes, selección de canal
- **Estadísticas**: Tasa de contacto, respuesta, conversión por categoría
- **Exportación**: CSV y Excel con todos los datos
- **Configuración**: Datos de contacto de la agencia editables desde la UI (se guardan en la BD, pero los generadores leen `AGENCY_*` del .env)
- **Búsqueda**: Iniciar scraping de Google Maps con parámetros configurables

## Modelos de base de datos

| Tabla | Descripción |
|-------|-------------|
| `prospects` | Negocios extraídos de Google Maps |
| `proposals` | Propuestas generadas por IA |
| `contacts` | Historial de envíos por canal |
| `opt_outs` | Lista de exclusión |
| `app_config` | Configuración editable en tiempo real |
