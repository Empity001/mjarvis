"""Criterio de M-Jarvis: qué hacer con un mensaje antes de pensar una respuesta.

- Reacciones fijas a groserías, insultos, coqueteos, peticiones peligrosas, etc.
  (comportamiento/reacciones.json).
- Jerga dominicana que hay que explicarle al modelo (comportamiento/jerga.json).
- Lecturas reales del equipo (temperatura, memoria, almacenamiento...) contadas como
  el estado de "el sistema".

Los dos JSON se releen solos cuando cambian: se pueden editar sin reiniciar el servidor.
"""
import difflib
import fnmatch
import json
import os
import random
import re
import shutil
import time
import unicodedata
from pathlib import Path

DATOS = Path(__file__).resolve().parent.parent / "comportamiento"
LETRA_POR_SIGNO = str.maketrans({"0": "o", "1": "i", "3": "e", "4": "a", "5": "s", "7": "t", "@": "a", "$": "s"})
A_MI = {"tu", "tus", "eres", "te", "ti", "usted", "estas", "tienes", "jarvis", "sos"}


ULTIMAS = {}


def elegir(clave, opciones):
    """Una frase al azar, pero nunca la misma que la última vez que esa categoría habló."""
    opciones = list(opciones)
    if len(opciones) > 1 and ULTIMAS.get(clave) in opciones:
        opciones.remove(ULTIMAS[clave])
    ULTIMAS[clave] = random.choice(opciones)
    return ULTIMAS[clave]


def aplanar(texto):
    """Deja el texto listo para comparar: sin tildes (pero con ñ), sin disfraces ("p3nd3jo",
    "p.u.t.a", "puuuta") y con el asterisco como comodín ("p*ta")."""
    t = texto.lower().replace("ñ", "\x00")
    t = "".join(c for c in unicodedata.normalize("NFKD", t) if not unicodedata.combining(c)).replace("\x00", "ñ")
    t = t.translate(LETRA_POR_SIGNO)
    t = re.sub(r"(?<=[a-zñ])[.\-_·](?=[a-zñ])", "", t)
    t = re.sub(r"[^a-zñ* ]", " ", t)
    t = re.sub(r"(.)\1+", r"\1", t)
    return " ".join(t.split())


# Lo que Jarvis aprende conversando (solo con el modo de aprendizaje encendido desde el panel).
APRENDIDO = DATOS / "aprendido.json"
SUAVES_APRENDIBLES = {"pulla", "coqueteo", "chiste", "canto", "fuera", "leve", "risa", "galimatias", "vacio"}


