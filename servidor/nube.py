"""La nube gratis como apoyo del modelo local.

Cuando está encendida y hay internet, el paso de redactar la respuesta lo hace un modelo más grande en la nube
(cuotas gratuitas, sin tarjeta). Todo lo demás —recetas, filtros, búsqueda en las notas, límites de longitud,
avisos de cifras— sigue corriendo en esta máquina. Si la nube falla, se acaba la cuota o no hay internet, responde
el modelo local como siempre: la persona no nota más que un segundo de espera.

Proveedores (todos hablan el mismo protocolo, el de OpenAI, con respuesta en streaming), por orden de preferencia:
  1. Groq · GPT-OSS 120B     - el mejor de los gratis de Groq (~1000 peticiones al día)
  2. Groq · Qwen 3.8 27B     - mismo proveedor y clave, otra cuota
  3. Groq · GPT-OSS 20B      - ídem, más pequeño
  4. Google · Gemini Flash-Lite - ~1000 al día. En su plan gratis Google puede usar lo que se le envía para mejorar sus
                              productos: por eso va el último y solo se usa si se le puso clave a propósito.
Los proveedores gratuitos retiran modelos con el tiempo (los Llama de Groq ya no están): si uno da 404, el Manager
muestra el mensaje del proveedor y se cambia el nombre aquí.

Las claves viven en ~/.config/mjarvis/nube.json (permisos 600), fuera de la carpeta del proyecto: no se copian al
desplegar ni salen en ningún registro. Lo que sale hacia la nube: la pregunta, las notas que se usan para responder
y la conversación reciente, con correos, teléfonos y enlaces tachados; y nunca salen las preguntas con datos personales
(ver `privado`).
"""
import http.client
import json
import os
import re
import threading
import time
import urllib.parse
from pathlib import Path

ARCHIVO = Path(os.environ.get("MJARVIS_NUBE") or Path.home() / ".config" / "mjarvis" / "nube.json")
USO = ARCHIVO.with_name("nube-uso.json")

PROVEEDORES = [
    # «extra» va tal cual en la petición; «holgura» son palabras de más para los modelos que razonan antes de responder.
    {"id": "groq-120b", "nombre": "Groq · GPT-OSS 120B", "clave": "groq", "modelo": "openai/gpt-oss-120b",
     "url": "https://api.groq.com/openai/v1/chat/completions", "limite_dia": 1000, "extra": {"reasoning_effort": "low"}, "holgura": 200},
    {"id": "groq-qwen", "nombre": "Groq · Qwen 3.8 27B", "clave": "groq", "modelo": "qwen/qwen3.8-27b",
     "url": "https://api.groq.com/openai/v1/chat/completions", "limite_dia": 1000, "extra": {}, "holgura": 0},
    {"id": "groq-20b", "nombre": "Groq · GPT-OSS 20B", "clave": "groq", "modelo": "openai/gpt-oss-20b",
     "url": "https://api.groq.com/openai/v1/chat/completions", "limite_dia": 1000, "extra": {"reasoning_effort": "low"}, "holgura": 200},
    {"id": "gemini", "nombre": "Google · Gemini Flash-Lite", "clave": "gemini", "modelo": "gemini-2.5-flash-lite",
     "url": "https://generativelanguage.googleapis.com/v1beta/openai/chat/completions", "limite_dia": 1000, "extra": {}, "holgura": 0},
]
CLAVES = {"groq": "Groq (console.groq.com)", "gemini": "Google AI Studio (aistudio.google.com)"}
CONEXION_S, LECTURA_S = 4, 20   # segundos para conectar y para esperar cada trozo
MAX_CLAVE = 200


class SinNube(Exception):
    """Ningún proveedor pudo responder (antes de escribir nada): que conteste el modelo local."""


_candado = threading.Lock()
_pausa = {}      # id -> hasta cuándo no se le pide nada
_error = {}      # id -> último problema, para mostrarlo
_ultimo_ok = {}  # id -> hora del último acierto
_cache = {"mtime": None, "datos": {}}


# ---------- Configuración ----------

