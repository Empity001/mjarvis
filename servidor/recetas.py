"""Habilidades (recetas) de M-Jarvis.

Una receta es una destreza concreta que se resuelve SIN el modelo: reconoce un tipo de mensaje y
contesta con un procedimiento fijo (a veces con lecturas reales del sistema o de las notas). Cuanto
más sabe hacer por receta, menos inventa el modelo y más rápido responde.

Cada receta se registra con @receta(nombre, titulo, etapa, descripcion, nodo):
  - etapa «primero»: antes que nada, incluso antes del filtro de groserías (duelo, y corregirse cuando alguien, ya
                     molesto, dice «¿de qué mierda hablas?»: ahí manda la corrección, no el regaño).
  - etapa «antes»  : tras el filtro de groserías, antes de lo demás (solo lo que no puede esperar).
  - etapa «pre»    : tras filtros y enseñanzas, antes del estado del sistema y la búsqueda de notas.
  - etapa «notas»  : con el rastro de la charla ya calculado, antes de buscar en las notas.
  - etapa «modelo» : con la búsqueda hecha, justo antes de llamar al modelo (si no hay nada que decir con datos).
  - etapa «datos»  : con notas halladas, justo antes de llamar al modelo: para comprobar que lo preguntado consta en ellas.
La función recibe un contexto (ver Contexto) y devuelve None (no aplica) o
(marca, frase, nodos|None) o un dict {"marca", "frase", "nodos", "efecto"}.

Cuántas veces se usó cada una, y si está activa, queda en comportamiento/recetas.json: se ve y se
enciende o apaga desde el panel (sección «Habilidades»).
"""
import json
import re
import time
from pathlib import Path
from types import SimpleNamespace

import criterio

ARCHIVO = Path(__file__).resolve().parent.parent / "comportamiento" / "recetas.json"
REGISTRO = {}
ETAPAS = ("primero", "antes", "pre", "notas", "modelo", "datos")


def receta(nombre, titulo, etapa, descripcion, nodo=None):
    assert etapa in ETAPAS

    def marca(funcion):
        REGISTRO[nombre] = {"nombre": nombre, "titulo": titulo, "etapa": etapa, "descripcion": descripcion,
                            "nodo": nodo or titulo, "funcion": funcion}
        return funcion
    return marca


# ---- Estado: activa / usos ----

