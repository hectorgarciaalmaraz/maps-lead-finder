"""
Generador local de propuestas comerciales para Maps Lead Finder.
Crea mensajes de email (160-190 palabras) y WhatsApp (70-90 palabras)
sin llamadas a API externas, usando datos reales de cada negocio.

Estrategia de mensajes:
- Email: abre con observacion empatica del dolor del negocio -> diferenciador
          presentacion de la agencia -> servicios en formato "nombre: que dolor resuelve" -> CTA
- WhatsApp: template completo 70-90 palabras, tono casual y empatico, hook de dolor + CTA directo
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from skills.proposals.service_catalog import ServiceCatalog

if TYPE_CHECKING:
    from skills.dashboard.app import Prospect

logger = logging.getLogger(__name__)

# -- Nombres de categorias en espanol --------------------------------------------------
CATEGORY_NAMES = {
    "restaurant": "restaurante",
    "gym": "gimnasio",
    "beauty_salon": "salon de belleza",
    "doctor": "consultorio medico",
    "dentist": "clinica dental",
    "lawyer": "despacho juridico",
    "accounting": "despacho contable",
    "real_estate_agency": "inmobiliaria",
    "car_dealer": "agencia automotriz",
    "hotel": "hotel",
    "veterinary_care": "clinica veterinaria",
    "pharmacy": "farmacia",
    "school": "institucion educativa",
    "store": "tienda",
    "general": "negocio",
}

CATEGORY_NAMES_PLURAL = {
    "restaurant": "restaurantes",
    "gym": "gimnasios",
    "beauty_salon": "salones de belleza",
    "doctor": "consultorios medicos",
    "dentist": "clinicas dentales",
    "lawyer": "despachos juridicos",
    "accounting": "despachos contables",
    "real_estate_agency": "inmobiliarias",
    "car_dealer": "agencias automotrices",
    "hotel": "hoteles",
    "veterinary_care": "clinicas veterinarias",
    "pharmacy": "farmacias",
    "school": "instituciones educativas",
    "store": "tiendas",
    "general": "negocios",
}

# -- Openers de email: hook "Sabias que?" especifico por categoria --------------------
# 2-3 oraciones: dato/pregunta que genera curiosidad -> implicacion para su negocio.
# Tono profesional (usted), empatico, no acusatorio. {name} como placeholder.
EMAIL_OPENERS = {
    "restaurant": [
        "\u00bfSab\u00eda que el 67% de los clientes que no reciben respuesta en menos de 5 minutos elige al restaurante que s\u00ed contest\u00f3? En los momentos de mayor actividad, cuando m\u00e1s dif\u00edcil es atender cada mensaje, ese ingreso sale sin hacer ruido.",
        "\u00bfSab\u00eda que el 80% de los comensales consulta Google Maps antes de decidir a d\u00f3nde ir a comer? Si no hay atenci\u00f3n r\u00e1pida en l\u00ednea ni informaci\u00f3n actualizada, muchos simplemente eligen la siguiente opci\u00f3n sin llamar.",
        "\u00bfSab\u00eda que los restaurantes que automatizan su atenci\u00f3n reciben en promedio un 30% m\u00e1s reservaciones \u2014 sin contratar personal adicional? La diferencia est\u00e1 en responder en segundos, incluso fuera de horario.",
    ],
    "gym": [
        "\u00bfSab\u00eda que el 40% de los socios que no renuevan membres\u00eda lo hacen simplemente porque nadie les record\u00f3 a tiempo \u2014 no porque no quisieran seguir? Ese ingreso ya est\u00e1 en el gimnasio, solo necesita un recordatorio oportuno para no salir.",
        "\u00bfSab\u00eda que un gimnasio pierde en promedio entre 20-30% de sus socios cada trimestre, y que la mayor\u00eda se recuperar\u00eda con un seguimiento automatizado antes del vencimiento? Es ingreso que ya se tiene, esperando ser retenido.",
        "\u00bfSab\u00eda que los gimnasios que automatizan recordatorios de renovaci\u00f3n retienen hasta un 25% m\u00e1s socios por mes, sin ning\u00fan trabajo manual del equipo? Cada membres\u00eda recuperada es dinero que de otra forma simplemente desaparece.",
    ],
    "beauty_salon": [
        "\u00bfSab\u00eda que el 35% de las ausencias en salones de belleza se evitar\u00edan simplemente con un recordatorio autom\u00e1tico el d\u00eda anterior? Cada cita vac\u00eda es tiempo perdido y un ingreso que no regresa.",
        "\u00bfSab\u00eda que cada cita vac\u00eda en un sal\u00f3n representa entre $500 y $800 de ingreso perdido \u2014 y que la mayor\u00eda ocurre por falta de una confirmaci\u00f3n oportuna? Es un problema solucionable sin agregar trabajo al equipo.",
        "\u00bfSab\u00eda que los salones que automatizan confirmaciones y recordatorios reducen ausencias hasta un 40% desde el primer mes, sin ning\u00fan cambio en c\u00f3mo trabaja el equipo?",
    ],
    "doctor": [
        "\u00bfSab\u00eda que entre el 20-30% de las citas m\u00e9dicas terminan en ausencia, y que el 80% de esos pacientes simplemente olvidaron porque nadie les record\u00f3? Cada cita perdida es tiempo e ingreso que no se recupera.",
        "\u00bfSab\u00eda que el equipo de recepci\u00f3n promedio dedica hasta 3 horas al d\u00eda solo a confirmar citas \u2014 tiempo que podr\u00eda dedicarse a atenci\u00f3n real a pacientes? Esas horas tienen un costo directo en productividad y desgaste del personal.",
        "\u00bfSab\u00eda que los consultorios que automatizan recordatorios reducen ausencias hasta un 40% y liberan horas de recepci\u00f3n desde el primer mes, sin contratar personal adicional?",
    ],
    "dentist": [
        "\u00bfSab\u00eda que un sill\u00f3n dental vac\u00edo por ausencia representa entre $800 y $2,000 de ingreso perdido \u2014 y que el 75% de esas ausencias se evitar\u00edan con un recordatorio autom\u00e1tico? Es dinero que ya estaba agendado y que se va sin aviso.",
        "\u00bfSab\u00eda que el 30% de los pacientes que no agendan cita de seguimiento simplemente olvidaron \u2014 no porque no quieran regresar? Con un recordatorio oportuno, la mayor\u00eda regresa sin ning\u00fan esfuerzo adicional del equipo.",
        "\u00bfSab\u00eda que las cl\u00ednicas dentales que automatizan confirmaciones de cita llenan hasta el 95% de su agenda cada semana, reduciendo el costo por sill\u00f3n vac\u00edo a casi cero?",
    ],
    "lawyer": [
        "\u00bfSab\u00eda que el 70% de los prospectos que buscan asesor\u00eda legal contratan al primer despacho que les responde \u2014 no necesariamente al m\u00e1s experimentado? Cada hora sin respuesta reduce directamente la probabilidad de convertir ese prospecto en cliente.",
        "\u00bfSab\u00eda que un prospecto legal sin respuesta en las primeras 24 horas tiene 5 veces m\u00e1s probabilidad de ir a la competencia? En servicios legales, la velocidad de respuesta frecuentemente importa m\u00e1s que el precio.",
        "\u00bfSab\u00eda que los despachos que responden prospectos autom\u00e1ticamente convierten hasta un 35% m\u00e1s consultas en clientes reales, sin agregar carga de trabajo al equipo jur\u00eddico?",
    ],
    "accounting": [
        "\u00bfSab\u00eda que el 60% de los clientes que cambian de contador lo hacen porque sienten que no reciben informaci\u00f3n oportuna \u2014 no por el precio? La percepci\u00f3n de atenci\u00f3n y seguimiento vale m\u00e1s que cualquier descuento.",
        "\u00bfSab\u00eda que los despachos contables que ofrecen reportes autom\u00e1ticos y alertas fiscales retienen hasta un 40% m\u00e1s clientes que los que solo entregan reportes mensuales? El valor percibido aumenta sin aumentar el trabajo manual.",
        "\u00bfSab\u00eda que los contadores que usan IA para automatizar reportes atienden hasta el doble de clientes sin aumentar personal \u2014 y cobran m\u00e1s porque entregan m\u00e1s valor a cada cliente?",
    ],
    "real_estate_agency": [
        "\u00bfSab\u00eda que el 80% de los prospectos inmobiliarios que no reciben respuesta el mismo d\u00eda terminan cerrando con otra agencia \u2014 aunque la suya fuera la mejor opci\u00f3n? En bienes ra\u00edces, el tiempo de respuesta determina qui\u00e9n cierra la operaci\u00f3n.",
        "\u00bfSab\u00eda que responder un lead inmobiliario en menos de 5 minutos aumenta la probabilidad de cierre en un 400% comparado con responder una hora despu\u00e9s? Ese prospecto ya est\u00e1 comparando opciones mientras espera.",
        "\u00bfSab\u00eda que las inmobiliarias que automatizan el seguimiento a leads cierran hasta un 35% m\u00e1s operaciones sin aumentar su equipo de ventas? Cada lead bien atendido es una comisi\u00f3n que de otra forma se va a la competencia.",
    ],
    "car_dealer": [
        "\u00bfSab\u00eda que el 64% de los compradores de autos contacta m\u00e1s de una agencia al mismo tiempo \u2014 y la que responde primero es la que casi siempre cierra la venta? Cada lead sin respuesta inmediata tiene m\u00e1s de un 60% de probabilidad de irse a la competencia.",
        "\u00bfSab\u00eda que el prospecto promedio que busca un auto en l\u00ednea espera respuesta en menos de 1 hora \u2014 y si no la recibe, llama a la siguiente agencia de la lista? En ventas de autos, la velocidad de respuesta es el primer filtro del cliente.",
        "\u00bfSab\u00eda que las agencias que automatizan seguimiento a prospectos con IA venden hasta un 30% m\u00e1s sin aumentar su equipo de ventas? La diferencia est\u00e1 en nunca dejar un lead sin atenci\u00f3n.",
    ],
    "hotel": [
        "\u00bfSab\u00eda que el 57% de los viajeros que no reciben respuesta inmediata reservan en otra plataforma en menos de 10 minutos? Cada consulta sin respuesta r\u00e1pida es una reservaci\u00f3n que se va \u2014 y en muchos casos, con una comisi\u00f3n que termina pag\u00e1ndose a una plataforma externa.",
        "\u00bfSab\u00eda que los hoteles que responden consultas en menos de 5 minutos tienen hasta un 40% m\u00e1s reservaciones directas, sin pagar comisi\u00f3n a Booking o Airbnb? Esa diferencia representa un ingreso adicional significativo por cada reservaci\u00f3n.",
        "\u00bfSab\u00eda que una reservaci\u00f3n directa genera al hotel entre 15-25% m\u00e1s ingreso que la misma reservaci\u00f3n por plataformas externas? Cada consulta respondida a tiempo es una oportunidad de captar ese ingreso completo.",
    ],
    "veterinary_care": [
        "\u00bfSab\u00eda que el 45% de los due\u00f1os de mascotas que no reciben recordatorio de vacuna simplemente lo posponen \u2014 y muchos terminan yendo a otra cl\u00ednica? El paciente que no regresa no siempre est\u00e1 insatisfecho: simplemente nadie le record\u00f3.",
        "\u00bfSab\u00eda que las cl\u00ednicas veterinarias que env\u00edan recordatorios autom\u00e1ticos de vacunas y revisiones retienen hasta un 30% m\u00e1s pacientes cada a\u00f1o, sin llamadas manuales ni trabajo extra?",
        "\u00bfSab\u00eda que el due\u00f1o de mascota promedio regresa a la cl\u00ednica de confianza cuando alguien se lo recuerda \u2014 pero el 45% no regresa simplemente porque nunca recibi\u00f3 ese recordatorio? Es retenci\u00f3n que no requiere ning\u00fan esfuerzo adicional.",
    ],
    "pharmacy": [
        "\u00bfSab\u00eda que el cliente de farmacia que recibe un recordatorio personalizado de su medicamento visita la farmacia un 35% m\u00e1s frecuente? La diferencia entre un cliente recurrente y uno que compra donde sea es, con frecuencia, tan simple como un aviso oportuno.",
        "\u00bfSab\u00eda que el 60% de los pacientes con tratamientos cr\u00f3nicos cambia de farmacia no por precio, sino porque ninguna les hace seguimiento ni les recuerda? Esos clientes est\u00e1n listos para quedarse \u2014 solo necesitan sentirse recordados.",
        "\u00bfSab\u00eda que las farmacias que personalizan comunicaci\u00f3n con IA aumentan ventas recurrentes sin invertir en publicidad, simplemente porque los clientes frecuentes compran m\u00e1s seguido?",
    ],
    "school": [
        "\u00bfSab\u00eda que el 70% de los padres que no reciben comunicaci\u00f3n oportuna de la escuela empiezan a considerar cambiar a sus hijos a otra instituci\u00f3n al a\u00f1o siguiente? La percepci\u00f3n de calidad de una escuela se construye, en gran medida, en la comunicaci\u00f3n del d\u00eda a d\u00eda.",
        "\u00bfSab\u00eda que el \u00e1rea administrativa de la mayor\u00eda de las escuelas dedica hasta un 40% de su tiempo solo a responder las mismas preguntas de padres? Ese tiempo tiene un costo real en personal y desgaste, y casi todo podr\u00eda automatizarse.",
        "\u00bfSab\u00eda que las instituciones que automatizan la comunicaci\u00f3n con padres tienen en promedio un 25% menos deserci\u00f3n escolar al a\u00f1o? La comunicaci\u00f3n oportuna genera confianza, y la confianza retiene familias.",
    ],
    "store": [
        "\u00bfSab\u00eda que el 76% de los consumidores busca en Google si una tienda tiene lo que necesita antes de salir de casa \u2014 y que si no encuentran informaci\u00f3n, simplemente van a otra? Sin presencia digital actualizada, ese cliente elige a la competencia sin siquiera llamar.",
        "\u00bfSab\u00eda que las tiendas con venta en l\u00ednea generan en promedio el 40% de sus ingresos fuera del horario de apertura f\u00edsica, sin costo fijo adicional? Cada hora que la tienda est\u00e1 cerrada es potencialmente ingreso que se pierde si no hay canal digital.",
        "\u00bfSab\u00eda que el cliente que busca sus productos en l\u00ednea un domingo y no puede comprarlos tiene menos del 20% de probabilidad de regresar el lunes? Ese ingreso perdido se acumula semana tras semana.",
    ],
    "general": [
        "\u00bfSab\u00eda que los negocios que automatizan su atenci\u00f3n al cliente ahorran en promedio 3 horas diarias de trabajo manual \u2014 y que ese tiempo se convierte directamente en m\u00e1s ventas y mejor servicio? Automatizar no requiere tecnolog\u00eda compleja ni grandes inversiones.",
        "\u00bfSab\u00eda que el 80% de los clientes potenciales elige al negocio que les responde primero \u2014 no necesariamente al m\u00e1s barato ni al mejor? La velocidad de respuesta y la disponibilidad son hoy los factores m\u00e1s determinantes en la decisi\u00f3n de compra.",
        "\u00bfSab\u00eda que la mayor\u00eda de las p\u00e9rdidas de clientes en negocios locales no son por precio ni calidad \u2014 sino por falta de seguimiento o respuesta oportuna? Es un problema que se resuelve con automatizaci\u00f3n, sin cambiar nada m\u00e1s en la operaci\u00f3n.",
    ],
}

# -- Lineas de servicio para email (ID -> "Nombre: ahorro de tiempo y dinero") ---------
# Formato: nombre + beneficio dual (tiempo + dinero) en ~15-18 palabras.
SERVICE_EMAIL_LINES = {
    "S01": "Automatizaci\u00f3n de Procesos: lo que hoy tarda horas se hace en minutos \u2014 menos carga de trabajo y menor costo operativo sin contratar m\u00e1s personal",
    "S02": "Atenci\u00f3n al Cliente 24/7: clientes atendidos autom\u00e1ticamente a cualquier hora, sin pagar personal extra por guardia nocturna ni fines de semana",
    "S03": "Bot Secretaria con IA: gestiona agenda y citas autom\u00e1ticamente \u2014 libera horas de su recepcionista y reduce ausencias que cuestan dinero",
    "S04": "P\u00e1gina Web con IA: su negocio visible en Google 24/7 \u2014 m\u00e1s clientes que llegan solos, sin invertir en publicidad costosa",
    "S05": "Contenido Visual con IA: im\u00e1genes y videos profesionales en minutos \u2014 ahorra el costo de dise\u00f1ador o fot\u00f3grafo en cada publicaci\u00f3n",
    "S06": "Marketing con IA: publicidad que se optimiza sola \u2014 maximiza cada peso invertido y atrae clientes con menor costo por adquisici\u00f3n",
    "S07": "An\u00e1lisis de Mercado con IA: monitorea competencia y tendencias autom\u00e1ticamente \u2014 decisiones m\u00e1s inteligentes en menos tiempo sin investigaci\u00f3n manual",
    "S08": "Gesti\u00f3n Financiera con IA: reportes y proyecciones al d\u00eda sin trabajo manual \u2014 ahorra horas de captura y reduce errores costosos",
    "S09": "Visibilidad en Google: m\u00e1s clientes encuentran su negocio org\u00e1nicamente \u2014 tr\u00e1fico sin costo recurrente por cada clic",
    "S10": "Procesamiento de Documentos con IA: digitaliza y organiza documentos autom\u00e1ticamente \u2014 elimina horas de captura manual y el costo de errores humanos",
    "S11": "Audio Profesional con IA: m\u00fasica y locuciones para videos y anuncios en segundos \u2014 sin pagar a m\u00fasicos ni locutores externos",
    "S12": "Voz Digital con IA: locuciones profesionales para atenci\u00f3n al cliente \u2014 sin estudio de grabaci\u00f3n ni honorarios por sesi\u00f3n",
    "S13": "Avatares Digitales con IA: representantes virtuales que presentan sus servicios en video \u2014 sin costo de producci\u00f3n ni actores",
    "S14": "Consultor\u00eda en IA: identificamos exactamente d\u00f3nde la IA ahorra m\u00e1s tiempo y dinero en su negocio espec\u00edfico, con implementaci\u00f3n guiada",
    "S15": "Manejo de Inventario con IA: control de stock en tiempo real con alertas autom\u00e1ticas \u2014 menos mermas, menos p\u00e9rdidas y cero horas de conteo manual",
    "S16": "Asistente Virtual con Voz para Llamadas: atiende y realiza llamadas autom\u00e1ticamente con voz natural \u2014 ninguna llamada sin respuesta, sin contratar recepcionistas adicionales ni pagar horas extra",
    "S17": "Redes Sociales con IA: perfil profesional en Instagram y Facebook gestionado autom\u00e1ticamente \u2014 publicaciones, dise\u00f1o y respuestas sin dedicar tiempo a ello, y seguidores creciendo de forma org\u00e1nica",
}

# -- Lineas de servicio para WhatsApp (ID -> descripcion con enfasis en tiempo Y dinero)
# Formato compacto: nombre + "ahorra/reduce/elimina [tiempo] y [costo]" en ~12-15 palabras.
# Siempre mencionan AMBOS: ahorro de tiempo Y ahorro de dinero.
SERVICE_WA_LINES = {
    "S01": "Automatizaci\u00f3n de Procesos \u2014 lo que hoy tarda horas se hace en minutos, sin contratar personal extra",
    "S02": "Atenci\u00f3n al Cliente 24/7 \u2014 cero costo de personal nocturno o fines de semana, clientes atendidos a cualquier hora",
    "S03": "Bot Secretaria con IA \u2014 libera horas de su recepcionista y elimina ausencias que cuestan dinero",
    "S04": "P\u00e1gina Web con IA \u2014 m\u00e1s clientes llegan solos desde Google, sin pagar publicidad costosa",
    "S05": "Contenido Visual con IA \u2014 im\u00e1genes y videos profesionales en minutos, ahorra el costo de dise\u00f1ador y fot\u00f3grafo",
    "S06": "Marketing con IA \u2014 maximiza cada peso invertido en publicidad, m\u00e1s clientes a menor costo",
    "S07": "An\u00e1lisis de Mercado con IA \u2014 datos de competencia actualizados autom\u00e1ticamente, ahorra horas de investigaci\u00f3n manual",
    "S08": "Gesti\u00f3n Financiera con IA \u2014 reportes al d\u00eda sin trabajo manual, ahorra horas de captura y reduce errores costosos",
    "S09": "Visibilidad en Google \u2014 tr\u00e1fico sin costo recurrente, m\u00e1s clientes encuentran el negocio org\u00e1nicamente",
    "S10": "Procesamiento de Documentos con IA \u2014 elimina horas de captura manual y el costo de errores humanos",
    "S11": "Audio Profesional con IA \u2014 m\u00fasica y anuncios en segundos, sin pagar m\u00fasicos ni locutores externos",
    "S12": "Voz Digital con IA \u2014 locuciones profesionales sin estudio de grabaci\u00f3n ni honorarios por sesi\u00f3n",
    "S13": "Avatares Digitales con IA \u2014 representantes en video sin costo de producci\u00f3n ni actores contratados",
    "S14": "Consultor\u00eda en IA \u2014 identificamos exactamente d\u00f3nde la IA ahorra m\u00e1s tiempo y dinero en su negocio espec\u00edfico",
    "S15": "Manejo de Inventario con IA \u2014 elimina mermas, p\u00e9rdidas y horas de conteo manual, stock controlado autom\u00e1ticamente",
    "S16": "Asistente con Voz para Llamadas \u2014 ninguna llamada sin respuesta, sin contratar recepcionistas adicionales ni pagar horas extra",
    "S17": "Redes Sociales con IA \u2014 sin dedicar tiempo a publicar ni responder, presencia y seguidores creciendo autom\u00e1ticamente",
}

# -- Parrafo diferenciador de la agencia (incluido en todos los emails) -------------------
EMAIL_DIFFERENTIATOR = (
    "Trabajamos exclusivamente con negocios locales en M\u00e9xico. "
    "No vendemos software gen\u00e9rico: implementamos soluciones adaptadas "
    "a su operaci\u00f3n, de forma pr\u00e1ctica y sin tecnicismos."
)

# -- CTAs de email (4 variantes) -------------------------------------------------------
EMAIL_CTAS = [
    "\u00bfLes gustar\u00eda agendar una llamada de 15 minutos sin costo para ver c\u00f3mo funciona esto para su negocio espec\u00edfico?",
    "\u00bfPodr\u00edamos agendar 15 minutos esta semana para mostrarles c\u00f3mo funciona, sin ning\u00fan compromiso?",
    "\u00bfLes interesar\u00eda una demostraci\u00f3n gratuita adaptada a su tipo de negocio? No tiene costo ni compromiso.",
    "Estamos disponibles esta semana para una llamada de 15 minutos donde les mostramos resultados concretos para su sector.",
]

# -- Intros de la lista de servicios en email (4 variantes, mismos indices que CTAs) --
# Misma idea que en WhatsApp: enfatizar tiempo y dinero, pero con frases distintas.
EMAIL_SERVICES_INTROS = [
    "Estos son los servicios que a {name} le pueden ahorrar mucho dinero y grandes cantidades de tiempo:",
    "Aqu\u00ed lo que podemos implementar para que {name} reduzca costos y libere horas de trabajo:",
    "Identificamos los servicios con mayor potencial de ahorro de tiempo y dinero para {name}:",
    "Esto es lo que podemos hacer para que {name} gaste menos y trabaje de forma m\u00e1s eficiente:",
]

# -- Hooks de WhatsApp por categoria (solo greeting + "Sabias que?", sin CTA) --------
# El metodo _build_whatsapp() agrega los servicios y el cierre de forma dinamica,
# asi todos los mensajes incluyen los servicios relevantes para ese negocio especifico.
WHATSAPP_HOOKS = {
    "restaurant": [
        "Hola {name} \U0001f37d\ufe0f \u00bfSab\u00eda que el 67% de los clientes que no reciben respuesta en menos de 5 minutos elige al restaurante que s\u00ed contest\u00f3?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que el 80% de los comensales consulta Google Maps antes de salir a comer \u2014 y que los restaurantes con atenci\u00f3n r\u00e1pida reciben hasta 30% m\u00e1s reservaciones?",
        "Hola {name} \U0001f37d\ufe0f \u00bfSab\u00eda que los restaurantes que responden mensajes autom\u00e1ticamente fuera de horario retienen hasta un 25% m\u00e1s clientes habituales?",
    ],
    "gym": [
        "Hola {name} \U0001f4aa \u00bfSab\u00eda que el 40% de los socios que no renuevan membres\u00eda lo hacen simplemente porque nadie les record\u00f3 a tiempo \u2014 no porque no quieran seguir?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que un gimnasio pierde en promedio entre 20-30% de socios cada trimestre \u2014 y que la mayor\u00eda se recuperar\u00eda con un recordatorio oportuno?",
        "Hola {name} \U0001f3cb\ufe0f \u00bfSab\u00eda que los gimnasios que env\u00edan recordatorios autom\u00e1ticos retienen hasta un 25% m\u00e1s socios por mes, sin llamadas manuales ni trabajo extra?",
    ],
    "beauty_salon": [
        "Hola {name} \U0001f485 \u00bfSab\u00eda que el 35% de las ausencias en salones de belleza se evitar\u00edan simplemente con un recordatorio autom\u00e1tico el d\u00eda anterior?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que cada cita vac\u00eda en un sal\u00f3n representa entre $500 y $800 de ingreso perdido \u2014 y que la mayor\u00eda ocurre por falta de confirmaci\u00f3n oportuna?",
        "Hola {name} \u2728 \u00bfSab\u00eda que los salones que automatizan confirmaciones reducen ausencias hasta un 40% desde el primer mes?",
    ],
    "doctor": [
        "Hola {name} \U0001f3e5 \u00bfSab\u00eda que entre el 20-30% de las citas m\u00e9dicas terminan en ausencia \u2014 y que el 80% de esos pacientes simplemente olvidaron porque nadie les record\u00f3?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que el equipo de recepci\u00f3n promedio dedica hasta 3 horas al d\u00eda solo a confirmar citas \u2014 tiempo que podr\u00eda usarse en atenci\u00f3n real a pacientes?",
        "Hola {name} \U0001f3e5 \u00bfSab\u00eda que los consultorios que automatizan recordatorios reducen ausencias hasta un 40% y liberan horas de recepci\u00f3n desde el primer mes?",
    ],
    "dentist": [
        "Hola {name} \U0001f9b7 \u00bfSab\u00eda que un sill\u00f3n dental vac\u00edo por ausencia representa entre $800 y $2,000 de ingreso perdido \u2014 y que el 75% de esas ausencias se evitar\u00edan con un recordatorio autom\u00e1tico?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que el 30% de los pacientes que no agendan seguimiento simplemente olvidaron \u2014 no porque no quieran regresar a su cl\u00ednica de confianza?",
        "Hola {name} \U0001f9b7 \u00bfSab\u00eda que las cl\u00ednicas que automatizan confirmaciones de cita llenan hasta el 95% de su agenda cada semana, sin llamar a cada paciente manualmente?",
    ],
    "lawyer": [
        "Hola {name} \u2696\ufe0f \u00bfSab\u00eda que el 70% de los prospectos que buscan asesor\u00eda legal contratan al primer despacho que les responde \u2014 no necesariamente al m\u00e1s experimentado?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que un prospecto legal sin respuesta en las primeras 24 horas tiene 5 veces m\u00e1s probabilidad de ir a la competencia?",
        "Hola {name} \u2696\ufe0f \u00bfSab\u00eda que los despachos que responden prospectos autom\u00e1ticamente convierten hasta un 35% m\u00e1s consultas en clientes reales?",
    ],
    "accounting": [
        "Hola {name} \U0001f4ca \u00bfSab\u00eda que el 60% de los clientes que cambian de contador lo hacen porque sienten que no reciben informaci\u00f3n oportuna \u2014 no por el precio?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que los despachos que ofrecen reportes autom\u00e1ticos y alertas fiscales retienen hasta un 40% m\u00e1s clientes que los que solo entregan reportes mensuales?",
        "Hola {name} \U0001f4ca \u00bfSab\u00eda que los contadores que usan IA para reportes autom\u00e1ticos atienden hasta el doble de clientes sin aumentar personal?",
    ],
    "real_estate_agency": [
        "Hola {name} \U0001f3e0 \u00bfSab\u00eda que el 80% de los prospectos inmobiliarios que no reciben respuesta el mismo d\u00eda terminan cerrando con otra agencia \u2014 aunque la suya fuera la mejor opci\u00f3n?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que responder un lead inmobiliario en menos de 5 minutos aumenta la probabilidad de cierre en un 400% comparado con responder una hora despu\u00e9s?",
        "Hola {name} \U0001f3e1 \u00bfSab\u00eda que las inmobiliarias que automatizan seguimiento a leads cierran hasta un 35% m\u00e1s operaciones sin aumentar su equipo?",
    ],
    "car_dealer": [
        "Hola {name} \U0001f697 \u00bfSab\u00eda que el 64% de los compradores de autos contacta m\u00e1s de una agencia al mismo tiempo \u2014 y la que responde primero es la que casi siempre cierra la venta?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que el prospecto promedio que busca un auto espera respuesta en menos de 1 hora \u2014 y si no la recibe, llama a la siguiente agencia de la lista?",
        "Hola {name} \U0001f698 \u00bfSab\u00eda que las agencias que automatizan seguimiento a prospectos con IA venden hasta un 30% m\u00e1s sin aumentar su equipo?",
    ],
    "hotel": [
        "Hola {name} \U0001f3e8 \u00bfSab\u00eda que el 57% de los viajeros que no reciben respuesta inmediata reservan en otra plataforma en menos de 10 minutos?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que los hoteles que responden consultas en menos de 5 minutos tienen hasta un 40% m\u00e1s reservaciones directas \u2014 sin pagar comisi\u00f3n a plataformas externas?",
        "Hola {name} \U0001f3e8 \u00bfSab\u00eda que una reservaci\u00f3n directa genera al hotel entre 15-25% m\u00e1s ingreso que la misma reservaci\u00f3n por Booking o Airbnb?",
    ],
    "veterinary_care": [
        "Hola {name} \U0001f43e \u00bfSab\u00eda que el 45% de los due\u00f1os de mascotas que no reciben recordatorio de vacuna simplemente lo posponen \u2014 y muchos terminan yendo a otra cl\u00ednica?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que las cl\u00ednicas veterinarias que env\u00edan recordatorios autom\u00e1ticos retienen hasta un 30% m\u00e1s pacientes cada a\u00f1o, sin llamadas manuales?",
        "Hola {name} \U0001f43e \u00bfSab\u00eda que el due\u00f1o de mascota promedio regresa a la cl\u00ednica de confianza cuando alguien se lo recuerda \u2014 pero el 45% nunca recibe ese recordatorio?",
    ],
    "pharmacy": [
        "Hola {name} \U0001f48a \u00bfSab\u00eda que el cliente de farmacia que recibe un recordatorio personalizado de su medicamento visita la farmacia un 35% m\u00e1s frecuente?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que el 60% de los pacientes con tratamientos cr\u00f3nicos cambia de farmacia no por precio, sino porque ninguna les hace seguimiento?",
        "Hola {name} \U0001f48a \u00bfSab\u00eda que las farmacias que personalizan comunicaci\u00f3n con IA aumentan ventas recurrentes sin invertir en publicidad?",
    ],
    "school": [
        "Hola {name} \U0001f393 \u00bfSab\u00eda que el 70% de los padres que no reciben comunicaci\u00f3n oportuna empiezan a considerar cambiar a sus hijos a otra instituci\u00f3n?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que el \u00e1rea administrativa de la mayor\u00eda de escuelas dedica hasta un 40% de su tiempo solo a responder las mismas preguntas de padres?",
        "Hola {name} \U0001f393 \u00bfSab\u00eda que las instituciones que automatizan comunicaci\u00f3n con padres tienen en promedio un 25% menos deserci\u00f3n escolar?",
    ],
    "store": [
        "Hola {name} \U0001f6cd\ufe0f \u00bfSab\u00eda que el 76% de los consumidores busca en Google si una tienda tiene lo que necesita antes de salir de casa \u2014 y si no encuentran informaci\u00f3n, van a otra?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que las tiendas con venta en l\u00ednea generan en promedio el 40% de sus ingresos fuera del horario de apertura, sin costo fijo adicional?",
        "Hola {name} \U0001f6d2 \u00bfSab\u00eda que el cliente que busca sus productos en l\u00ednea un domingo y no puede comprarlos tiene menos del 20% de probabilidad de regresar el lunes?",
    ],
    "general": [
        "Hola {name} \U0001f4a1 \u00bfSab\u00eda que los negocios que automatizan su atenci\u00f3n al cliente ahorran en promedio 3 horas diarias de trabajo manual \u2014 tiempo que se convierte directamente en m\u00e1s ventas?",
        "Hola {name} \U0001f44b \u00bfSab\u00eda que el 80% de los clientes potenciales elige al negocio que les responde primero \u2014 no necesariamente al m\u00e1s barato ni al mejor?",
        "Hola {name} \U0001f680 \u00bfSab\u00eda que la mayor\u00eda de las p\u00e9rdidas de clientes en negocios locales no son por precio ni calidad \u2014 sino por falta de seguimiento oportuno?",
    ],
}

# -- Hooks de presencia digital para negocios SIN sitio web (S04 prioritario) --------
WHATSAPP_NO_WEBSITE_HOOKS = [
    "Hola {name} \U0001f30e \u00bfSab\u00eda que el 97% de los consumidores busca negocios locales en Google \u2014 y que sin sitio web, simplemente no aparecen en esa b\u00fasqueda?",
    "Hola {name} \U0001f44b \u00bfSab\u00eda que el negocio que aparece primero en Google recibe hasta 10 veces m\u00e1s visitas que el que no aparece \u2014 y sin sitio web, ni siquiera est\u00e1n en esa competencia?",
    "Hola {name} \U0001f30e \u00bfSab\u00eda que el 70% de los clientes que busca un negocio como el suyo en Google elige al primero que le da toda la informaci\u00f3n sin tener que llamar?",
]

# -- CTAs cortos para mensajes de WhatsApp (3 variantes, mismos indices que hooks) ----
WHATSAPP_SHORT_CTAS = [
    "Somos el Departamento de IA de [NOMBRE_AGENCIA]. \u00bfLes contamos c\u00f3mo en 15 min sin costo? \U0001f680",
    "Somos el Departamento de IA de [NOMBRE_AGENCIA]. \u00bfPlaticamos esta semana? Sin costo ni compromiso \U0001f60a",
    "Somos el Departamento de IA de [NOMBRE_AGENCIA]. \u00bfHablamos 15 min? Sin compromiso \U0001f4ac",
]

# -- Intros de la lista de servicios (3 variantes, rotan por variacion) ---------------
# Transmiten la misma idea — tiempo y dinero ahorrado — pero con frases distintas
# para que los mensajes no suenen identicos entre si.
WHATSAPP_SERVICES_INTROS = [
    "Estos son los servicios que a {name} le pueden ahorrar mucho dinero y grandes cantidades de tiempo:",
    "Aqu\u00ed lo que podemos hacer para que {name} reduzca costos y libere horas de trabajo:",
    "Identificamos los servicios con mayor potencial de ahorro de tiempo y dinero para {name}:",
]

# -- Frase de cierre invitando a conocer más servicios (3 variantes) ------------------
# Va justo antes del CTA — recuerda al prospecto que hay más opciones disponibles.
SERVICES_TEASER = [
    "Y si alguno de estos servicios les llama la atención, o quieren conocer nuestra lista completa, con gusto les platicamos más.",
    "Estos son solo los que más aplican para su tipo de negocio — tenemos más soluciones disponibles si quieren conocerlas.",
    "Si quieren ver todo lo que podemos hacer por su negocio, no duden en escribirnos — la lista es más amplia de lo que cabe aquí.",
]

# -- Hooks "Sabias que" para mensajes extendidos (negocios sin email) -----------------
# Primera oracion tipo dato/pregunta que genera curiosidad y toca la debilidad,
# especifica al tipo de negocio. Aparece en los primeros ~300 chars antes del "Ver mas..."
WHATSAPP_EXTENDED_HOOKS = {
    "restaurant": [
        "\u00bfSab\u00eda que el 67% de los clientes que no reciben respuesta r\u00e1pida elige al restaurante que s\u00ed contest\u00f3 \u2014 y que muchos nunca vuelven a intentarlo?",
        "\u00bfSab\u00eda que el 80% de los comensales revisa Google Maps antes de salir a comer, y que los restaurantes con atenci\u00f3n r\u00e1pida reciben hasta un 30% m\u00e1s reservaciones?",
        "\u00bfSab\u00eda que los restaurantes que responden mensajes autom\u00e1ticamente fuera de horario retienen hasta un 25% m\u00e1s clientes habituales?",
    ],
    "gym": [
        "\u00bfSab\u00eda que el 40% de los socios que no renuevan membres\u00eda lo hicieron simplemente porque nadie les record\u00f3 a tiempo \u2014 no porque no quisieran seguir?",
        "\u00bfSab\u00eda que un gimnasio pierde en promedio entre 20-30% de sus socios cada trimestre, y que la mayor\u00eda se recuperar\u00eda con un recordatorio oportuno?",
        "\u00bfSab\u00eda que los gimnasios que env\u00edan recordatorios autom\u00e1ticos de renovaci\u00f3n retienen hasta un 25% m\u00e1s socios por mes, sin llamadas manuales ni trabajo extra?",
    ],
    "beauty_salon": [
        "\u00bfSab\u00eda que el 35% de las ausencias en salones de belleza se evitar\u00edan simplemente con un recordatorio autom\u00e1tico enviado el d\u00eda anterior?",
        "\u00bfSab\u00eda que cada cita vac\u00eda en un sal\u00f3n representa entre $500 y $800 de ingreso perdido \u2014 y que la mayor\u00eda ocurre por falta de confirmaci\u00f3n oportuna?",
        "\u00bfSab\u00eda que los salones que automatizan confirmaciones y recordatorios reducen ausencias hasta en un 40% desde el primer mes?",
    ],
    "doctor": [
        "\u00bfSab\u00eda que entre el 20-30% de las citas m\u00e9dicas terminan en ausencia, y que el 80% de esos pacientes simplemente olvidaron porque nadie les record\u00f3?",
        "\u00bfSab\u00eda que el equipo de recepci\u00f3n promedio dedica hasta 3 horas al d\u00eda solo a confirmar citas \u2014 tiempo que podr\u00eda dedicarse a atenci\u00f3n real a pacientes?",
        "\u00bfSab\u00eda que los consultorios que automatizan recordatorios reducen ausencias hasta un 40% y liberan horas de recepci\u00f3n desde el primer mes?",
    ],
    "dentist": [
        "\u00bfSab\u00eda que un sill\u00f3n dental vac\u00edo por ausencia representa entre $800 y $2,000 de ingreso perdido \u2014 y que el 75% de esas ausencias se evitar\u00edan con un recordatorio autom\u00e1tico?",
        "\u00bfSab\u00eda que el 30% de los pacientes que no agendan cita de seguimiento simplemente olvidaron \u2014 no porque no quieran regresar a su cl\u00ednica de confianza?",
        "\u00bfSab\u00eda que las cl\u00ednicas dentales que automatizan confirmaciones de cita llenan hasta el 95% de su agenda cada semana?",
    ],
    "lawyer": [
        "\u00bfSab\u00eda que el 70% de los prospectos que buscan asesor\u00eda legal contratan al primer despacho que les responde \u2014 no necesariamente al m\u00e1s experimentado?",
        "\u00bfSab\u00eda que un prospecto legal sin respuesta en las primeras 24 horas tiene 5 veces m\u00e1s probabilidad de ir a la competencia \u2014 aunque su despacho sea la mejor opci\u00f3n?",
        "\u00bfSab\u00eda que los despachos que responden prospectos autom\u00e1ticamente convierten hasta un 35% m\u00e1s consultas en clientes reales?",
    ],
    "accounting": [
        "\u00bfSab\u00eda que el 60% de los clientes que cambian de contador lo hacen porque sienten que no reciben informaci\u00f3n oportuna \u2014 no por el precio ni la calidad?",
        "\u00bfSab\u00eda que los despachos contables que ofrecen reportes autom\u00e1ticos y alertas fiscales retienen hasta un 40% m\u00e1s clientes que los que solo entregan reportes mensuales?",
        "\u00bfSab\u00eda que los contadores que usan IA para reportes autom\u00e1ticos atienden hasta el doble de clientes sin aumentar personal \u2014 y cobran m\u00e1s por el valor que entregan?",
    ],
    "real_estate_agency": [
        "\u00bfSab\u00eda que el 80% de los prospectos inmobiliarios que no reciben respuesta el mismo d\u00eda terminan cerrando con otra agencia \u2014 aunque la suya fuera la mejor opci\u00f3n?",
        "\u00bfSab\u00eda que responder un lead inmobiliario en menos de 5 minutos aumenta la probabilidad de cierre en un 400% comparado con responder una hora despu\u00e9s?",
        "\u00bfSab\u00eda que las inmobiliarias que automatizan el seguimiento a leads cierran hasta un 35% m\u00e1s operaciones sin aumentar su equipo de ventas?",
    ],
    "car_dealer": [
        "\u00bfSab\u00eda que el 64% de los compradores de autos contacta m\u00e1s de una agencia al mismo tiempo \u2014 y la que responde primero es la que casi siempre cierra la venta?",
        "\u00bfSab\u00eda que el prospecto promedio que busca un auto en l\u00ednea espera respuesta en menos de 1 hora \u2014 y si no la recibe, llama a la siguiente agencia de la lista?",
        "\u00bfSab\u00eda que las agencias que automatizan seguimiento a prospectos con IA venden hasta un 30% m\u00e1s sin aumentar su equipo de ventas?",
    ],
    "hotel": [
        "\u00bfSab\u00eda que el 57% de los viajeros que no reciben respuesta inmediata reservan en otra plataforma en menos de 10 minutos \u2014 y que esa reservaci\u00f3n pudo ser directa?",
        "\u00bfSab\u00eda que los hoteles que responden consultas en menos de 5 minutos tienen hasta un 40% m\u00e1s reservaciones directas sin pagar comisi\u00f3n a plataformas externas?",
        "\u00bfSab\u00eda que una reservaci\u00f3n directa genera al hotel entre 15-25% m\u00e1s ingreso que la misma reservaci\u00f3n por Booking o Airbnb?",
    ],
    "veterinary_care": [
        "\u00bfSab\u00eda que el 45% de los due\u00f1os de mascotas que no reciben recordatorio de vacuna simplemente lo posponen \u2014 y muchos terminan yendo a otra cl\u00ednica?",
        "\u00bfSab\u00eda que las cl\u00ednicas veterinarias que env\u00edan recordatorios autom\u00e1ticos de vacunas y revisiones retienen hasta un 30% m\u00e1s pacientes cada a\u00f1o?",
        "\u00bfSab\u00eda que el due\u00f1o de mascota promedio regresa a la cl\u00ednica de confianza cuando alguien se lo recuerda \u2014 pero el 45% no regresa porque nadie le record\u00f3?",
    ],
    "pharmacy": [
        "\u00bfSab\u00eda que el cliente de farmacia que recibe un recordatorio personalizado de su medicamento visita la farmacia un 35% m\u00e1s frecuente que los que no lo reciben?",
        "\u00bfSab\u00eda que el 60% de los pacientes con tratamientos cr\u00f3nicos cambia de farmacia no por precio, sino porque ninguna les hace seguimiento ni les recuerda?",
        "\u00bfSab\u00eda que las farmacias que personalizan la comunicaci\u00f3n con sus clientes con IA aumentan ventas recurrentes sin necesidad de invertir en publicidad?",
    ],
    "school": [
        "\u00bfSab\u00eda que el 70% de los padres que no reciben comunicaci\u00f3n oportuna de la escuela empiezan a considerar cambiar a sus hijos a otra instituci\u00f3n al a\u00f1o siguiente?",
        "\u00bfSab\u00eda que el \u00e1rea administrativa de la mayor\u00eda de las escuelas dedica hasta un 40% de su tiempo solo a responder las mismas preguntas de padres de familia?",
        "\u00bfSab\u00eda que las instituciones que automatizan la comunicaci\u00f3n con padres tienen en promedio un 25% menos deserci\u00f3n escolar al a\u00f1o?",
    ],
    "store": [
        "\u00bfSab\u00eda que el 76% de los consumidores busca en Google si una tienda tiene lo que necesita antes de salir de casa \u2014 y si no encuentran informaci\u00f3n, van a otra tienda?",
        "\u00bfSab\u00eda que las tiendas con venta en l\u00ednea generan en promedio el 40% de sus ingresos fuera del horario de apertura f\u00edsica, sin costo fijo adicional?",
        "\u00bfSab\u00eda que el cliente que busca sus productos en l\u00ednea un domingo y no puede comprarlos tiene menos del 20% de probabilidad de regresar el lunes?",
    ],
    "general": [
        "\u00bfSab\u00eda que los negocios que automatizan su atenci\u00f3n al cliente ahorran en promedio 3 horas diarias de trabajo manual \u2014 tiempo que se convierte directamente en m\u00e1s ventas?",
        "\u00bfSab\u00eda que el 80% de los clientes potenciales elige al negocio que les responde primero \u2014 no necesariamente al m\u00e1s barato ni al de mejor calidad?",
        "\u00bfSab\u00eda que la mayor\u00eda de las p\u00e9rdidas de clientes en negocios locales no son por precio ni calidad \u2014 sino por falta de seguimiento o respuesta oportuna?",
    ],
}


# -- Guiones de llamada telefónica por categoría (3 variantes) -------------------------
# Formato legible en voz alta: [indicaciones entre corchetes], pausas naturales.
# Orden: saludo → presentación → dato de industria → beneficio → CTA.
PHONE_HOOKS = {
    "restaurant": [
        "Le llamamos porque el 67% de los clientes que no reciben respuesta en menos de 5 minutos elige al restaurante que sí contestó. Nosotros ayudamos a restaurantes como el suyo a nunca perder esa oportunidad — sin contratar personal extra.",
        "Le llamamos porque el 80% de los comensales consulta Google Maps antes de salir a comer, y los restaurantes con atención rápida reciben hasta 30% más reservaciones. Ayudamos a restaurantes a automatizar esa atención sin tecnicismos.",
        "Le llamamos porque los restaurantes que automatizan su atención retienen hasta un 25% más clientes habituales. Trabajamos con negocios como el suyo para lograrlo desde el primer mes.",
    ],
    "gym": [
        "Le llamamos porque el 60% de los socios de gimnasio que no reciben seguimiento en las primeras dos semanas no renueva su membresía. Ayudamos a gimnasios a automatizar ese seguimiento sin carga extra para su equipo.",
        "Le llamamos porque los gimnasios que responden consultas en menos de 5 minutos convierten hasta 3 veces más prospectos. Trabajamos con gimnasios para que ninguna consulta quede sin respuesta.",
        "Le llamamos porque el 70% de quienes buscan gimnasio en línea elige al que responde más rápido, no necesariamente al más cercano. Ayudamos a gimnasios a ser ese negocio que siempre responde.",
    ],
    "beauty_salon": [
        "Le llamamos porque el 65% de los clientes de belleza que no reciben confirmación de cita la cancela o no se presenta. Ayudamos a salones a automatizar confirmaciones y recordatorios sin costo de personal adicional.",
        "Le llamamos porque los salones con reservaciones en línea tienen hasta un 40% menos cancelaciones de último minuto. Trabajamos con salones para implementar eso sin complicaciones técnicas.",
        "Le llamamos porque el 75% de los clientes de belleza prefiere agendar por WhatsApp o en línea antes que llamar. Ayudamos a salones a captar esos clientes que de otra forma se van con la competencia.",
    ],
    "doctor": [
        "Le llamamos porque el 55% de los pacientes que no pueden agendar cita en línea busca otro médico ese mismo día. Ayudamos a consultorios a nunca perder un paciente por falta de disponibilidad inmediata.",
        "Le llamamos porque los consultorios con recordatorios automáticos reducen sus citas perdidas hasta en un 40%. Trabajamos con médicos para implementar eso sin modificar su flujo de trabajo.",
        "Le llamamos porque el 70% de los pacientes nuevos elige al médico que le respondió primero. Ayudamos a consultorios a ser siempre el primero en responder, incluso fuera de horario.",
    ],
    "dentist": [
        "Le llamamos porque el 60% de los pacientes dentales que no reciben recordatorio no se presenta a su cita. Ayudamos a clínicas dentales a reducir ese ausentismo con recordatorios automáticos.",
        "Le llamamos porque las clínicas dentales con confirmación automática de cita ahorran en promedio 3 horas de llamadas manuales por semana. Trabajamos con dentistas para implementar eso sin complicaciones.",
        "Le llamamos porque el 65% de los pacientes nuevos elige al dentista que les respondió primero en línea. Ayudamos a clínicas a captar esos pacientes sin esfuerzo adicional.",
    ],
    "lawyer": [
        "Le llamamos porque el 70% de los clientes potenciales de servicios legales contacta a varios despachos y elige al que responde primero. Ayudamos a despachos a nunca perder esa ventana de oportunidad.",
        "Le llamamos porque los despachos que dan seguimiento automatizado a prospectos convierten hasta un 35% más casos. Trabajamos con abogados para implementar ese seguimiento sin carga administrativa.",
        "Le llamamos porque el 65% de quienes buscan asesoría legal en línea toma una decisión en las primeras 24 horas. Ayudamos a despachos a responder en minutos, no en días.",
    ],
    "accounting": [
        "Le llamamos porque los despachos contables que automatizan su comunicación con clientes reducen hasta un 50% las llamadas de seguimiento repetitivas. Ayudamos a contadores a liberar ese tiempo para trabajo que sí genera valor.",
        "Le llamamos porque el 60% de las empresas cambia de contador por falta de comunicación oportuna, no por precio. Trabajamos con despachos para que sus clientes siempre reciban respuesta a tiempo.",
        "Le llamamos porque los despachos contables con procesos automatizados atienden hasta un 40% más clientes sin contratar personal extra. Ayudamos a contadores a escalar sin escalar sus costos.",
    ],
    "real_estate_agency": [
        "Le llamamos porque el 80% de los compradores de inmueble contacta a varias agencias y elige a la que responde más rápido. Ayudamos a inmobiliarias a nunca ser la segunda en responder.",
        "Le llamamos porque las inmobiliarias que dan seguimiento automático a prospectos cierran hasta un 45% más operaciones. Trabajamos con agencias para implementar ese seguimiento sin esfuerzo manual.",
        "Le llamamos porque el 70% de los prospectos inmobiliarios se enfría si no recibe respuesta en las primeras 2 horas. Ayudamos a agencias a responder en segundos, no en horas.",
    ],
    "car_dealer": [
        "Le llamamos porque el 75% de los compradores de auto visita la agencia que le respondió primero en línea. Ayudamos a agencias automotrices a captar esos clientes antes que la competencia.",
        "Le llamamos porque las agencias que automatizan el seguimiento de prospectos venden hasta un 30% más unidades sin aumentar su equipo de ventas. Trabajamos con concesionarias para implementar eso.",
        "Le llamamos porque el 65% de los prospectos automotrices abandona si no recibe respuesta en menos de una hora. Ayudamos a agencias a nunca perder una venta por tiempo de respuesta.",
    ],
    "hotel": [
        "Le llamamos porque el 70% de los viajeros que no recibe confirmación inmediata cancela y busca otro hotel. Ayudamos a hoteles a automatizar esa confirmación sin carga para su recepción.",
        "Le llamamos porque los hoteles con atención automatizada fuera de horario reciben hasta un 25% más reservaciones directas. Trabajamos con hoteles para captar esas reservaciones que de otra forma van a OTAs.",
        "Le llamamos porque el 65% de los huéspedes decide su hotel basándose en velocidad de respuesta y disponibilidad de información en línea. Ayudamos a hoteles a ser siempre la mejor opción.",
    ],
    "veterinary_care": [
        "Le llamamos porque el 60% de los dueños de mascotas que no pueden agendar cita en línea busca otra veterinaria ese mismo día. Ayudamos a clínicas veterinarias a nunca perder un paciente por disponibilidad.",
        "Le llamamos porque las veterinarias con recordatorios automáticos de vacunas y citas retienen hasta un 35% más clientes habituales. Trabajamos con veterinarios para implementar eso sin complicaciones.",
        "Le llamamos porque el 70% de los dueños de mascotas prefiere comunicarse por WhatsApp antes que llamar. Ayudamos a veterinarias a atender esa demanda sin personal adicional.",
    ],
    "pharmacy": [
        "Le llamamos porque las farmacias con recordatorios automáticos de medicamentos crónicos tienen hasta un 40% más compras recurrentes. Ayudamos a farmacias a generar esa lealtad sin esfuerzo manual.",
        "Le llamamos porque el 65% de los clientes de farmacia elige la que le ofrece información y disponibilidad en línea. Trabajamos con farmacias para tener esa presencia sin inversión en infraestructura costosa.",
        "Le llamamos porque las farmacias que automatizan su comunicación con clientes habituales reducen hasta un 50% las llamadas de consulta repetitivas. Ayudamos a farmacias a liberar ese tiempo.",
    ],
    "school": [
        "Le llamamos porque el 70% de los padres que busca escuela elige a la que le respondió primero con información completa. Ayudamos a instituciones educativas a nunca perder un prospecto por falta de respuesta oportuna.",
        "Le llamamos porque las escuelas con comunicación automatizada con padres reducen hasta un 60% las llamadas de seguimiento repetitivas. Trabajamos con instituciones para implementar eso sin carga para su administración.",
        "Le llamamos porque el 65% de los padres prefiere recibir información escolar por WhatsApp antes que por correo o llamada. Ayudamos a escuelas a comunicarse como sus familias esperan.",
    ],
    "store": [
        "Le llamamos porque el 75% de los compradores en línea elige la tienda que responde primero sus preguntas. Ayudamos a tiendas a nunca perder una venta por tiempo de respuesta.",
        "Le llamamos porque las tiendas con atención automatizada por WhatsApp tienen hasta un 35% más conversiones de consulta a compra. Trabajamos con comercios para implementar eso sin contratar personal.",
        "Le llamamos porque el 70% de los clientes que no recibe respuesta inmediata compra en la competencia ese mismo día. Ayudamos a tiendas a retener esos clientes con atención instantánea.",
    ],
    "general": [
        "Le llamamos porque el 75% de los clientes potenciales elige al negocio que le responde primero, no necesariamente al mejor o al más barato. Ayudamos a negocios como el suyo a ser siempre el primero en responder.",
        "Le llamamos porque los negocios que automatizan su atención al cliente ahorran en promedio 15 horas semanales de trabajo repetitivo. Trabajamos con negocios locales para liberar ese tiempo.",
        "Le llamamos porque el 70% de las pérdidas de clientes en negocios locales no son por precio ni calidad, sino por falta de seguimiento oportuno. Ayudamos a negocios a eliminar esa fuga.",
    ],
}

PHONE_CTAS = [
    "¿Tendría 15 minutos esta semana para una llamada rápida donde le mostramos exactamente cómo funciona para su negocio?\n\n[Si acepta] Perfecto, ¿cuándo le viene mejor — mañana o pasado?\n[Si está ocupado] No hay problema, ¿cuándo sería un buen momento para marcarle?",
    "¿Le interesaría que le mostremos cómo funciona esto específicamente para su negocio? No toma más de 15 minutos y no tiene ningún costo.\n\n[Si acepta] Excelente, ¿esta semana o la próxima le queda mejor?\n[Si está ocupado] Entiendo perfectamente, ¿a qué hora del día le es más cómodo que le llame?",
    "¿Podríamos agendar 15 minutos esta semana para mostrarle el impacto real que esto tendría en su operación? Sin costo ni compromiso.\n\n[Si acepta] Perfecto, ¿mañana por la mañana o por la tarde le funciona mejor?\n[Si está ocupado] Con gusto le llamo cuando sea mejor momento, ¿cuándo le viene bien?",
]


class LocalProposalGenerator:
    """
    Genera propuestas personalizadas de email y WhatsApp sin usar APIs externas.
    Email: 160-190 palabras con observacion empatica + diferenciador de la agencia + servicios.
    WhatsApp: 70-90 palabras, template completo por categoria, tono casual y empatico.
    """

    def __init__(
        self, catalog: ServiceCatalog, agency_contact: str, agency_name: str = "[NOMBRE_AGENCIA]"
    ) -> None:
        """
        Args:
            catalog: Catalogo de servicios de la agencia.
            agency_contact: Texto con datos de contacto formateados (telefono, email, etc.)
            agency_name: Nombre de la agencia (AGENCY_NAME); sustituye [NOMBRE_AGENCIA].
        """
        self.catalog = catalog
        self.agency_contact = agency_contact
        self.agency_name = agency_name

    def generate(self, prospect: "Prospect") -> tuple[str, str, str, list[str]]:
        """
        Genera email, mensaje de WhatsApp y guion de llamada para un prospecto.

        Args:
            prospect: Objeto Prospect con name, category, website, rating, review_count, etc.

        Returns:
            Tupla (email_text, whatsapp_text, phone_script, service_ids).
        """
        has_website = bool(getattr(prospect, "website", None))
        has_social_media = bool(
            getattr(prospect, "instagram_url", None) or getattr(prospect, "facebook_url", None)
        )

        # Seleccionar servicios relevantes (S04 prioridad sin web, S17 sin redes sociales)
        services = self.catalog.get_services_for_category(
            prospect.category,
            count=3,
            has_website=has_website,
            has_social_media=has_social_media,
        )
        service_ids = self.catalog.get_service_ids(services)

        # Indice de variante basado en el nombre del negocio (consistente entre ejecuciones)
        name_bytes = sum(ord(c) for c in (prospect.name or ""))
        variation = name_bytes % 3

        email = self._build_email(prospect, services, variation)
        whatsapp = self._build_whatsapp(prospect, services, variation)
        phone = self._build_phone_script(prospect, services, variation)

        if self.agency_name and "[" not in self.agency_name:
            email, whatsapp, phone = (
                t.replace("[NOMBRE_AGENCIA]", self.agency_name) for t in (email, whatsapp, phone)
            )

        return email, whatsapp, phone, service_ids

    # -- Construccion de EMAIL -------------------------------------------------------

    def _build_email(self, prospect, services: list[dict], variation: int) -> str:
        """
        Construye el email personalizado (~160-190 palabras).
        Estructura: saludo -> observacion empatica -> diferenciador -> servicios -> hook -> CTA
        """
        name = prospect.name or "su negocio"
        cat = prospect.category or "general"
        cat_name = CATEGORY_NAMES.get(cat, "negocio")
        has_website = bool(getattr(prospect, "website", None))
        has_social_media = bool(
            getattr(prospect, "instagram_url", None) or getattr(prospect, "facebook_url", None)
        )
        rating = getattr(prospect, "rating", None)
        review_count = getattr(prospect, "review_count", None)

        # Opener empatico especifico al tipo de negocio
        openers = EMAIL_OPENERS.get(cat, EMAIL_OPENERS["general"])
        opener = openers[variation % len(openers)].format(name=name)

        # Bloque de servicios en formato "Nombre: que dolor resuelve"
        service_lines = []
        for s in services:
            sid = s.get("id", "")
            if sid in SERVICE_EMAIL_LINES:
                service_lines.append(f"\u2022 {SERVICE_EMAIL_LINES[sid]}")
            else:
                service_lines.append(f"\u2022 {s['name']}: {s['short_description']}")
        services_block = "\n".join(service_lines)

        # Hook de personalizacion (basado en datos reales del negocio)
        hook = self._build_email_hook(name, has_website, has_social_media, rating, review_count)

        # CTA y frase intro de servicios (rotan con la misma variacion)
        cta = EMAIL_CTAS[variation % len(EMAIL_CTAS)]
        services_intro = EMAIL_SERVICES_INTROS[variation % len(EMAIL_SERVICES_INTROS)].format(
            name=name
        )

        parts = [
            f"Estimado equipo de {name},",
            "",
            f"Somos el Departamento de IA de [NOMBRE_AGENCIA], especializados en soluciones para {cat_name}s. {EMAIL_DIFFERENTIATOR}",
            "",
            opener,
            "",
            services_intro,
            "",
            services_block,
        ]

        if hook:
            parts += ["", hook]

        teaser = SERVICES_TEASER[variation % len(SERVICES_TEASER)]

        parts += [
            "",
            teaser,
            "",
            cta,
            "",
            self.agency_contact,
            "",
            "Saludos cordiales,",
            "Departamento de IA | [NOMBRE_AGENCIA]",
        ]

        return "\n".join(parts)

    def _build_phone_script(self, prospect, services: list[dict], variation: int) -> str:
        """
        Construye el guión de llamada telefónica para el prospecto.
        Estructura: saludo → presentación → dato de industria → servicios clave → CTA con manejo de respuestas.
        """
        name = prospect.name or "su negocio"
        cat = prospect.category or "general"
        cat_name = CATEGORY_NAMES.get(cat, "negocio")
        has_website = bool(getattr(prospect, "website", None))

        hooks = PHONE_HOOKS.get(cat, PHONE_HOOKS["general"])
        hook = hooks[variation % len(hooks)]
        cta = PHONE_CTAS[variation % len(PHONE_CTAS)]

        # Servicios con descripción de beneficio (usando SERVICE_WA_LINES para mayor impacto)
        service_lines_phone = []
        for s in services[:2]:
            sid = s.get("id", "")
            wa_line = SERVICE_WA_LINES.get(sid, "")
            if wa_line and " — " in wa_line:
                svc_name, svc_benefit = wa_line.split(" — ", 1)
                service_lines_phone.append(f"{svc_name} ({svc_benefit})")
            else:
                service_lines_phone.append(s["name"])
        services_mention = (
            " y ".join(service_lines_phone) if service_lines_phone else "soluciones de IA"
        )

        ai_interest_phrases = [
            f"Me preguntaba si {name} está considerando implementar herramientas de inteligencia artificial en su operación.",
            f"Le llamamos para saber si {name} ha pensado en aprovechar la inteligencia artificial para mejorar su operación.",
            f"Quería preguntarle si en {name} han evaluado el uso de herramientas de IA para optimizar su negocio.",
        ]
        ai_interest = ai_interest_phrases[variation % len(ai_interest_phrases)]

        raw_phone = getattr(prospect, "phone", None) or ""
        if raw_phone:
            digits = "".join(c for c in raw_phone if c.isdigit())
            if digits.startswith("52") and len(digits) == 12:
                digits = digits[2:]
            if len(digits) == 10:
                phone_number = f"+52 {digits[0:2]} {digits[2:6]} {digits[6:10]}"
            else:
                phone_number = raw_phone
        else:
            phone_number = "Sin teléfono registrado"

        web_status = "Sin sitio web" if not has_website else "Tiene sitio web"

        # Formatear horario compacto agrupando días con el mismo horario
        hours_line = "Sin horario registrado"
        raw_hours = getattr(prospect, "hours", None)
        if raw_hours:
            try:
                hours_data = json.loads(raw_hours) if isinstance(raw_hours, str) else raw_hours
                weekday_text = hours_data.get("weekday_text", [])
                if weekday_text:
                    # Agrupar días consecutivos con el mismo horario
                    day_abbr = {
                        "lunes": "Lun",
                        "martes": "Mar",
                        "miércoles": "Mié",
                        "jueves": "Jue",
                        "viernes": "Vie",
                        "sábado": "Sáb",
                        "domingo": "Dom",
                    }
                    parsed = []
                    for entry in weekday_text:
                        if ": " in entry:
                            day, time = entry.split(": ", 1)
                            parsed.append((day_abbr.get(day.lower(), day), time))
                    # Comprimir: si todos igual → un rango; si no → agrupar consecutivos
                    groups = []
                    i = 0
                    while i < len(parsed):
                        j = i
                        while j + 1 < len(parsed) and parsed[j + 1][1] == parsed[i][1]:
                            j += 1
                        if i == j:
                            groups.append(f"{parsed[i][0]}: {parsed[i][1]}")
                        else:
                            groups.append(f"{parsed[i][0]}-{parsed[j][0]}: {parsed[i][1]}")
                        i = j + 1
                    hours_line = " | ".join(groups)
            except Exception:
                pass

        parts = [
            f"━━━ GUIÓN DE LLAMADA — {name.upper()} ━━━",
            f"📞 {phone_number}   ({web_status})",
            f"🕐 {hours_line}",
            "",
            f"Buenos días/tardes, ¿me comunico con {name}?",
            "",
            "[Esperan confirmación]",
            "",
            f"Mi nombre es [su nombre], le llamo de [NOMBRE_AGENCIA] — somos un departamento especializado en inteligencia artificial para {cat_name}s en México.",
            "",
            ai_interest,
            "",
            hook,
            "",
            f"En particular, podemos ayudarles con {services_mention} — todo implementado sin tecnicismos y con ahorro real desde el primer mes.",
            "",
            cta,
            "",
            "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━",
        ]
        return "\n".join(parts)

    def _build_email_hook(
        self,
        name: str,
        has_website: bool,
        has_social_media: bool,
        rating,
        review_count,
    ) -> str:
        """Construye el parrafo de personalizacion segun datos reales del negocio."""
        if not has_website:
            return (
                f"Tambi\u00e9n notamos que {name} a\u00fan no cuenta con sitio web. "
                f"Hoy el 80% de los clientes busca en Google antes de visitar un negocio \u2014 "
                f"una p\u00e1gina web inteligente puede ser su mejor vendedor disponible las 24 horas."
            )
        if not has_social_media:
            return (
                f"Tambi\u00e9n notamos que {name} no tiene presencia activa en Instagram ni Facebook. "
                f"El 78% de los consumidores revisa las redes sociales de un negocio antes de visitarlo \u2014 "
                f"un perfil bien gestionado con IA puede convertir esa b\u00fasqueda en una visita real, "
                f"sin que el equipo dedique tiempo a publicar o responder mensajes."
            )
        if rating and rating >= 4.5 and review_count and review_count >= 200:
            return (
                f"Su calificaci\u00f3n de {rating:.1f} estrellas con {review_count:,} rese\u00f1as en Google "
                f"demuestra la calidad de su servicio. La IA puede ayudarles a mantener ese est\u00e1ndar "
                f"y escalar su operaci\u00f3n sin necesitar m\u00e1s personal."
            )
        if rating and rating >= 4.0 and review_count and review_count >= 500:
            return (
                f"Con {review_count:,} rese\u00f1as en Google, {name} ya cuenta con una base s\u00f3lida "
                f"de clientes satisfechos. La tecnolog\u00eda puede convertir a\u00fan m\u00e1s de esas visitas "
                f"en clientes recurrentes de forma completamente autom\u00e1tica."
            )
        return ""

    # -- Construccion de WHATSAPP ----------------------------------------------------

    def _build_whatsapp(self, prospect, services: list[dict], variation: int) -> str:
        """
        Construye el mensaje de WhatsApp completo para todos los prospectos.
        WhatsApp es el canal principal de contacto — todos reciben el mismo
        formato completo independientemente de si tienen email o no.

        Estructura:
            "Hola {name} Somos el Departamento de IA de [NOMBRE_AGENCIA]..."
            [linea en blanco]
            "¿Sabía que [stat de su industria]?"  <- presentación primero, debilidad después
            [linea en blanco]
            {intro variado: "Estos son los servicios que le pueden ahorrar..."}
            • Servicio 1 — ahorra tiempo y dinero
            • Servicio 2 — ...
            • Servicio 3 — ...
            [linea en blanco]
            Todo implementado sin tecnicismos...
            [linea en blanco]
            CTA
            [linea en blanco]
            contacto
        """
        name = prospect.name or "su negocio"
        cat = prospect.category or "general"
        has_website = bool(getattr(prospect, "website", None))

        # Hook de apertura con saludo incluido (primeros ~250 chars antes del "Ver mas...")
        if not has_website:
            hook = WHATSAPP_NO_WEBSITE_HOOKS[variation % len(WHATSAPP_NO_WEBSITE_HOOKS)].format(
                name=name
            )
        else:
            hooks = WHATSAPP_HOOKS.get(cat, WHATSAPP_HOOKS["general"])
            hook = hooks[variation % len(hooks)].format(name=name)

        # Servicios con enfasis en ahorro de tiempo y dinero
        service_lines = []
        for s in services:
            sid = s.get("id", "")
            line = SERVICE_WA_LINES.get(sid) or f"{s['name']}: {s.get('short_description', '')}"
            service_lines.append(f"\u2022 {line}")
        services_block = "\n".join(service_lines)

        services_intro = WHATSAPP_SERVICES_INTROS[variation % len(WHATSAPP_SERVICES_INTROS)].format(
            name=name
        )

        ctas = [
            "\u00bfLes gustar\u00eda una llamada de 15 minutos sin costo para ver exactamente cu\u00e1nto pueden ahorrar? \U0001f680",
            "\u00bfPodemos platicar 15 minutos esta semana? Sin costo ni compromiso \u2014 solo para mostrarles c\u00f3mo funciona en su negocio \U0001f60a",
            "\u00bfLes interesa una demostraci\u00f3n gratuita donde les mostramos el ahorro real para su operaci\u00f3n espec\u00edfica? \U0001f4ac",
        ]
        cta = ctas[variation % len(ctas)]

        teaser = SERVICES_TEASER[variation % len(SERVICES_TEASER)]

        # Separar el saludo del "¿Sabía que?" para reordenar: presentación → debilidad.
        # Los hooks tienen formato "Hola {name} [emoji] ¿Sabía que..."; extraemos solo
        # la pregunta para que el saludo quede en la línea de presentación.
        idx = hook.find("¿")
        hook_stat = hook[idx:] if idx > 0 else hook

        parts = [
            f"Hola {name} \U0001f44b Somos el Departamento de IA de [NOMBRE_AGENCIA], especializados en soluciones pr\u00e1cticas para negocios locales en M\u00e9xico.",
            "",
            hook_stat,
            "",
            services_intro,
            services_block,
            "",
            "Todo implementado sin tecnicismos y adaptado a su operaci\u00f3n \u2014 menos horas en tareas que no generan valor y un ahorro real desde el primer mes.",
            "",
            teaser,
            "",
            cta,
            "",
            self.agency_contact,
        ]
        return "\n".join(parts)


# -- Regenerar TODAS las propuestas desde cero -----------------------------------------


def regenerate_all(verbose: bool = True) -> dict:
    """
    Elimina todas las propuestas existentes y las regenera con los templates actualizados.
    Util cuando se mejoran los mensajes y se quiere aplicar a todos los prospectos.

    Returns:
        Diccionario con {deleted, generated, errors}.
    """
    import json as _json

    from config import config
    from skills.dashboard.app import Proposal, Prospect, create_app, db

    app = create_app()
    summary = {"deleted": 0, "generated": 0, "errors": 0}

    catalog = ServiceCatalog(Path(__file__).parent.parent / "config" / "services_catalog.yaml")
    agency_contact = _build_contact_string(config)
    generator = LocalProposalGenerator(
        catalog=catalog, agency_contact=agency_contact, agency_name=config.agency.name
    )

    with app.app_context():
        # Eliminar todas las propuestas existentes
        deleted = Proposal.query.delete()
        db.session.commit()
        summary["deleted"] = deleted

        if verbose:
            print(
                f"\n\U0001f5d1\ufe0f  {deleted} propuestas eliminadas. Regenerando con templates actualizados..."
            )

        # Restablecer status de todos los prospectos a "nuevo"
        Prospect.query.update({"status": "nuevo"})
        db.session.commit()

        # Regenerar para todos los prospectos
        prospects = Prospect.query.all()
        total = len(prospects)

        if verbose:
            print(f"\U0001f4dd Generando propuestas para {total} prospectos...")

        for i, prospect in enumerate(prospects, 1):
            if verbose and i % 100 == 0:
                print(f"  [{i}/{total}] procesados...")

            try:
                email_text, whatsapp_text, phone_text, service_ids = generator.generate(prospect)
                word_count_email = len(email_text.split())
                word_count_wa = len(whatsapp_text.split())

                proposal = Proposal(
                    prospect_id=prospect.id,
                    content=email_text,
                    content_whatsapp=whatsapp_text,
                    content_phone=phone_text,
                    services_selected=_json.dumps(service_ids),
                    template_used=prospect.category,
                    word_count=word_count_email,
                    word_count_whatsapp=word_count_wa,
                )
                db.session.add(proposal)
                prospect.status = "propuesta_generada"
                summary["generated"] += 1

            except Exception as e:
                summary["errors"] += 1
                logger.warning(f"Error regenerando propuesta para {prospect.name}: {e}")
                if verbose:
                    print(f"  \u2717 Error en {prospect.name}: {e}")

        try:
            db.session.commit()
            if verbose:
                print(
                    f"\n\u2705 {summary['generated']} propuestas regeneradas, {summary['errors']} errores"
                )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al guardar propuestas: {e}")
            raise

    return summary


# -- Actualizar solo los mensajes de WhatsApp ------------------------------------------


def update_whatsapp_messages(verbose: bool = True) -> dict:
    """
    Actualiza el campo content_whatsapp de todas las propuestas existentes
    sin modificar los emails ya generados.

    Returns:
        Diccionario con {updated, errors}.
    """
    from config import config
    from skills.dashboard.app import Proposal, Prospect, create_app, db

    app = create_app()
    summary = {"updated": 0, "errors": 0}

    catalog = ServiceCatalog(Path(__file__).parent.parent / "config" / "services_catalog.yaml")
    agency_contact = _build_contact_string(config)
    generator = LocalProposalGenerator(
        catalog=catalog, agency_contact=agency_contact, agency_name=config.agency.name
    )

    with app.app_context():
        proposals = Proposal.query.all()
        total = len(proposals)

        if verbose:
            print(f"\n\U0001f4f1 Actualizando WhatsApp de {total} propuestas...")

        for i, proposal in enumerate(proposals, 1):
            if verbose and i % 100 == 0:
                print(f"  [{i}/{total}] procesados...")

            try:
                prospect = db.session.get(Prospect, proposal.prospect_id)
                if not prospect:
                    continue

                has_website = bool(getattr(prospect, "website", None))
                has_social_media = bool(
                    getattr(prospect, "instagram_url", None)
                    or getattr(prospect, "facebook_url", None)
                )
                services = catalog.get_services_for_category(
                    prospect.category,
                    count=3,
                    has_website=has_website,
                    has_social_media=has_social_media,
                )
                name_bytes = sum(ord(c) for c in (prospect.name or ""))
                variation = name_bytes % 3

                whatsapp_text = generator._build_whatsapp(prospect, services, variation)
                proposal.content_whatsapp = whatsapp_text
                proposal.word_count_whatsapp = len(whatsapp_text.split())
                summary["updated"] += 1

            except Exception as e:
                summary["errors"] += 1
                if verbose:
                    print(f"  \u2717 Error en propuesta #{proposal.id}: {e}")

        try:
            db.session.commit()
            if verbose:
                print(
                    f"\n\u2705 {summary['updated']} mensajes de WhatsApp actualizados, {summary['errors']} errores"
                )
        except Exception:
            db.session.rollback()
            raise

    return summary


# -- Generar propuestas para prospectos nuevos (sin propuesta aun) ---------------------


def generate_all_local(batch_size: int = 796, verbose: bool = True) -> dict:
    """
    Genera propuestas locales para todos los prospectos sin propuesta asignada.

    Args:
        batch_size: Maximo de prospectos a procesar.
        verbose: Si imprimir progreso.

    Returns:
        Diccionario con {generated, errors, skipped}.
    """
    import json as _json

    from config import config
    from skills.dashboard.app import Proposal, Prospect, create_app, db

    app = create_app()
    summary = {"generated": 0, "errors": 0, "skipped": 0}

    catalog = ServiceCatalog(Path(__file__).parent.parent / "config" / "services_catalog.yaml")
    agency_contact = _build_contact_string(config)
    generator = LocalProposalGenerator(
        catalog=catalog, agency_contact=agency_contact, agency_name=config.agency.name
    )

    with app.app_context():
        # Solo prospectos sin propuesta generada
        prospects = Prospect.query.filter(~Prospect.proposals.any()).limit(batch_size).all()

        if not prospects:
            if verbose:
                print("Todos los prospectos ya tienen propuesta generada.")
            return summary

        total = len(prospects)
        if verbose:
            print(f"\n\U0001f4dd Generando propuestas para {total} prospectos...")

        for i, prospect in enumerate(prospects, 1):
            if verbose and i % 50 == 0:
                print(f"  [{i}/{total}] procesados...")

            try:
                email_text, whatsapp_text, phone_text, service_ids = generator.generate(prospect)
                word_count_email = len(email_text.split())
                word_count_wa = len(whatsapp_text.split())

                proposal = Proposal(
                    prospect_id=prospect.id,
                    content=email_text,
                    content_whatsapp=whatsapp_text,
                    content_phone=phone_text,
                    services_selected=_json.dumps(service_ids),
                    template_used=prospect.category,
                    word_count=word_count_email,
                    word_count_whatsapp=word_count_wa,
                )
                db.session.add(proposal)
                prospect.status = "propuesta_generada"
                summary["generated"] += 1

            except Exception as e:
                summary["errors"] += 1
                logger.warning(f"Error generando propuesta para {prospect.name}: {e}")
                if verbose:
                    print(f"  \u2717 Error en {prospect.name}: {e}")

        try:
            db.session.commit()
            if verbose:
                print(
                    f"\n\u2705 {summary['generated']} propuestas generadas, {summary['errors']} errores"
                )
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error al guardar propuestas: {e}")
            raise

    return summary


# -- Helper privado --------------------------------------------------------------------


def _build_contact_string(config) -> str:
    """Construye el string de contacto de la agencia desde la configuracion."""
    lines = []
    if config.agency.phone and "[" not in config.agency.phone:
        lines.append(f"\U0001f4f1 {config.agency.phone}")
    if config.agency.email and "[" not in config.agency.email:
        lines.append(f"\u2709\ufe0f {config.agency.email}")
    if config.agency.instagram and "[" not in config.agency.instagram:
        lines.append(f"\U0001f4f8 {config.agency.instagram}")
    return (
        "\n".join(lines) if lines else "\U0001f4f1 [TELEFONO_AGENCIA]\n\u2709\ufe0f [EMAIL_AGENCIA]"
    )
