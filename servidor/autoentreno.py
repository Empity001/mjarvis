"""Auto-entrenamiento de M-Jarvis: se analiza, practica y propone mejoras, bajo reglas.

Qué hace (y qué NO hace):
  - NO cambia el modelo ni sus pesos: un modelo de 4B en CPU no puede reentrenarse sin estropearse, y el
    dueño no quiere depender de nada externo. Mejora lo que lo rodea: filtros, frases, rutas, notas.
  - ANALIZA la bitácora real con la rúbrica (comportamiento/criterios.json): puntaje de cada respuesta,
    qué reglas se rompen más, qué preguntas quedan sin respuesta, qué se contesta lento.
  - PRUEBA que nada se rompa: corre los ~300 escenarios (pruebas_rutas.py) en segundos.
  - PRACTICA con el modelo real una muestra de escenarios (extensión, tono, exactitud) y los califica.
  - PROPONE cambios (palabras para el filtro, variantes de frases en su voz). Nada se aplica solo:
    el dueño aprueba cada propuesta en el panel, y al aplicarla se repiten las pruebas; si empeoran,
    se deshace sola.

El estado vive en autoentreno.json y las propuestas pendientes en comportamiento/propuestas.json.
"""
import json
import random
import re
import shutil
import subprocess
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

import criterio
import criterios

AQUI = Path(__file__).resolve().parent
RAIZ = AQUI.parent
ESTADO = RAIZ / "autoentreno.json"
PROPUESTAS = RAIZ / "comportamiento" / "propuestas.json"
RESPALDOS = RAIZ / "comportamiento" / "_respaldos"
ESCENARIOS = RAIZ / "comportamiento" / "escenarios.json"
REACCIONES = RAIZ / "comportamiento" / "reacciones.json"
PERSONALIDAD = RAIZ / "comportamiento" / "personalidad.json"

S = None            # el módulo servidor (se pasa en iniciar())
CANDADO = threading.Lock()
EJEC = {"corriendo": False, "modo": "", "paso": "", "hecho": 0, "total": 0, "cancelar": False, "inicio": 0.0}
HISTORIAL_MAX = 40

# Palabras de las que conviene que el filtro se entere si aparecen en la bitácora sin haber sido filtradas.
SOSPECHOSAS = {
    "sexual": "zorra zorro perra guarra cachonda cachondo semen coito pija pito pitos pechos tetona culona sexo anal oral desnudar desnudarte "
              "bragas calzones follar follame coger chupar chupame lamer pajero masturbacion masturbar eyacular erecto erecta".split(),
    "insulto": "idiota imbecil estupido estupida mierda carajo joder gilipollas pelotudo boludo cabron cabrona culero culera hdp "
               "gonorrea malparido malparida basura asqueroso asquerosa inutil subnormal capullo capulla huevon huevona "
               "stupid idiot moron bitch asshole shit fuck damn dumbass".split(),
    "odio": "nazi negrata sudaca terrorista moro maricon marica".split(),
}
DESCRIPCION = {
    "saludo": "cuando alguien lo saluda", "estado": "cuando le preguntan cómo está", "gracias": "cuando le dan las gracias",
    "despedida": "cuando alguien se despide", "extrañeza": "cuando no entiende el mensaje de la persona",
    "haciendo": "cuando le preguntan qué está haciendo", "creador": "cuando le preguntan quién lo creó",
    "identidad": "cuando le preguntan quién es", "capacidad": "cuando le preguntan qué sabe hacer",
}


def iniciar(servidor):
    global S
    S = servidor
    if not ESTADO.exists():
        _escribir(ESTADO, {"automatico": True, "historial": []})
    threading.Thread(target=_vigilante, daemon=True).start()


# ---- Archivos ----

