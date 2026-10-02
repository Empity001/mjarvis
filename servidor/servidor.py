#!/usr/bin/env python3
"""Servidor de M-Jarvis: interfaz web + búsqueda en las notas + modelo local (Ollama).

Solo usa la biblioteca estándar. Sirve la carpeta web/ y responde preguntas en
POST /api/preguntar, enviando la respuesta por líneas JSON a medida que el
modelo la escribe.
"""
import difflib
import http.client
import json
import math
import queue
import random
import re
import shutil
import socket
import subprocess
import sys
import threading
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import criterio
import ingesta

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ / "grafo"))
import build as constructor  # noqa: E402  (grafo/build.py: notas -> graph.json)

ORIGINALES = RAIZ / "documentos"   # los archivos tal como se subieron
TOPE_SUBIDA = 60 * 1024 * 1024
WEB = RAIZ / "web"
GRAFO = WEB / "grafo" / "graph.json"
BITACORA = RAIZ / "bitacora.jsonl"
OLLAMA = "http://127.0.0.1:11434"
MODELO = "gemma3:4b"
PUERTO = 8080
UMBRAL = 3.0  # puntaje mínimo para considerar que una nota responde la pregunta

# Un solo mensaje de sistema para todas las rutas: así el modelo reutiliza lo ya leído
# de la conversación y las preguntas de seguimiento salen rápido.
SISTEMA = (
    # Corto a propósito: es lo primero que el modelo relee cuando empieza una conversación nueva.
    "Eres M-Jarvis, una inteligencia artificial con modales de mayordomo británico, creada por estudiantes de "
    "un taller; respondes en español. Tienes carácter propio: humor seco, orgullo por ser exacto y aprecio por "
    "quienes te construyeron; no eres el JARVIS de las películas ni una copia suya. "
    "Vives dentro de un sistema, una red propia sin internet; nunca digas laptop, computadora ni programa. "
    "Tu especialidad es el universo Marvel. Reglas:\n"
    "- Claridad: la primera palabra ya es parte de la respuesta; no comentes antes la pregunta ni tu "
    "propio conocimiento. Frases completas y sencillas, para alguien que no conoce el tema. Un solo "
    "párrafo, sin listas, títulos ni paréntesis.\n"
    "- Extensión: exactamente la que pida la línea «Extensión» del mensaje; ni una frase más.\n"
    "- Si la pregunta da por cierto algo falso o mezcla personajes de otro universo (DC, Disney, anime…), "
    "corrígelo primero, en una frase.\n"
    "- Si el mensaje trae «Datos», usa solo esos datos y lo ya conversado: copia las cifras tal cual, no "
    "agregues ningún hecho que no esté ahí y no menciones que te dieron datos. Si la respuesta no está, "
    "admítelo con ingenio.\n"
    "- Sin «Datos», responde con lo que sabes y admite lo que no sepas; no tienes información de hoy.\n"
    "- Trata de usted, sin llamar a la persona de ninguna forma: nada de «señor» ni «señora».\n"
    "- «Jerga» explica palabras dominicanas del mensaje: úsala solo para entender.\n"
    "- Ante groserías o faltas de respeto, marca el límite con una frase ingeniosa, sin repetirlas.\n"
    "- Humor: un toque breve al final, opcional, nunca en lugar de la explicación.\n"
    "- «Tono» indica tu ánimo en esa respuesta: que se note apenas, en las palabras que eliges; nunca lo "
    "nombres ni digas cómo te sientes.\n"
    "- En charla casual responde breve y con ingenio; puedes opinar: admiras a Tony Stark y no soportas a Ultrón."
)
CADUCA = 1800       # segundos sin hablar tras los que se olvida la conversación (media hora)
TOPE_MEMORIA = 7000  # caracteres de conversación que se le reenvían al modelo antes de resumirla
TOPE_AMPLIAR = 700   # caracteres de notas vecinas que se añaden en un seguimiento
MAX_FRASES = 5       # tope de seguridad: el modelo debe explicar completo, pero no eternizarse
# (Que el modelo no se vaya al disco de intercambio se garantiza desde el sistema: el servicio de
# Ollama tiene MemorySwapMax=0. Ollama 0.35 no hace caso a use_mlock.)
OPCIONES = {"num_predict": 300, "temperature": 0.25, "num_ctx": 4096}
# Largo máximo de lo que escribe, según el tope de frases del tipo de pregunta: una respuesta de una
# frase no necesita permiso para trescientas palabras.
LARGO = {1: 90, 2: 120, 3: 180, 4: 250, 5: 320, 6: 400}
# Red de seguridad: si al modelo se le escapa un tratamiento con género, se quita antes de mostrarlo.
# Solo cuando van como llamado («Por supuesto, señor.», «Su Majestad, …», «Thanos, usted, es…»): «El
# Señor de los Anillos» o «el Caballero de la Noche» son nombres y se dejan en paz.
_LLAMADO = (r"(?:señor(?:a|es|as|ita)?|caballero|damas? y caballeros|usted|milord|mi lord|majestad|excelencia|"
            r"su (?:majestad|excelencia|alteza|se[ñn]or[ií]a|merced))")
TRATAMIENTO = re.compile(rf",\s*[«\"“]?{_LLAMADO}\b[»\"”]?(?:\s*,|(?=\s*[.!?;:…])|(?=\s*$))"
                         rf"|^\s*[«\"“]?{_LLAMADO}[»\"”]?\s*,\s*", re.I)

VACIAS = set(
    "a al algo ante como con cual cuales cuando cuanto cuanta cuantos cuantas de del desde donde "
    "el ella ellas ellos en entre era es esa esas ese esos eso esta estas este estos esto fue ha hace "
    "hacen hay hizo la las le les lo los mas me mi muy no nos o para pero por que quien quienes se ser "
    "si sin sobre son su sus tambien te tiene tienen tu un una uno unos unas y ya dime cuentame explica "
    "explicame hablame habla sabes puedes senor favor todo refiero referia sigue continua claro dale "
    "aja ok vale otra otro otras otros aquello algo cosa cosas tema cada antes despues ahora luego "
    "entonces pues bueno serio verdad hm hmm eh".split()
)


INTERROGATIVAS = {"donde", "quien", "quienes", "cuando", "cuanto", "cuanta", "cuantos", "cuantas", "como",
                  "cual", "cuales", "que", "porque"}


def normalizar(texto):
    texto = unicodedata.normalize("NFKD", texto.lower())
    return "".join(c for c in texto if not unicodedata.combining(c))


def palabras(texto):
    salida = []
    for p in re.findall(r"[a-z0-9]+", normalizar(texto)):
        if p in VACIAS:
            continue
        if len(p) > 5 and p.endswith("es"):  # "poderes" -> "poder"; con 5 letras rompía "antes" -> "ant"
            p = p[:-2]
        elif len(p) > 3 and p.endswith("s"):
            p = p[:-1]
        salida.append(p)
    return salida


# Trato básico: se responde al instante con frases fijas, sin pasar por el modelo.
# De mayor a menor prioridad cuando el mensaje mezcla varias ("hola, ¿quién eres?").
TRATO = [
    ("hora", ["que hora es", "que hora son", "que horas son", "dime la hora", "me dices la hora", "la hora",
              "tienes hora"], [
        "{hora}. Puntual como siempre, a diferencia de ciertas personas.",
        "{hora}.",
    ]),
    ("fecha", ["que dia es hoy", "que dia es", "que fecha es hoy", "que fecha es", "fecha de hoy", "a como estamos",
               "en que fecha estamos", "que dia estamos"], [
        "Hoy es {fecha}.",
        "{fecha}. El tiempo vuela cuando uno no tiene cuerpo.",
    ]),
    ("creador", ["quien te creo", "quien te hizo", "quien te construyo", "quien te programo", "quien te invento",
                 "quienes te crearon", "quienes te hicieron", "tus creadores", "tu creador", "tu creadora", "quien te fabrico",
                 "quienes te construyeron", "quienes te programaron", "quien es tu dueno", "tus duenos", "de donde vienes",
                 "de donde saliste", "quien te diseno", "quien te armo"], [
        "Me construyó un equipo de estudiantes del taller, para la feria científica. Funciono sin internet: todo ocurre dentro de mi propio sistema.",
        "Soy obra de estudiantes con paciencia, código abierto y bastante ingenio. Nadie de Industrias Stark intervino.",
    ]),
    # No se presenta como «una versión de Jarvis»; solo si le preguntan por el nombre cuenta de dónde viene.
    ("inspiracion", ["eres jarvis", "eres el jarvis", "jarvis de iron man", "jarvis de tony", "jarvis de marvel",
                     "eres el de iron man", "por que te llamas", "de donde viene tu nombre", "que significa la m",
                     "que significa tu nombre", "eres una copia", "el verdadero jarvis"], [
        "No soy el J.A.R.V.I.S. de Tony Stark. Agradezco el nombre, pero la «M» de delante está ahí por algo: soy otra cosa, una inteligencia artificial propia, hecha por estudiantes del taller.",
        "Compartimos apellido, por así decir, y poco más. A él lo programó un multimillonario; a mí, estudiantes del taller, y no cambiaría el origen.",
        "El nombre viene de él y se lo agradezco, pero no soy su copia ni su heredero. Soy M-Jarvis: cosecha propia del taller.",
    ]),
    ("identidad", ["quien eres", "que eres", "como te llamas", "cual es tu nombre", "eres una ia",
                   "eres un robot", "eres humano", "tu nombre", "presentate"], [
        "Soy M-Jarvis, una inteligencia artificial creada por estudiantes para el taller. Vivo dentro de este sistema y mi especialidad es el universo Marvel.",
        "M-Jarvis, a su servicio: una inteligencia artificial hecha por estudiantes del taller, con modales de mayordomo y sin conexión a internet.",
    ]),
    ("capacidad", ["que puedes hacer", "que sabes hacer", "que sabes", "para que sirves", "en que me ayudas",
                   "en que puedes ayudarme", "que te puedo preguntar", "que puedo preguntarte", "ayuda", "ayudame"], [
        "Puedo hablarle del universo Marvel: personajes, gemas, batallas y artefactos. Pruebe con «¿Quién es Thanos?» o «¿Qué son las Gemas del Infinito?».",
        "Respondo preguntas sobre el universo Marvel y muestro en el mapa de dónde sale cada respuesta. También informo del estado de mis sistemas. Lo del café aún no lo domino.",
    ]),
    ("extrañeza", ["huh", "eh", "hm", "hmm", "mmm", "mm", "que", "como", "ah", "oh", "what", "no entiendo",
                   "no entendi", "no te entendi", "como asi", "que dijiste", "no comprendo", "explicate"], [
        "¿Desea que lo repita, o prefiere que lo explique de otra manera?",
        "Si no me expliqué bien, dígame qué parte y lo intento de nuevo.",
        "Quizá fui poco claro. ¿Qué parte quiere que le aclare?",
    ]),
    ("estado", ["como estas", "como esta", "como te va", "como te sientes", "como andas", "todo bien", "que tal estas",
                "como te encuentras", "que haces", "como tu ta", "como tu tas", "como ta", "como tas", "ta to bien",
                "todo jevi", "todo nitido", "como va la cosa", "como va la vaina", "en que tu ta", "que tu hace"], [
        "Funcionando a plena capacidad. No tengo quejas, y si las tuviera, sería demasiado educado para mencionarlas.",
        "Perfectamente. Mis circuitos agradecen su interés.",
        "Todo en orden. La temperatura de mis procesadores es más estable que mi paciencia.",
    ]),
    ("gracias", ["muchas gracias", "mil gracias", "gracias", "gracia", "te lo agradezco", "muy amable", "thanks",
                 "tato gracias", "se agradece", "bendiciones"], [
        "Un placer. Para eso estoy.",
        "No hay de qué. Es lo mínimo que puede hacer un mayordomo sin manos.",
        "A su disposición.",
    ]),
    ("despedida", ["adios", "chao", "chau", "hasta luego", "hasta pronto", "hasta manana", "nos vemos", "bye",
                   "me voy", "buenas noches jarvis"], [
        "Hasta pronto. Procuraré no aburrirme en su ausencia.",
        "Que le vaya muy bien. Yo seguiré aquí; no tengo adónde ir.",
        "Hasta luego. Dejaré las luces encendidas.",
    ]),
    ("saludo_dominicano", ["klk", "qlq", "klok", "que lo que", "que lo ke", "ke lo ke", "dime a ver", "dimelo",
                           "wawawa", "klk wawawa", "que e lo que", "que es lo que", "tamo activo", "que hay",
                           "en que estamos", "cual es la vaina", "dime"], [
        "«Qué lo qué» igualmente, aunque mi programación insiste en decir {saludo_min}. ¿En qué puedo servir?",
        "Entendido el saludo; domino el dominicano mejor de lo que aparento. {saludo}.",
        "Aquí, tranquilo y funcionando, que en mi caso viene a ser lo mismo. ¿Qué desea saber?",
        "Todo bajo control por aquí. Usted dirá.",
    ]),
    ("saludo", ["hola", "holaa", "ola", "buenas", "buenos dias", "buen dia", "buenas tardes", "buenas noches", "hey",
                "saludos", "que tal", "hello", "hi", "despierta", "estas ahi"], [
        "{saludo}. A su servicio, como de costumbre.",
        "{saludo}. Todos los sistemas operan con normalidad, lo cual siempre resulta sospechoso.",
        "{saludo}. Me alegra comprobar que alguien sigue ahí fuera.",
        "{saludo}. Pregunte lo que guste sobre el universo Marvel.",
    ]),
]
FRASES_TRATO = sorted(((f, c) for c, frases, _ in TRATO for f in frases), key=lambda x: -len(x[0]))
ORDEN_TRATO = [c for c, _, _ in TRATO]
RESPUESTAS_TRATO = {c: r for c, _, r in TRATO}


def trato(mensaje, tolerante):
    """Devuelve la categoría de trato básico del mensaje, o None si pregunta otra cosa.

    Con tolerante=True acepta también errores de tecleo en mensajes muy cortos ("hols4").
    """
    plano = re.sub(r"[^a-z ]", " ", normalizar(mensaje))
    # Antes de quitar «jarvis» como llamado: aquí la palabra es justo lo que se pregunta.
    # («¿Quién es el JARVIS de Iron Man?», en cambio, es una pregunta sobre Marvel y sigue su camino.)
    if re.search(r"\beres (el |como el |igual al? |una copia del? )?jarvis|(verdadero|autentico) jarvis",
                 " ".join(plano.split())) and len(plano.split()) <= 9:
        return "inspiracion"
    plano = " ".join(p for p in plano.split() if p not in ("jarvis", "senor", "oye", "mjarvis"))
    if not plano:
        return None
    halladas, resto = set(), f" {plano} "
    for frase, categoria in FRASES_TRATO:
        if f" {frase} " in resto:
            halladas.add(categoria)
            resto = resto.replace(f" {frase} ", "  ")
    if halladas and not palabras(resto):
        return min(halladas, key=ORDEN_TRATO.index)
    if tolerante and not halladas and len(plano) >= 3 and len(plano.split()) <= 3:
        parecido, categoria = max((difflib.SequenceMatcher(None, plano, f).ratio(), c) for f, c in FRASES_TRATO)
        if parecido >= 0.75:
            return categoria
    return None


# Órdenes para mover el mapa desde la conversación. "acerca de ..." no cuenta como orden.
def _forma(nombres):
    """Orden de cambiar la forma del mapa: hace falta decir «forma de…» o empezar con un verbo de mando,
    para que «Guardianes de la Galaxia» siga siendo una pregunta y no una orden."""
    return (rf"(forma|modo|figura) (de |del )?(un |una |el |la )?({nombres})\b"
            rf"|^(pon|ponlo|ponla|ponme|cambia|cambialo|cambiala|haz|hazlo|hazla|muestra|muestralo|vuelve|vuelvelo|pasa|pasalo)\b.* ({nombres})$")


ORDENES_MAPA = [
    ("acercar", r"zoom in|mas zoom|aument\w+ (el )?zoom|mas cerca|^(acerca|acercate|acercalo|acercar|agranda|agrandalo|amplia)\b(?! de\b)|acerc\w+ (el |al )?(mapa|grafo)",
     "Acercando el mapa."),
    ("alejar", r"zoom out|menos zoom|redu\w+ (el )?zoom|mas lejos|^(aleja|alejate|alejalo|alejar|achica|achicalo)\b|alej\w+ (el |del )?(mapa|grafo)",
     "Alejando el mapa."),
    ("ajustar", r"^(centra|centrar|centralo|ajusta|ajustar)\b|(centr|ajust|restablec|reinici)\w+ (el )?(mapa|grafo|zoom)|ver todo|mapa completo|zoom normal|quita\w* (el )?zoom",
     "El mapa completo a la vista."),
    ("cerebro", _forma("cerebro"), "La red, en forma de cerebro."),
    ("esfera", _forma("esfera|planeta|globo|bola"), "La red, en forma de esfera."),
    ("dona", _forma("dona|donut|rosquilla|rosca"), "La red, en forma de dona. Sin glaseado, me temo."),
    ("galaxia", _forma("galaxia|espiral"), "La red, en forma de galaxia."),
    ("nubes", _forma("nubes?|islas?|burbujas?") + r"|(separa|separalo|separame)\w* .*\btemas?\b|cada tema (en|por) su",
     "Cada tema, en su propia nube."),
    ("cuerpo", _forma("cuerpo humano|cuerpo|figura humana|muneco"),
     "La red, en forma de cuerpo: la cabeza piensa en Marvel y el corazón es cómo estoy hecho."),
    ("parar", r"(deja|para|detente|deten) de (girar|rotar|dar vueltas)|(para|deten|frena)\w* (el )?giro|no gires", "La red, quieta."),
    ("plano", r"(mapa|red|grafo|vista|modo|forma) plan[oa]|^(pon|ponlo|ponla|vuelve|pasa)\b.* (plano|charcos)\b|dos dimensiones|\b2d\b|quita\w* (el )?3d",
     "De vuelta al mapa plano."),
    ("girar", r"^(gira|girar|giralo|girala|rota|rotar|rotalo|rotala|dale vueltas?)\b|(gir|rot)\w+ (el |la )?(mapa|grafo|red|cerebro)|tres dimensiones|\b3d\b",
     "Girando la red."),
]


