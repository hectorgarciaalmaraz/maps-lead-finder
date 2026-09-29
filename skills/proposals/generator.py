"""
Generador de propuestas comerciales con IA para Maps Lead Finder.
Usa la API de Anthropic (Claude) para generar propuestas personalizadas de 150-200 palabras
por tipo de negocio, usando plantillas y el catálogo de servicios.
"""

import logging
import re
from pathlib import Path
from typing import TYPE_CHECKING

import anthropic

from config import AgencyContactInfo, ProposalsConfig
from skills.proposals.service_catalog import ServiceCatalog

if TYPE_CHECKING:
    from skills.dashboard.app import Prospect

logger = logging.getLogger(__name__)

# Directorio de plantillas
TEMPLATES_DIR = Path(__file__).parent / "templates"

# Prompt de sistema para el modelo de IA — versión email
SYSTEM_PROMPT = """Eres un experto redactor de propuestas comerciales para [NOMBRE_AGENCIA],
empresa mexicana especializada en soluciones de Inteligencia Artificial para negocios locales.

Tu tarea es escribir propuestas comerciales cortas y efectivas que cumplan estas reglas:

REGLAS OBLIGATORIAS:
1. Máximo 200 palabras. Cuenta las palabras y asegúrate de no pasarte.
2. Mínimo 150 palabras. Sé suficientemente informativo.
3. Menciona el nombre del negocio específicamente al inicio.
4. Presenta exactamente los servicios indicados en el contexto.
5. Usa lenguaje simple y accesible. Cero jerga técnica.
6. Tono cálido, profesional y amable. Nunca agresivo ni insistente.
7. Incluye los datos de contacto de la agencia exactamente como se proporcionan.
8. Termina siempre con "Saludos cordiales, Equipo [NOMBRE_AGENCIA]"
9. Si se proporcionan reseñas del negocio, úsalas para personalizar el mensaje (menciona algo específico que hacen bien o un área donde la IA los puede ayudar más).

ESTRUCTURA OBLIGATORIA:
1. Saludo personalizado con el nombre del negocio
2. Presentación: "Somos [NOMBRE_AGENCIA], especializados en IA"
3. 2-3 servicios relevantes explicados en lenguaje simple
4. Beneficio concreto: qué ganarán
5. Llamada a la acción clara
6. Datos de contacto
7. Despedida

FORMATO: Solo el texto de la propuesta. Sin encabezados, sin markdown, sin notas adicionales."""

# Prompt de sistema para el modelo de IA — versión WhatsApp
WHATSAPP_SYSTEM_PROMPT = """Eres un experto en comunicación directa y persuasiva por WhatsApp para [NOMBRE_AGENCIA],
empresa mexicana especializada en Inteligencia Artificial para negocios locales.

Tu tarea es escribir un mensaje de WhatsApp corto, personal y persuasivo. Reglas:

REGLAS OBLIGATORIAS:
1. Máximo 100 palabras. Cuenta bien.
2. Mínimo 60 palabras.
3. Tono casual y cercano, como si fuera de persona a persona. Nada formal.
4. Empieza con un saludo directo usando el nombre del negocio.
5. Menciona 1-2 beneficios concretos y específicos para ese tipo de negocio.
6. Una llamada a la acción simple: "¿Les interesa saber más?" o "¿Hablamos esta semana?"
7. Incluye los datos de contacto al final.
8. Usa 2-3 emojis relevantes (no exageres).
9. Si hay reseñas del negocio, personaliza con algo específico que se mencione en ellas.

FORMATO: Solo el texto del mensaje. Sin encabezados, sin comillas, sin notas adicionales.
El mensaje debe sentirse como escrito por un humano real, no como publicidad genérica."""