def _leer(ruta, defecto):
    try:
        return json.loads(Path(ruta).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defecto


def _escribir(ruta, datos):
    Path(ruta).write_text(json.dumps(datos, ensure_ascii=False, indent=1), encoding="utf-8")


def _respaldar(*archivos):
    carpeta = RESPALDOS / time.strftime("%Y%m%d-%H%M%S")
    carpeta.mkdir(parents=True, exist_ok=True)
    for a in archivos:
        if Path(a).exists():
            shutil.copy2(a, carpeta / Path(a).name)
    return carpeta


def _restaurar(carpeta):
    for f in Path(carpeta).glob("*.json"):
        shutil.copy2(f, RAIZ / "comportamiento" / f.name)


# ---- Análisis de la bitácora ----

def analizar(ultimas=400):
    if not S.BITACORA.exists():
        return {"n": 0}
    lineas = S.BITACORA.read_text(encoding="utf-8").splitlines()[-ultimas:]
    entradas = [e for e in (_json(l) for l in lineas) if e and not str(e.get("cliente", "")).startswith("entrenamiento")]
    evals = criterios.evaluar_bitacora(entradas, crit=S.CRITERIO)
    if not evals:
        return {"n": 0}
    pesos = criterios.datos().get("pesos", {})
    por, ejemplos = Counter(), defaultdict(list)
    for e, ev in evals:
        for f in ev["fallos"]:
            por[f["id"]] += 1
            if len(ejemplos[f["id"]]) < 3:
                ejemplos[f["id"]].append({"pregunta": e["pregunta"][:80], "respuesta": e["respuesta"][:120], "detalle": f["detalle"]})
    medio = sum(ev["puntaje"] for _, ev in evals) / len(evals)
    desde = getattr(S, "INICIO_SERVICIO", "")
    recientes = [(e, ev) for e, ev in evals if e.get("hora", "") >= desde]
    reciente = {"n": len(recientes), "criticos": sum(1 for _, ev in recientes if ev["critico"]),
                "puntaje_medio": round(sum(ev["puntaje"] for _, ev in recientes) / len(recientes), 1) if recientes else None}
    sin_nota = Counter()
    for e, _ in evals:
        if e.get("fuente") == "general" and e.get("tipo") in ("dato", "identidad", "amplia", "lista", "sí o no"):
            sin_nota[S.normalizar(e["pregunta"]).strip(" ?¿!¡.")] += 1
    lentas = sorted(((e["total_s"], e["pregunta"][:60]) for e, _ in evals
                     if e.get("fuente") in ("documentos", "general") and (e.get("total_s") or 0) > 30), reverse=True)[:5]
    return {
        "n": len(evals), "puntaje_medio": round(medio, 1), "reciente": reciente,
        "criticos": sum(1 for _, ev in evals if ev["critico"]),
        "por_criterio": [{"id": k, "conteo": v, "peso": pesos.get(k, 10), "ejemplos": ejemplos[k]} for k, v in por.most_common()],
        "sin_nota": [{"pregunta": p, "veces": v} for p, v in sin_nota.most_common(8)],
        "lentas": [{"segundos": s, "pregunta": p} for s, p in lentas],
        "entradas": [(e, ev) for e, ev in evals],
    }


def _json(linea):
    try:
        return json.loads(linea)
    except ValueError:
        return None


# ---- Pruebas de rutas (rápidas, sin gastar el modelo) ----

def correr_pruebas():
    try:
        salida = subprocess.run([sys.executable, str(AQUI / "pruebas_rutas.py"), "--json"], capture_output=True,
                                text=True, timeout=240, cwd=str(AQUI))
        datos = json.loads(salida.stdout.strip().splitlines()[-1])
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return {"total": 0, "fallaron": 0, "error": "no se pudieron correr las pruebas", "fallos": []}
    fallos = [{"id": r["id"], "cat": r["cat"], "entrada": r["entrada"][-1][:70], "texto": r["texto"][:90],
               "motivos": r["fallos"]} for r in datos["resultados"] if r["fallos"]]
    return {"total": datos["total"], "fallaron": datos["fallaron"], "segundos": datos["segundos"], "fallos": fallos[:12]}


# ---- Práctica con el modelo real ----

def _correr_real(esc):
    """Una conversación de práctica con el modelo de verdad. Devuelve el resultado calificado."""
    cliente = f"entrenamiento-{esc['id']}"
    texto, inicio = "", time.time()
    try:
        for i, mensaje in enumerate(esc["entrada"]):
            piezas = []
            S.responder(mensaje, lambda o, p=piezas: p.append(o.get("t", "")) if o.get("tipo") == "texto" else None,
                        nueva=(i == 0), cliente=cliente)
            texto = "".join(piezas).strip()
    finally:
        S.MEMORIAS.pop(cliente, None)  # la práctica no desaloja las conversaciones de la gente
    ultimo = _json(S.BITACORA.read_text(encoding="utf-8").splitlines()[-1]) or {}
    ev = criterios.evaluar(ultimo, crit=S.CRITERIO) if ultimo else {"puntaje": 0, "fallos": []}
    fallos = list(ev["fallos"])
    for patron in esc.get("contiene", []):
        if not re.search(patron, texto, re.I):
            fallos.append({"id": "esperado", "peso": 20, "detalle": f"debía contener /{patron}/"})
    for patron in esc.get("no", []):
        if re.search(patron, texto, re.I):
            fallos.append({"id": "prohibido", "peso": 20, "detalle": f"no debía contener /{patron}/"})
    if esc.get("ruta") and ultimo.get("fuente") != esc["ruta"]:
        fallos.append({"id": "ruta", "peso": 10, "detalle": f"salió por {ultimo.get('fuente')}, esperado {esc['ruta']}"})
    puntaje = max(0, 100 - sum(f["peso"] for f in fallos))
    return {"id": esc["id"], "cat": esc["cat"], "pregunta": esc["entrada"][-1], "respuesta": texto, "puntaje": puntaje,
            "palabras": criterios.palabras(texto), "tipo": ultimo.get("tipo"), "segundos": round(time.time() - inicio, 1),
            "fallos": [f"{f['id']}: {f['detalle']}" for f in fallos]}


def practicar(cuantas, previos=None):
    datos = _leer(ESCENARIOS, {"escenarios": []})["escenarios"]
    candidatos = [e for e in datos if e.get("modelo")]
    malos = {r["cat"] for r in (previos or [])}
    random.shuffle(candidatos)
    candidatos.sort(key=lambda e: 0 if e["cat"] in malos else 1)  # primero las categorías que fallaron la vez anterior
    elegidos = candidatos[:cuantas]
    EJEC.update(total=len(elegidos), hecho=0)
    resultados = []
    for i, esc in enumerate(elegidos):
        if EJEC["cancelar"]:
            break
        EJEC.update(paso=f"Practicando {i + 1}/{len(elegidos)}: «{esc['entrada'][-1][:50]}»", hecho=i)
        try:
            resultados.append(_correr_real(esc))
        except Exception as error:  # una práctica rota no detiene las demás
            resultados.append({"id": esc["id"], "cat": esc["cat"], "pregunta": esc["entrada"][-1], "respuesta": "",
                               "puntaje": 0, "palabras": 0, "fallos": [f"error: {error}"]})
    EJEC["hecho"] = len(resultados)
    return resultados


def resumen_practica(resultados):
    if not resultados:
        return None
    rango = criterios.datos().get("longitud", {})
    dentro = cortas = largas = 0
    for r in resultados:
        lim = rango.get(r.get("tipo") or "")
        if not lim:
            continue
        if r["palabras"] < lim[0]:
            cortas += 1
        elif r["palabras"] > lim[1] * 1.15:
            largas += 1
        else:
            dentro += 1
    por = Counter(f.split(":")[0] for r in resultados for f in r["fallos"])
    return {"n": len(resultados), "puntaje_medio": round(sum(r["puntaje"] for r in resultados) / len(resultados), 1),
            "extension": {"dentro": dentro, "cortas": cortas, "largas": largas},
            "fallos_por_criterio": dict(por.most_common()), "peores": sorted(resultados, key=lambda r: r["puntaje"])[:5],
            "mejores": sorted(resultados, key=lambda r: -r["puntaje"])[:2]}


# ---- Propuestas ----

def _propuestas():
    return _leer(PROPUESTAS, [])


def _guardar_propuestas(lista):
    _escribir(PROPUESTAS, lista)


def _nueva(tipo, valor, **datos):
    lista = _propuestas()
    if any(p["tipo"] == tipo and p["valor"] == valor and p["estado"] in ("pendiente", "aplicada") for p in lista):
        return None
    p = {"id": f"{int(time.time() * 1000)}{random.randint(10, 99)}", "tipo": tipo, "valor": valor, "estado": "pendiente",
         "fecha": time.strftime("%Y-%m-%d %H:%M"), **datos}
    lista.append(p)
    _guardar_propuestas(lista[-200:])
    return p


def proponer_filtro(entradas):
    """Palabras que pasaron al modelo sin que el filtro las conociera."""
    nuevas = 0
    for e, _ in entradas:
        if e.get("fuente") in ("filtro", "aprendizaje", "trato"):
            continue
        plano = criterio.aplanar(e["pregunta"])
        for categoria, palabras in SOSPECHOSAS.items():
            for p in palabras:
                if f" {p} " in f" {plano} " and not S.CRITERIO.juzgar(p):
                    if _nueva("filtro_palabra", p, categoria=categoria,
                              motivo=f"apareció en «{e['pregunta'][:70]}» y no la detuvo el filtro"):
                        nuevas += 1
    return nuevas


def _limpiar_variante(linea):
    linea = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", linea).strip().strip("\"“”«»")
    return linea