def _leer():
    try:
        mtime = ARCHIVO.stat().st_mtime
    except OSError:
        return {}
    if _cache["mtime"] != mtime:
        try:
            _cache["datos"] = json.loads(ARCHIVO.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _cache["datos"] = {}
        _cache["mtime"] = mtime
    return _cache["datos"]


def _guardar(datos):
    ARCHIVO.parent.mkdir(parents=True, exist_ok=True)
    temporal = ARCHIVO.with_suffix(".tmp")
    descriptor = os.open(temporal, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    os.replace(temporal, ARCHIVO)
    _cache["mtime"] = None


def activa():
    return bool(_leer().get("activo", True))


def poner_activa(valor):
    datos = dict(_leer())
    datos["activo"] = bool(valor)
    _guardar(datos)


def poner_clave(nombre, valor):
    """Guarda la clave de un proveedor ('groq' o 'gemini'). Vacía la borra. Devuelve un mensaje de error o None."""
    if nombre not in CLAVES:
        return "Proveedor desconocido."
    valor = (valor or "").strip()
    if valor and (len(valor) < 20 or len(valor) > MAX_CLAVE or not re.fullmatch(r"[A-Za-z0-9_\-.]+", valor)):
        return "Esa clave no parece válida: es una sola palabra larga, sin espacios."
    datos = dict(_leer())
    claves = dict(datos.get("claves", {}))
    if valor:
        claves[nombre] = valor
    else:
        claves.pop(nombre, None)
    datos["claves"] = claves
    _guardar(datos)
    for p in PROVEEDORES:
        if p["clave"] == nombre:
            _pausa.pop(p["id"], None)
            _error.pop(p["id"], None)
    return None


def _clave(proveedor):
    return _leer().get("claves", {}).get(proveedor["clave"], "")


# ---------- Uso diario (para no pasarse de la cuota y mostrarla) ----------

def _usos():
    hoy = time.strftime("%Y-%m-%d")
    try:
        datos = json.loads(USO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        datos = {}
    return datos if datos.get("dia") == hoy else {"dia": hoy}


def _contar(id_):
    with _candado:
        datos = _usos()
        datos[id_] = datos.get(id_, 0) + 1
        try:
            USO.parent.mkdir(parents=True, exist_ok=True)
            USO.write_text(json.dumps(datos), encoding="utf-8")
        except OSError:
            pass


# ---------- Privacidad ----------

PRIVADO = re.compile(
    r"\bme llamo\b|\bmi nombre\b|\bmi apellido\b|\bvivo en\b|\bmi (casa|direcci[oó]n|tel[eé]fono|celular|correo|email|"
    r"escuela|colegio|cédula|cedula|contrase[ñn]a|clave)\b|\bmis (padres|hijos|vecinos)\b|\bcontrase[ñn]a\b", re.I)
CORREO = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")
ENLACE = re.compile(r"https?://\S+|www\.\S+")
TELEFONO = re.compile(r"\+?\d(?:[\s().-]?\d){8,}")


def privado(usuario):
    """True si la pregunta trae datos de la persona: esas se responden siempre en esta máquina."""
    dicho = re.findall(r"^Pregunta: (.*)$", usuario, re.M)
    return bool(PRIVADO.search(dicho[-1] if dicho else usuario))


def tachar(texto):
    texto = CORREO.sub("[correo]", texto)
    texto = ENLACE.sub("[enlace]", texto)
    return TELEFONO.sub("[número]", texto)


def _anonimizar(mensaje):
    """Solo se tachan las preguntas de la gente; las notas (Datos:) llevan cifras legítimas y no se tocan."""
    if mensaje["role"] != "user":
        return mensaje
    lineas = [("Pregunta: " + tachar(l[10:])) if l.startswith("Pregunta: ") else l for l in mensaje["content"].split("\n")]
    return {"role": "user", "content": "\n".join(lineas)}


# ---------- Disponibilidad ----------

def _listos():
    ahora = time.time()
    usos = _usos()
    return [p for p in PROVEEDORES if _clave(p) and _pausa.get(p["id"], 0) <= ahora and usos.get(p["id"], 0) < p["limite_dia"]]


def disponible(usuario="", hay_internet=lambda: True):
    """¿Esta pregunta puede intentarse en la nube?"""
    return activa() and not privado(usuario) and bool(_listos()) and bool(hay_internet())


def _pausar(id_, segundos, motivo):
    _pausa[id_] = time.time() + segundos
    _error[id_] = f"{time.strftime('%H:%M')} · {motivo}"


# ---------- Una petición ----------

def _abrir(proveedor, cuerpo):
    destino = urllib.parse.urlsplit(proveedor["url"])
    clase = http.client.HTTPSConnection if destino.scheme == "https" else http.client.HTTPConnection
    conexion = clase(destino.hostname, destino.port, timeout=CONEXION_S)
    conexion.request("POST", destino.path, json.dumps(cuerpo).encode(), {
        "Content-Type": "application/json", "Authorization": "Bearer " + _clave(proveedor),
        "User-Agent": "M-Jarvis/1.0", "Accept": "text/event-stream"})
    respuesta = conexion.getresponse()
    if conexion.sock:
        conexion.sock.settimeout(LECTURA_S)
    return conexion, respuesta


def _fallo_http(proveedor, respuesta):
    """Traduce un error del proveedor en una pausa razonable."""
    id_ = proveedor["id"]
    try:
        detalle = respuesta.read(600).decode("utf-8", "replace")
    except OSError:
        detalle = ""
    if respuesta.status == 429:
        diario = re.search(r"per day|daily|\bRPD\b|\bTPD\b", detalle, re.I)
        espera = 3600 if diario else int(float(respuesta.getheader("Retry-After") or 60))
        _pausar(id_, min(max(espera, 20), 3600), "límite de uso alcanzado" + (" (del día)" if diario else ""))
    elif respuesta.status in (401, 403):
        _pausar(id_, 3600, "la clave no fue aceptada")
    elif respuesta.status in (400, 404):
        _pausar(id_, 3600, f"el proveedor rechazó la petición ({respuesta.status})")
    else:
        _pausar(id_, 45, f"el proveedor respondió {respuesta.status}")
    mensaje = re.search(r'"message"\s*:\s*"([^"]{5,140})', detalle)
    if mensaje and respuesta.status in (400, 404):
        _error[id_] += f": {mensaje.group(1)}"


def generar(sistema, mensajes, usuario, largo, temperatura, parar, en_curso, al_empezar=None):
    """Trozos de texto de la respuesta, probando cada proveedor listo. Lanza SinNube si ninguno llegó a escribir."""
    cuerpo_mensajes = [{"role": "system", "content": sistema}] + [_anonimizar(m) for m in mensajes] + \
                      [_anonimizar({"role": "user", "content": usuario})]
    for proveedor in _listos():
        if parar.is_set():
            return
        id_ = proveedor["id"]
        conexion, empezo = None, False
        try:
            conexion, respuesta = _abrir(proveedor, {**proveedor["extra"], "model": proveedor["modelo"], "messages": cuerpo_mensajes,
                                                     "stream": True, "temperature": temperatura, "max_tokens": largo + proveedor["holgura"]})
            en_curso["conexion"] = conexion  # para que «Detener» corte también esta espera
            if respuesta.status != 200:
                _fallo_http(proveedor, respuesta)
                continue
            _contar(id_)
            for linea in respuesta:
                if parar.is_set():
                    return
                linea = linea.decode("utf-8", "replace").strip()
                if not linea.startswith("data:"):
                    continue
                dato = linea[5:].strip()
                if dato == "[DONE]":
                    break
                try:
                    opcion = json.loads(dato)["choices"][0]
                except (ValueError, KeyError, IndexError):
                    continue
                trozo = (opcion.get("delta") or {}).get("content") or ""
                if trozo:
                    if not empezo:
                        empezo = True
                        _ultimo_ok[id_] = time.time()
                        _error.pop(id_, None)
                        if al_empezar:
                            al_empezar(id_)
                    yield trozo
                if opcion.get("finish_reason") == "length":
                    yield "…"
                    return
            if empezo:
                return
            _pausar(id_, 45, "respondió vacío")
        except (OSError, http.client.HTTPException, TimeoutError) as error:
            if parar.is_set():
                return
            if empezo:  # ya se escribió algo: se deja ahí, no se mezcla con otro modelo
                return
            _pausar(id_, 60, f"sin conexión ({type(error).__name__})")
        finally:
            en_curso["conexion"] = None
            if conexion:
                conexion.close()
    raise SinNube()


# ---------- Para el Manager ----------

def probar(id_):
    """Prueba un proveedor con una pregunta mínima. Devuelve {ok, mensaje, ms}."""
    proveedor = next((p for p in PROVEEDORES if p["id"] == id_), None)
    if not proveedor:
        return {"ok": False, "mensaje": "Proveedor desconocido."}
    if not _clave(proveedor):
        return {"ok": False, "mensaje": "Falta la clave."}
    inicio = time.time()
    conexion = None
    try:
        conexion, respuesta = _abrir(proveedor, {**proveedor["extra"], "model": proveedor["modelo"], "stream": False, "max_tokens": 8 + proveedor["holgura"],
                                                 "messages": [{"role": "user", "content": "Responde solo: listo"}]})
        if respuesta.status != 200:
            _fallo_http(proveedor, respuesta)
            return {"ok": False, "mensaje": _error.get(id_, f"Respondió {respuesta.status}")}
        _pausa.pop(id_, None)
        _error.pop(id_, None)
        _ultimo_ok[id_] = time.time()
        return {"ok": True, "mensaje": "Funciona.", "ms": int((time.time() - inicio) * 1000)}
    except (OSError, http.client.HTTPException) as error:
        return {"ok": False, "mensaje": f"No se pudo conectar ({type(error).__name__})."}
    finally:
        if conexion:
            conexion.close()


def estado():
    ahora = time.time()
    usos = _usos()
    claves = _leer().get("claves", {})
    return {
        "activo": activa(),
        "claves": {k: {"nombre": n, "puesta": k in claves, "final": claves[k][-4:] if k in claves else ""} for k, n in CLAVES.items()},
        "proveedores": [{
            "id": p["id"], "nombre": p["nombre"], "clave": p["clave"], "con_clave": bool(_clave(p)),
            "usos_hoy": usos.get(p["id"], 0), "limite_dia": p["limite_dia"],
            "pausa_s": max(0, int(_pausa.get(p["id"], 0) - ahora)), "error": _error.get(p["id"], ""),
            "ultimo_ok": int(ahora - _ultimo_ok[p["id"]]) if p["id"] in _ultimo_ok else None,
        } for p in PROVEEDORES],
    }