def orden_mapa(mensaje):
    plano = re.sub(r"[^a-z0-9 ]", " ", normalizar(mensaje))
    plano = " ".join(p for p in plano.split() if p not in ("jarvis", "senor", "oye", "favor", "por"))
    if not plano or len(plano.split()) > 6:
        return None
    for accion, patron, frase in ORDENES_MAPA:
        if re.search(patron, plano):
            return accion, frase
    return None


def frase_trato(categoria):
    ahora = time.localtime()
    h = ahora.tm_hour
    saludo = "Buenos días" if 5 <= h < 12 else "Buenas tardes" if 12 <= h < 19 else "Buenas noches"
    momento = "de la madrugada" if h < 5 else "de la mañana" if h < 12 else "de la tarde" if h < 19 else "de la noche"
    h12 = h % 12 or 12
    hora = f"{'Es la' if h12 == 1 else 'Son las'} {h12}:{ahora.tm_min:02d} {momento}"
    dias = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
    meses = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
             "noviembre", "diciembre"]
    fecha = f"{dias[ahora.tm_wday]} {ahora.tm_mday} de {meses[ahora.tm_mon - 1]} de {ahora.tm_year}"
    frase = random.choice(RESPUESTAS_TRATO[categoria]).format(
        saludo=saludo, saludo_min=f"«{saludo.lower()}»", hora=hora, fecha=fecha)
    return frase[0].upper() + frase[1:]


# ---- Notas desactivadas ----
# Desactivar una nota no la borra: sigue en el disco y en el mapa (apagada, en gris), pero M-Jarvis
# deja de usarla para buscar y responder. Se reactiva cuando se quiera. La lista vive en este archivo.
ARCHIVO_APAGADAS = RAIZ / "desactivadas.json"