def _valida_variante(frase, existentes):
    n = criterios.palabras(frase)
    if not 6 <= n <= 28 or frase in existentes or "{" in frase:
        return False
    if not frase.endswith((".", "!", "?")) or re.search(r"\d|laptop|computadora|port[aá]til|aqu[ií] tienes|claro,? aqu", frase, re.I):
        return False
    if criterios.TRATAMIENTO.search(frase) or criterios.REGAÑO.search(frase) or criterios.MULETILLA.search(frase):
        return False
    return bool(re.search(r"[a-záéíóúñ]", frase, re.I))


def proponer_variantes(cuantas_categorias=2, por_categoria=4):
    """El propio modelo escribe variantes de sus frases fijas, en su voz; pasan un filtro y esperan aprobación."""
    candidatas = [(c, d) for c, d in DESCRIPCION.items() if c in S.RESPUESTAS_TRATO and len(S.RESPUESTAS_TRATO[c]) <= 7]
    candidatas += [(clave, f"charla: {S.ETIQUETAS_CHARLA.get(clave, clave).lower()}") for clave, _, _, frases, _ in S.CHARLA
                   if len(frases) <= 2 and clave in S.ETIQUETAS_CHARLA]
    random.shuffle(candidatas)
    nuevas = 0
    for categoria, descripcion in candidatas[:cuantas_categorias]:
        if EJEC["cancelar"]:
            break
        EJEC["paso"] = f"Escribiendo variantes: {descripcion}"
        existentes = list(S.RESPUESTAS_TRATO.get(categoria, [])) or next((f for c, _, _, f, _ in S.CHARLA if c == categoria), [])
        ejemplos = "\n".join(f"- {f}" for f in random.sample(existentes, min(2, len(existentes))))
        pedido = ("Eres M-Jarvis, una inteligencia artificial de un taller escolar, con humor seco y modales de mayordomo "
                  "británico. Hablas de usted y nunca llamas a nadie «señor», «señora» ni «estimado». "
                  f"Escribe {por_categoria} respuestas breves y DISTINTAS entre sí (una por línea, sin numerar, de 8 a 22 palabras, "
                  "sencillas y con una pizca de ironía, nada pomposo) "
                  f"para esta situación: {descripcion}.\nEjemplos del estilo:\n{ejemplos}\n"
                  "No menciones computadoras, laptop ni números. Solo las respuestas, nada más.")
        try:
            texto = S.pedir_con_turno(pedido)
        except Exception:
            continue
        for linea in texto.splitlines():
            frase = _limpiar_variante(linea)
            if _valida_variante(frase, existentes) and _nueva("variante", frase, categoria=categoria,
                                                              motivo=f"escrita por el modelo para: {descripcion}"):
                nuevas += 1
    return nuevas


