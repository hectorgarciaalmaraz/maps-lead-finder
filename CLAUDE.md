# Maps Lead Finder

## Descripción del Proyecto

Sistema de prospección comercial automatizada para una agencia de servicios de IA (nombre y contacto configurables con `AGENCY_*`).
Extrae negocios locales de Google Maps, genera propuestas personalizadas con IA (Claude) y las envía
por múltiples canales: email, SMS y WhatsApp.

## Identidad y Tono de Comunicación

- Agencia: la definida en `AGENCY_NAME` (placeholder `[NOMBRE_AGENCIA]` si no está configurada)
- Tono: Profesional, amable, claro y accesible
- Sin jerga técnica en propuestas y comunicaciones externas
- Propuestas: **Máximo 200 palabras** (regla de negocio crítica)
- Idioma de propuestas: Español latinoamericano

## Comandos Rápidos

```bash
# Instalar dependencias
pip install -r requirements.txt

# Inicializar base de datos
python main.py init-db

# Configurar variables de entorno
cp config/.env.example .env
# Editar .env con tus credenciales

# Buscar negocios (radio configurable)
python main.py scrape --lat 19.4326 --lng -99.1332 --radius 5
python main.py scrape --radius 10 -c restaurant -c gym

# Generar propuestas
python main.py generate --all-pending --batch-size 20
python main.py generate --prospect-id 42

# Enviar propuestas
python main.py send --proposal-id 15 --channel email
python main.py send-batch --all-ready --channel email --dry-run

# Ver estadísticas
python main.py stats

# Iniciar dashboard web
python dashboard.py
# Abrir: http://localhost:5000

# Ejecutar tests
pytest tests/ -v
pytest tests/ --cov=skills --cov-report=html
```

## Arquitectura del Sistema

```
maps-lead-finder/
├── config/                    # Configuración centralizada
│   ├── __init__.py            # Singleton de configuración (AppConfig)
│   ├── settings.yaml          # Parámetros no sensibles
│   ├── services_catalog.yaml  # Catálogo de 17 servicios de IA (ejemplo)
│   └── .env.example           # Template de variables de entorno
├── skills/
│   ├── scraping/              # Módulo de Google Maps
│   │   ├── google_maps.py     # Scraper principal con paginación
│   │   ├── data_enrichment.py # Enriquecimiento con web scraping
│   │   └── validators.py      # Modelos Pydantic
│   ├── proposals/             # Módulo de propuestas IA
│   │   ├── generator.py       # Generador usando Anthropic Claude
│   │   ├── service_catalog.py # Selección inteligente de servicios
│   │   └── templates/         # Plantillas por tipo de negocio
│   ├── contact/               # Módulo de contacto
│   │   ├── email_sender.py    # Email (SMTP/SendGrid)
│   │   ├── sms_sender.py      # SMS (Twilio)
│   │   └── social_messenger.py # WhatsApp (Twilio) + stubs sociales
│   └── dashboard/             # Dashboard Flask
│       └── app.py             # Factory + ORM models + rutas
├── tools/                     # Orquestación usada por el CLI
├── templates/                 # HTML del dashboard
├── tests/                     # Suite de tests
├── main.py                    # CLI principal (Click)
└── dashboard.py               # Runner del servidor Flask
```

## Skills Disponibles

| Skill | Descripción |
|-------|-------------|
| `skills/scraping/` | Extrae negocios de Google Maps por radio configurable |
| `skills/proposals/` | Genera propuestas con Claude API (150-200 palabras) |
| `skills/contact/` | Envía propuestas por email, SMS y WhatsApp |
| `skills/dashboard/` | Panel web Flask para gestión completa |

## Catálogo de Servicios de ejemplo (17)

S01: Sistemas Automatizados con IA
S02: Bot Asistente para Negocios con IA
S03: Bot Tipo Secretaria con IA
S04: Páginas Web y Apps Móviles con IA
S05: Generación de Imágenes y Videos con IA
S06: Campañas de Marketing/Publicidad con IA
S07: Sistemas de Scraping de Datos con IA
S08: Sistemas Financieros con IA (Excel/Sheets)
S09: Gestión de Herramientas Google con IA
S10: Extracción de Datos de Documentos con IA
S11: Generación de Música con IA
S12: Generación y Clonación de Voz con IA
S13: Generación de Avatares con IA
S14: Consultoría en Herramientas de IA
S15: Manejo de Inventario con IA
S16: Asistente Virtual con Voz para Llamadas Telefónicas
S17: Manejo y Creación de Redes Sociales con IA

El catálogo vive en `config/services_catalog.yaml` y es un ejemplo: reemplázalo por los servicios de tu agencia.

## Reglas de Negocio Críticas

1. **Propuestas: MÁXIMO 200 palabras** – Validado en `skills/proposals/generator.py`
2. **Ventana de contacto: 9 AM – 7 PM** hora local – Implementado en todos los senders
3. **Límite diario: 50 contactos** – Configurable en `config/settings.yaml`
4. **1 mensaje por negocio** en primer contacto – Verificar status antes de enviar
5. **Opt-out inmediato** – Tabla `opt_outs` revisada antes de cada envío

## Variables de Entorno Requeridas

Ver `config/.env.example` para la lista completa. Las mínimas para funcionar:
- `GOOGLE_MAPS_API_KEY` – Para búsquedas en Google Maps
- `ANTHROPIC_API_KEY` – Para generación de propuestas con IA
- `AGENCY_NAME`, `AGENCY_PHONE`, `AGENCY_EMAIL` – Nombre y contacto de la agencia (en propuestas)

## Datos de Contacto Placeholders

Si no están configuradas las variables de entorno, las propuestas usarán:
- `[NOMBRE_AGENCIA]`
- `[TELEFONO_AGENCIA]`
- `[EMAIL_AGENCIA]`
- `[REDES_AGENCIA]`

## Notas de Desarrollo

- Todo el código está comentado en **español**
- Se usan type hints en Python en todos los módulos
- Se sigue PEP 8
- Los secretos NUNCA se hardcodean en el código
- El radio de búsqueda SIEMPRE es configurable (`--radius N` en CLI o `settings.yaml`)
