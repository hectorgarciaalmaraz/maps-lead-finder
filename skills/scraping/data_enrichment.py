"""
Módulo de enriquecimiento de datos para Maps Lead Finder.
Visita los sitios web de los negocios para extraer emails, redes sociales y WhatsApp.
Usa web scraping ético con respeto a robots.txt y timeouts configurables.
"""

import logging
import re
import time
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup

from skills.scraping.validators import EnrichmentResult

logger = logging.getLogger(__name__)


class DataEnricher:
    """
    Enriquece datos de prospectos visitando sus sitios web.
    Extrae emails, redes sociales (Facebook, Instagram, LinkedIn) y WhatsApp.
    """

    # Patrones regex para extraer datos de contacto
    EMAIL_PATTERN = re.compile(
        r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}",
        re.IGNORECASE,
    )
    WHATSAPP_PATTERN = re.compile(
        r"(?:wa\.me/|whatsapp[:\s.]*(?:\+|00)?)([\d\s\-]{8,15})",
        re.IGNORECASE,
    )
    FACEBOOK_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?facebook\.com/(?!sharer|share|plugins|dialog|login)"
        r"(?:pages/)?([a-zA-Z0-9._%+\-]+/?)",
        re.IGNORECASE,
    )
    INSTAGRAM_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?instagram\.com/([a-zA-Z0-9._]+)/?",
        re.IGNORECASE,
    )
    LINKEDIN_PATTERN = re.compile(
        r"(?:https?://)?(?:www\.)?linkedin\.com/(?:company|in)/([a-zA-Z0-9._\-]+)/?",
        re.IGNORECASE,
    )

    # Emails de sistema a ignorar (no son correos de contacto del negocio)
    EXCLUDED_EMAIL_DOMAINS = {
        "example.com",
        "sentry.io",
        "w3.org",
        "schema.org",
        "wordpress.com",
        "wix.com",
        "squarespace.com",
        "google.com",
        "facebook.com",
        "instagram.com",
        "yoursite.com",
        "domain.com",
        "email.com",
        "doe.com",
        "test.com",
        "mail.com",
        "acme.com",
        "company.com",
        "business.com",
        "website.com",
        "correo.com",
        "tuempresa.com",
        "miempresa.com",
    }
    EXCLUDED_EMAIL_PREFIXES = {
        "noreply",
        "no-reply",
        "donotreply",
        "unsubscribe",
        "bounce",
        "mailer-daemon",
        "postmaster",
        "webmaster",
        "admin",
        "info@example",
        "test",
        "sample",
        "john",
        "jane",
        "nombre",
        "name",
        "usuario",
        "correo",
        "email",
        "youremail",
        "tuemail",
    }

    # Palabras clave para encontrar la página de contacto
    CONTACT_KEYWORDS = [
        "contacto",
        "contact",
        "contactanos",
        "contáctanos",
        "ubicacion",
        "ubicación",
        "where",
        "donde",
        "nosotros",
        "about",
        "quienes-somos",
        "quiénes-somos",
    ]

    HEADERS = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "es-MX,es;q=0.9,en;q=0.8",
    }

    def __init__(self, timeout: int = 10, respect_robots: bool = True) -> None:
        self.timeout = timeout
        self.respect_robots = respect_robots
        self.session = requests.Session()
        self.session.headers.update(self.HEADERS)

    def enrich_prospect(self, prospect_id: int, website_url: str) -> EnrichmentResult:
        """
        Visita el sitio web de un negocio y extrae datos de contacto.

        Args:
            prospect_id: ID del prospecto en la base de datos.
            website_url: URL del sitio web del negocio.

        Returns:
            EnrichmentResult con los datos encontrados.
        """
        logger.info(f"Enriqueciendo prospecto {prospect_id}: {website_url}")

        try:
            # Verificar robots.txt antes de visitar
            if self.respect_robots and not self._is_allowed_by_robots(website_url):
                logger.info(f"robots.txt no permite el acceso a {website_url}")
                return EnrichmentResult(prospect_id=prospect_id, success=False, error="robots.txt")

            # Visitar página principal
            html_main = self._fetch_page(website_url)
            if not html_main:
                return EnrichmentResult(
                    prospect_id=prospect_id, success=False, error="No se pudo acceder al sitio"
                )

            contacts = self._extract_contacts(html_main, website_url)

            # Si no encontramos email, buscar en la página de contacto
            if not contacts.get("email"):
                soup = BeautifulSoup(html_main, "lxml")
                contact_url = self._find_contact_page(soup, website_url)
                if (
                    contact_url
                    and self.respect_robots
                    and not self._is_allowed_by_robots(contact_url)
                ):
                    logger.info(f"robots.txt no permite la página de contacto {contact_url}")
                    contact_url = None
                if contact_url:
                    time.sleep(1.0)  # Pausa cortés entre requests
                    html_contact = self._fetch_page(contact_url)
                    if html_contact:
                        extra_contacts = self._extract_contacts(html_contact, website_url)
                        # Combinar resultados, preferir los de la página de contacto
                        for key, value in extra_contacts.items():
                            if value and not contacts.get(key):
                                contacts[key] = value

            result = EnrichmentResult(prospect_id=prospect_id, **contacts)
            if result.has_data():
                logger.info(f"Prospecto {prospect_id} enriquecido: {contacts}")
            else:
                logger.info(f"Prospecto {prospect_id}: no se encontraron datos adicionales")

            return result

        except Exception as e:
            logger.error(f"Error enriqueciendo prospecto {prospect_id}: {e}")
            return EnrichmentResult(prospect_id=prospect_id, success=False, error=str(e))

    def _fetch_page(self, url: str) -> str | None:
        """
        Descarga una página web y retorna el HTML.
        Retorna None si no se puede acceder.
        """
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            response.raise_for_status()

            # Verificar que es HTML
            content_type = response.headers.get("content-type", "")
            if "text/html" not in content_type and "application/xhtml" not in content_type:
                return None

            return response.text

        except requests.exceptions.SSLError:
            # Certificado inválido: se omite el sitio (nunca se desactiva la verificación SSL)
            logger.debug(f"Certificado SSL inválido, se omite {url}")
            return None
        except Exception as e:
            logger.debug(f"Error fetching {url}: {e}")
            return None

    def _extract_contacts(self, html: str, base_url: str) -> dict:
        """
        Extrae emails, redes sociales y WhatsApp del HTML de una página.

        Args:
            html: Contenido HTML de la página.
            base_url: URL base para resolver enlaces relativos.

        Returns:
            Diccionario con los datos encontrados.
        """
        soup = BeautifulSoup(html, "lxml")

        # Eliminar scripts y estilos para evitar falsos positivos
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        text_content = soup.get_text(separator=" ")

        # Extraer emails del texto visible y del HTML fuente
        emails = self.EMAIL_PATTERN.findall(text_content)
        emails += self.EMAIL_PATTERN.findall(html)
        email = self._filter_emails(set(emails))

        # Extraer redes sociales de los enlaces href
        facebook_url = None
        instagram_url = None
        linkedin_url = None
        whatsapp = None

        for link in soup.find_all("a", href=True):
            href = link["href"]

            if not facebook_url:
                match = self.FACEBOOK_PATTERN.search(href)
                if match:
                    full_url = (
                        href
                        if href.startswith("http")
                        else f"https://facebook.com/{match.group(1)}"
                    )
                    # Evitar páginas genéricas de Facebook
                    if not any(x in full_url for x in ["/login", "/share", "/sharer", "/dialog"]):
                        facebook_url = full_url

            if not instagram_url:
                match = self.INSTAGRAM_PATTERN.search(href)
                if match:
                    instagram_url = (
                        href
                        if href.startswith("http")
                        else f"https://instagram.com/{match.group(1)}"
                    )

            if not linkedin_url:
                match = self.LINKEDIN_PATTERN.search(href)
                if match:
                    linkedin_url = (
                        href
                        if href.startswith("http")
                        else f"https://linkedin.com/company/{match.group(1)}"
                    )

            if not whatsapp:
                match = self.WHATSAPP_PATTERN.search(href)
                if match:
                    number = re.sub(r"[^\d+]", "", match.group(1))
                    if len(number) >= 8:
                        whatsapp = f"+{number}" if not number.startswith("+") else number

        # Buscar WhatsApp también en el texto
        if not whatsapp:
            match = self.WHATSAPP_PATTERN.search(text_content)
            if match:
                number = re.sub(r"[^\d+]", "", match.group(1))
                if len(number) >= 8:
                    whatsapp = f"+{number}" if not number.startswith("+") else number

        return {
            "email": email,
            "facebook_url": facebook_url,
            "instagram_url": instagram_url,
            "linkedin_url": linkedin_url,
            "whatsapp": whatsapp,
        }

    def _find_contact_page(self, soup: BeautifulSoup, base_url: str) -> str | None:
        """
        Busca el enlace a la página de contacto dentro del sitio web.

        Args:
            soup: BeautifulSoup de la página principal.
            base_url: URL base para resolver rutas relativas.

        Returns:
            URL de la página de contacto o None si no se encuentra.
        """
        for link in soup.find_all("a", href=True):
            href = link["href"].lower().strip()
            link_text = link.get_text(separator=" ").lower().strip()

            # Verificar si el enlace o texto coincide con palabras clave de contacto
            is_contact = any(
                keyword in href or keyword in link_text for keyword in self.CONTACT_KEYWORDS
            )

            if is_contact:
                full_url = urljoin(base_url, link["href"])
                # Verificar que es del mismo dominio
                if urlparse(full_url).netloc == urlparse(base_url).netloc:
                    return full_url

        return None

    def _filter_emails(self, emails: set) -> str | None:
        """
        Filtra emails de sistema/spam y retorna el mejor candidato.
        Prioriza emails con dominios propios sobre emails genéricos.

        Args:
            emails: Conjunto de emails encontrados.

        Returns:
            El email más probable de ser el contacto del negocio.
        """
        valid_emails = []

        for email in emails:
            email = email.lower().strip()
            domain = email.split("@")[-1] if "@" in email else ""

            # Filtrar dominios excluidos
            if domain in self.EXCLUDED_EMAIL_DOMAINS:
                continue

            # Filtrar prefijos excluidos
            prefix = email.split("@")[0] if "@" in email else ""
            if any(excl in prefix for excl in self.EXCLUDED_EMAIL_PREFIXES):
                continue

            # Filtrar emails con extensiones de imagen (falsos positivos)
            if domain.endswith((".png", ".jpg", ".gif", ".svg", ".css", ".js")):
                continue

            # Filtrar emails muy largos (probablemente falsas detecciones)
            if len(email) > 100:
                continue

            valid_emails.append(email)

        if not valid_emails:
            return None

        # Priorizar emails de contacto sobre otros
        priority_prefixes = ["contacto", "contact", "info", "hola", "hello", "ventas", "sales"]
        for prefix in priority_prefixes:
            for email in valid_emails:
                if email.startswith(prefix):
                    return email

        return valid_emails[0]

    def _is_allowed_by_robots(self, url: str) -> bool:
        """
        Verifica si robots.txt permite acceso a la URL.
        Retorna True si se permite (o si no se puede verificar).
        Usa timeout para no colgarse en sitios que no responden.
        """
        try:
            parsed = urlparse(url)
            robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"

            # Descargar robots.txt con timeout explícito para no colgarse
            resp = self.session.get(robots_url, timeout=self.timeout, allow_redirects=True)
            rp = RobotFileParser()
            rp.set_url(robots_url)
            rp.parse(resp.text.splitlines())

            return rp.can_fetch(self.HEADERS["User-Agent"], url)
        except Exception:
            return True  # Si no se puede verificar, asumir que está permitido