def listar_propuestas():
    return [p for p in _propuestas() if p["estado"] == "pendiente"]


def descartar(id_):
    lista = _propuestas()
    for p in lista:
        if p["id"] == id_ and p["estado"] == "pendiente":
            p["estado"] = "descartada"
    _guardar_propuestas(lista)
    return True


def aprobar(id_):
    """Aplica una propuesta y comprueba que las pruebas no empeoren; si empeoran, la deshace."""
    with CANDADO:
        lista = _propuestas()
        p = next((x for x in lista if x["id"] == id_ and x["estado"] == "pendiente"), None)
        if not p:
            return {"ok": False, "error": "esa propuesta ya no está pendiente"}
        antes = correr_pruebas()
        copia = _respaldar(REACCIONES, PERSONALIDAD)
        try:
            if p["tipo"] == "filtro_palabra":
                datos = _leer(REACCIONES, {})
                objetivo = [c for c in datos["categorias"] if c["id"] == p["categoria"] and c.get("palabras")]
                objetivo[0]["palabras"].append(criterio.aplanar(p["valor"]))
                _escribir(REACCIONES, datos)
                S.CRITERIO.cargar()
            elif p["tipo"] == "variante":
                datos = _leer(PERSONALIDAD, {})
                clave = "extra" if p["categoria"] in S.RESPUESTAS_TRATO else "extra_charla"
                datos.setdefault(clave, {}).setdefault(p["categoria"], []).append(p["valor"])
                _escribir(PERSONALIDAD, datos)
                if clave == "extra":
                    S.RESPUESTAS_TRATO[p["categoria"]].append(p["valor"])
                else:
                    for c, _, _, frases, _ in S.CHARLA:
                        if c == p["categoria"]:
                            frases.append(p["valor"])
        except Exception as error:
            _restaurar(copia)
            return {"ok": False, "error": f"no se pudo aplicar: {error}"}
        despues = correr_pruebas()
        if despues["fallaron"] > antes["fallaron"]:
            _restaurar(copia)
            S.CRITERIO.marcas = None
            S.CRITERIO.cargar()
            p["estado"] = "revertida"
            p["motivo_reversion"] = f"empeoraba las pruebas ({antes['fallaron']} → {despues['fallaron']} fallos)"
            _guardar_propuestas(lista)
            return {"ok": False, "error": p["motivo_reversion"]}
        p["estado"] = "aplicada"
        p["aplicada"] = time.strftime("%Y-%m-%d %H:%M")
        _guardar_propuestas(lista)
        return {"ok": True}