class ProposalGenerator:
    """
    Genera propuestas comerciales personalizadas usando la API de Anthropic.
    Las propuestas se adaptan al tipo de negocio y mencionan servicios relevantes.
    """

    def __init__(
        self,
        api_key: str,
        config: ProposalsConfig,
        catalog: ServiceCatalog,
        agency: AgencyContactInfo,
    ) -> None:
        """
        Args:
            api_key: API Key de Anthropic.
            config: Configuración de propuestas (modelo, tokens, etc.).
            catalog: Catálogo de servicios de la agencia.
            agency: Nombre y datos de contacto de la agencia.
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.config = config
        self.catalog = catalog
        self.agency = agency

    def generate(self, prospect: "Prospect") -> tuple[str, str, list[str], int]:
        """
        Genera dos versiones de propuesta para un prospecto: email y WhatsApp.

        Args:
            prospect: Objeto Prospect de SQLAlchemy (o cualquier objeto con .name,
                     .category, .address, .rating, .review_count).

        Returns:
            Tupla (email_text, whatsapp_text, ids_servicios_usados, conteo_palabras_email).

        Raises:
            RuntimeError: Si la API de Anthropic falla o la propuesta supera el límite.
        """
        # Seleccionar servicios relevantes para el tipo de negocio.
        # S04 se prioriza si no tiene sitio web; S17 si no tiene redes sociales.
        has_website = bool(getattr(prospect, "website", None))
        has_social_media = bool(
            getattr(prospect, "instagram_url", None) or getattr(prospect, "facebook_url", None)
        )
        services = self.catalog.get_services_for_category(
            prospect.category,
            count=self.config.services_per_proposal,
            has_website=has_website,
            has_social_media=has_social_media,
        )
        service_ids = self.catalog.get_service_ids(services)
        services_text = self.catalog.format_for_prompt(services)

        # Cargar plantilla según categoría
        template = self._load_template(prospect.category)

        # Formatear datos de contacto de la agencia
        contact_info = self._format_contact_info()

        # Construir el prompt de usuario con todos los datos del negocio
        user_prompt = self._build_user_prompt(
            prospect=prospect,
            template=template,
            services_text=services_text,
            contact_info=contact_info,
        )
        user_prompt = self._apply_agency_name(user_prompt)

        logger.info(
            f"Generando propuestas para '{prospect.name}' ({prospect.category}) "
            f"con servicios: {service_ids}"
        )

        try:
            # ── Versión EMAIL ─────────────────────────────────────────────────
            email_response = self.client.messages.create(
                model=self.config.model,
                max_tokens=self.config.max_tokens,
                temperature=self.config.temperature,
                system=self._apply_agency_name(SYSTEM_PROMPT),
                messages=[{"role": "user", "content": user_prompt}],
            )
            email_text = email_response.content[0].text.strip()

            # Validar longitud del email
            word_count = len(email_text.split())
            if word_count > self.config.max_words + 20:
                email_text = self._truncate_to_limit(email_text, self.config.max_words)
                word_count = len(email_text.split())

            email_text = self._inject_contact_info(email_text)

            # ── Versión WHATSAPP ──────────────────────────────────────────────
            whatsapp_text = self._generate_whatsapp(user_prompt, contact_info)

            logger.info(
                f"Propuestas generadas para '{prospect.name}': "
                f"email={word_count} palabras, whatsapp={len(whatsapp_text.split())} palabras"
            )

            return email_text, whatsapp_text, service_ids, word_count

        except anthropic.APIConnectionError as e:
            logger.error(f"Error de conexión con Anthropic API: {e}")
            raise RuntimeError(f"No se pudo conectar con la API de IA: {e}") from e
        except anthropic.AuthenticationError as e:
            logger.error(f"API Key de Anthropic inválida: {e}")
            raise RuntimeError(
                "API Key de Anthropic inválida. Verifica tu configuración en .env"
            ) from e
        except anthropic.RateLimitError as e:
            logger.error(f"Límite de requests de Anthropic alcanzado: {e}")
            raise RuntimeError("Límite de la API alcanzado. Intenta más tarde.") from e
        except Exception as e:
            logger.error(f"Error inesperado generando propuesta: {e}")
            raise RuntimeError(f"Error al generar propuesta: {e}") from e

    def _generate_whatsapp(self, user_prompt: str, contact_info: str) -> str:
        """
        Genera la versión WhatsApp del mensaje (casual, 60-100 palabras, con emojis).

        Args:
            user_prompt: El mismo prompt de negocio usado para el email.
            contact_info: Datos de contacto formateados de la agencia.

        Returns:
            Texto del mensaje de WhatsApp listo para enviar.
        """
        whatsapp_prompt = (
            f"{user_prompt}\n\n"
            f"IMPORTANTE: Escribe la versión para WhatsApp. "
            f"Máximo 100 palabras, tono casual, 2-3 emojis, directo y persuasivo.\n"
            f"Datos de contacto a incluir: {contact_info}"
        )

        response = self.client.messages.create(
            model=self.config.model,
            max_tokens=400,
            temperature=self.config.temperature + 0.1,  # Ligeramente más creativo
            system=self._apply_agency_name(WHATSAPP_SYSTEM_PROMPT),
            messages=[{"role": "user", "content": whatsapp_prompt}],
        )
        whatsapp_text = response.content[0].text.strip()
        return self._inject_contact_info(whatsapp_text)

    def _load_template(self, category: str) -> str:
        """
        Carga la plantilla Markdown correspondiente a la categoría del negocio.
        Si no existe, usa la plantilla genérica.

        Args:
            category: Categoría del negocio (restaurant, gym, etc.).

        Returns:
            Contenido del cuerpo de la plantilla (sin frontmatter YAML).
        """
        # Mapeo de categorías a nombres de archivos de plantilla
        category_to_template = {
            "restaurant": "restaurante.md",
            "store": "tienda_retail.md",
            "doctor": "consultorio.md",
            "dentist": "consultorio.md",
            "gym": "gimnasio.md",
            "beauty_salon": "salon_belleza.md",
            "spa": "salon_belleza.md",
        }

        template_file = category_to_template.get(category, "generico.md")
        template_path = TEMPLATES_DIR / template_file

        # Fallback a generico si el archivo específico no existe
        if not template_path.exists():
            template_path = TEMPLATES_DIR / "generico.md"

        with open(template_path, encoding="utf-8") as f:
            content = f.read()

        # Eliminar frontmatter YAML (entre --- y ---)
        content = re.sub(r"^---.*?---\s*", "", content, flags=re.DOTALL)
        return content.strip()

    def _build_user_prompt(
        self,
        prospect,
        template: str,
        services_text: str,
        contact_info: str,
    ) -> str:
        """
        Construye el prompt completo para enviar a Claude.
        Combina la plantilla con los datos reales del prospecto, incluyendo
        contexto enriquecido (editorial_summary, review_snippets, price_level).
        """
        # Datos seguros del prospecto (con valores por defecto si están vacíos)
        name = prospect.name or "el negocio"
        address = prospect.address or "su ubicación"
        rating = f"{prospect.rating:.1f}" if prospect.rating else "sin calificación"
        review_count = str(prospect.review_count) if prospect.review_count else "0"

        # Reemplazar placeholders en la plantilla
        prompt = template.format(
            business_name=name,
            address=address,
            rating=rating,
            review_count=review_count,
            services_list=services_text,
            contact_info=contact_info,
        )

        # ── Contexto enriquecido para personalización profunda ─────────────
        extra_context = []

        # Indicar si el negocio NO tiene sitio web (importante para personalizar el pitch)
        prospect_has_website = bool(getattr(prospect, "website", None))
        if not prospect_has_website:
            extra_context.append(
                "IMPORTANTE: Este negocio NO tiene sitio web. "
                "Resalta especialmente el servicio de Páginas Web y Apps Móviles con IA "
                "como una oportunidad de crecimiento digital que están perdiendo ahora mismo."
            )

        # Descripción editorial de Google (cuando existe, es muy valiosa)
        editorial = getattr(prospect, "editorial_summary", None)
        if editorial:
            extra_context.append(f"Descripción del negocio (Google): {editorial}")

        # Nivel de precios
        price_level = getattr(prospect, "price_level", None)
        if price_level is not None:
            price_labels = {
                0: "gratuito",
                1: "económico",
                2: "precio moderado",
                3: "precio alto",
                4: "muy exclusivo",
            }
            extra_context.append(
                f"Nivel de precios: {price_labels.get(price_level, 'no especificado')}"
            )

        # Reseñas reales de clientes
        review_snippets = getattr(prospect, "review_snippets", None)
        if review_snippets:
            # Puede ser lista (ORM nuevo) o string JSON (ORM viejo)
            if isinstance(review_snippets, str):
                import json as _json

                try:
                    review_snippets = _json.loads(review_snippets)
                except Exception:
                    review_snippets = None
            if review_snippets:
                snippets_text = "\n  - ".join(review_snippets[:3])
                extra_context.append(f"Reseñas reales de clientes:\n  - {snippets_text}")

        # Agregar contexto enriquecido al prompt si existe
        if extra_context:
            prompt += "\n\nCONTEXTO ADICIONAL PARA PERSONALIZAR EL MENSAJE:\n"
            prompt += "\n".join(extra_context)

        return prompt

    def _format_contact_info(self) -> str:
        """Formatea los datos de contacto de la agencia para incluir en la propuesta."""
        lines = []

        phone = self.agency.phone
        if phone and phone != "[TELEFONO_AGENCIA]":
            lines.append(f"📱 {phone}")
        else:
            lines.append("📱 [TELEFONO_AGENCIA]")

        email = self.agency.email
        if email and email != "[EMAIL_AGENCIA]":
            lines.append(f"✉️ {email}")
        else:
            lines.append("✉️ [EMAIL_AGENCIA]")

        instagram = self.agency.instagram
        if instagram and "[" not in instagram:
            lines.append(f"📸 Instagram: {instagram}")

        facebook = self.agency.facebook
        if facebook and "[" not in facebook:
            lines.append(f"👍 Facebook: {facebook}")

        return "\n".join(lines)

    def _inject_contact_info(self, text: str) -> str:
        """
        Reemplaza los placeholders de contacto en el texto de la propuesta
        con los datos reales de la agencia (nombre, teléfono, email y redes).
        """
        replacements = {
            "[TELEFONO_AGENCIA]": self.agency.phone,
            "[EMAIL_AGENCIA]": self.agency.email,
            "[REDES_AGENCIA]": (
                f"Instagram: {self.agency.instagram} | " f"Facebook: {self.agency.facebook}"
            ),
            "[FACEBOOK_AGENCIA]": self.agency.facebook,
            "[INSTAGRAM_AGENCIA]": self.agency.instagram,
        }

        for placeholder, value in replacements.items():
            if value and "[" not in str(value):  # Solo reemplazar si hay valor real
                text = text.replace(placeholder, value)

        return self._apply_agency_name(text)

    def _apply_agency_name(self, text: str) -> str:
        """Sustituye [NOMBRE_AGENCIA] por el nombre configurado en AGENCY_NAME (si existe)."""
        name = getattr(self.agency, "name", None)
        if isinstance(name, str) and name and "[" not in name:
            return text.replace("[NOMBRE_AGENCIA]", name)
        return text

    @staticmethod
    def _truncate_to_limit(text: str, max_words: int) -> str:
        """
        Trunca el texto al límite de palabras, terminando en el último punto completo.
        Agrega '...' solo si el texto fue cortado en medio de una oración.
        """
        words = text.split()
        if len(words) <= max_words:
            return text

        # Tomar las primeras max_words palabras
        truncated = " ".join(words[:max_words])

        # Buscar el último punto para un corte limpio
        last_period = truncated.rfind(".")
        if last_period > len(truncated) * 0.6:  # Si el punto está en el 60%+ del texto
            return truncated[: last_period + 1]

        return truncated + "..."
