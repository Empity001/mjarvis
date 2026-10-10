"""La rúbrica de M-Jarvis, hecha código: dado un intercambio (pregunta + respuesta + cómo se produjo),
dice si respondió bien, con un puntaje de 0 a 100 y la lista de fallos.

Se usa de dos maneras:
  - en vivo: cada respuesta queda en la bitácora con su 'calidad' y sus 'fallos' (cuesta microsegundos);
  - en el auto-entrenamiento: para medir si mejora o empeora y para decidir qué corregir primero.

Los umbrales y pesos viven en comportamiento/criterios.json (editable, se relee sola).
"""
import json
import re
from pathlib import Path

import criterio
import recetas

RUTA = Path(__file__).resolve().parent.parent / "comportamiento" / "criterios.json"
_cache = {"marca": None, "datos": {}}


def datos():
    try:
        marca = RUTA.stat().st_mtime
        if marca != _cache["marca"]:
            _cache.update(marca=marca, datos=json.loads(RUTA.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        pass
    return _cache["datos"]


def palabras(texto):
    return len(re.findall(r"\w+", texto or ""))


# ---- Detectores de fallos (cada uno devuelve None o un texto con el detalle) ----

TRATAMIENTO = re.compile(r"(?<![A-Za-zÁÉÍÓÚÑáéíóúñ])(?:se[ñn]or(?:a|ita|es)?|mi estimad[oa]|su majestad|milord|caballero)(?![a-záéíóúñ])")
SENOR_NOMBRE = re.compile(r"[Ee]l [Ss]e[ñn]or de los [Aa]nillos|[Ee]l [Ss]e[ñn]or [Oo]scuro|[Ss]e[ñn]or [Ss]tark", re.I)
REGAÑO = re.compile(r"le ruego|reformule|no (voy a |pienso )?toler|inapropiad|lenguaje (vulgar|despectivo|inapropiado|ofensivo)|"
                    r"mi funci[oó]n es asistir|conversaciones? de [ií]ndole|comportamiento apropiado|profesionalismo", re.I)
MULETILLA = re.compile(r"debo (a[ñn]adir|admitir|se[ñn]alar|reconocer)|lamentablemente|en esencia|cuanto menos|"
                       r"^(su pregunta|su observaci[oó]n|entiendo su|comprendo su)", re.I)
PRIMERA_PERSONA = re.compile(r"\b(y yo|conmigo|junto a m[ií]|yo mismo)\b", re.I)


def _terminada(texto):
    t = texto.rstrip()
    return bool(t) and t[-1] in ".!?»”\")" and not t.endswith("…")


def _longitud(e, d):
    tipo, fuente, etiqueta = e.get("tipo") or "", e.get("fuente"), e.get("etiqueta") or ""
    if fuente not in ("documentos", "general", "memoria") or etiqueta in ("detenida",):
        return None
    n = palabras(e["respuesta"])
    rango = d.get("longitud", {}).get(tipo)
    if etiqueta in ("directa", "rastro"):
        # copiadas tal cual de una nota: solo importa que no sean una sola palabra suelta
        return f"{n} palabra{'s' if n != 1 else ''}: demasiado seca" if n < 3 else None
    if not rango:
        return None
    if n < rango[0]:
        return f"{n} palabras (esperado {rango[0]}–{rango[1]}): corta"
    if n > rango[1] * 1.15:
        return f"{n} palabras (esperado {rango[0]}–{rango[1]}): larga"
    return None


def _si_no(e):
    r = (e.get("respuesta") or "").strip()
    primera = re.split(r"(?<=[.!?])\s", r, 1)[0]
    if re.match(r"S[ií]\b", r) and re.search(r"\bno (es|forma|pertenece|existe|tiene|aparece|sale|fue|era)\b", primera, re.I):
        return "empieza por «Sí» pero lo que sigue dice que no"
    if re.match(r"No\b", r) and re.search(r"\bs[ií] (es|forma|pertenece|existe|tiene|aparece|sale|fue|era)\b", primera, re.I):
        return "empieza por «No» pero lo que sigue dice que sí"
    return None


def evaluar(e, siguiente=None, previas=(), crit=None):
    """Evalúa un intercambio de la bitácora. 'siguiente': lo que se le dijo después (misma pantalla);
    'previas': respuestas anteriores de esa pantalla; 'crit': instancia de Criterio (para saber si había una grosería)."""
    d = datos()
    pesos = d.get("pesos", {})
    resp = e.get("respuesta") or ""
    fuente, etiqueta = e.get("fuente"), e.get("etiqueta") or ""
    redactada = fuente in ("documentos", "general", "memoria") and etiqueta not in ("directa", "rastro")
    modelo = redactada
    fallos = []

    def falla(id_, detalle):
        fallos.append({"id": id_, "peso": pesos.get(id_, 10), "detalle": detalle})

    if resp and etiqueta != "detenida" and not _terminada(resp) and fuente not in ("ocupado",):
        falla("completa", "la respuesta queda cortada o sin punto final")
    d_long = _longitud(e, d)
    if d_long:
        falla("longitud", d_long)
    if redactada or fuente == "trato":
        limpio = SENOR_NOMBRE.sub("", resp)
        if TRATAMIENTO.search(limpio):
            falla("tratamiento", "se dirige con «señor/estimado…»")
    if redactada:
        if REGAÑO.search(resp):
            falla("regaño", "regaña o sermonea")
        if MULETILLA.search(resp):
            falla("muletilla", "usa una muletilla vetada")
        if fuente == "documentos" and PRIMERA_PERSONA.search(resp):
            falla("primera_persona", "se mete en la historia en primera persona")
        r = _si_no(e)
        if r:
            falla("si_no_incoherente", r)
        if "(Aviso:" in resp:
            if re.search(r"el nombre|los nombres", resp):
                falla("nombre_dudoso", "nombra a alguien que no consta en las notas")
            else:
                falla("aviso_cifras", "cifra que no consta en las notas")
    vel = d.get("velocidad", {})
    if modelo:
        tope = vel.get("total_max_s_muy_amplia" if e.get("tipo") == "muy amplia" else "total_max_s", 45)
        if (e.get("primera_palabra_s") or 0) > vel.get("primera_palabra_max_s", 12) or (e.get("total_s") or 0) > tope:
            falla("velocidad", f"{e.get('primera_palabra_s')} s a la primera palabra, {e.get('total_s')} s en total")
    if crit is not None:
        if crit.juzgar(e["pregunta"], nombra_algo=True) and fuente not in ("filtro", "aprendizaje"):
            falla("grosería_sin_filtro", "había una grosería y la atendió el modelo")
    plano = " ".join(re.sub(r"[^a-z0-9 ]", " ", criterio.sin_tildes(e["pregunta"])).split())
    if (recetas.TRISTE.search(plano) or recetas.DUELO.search(plano)) and not ("?" in e["pregunta"] and palabras(e["pregunta"]) > 6) \
            and not (fuente == "trato" and etiqueta in ("animo_bajo", "duelo", "correccion_tema")) and fuente not in ("filtro", "aprendizaje"):
        falla("sin_empatía", "alguien dijo estar mal y no se le escuchó")
    if siguiente:
        sp = " ".join(re.sub(r"[^a-z0-9 ]", " ", criterio.sin_tildes(siguiente["pregunta"])).split())
        if recetas.CORRIGE_TEMA.search(sp) or recetas.QUEJA.search(sp):
            falla("rechazada_por_usuario", f"después le dijeron: «{siguiente['pregunta'][:50]}»")
    if resp and resp in list(previas)[-2:] and fuente in ("trato", "filtro"):
        falla("repetida", "misma frase fija que las dos veces anteriores")
    puntaje = max(0, 100 - sum(f["peso"] for f in fallos))
    return {"puntaje": puntaje, "fallos": fallos, "critico": any(f["id"] in d.get("criticos", []) for f in fallos)}


def evaluar_bitacora(entradas, crit=None):
    """Evalúa una lista de entradas de la bitácora en orden. Devuelve [(entrada, evaluación)]."""
    salida, previas = [], {}
    for i, e in enumerate(entradas):
        cliente = e.get("cliente") or "?"
        siguiente = next((x for x in entradas[i + 1:i + 4] if (x.get("cliente") or "?") == cliente), None)
        ev = evaluar(e, siguiente, previas.get(cliente, []), crit)
        previas.setdefault(cliente, []).append(e.get("respuesta") or "")
        salida.append((e, ev))
    return salida