# ---- Ejecución completa ----

def _veredicto(nuevo, previo):
    if not previo:
        return "primera medición"
    claves = [("practica", "puntaje_medio"), ("bitacora", "puntaje_medio")]
    for a, b in claves:
        if nuevo.get(a) and previo.get(a) and nuevo[a].get(b) is not None and previo[a].get(b) is not None:
            d = nuevo[a][b] - previo[a][b]
            return "mejora" if d > 1 else "empeora" if d < -1 else "igual"
    return "igual"


def ejecutar(modo):
    """modo 'rapido': analiza + pruebas + propone palabras. modo 'completo': además practica con el modelo y
    escribe variantes. Se llama en un hilo."""
    if EJEC["corriendo"]:
        return
    EJEC.update(corriendo=True, modo=modo, cancelar=False, inicio=time.time(), paso="Analizando la bitácora…", hecho=0, total=0)
    try:
        estado = _leer(ESTADO, {"automatico": True, "historial": []})
        previo = estado["historial"][-1] if estado["historial"] else None
        bit = analizar()
        informe = {"fecha": time.strftime("%Y-%m-%d %H:%M"), "modo": modo, "bitacora": {k: v for k, v in bit.items() if k != "entradas"}}
        nuevas = 0
        if bit.get("n"):
            EJEC["paso"] = "Buscando palabras que el filtro no conoce…"
            nuevas += proponer_filtro(bit["entradas"])
        EJEC["paso"] = "Corriendo las pruebas de comportamiento…"
        informe["pruebas"] = correr_pruebas()
        if modo == "completo" and not EJEC["cancelar"]:
            previos = (previo or {}).get("practica", {}) and (previo["practica"].get("peores") or [])
            resultados = practicar(12, previos)
            informe["practica"] = resumen_practica(resultados)
            if not EJEC["cancelar"]:
                nuevas += proponer_variantes()
        informe["propuestas_nuevas"] = nuevas
        informe["propuestas_pendientes"] = len(listar_propuestas())
        meta = criterios.datos().get("meta", {})
        base = (informe.get("practica") or informe["bitacora"]).get("puntaje_medio")
        rec = informe["bitacora"].get("reciente") or {}
        criticos_ok = not rec.get("n", 0) >= 10 or 100 * rec["criticos"] / rec["n"] <= meta.get("tasa_critica_maxima_pct", 1)
        informe["cumple_meta"] = bool(base is not None and base >= meta.get("puntaje_minimo_bueno", 80)
                                      and informe["pruebas"].get("fallaron", 0) == 0 and criticos_ok)
        informe["veredicto"] = _veredicto(informe, previo)
        informe["duracion_s"] = round(time.time() - EJEC["inicio"], 1)
        estado["historial"] = (estado.get("historial", []) + [informe])[-HISTORIAL_MAX:]
        _escribir(ESTADO, estado)
    finally:
        EJEC.update(corriendo=False, paso="", cancelar=False)