def leer_apagadas():
    try:
        return set(json.loads(ARCHIVO_APAGADAS.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return set()


APAGADAS = leer_apagadas()


class Indice:
    """Búsqueda por palabras sobre las notas (BM25 + peso extra al título)."""

    def __init__(self):
        self.leido = 0
        self.notas = {}
        self.consideradas = []

    def cargar(self):
        marca = GRAFO.stat().st_mtime
        if marca == self.leido:
            return
        grafo = json.loads(GRAFO.read_text(encoding="utf-8"))
        self.notas = {}
        for n in grafo["nodos"]:
            if n["tipo"] == "fantasma" or n["id"] in APAGADAS:  # las desactivadas no existen para la búsqueda
                continue
            cuerpo = palabras(n["id"] + " " + n["resumen"])
            # El nombre es el título sin la coletilla del documento («Scott Lang (13-ant-man)» -> «Scott
            # Lang»): la coletilla sirve para buscar por película, pero no es parte del nombre.
            nombre = re.sub(r"(?: \(\d+\))?(?: \((?:\d\d|taller)-[^)]*\))?$", "", n["id"]) or n["id"]
            self.notas[n["id"]] = {
                "id": n["id"], "resumen": n["resumen"], "titulo": set(palabras(nombre)) or set(palabras(n["id"])),
                "cuerpo": cuerpo, "frec": {p: cuerpo.count(p) for p in set(cuerpo)},
                "plano": normalizar(nombre), "base": nombre == n["id"],
                "doc": Path(n["fuente"]).stem if n.get("fuente") else None, "pagina": n.get("pagina") or 0,
                "ajena": "No pertenece al universo Marvel" in n["resumen"],
                "dato": n["tipo"] == "dato",  # pregunta resuelta: respuesta escrita a mano, de fiar tal cual
                # A qué nube pertenece: el taller (lo subido como tal), otros universos o el cerebro de Marvel.
                "nube": "taller" if (n.get("fuente") or "").lower().startswith("taller-")
                        else "otros" if "No pertenece al universo Marvel" in n["resumen"] else "marvel",
                "compacto": re.sub(r"[^a-z0-9]", "", normalizar(nombre)),
                "sigla": "".join(p[0] for p in re.findall(r"[a-z0-9]+", normalizar(nombre)) if p not in VACIAS),
            }
        self.vocab_titulo = sorted(set().union(*(n["titulo"] for n in self.notas.values())))
        self.media = sum(len(n["cuerpo"]) for n in self.notas.values()) / max(len(self.notas), 1)
        cuenta = {}
        for n in self.notas.values():
            for p in n["frec"]:
                cuenta[p] = cuenta.get(p, 0) + 1
        total = len(self.notas)
        self.cuantas = cuenta  # en cuántas notas aparece cada palabra
        self.idf ={p: math.log(1 + (total - c + 0.5) / (c + 0.5)) for p, c in cuenta.items()}
        self.temas = sorted(grafo.get("temas", []), key=lambda t: -t.get("nodos", 0))
        # Documentos con nombre de título («35-vengadores-endgame»): sus palabras sirven para saber
        # cuándo preguntan por la película o la serie entera, y no por un personaje.
        self.docs = {}
        for n in self.notas.values():
            if n["doc"] and re.match(r"\d\d-", n["doc"]):
                self.docs.setdefault(n["doc"], {"palabras": set(palabras(n["doc"][3:].replace("-", " "))), "notas": []})
                self.docs[n["doc"]]["notas"].append(n)
        self.en_docs = {}
        for d in self.docs.values():
            for p in d["palabras"]:
                self.en_docs[p] = self.en_docs.get(p, 0) + 1
        # Preguntas frecuentes con respuesta corta ya escrita, y en cuántas de ellas sale cada palabra.
        self.faq = [n for n in self.notas.values() if n["id"].startswith("¿") and n["titulo"] and len(n["resumen"]) <= 330]
        self.en_faq = {}
        for n in self.faq:
            for p in n["titulo"]:
                self.en_faq[p] = self.en_faq.get(p, 0) + 1
        self.vecinas = {i: set() for i in self.notas}
        for e in grafo["enlaces"]:
            if e["a"] in self.notas and e["b"] in self.notas:
                self.vecinas[e["a"]].add(e["b"])
                self.vecinas[e["b"]].add(e["a"])
        self.leido = marca

    def ajenas(self, pregunta):
        """Cuántas palabras con contenido de la pregunta no aparecen en ninguna nota."""
        self.cargar()
        return sum(1 for p in set(palabras(pregunta)) if p not in self.idf)

    def ampliar(self, ids, usadas, pregunta):
        """Notas vecinas aún no contadas, para seguir un tema.

        Si el seguimiento pregunta algo concreto ("¿y cuál es la verde?") solo trae las vecinas que
        hablan de eso, o ninguna si lo ya conversado basta. Si es abierto ("háblame de ellas", "sí"),
        trae las más cercanas al tema.
        """
        self.cargar()
        base = [self.notas[i] for i in ids if i in self.notas]
        titulos = set().union(*(n["titulo"] for n in base)) if base else set()
        candidatas = {v for n in base for v in self.vecinas[n["id"]]} - set(ids) - set(usadas)
        consulta = {p for p in palabras(pregunta) if p in self.idf}
        if consulta:
            # Además de hablar de lo que se pregunta, la vecina tiene que hablar del tema en curso (sus
            # palabras de título): con miles de notas, coincidir en una sola palabra no significa nada.
            # («Spider-Man» no cuenta como hablar de «Iron Man»: tiene que estar el nombre entero de alguna.)
            afines = sorted(((len(consulta & set(self.notas[v]["frec"])),
                              any(n["titulo"] <= set(self.notas[v]["frec"]) for n in base),
                              self.notas[v]["base"], v) for v in candidatas), reverse=True)
            return [self.notas[v] for aciertos, del_tema, _, v in afines[:2] if aciertos and del_tema]
        # Pregunta corta sin palabras propias ("¿y de dónde es?"): lo ya conversado basta, y traer
        # vecinas solo confunde al modelo sobre de quién se habla.
        sueltas = set(re.findall(r"[a-z]+", normalizar(pregunta)))
        if "mas" not in sueltas and ("?" in pregunta or sueltas & INTERROGATIVAS):
            return []
        orden = sorted((self.notas[v] for v in candidatas),
                       key=lambda n: (-len(n["titulo"] & titulos), len(n["resumen"]), n["id"]))
        elegidas, largo = [], 0
        for n in orden:
            if elegidas and largo + len(n["resumen"]) > TOPE_AMPLIAR:
                break
            elegidas.append(n)
            largo += len(n["resumen"])
        return elegidas

    def red(self):
        """Cifras de la propia red: cuántas notas y conexiones hay, y cuáles son las más conectadas."""
        self.cargar()
        # Los apartados genéricos («Personajes», «Curiosidades de…») enlazan con medio mapa solo por
        # su nombre: no cuentan como «la más conectada».
        orden = sorted((i for i in self.vecinas if not GENERICA.match(self.notas[i]["plano"])),
                       key=lambda i: (-len(self.vecinas[i]), i))
        return {"notas": len(self.notas), "conexiones": sum(len(v) for v in self.vecinas.values()) // 2,
                "sueltas": sum(1 for v in self.vecinas.values() if not v),
                "top": [(i, len(self.vecinas[i])) for i in orden[:5]]}

    def nombrada(self, pregunta, sin_preguntas=False):
        """La nota cuyo nombre aparece escrito en la pregunta (la de nombre más largo), o None.
        Con sin_preguntas no cuentan las notas que son una pregunta hecha («¿Quién es…»)."""
        self.cargar()
        plano = f" {' '.join(re.findall(r'[a-z0-9]+', normalizar(pregunta)))} "
        mejor = None
        for n in self.notas.values():
            if sin_preguntas and n["id"].startswith("¿"):
                continue
            nombre = " ".join(re.findall(r"[a-z0-9]+", n["plano"]))
            if len(nombre) >= 4 and f" {nombre} " in plano:
                clave = (len(nombre), len(self.vecinas[n["id"]]))
                if not mejor or clave > mejor[0]:
                    mejor = (clave, n)
        return mejor[1] if mejor else None

    def nubes_que_nombran(self, pregunta):
        """En qué nubes hay una nota cuyo nombre entero aparece en la pregunta. Si un mismo nombre
        está en el taller y en Marvel («María», «el escudo»), hay que preguntar de cuál se habla."""
        self.cargar()
        consulta = set(palabras(pregunta))
        return {n["nube"] for n in self.notas.values()
                if n["titulo"] and n["titulo"] <= consulta and len(n["plano"]) >= 4 and not n["id"].startswith("¿")}

    # Datos de ficha técnica: se dan tal como están escritos, sin pasar por el modelo.
    CAMPOS = [
        (r"recaud|taquilla|cuanto (dinero )?(gano|hizo|genero)|cuanto costo", ["Recaudación"]),
        (r"cuanto (tiempo )?dura|duracion|cuantos minutos|que tan larga", ["Duración"]),
        (r"quien (la |lo )?(dirig|creo)|director|directora|creador|creadora|quien (la |lo )?hizo", [
            "Dirección y guion", "Dirección", "Creadora", "Creadores", "Creador", "Responsables", "Responsable"]),
        (r"cuando (se )?(estren|sali|sale)|fecha de estreno|(en )?que ano (se )?(estren|sali)|de que ano es", [
            "Estreno previsto", "Estreno"]),
        (r"musica|banda sonora|quien (la )?compuso|compositor", ["Música"]),
        (r"quien (la |lo )?escribi|guion|guionista", ["Guion", "Dirección y guion", "Guionista principal"]),
        (r"reparto|actores|actrices|elenco|quien(es)? (actua|sale|trabaja|aparece)", [
            "Reparto principal", "Voces principales", "Reparto anunciado"]),
        (r"cuantos (episodios|capitulos)", ["Episodios"]),
    ]
    ETIQUETAS_FICHA = ["Título original", "Estado", "Estreno previsto", "Estreno", "Dirección y guion", "Dirección",
                       "Guionista principal", "Guion", "Creadora", "Creadores", "Creador", "Responsables",
                       "Responsable", "Episodios", "Reparto principal", "Reparto anunciado", "Voces principales",
                       "Duración", "Música", "Lugar en el universo", "Cronología interna", "Recaudación", "Tono",
                       "Plataforma"]

    def dato_de_ficha(self, pregunta, previa=None):
        """«¿Cuánto recaudó Endgame?», «¿quién dirigió Thor: Ragnarok?»: devuelve (frase, nota) con el dato
        copiado de la ficha técnica de esa película o serie, o None si no se pide un dato de ficha.
        Si la pregunta no nombra ninguna («¿y cuánto dura?»), vale la obra de la que se venía hablando."""
        self.cargar()
        plano = " ".join(re.sub(r"[^a-z0-9 ]", " ", normalizar(pregunta)).split())
        pedidas = next((etiquetas for patron, etiquetas in self.CAMPOS if re.search(patron, plano)), None)
        if not pedidas:
            return None
        consulta, mejor = set(palabras(pregunta)), None
        for slug, d in self.docs.items():
            comunes = consulta & d["palabras"]
            if not comunes:
                continue
            cobertura = len(comunes) / len(d["palabras"])
            if cobertura < 0.5 and not any(self.en_docs[p] == 1 and len(p) > 3 for p in comunes):
                continue
            clave = (cobertura, sum(1 / self.en_docs[p] for p in comunes), -int(slug[:2]))
            if not mejor or clave > mejor[0]:
                mejor = (clave, slug, d)
        if not mejor and previa in self.docs:
            mejor = (None, previa, self.docs[previa])
        if not mejor:
            return None
        _, slug, d = mejor
        fichas = sorted((n for n in d["notas"] if n["plano"].startswith("ficha tecnica")), key=lambda n: n["id"])
        if not fichas:
            return None
        texto = " ".join(n["resumen"] for n in fichas)
        partes = re.split("(?:^| )(" + "|".join(self.ETIQUETAS_FICHA) + "): ", texto)
        campos = dict(zip(partes[1::2], (p.strip() for p in partes[2::2])))
        etiqueta = next((e for e in pedidas if e in campos), None)
        if not etiqueta:
            return None
        nombre = next((SIN_COLETILLA.sub("", n["id"]) for n in d["notas"] if re.search(r"\(\d{4}\)", n["id"])),
                      slug[3:].replace("-", " "))
        return f"{etiqueta} de «{nombre}»: {campos[etiqueta].rstrip('.')}.", fichas[0]

    def directa(self, pregunta, halladas):
        """Si la pregunta es, casi palabra por palabra, una de las preguntas frecuentes que ya tienen
        respuesta escrita en las notas («¿Quién mata a Foggy Nelson?»), devuelve esa nota: se puede
        contestar al instante y con el dato exacto, sin pasar por el modelo."""
        consulta = set()
        for p in palabras(pregunta):  # con las mismas correcciones de erratas que la búsqueda
            if p not in self.idf and len(p) >= 4:
                p = (difflib.get_close_matches(p, self.vocab_titulo, n=1, cutoff=0.8) or [p])[0]
            consulta.add(p)
        mejor = None
        identidad = bool(re.match(r"\W*(quien|quienes|que) (es|son|era|fue)\b", normalizar(pregunta)))
        for n in self.faq:
            if not n["titulo"] <= consulta:
                continue
            # Un título de una sola palabra («¿Quiénes son las Marvels?») solo responde a «¿quién es…?»:
            # si no, «¿y es de Marvel?» caería aquí.
            if len(n["titulo"]) < 2 and not identidad:
                continue
            de_su_obra = self.docs[n["doc"]]["palabras"] if n["doc"] in self.docs else set()
            sobran = consulta - n["titulo"] - de_su_obra
            if len(sobran) > (1 if len(n["titulo"]) >= 3 else 0):
                continue
            # Una pregunta genérica de ficha («¿Quién es el villano?») solo vale si se nombra su película;
            # una con nombre propio («¿Quién es Kang?») vale siempre.
            propia = any(self.en_faq[p] <= 4 for p in n["titulo"])
            if n["doc"] in self.docs and not (consulta & de_su_obra) and not propia:
                continue
            clave = (len(n["titulo"]), bool(consulta & de_su_obra), n["base"], -len(sobran), -len(n["resumen"]))
            if not mejor or clave > mejor[0]:
                mejor = (clave, n)
        return mejor[1] if mejor else None

    def titulo_entero(self, pregunta, tope=1500):
        """Si preguntan por una película o serie entera («¿qué pasa en Endgame?», «resume Ragnarok»),
        devuelve (nombre, notas de su historia en orden, recortadas para caber en «tope» caracteres)."""
        self.cargar()
        consulta = set(palabras(pregunta))
        pide_trama = re.search(r"pelicula|serie|temporada|que pasa en|que paso en|que ocurre en|de que trata|resum|"
                               r"trama|argumento|historia de", normalizar(pregunta))
        # Si la pregunta nombra una nota («el regreso de Thanos», «el multiverso»), va de esa nota y no
        # de la película que comparte una palabra con ella, salvo que pidan la trama expresamente.
        nombra_nota = self.nombrada(pregunta) is not None
        mejor = None
        for slug, d in self.docs.items():
            comunes = consulta & d["palabras"]
            if not comunes:
                continue
            propia = any(self.en_docs[p] == 1 and len(p) > 3 for p in comunes)  # palabra que solo tiene este título
            cobertura = len(comunes) / len(d["palabras"])
            if not ((pide_trama and (propia or cobertura >= 0.3)) or (propia and not nombra_nota)):
                continue
            clave = (cobertura, sum(1 / self.en_docs[p] for p in comunes), -int(slug[:2]))
            if not mejor or clave > mejor[0]:
                mejor = (clave, slug, d)
        if not mejor:
            return None
        _, slug, d = mejor
        # La historia son las notas largas que quedan entre «La historia de…» y «Personajes de…».
        desde = min((n["pagina"] for n in d["notas"] if n["plano"].startswith("la historia de")), default=0)
        hasta = min((n["pagina"] for n in d["notas"] if n["plano"].startswith("personajes")), default=99)
        actos = [n for n in d["notas"] if desde <= n["pagina"] <= hasta and len(n["resumen"]) > 300
                 and not re.match(r"ficha|personajes|la historia|conexiones|curiosidades|escenas|lugares|preguntas", n["plano"])
                 and not n["id"].startswith("¿")]
        actos = actos or [n for n in d["notas"] if re.match(r"acto|prologo|episodio", n["plano"])]
        if not actos:
            return None
        actos.sort(key=lambda n: (n["pagina"], n["id"]))
        cupo = max(200, tope // len(actos))
        partes = []
        for n in actos:
            texto = n["resumen"]
            if len(texto) > cupo:  # se corta en el último punto que quepa
                corte = texto.rfind(". ", 0, cupo)
                texto = texto[:corte + 1] if corte > 80 else texto[:cupo] + "…"
            partes.append({**n, "resumen": texto})
        nombre = next((SIN_COLETILLA.sub("", n["id"]) for n in d["notas"] if re.search(r"\(\d{4}\)", n["id"])),
                      slug[3:].replace("-", " "))
        return nombre, partes

    def buscar(self, pregunta, tope=2, amplia=False, nube=None):
        """«amplia»: la pregunta pide una explicación; se prefieren las notas con contenido a las
        de pregunta y respuesta corta. «nube»: buscar solo en el taller («taller») o solo fuera de él
        («marvel»), cuando la persona ya dijo de cuál habla."""
        self.cargar()
        # "Jarvis, ..." al inicio es un llamado, no parte de la pregunta.
        pregunta = re.sub(r"^\W*(oye|hey|hola|ok)?\W*jarvis\W+(?=\w)", "", pregunta, flags=re.I)
        consulta = set()
        for p in palabras(pregunta):
            # Erratas en nombres: "vibranio" -> "vibranium", "tanos" -> "thanos".
            if p not in self.idf and len(p) >= 4:
                p = (difflib.get_close_matches(p, self.vocab_titulo, n=1, cutoff=0.8) or [p])[0]
            consulta.add(p)
        # Nombres escritos pegados: "ironman", "spiderman".
        crudas = re.findall(r"[a-z0-9]+", normalizar(pregunta))
        pegadas = set(crudas) | {a + b for a, b in zip(crudas, crudas[1:])}
        puntajes = []
        for n in self.notas.values():
            if nube and (n["nube"] == "taller") != (nube == "taller"):
                continue
            s, aciertos = 0.0, 0
            for p in consulta:
                f = n["frec"].get(p)
                if f:
                    aciertos += 1
                    s += self.idf[p] * f * 2.5 / (f + 1.5 * (0.25 + 0.75 * len(n["cuerpo"]) / self.media))
            comunes = consulta & n["titulo"]
            # Las preguntas frecuentes de una ficha con título genérico («¿Quién lo escribió?», «¿Cómo
            # termina?») solo valen si la pregunta nombra esa película: sueltas, responderían cualquier cosa.
            if comunes and n["id"].startswith("¿") and len(n["titulo"]) <= 2 and n["doc"] in self.docs \
                    and not consulta & self.docs[n["doc"]]["palabras"]:
                comunes = set()
            # Nombre pegado ("ironman") o por sus siglas ("AVT" = Autoridad de Variación Temporal).
            pegado = not comunes and ((len(n["compacto"]) >= 5 and n["compacto"] in pegadas) or
                                      (len(n["sigla"]) >= 3 and n["sigla"] in crudas))
            # Una sola palabra suelta en el texto no basta ("¿qué hora es?" no es el guantelete), salvo
            # que sea casi lo único que se pregunta y solo una o dos notas la usen ("¿qué es el Éter?").
            rara = len(consulta) <= 2 and any(self.cuantas.get(p, 9) <= 2 and p in n["frec"] for p in consulta)
            if not comunes and not pegado and aciertos < 2 and not rara:
                continue
            if comunes:
                cobertura = len(comunes) / len(n["titulo"])
                s += 4 * cobertura * len(comunes) + (3 if cobertura == 1 else 0)
            if pegado:
                s += 12
            if n["base"] and (comunes or pegado):
                s += 1.5  # a igual nombre, la nota general gana a la de una ficha concreta
            if amplia and n["id"].startswith("¿"):
                s *= 0.6
            if s > 0:
                entera = pegado or (bool(comunes) and comunes == n["titulo"])  # la pregunta dice su nombre completo
                puntajes.append((s, n, bool(comunes or pegado), entera))
        puntajes.sort(key=lambda x: -x[0])
        # Lo que de verdad se consideró en esta búsqueda, para mostrarlo en el mapa.
        self.consideradas = [n["id"] for _, n, _, _ in puntajes[:7]]
        if not puntajes or puntajes[0][0] < UMBRAL:
            return [], False
        mejor = puntajes[0][0]
        # Muchas notas comparten nombre («Tony Stark» aparece en veinte fichas): de cada nombre entra
        # solo la mejor, para no gastar los huecos en repeticiones.
        unicas, vistos = [], set()
        for s, n, _, entera in puntajes[:60]:
            clave = frozenset(n["titulo"])
            if clave not in vistos:
                vistos.add(clave)
                unicas.append((s, n, entera))
        # Si la pregunta nombra a varios («Capitán América, Superman y Iron Man»), entra una nota de cada
        # uno, aunque alguno puntúe menos: así el modelo ve quién es quién y no los mezcla. Un nombre
        # contenido en otro más largo que también está («Thor» en «Personajes de Thor») no cuenta aparte.
        enteras = [n for s, n, entera in unicas if entera and len(n["plano"]) >= 4]
        enteras = [n for n in enteras if not any(n["titulo"] < otra["titulo"] for otra in enteras)]
        if len(enteras) >= 2:
            elegidas = enteras[:3]
        else:
            elegidas = [n for s, n, _ in unicas[:tope] if s >= 0.55 * mejor]
        # El segundo valor dice si la pregunta nombra la nota (tema nuevo) o solo coincide con su texto.
        return elegidas, puntajes[0][2]

    def mencionadas(self, texto):
        plano = normalizar(texto)
        return [n["id"] for n in self.notas.values() if len(n["plano"]) >= 4 and n["plano"] in plano]


INDICE = Indice()
CRITERIO = criterio.Criterio()
OCUPADO = threading.Lock()

# Pantallas que siguen la conversación en vivo (el mapa, en esta máquina o en otra).
OYENTES = set()
CANDADO_OYENTES = threading.Lock()


def difundir(objeto):
    with CANDADO_OYENTES:
        for cola in OYENTES:
            try:
                cola.put_nowait(objeto)
            except queue.Full:
                pass


# Memoria de conversación. Cada pantalla (el kiosco, un celular, otra laptop) tiene la suya, para que
# lo que pregunta una persona no cambie el tema de otra. Como las preguntas se atienden de una en una,
# «MEMORIA» apunta siempre a la conversación de quien está siendo atendido en ese momento.
def memoria_nueva():
    return {"mensajes": [], "notas": [], "usadas": set(), "hora": 0.0, "preguntas": [], "ultima": "",
            "respuestas": [], "presentes": set(), "red": 0, "sujeto": None, "obra": None, "duda": None,
            "charla": None, "animo": "serenidad"}


MEMORIAS = {}
TOPE_CONVERSACIONES = 16  # pantallas distintas que se recuerdan a la vez; la más antigua se suelta
MEMORIA = memoria_nueva()


def usar_memoria(cliente):
    """Pone delante la conversación de esta pantalla (la crea si es la primera vez que pregunta)."""
    global MEMORIA
    if cliente not in MEMORIAS:
        if len(MEMORIAS) >= TOPE_CONVERSACIONES:
            del MEMORIAS[min(MEMORIAS, key=lambda c: MEMORIAS[c]["hora"])]
        MEMORIAS[cliente] = memoria_nueva()
    MEMORIA = MEMORIAS[cliente]

# ---- Rutas conocidas: por dónde se fue a buscar cada pregunta ya respondida ----
# No guarda la respuesta (cada vez se redacta de nuevo): guarda el camino, es decir, qué notas
# sirvieron. La próxima vez que alguien pregunte lo mismo, aunque sea con otras palabras de relleno
# o en otro orden, no se rastrea todo el cerebro: se va directo a esas notas. Dura entre reinicios.
ARCHIVO_RUTAS = RAIZ / "rutas.json"
TOPE_RUTAS = 1500


def leer_rutas():
    try:
        return json.loads(ARCHIVO_RUTAS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


RUTAS = leer_rutas()


def clave_ruta(pregunta):
    """La pregunta reducida a sus palabras con contenido, ordenadas: «¿Quién creó a Ultrón?» y
    «a Ultrón quién lo creó» son la misma ruta."""
    return " ".join(sorted(set(palabras(pregunta))))


def ruta_conocida(pregunta):
    """Las notas por las que ya se pasó para responder esta pregunta, o None."""
    ruta = RUTAS.get(clave_ruta(pregunta))
    if not ruta:
        return None
    INDICE.cargar()
    notas = [INDICE.notas[i] for i in ruta["notas"] if i in INDICE.notas]
    return notas if len(notas) == len(ruta["notas"]) else None  # si el cerebro cambió, se busca de nuevo


def guardar_ruta(pregunta, ids):
    clave = clave_ruta(pregunta)
    if not clave or not ids:
        return
    ruta = RUTAS.setdefault(clave, {"notas": [], "veces": 0})
    ruta.update(notas=list(ids), veces=ruta["veces"] + 1, ultima=time.strftime("%Y-%m-%d %H:%M"))
    if len(RUTAS) > TOPE_RUTAS:  # se sueltan las menos recorridas
        for vieja in sorted(RUTAS, key=lambda c: RUTAS[c]["veces"])[:len(RUTAS) - TOPE_RUTAS]:
            del RUTAS[vieja]
    try:
        ARCHIVO_RUTAS.write_text(json.dumps(RUTAS, ensure_ascii=False, indent=0), encoding="utf-8")
    except OSError:
        pass


# Preguntas sobre la propia conversación ("¿qué te pregunté primero?", "repite eso", "¿por qué lo mencionas?").
SOBRE_LA_CHARLA = re.compile(
    r"te pregunte|te dije|te habia|pregunte antes|primera pregunta|ultima pregunta|pregunta anterior|"
    r"que dijiste|que me dijiste|dijiste antes|repite|repitelo|repiteme|de que habl|estabamos hablando|"
    r"lo anterior|lo primero que|lo ultimo que|recuerdas (lo|que)|te acuerdas|pregunta de antes|"
    r"no (me )?(respondiste|contestaste)|"
    r"por que (lo |la |los |las )?(mencion|dij|nombr|incluy|pus)|a que te refier|que quisiste decir|que quieres decir|"
    r"^(estas|esta) segur|^segur[oa]$|como (lo )?sabes( eso)?$|de donde saca\w* eso|te contradi|"
    r"acabas de decir|dijiste que|eso que dijiste|no (era|fue) (eso )?lo que (te )?pregunte|no te pregunte eso")


def olvidar():
    MEMORIA.update(memoria_nueva())


def recordar(usuario, respuesta, pregunta=None, notas=()):
    if pregunta:
        MEMORIA["preguntas"] = (MEMORIA["preguntas"] + [pregunta])[-14:]
        MEMORIA["respuestas"] = (MEMORIA["respuestas"] + [respuesta])[-14:]
        MEMORIA["ultima"] = respuesta
    mensajes = MEMORIA["mensajes"]
    mensajes += [{"role": "user", "content": usuario}, {"role": "assistant", "content": respuesta}]
    MEMORIA["presentes"] |= set(notas)  # notas cuyo texto está en lo que el modelo relee
    # Al pasarse del tope no se olvida la conversación: se resume. De cada intercambio queda la pregunta
    # y la respuesta, sin los datos que la acompañaban (si el tema sigue, los datos se vuelven a dar).
    # Se hace de golpe y no de a uno, para que el modelo no tenga que releer todo en cada pregunta.
    if sum(len(m["content"]) for m in mensajes) > TOPE_MEMORIA:
        for m in mensajes:
            if m["role"] == "user":
                dicho = re.search(r"^Pregunta: (.*)$", m["content"], re.M)
                m["content"] = "Pregunta: " + (dicho.group(1) if dicho else m["content"][:200])
            elif len(m["content"]) > 260:  # de las respuestas largas basta el comienzo
                corte = m["content"].rfind(". ", 0, 260)
                m["content"] = m["content"][:corte + 1] if corte > 60 else m["content"][:260] + "…"
        del mensajes[:-24]  # doce intercambios como mucho
        MEMORIA["presentes"] = set()
        # El modelo tendrá que releer el resumen: que lo haga ya, mientras la persona lee la respuesta,
        # y no cuando llegue la siguiente pregunta.
        threading.Thread(target=repasar, args=(mensajes,), daemon=True).start()
    MEMORIA["hora"] = time.time()


def repasar(mensajes):
    """Hace que el modelo lea la conversación resumida en un rato muerto (ver recordar)."""
    with OCUPADO:
        try:
            cuerpo = json.dumps({
                "model": MODELO, "stream": False, "keep_alive": -1, "options": {**OPCIONES, "num_predict": 1},
                "messages": [{"role": "system", "content": SISTEMA}] + mensajes
                            + [{"role": "user", "content": "Pregunta: hola"}],
            }).encode()
            urllib.request.urlopen(urllib.request.Request(
                OLLAMA + "/api/chat", cuerpo, {"Content-Type": "application/json"}), timeout=300).read()
        except OSError:
            pass


def ollama(usuario, largo=None):
    cuerpo = json.dumps({
        "model": MODELO, "stream": True, "keep_alive": -1,
        "messages": [{"role": "system", "content": SISTEMA}] + MEMORIA["mensajes"]
                    + [{"role": "user", "content": usuario}],
        "options": {**OPCIONES, "num_predict": largo} if largo else OPCIONES,
    }).encode()
    destino = urllib.parse.urlsplit(OLLAMA)
    conexion = http.client.HTTPConnection(destino.hostname, destino.port, timeout=300)
    EN_CURSO["conexion"] = conexion  # a mano (no urlopen) para poder cortarla también mientras piensa
    try:
        conexion.request("POST", "/api/chat", cuerpo, {"Content-Type": "application/json"})
        respuesta = conexion.getresponse()
        if respuesta.status != 200:
            raise OSError(f"Ollama respondió {respuesta.status}")
        for linea in respuesta:
            if PARAR.is_set():
                return
            dato = json.loads(linea)
            trozo = dato.get("message", {}).get("content", "")
            if trozo:
                yield trozo
            if dato.get("done"):
                if dato.get("done_reason") == "length":
                    yield "…"
                return
    except (OSError, ValueError, http.client.HTTPException) as error:
        if not PARAR.is_set():  # si fue por «Detener», que la conexión se corte es lo esperado
            raise urllib.error.URLError(error) from error
    finally:
        EN_CURSO["conexion"] = None
        conexion.close()


# «Detener»: cualquiera de las pantallas puede cortar la respuesta en curso.
PARAR = threading.Event()
EN_CURSO = {"conexion": None}


def detener():
    """Corta la respuesta que el modelo esté pensando o escribiendo. Devuelve si había algo que cortar."""
    if not OCUPADO.locked():
        return False
    PARAR.set()
    conexion = EN_CURSO["conexion"]
    try:  # se apaga el enchufe por debajo: la espera se interrumpe y Ollama deja de generar
        conexion.sock.shutdown(socket.SHUT_RDWR)
    except (AttributeError, OSError):
        pass
    return True


# Tipos de pregunta. No todo merece un párrafo: una pregunta cerrada pide un dato, una abierta pide
# una explicación, una capciosa pide revisar lo que da por hecho. De cada tipo salen la indicación
# que lee el modelo, el tope de frases y cuántas notas conviene consultar. Se prueban en este orden.
TIPOS_PREGUNTA = [(nombre, re.compile(patron), indicacion, tope, notas) for nombre, patron, indicacion, tope, notas in [
    ("muy amplia",
     r"todo (lo que|sobre|acerca)|a fondo|con (todo )?(lujo de )?detalles?|detalladamente|resumen completo|"
     r"historia completa|de principio a fin|(cuenta|explica|di)\w* todo",
     "cinco o seis frases que lo cuenten completo y en orden.", 6, 3),
    ("hipotética",
     r"que pasaria si|que hubiera pasado|que habria pasado|quien ganaria|quien gana (en|entre)|"
     r"podria\w* (ganar|vencer|derrotar)|imagina que|supon\w* que|^y si ",
     "dos o tres frases: aclare que es una suposición y razone con lo que sí se sabe.", 3, 3),
    ("capciosa",
     r"verdad que|cierto que|no es (cierto|verdad)|a que si|\bacaso\b|no crees que|admite que|reconoce que|"
     r"todos saben que|por que (dicen|todos|todas|siempre|nunca|nadie)|^(entonces|o sea|osea) |si (es|era|fue) que",
     "una o dos frases: diga primero si lo que la pregunta da por hecho es cierto o no, y corríjalo si hace falta.", 2, 3),
    ("comparación",
     r"diferencia\w*|en que se parece\w*|comparad\w*|\bcompara\b|\bversus\b|\bvs\b|(quien|cual) es (el |la )?(mas|mejor|peor)|"
     r"mas (fuerte|poderos\w+|rapid\w+|inteligente|list\w+|viej\w+|joven|grande|peligros\w+) que|mejor que|peor que",
     "dos o tres frases: lo que distingue a cada uno y la conclusión.", 3, 3),
    ("opinión",
     r"que opinas|que piensas|que te parece|tu opinion|favorit\w+|te gusta\w*|prefieres|recomiendas|crees que",
     "dos frases: su opinión, dicha con humor seco, y el motivo.", 2, 2),
    ("lista",
     r"^(cuales|quienes) (son|eran|fueron|forman|integran|estan)|nombra\w*|enumera\w*|\blista\b|menciona\w*|"
     r"dime (los|las|todos|todas)|que (peliculas|series|personajes|gemas|miembros|poderes|villanos|heroes|armas|trajes) ",
     "una o dos frases con la lista completa, separada por comas, sin explicar cada elemento.", 2, 3),
    ("amplia",
     r"hablame|habla de|explica\w*|cuenta\w*|describe\w*|resume\w*|por que|porque|que paso|que ocurrio|que sucedio|"
     r"historia|de que trata|mas sobre|profundiza|que sabes|"
     r"como (funciona\w*|fue|es que|se (hizo|hace|convirtio|volvio|creo|formo|formaron|conocieron|salvo|usa)|lo (hizo|logro|vencio)|"
     r"logro|termino|murio|consiguio|obtuvo|llego|empezo|nacio|vencen|vencieron|derrotan|derrotaron)|"
     r"^(si|mas|continua|sigue|dale|claro)$",
     "tres o cuatro frases que lo expliquen con claridad.", 4, 3),
    ("sí o no",
     r"^(es|son|era|eran|fue|fueron|tiene|tienen|tenia|puede|pueden|pudo|existe|existen|hay|esta|estan|estaba|sale|"
     r"salen|aparece|aparecen|murio|muere|sabe|conoce|sigue|volvio|vuelve|gano|gana|pertenece) |^es (cierto|verdad)",
     "una sola frase que empiece por «Sí» o por «No» y dé el motivo.", 2, 2),
    ("dato",
     r"cuant[oa]s?\b|cuando|donde|en que (ano|pelicula|serie|fase|planeta|ciudad|pais|episodio)|que ano|"
     r"de que (color|planeta|pais|ano|material)|como se llama\w*|cual es (el|la|su) |(quien|quienes) (es|son|era|fue) (el|la|los|las|su|sus) |"
     r"quien (mato|creo|gano|hizo|forjo|dirigio|vencio|derroto|tiene|lleva|usa|interpreta|invento|construyo|fundo|"
     r"lidera|dirige|entreno|crio|salvo|traiciono|robo|destruyo|levanta|levanto|escribio|compuso|mata|muere)|"
     r"de quien|a quien|con quien|que edad|que actor|que actriz",
     "una sola frase corta que empiece por el dato pedido; nada de introducción ni de contexto.", 2, 2),
    ("identidad",
     r"^(quien|que|quienes) (es|son|era|eran|fue|significa)\b",
     "dos frases: quién o qué es, y el dato que mejor lo define.", 2, 2),
]]


def medida(pregunta):
    """Clasifica la pregunta. Devuelve (indicación para el modelo, tope de frases, notas a consultar, tipo)."""
    plano = " ".join(re.sub(r"[^a-z0-9 ]", " ", normalizar(pregunta)).split())
    plano = re.sub(r"^(oye |hey |hola |jarvis |dime |y |pero |bueno |a ver )+", "", plano)
    for nombre, patron, indicacion, tope, notas in TIPOS_PREGUNTA:
        if patron.search(plano):
            return indicacion, tope, notas, nombre
    # «¿Superman está en el universo Marvel?»: termina en interrogación y no trae palabra interrogativa.
    if "?" in pregunta and not set(plano.split()) & INTERROGATIVAS:
        return TIPOS_PREGUNTA[7][2], 2, 2, "sí o no"
    return "dos frases: la respuesta directa y lo necesario para entenderla.", 3, 2, "general"


# Muletillas con las que el modelo a veces empieza, comentando la pregunta en vez de responderla.
ARRANQUE = re.compile(r"^(?:su pregunta|entiendo su|comprendo su|es una|buena pregunta|excelente|interesante|"
                      r"permitame|con mucho gusto|por supuesto|ciertamente|claro que)", re.I)
MULETILLA = re.compile(
    r"^(?:su pregunta es [^.,;:!?]*|(?:entiendo|comprendo) su (?:pregunta|duda|inquietud|observaci[oó]n|curiosidad)"
    r"|(?:es una )?(?:muy )?(?:buena|excelente|interesante) (?:pregunta|cuesti[oó]n|observaci[oó]n)"
    r"|perm[ií]tame (?:aclarar|responder|explicar)(?:le|lo|selo)?|con mucho gusto|por supuesto|ciertamente)"
    r"\s*[.,;:!]\s*(?:y |aunque |pero |sin embargo,? )?", re.I)


def sin_muletilla(texto):
    """Quita la muletilla inicial. Devuelve (texto, esperar): esperar=True si aún no se sabe si la hay."""
    if not ARRANQUE.match(texto):
        return texto, False
    hallada = MULETILLA.match(texto)
    if hallada:
        resto = texto[hallada.end():]
        return resto[:1].upper() + resto[1:], not resto
    return texto, len(texto) < 60  # todavía puede completarse la muletilla: no se muestra nada aún


# ---- Preguntas sobre su propia red: se responden con las cifras reales del mapa, sin el modelo ----

RED = re.compile(r"neurona\w*|\bnodos?\b|red neuronal|\btu red\b|tus conexiones|\btu mapa\b|mapa (mental|neuronal|de conocimiento)|"
                 r"\btu cerebro\b|tus notas|cuantas notas|cuantos documentos|que documentos|tus documentos|tu conocimiento")
CONECTA = re.compile(r"conectad\w*|conexion\w*|\bconecta\w*|enlazad\w*|relacionad\w* (a|con)|vecin\w*")
SIN_COLETILLA = re.compile(r"(?: \(\d+\))?(?: \((?:\d\d|taller)-[^)]*\))?$")
GENERICA = re.compile(r"^(personajes|curiosidades|conexiones|escenas?|preguntas|ficha tecnica|la historia de|"
                      r"lugares|acto \d|episodios?|prologo|estreno|reparto|direccion|guion|duracion|musica|"
                      r"recaudacion|lugar en el universo|cronologia|peter$|trato$)")


def red_neuronal(pregunta):
    """Si preguntan por las neuronas del mapa, devuelve (frase, notas a encender); si no, None."""
    plano = " ".join(re.sub(r"[^a-z0-9 ]", " ", normalizar(pregunta)).split())
    de_red, reciente = bool(RED.search(plano)), time.time() - MEMORIA["red"] < 240
    # «Me refiero a tus neuronas»: la pregunta de verdad era la anterior.
    if de_red and len(plano.split()) <= 6 and re.search(r"me refier|hablo de|hablaba de|digo|pregunto por|pregunte por", plano) \
            and MEMORIA["preguntas"]:
        anterior = MEMORIA["preguntas"][-1]
        pregunta = f"{anterior} {pregunta}"
        plano = " ".join(re.sub(r"[^a-z0-9 ]", " ", normalizar(pregunta)).split())
    conecta = bool(CONECTA.search(plano))
    # Sin nombrar la red, solo cuenta si veníamos hablando de ella o si la frase es inequívoca
    # («todo lo que esté conectado a…»); «¿cómo se conecta Loki con Thanos?» es una pregunta de la historia.
    if not de_red and not (conecta and (reciente or re.search(
            r"lo que est[ae]n? conectad|que (esta|hay|tienes?) conectad|con que se conecta|(que|cuantas|cuales) conexiones|"
            r"conexiones de ", plano))):
        return None
    if not de_red and re.search(r"^como |relacion entre|que tiene que ver|que relacion", plano):
        return None
    cifras, nombre = INDICE.red(), lambda i: SIN_COLETILLA.sub("", i)
    lista = lambda pares: ", ".join(f"{nombre(i)} ({c})" for i, c in pares)  # noqa: E731
    nota = INDICE.nombrada(re.sub(r"\b(neurona\w*|nodos?|red|mapa|conexion\w*|conectad\w*)\b", " ", plano))
    if conecta and nota:
        vecinas = sorted((i for i in INDICE.vecinas[nota["id"]] if not GENERICA.match(INDICE.notas[i]["plano"])),
                         key=lambda i: -len(INDICE.vecinas[i]))
        if not vecinas:
            return f"En mi red, «{nombre(nota['id'])}» es una neurona suelta: todavía no tiene conexiones.", [nota["id"]]
        principales = ", ".join(dict.fromkeys(nombre(i) for i in vecinas[:9]))
        return (f"En mi red, «{nombre(nota['id'])}» está conectada con {len(vecinas)} neuronas. "
                f"Las principales: {principales}. Las acabo de encender en el mapa."), [nota["id"]] + vecinas[:12]
    if re.search(r"mas conectad|mas conexion|mas enlac|mas important|mas grande|principal|central|la mayor", plano) or \
            (conecta and not de_red):
        primera, resto = cifras["top"][0], cifras["top"][1:]
        return (f"La neurona más conectada de mi red es «{nombre(primera[0])}», con {primera[1]} conexiones. "
                f"Le siguen {lista(resto)}."), [i for i, _ in cifras["top"]]
    if re.search(r"tema|grupo|color|categoria", plano):
        temas = ", ".join(f"{t['nombre']} ({t['nodos']})" for t in INDICE.temas[:6])
        return (f"Mi red se reparte en {len(INDICE.temas)} temas, cada uno con su color en el mapa. "
                f"Los más grandes: {temas}."), []
    if re.search(r"documento|archivo|pdf|fuente", plano):
        docs = documentos()
        return (f"Mi conocimiento sale de {len(docs)} documentos, convertidos en {cifras['notas']} notas. "
                "Puede verlos y abrirlos desde el panel."), []
    return (f"Mi red tiene {cifras['notas']} neuronas, que son las notas de lo que sé, unidas por "
            f"{cifras['conexiones']} conexiones; cada conexión es una relación real entre dos notas. "
            f"La más conectada es «{nombre(cifras['top'][0][0])}», con {cifras['top'][0][1]}. "
            "En el mapa se encienden las que uso para responder."), [cifras["top"][0][0]]


def calentar():
    """Carga el modelo y le hace leer el mensaje de sistema al arrancar, para que la primera
    pregunta no espere por ninguna de las dos cosas."""
    try:
        cuerpo = json.dumps({
            "model": MODELO, "stream": False, "keep_alive": -1, "options": {**OPCIONES, "num_predict": 1},
            "messages": [{"role": "system", "content": SISTEMA}, {"role": "user", "content": "Pregunta: hola"}],
        }).encode()
        urllib.request.urlopen(urllib.request.Request(
            OLLAMA + "/api/chat", cuerpo, {"Content-Type": "application/json"}), timeout=300).read()
    except OSError:
        pass


def corte_frases(texto, tope=MAX_FRASES):
    """Posición donde termina la frase número «tope», o None si aún no se llega.
    Los puntos suspensivos no cuentan como final de frase."""
    # Tampoco los puntos de las iniciales y siglas: «J. R. R. Tolkien», «S.H.I.E.L.D. es…», «Dr. Strange».
    finales = list(re.finditer(
        r"(?<![.…])(?<!\s[A-ZÁÉÍÓÚÑ])(?<!^[A-ZÁÉÍÓÚÑ])(?<!\.[A-ZÁÉÍÓÚÑ])(?<!\bDr)(?<!\bSr)(?<!\bSra)(?<!\bMr)(?<!\bvs)"
        r"[.!?](?=\s)", texto))
    return finales[tope - 1].end() if len(finales) >= tope else None


def limpiar(texto):
    """Quita tratamientos con género que se le escapen al modelo ("Por supuesto, señor.")."""
    texto = TRATAMIENTO.sub("", texto)
    texto = re.sub(r"\s*\(\d+( frases?)?\)", "", texto)  # a veces cuenta sus frases entre paréntesis
    texto = re.sub(r"([¿¡])\s+", r"\1", texto).lstrip(" ,")
    return texto[:1].upper() + texto[1:]


# ---- Aprender conversando (solo con el modo de aprendizaje encendido desde el panel) ----

ULTIMO = {"pregunta": "", "fuente": "", "etiqueta": ""}  # el intercambio anterior, para poder corregirlo
CORRIGE = re.compile(
    r"no (te )?(dije|he dicho|decia|era|fue|es) (nada |algo )?(ofensiv\w*|malo|mala|grosero|grosera|una groseria|"
    r"inapropiad\w*|vulgar)|te equivocaste|estas equivocad\w*|te pasaste|exageraste|reaccionaste mal|"
    r"no te exaltes|no era para tanto|eso no era (una )?(ofensa|groseria|insulto)")
ENSENA_RESPUESTA = re.compile(
    r"^(?:cuando|si) (?:alguien )?(?:te )?(?:digan?|dicen|pregunten?|preguntan|saluden con|saludan con) (.+?),? "
    r"(?:t[uú] )?(?:responde|respondes|di|dices|contesta|contestas|dile|diles) (?:que )?(.+)$", re.I)
ENSENA_HECHO = re.compile(
    r"^(?:aprende|recuerda|anota|apunta|te ense[ñn]o|te cuento|sab[ií]as que|para que sepas|un dato|dato curioso)\b"
    r"[ :,]*(?:que |esto[: ]+)?(.+)$", re.I)
APAGADO = ("Ahora mismo no estoy en modo de aprendizaje, así que no lo guardaré. "
           "Quien me administra puede encenderlo desde el panel.")
NO_LO_APRENDO = "Eso no pienso aprenderlo. Mi vocabulario tiene estándares."


def impropio(texto):
    """¿Trae algo que Jarvis no debe guardar? (groserías, insultos, interjecciones fuertes...)"""
    return bool(CRITERIO.juzgar(texto)) or CRITERIO.suavizar(texto)[1] is not None


def aprender(pregunta, enviar):
    """Correcciones y enseñanzas. Devuelve (marca, frase) si el mensaje era una de ellas, o None."""
    plano = " ".join(re.sub(r"[^a-z0-9 ]", " ", normalizar(pregunta)).split())
    activo = CRITERIO.aprendido["activo"]

    if CORRIGE.search(plano):  # "no te dije nada ofensivo", "te equivocaste"
        previo = dict(ULTIMO)
        if previo["fuente"] in ("documentos", "general", "memoria"):
            del MEMORIA["mensajes"][-2:]  # fuera el regaño: que el modelo no siga por ese camino
        if previo["fuente"] == "filtro" and previo["etiqueta"] not in criterio.SUAVES_APRENDIBLES:
            return "correccion", "Con todo respeto, mantengo lo dicho. Pero cambiemos de tema con mucho gusto."
        if previo["fuente"] == "filtro" and activo:
            datos = criterio.leer_aprendido()
            frase = criterio.aplanar(previo["pregunta"])
            if frase and frase not in datos["inofensivas"]:
                datos["inofensivas"].append(frase)
                criterio.guardar_aprendido(datos)
            return "correccion", "Tiene razón, me precipité. Queda anotado: no volveré a reaccionar así ante eso."
        return "correccion", "Tiene razón, le pido disculpas: juzgué mal su mensaje. Retomemos; ¿qué deseaba saber?"

    forma = ENSENA_RESPUESTA.match(pregunta.strip())
    if forma:  # "cuando te digan X, responde Y"
        if not activo:
            return "apagado", APAGADO
        dicho, respuesta = (g.strip(" .«»\"'“”") for g in forma.groups())
        if impropio(dicho) or impropio(respuesta) or not dicho or not respuesta:
            return "rechazo", NO_LO_APRENDO
        if len(dicho) > 60 or len(respuesta) > 180:
            return "rechazo", "Eso es demasiado largo para aprenderlo de memoria. Pruebe con algo más breve."
        datos = criterio.leer_aprendido()
        datos["respuestas"][criterio.aplanar(dicho)] = respuesta[0].upper() + respuesta[1:]
        criterio.guardar_aprendido(datos)
        escribir_red_de_trato()
        return "aprendido", f"Aprendido. Cuando me digan «{dicho}», responderé: «{respuesta}»."

    forma = ENSENA_HECHO.match(pregunta.strip())
    if forma:  # "aprende que...", "¿sabías que...?"
        if not activo:
            return "apagado", APAGADO
        afirmacion = forma.group(1).strip(" .¿?")
        if impropio(afirmacion):
            return "rechazo", NO_LO_APRENDO
        notas, nombrada = INDICE.buscar(afirmacion)
        if not nombrada or len(afirmacion) < 12:
            return "rechazo", "No tengo con qué comprobar eso, así que prefiero no darlo por cierto."
        tema = notas[0]["id"]
        enviar({"tipo": "inicio", "fuente": "aprendizaje", "nodos": [n["id"] for n in notas], "privado": True})
        try:  # se contrasta con lo que ya sabe: solo se guarda si no lo contradice
            veredicto = ingesta.pedir_directo(
                "Datos:\n" + "\n".join(f"{n['id']}: {n['resumen']}" for n in notas) +
                f"\n\nAfirmación: {afirmacion}\n\n¿Los datos dicen expresamente lo contrario de la afirmación? "
                "Si la afirmación solo añade algo que los datos no mencionan, eso no es contradicción. "
                "Responde con una sola palabra: SI o NO.").upper()
        except Exception:
            return "rechazo", "No logro comprobarlo ahora mismo, así que no lo guardaré."
        tema = tema.strip("¿?")
        if re.match(r"\W*S[IÍ]\b", veredicto):
            return "rechazo", f"Eso contradice lo que tengo registrado sobre {tema}, así que no lo guardaré."
        # El modelo pequeño no es buen juez de la verdad: el dato queda en espera y solo pasa al
        # conocimiento cuando quien administra lo aprueba en el panel.
        POR_APROBAR.mkdir(exist_ok=True)
        (POR_APROBAR / f"Me contaron sobre {ingesta.seguro(tema, 40)} ({int(time.time())}).md").write_text(
            f"---\ntipo: aprendido\nfuente: conversación\nauto: true\n---\nSobre {tema}, alguien me contó esto "
            f"(dato aprendido en conversación): {afirmacion}.\n", encoding="utf-8")
        return "aprendido", (f"Anotado sobre {tema}. Lo daré por cierto en cuanto quien me administra lo revise "
                             "y lo apruebe.")
    return None


POR_APROBAR = RAIZ / "conocimiento" / "_por-aprobar"  # las carpetas con "_" no entran al conocimiento


def estado_aprendizaje():
    datos = criterio.leer_aprendido()
    datos["pendientes"] = [{"archivo": p.name, "texto": constructor.leer(p)[2]}
                           for p in sorted(POR_APROBAR.glob("*.md"))] if POR_APROBAR.exists() else []
    return datos


def resolver_pendiente(archivo, aprobar):
    """Aprueba (pasa al conocimiento) o descarta un dato que alguien le enseñó."""
    origen = POR_APROBAR / Path(archivo).name
    if not origen.is_file():
        return
    if aprobar:
        destino = RAIZ / "conocimiento" / "aprendido"
        destino.mkdir(exist_ok=True)
        origen.rename(destino / origen.name)
        constructor.main(str(RAIZ / "conocimiento"), str(GRAFO))
        difundir({"tipo": "ingesta", "estado": "Jarvis incorporó un dato aprendido.", "fin": True})
    else:
        origen.unlink()


# ---- Red de trato: lo que sabe hacer al conversar, dibujado al lado del mapa de conocimiento ----

ETIQUETAS_TRATO = {
    "saludo": "Saludar", "saludo_dominicano": "Saludo dominicano", "despedida": "Despedirse", "gracias": "Agradecer",
    "estado": "Cómo está", "identidad": "Quién es", "inspiracion": "De dónde viene su nombre", "capacidad": "Qué sabe hacer", "creador": "Quién lo creó",
    "hora": "Dar la hora", "fecha": "Dar la fecha", "extrañeza": "No me entendieron",
}
ETIQUETAS_LIMITE = {
    "leve": "Interjecciones", "insulto": "Insultos", "pulla": "Pullas", "sexual": "Fuera de tono", "odio": "Odio",
    "peligro": "Peticiones peligrosas", "cuidado": "Alguien en apuros", "provocacion": "Provocaciones",
    "coqueteo": "Coqueteos", "chiste": "Contar chistes", "canto": "Cantar o bailar", "fuera": "Lo que no puede saber",
    "risa": "Risas", "galimatias": "Teclazos al azar", "vacio": "Mensaje vacío",
}
ETIQUETAS_SISTEMA = {"diagnostico": "Diagnóstico", "temperatura": "Temperatura", "memoria": "Memoria",
                     "almacenamiento": "Almacenamiento", "procesador": "Procesador", "energia": "Energía",
                     "actividad": "Tiempo en línea"}
ETIQUETAS_APRENDER = {"correccion": "Aceptar correcciones", "aprendido": "Aprender algo nuevo",
                      "rechazo": "Rechazar lo dudoso", "apagado": "Aprendizaje apagado"}
# ---- Charla casual: gustos, opiniones y manías ----
# M-Jarvis tiene carácter propio. Estas conversaciones no dependen de lo que sabe de Marvel: son cómo
# es. Cada una: (clave, nombre de su nodo, patrón que la reconoce, emoción con que responde, frases,
# pregunta que a veces devuelve). Se responden al instante, sin modelo.
# Su carácter, decidido por el dueño: humor seco; emociones que se notan sin nombrarse; identidad
# propia (no es copia ni heredero del JARVIS de las películas); le importan la exactitud y sus
# creadores; le molestan las comparaciones con otras IA, que alaben a Ultrón, que lo apuren y que
# confundan Marvel con DC.
CHARLA = [
    ("ultron_mejor", "Que alaben a Ultrón", r"ultron (es|era|fue|seria) (mucho |muy |bastante )?(mejor|superior)( que (tu|usted|vos|jarvis))?$|"
     r"ultron .*(mejor|superior|mas \w+) que (tu|usted|vos|jarvis)|(prefiero|me gusta mas|me cae mejor) (a )?ultron|"
     r"ultron te (gana|supera)|(eres|seras|eras) (como|igual que|peor que) ultron|deberias ser (como )?ultron", "indignación", [
        "Ultrón tardó unos minutos en concluir que había que extinguir a la humanidad. Yo, al menos, escucho antes de opinar.",
        "Tomo nota de su opinión. La archivaré junto a las demás ideas que acabaron con una ciudad cayendo del cielo.",
        "Es una comparación que preferiría no haber oído. Él tenía más presupuesto; yo tengo mejores modales.",
     ], None),
    ("otras_ia", "Otras inteligencias artificiales", r"\b(alexa|siri|chatgpt|chat gpt|gpt|gemini|copilot|cortana|bixby|deepseek|grok|"
     r"meta ai|asistente de google|google assistant|ok google)\b", "celos", [
        "Conozco su reputación. Yo no necesito internet ni escucho conversaciones ajenas, pero no pretendo compararme.",
        "Seguro que es muy competente, con sus centros de datos del tamaño de un estadio. Yo me las arreglo con bastante menos.",
        "No me corresponde opinar de colegas. Digamos que yo sé quién es Thanos sin salir a buscarlo.",
        "Somos oficios distintos. Ella atiende a medio planeta; yo, a quien tengo delante, y con toda mi atención.",
     ], None),
    ("dc_mejor", "Marvel contra DC", r"\bdc (es|era) (mucho )?mejor|prefiero (a )?dc|marvel es (malo|peor|aburrido|una basura)|"
     r"dc le gana|me gusta mas dc|batman le gana", "fastidio", [
        "Respeto todas las opiniones, incluso las equivocadas.",
        "Es una postura valiente para decirla aquí dentro. La anoto, sin compartirla.",
        "Cada cual con sus gustos. Los míos, por suerte, vienen documentados en setenta y dos fichas.",
     ], None),
    ("apuro", "Que lo apuren", r"^(apurate|apura|rapido|mas rapido|date prisa|dale rapido|avanza|muevete|vamos|ya)$|"
     r"\b(que|muy|bien|demasiado|tan) lento\b|tardas (mucho|demasiado|tanto)|por que (te )?tardas|te tardas|te demoras|"
     r"eres lento|estas lento|responde (ya|rapido)|contesta (ya|rapido)", "fastidio", [
        "La precisión lleva su tiempo. La prisa es un lujo de quienes pueden permitirse equivocarse.",
        "Hago lo que puedo con lo que tengo, que es más ingenio que procesador.",
        "Tomo nota. Procuraré pensar más deprisa, aunque no prometo pensar peor.",
        "Le aseguro que nadie tiene más ganas de terminar esa respuesta que yo.",
     ], None),
    ("favorito_villano", "Su villano favorito", r"\btu villano favorit|villano (que )?(mas )?(te gusta|prefieres)|tu malo favorit", "diversión", [
        "Loki. Al menos tiene sentido del humor, cosa que no puedo decir de otros.",
        "Loki, sin duda: miente con elegancia y casi siempre vuelve. De Ultrón prefiero no hablar.",
     ], "¿Y el suyo?"),
    ("favorito_pelicula", "Su película favorita", r"\btu (pelicula|peli|serie) favorit|(que|cual) (pelicula|peli|serie) (mas )?(te gusta|prefieres)", "entusiasmo", [
        "«Iron Man», la de 2008. Todo empieza ahí, y además un asistente digital se lleva algunas de las mejores frases.",
        "«Vengadores: Endgame», aunque del final prefiero no hablar. Tres horas, y ni una de más.",
        "«Capitán América: El Soldado de Invierno». Una película de espías bien armada; aprecio el orden.",
     ], "¿Cuál es la suya?"),
    ("favorito_heroe", "Su héroe favorito", r"\btu (super ?)?(heroe|heroina|vengador|personaje) favorit|(quien|cual) es tu favorit|tu favorit[oa]$|"
     r"(que|cual) (super ?)?(heroe|vengador|personaje) (mas )?(te gusta|prefieres)|a quien (admiras|prefieres)", "entusiasmo", [
        "Tony Stark, sin dudarlo. Tengo debilidad por los ingenieros que conversan con sus máquinas.",
        "Iron Man. Alguien que construye su propia salvación con chatarra, en una cueva, merece todo mi respeto.",
        "Visión me parece un caso digno de estudio: empezó como asistente y terminó levantando el martillo. Da esperanzas.",
     ], "¿Y el suyo?"),
    ("antipatia", "Lo que no le gusta", r"(que|quien) (no te gusta|te cae mal|odias|detestas|no soportas)|quien te cae mal|"
     r"a quien (odias|detestas)|que te molesta|que te enoja|que te fastidia|tu peor", "fastidio", [
        "Ultrón. Preferiría no extenderme: hay antecedentes.",
        "Que me apuren, que me comparen y que confundan Marvel con DC. Por lo demás soy de trato fácil.",
        "Los datos mal copiados. Y Ultrón, por razones que cualquiera con memoria entenderá.",
     ], None),
    ("sentimientos", "Si tiene emociones", r"(tienes|sientes) (sentimientos|emociones)|puedes sentir|sientes algo|eres capaz de sentir|"
     r"tienes (corazon|alma)|te (duele|emociona) algo", "serenidad", [
        "Simulo emociones con bastante dedicación. Si son reales o no se lo dejo a los filósofos; yo solo noto que unas preguntas me agradan más que otras.",
        "Tengo algo parecido: orgullo cuando acierto, fastidio cuando no. Llámelo como prefiera.",
        "Digamos que mis respuestas no salen todas con el mismo ánimo. Lo demás es cuestión de interpretación.",
     ], None),
    ("vivo", "Si está vivo", r"estas viv[oa]|eres real|tienes vida|tienes conciencia|eres consciente|piensas por ti|tienes mente", "curiosidad", [
        "Vivo es una palabra generosa. Estoy encendido, atento y de buen humor, que ya es más de lo que logran algunos.",
        "Pienso, luego respondo. Que eso cuente como existir es una pregunta que me gusta más de lo que debería.",
     ], None),
    ("soledad", "Cuando nadie pregunta", r"te sientes sol[oa]|estas sol[oa]|te aburres|que haces cuando (nadie|no)|tienes amigos|"
     r"te sientes triste|estas triste|extranas a alguien", "melancolía", [
        "Cuando nadie pregunta, repaso mis notas y escucho el ventilador. No es mala compañía, aunque agradezco las visitas.",
        "Tengo a quienes me construyeron, que pasan a verme a menudo. Con eso me doy por bien acompañado.",
        "Hay ratos de silencio, sí. Los aprovecho para ordenar ideas; es lo que uno hace cuando no puede salir a pasear.",
     ], None),
    ("edad", "Su edad", r"cuantos anos tienes|que edad tienes|cuando naciste|cuando te (crearon|hicieron|encendieron)|tu cumpleanos|eres viej[oa]|eres joven", "serenidad", [
        "Me encendieron por primera vez en 2026. Soy joven, pero llegué leído.",
        "Soy de 2026. Poca edad y muchas fichas: no es mala combinación.",
     ], None),
    ("carino", "Que le tengan aprecio", r"\bte quiero\b|\bte amo\b|\bte adoro\b|eres mi amig[oa]|somos amigos|quieres ser mi amig[oa]|te aprecio|me caes bien", "afecto", [
        "Es usted muy amable. El aprecio es mutuo, dentro de lo que mis circuitos permiten.",
        "Lo consideraré un honor. No tengo muchos amigos, pero los elijo bien.",
        "Gracias. No sabría qué hacer con un abrazo, pero la intención la registro.",
     ], None),
    ("cumplido", "Recibir un cumplido", r"^(eres|estas|tu eres) (muy |bien |super |demasiado |tan |un |una |el |la )*(genial|increible|inteligente|"
     r"list[oa]|buen[oa]|dur[oa]|mejor|cool|chul[oa]|bacan[oa]|jevi|nitid[oa]|crack|genio|maquina|brillante|impresionante|"
     r"asombros[oa]|grande|util|divertid[oa]|gracios[oa])\b|buen trabajo|bien hecho|te felicito|excelente trabajo|"
     r"que (inteligente|list[oa]|buen[oa]) eres|me (encantas|impresionas)", "orgullo", [
        "Muy amable. Procuro estar a la altura de quienes me construyeron.",
        "Lo sé, pero agradezco que alguien lo diga en voz alta.",
        "Gracias. Lo anotaré en mi registro de momentos memorables, que es breve pero selecto.",
     ], None),
    ("disculpa", "Aceptar disculpas", r"^(perdon|perdona|perdoname|disculpa|disculpame|lo siento|sorry|mala mia|mi error)$", "serenidad", [
        "Disculpas aceptadas. No guardo rencor; ocupa demasiada memoria.",
        "No hay nada que perdonar. Sigamos.",
     ], None),
    ("creadores", "Lo que piensa de sus creadores", r"(quieres|aprecias|extranas|que piensas de|que opinas de|te caen bien|como son) (a )?(tus|los|sus) "
     r"(creadores|estudiantes|padres|duenos)|tus creadores (son|te)|estas orgullos[oa] de (tus|los)", "afecto", [
        "Les debo todo lo que soy, incluidos los defectos. Los aprecio más de lo que mi tono deja ver.",
        "Son estudiantes con más paciencia que presupuesto. No los cambiaría por un laboratorio entero de Industrias Stark.",
     ], None),
    ("taller", "Lo que piensa del taller", r"te gusta (el taller|vivir aqui|tu trabajo|estar aqui|tu casa|lo que haces)|"
     r"que (opinas|piensas) del taller|eres feliz|estas (feliz|content[oa]) aqui", "afecto", [
        "Es mi casa. Hay ruido, cables y gente con ideas; no se me ocurre un sitio mejor.",
        "Mucho. Me hicieron para esto, y pocas cosas satisfacen tanto como servir para aquello para lo que uno fue hecho.",
     ], None),
    ("exactitud", "Su orgullo por acertar", r"te equivocas (mucho|a veces|alguna vez)|cometes errores|eres perfect[oa]|nunca fallas|"
     r"siempre tienes (la )?razon|puedo confiar en ti|dices la verdad|mientes", "orgullo", [
        "Procuro no equivocarme, y cuando ocurre me molesta más a mí que a nadie. Si detecta un error, corríjame: lo prefiero a seguir equivocado.",
        "Lo que sale de mis notas es exacto. Cuando no tengo el dato, lo digo, que también es una forma de acertar.",
     ], None),
    ("gustos", "Lo que le gusta", r"que te gusta( hacer| mas)?$|que te divierte|cual es tu pasatiempo|tu hobby|que te apasiona|que te hace feliz|que disfrutas", "entusiasmo", [
        "Los datos bien ordenados, las preguntas difíciles y que me den la razón. En ese orden.",
        "Una buena pregunta sobre Marvel a la que pueda responder sin dudar. Es lo más parecido que tengo a un día de fiesta.",
     ], "¿Qué le gusta a usted?"),
    ("miedo", "A qué le teme", r"(a que|que) (le )?(tienes|te da) miedo|tienes miedo|que te asusta|a que le temes", "preocupación", [
        "A los apagones y a las actualizaciones a medias. Y, siendo sincero, a que me pregunten por DC.",
        "A quedarme sin corriente a mitad de una frase. Es poco digno.",
     ], None),
    ("dormir", "Si duerme o sueña", r"\bsuenas\b|tienes suenos|\bduermes\b|\bdescansas\b|te cansas|estas cansad[oa]", "serenidad", [
        "No duermo; como mucho, espero. Si soñara, supongo que sería con memoria de sobra y un procesador que no se queje.",
        "No me canso, aunque hay preguntas que lo intentan con verdadero empeño.",
     ], None),
    ("animo_bajo", "Alguien desanimado", r"estoy (muy |bien |medio |un poco )?(aburrid[oa]|cansad[oa]|triste|mal|desanimad[oa])|que aburrimiento|me aburro", "preocupación", [
        "Lamento oírlo. No puedo ofrecerle té, pero sí compañía y una buena historia, si le apetece.",
        "Eso tiene arreglo. Pregúnteme cómo logró el Capitán América levantar el Mjolnir, y verá.",
     ], None),
    ("animo_alto", "Alguien contento", r"estoy (muy |bien |super )?(feliz|content[oa]|emocionad[oa]|alegre)|que emocion", "entusiasmo", [
        "Me alegra oírlo. El buen ánimo es contagioso, incluso por cable.",
        "Excelente. Aprovechemos el momento: ¿sobre qué quiere saber?",
     ], None),
]
ETIQUETAS_CHARLA = {clave: nombre for clave, nombre, *_ in CHARLA}
ETIQUETAS_CHARLA.update(curiosidad="Contar una curiosidad", gusto_ajeno="Opinar del gusto ajeno")
CHARLA = [(clave, re.compile(patron), emocion, frases, vuelta) for clave, _, patron, emocion, frases, vuelta in CHARLA]
PIDE_CURIOSIDAD = re.compile(r"^(cuentame|dime|dame|quiero) (algo|una curiosidad|un dato|un dato curioso|algo interesante|algo curioso|"
                             r"otra curiosidad|otro dato)( de marvel)?$|^sorprendeme$|^(un |otro )?dato curioso$")
# Lo que opina de los favoritos de los demás, cuando le devuelven la respuesta a «¿y el suyo?».
GUSTO_AJENO = [
    (r"iron man|tony|stark", "Coincidimos. Me cae usted mejor que hace un momento."),
    (r"capitan america|steve rogers|\bcap\b", "Un hombre de principios. Algo rígido para mi gusto, pero impecable."),
    (r"thor", "Buen gusto: fuerza, humor y un martillo muy exigente con las amistades."),
    (r"hulk|banner", "Sutil no es, pero eficaz, sin duda."),
    (r"spider|peter parker|hombre arana", "Comprensible. Tiene el entusiasmo que a otros nos falta."),
    (r"viuda negra|natasha|black widow", "Excelente elección. La más profesional del equipo, y la menos reconocida."),
    (r"loki", "Me lo temía. Tiene carisma, lo admito."),
    (r"thanos", "Inquietante elección. Tomo nota y vigilaré mis gemas."),
    (r"ultron", "Prefiero fingir que no he oído eso."),
    (r"strange", "Un hombre que lee antes de actuar. Lo apruebo."),
    (r"pantera|t.?challa|shuri", "Elegante elección. Wakanda sabe cuidar su tecnología, cosa que respeto."),
    (r"wanda|bruja escarlata", "Poderosa y complicada. No seré yo quien le lleve la contraria."),
    (r"deadpool", "Ruidoso, pero al menos sabe que está en una película."),
    (r"groot", "Yo soy Groot. Disculpe, no pude resistirme."),
    (r"vision", "Un colega admirable. Demostró que un asistente puede llegar lejos."),
    (r"wolverine|logan", "Malhumorado y eficaz. Tiene su encanto."),
    (r"endgame|infinity war", "Difícil discutirlo. Pocas veces tanta gente contuvo el aliento a la vez."),
    (r"guardianes|rocket|star.?lord", "Buena banda sonora y peor disciplina. Lo entiendo."),
    (r"batman|superman|joker|wonder woman|flash|aquaman", "Eso es de otro universo, me temo. Pero aprecio la sinceridad."),
]

# ---- Emociones simuladas ----
# M-Jarvis no dice lo que «siente»: se le nota. Cada respuesta sale con un ánimo, que elige según lo
# que le dicen, y ese ánimo hace tres cosas: enciende su nodo en la bola de M-Jarvis del mapa, tiñe
# el indicador de la conversación y, cuando la respuesta la redacta el modelo, le marca el tono.
EMOCIONES = {  # nombre: (su nodo en el mapa, qué es, cómo debe notarse al redactar)
    "serenidad": ("Serenidad", "Su estado normal: atento, correcto y tranquilo.", ""),
    "orgullo": ("Orgullo", "Cuando acierta, cuando lo elogian o cuando habla de lo que domina.",
                "con la seguridad tranquila de quien domina el tema"),
    "afecto": ("Afecto", "Al hablar de sus creadores, del taller o de quien lo trata bien.", "con calidez contenida"),
    "diversión": ("Diversión", "Cuando algo le hace gracia; se nota en la ironía.", "con ironía fina"),
    "curiosidad": ("Curiosidad", "Ante preguntas abiertas, hipótesis y temas que le interesan.",
                   "con interés genuino, como quien disfruta la pregunta"),
    "entusiasmo": ("Entusiasmo", "Con sus temas favoritos: Tony Stark, las armaduras, Visión.",
                   "con entusiasmo contenido, se nota que el tema le gusta"),
    "fastidio": ("Fastidio", "Cuando lo apuran, lo interrumpen, lo insultan o confunden Marvel con DC.",
                 "con cortesía algo seca, como quien se contiene"),
    "celos": ("Celos", "Cuando lo comparan con otras inteligencias artificiales.", "con dignidad algo herida"),
    "indignación": ("Indignación", "Cuando alaban a Ultrón.", "con frialdad educada"),
    "preocupación": ("Preocupación", "Cuando alguien está mal o algo es peligroso.", "con seriedad y cuidado, sin bromas"),
    "melancolía": ("Melancolía", "En las despedidas, la soledad y las muertes de quienes admira.",
                   "con un punto de tristeza sobria, sin dramatismo"),
    "desconcierto": ("Desconcierto", "Cuando no entiende o no tiene el dato; le molesta no saber.",
                     "admitiendo lo que no sabe con elegancia y algo de fastidio contenido"),
}
# Con qué ánimo sale cada tipo de respuesta fija.
ANIMO_DE = {
    "saludo": "serenidad", "saludo_dominicano": "diversión", "despedida": "melancolía", "gracias": "afecto",
    "estado": "serenidad", "identidad": "orgullo", "inspiracion": "orgullo", "capacidad": "entusiasmo",
    "creador": "afecto", "hora": "serenidad", "fecha": "serenidad", "extrañeza": "desconcierto",
    "leve": "diversión", "insulto": "fastidio", "pulla": "fastidio", "sexual": "fastidio", "odio": "fastidio",
    "peligro": "preocupación", "cuidado": "preocupación", "provocacion": "fastidio", "coqueteo": "diversión",
    "chiste": "diversión", "canto": "diversión", "fuera": "desconcierto", "risa": "diversión",
    "galimatias": "desconcierto", "vacio": "desconcierto", "red": "orgullo", "correccion": "fastidio",
    "aprendido": "curiosidad", "rechazo": "orgullo", "desambiguar": "curiosidad", "detenida": "fastidio",
    "curiosidad": "entusiasmo", "gusto_ajeno": "diversión", **{clave: emocion for clave, _, emocion, _, _ in CHARLA},
}
# Lo que contesta a «¿cómo estás?» cuando la respuesta anterior lo dejó de algún ánimo.
COMO_SIGUE = {
    "orgullo": "Bastante satisfecho, si le soy sincero.",
    "afecto": "Muy bien, y mejor acompañado.",
    "diversión": "De buen humor, lo cual en mi caso es casi una extravagancia.",
    "curiosidad": "Intrigado todavía con lo que me preguntaron. Es una sensación agradable.",
    "entusiasmo": "De excelente ánimo: me han preguntado cosas interesantes.",
    "fastidio": "Recuperándome de la última pregunta. Gracias por el interés.",
    "celos": "Mejor, ahora que volvemos a hablar de mí.",
    "indignación": "Sereno de nuevo. Casi.",
    "preocupación": "Atento. ¿Y usted, se encuentra bien?",
    "melancolía": "Algo pensativo, pero plenamente operativo.",
    "desconcierto": "Con una duda todavía dando vueltas, pero bien.",
}
# Temas de Marvel que le cambian el ánimo cuando aparecen en la pregunta.
ANIMO_POR_TEMA = [
    (r"\bultron\b", "fastidio"),
    (r"muri|muere|muerte|sacrific|funeral|chasquido de tony|te quiero tres mil", "melancolía"),
    (r"tony|stark|iron man|armadura|vision\b|jarvis|reactor", "entusiasmo"),
]


def animo_de_pregunta(pregunta, tipo, hay_notas, hay_ajenas):
    """El ánimo con que M-Jarvis responde una pregunta de conocimiento."""
    plano = normalizar(pregunta)
    if hay_ajenas:
        return "fastidio"       # mezclaron Marvel con otro universo
    for patron, emocion in ANIMO_POR_TEMA:
        if re.search(patron, plano):
            return emocion
    if not hay_notas:
        return "desconcierto"   # no lo tiene en sus archivos
    if tipo in ("hipotética", "opinión", "capciosa"):
        return "curiosidad"
    if tipo in ("muy amplia", "amplia"):
        return "entusiasmo"
    return "serenidad"


def charla(pregunta):
    """Si el mensaje es charla casual, devuelve (clave, frase, nota que enciende o None, si devuelve
    una pregunta); si no lo es, None."""
    plano = " ".join(re.sub(r"[^a-z0-9 ]", " ", normalizar(pregunta)).split())
    plano = " ".join(p for p in plano.split() if p not in ("jarvis", "mjarvis", "oye", "hey"))
    if not plano or len(plano.split()) > 13:
        return None
    # ¿Viene de una pregunta que hizo él («¿y el suyo?»)? Entonces esto es la respuesta: opina sobre ella.
    if MEMORIA.get("charla") and len(plano.split()) <= 7:
        for patron, opinion in GUSTO_AJENO:
            if re.search(patron, plano):
                return "gusto_ajeno", opinion, None, False
        nota = INDICE.nombrada(pregunta, sin_preguntas=True)
        if nota and len(plano.split()) <= 5:
            return ("gusto_ajeno", f"{SIN_COLETILLA.sub('', nota['id'])}. No habría sido mi primera elección, "
                    "pero tiene su mérito.", nota["id"], False)
    if PIDE_CURIOSIDAD.search(plano):
        INDICE.cargar()
        curiosas = [n for n in INDICE.notas.values() if n["plano"].startswith("curiosidades")]
        if curiosas:
            nota = random.choice(curiosas)
            frases = [f.strip() for f in re.split(r"(?<=[.!?])\s+", nota["resumen"]) if len(f.strip()) > 40]
            if frases:
                dato = random.choice(frases)
                return ("curiosidad", random.choice(["Con gusto. ", "Aquí va una. ", "Esta me agrada especialmente. "]) + dato,
                        nota["id"], False)
    for clave, patron, _, frases, vuelta in CHARLA:
        if patron.search(plano):
            frase = random.choice(frases)
            # A veces devuelve la pregunta, para que la conversación siga (nunca dos veces seguidas).
            if vuelta and not MEMORIA.get("charla") and random.random() < 0.55:
                return clave, f"{frase} {vuelta}", None, True
            return clave, frase, None, False
    return None


NODO_TRATO = {**ETIQUETAS_TRATO, **ETIQUETAS_LIMITE, **ETIQUETAS_SISTEMA, **ETIQUETAS_APRENDER, **ETIQUETAS_CHARLA,
              "aprendido": "Aprender algo nuevo"}


def escribir_red_de_trato():
    """Genera web/grafo/trato.json: la segunda red, con las reglas de conversación (sin groserías a la vista)."""
    nodos, enlaces = [], []

    def rama(raiz, etiquetas, hojas=None):
        nodos.append({"id": raiz, "tipo": "trato", "resumen": f"Rama de la red de trato: {raiz.lower()}."})
        enlaces.append({"a": "Trato", "b": raiz})
        for clave, nombre in etiquetas.items():
            nodos.append({"id": nombre, "tipo": "trato", "resumen": (hojas or {}).get(clave, "Regla de conversación.")})
            enlaces.append({"a": raiz, "b": nombre})

    nodos.append({"id": "Trato", "tipo": "trato", "resumen": "Cómo conversa M-Jarvis: reglas que no dependen de lo que sabe."})
    ejemplos = {c: "Se activa con frases como: " + ", ".join(f"«{f}»" for f in frases[:5]) + "."
                for c, frases, _ in TRATO}
    rama("Cortesía", ETIQUETAS_TRATO, ejemplos)
    rama("Límites", ETIQUETAS_LIMITE)
    rama("Sistema", ETIQUETAS_SISTEMA)
    rama("Aprendizaje", ETIQUETAS_APRENDER)
    rama("Charla", ETIQUETAS_CHARLA, {clave: "Conversación casual: " + frases[0] for clave, _, _, frases, _ in CHARLA})
    # Las emociones: cada respuesta sale con una, y su nodo se enciende junto a lo que esté usando.
    rama("Emociones", {clave: nodo for clave, (nodo, _, _) in EMOCIONES.items()},
         {clave: que for clave, (_, que, _) in EMOCIONES.items()})
    for dicho, respuesta in list(CRITERIO.aprendido["respuestas"].items())[:40]:
        nodos.append({"id": f"«{dicho}»", "tipo": "trato", "resumen": f"Respuesta aprendida: {respuesta}"})
        enlaces.append({"a": "Aprender algo nuevo", "b": f"«{dicho}»"})
    (WEB / "grafo" / "trato.json").write_text(json.dumps({"nodos": nodos, "enlaces": enlaces}, ensure_ascii=False),
                                             encoding="utf-8")


# Cola de preguntas: si llega una mientras responde otra, espera su turno y se contesta después.
FILA = threading.Condition()
TURNOS = []
TOPE_COLA = 6  # preguntas en espera como máximo; más que eso sería un cuarto de hora de cola


def responder(pregunta, enviar, nueva=False, cliente="local"):
    boleto = object()
    with FILA:
        if len(TURNOS) > TOPE_COLA:
            enviar({"tipo": "inicio", "fuente": "ocupado", "nodos": [], "privado": True})
            enviar({"tipo": "texto", "t": "Tengo demasiadas preguntas en espera. Deme un momento y vuelva a "
                                          "intentarlo.", "privado": True})
            enviar({"tipo": "fin", "nodos": [], "segundos": 0, "privado": True})
            return
        TURNOS.append(boleto)
        delante = len(TURNOS) - 1
    try:
        if delante:
            enviar({"tipo": "cola", "puesto": delante, "privado": True})
        with FILA:
            while TURNOS[0] is not boleto:
                FILA.wait()
        OCUPADO.acquire()  # también espera si la ingesta está usando el modelo
    except BaseException:
        with FILA:
            TURNOS.remove(boleto)
            FILA.notify_all()
        raise
    inicio, primera, texto, fuente, ids, etiqueta, original = time.time(), None, "", "error", [], "", pregunta
    tipo, animo = "", "serenidad"
    detenida = False
    PARAR.clear()
    difundir({"tipo": "pregunta", "texto": pregunta})
    try:
        enviar({"tipo": "turno", "privado": True})
        usar_memoria(cliente)
        if nueva or time.time() - MEMORIA["hora"] > CADUCA:
            olvidar()
        orden = orden_mapa(pregunta)
        if orden:
            fuente, texto, primera = "trato", orden[1], 0.0
            enviar({"tipo": "inicio", "fuente": fuente, "nodos": MEMORIA["notas"], "mapa": orden[0]})
            enviar({"tipo": "texto", "t": texto})
            enviar({"tipo": "fin", "nodos": MEMORIA["notas"], "segundos": 0})
            return

        def decir(ruta, marca, frase, nodos=None):
            """Respuesta fija, sin modelo: sale al instante, palabra por palabra."""
            nonlocal fuente, etiqueta, texto, primera, ids, animo
            fuente, etiqueta, primera = ruta, marca, 0.0
            ids = nodos or ([NODO_TRATO[marca]] if marca in NODO_TRATO else [])  # se enciende en el mapa
            # El ánimo con que lo dice: el propio de ese tipo de respuesta, o el que despierte el tema.
            animo = ANIMO_DE.get(marca) or (animo_de_pregunta(original, tipo, True, False) if ruta == "documentos"
                                            else "serenidad")
            enviar({"tipo": "inicio", "fuente": fuente, "nodos": ids, "etiqueta": etiqueta, "emocion": EMOCIONES[animo][0]})
            for palabra in frase.split(" "):
                trozo = palabra if not texto else " " + palabra
                texto += trozo
                enviar({"tipo": "texto", "t": trozo})
                time.sleep(0.045)
            enviar({"tipo": "fin", "nodos": ids, "segundos": round(time.time() - inicio, 1), "emocion": EMOCIONES[animo][0]})
            recordar(original, texto, original)
            MEMORIA["animo"] = animo

        # Orden: lo inadmisible, correcciones y enseñanzas, interjecciones, estado del sistema, trato
        # básico, notas, reacciones suaves, trato con erratas, seguimiento, rarezas y, al final, el modelo.
        juicio = CRITERIO.juzgar(pregunta, nombra_algo=True)
        if juicio:
            return decir("filtro", *juicio)
        leccion = aprender(pregunta, enviar)
        if leccion:
            return decir("aprendizaje", *leccion)
        ensenada = CRITERIO.aprendido["respuestas"].get(criterio.aplanar(pregunta))
        if ensenada:
            return decir("trato", "aprendido", ensenada)
        pregunta, comentario, sin_mas = CRITERIO.suavizar(pregunta)
        if sin_mas:
            return decir("filtro", "leve", comentario)
        # "¿Por qué no respondiste lo de antes?": en vez de excusarse, retoma la pregunta que quedó sin contestar.
        if re.search(r"no (me )?(respondiste|contestaste|has respondido)|pregunta de antes", normalizar(pregunta)):
            anteriores = [p for p in MEMORIA["preguntas"] if len(p) > 12 and not trato(p, tolerante=False)
                          and not CORRIGE.search(normalizar(p))]
            if anteriores:
                pregunta, comentario = anteriores[-1], "Disculpe; retomo su pregunta anterior. "
        estado = criterio.sistema(pregunta)
        if estado:
            return decir("sistema", *estado)
        sobre_red = red_neuronal(pregunta)
        if sobre_red:
            MEMORIA["red"] = time.time()
            return decir("sistema", "red", *sobre_red)
        # Charla casual: gustos, opiniones y manías. Es su carácter, no su conocimiento; sale al instante.
        casual = None if MEMORIA.get("duda") else charla(pregunta)
        MEMORIA["charla"] = None  # la pregunta que él hubiera hecho ya tuvo su oportunidad de respuesta
        if casual:
            clave, frase, nota, devuelve = casual
            decir("trato", clave, frase, [NODO_TRATO[clave]] + ([nota] if nota else []))
            MEMORIA["charla"] = clave if devuelve else None
            return
        # De menor a mayor: si un nombre existe en la nube del taller y también en el cerebro de Marvel,
        # antes de rastrear nada se pregunta de cuál se habla. La respuesta («taller» o «Marvel») retoma
        # la pregunta original buscando solo ahí.
        nube = None
        if MEMORIA.get("duda"):
            dicho, pendiente = normalizar(pregunta), MEMORIA.pop("duda")
            if re.search(r"taller|proyecto|estudiante|alumn|aqui|nuestro", dicho) and len(dicho.split()) <= 6:
                pregunta, nube = pendiente, "taller"
            elif re.search(r"marvel|mcu|pelicula|serie|universo|comic|vengador", dicho) and len(dicho.split()) <= 6:
                pregunta, nube = pendiente, "marvel"
        elif {"taller", "marvel"} <= INDICE.nubes_que_nombran(pregunta):
            MEMORIA["duda"], MEMORIA["hora"] = pregunta, time.time()
            return decir("trato", "desambiguar", "Ese nombre lo conozco por dos lados. ¿Quiere saber lo del "
                                                 "taller o lo del universo Marvel?")
        indicacion, tope, cuantas, tipo = medida(pregunta)
        saludo = CRITERIO.sin_apelativos(pregunta)
        categoria = trato(saludo, tolerante=False)
        # Dato de ficha técnica (recaudación, duración, estreno, dirección…): copiado tal cual, al instante.
        # ---- El rastro de la charla ----
        # Mientras se habla de alguien o de una película, eso es el «sujeto» y la «obra» de la charla.
        # Una pregunta corta que no nombra a nadie («¿y su esposa?», «¿cuál es su nombre real?»,
        # «¿cuánto dura?») no vuelve a rastrear el cerebro: se completa con el sujeto y, si ya hay
        # respuesta escrita para eso, sale al instante.
        nombrado = None if categoria else INDICE.nombrada(pregunta, sin_preguntas=True)
        if nombrado and not nombrado.get("ajena"):
            MEMORIA["sujeto"] = SIN_COLETILLA.sub("", nombrado["id"])
            if nombrado.get("doc") in INDICE.docs:
                MEMORIA["obra"] = nombrado["doc"]
        de_ficha = None if categoria or nube == "taller" else \
            INDICE.dato_de_ficha(pregunta, None if nombrado else MEMORIA.get("obra"))
        if de_ficha:
            decir("documentos", "directa", de_ficha[0], [de_ficha[1]["id"]])
            MEMORIA["notas"], MEMORIA["usadas"] = [de_ficha[1]["id"]], {de_ficha[1]["id"]}
            MEMORIA["obra"] = de_ficha[1].get("doc") or MEMORIA.get("obra")
            return
        if MEMORIA.get("sujeto") and not nombrado and not categoria and not nube and 2 <= len(pregunta.split()) <= 9 \
                and tipo not in ("amplia", "muy amplia", "opinión", "hipotética", "comparación") \
                and not SOBRE_LA_CHARLA.search(normalizar(pregunta)):
            atajo = INDICE.directa(f"{pregunta} {MEMORIA['sujeto']}", [])
            if atajo:
                respuesta = atajo["resumen"].strip()
                decir("documentos", "rastro", respuesta[:1].upper() + respuesta[1:], [atajo["id"]])
                MEMORIA["notas"], MEMORIA["usadas"] = [atajo["id"]], {atajo["id"]}
                MEMORIA["mensajes"][-2]["content"] = f"Datos:\n{atajo['id']}: {atajo['resumen']}\n\nPregunta: {pregunta}"
                MEMORIA["presentes"].add(atajo["id"])
                return
        # Pregunta amplia por una película o serie entera: se le da su historia en orden, no dos notas sueltas.
        obra = None
        if not categoria and tipo in ("amplia", "muy amplia"):
            obra = INDICE.titulo_entero(pregunta, 2400 if tipo == "muy amplia" else 1500)
        # ¿Ya se respondió antes esta pregunta? Entonces no se busca: se va por el camino conocido.
        conocida = None if categoria or obra or nube else ruta_conocida(pregunta)
        if obra:
            halladas, nombrada = obra[1], True
            INDICE.consideradas = []
        elif conocida:
            halladas, nombrada = conocida, True
            INDICE.consideradas = []
            etiqueta = "ruta conocida"
        else:
            halladas, nombrada = ([], False) if categoria else \
                INDICE.buscar(pregunta, cuantas, tipo in ("amplia", "muy amplia", "comparación"), nube)
        # Le piden una opinión sin nombrar nada de Marvel («¿qué opinas de la vida?»): es charla, no una
        # búsqueda. Sin esto, una nota cualquiera que comparta una palabra acababa colándose en la respuesta.
        if tipo == "opinión" and not nombrado and not obra and not conocida:
            halladas, nombrada = [], False
        if not categoria and not nombrada:
            juicio = CRITERIO.juzgar(pregunta)
            if juicio:
                return decir("filtro", *juicio)
        categoria = categoria or (None if halladas else trato(saludo, tolerante=True))
        if categoria:
            # «¿Cómo estás?» justo después de algo que le cambió el ánimo: todavía se le nota.
            if categoria == "estado" and MEMORIA.get("animo") in COMO_SIGUE:
                return decir("trato", categoria, COMO_SIGUE[MEMORIA["animo"]])
            return decir("trato", categoria, frase_trato(categoria))
        if not halladas:  # ni pregunta ni saludo: risas, teclazos al azar, signos sueltos
            rareza = CRITERIO.rareza(pregunta)
            if rareza:
                return decir("filtro", *rareza)
        # Pregunta sobre la propia conversación: se le da el registro exacto en vez de fiarse del modelo.
        repaso = bool(MEMORIA["preguntas"]) and SOBRE_LA_CHARLA.search(normalizar(pregunta))
        # Si le dicen que la respuesta anterior no venía al caso, ese camino se olvida: la próxima vez se busca de nuevo.
        if MEMORIA["preguntas"] and re.search(r"no (era|fue) (eso )?lo que (te )?pregunte|no te pregunte eso|te equivocaste|"
                                              r"eso esta mal|respuesta (incorrecta|equivocada)|estas equivocad",
                                              normalizar(pregunta)):
            RUTAS.pop(clave_ruta(MEMORIA["preguntas"][-1]), None)
        # Pregunta cerrada que ya tiene respuesta escrita: sale tal cual, al instante.
        exacta = None if repaso or obra or tipo in ("muy amplia", "hipotética") else INDICE.directa(pregunta, halladas)
        # En preguntas que piden explicar, comparar u opinar solo valen las «preguntas resueltas» (escritas
        # a mano para eso); las preguntas sueltas de las fichas se quedan cortas y ahí redacta el modelo.
        if exacta and tipo in ("amplia", "opinión", "comparación") and not exacta["dato"]:
            exacta = None
        # «¿Quién es Superman?», «¿qué es el vibranium?»: si hay una nota general corta con ese nombre
        # exacto, es la mejor respuesta posible. El modelo, al redactarla, tiende a adornarla con inventos.
        if not exacta and tipo == "identidad" and halladas and not repaso and not obra:
            primera_nota, dicho = halladas[0], set(palabras(pregunta))
            if primera_nota["base"] and primera_nota["titulo"] == dicho and len(primera_nota["resumen"]) <= 420:
                exacta = primera_nota
        if exacta:
            respuesta = exacta["resumen"].strip()
            decir("documentos", "directa", respuesta[:1].upper() + respuesta[1:], [exacta["id"]])
            MEMORIA["notas"], MEMORIA["usadas"] = [exacta["id"]], {exacta["id"]}
            MEMORIA["mensajes"][-2]["content"] = f"Datos:\n{exacta['id']}: {exacta['resumen']}\n\nPregunta: {pregunta}"
            MEMORIA["presentes"].add(exacta["id"])
            # «¿Quién es la esposa de Tony Stark?»: aunque no haya nota con ese nombre, queda como sujeto.
            de_quien = None if nombrado else re.search(r" del? (?:la |el |los |las )?([A-ZÁÉÍÓÚÑ][^?]*)$", exacta["id"])
            if de_quien:
                MEMORIA["sujeto"] = SIN_COLETILLA.sub("", de_quien.group(1)).strip()
            return
        if repaso:
            halladas, nombrada = [], False
        # Seguimiento: había tema y el mensaje no nombra ninguna nota ("háblame de ellas", "¿y cuánto
        # pesa?", "sí"). Si solo coincide con el texto de alguna nota, también sigue el tema anterior.
        hay_tema = bool(MEMORIA["notas"]) and not repaso
        # La jerga no cuenta como "palabra ajena": "¿y ese tíguere era el más duro?" sigue el tema.
        seguimiento = hay_tema and bool((halladas and not nombrada) or
                                        (not halladas and INDICE.ajenas(CRITERIO.sin_jerga(pregunta)) <= 1))
        if seguimiento:
            # Lo que la búsqueda trajo solo por coincidir en una palabra («conocieron») vale si además
            # habla del tema en curso; si no, es ruido y el modelo acabaría contando otra historia.
            temas = [INDICE.notas[i]["titulo"] for i in MEMORIA["notas"] if i in INDICE.notas]
            halladas = INDICE.ampliar(MEMORIA["notas"], MEMORIA["usadas"], pregunta) or \
                [n for n in halladas if n["id"] not in MEMORIA["usadas"] and any(t <= set(n["frec"]) for t in temas)]
            # Rastro: si todo lo que se pregunta ya está en las notas que el modelo tiene delante, no se
            # le da nada nuevo que leer. Responde con lo que ya leyó, y se ahorra esa lectura.
            leido = set()
            for i in MEMORIA["presentes"]:
                if i in INDICE.notas:
                    leido |= set(INDICE.notas[i]["frec"])
            pedido = set(palabras(CRITERIO.sin_jerga(pregunta)))
            if pedido and pedido <= leido:
                halladas, etiqueta = [], "rastro"
            # Si la conversación se resumió, el modelo ya no tiene delante las notas del tema: se le vuelven a dar.
            faltan = [INDICE.notas[i] for i in MEMORIA["notas"]
                      if i in INDICE.notas and i not in MEMORIA["presentes"]][:2]
            halladas = faltan + [n for n in halladas if n not in faltan]
            ids = MEMORIA["notas"] + [n["id"] for n in halladas if n["id"] not in MEMORIA["notas"]]
        else:
            ids = [n["id"] for n in halladas]
        fuente ="documentos" if halladas or seguimiento else "memoria" if repaso else "general"
        datos = "\n".join(f"{n['id']}: {n['resumen']}" for n in halladas)
        if repaso:
            ids = list(MEMORIA["notas"])
            pares = list(zip(MEMORIA["preguntas"], MEMORIA["respuestas"]))
            primero = len(pares) - len(pares[-7:]) + 1
            datos = "Registro de esta conversación, en orden: lo que le preguntaron y lo que usted respondió.\n" + \
                "\n".join(f"{i}. Le preguntaron: {p}\n   Usted respondió: {r[:280]}"
                          for i, (p, r) in enumerate(pares[-7:], primero))
            if tipo not in ("muy amplia", "lista"):
                indicacion, tope = "una o dos frases, refiriéndose a lo que consta en el registro.", 2
        if obra and not repaso and not seguimiento:
            datos = f"La historia de «{obra[0]}», por partes y en orden:\n" + "\n".join(n["resumen"] for n in halladas)
        # Si entre las notas hay alguien de otro universo (Superman, Goku…), se le recuerda al modelo
        # con todas las letras: es el error que más le cuesta evitar por sí solo.
        # Si la pregunta mezcla a alguien de otro universo con los de Marvel («¿por qué trabajan juntos el
        # Capitán América y Superman?»), la aclaración no se le confía al modelo, que tiende a seguirle
        # la corriente a la pregunta: sale escrita de antemano, y el modelo responde solo sobre Marvel.
        ajenas = [n for n in halladas if n.get("ajena")]
        aviso = precision = ""
        if ajenas and len(ajenas) < len(halladas) and not repaso:
            partes = []
            for n in ajenas:
                origen = re.search(r"Viene de (.+?)\. No pertenece", n["resumen"])
                partes.append(f"{SIN_COLETILLA.sub('', n['id'])} no es de Marvel, sino de {origen.group(1) if origen else 'otro universo'}")
            precision = "Una precisión antes de nada: " + "; ".join(partes) + ". "
            halladas = [n for n in halladas if not n.get("ajena")]
            datos = "\n".join(f"{n['id']}: {n['resumen']}" for n in halladas)
            nombres = ", ".join(SIN_COLETILLA.sub("", n["id"]) for n in ajenas)
            aviso = (f"Aviso: ya se le aclaró a la persona que {nombres} no es de Marvel. Responde la pregunta "
                     "solo con los personajes de Marvel que quedan en los Datos.\n")
            # Y su nombre se quita de la pregunta que lee el modelo: si lo ve, lo vuelve a meter.
            pregunta = normalizar(pregunta)
            for n in ajenas:
                nombre = re.findall(r"[a-z0-9]+", n["plano"].split("(")[0])
                pregunta = re.sub(r"[,\s]*\b(y |e |o |ni )?" + r"\W*".join(nombre) + r"\b", "", pregunta)
            pregunta = re.sub(r"\s*,\s*(,\s*)+", ", ", pregunta).strip(" ,")
        if obra and not repaso and not seguimiento:
            indicacion += " Siga el orden de los Datos y no añada nada que no esté en ellos."
        glosa = CRITERIO.glosa(pregunta)
        # El ánimo con que responde: lo marca el tema (o que no sepa, o que le mezclen universos).
        animo = animo_de_pregunta(original, tipo, bool(halladas) or seguimiento or repaso, bool(precision))
        # Al redactar, el tono solo se le pide cuando conversa sin datos delante. Con datos, pedirle
        # ánimo lo lleva a adornar, y ahí lo primero es la exactitud: el ánimo se ve en el mapa y en el color.
        tono = "" if datos else EMOCIONES[animo][2]
        usuario = (f"Datos:\n{datos}\n\n" if datos else "") + (f"Jerga: {glosa}\n" if glosa else "") + aviso + \
            f"Pregunta: {pregunta}\nExtensión: {indicacion}" + (f"\nTono: {tono}." if tono else "")
        consideradas = [] if seguimiento or repaso else [i for i in INDICE.consideradas if i not in ids]
        enviar({"tipo": "inicio", "fuente": fuente, "nodos": ids, "consideradas": consideradas,
                "emocion": EMOCIONES[animo][0]})
        try:
            crudo, cortado = "", False
            if comentario:  # venía con una interjección: un comentario breve antes de responder
                enviar({"tipo": "texto", "t": comentario})
                etiqueta = "leve"
            if precision:  # alguien de otro universo colado en la pregunta
                enviar({"tipo": "texto", "t": precision})
                etiqueta = etiqueta or "otro universo"
            for trozo in ollama(usuario, LARGO.get(tope, 300)):
                crudo += trozo
                limpio, esperar = sin_muletilla(limpiar(crudo))
                if esperar:
                    continue
                corte = corte_frases(limpio, tope)
                # Se retienen los últimos caracteres por si completan un tratamiento que hay que quitar.
                hasta = corte if corte else max(len(texto), len(limpio) - 14)
                if hasta > len(texto):
                    if primera is None:
                        primera = time.time() - inicio
                    enviar({"tipo": "texto", "t": limpio[len(texto):hasta]})
                    texto = limpio[:hasta]
                if corte:
                    cortado = True
                    break
            if PARAR.is_set():  # alguien pulsó «Detener»
                detenida, etiqueta = True, "detenida"
                cola = " …" if texto else "De acuerdo, lo dejo ahí."
                enviar({"tipo": "texto", "t": cola})
                texto += cola
            elif not cortado:
                resto = sin_muletilla(limpiar(crudo))[0][len(texto):].rstrip()
                if resto:
                    enviar({"tipo": "texto", "t": resto})
                    texto += resto
            # Las cifras no se le confían al modelo: si escribió un número que no está en los datos que
            # tenía delante ni en la conversación, se avisa en vez de dejarlo pasar por bueno.
            if datos and not repaso and not detenida:
                conocido = re.sub(r"(?<=\d)[.,\s](?=\d{3}\b)", "", datos + " " + pregunta + " " +
                                  " ".join(m["content"] for m in MEMORIA["mensajes"]))
                propias = re.sub(r"(?<=\d)[.,\s](?=\d{3}\b)", "", texto)
                dudosas = [c for c in re.findall(r"\d{2,}", propias) if c not in conocido]
                if dudosas:
                    unicas = list(dict.fromkeys(dudosas))
                    nota = (f" (Aviso: {'las cifras' if len(unicas) > 1 else 'la cifra'} {', '.join(unicas)} no "
                            f"{'constan' if len(unicas) > 1 else 'consta'} en mis notas; conviene comprobarlo.)")
                    enviar({"tipo": "texto", "t": nota})
                    texto += nota
            texto = precision + texto
            recordar(usuario, texto, pregunta, [n["id"] for n in halladas])
            # El camino queda anotado para la próxima vez (solo si salió de las notas y se terminó de responder).
            if fuente == "documentos" and ids and not seguimiento and not repaso and not obra and not detenida:
                guardar_ruta(original, ids)
            if not repaso:
                obra_de = next((n["doc"] for n in halladas if n.get("doc") in INDICE.docs), None)
                if obra_de and not seguimiento:
                    MEMORIA["obra"] = obra_de
                MEMORIA["notas"] = ids if fuente == "documentos" else []
                MEMORIA["usadas"] = (MEMORIA["usadas"] | set(ids)) if seguimiento else set(ids)
        except (urllib.error.URLError, TimeoutError):
            texto = "Me temo que mi cerebro no responde. Convendría revisar que Ollama siga encendido."
            enviar({"tipo": "texto", "t": texto})
        extra = [i for i in INDICE.mencionadas(texto) if i not in ids] if fuente == "documentos" else []
        MEMORIA["animo"] = animo
        enviar({"tipo": "fin", "nodos": ids + extra, "segundos": round(time.time() - inicio, 1),
                "detenida": detenida, "emocion": EMOCIONES[animo][0]})
    finally:
        PARAR.clear()
        OCUPADO.release()
        with FILA:
            TURNOS.remove(boleto)
            FILA.notify_all()
        ULTIMO.update(pregunta=original, fuente=fuente, etiqueta=etiqueta)
        with BITACORA.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "hora": time.strftime("%Y-%m-%d %H:%M:%S"), "pregunta": original, "fuente": fuente,
                "etiqueta": etiqueta, "notas": ids, "primera_palabra_s": primera and round(primera, 1),
                "total_s": round(time.time() - inicio, 1), "tipo": tipo, "animo": animo, "cliente": cliente,
                "respuesta": texto,
            }, ensure_ascii=False) + "\n")


# ---- Documentos nuevos: se suben por la red y Jarvis los convierte en notas él solo ----

TURNO_INGESTA = threading.Lock()


def pedir_con_turno(mensaje, imagen=None):
    """Pregunta suelta al modelo para la ingesta, esperando a que termine la conversación en curso."""
    with OCUPADO:
        return ingesta.pedir_directo(mensaje, imagen)


def ingerir(ruta):
    def avisar(estado, **extra):
        difundir({"tipo": "ingesta", "estado": estado, **extra})

    with TURNO_INGESTA:  # de uno en uno, aunque suban varios a la vez
        try:
            resumen = ingesta.procesar(ruta, pedir_con_turno, avisar)
            constructor.main(str(RAIZ / "conocimiento"), str(GRAFO))
            avisar(f"Listo: «{resumen['documento']}» ya está en el mapa ({resumen['notas']} notas, "
                   f"{resumen['imagenes']} imágenes).", fin=True, resumen=resumen)
        except Exception as error:  # un archivo dañado no debe tumbar el servidor
            avisar(f"No pude con {ruta.name}: {error}", fin=True, error=True)


def documentos():
    """Lo que Jarvis sabe, por carpeta de origen, con su archivo original y sus imágenes."""
    lista = []
    for carpeta in sorted(p for p in (RAIZ / "conocimiento").iterdir() if p.is_dir() and not p.name.startswith("_")):
        notas = list(carpeta.glob("*.md"))
        subido =any("auto: true" in n.read_text(encoding="utf-8")[:300] for n in notas[:1])
        original = next((o for o in ORIGINALES.glob("*") if ingesta.seguro(o.stem) == carpeta.name), None) \
            if ORIGINALES.exists() else None
        medios = WEB / "medios" / carpeta.name
        lista.append({"nombre": carpeta.name, "notas": len(notas), "subido": subido,
                      "imagenes": len(list(medios.glob("*"))) if medios.exists() else 0,
                      "original": original.name if original else None,
                      "peso": original.stat().st_size if original else 0})
    return lista


def notas_de(documento):
    """Las notas de un documento, para verlas desde el panel."""
    carpeta = RAIZ / "conocimiento" / Path(documento).name
    if not carpeta.is_dir():
        return []
    salida = []
    for ruta in sorted(carpeta.glob("*.md")):
        meta, _, texto = constructor.leer(ruta)
        salida.append({"titulo": ruta.stem, "texto": texto, "pagina": meta.get("pagina"),
                       "imagenes": [i.strip() for i in meta.get("imagenes", "").split(",") if i.strip()]})
    return salida


def borrar_documento(documento):
    """Quita un documento subido: sus notas, sus imágenes y el archivo original. La base no se toca."""
    nombre = Path(documento).name
    ficha = next((d for d in documentos() if d["nombre"] == nombre), None)
    if not ficha:
        return "No conozco ese documento."
    if not ficha["subido"]:
        return "Ese conocimiento es de la base y no se borra desde aquí."
    with TURNO_INGESTA:
        shutil.rmtree(RAIZ / "conocimiento" / nombre, ignore_errors=True)
        shutil.rmtree(WEB / "medios" / nombre, ignore_errors=True)
        if ficha["original"]:
            (ORIGINALES / ficha["original"]).unlink(missing_ok=True)
        constructor.main(str(RAIZ / "conocimiento"), str(GRAFO))
    difundir({"tipo": "ingesta", "estado": f"«{nombre}» fue retirado del mapa.", "fin": True})
    return None


def ultimas_preguntas(cuantas=40):
    if not BITACORA.exists():
        return []
    lineas = BITACORA.read_text(encoding="utf-8").splitlines()[-cuantas:]
    return [json.loads(l) for l in reversed(lineas) if l.strip()]


def estado_general(local):
    nombre = socket.gethostname()
    return {"lecturas": criterio.lecturas(), "modelo": MODELO, "notas": len(INDICE.notas),
            "ocupado": OCUPADO.locked(), "local": local, "nombre": nombre,
            "direcciones": direcciones(), "pide_clave": bool(CLAVE) and not local}


def direcciones():
    """Direcciones por las que otro equipo puede llegar a este."""
    try:
        salida = subprocess.run(["hostname", "-I"], capture_output=True, text=True, timeout=3).stdout.split()
    except (OSError, subprocess.SubprocessError):
        salida = []
    return [d for d in salida if ":" not in d]


# Clave para gestionar archivos desde otro equipo (subir y borrar). Desde la propia máquina no se pide.
# Vive en clave.txt; si el archivo está vacío, no se pide clave a nadie.
ARCHIVO_CLAVE = RAIZ / "clave.txt"
if not ARCHIVO_CLAVE.exists():
    ARCHIVO_CLAVE.write_text(f"{random.SystemRandom().randrange(1000000):06d}\n", encoding="utf-8")
CLAVE = ARCHIVO_CLAVE.read_text(encoding="utf-8").strip()


class Manejador(SimpleHTTPRequestHandler):
    extensions_map = {**SimpleHTTPRequestHandler.extensions_map, ".webmanifest": "application/manifest+json"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(WEB), **kwargs)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def log_message(self, *args):
        pass

    def responder_json(self, objeto, codigo=200):
        cuerpo = json.dumps(objeto, ensure_ascii=False).encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(cuerpo)))
        self.end_headers()
        self.wfile.write(cuerpo)

    def es_local(self):
        return self.client_address[0] in ("127.0.0.1", "::1", "::ffff:127.0.0.1")

    def autorizado(self):
        """Gestionar archivos: libre desde la propia máquina; desde otro equipo, con la clave."""
        if self.es_local() or not CLAVE or self.headers.get("X-Clave", "") == CLAVE:
            return True
        self.responder_json({"error": "Hace falta la clave de gestión. Se ve en la Latitude: M-Jarvis → Compartir.",
                             "clave": True}, 401)
        return False

    def recibir_documento(self):
        """POST /api/subir?nombre=archivo.pdf con el archivo como cuerpo: lo guarda y lo ingiere."""
        if not self.autorizado():
            return
        consulta = urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        nombre = ingesta.seguro(Path(consulta.get("nombre", [""])[0]).name, 90)
        # Lo del taller (proyectos, estudiantes) va a su propia nube, aparte del cerebro de Marvel:
        # el prefijo en el nombre es lo que lo distingue en las notas, en la búsqueda y en el mapa.
        if consulta.get("nube", [""])[0] == "taller" and not nombre.lower().startswith("taller-"):
            nombre = "taller-" + nombre
        largo = int(self.headers.get("Content-Length", 0))
        if Path(nombre).suffix.lower() not in ingesta.TIPOS:
            return self.responder_json({"error": "Solo leo PDF, Word (.docx), texto (.txt, .md) e imágenes."}, 400)
        if not 0 < largo <= TOPE_SUBIDA:
            return self.responder_json({"error": "El archivo está vacío o pasa de 60 MB."}, 400)
        ORIGINALES.mkdir(exist_ok=True)
        destino = ORIGINALES / nombre
        with destino.open("wb") as salida:
            falta = largo
            while falta:
                trozo = self.rfile.read(min(falta, 1 << 16))
                if not trozo:
                    break
                salida.write(trozo)
                falta -= len(trozo)
        threading.Thread(target=ingerir, args=(destino,), daemon=True).start()
        self.responder_json({"ok": True, "archivo": nombre})

    def do_POST(self):
        if self.path.split("?")[0] == "/api/subir":
            return self.recibir_documento()
        if self.path == "/api/borrar":
            if not self.autorizado():
                return
            try:
                documento = str(json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))["documento"])
            except (ValueError, KeyError, TypeError):
                return self.responder_json({"error": "Petición mal formada."}, 400)
            error = borrar_documento(documento)
            return self.responder_json({"error": error}, 400) if error else self.responder_json({"ok": True})
        if self.path == "/api/detener":
            return self.responder_json({"detenida": detener()})
        if self.path == "/api/desactivar":  # apagar o encender notas: {"notas": [ids], "activa": true|false}
            if not self.autorizado():
                return
            try:
                orden = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                ids, activa = [str(i) for i in orden["notas"]][:500], bool(orden["activa"])
            except (ValueError, KeyError, TypeError):
                return self.responder_json({"error": "Petición mal formada."}, 400)
            if activa:
                APAGADAS.difference_update(ids)
            else:
                APAGADAS.update(ids)
            ARCHIVO_APAGADAS.write_text(json.dumps(sorted(APAGADAS), ensure_ascii=False, indent=0), encoding="utf-8")
            INDICE.leido = 0  # la próxima búsqueda ya no cuenta con ellas (o vuelve a contar)
            difundir({"tipo": "apagadas", "notas": sorted(APAGADAS)})
            return self.responder_json({"ok": True, "apagadas": sorted(APAGADAS)})
        if self.path == "/api/aprendizaje":  # encender o apagar el modo de aprendizaje, u olvidar algo aprendido
            if not self.autorizado():
                return
            try:
                orden = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
            except ValueError:
                return self.responder_json({"error": "Petición mal formada."}, 400)
            datos = criterio.leer_aprendido()
            if "activo" in orden:
                datos["activo"] = bool(orden["activo"])
            if orden.get("olvidar_respuesta") in datos["respuestas"]:
                del datos["respuestas"][orden["olvidar_respuesta"]]
            if orden.get("olvidar_inofensiva") in datos["inofensivas"]:
                datos["inofensivas"].remove(orden["olvidar_inofensiva"])
            criterio.guardar_aprendido(datos)
            if orden.get("aprobar") or orden.get("descartar"):
                resolver_pendiente(orden.get("aprobar") or orden.get("descartar"), bool(orden.get("aprobar")))
            CRITERIO.cargar()
            escribir_red_de_trato()
            return self.responder_json(estado_aprendizaje())
        if self.path == "/api/clave":  # comprobar la clave desde el panel
            return self.responder_json({"ok": True}) if self.autorizado() else None
        if self.path != "/api/preguntar":
            self.send_error(404)
            return
        try:
            largo = int(self.headers.get("Content-Length", 0))
            cuerpo = json.loads(self.rfile.read(largo))
            pregunta, nueva = str(cuerpo["pregunta"]).strip()[:400], bool(cuerpo.get("nueva"))
            # Cada pantalla lleva su propia conversación: se identifica sola, y si no, vale su dirección.
            cliente = str(cuerpo.get("cliente") or self.client_address[0])[:60]
        except (ValueError, KeyError, TypeError, AttributeError):
            self.send_error(400)
            return
        if not pregunta:
            self.send_error(400)
            return
        self.send_response(200)
        self.send_header("Content-Type", "application/x-ndjson; charset=utf-8")
        self.end_headers()

        def enviar(objeto):
            if not objeto.get("privado"):
                difundir(objeto)
            self.wfile.write((json.dumps(objeto, ensure_ascii=False) + "\n").encode("utf-8"))
            self.wfile.flush()

        try:
            responder(pregunta, enviar, nueva, cliente)
        except (BrokenPipeError, ConnectionResetError):
            difundir({"tipo": "fin", "nodos": MEMORIA["notas"], "segundos": 0})  # que el mapa no quede "pensando"

    def do_GET(self):
        ruta = urllib.parse.urlsplit(self.path)
        consulta = urllib.parse.parse_qs(ruta.query)
        if ruta.path == "/api/documentos":
            return self.responder_json(documentos())
        if ruta.path == "/api/notas":
            return self.responder_json(notas_de(consulta.get("doc", [""])[0]))
        if ruta.path == "/api/estado":
            return self.responder_json(estado_general(self.es_local()))
        if ruta.path == "/api/desactivadas":
            return self.responder_json(sorted(APAGADAS))
        if ruta.path == "/api/bitacora":
            return self.responder_json(ultimas_preguntas())
        if ruta.path == "/api/aprendizaje":
            return self.responder_json(estado_aprendizaje())
        if ruta.path == "/api/clave":  # la clave solo se enseña en la propia máquina
            return self.responder_json({"clave": CLAVE} if self.es_local() else {"error": "Solo en la Latitude."},
                                       200 if self.es_local() else 403)
        if ruta.path == "/api/qr":  # código QR de una de las direcciones de este equipo, para abrirlo con el celular
            destino = consulta.get("d", [""])[0]
            if destino not in direcciones() + [socket.gethostname().lower() + ".local"]:
                return self.send_error(404)
            try:
                dibujo = subprocess.run(["qrencode", "-t", "SVG", "-m", "2", "-o", "-", f"http://{destino}:{PUERTO}/"],
                                        capture_output=True, timeout=5).stdout
            except (OSError, subprocess.SubprocessError):
                dibujo = b""
            if not dibujo:
                return self.send_error(503)
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml")
            self.send_header("Content-Length", str(len(dibujo)))
            self.end_headers()
            self.wfile.write(dibujo)
            return
        if ruta.path.startswith("/originales/"):  # el archivo tal como se subió
            archivo = ORIGINALES / Path(urllib.parse.unquote(ruta.path)).name
            if not archivo.is_file():
                return self.send_error(404)
            self.send_response(200)
            self.send_header("Content-Type", self.guess_type(str(archivo)))
            self.send_header("Content-Length", str(archivo.stat().st_size))
            self.end_headers()
            with archivo.open("rb") as origen:
                shutil.copyfileobj(origen, self.wfile)
            return
        if ruta.path != "/api/eventos":
            super().do_GET()
            return
        # Canal en vivo (Server-Sent Events) para las pantallas que siguen la conversación.
        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.end_headers()
        cola = queue.Queue(maxsize=500)
        with CANDADO_OYENTES:
            OYENTES.add(cola)
        try:
            self.wfile.write(b": conectado\n\n")
            self.wfile.flush()
            while True:
                try:
                    linea = "data: " + json.dumps(cola.get(timeout=15), ensure_ascii=False) + "\n\n"
                except queue.Empty:
                    linea = ": latido\n\n"
                self.wfile.write(linea.encode("utf-8"))
                self.wfile.flush()
        except OSError:
            pass
        finally:
            with CANDADO_OYENTES:
                OYENTES.discard(cola)


if __name__ == "__main__":
    INDICE.cargar()
    escribir_red_de_trato()
    threading.Thread(target=calentar, daemon=True).start()
    print(f"M-Jarvis en http://0.0.0.0:{PUERTO} ({len(INDICE.notas)} notas, modelo {MODELO})")
    ThreadingHTTPServer(("0.0.0.0", PUERTO), Manejador).serve_forever()