def _leer():
    try:
        return json.loads(ARCHIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


ESTADO = _leer()


def _guardar():
    try:
        ARCHIVO.write_text(json.dumps(ESTADO, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


def activa(nombre):
    return ESTADO.get(nombre, {}).get("activa", True)


def poner_activa(nombre, valor):
    if nombre in REGISTRO:
        ESTADO.setdefault(nombre, {})["activa"] = bool(valor)
        _guardar()


def _anotar_uso(nombre):
    e = ESTADO.setdefault(nombre, {})
    e["usos"] = e.get("usos", 0) + 1
    e["ultima"] = time.strftime("%Y-%m-%d %H:%M")
    _guardar()


def listado():
    """Para el panel: todas las habilidades con su uso."""
    return [{"nombre": r["nombre"], "titulo": r["titulo"], "etapa": r["etapa"], "descripcion": r["descripcion"],
             "activa": activa(r["nombre"]), "usos": ESTADO.get(r["nombre"], {}).get("usos", 0),
             "ultima": ESTADO.get(r["nombre"], {}).get("ultima", "")} for r in REGISTRO.values()]


def etiquetas():
    """{marca: nombre del nodo} para dibujarlas en la red de trato."""
    return {r["nombre"]: r["nodo"] for r in REGISTRO.values()}


def intentar(etapa, ctx):
    """Prueba, en orden, las recetas activas de esa etapa. Devuelve un dict o None."""
    for r in list(REGISTRO.values()):
        if r["etapa"] != etapa or not activa(r["nombre"]):
            continue
        try:
            res = r["funcion"](ctx)
        except Exception:  # una receta rota nunca debe tumbar la conversación
            continue
        if not res:
            continue
        if isinstance(res, dict) and res.get("continuar"):
            res["receta"] = r["nombre"]
            _anotar_uso(r["nombre"])
            return res
        if not isinstance(res, dict):
            res = {"marca": res[0], "frase": res[1], "nodos": res[2] if len(res) > 2 else None}
        res.setdefault("nodos", None)
        res["receta"] = r["nombre"]
        _anotar_uso(r["nombre"])
        return res
    return None


def contexto(pregunta, original, memoria, indice, normalizar, **extra):
    plano = " ".join(re.sub(r"[^a-z0-9 ]", " ", normalizar(pregunta)).split())
    return SimpleNamespace(pregunta=pregunta, original=original, plano=plano, memoria=memoria, indice=indice,
                           normalizar=normalizar, **extra)


def _ultima_hace(memoria, clave, segundos):
    return time.time() - memoria.get(clave, 0) < segundos


# ============================================================================================
# Etapa «antes»
# ============================================================================================

@receta("texto_largo", "Textos larguísimos sin pregunta", "antes",
        "Un mensaje enorme y sin pregunta no se le entrega al modelo: se le pide una pregunta concreta.",
        "Texto larguísimo")
def texto_largo(c):
    if len(c.original) < 280 or "?" in c.original:
        return None
    if c.indice.nombrada(c.original, sin_preguntas=True):
        return None
    return ("texto_largo", criterio.elegir("texto_largo", [
        "Eso es bastante texto para una sola entrega, y no veo una pregunta dentro. Si quiere saber algo del universo "
        "Marvel, dígamelo en una frase y encantado.",
        "Lo he leído entero, o al menos lo he sobrevolado. No hay pregunta ahí. Pruebe con algo más breve y más Marvel.",
        "Mi capacidad de lectura es amplia; mi paciencia con los testamentos, limitada. ¿Cuál es la pregunta?"]), None)


# ============================================================================================
# Etapa «pre»
# ============================================================================================

CORRIGE_TEMA = re.compile(
    r"no te (pregunte|hable|dije|pedi|habia pedido)( nada)? (de|por|sobre|eso|esto)\b|"
    r"que (mierda |cojones |carajo |carajos |diablos |demonios |rayos |coño )?(tiene|tienen) que ver|eso no tiene (nada )?que ver|"
    r"de que (mierda |carajo |carajos |cojones |diablos |demonios |rayos |coño )?(me )?(hablas|estas hablando|me hablas)|"
    r"literalmente no (te )?(hable|dije|pregunte)|"
    r"\bno (era|es|fue) eso\b|no me refiero a eso|no te pedi (eso|informacion)|eso no te lo (pregunte|pedi)|"
    r"por que me (dices|cuentas|hablas de) (eso|esto)|pero (eso )?no (te )?(pregunte|hable)|no (hablo|hablaba) de eso")


@receta("correccion_tema", "Corregirse cuando se fue por otro lado", "primero",
        "Si le dicen «no te pregunté de eso» o «¿qué tiene que ver?», borra el último intercambio y el tema "
        "de su memoria, se disculpa y empieza de nuevo. No defiende un error.", "Aceptar que se equivocó")
def correccion_tema(c):
    m = c.memoria
    tras_personal = m.get("personal_hasta", 0) > time.time()
    if not (m["preguntas"] or tras_personal) or not CORRIGE_TEMA.search(c.plano):
        return None
    ultima = m["preguntas"][-1] if m["preguntas"] else ""
    if m["preguntas"]:
        if len(m["mensajes"]) >= 2:
            del m["mensajes"][-2:]
        del m["preguntas"][-1:]
        del m["respuestas"][-1:]
    m.update(sujeto=None, obra=None, notas=[], usadas=set(), presentes=set(), charla=None)
    m.pop("personal_hasta", None)
    return {"marca": "correccion_tema", "efecto": ("olvidar_ruta", ultima), "frase": criterio.elegir("corr_tema", [
        "Tiene razón, me fui por otro lado. Borro eso de mi memoria y empezamos de nuevo: ¿qué quería saber?",
        "Me equivoqué de tema, y lo admito sin excusas. Lo olvido; dígame qué quería preguntar.",
        "Disculpe la confusión: esa respuesta no venía al caso. Borrón y cuenta nueva."])}


PARIENTE = (r"(?:mi|mis|nuestr[oa]s?)\s+(?:mama|madre|mami|papa|padre|papi|abuel[oa]|abuelit[oa]|herman[oa]|hij[oa]|ti[oa]|prim[oa]|"
            r"amig[oa]|mejor amig[oa]|novi[oa]|espos[oa]|marid[oa]|mujer|perr[oa]|gat[oa]|mascota|ama|amá|bisabuel[oa]|suegr[oa]|cunad[oa]|"
            r"maestr[oa]|profe(?:sor|sora)?|vecin[oa])")
DUELO = re.compile(
    rf"\b{PARIENTE}\b.{{0,40}}\b(murio|fallecio|se murio|se me murio|se nos murio|se fue|acaba de morir|esta muriendo|esta grave|"
    r"esta en el hospital|esta en cuidados intensivos|fue asesinad[oa]|se mato|se suicido|tuvo un accidente|esta desaparecid[oa])\b|"
    rf"\b(murio|fallecio|se murio|se mato|se suicido)\s+{PARIENTE}\b|\bperdi a {PARIENTE}\b|\bse me murio\b|\bse nos murio\b|"
    r"\bacaba de morir\b|\bvoy a un funeral\b|\bfui a un funeral\b|\bmurio alguien\b")
SUICIDIO = re.compile(r"suicid|se mato|se quito la vida")


PESAME = [
    "Lamento mucho su pérdida. No tengo palabras que lo arreglen, pero le acompaño en el sentimiento. Si necesita hablarlo, busque a alguien de confianza; "
    "yo, aquí, solo sé de Marvel.",
    "Cuánto lo siento. Perder a alguien querido duele de verdad. Lo mejor es que lo comparta con personas cercanas; yo me quedo con lo mío, que es Marvel.",
    "Le acompaño en el sentimiento. Esto es de las cosas que se atraviesan mejor con gente querida cerca. Cuando quiera preguntar algo de Marvel, aquí estoy."]
CORTES_PERSONAL = [
    "Lamento oírlo. Es algo que merece hablarse con alguien de confianza; yo, aquí, solo sé de Marvel. Cuando quiera preguntar algo del universo Marvel, con gusto.",
    "Gracias por contármelo. Para eso mejor una persona cercana que una máquina con notas de películas. Aquí sigo para lo de Marvel, cuando quiera.",
    "Siento que esté pasando por eso. No es un tema que me corresponda, pero le deseo que mejore pronto. Para lo de Marvel, estoy a su disposición."]


@receta("duelo", "Dar el pésame sin guardar el tema", "primero",
        "Si alguien cuenta que murió o está grave alguien querido, da el pésame con calidez, sin datos ni chistes, y "
        "sin guardar nada de ello: no sigue el hilo ni lo mezcla con la conversación de Marvel. Si fue un suicidio, "
        "remite a una persona de confianza o al 911.", "Dar el pésame")
def duelo(c):
    if "?" in c.original and len(c.plano.split()) > 12:
        return None
    if not DUELO.search(c.plano):
        return None
    c.memoria["personal_hasta"] = time.time() + 120  # solo para entender un «¿de qué hablas?» inmediato
    if SUICIDIO.search(c.plano):
        return {"marca": "duelo", "nodos": [], "sin_memoria": True,
                "frase": "Lamento muchísimo lo ocurrido. Esto es serio y no es algo que deba cargar solo: hable ahora con una persona adulta "
                         "de confianza, y si usted o alguien cercano corre peligro, llame al 911."}
    return {"marca": "duelo", "nodos": [], "sin_memoria": True, "frase": criterio.elegir("duelo", PESAME)}


TRISTE = re.compile(
    r"\b(me siento|estoy|ando|me encuentro|me puse|me pone|tengo el animo|tengo un dia)\b.*\b(triste|tristeza|mal|deprimid\w+|solo|sola|"
    r"agobiad\w+|estresad\w+|ansios\w+|angustiad\w+|desanimad\w+|llorando|fatal|horrible|"
    r"vacio|vacia|destrozad\w+|hecho polvo|hecha polvo|sin ganas|sin animo|abatid\w+|desesperad\w+)\b|"
    r"\b(animo por el suelo|animo por los suelos|todo me sale mal|nada me sale bien|no tengo ganas de nada|"
    r"no valgo nada|me siento un fracaso|estoy harto de todo|estoy harta de todo|mal de animo)\b|"
    r"\b(no me siento bien|me siento (muy )?mal|tuve un mal dia|mal dia|nadie me (quiere|entiende|escucha|habla)|"
    r"me duele el corazon|quiero llorar|ganas de llorar|me siento sol[oa]|estoy sol[oa])\b|"
    r"\b(mis padres se pelean|mis padres se separan|mis padres se divorcian|me hacen bullying|me molestan en el colegio|reprobe|"
    r"perdi mi trabajo|me corrieron|me botaron|me dejo mi novi[oa]|me dejaron|terminamos|termine con mi novi[oa]|me peleé con mi mejor amig[oa]|"
    r"me pelee con mi mejor amig[oa]|me robaron|me pegaron|me siento culpable|me siento un inutil|tengo problemas en casa)\b")
@receta("animo_bajo", "Responder con cortesía a lo personal", "pre",
        "Si alguien cuenta que está triste, mal o solo, contesta una vez con un mensaje cortés (sin datos, sin "
        "trivia, sin chistes) y sigue adelante: no guarda ni continúa el tema, para que no se cuele en la "
        "conversación de Marvel.", "Responder con cortesía a lo personal")
def animo_bajo(c):
    if "?" in c.original and len(c.plano.split()) > 6:
        return None  # pregunta de verdad con una queja de paso: se responde la pregunta
    if not TRISTE.search(c.plano):
        return None
    c.memoria["personal_hasta"] = time.time() + 120
    return {"marca": "animo_bajo", "nodos": [], "sin_memoria": True, "frase": criterio.elegir("personal", CORTES_PERSONAL)}


QUEJA = re.compile(r"no me ayud(aste|as|o)|no me sirvio|no sirvio de nada|no me haces caso|me ignoras|no me escuchas|"
                   r"no me entiendes|no me entendiste|no te importo|no te importa|no me estas ayudando|"
                   r"no entendiste nada|no ayudas en nada|cortala|no hiciste nada")


@receta("queja", "Aceptar una queja sin ponerse a la defensiva", "pre",
        "Ante «no me ayudaste» o «no me escuchas» reconoce el fallo con humor seco y pide que se lo "
        "repitan. Nada de justificaciones ni sermones.", "Aceptar una queja")
def queja(c):
    if "?" in c.original and len(c.plano.split()) > 8:
        return None
    if not QUEJA.search(c.plano):
        return None
    return ("queja", criterio.elegir("queja", [
        "Tiene razón: no estuve a la altura. Dígame qué necesitaba y lo intento de nuevo, sin discursos.",
        "Fallé, y me molesta más a mí que a usted. ¿Me da otra oportunidad? Prometo ser útil y breve.",
        "Si no le ayudé, fue mi error y no el suyo. Cuénteme otra vez, con calma."]), None)


SILENCIO = re.compile(r"^(detente|deten|para|alto|stop|ya para|para ya|quedate callad[oa]|callate un rato|no digas nada|no hables|silencio|ya basta|basta|no conectes nada|"
                      r"no conectes nada quedate callad[oa]|dejalo asi|dejalo|olvidalo)( por favor)?$|quedate callad[oa]|no conectes nada")


@receta("silencio", "Guardar silencio cuando se lo piden", "pre",
        "«Quédate callado», «déjalo así»: acepta con una frase corta y apaga lo que estaba encendido en el mapa.",
        "Guardar silencio")
def silencio(c):
    if not SILENCIO.search(c.plano):
        return None
    return {"marca": "silencio", "frase": criterio.elegir("silencio", [
        "Entendido. Silencio.", "Como guste. No diré una palabra más hasta que me pregunten.",
        "Hecho. Me quedo quieto."]), "nodos": [], "mapa": "apagar"}


APRENDISTE = re.compile(r"que (has |acabas de |ya )?aprend(iste|ido)|que te (han |hemos )?ensen(ado|aron)|"
                        r"que cosas (nuevas )?aprendiste|que sabes de nuevo|que hay de nuevo en tu cerebro")


@receta("que_aprendiste", "Contar lo que ha aprendido de verdad", "pre",
        "Responde «¿qué aprendiste?» leyendo lo que realmente quedó guardado (respuestas enseñadas y datos "
        "pendientes de aprobar), no inventando.", "Contar lo aprendido")
def que_aprendiste(c):
    if not APRENDISTE.search(c.plano):
        return None
    datos = criterio.leer_aprendido()
    respuestas = list(datos.get("respuestas", {}))
    pendientes = c.pendientes() if getattr(c, "pendientes", None) else 0
    partes = []
    if respuestas:
        lista = ", ".join(f"«{r}»" for r in respuestas[:5])
        partes.append(f"Me enseñaron {len(respuestas)} respuesta{'s' if len(respuestas) != 1 else ''} de trato: {lista}")
    if pendientes:
        partes.append(f"y hay {pendientes} dato{'s' if pendientes != 1 else ''} esperando que quien me administra "
                      "los apruebe")
    if not partes:
        estado = "encendido" if datos.get("activo") else "apagado"
        return ("que_aprendiste", f"Nada nuevo, de momento. Mi modo de aprendizaje está {estado}, "
                                  "y lo que no me enseñan no lo invento.", None)
    return ("que_aprendiste", " ".join(partes).strip() + ".", None)


# ============================================================================================
# Etapa «notas» (el rastro de la charla ya está calculado)
# ============================================================================================

PERTENENCIA = re.compile(r"\b(es|son|era|eran|esta|estan|pertenece|pertenecen|forma(n)? parte|sale|salen|aparece|aparecen)\b.*"
                         r"\b(de |del |en |a )?(el |la )?(universo )?(marvel|mcu|los vengadores)\b|"
                         r"^y (es|son) de marvel$|de marvel (es|son)\b")
INTERROGA = re.compile(r"^(donde|cuando|como|por que|porque|cuanto|cuantos|cuantas|cuanta|quien|quienes|que|cual|cuales)\b")
QUITAR_MARVEL = re.compile(r"\b(de|del|en|a)?\s*(el )?(universo )?(cinematografico )?(de )?(marvel|mcu)\b")


@receta("pertenencia_marvel", "Decir si algo es de Marvel o de otro universo", "notas",
        "«¿Es de Marvel?»: lo resuelve mirando de dónde viene la nota (Marvel u otro universo), sin pasar "
        "por el modelo. Usa el rastro si no nombran a nadie.", "Si es de Marvel o no")
def pertenencia_marvel(c):
    if not PERTENENCIA.search(c.plano) or INTERROGA.match(c.plano) or len(c.plano.split()) > 9:
        return None
    sin = QUITAR_MARVEL.sub(" ", c.plano)
    nota = c.indice.nombrada(sin, sin_preguntas=True)
    if not nota and c.memoria.get("sujeto") and len(sin.split()) <= 4:
        nota = c.indice.nombrada(c.memoria["sujeto"], sin_preguntas=True)
    if not nota or nota["plano"] in ("marvel", "universo marvel", "mcu"):
        return None
    nombre = c.nombre(nota["id"])
    if nota.get("ajena"):
        origen = re.search(r"Viene de (.+?)\. No pertenece", nota["resumen"])
        return {"marca": "pertenencia_marvel", "nodos": [nota["id"]],
                "frase": f"No. {nombre} viene de {origen.group(1) if origen else 'otro universo'}; no pertenece al universo Marvel."}
    if nota.get("nube") == "marvel":
        return {"marca": "pertenencia_marvel", "nodos": [nota["id"]],
                "frase": f"Sí. {nombre} forma parte del universo Marvel."}
    return None


@receta("que_es_marvel", "Explicar qué es el universo Marvel", "notas",
        "«¿Qué es Marvel?» siempre sale de la nota general escrita a mano, nunca de una nota cualquiera "
        "que comparta la palabra.", "Qué es Marvel")
def que_es_marvel(c):
    if not re.match(r"^(que|quien) (es|son|significa) (el |la )?(universo )?(cinematografico )?(de )?(marvel|mcu)$", c.plano):
        return None
    for n in c.indice.notas.values():
        plano_n = n["plano"].lstrip("¿ ")
        if plano_n.startswith("que es el universo marvel") or plano_n.startswith("que es el universo cinematografico"):
            r = n["resumen"].strip()
            return {"marca": "que_es_marvel", "frase": r[:1].upper() + r[1:], "nodos": [n["id"]]}
    return None


PLURAL = re.compile(r"\b(como|cuando|donde|por que) se (conocieron|casaron|enamoraron|separaron|reencontraron|hicieron amigos|unieron|"
                    r"pelearon|reconciliaron)\b|\bson (hermanos|amigos|pareja|enemigos|familia)\b")


@receta("aclarar_plural", "Pedir el segundo nombre antes de adivinar", "notas",
        "Si preguntan por dos («¿cómo se conocieron?») y solo hay un sujeto en la charla, pregunta con quién "
        "en vez de buscar notas al azar.", "Pedir aclaración")
def aclarar_plural(c):
    if not PLURAL.search(c.plano) or not c.memoria.get("sujeto"):
        return None
    if c.indice.nombrada(c.original, sin_preguntas=True):
        return None
    sujeto = c.nombre(c.memoria["sujeto"])
    return ("aclarar_plural", criterio.elegir("aclarar", [
        f"¿Quiénes exactamente? Veníamos hablando de {sujeto}; dígame con quién para no confundirlos.",
        f"Para no inventar nada: ¿{sujeto} y quién más?"]), None)


# ============================================================================================
# Etapa «modelo» (ya se buscó en las notas y no hay nada con qué responder)
# ============================================================================================

@receta("sin_pregunta", "No inventar cuando no hay pregunta", "modelo",
        "Si el mensaje no es una pregunta, no nombra nada que conozca y no sigue ningún tema, no se lo "
        "entrega al modelo (que acaba regañando o inventando): dice con ingenio que no lo entendió.",
        "Mensaje sin pregunta")
def sin_pregunta(c):
    if c.halladas or c.seguimiento or c.repaso or c.tipo != "general":
        return None
    if "?" in c.original or len(c.plano.split()) > 9 or len(c.plano) < 3:
        return None
    interrogativas = {"quien", "quienes", "que", "cual", "cuales", "como", "cuando", "donde", "cuanto", "cuantos",
                      "cuantas", "cuanta", "por", "porque"}
    if set(c.plano.split()) & interrogativas:
        return None
    return ("sin_pregunta", criterio.elegir("sin_pregunta", [
        "No estoy seguro de qué hacer con eso. Si es una pregunta, formúlela y la atiendo con gusto.",
        "Eso no me llegó como pregunta. Dígamelo de otra forma y lo intento.",
        "Me perdí. Con una pregunta concreta me va mejor que con indirectas.",
        "Mi archivo de respuestas a eso está vacío, y no pienso rellenarlo con inventos. ¿Qué quería saber?"]), None)


RELACIONES = {
    "hermano": ("ningún", "hermano"), "hermana": ("ninguna", "hermana"), "hermanos": ("ningún", "hermano"),
    "padre": ("ningún", "padre"), "madre": ("ninguna", "madre"), "hijo": ("ningún", "hijo"), "hija": ("ninguna", "hija"),
    "hijos": ("ningún", "hijo"), "esposa": ("ninguna", "esposa"), "esposo": ("ningún", "esposo"), "marido": ("ningún", "marido"),
    "novia": ("ninguna", "novia"), "novio": ("ningún", "novio"), "abuelo": ("ningún", "abuelo"), "abuela": ("ninguna", "abuela"),
    "tio": ("ningún", "tío"), "tia": ("ninguna", "tía"), "primo": ("ningún", "primo"), "prima": ("ninguna", "prima"),
    "nieto": ("ningún", "nieto"), "nieta": ("ninguna", "nieta"), "mascota": ("ninguna", "mascota"),
}
# Palabras completas (sin tildes) con las que unas notas dicen ese parentesco; «Herman Schultz» no es un hermano.
FAMILIA = {"hermano": r"herman[oa]s?", "hermana": r"herman[oa]s?", "hermanos": r"herman[oa]s?",
           "padre": r"padres?|papa", "madre": r"madres?|mama", "hijo": r"hij[oa]s?", "hija": r"hij[oa]s?", "hijos": r"hij[oa]s?",
           "esposa": r"espos[oa]s?|marid[oa]", "esposo": r"espos[oa]s?|marid[oa]", "marido": r"espos[oa]s?|marid[oa]",
           "novia": r"novi[oa]s?|pareja", "novio": r"novi[oa]s?|pareja", "abuelo": r"abuel[oa]s?", "abuela": r"abuel[oa]s?",
           "tio": r"ti[oa]s?", "tia": r"ti[oa]s?", "primo": r"prim[oa]s?", "prima": r"prim[oa]s?",
           "nieto": r"niet[oa]s?", "nieta": r"niet[oa]s?", "mascota": r"mascotas?|perr[oa]s?|gatos?"}


@receta("relacion_sin_dato", "No inventar parientes que no constan", "datos",
        "Si preguntan por un familiar («¿quién es su hermano?») y ninguna nota que tiene delante lo menciona, "
        "lo dice con claridad en vez de dejar que el modelo invente a alguien.", "Admitir que un dato no consta")
def relacion_sin_dato(c):
    if c.tipo not in ("dato", "identidad", "general", "sí o no"):
        return None
    palabras_p = c.plano.split()
    rel = next((p for p in palabras_p if p in RELACIONES), None)
    if not rel:
        return None
    familia = re.compile(r"\b(" + FAMILIA[rel] + r")\b")
    cuerpo = " ".join(c.normalizar(n["id"] + " " + n["resumen"]) for n in c.halladas)
    if familia.search(cuerpo):
        return None
    sujeto = c.memoria.get("sujeto")
    nombrada = c.indice.nombrada(c.original, sin_preguntas=True)
    if nombrada:
        sujeto = c.nombre(nombrada["id"])
    if not sujeto:
        return None
    # Quizá la nota que lo dice no estaba entre las primeras: se busca en todas las que hablan del sujeto.
    nombre_s = set(c.palabras(sujeto))
    otras = []
    for n in c.indice.notas.values():
        if n["titulo"] and nombre_s <= n["titulo"] and familia.search(c.normalizar(n["resumen"])):  # la ficha del propio sujeto
            otras.append(n)
            continue
        for frase in re.split(r"(?<=[.!?])\s+", n["resumen"]):  # o una frase donde se junten él y el parentesco
            if familia.search(c.normalizar(frase)) and nombre_s <= set(c.palabras(frase)):
                otras.append(n)
                break
    if otras:
        otras.sort(key=lambda n: len(n["resumen"]))
        return {"continuar": True, "agregar": otras[:2]}  # consta: que el modelo lo lea
    art, palabra = RELACIONES[rel]
    return ("relacion_sin_dato", criterio.elegir("sin_dato", [
        f"En mis notas no consta {art} {palabra} de {sujeto}, y prefiero no inventar nada.",
        f"No tengo registro de {art} {palabra} de {sujeto}. Antes que adivinar, lo admito.",
        f"De {sujeto} no figura {art} {palabra} en mis archivos, y no pienso rellenar el hueco con un invento."]),
        [c.halladas[0]["id"]] if c.halladas else None)


# ============================================================================================
# Utilidades para el servidor
# ============================================================================================

REINTENTA = re.compile(r"^(hazlo|hazla|haslo|dilo|intentalo|contestalo|respondelo|responde|respondeme|contesta|contestame|sigue|"
                       r"continua|otra vez|de nuevo|vuelve a (intentar|responder|contestar)|termina(lo)?|acaba(lo)?)"
                       r"( otra vez| de nuevo| por favor)?$")


REPITE = re.compile(r"^(hazlo|dilo|contestalo|respondelo|intentalo) (otra vez|de nuevo)$|^(otra vez|de nuevo|una vez mas)$")
MAS_FACIL = re.compile(r"^(explicamelo|explicalo|dilo|repitelo|explicame|explica) (otra vez )?(mas |de forma |de manera |con palabras )?"
                       r"(facil|simple|sencillo|sencilla|simples|sencillas|claro)$|^(mas facil|mas simple|mas sencillo)$|"
                       r"^(no entendi|no entiendo|no comprendo)$")


def reintento(plano, memoria):
    """Pedidos que retoman la pregunta anterior:
    - tras cortarle una respuesta: «hazlo otra vez», «responde» → esa pregunta;
    - «otra vez», «de nuevo» → la última pregunta;
    - «no entendí», «explícalo más fácil» → la última pregunta, pidiendo palabras sencillas.
    Devuelve el texto de la pregunta que hay que contestar, o None."""
    if memoria.get("detenida") and REINTENTA.match(plano):
        return memoria.pop("detenida")
    if memoria.get("preguntas"):
        ultima = memoria["preguntas"][-1]
        if REPITE.match(plano):
            return ultima
        if MAS_FACIL.match(plano):
            return ultima + " (explícalo con palabras muy sencillas)"
    return None
