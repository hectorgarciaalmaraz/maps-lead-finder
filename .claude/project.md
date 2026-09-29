# Maps Lead Finder – Contexto del Proyecto

## Descripción
Sistema automatizado de prospección comercial para una agencia de servicios de IA (identidad configurable con `AGENCY_*`).
Scraping de Google Maps → Generación de propuestas con IA → Envío multicanal.

## Stack
- **Backend:** Python 3.10+, Flask 3.x, Flask-SQLAlchemy 3.x
- **IA:** Anthropic Claude (`claude-haiku-4-5-20251001`)
- **BD:** SQLite en `data/prospects.db`
- **CLI:** Click
- **APIs externas:** Google Places API, Twilio, SendGrid/SMTP

## Comandos Frecuentes
```bash
# Inicializar BD
python main.py init-db

# Scraping básico
python main.py scrape --lat 19.4326 --lng -99.1332 --radius 5

# Generar propuestas
python main.py generate --all-pending --batch-size 20

# Enviar (simulación)
python main.py send-batch --all-ready --channel email --dry-run

# Dashboard web
python dashboard.py

# Tests
pytest tests/ -v
```

## Estructura de Skills
```
skills/
  scraping/     – Google Maps + enriquecimiento web
  proposals/    – Generador de propuestas con Claude
  contact/      – Envío por email, SMS, WhatsApp
  dashboard/    – Flask app + modelos ORM
```

## Reglas de Negocio Críticas
- Propuestas: 150-200 palabras MAX (validado post-generación)
- Ventana de contacto: 9AM-7PM hora local
- Límite diario: 50 contactos/día
- 1 mensaje por negocio en primer contacto
- Placeholders: `[TELEFONO_AGENCIA]`, `[EMAIL_AGENCIA]`, `[REDES_AGENCIA]`

## Variables de Entorno Necesarias
Ver `config/.env.example` para la lista completa.
Archivo `.env` va en la raíz del proyecto (nunca en git).

## Notas para Claude
- Todo el código y comentarios están en español
- Los modelos ORM están en `skills/dashboard/app.py`
- El config singleton se importa como `from config import config`
- No hardcodear credenciales — usar `config.*` siempre