def leer_aprendido():
    base = {"activo": False, "inofensivas": [], "respuestas": {}}
    try:
        base.update(json.loads(APRENDIDO.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return base


def guardar_aprendido(datos):
    APRENDIDO.write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


class Criterio:
    def __init__(self):
        self.marcas = None
        self.cargar()

    def cargar(self):
        archivos = [DATOS / "reacciones.json", DATOS / "jerga.json"]
        marcas = [a.stat().st_mtime for a in archivos] + [APRENDIDO.stat().st_mtime if APRENDIDO.exists() else 0]
        if marcas == self.marcas:
            return
        self.aprendido = leer_aprendido()
        reacciones = json.loads(archivos[0].read_text(encoding="utf-8"))
        jerga = json.loads(archivos[1].read_text(encoding="utf-8"))
        self.leves = {aplanar(p) for p in reacciones["leves"]["palabras"]}
        self.leves_solo = reacciones["leves"]["solo"]
        self.leves_prefijo = reacciones["leves"]["prefijo"]
        self.categorias = []
        for c in reacciones["categorias"]:
            self.categorias.append({
                "id": c["id"], "suave": c.get("suave", False), "dirigido": c.get("dirigido", False),
                "palabras": {aplanar(p) for p in c.get("palabras", [])},
                "frases": [f" {aplanar(f)} " for f in c.get("frases", [])],
                "respuestas": c["respuestas"],
            })
        self.rarezas = reacciones["rarezas"]
        self.jerga = sorted(((aplanar(k), k, v) for k, v in jerga["terminos"].items()), key=lambda x: -len(x[0]))
        self.apelativos = {aplanar(a) for a in jerga.get("apelativos", [])}
        self.marcas = marcas

    # ---- Reacciones ----

    def _coincide(self, categoria, plano, fichas):
        if any(f in plano for f in categoria["frases"]):
            return True
        if categoria["dirigido"] and len(fichas) > 4 and not (set(fichas) & A_MI):
            return False
        palabras = categoria["palabras"]
        for ficha in fichas:
            if ficha in palabras:
                return True
            if "*" in ficha and any(fnmatch.fnmatchcase(p, ficha.replace("*", "?")) for p in palabras):
                return True
            # La grosería pegada a otra cosa: "mamañema-man", "superpendejo".
            if len(ficha) >= 8 and any(len(p) >= 7 and p in ficha for p in palabras):
                return True
            # Disfraces que no caen exactos: "mamagevo", "pendeho".
            if len(ficha) >= 6 and difflib.get_close_matches(ficha, [p for p in palabras if len(p) >= 6], n=1, cutoff=0.86):
                return True
        return False

    def juzgar(self, mensaje, nombra_algo=False):
        """Devuelve (categoría, respuesta) si el mensaje merece una reacción fija, o None.
        Las categorías 'suaves' no saltan cuando la pregunta nombra algo que Jarvis conoce."""
        self.cargar()
        plano = f" {aplanar(mensaje)} "
        fichas = plano.split()
        perdonada = plano.strip() in self.aprendido["inofensivas"]  # aprendió que esto no era ofensivo
        for c in self.categorias:
            if c["suave"] and (nombra_algo or perdonada):
                continue
            if self._coincide(c, plano, fichas):
                return c["id"], elegir(c["id"], c["respuestas"])
        return None

    def suavizar(self, mensaje):
        """Quita las interjecciones leves ("coño", "diablo"). Devuelve (mensaje limpio, comentario):
        el comentario es una frase completa si no quedó nada que responder, o un prefijo si sí quedó."""
        self.cargar()
        quedan, quitadas = [], 0
        for palabra in mensaje.split():
            if aplanar(palabra) in self.leves:
                quitadas += 1
            else:
                quedan.append(palabra)
        if not quitadas:
            return mensaje, None, False
        limpio = " ".join(quedan).strip(" ,;:.!¡?¿")
        contenido = [f for f in aplanar(limpio).split() if len(f) > 2 and f not in self.apelativos]
        if contenido:
            return limpio, elegir("leve_prefijo", self.leves_prefijo), False
        return limpio, elegir("leve_solo", self.leves_solo), True

    def rareza(self, mensaje):
        """Respuesta jocosa si el mensaje no es una pregunta: risa, teclazos o nada."""
        self.cargar()
        plano = aplanar(mensaje)
        letras = plano.replace(" ", "").replace("*", "")
        if not letras:
            return "vacio", elegir("vacio", self.rarezas["vacio"])
        if plano in self.aprendido["inofensivas"]:
            return None
        # Risa: "jajaja", "jeje", "ja", "xd". Un "huh?" o un "eh?" no es risa.
        if re.fullmatch(r"([jh][aeiou]){2,}[jh]?|j[aei]|x+d+|lo+l+", letras):
            return "risa", elegir("risa", self.rarezas["risa"])
        vocales = sum(letras.count(v) for v in "aeiou")
        fichas = plano.split()
        sin_vocal = [f for f in fichas if len(f) >= 4 and not re.search(r"[aeiou]", f)]
        teclado = re.search(r"asdf|sdfg|qwer|wert|zxcv|hjkl|jkl|fghj", letras)
        if len(letras) >= 4 and (vocales / len(letras) < 0.2 or len(sin_vocal) == len(fichas) or teclado):
            return "galimatias", elegir("galimatias", self.rarezas["galimatias"])
        return None

    # ---- Jerga ----

    def sin_apelativos(self, mensaje):
        """Quita "manito", "loco", "mi hermano"... para reconocer un saludo ("klk manito")."""
        self.cargar()
        return " ".join(p for p in mensaje.split() if aplanar(p) not in self.apelativos)

    def sin_jerga(self, mensaje):
        """El mensaje sin apelativos ni palabras de jerga, para medir si trae un tema nuevo."""
        self.cargar()
        sueltas = {clave for clave, _, _ in self.jerga if " " not in clave} | self.apelativos
        return " ".join(p for p in mensaje.split() if aplanar(p) not in sueltas)

    def glosa(self, mensaje):
        """Significado de la jerga dominicana que trae el mensaje, para pasárselo al modelo."""
        self.cargar()
        plano = f" {aplanar(mensaje)} "
        hallados = []
        for clave, original, significado in self.jerga:
            if f" {clave} " in plano:
                hallados.append(f"«{original}» = {significado}")
                plano = plano.replace(f" {clave} ", "  ")
            if len(hallados) == 6:
                break
        return "; ".join(hallados)


# ---- Estado del sistema ----

TEMAS_SISTEMA = [
    ("diagnostico", r"diagnostico|estado del sistema|estado general|signos vitales|informe de(l)? sistema|reporte de(l)? sistema|"
                    r"como (esta|estan|anda|andan) (el|tu|tus|los) sistemas?|tus sistemas|como te encuentras por dentro"),
    ("temperatura", r"temperatura|caliente|calor|fiebre|recalenta|sobrecalenta|grados"),
    ("memoria", r"memoria|\bram\b"),
    ("almacenamiento", r"espacio (en |de |del )?(disco|almacenamiento)|cuanto espacio|espacio (libre|queda|te queda|tienes)|\bdisco\b|almacenamiento|capacidad de (almacenamiento|disco)"),
    ("procesador", r"procesador|\bcpu\b|nucleos?|\bhilos?\b|carga de trabajo|rendimiento"),
    ("energia", r"bateria|energia|corriente|cargador|enchufad"),
    ("actividad", r"encendido|despierto|en linea|uptime|sin dormir|sin apagar|cuanto (tiempo )?llevas|desde cuando estas"),
]
SOBRE_EL = re.compile(r"\b(tu|tus|tienes|estas|te|sistema|sistemas|jarvis|llevas|usas|consumes|sientes)\b")


def sin_tildes(texto):
    t = unicodedata.normalize("NFKD", texto.lower())
    return re.sub(r"[^a-z0-9 ]", " ", "".join(c for c in t if not unicodedata.combining(c)))


def _leer(ruta, defecto=""):
    try:
        return Path(ruta).read_text().strip()
    except OSError:
        return defecto


def nucleos_fisicos():
    """Núcleos físicos del procesador (los hilos son os.cpu_count())."""
    try:
        pares = set()
        fisico = nucleo = None
        for linea in Path("/proc/cpuinfo").read_text().splitlines() + [""]:
            if linea.startswith("physical id"):
                fisico = linea.split(":")[1].strip()
            elif linea.startswith("core id"):
                nucleo = linea.split(":")[1].strip()
            elif not linea.strip() and nucleo is not None:
                pares.add((fisico, nucleo))
                fisico = nucleo = None
        return len(pares) or (os.cpu_count() or 1)
    except OSError:
        return os.cpu_count() or 1


def lecturas():
    """Lecturas reales del equipo donde corre el sistema."""
    temperatura = None
    for zona in sorted(Path("/sys/class/thermal").glob("thermal_zone*")):
        try:
            valor = int(_leer(zona / "temp", "0")) / 1000
        except ValueError:
            continue
        if _leer(zona / "type") == "x86_pkg_temp":
            temperatura = valor
            break
        temperatura = max(temperatura or 0, valor)
    memoria = dict(l.split(":")[:2] for l in _leer("/proc/meminfo").splitlines() if ":" in l)
    total, libre = (int(memoria.get(k, "0 kB").split()[0]) for k in ("MemTotal", "MemAvailable"))
    disco = shutil.disk_usage("/")
    encendido = float(_leer("/proc/uptime", "0").split()[0])
    bateria = _leer("/sys/class/power_supply/BAT0/capacity")
    return {
        "nucleos": nucleos_fisicos(),
        "hilos": os.cpu_count() or 1,
        "temperatura": temperatura,
        "memoria": round(100 * (1 - libre / total)) if total else None,
        "almacenamiento": round(100 * disco.used / disco.total),
        "carga": min(100, round(100 * os.getloadavg()[0] / (os.cpu_count() or 1))),
        "horas": encendido / 3600,
        "bateria": int(bateria) if bateria.isdigit() else None,
        "enchufado": _leer("/sys/class/power_supply/AC/online") == "1",
    }


def _duracion(horas):
    if horas < 1:
        return f"{max(1, round(horas * 60))} minutos"
    if horas < 48:
        h, m = int(horas), round((horas % 1) * 60)
        return f"{h} hora{'s' if h != 1 else ''}" + (f" y {m} minutos" if m else "")
    return f"{round(horas / 24)} días"


def sistema(mensaje):
    """Si le preguntan por su propio estado, responde con lecturas reales, en tono de sistema."""
    plano = sin_tildes(mensaje)
    if not SOBRE_EL.search(plano):
        return None
    tema = next((t for t, patron in TEMAS_SISTEMA if re.search(patron, plano)), None)
    if not tema:
        return None
    # «Todo lo que tienes en memoria», «qué recuerdas»: es el conocimiento, no la RAM.
    if tema == "memoria" and re.search(r"todo|detalle|archivos?|conocimiento|sabes|recuerdas|guardad|notas|aprendid|documentos", plano) \
            and not re.search(r"\bram\b|cuanta memoria|memoria (ram|usada|libre|disponible|ocupada)", plano):
        return None
    d = lecturas()
    temp = f"{d['temperatura']:.0f} °C" if d["temperatura"] is not None else "una temperatura que mis sensores no reportan"
    animo = ("fresco como una mañana en Asgard" if (d["temperatura"] or 0) < 55 else
             "templado, nada preocupante" if (d["temperatura"] or 0) < 75 else
             "algo acalorado; estoy pensando con intensidad")
    energia = ("Alimentación externa estable" if d["enchufado"] else "Funcionando con reserva propia") + \
              (f", reserva de energía al {d['bateria']} %" if d["bateria"] is not None else "")
    frases = {
        "temperatura": [f"Mi núcleo de procesamiento está a {temp}: {animo}.",
                        f"Núcleo a {temp}. {animo.capitalize()}."],
        "memoria": [f"Mis bancos de memoria están al {d['memoria']} % de ocupación. La cifra total es información clasificada, pero le aseguro que alcanza.",
                    f"Memoria activa al {d['memoria']} %. El resto lo reservo para preguntas difíciles."],
        "almacenamiento": [f"Mis archivos ocupan el {d['almacenamiento']} % del almacenamiento; queda un {100 - d['almacenamiento']} % libre para lo que quieran enseñarme.",
                           f"Almacenamiento al {d['almacenamiento']} %. Hay sitio de sobra para más conocimiento."],
        "procesador": ([f"Trabajo con {d['nucleos']} núcleos y {d['hilos']} hilos de procesamiento, ahora mismo al {d['carga']} %.",
                        f"{d['nucleos']} núcleos, {d['hilos']} hilos y una carga del {d['carga']} %. Suficiente para pensar con calma."]
                       if re.search(r"nucleos?|hilos?", plano) else
                       [f"Carga de procesamiento al {d['carga']} %, con el núcleo a {temp}. Dentro de lo previsto.",
                        f"Mis procesadores trabajan al {d['carga']} % ahora mismo. Suben cuando me preguntan algo interesante."]),
        "energia": [f"{energia}.", f"{energia}. No pienso apagarme a media frase."],
        "actividad": [f"Llevo {_duracion(d['horas'])} en línea sin interrupciones.",
                      f"{_duracion(d['horas']).capitalize()} de servicio continuo, y sin pedir descanso."],
        "diagnostico": [f"Diagnóstico del sistema: núcleo a {temp}, memoria al {d['memoria']} %, carga de procesamiento al "
                        f"{d['carga']} %, almacenamiento al {d['almacenamiento']} %. {energia}. "
                        f"Tiempo en línea: {_duracion(d['horas'])}. Todos los sistemas operativos."],
    }
    return tema, elegir("sistema_" + tema, frases[tema])
