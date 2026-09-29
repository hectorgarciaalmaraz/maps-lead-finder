---
name: contact-automation
version: "1.0.0"
description: "Envía propuestas a negocios por email, SMS y WhatsApp con reglas de negocio"
author: "Hector Garcia Almaraz"
tags: [contact, email, sms, whatsapp, automation]
dependencies:
  - twilio>=9.4.0
  - sendgrid>=6.11.0
  - pytz>=2024.0
inputs:
  - name: prospect_id
    type: int
    required: true
    description: "ID del prospecto en la base de datos"
  - name: proposal_id
    type: int
    required: true
    description: "ID de la propuesta a enviar"
  - name: channel
    type: str
    required: true
    description: "Canal de envío: 'email', 'sms', 'whatsapp'"
outputs:
  - name: success
    type: bool
    description: "Si el envío fue exitoso"
  - name: message
    type: str
    description: "Mensaje descriptivo del resultado"
env_required:
  - SMTP_USER
  - SMTP_PASSWORD
  - TWILIO_ACCOUNT_SID
  - TWILIO_AUTH_TOKEN
  - TWILIO_PHONE_NUMBER
---

# Skill: Contact Automation

## Descripción

Esta skill gestiona el envío automatizado de propuestas comerciales a negocios
prospecto a través de múltiples canales de comunicación. Implementa todas las
reglas de negocio: opt-out, ventana horaria y límite diario.

## Archivos del módulo

| Archivo | Propósito |
|---------|-----------|
| `email_sender.py` | Envío por email (SMTP + SendGrid como alternativa) |
| `sms_sender.py` | Envío de SMS por Twilio |
| `social_messenger.py` | WhatsApp vía Twilio; IG/LinkedIn como pendiente manual |

## Canales disponibles

| Canal | Estado | Requisito |
|-------|--------|-----------|
| Email | ✅ Automatizado | SMTP_USER + SMTP_PASSWORD (o SENDGRID_API_KEY) |
| SMS | ✅ Automatizado | TWILIO_ACCOUNT_SID + TWILIO_AUTH_TOKEN |
| WhatsApp | ✅ Automatizado | Twilio con WhatsApp Business habilitado |
| Instagram DM | ⚠️ Manual | Registra como pendiente; requiere envío manual |
| LinkedIn DM | ⚠️ Manual | Registra como pendiente; requiere envío manual |

## Reglas de negocio implementadas

1. **Opt-out**: Se verifica antes de cada envío. Lista en tabla `opt_outs` de la BD.
2. **Ventana horaria**: Solo se envía entre 9:00 AM y 7:00 PM hora local (México).
3. **Límite diario**: Máximo 50 contactos por día (configurable en settings.yaml).
4. **Un mensaje**: El sistema no evita reenvíos automáticamente; esta regla se aplica
   en el dashboard (no mostrar prospectos ya contactados por defecto).
5. **Footer de opt-out**: Todos los mensajes incluyen instrucciones para darse de baja.

## Uso desde CLI

```bash
# Enviar propuesta específica por email
python main.py send --proposal-id 15 --channel email

# Envío masivo de todas las propuestas pendientes
python main.py send-batch --all-ready --channel email

# Simular envío sin hacerlo realmente
python main.py send-batch --all-ready --channel email --dry-run
```

## Uso desde Python

```python
from skills.contact.email_sender import EmailSender
from config import config

sender = EmailSender(config)
result = sender.send(
    to_email="negocio@ejemplo.com",
    subject="Una propuesta para Tu Negocio – Tu Agencia",
    body="Texto de la propuesta...",
    prospect_id=42,
    proposal_id=15,
    db_session=db.session,
)
print(result)  # {"success": True, "message": "Email enviado a negocio@ejemplo.com"}
```

## Notas importantes

- El canal **WhatsApp** requiere que el número de Twilio esté aprobado para WhatsApp Business.
  Puedes probarlo con el Twilio Sandbox de WhatsApp sin aprobación formal.
- Para **Instagram** y **LinkedIn**, el sistema registra la intención de contacto como
  `pendiente` en la BD, pero el encargado debe enviar el mensaje manualmente.
- El **opt-out** por email se activa cuando el destinatario responde con 'BAJA' en el asunto.
  Este procesamiento requiere configurar un webhook de respuestas en el servidor de email.