def lanzar(modo):
    if EJEC["corriendo"]:
        return False
    threading.Thread(target=ejecutar, args=(modo,), daemon=True).start()
    return True


def cancelar():
    EJEC["cancelar"] = True


def poner_automatico(valor):
    e = _leer(ESTADO, {"automatico": True, "historial": []})
    e["automatico"] = bool(valor)
    _escribir(ESTADO, e)


def _vigilante():
    """Si está activado, cada 6 horas con la casa en calma (sin preguntas en 10 min) hace un análisis rápido."""
    ultima = time.time()
    while True:
        time.sleep(900)
        try:
            e = _leer(ESTADO, {"automatico": True, "historial": []})
            reposo = time.time() - max((m["hora"] for m in S.MEMORIAS.values()), default=0) > 600
            if e.get("automatico") and reposo and not EJEC["corriendo"] and time.time() - ultima > 6 * 3600:
                ultima = time.time()
                ejecutar("rapido")
        except Exception:
            pass


# ---- Para el panel ----

def estado_panel():
    e = _leer(ESTADO, {"automatico": True, "historial": []})
    hist = e.get("historial", [])
    crit = criterios.datos()
    return {
        "automatico": e.get("automatico", True), "ejecutando": dict(EJEC, transcurrido=round(time.time() - EJEC["inicio"], 1) if EJEC["corriendo"] else 0),
        "ultimo": hist[-1] if hist else None,
        "tendencia": [{"fecha": h["fecha"], "calidad": (h.get("practica") or h.get("bitacora") or {}).get("puntaje_medio"),
                       "pruebas_ok": (h.get("pruebas", {}).get("total", 0) - h.get("pruebas", {}).get("fallaron", 0)),
                       "pruebas": h.get("pruebas", {}).get("total", 0)} for h in hist[-12:]],
        "propuestas": listar_propuestas(),
        "reglas": {"principios": crit.get("_principios", []), "pesos": crit.get("pesos", {}),
                   "longitud": crit.get("longitud", {}), "meta": crit.get("meta", {}), "criticos": crit.get("criticos", [])},
        "escenarios": len(_leer(ESCENARIOS, {"escenarios": []})["escenarios"]),
    }
