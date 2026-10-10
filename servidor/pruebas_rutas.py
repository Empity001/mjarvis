#!/usr/bin/env python3
"""Banco de pruebas de M-Jarvis: corre los escenarios de comportamiento/escenarios.json por el mismo
camino que una pregunta real, pero con un modelo simulado (así tarda segundos y no gasta el modelo).

Comprueba, para la ÚLTIMA respuesta de cada escenario:
  - por dónde salió (fuente / etiqueta de la bitácora),
  - que contenga o no ciertas expresiones,
  - que no se pase ni se quede corta de palabras,
  - que si el escenario necesita al modelo, llegue hasta él.

Uso:  python3 pruebas_rutas.py              # todo, resumen
      python3 pruebas_rutas.py -v           # detalle de cada fallo
      python3 pruebas_rutas.py --cat tristeza --id animo-03
      python3 pruebas_rutas.py --json       # salida para el auto-entrenamiento
No toca la bitácora, las rutas ni los contadores reales: todo se escribe en una carpeta temporal.
"""
import argparse
import json
import re
import sys
import tempfile
import time
from pathlib import Path

AQUI = Path(__file__).resolve().parent
sys.path.insert(0, str(AQUI))
import criterio  # noqa: E402
import criterios  # noqa: E402
import ingesta  # noqa: E402
import recetas  # noqa: E402
import nube  # noqa: E402
import red  # noqa: E402
import servidor  # noqa: E402
import voz  # noqa: E402

OLLAMA_REAL = servidor.ollama  # la preparación de las pruebas lo reemplaza por un modelo falso

ESCENARIOS = AQUI.parent / "comportamiento" / "escenarios.json"
MARCA_MODELO = "[MODELO] "
INSTANTANEA = {}


def _huella():
    """Lo real que las pruebas jamás deben tocar: lo aprendido y los datos pendientes de aprobar."""
    real = criterio.DATOS / "aprendido.json"
    pendientes = servidor.RAIZ / "conocimiento" / "_por-aprobar"
    return (real.read_bytes() if real.exists() else b"", sorted(p.name for p in pendientes.glob("*")) if pendientes.exists() else [])


def preparar():
    """Aísla todo lo que escribe y simula el modelo."""
    INSTANTANEA["antes"] = _huella()
    tmp = Path(tempfile.mkdtemp(prefix="mjarvis-pruebas-"))
    # Aislamiento total: las pruebas NUNCA tocan lo que la gente enseñó ni sus datos pendientes (en el servidor
    # real el modo de aprendizaje puede estar encendido y los escenarios de «aprende que…» se lo creerían).
    criterio.APRENDIDO = tmp / "aprendido.json"
    servidor.POR_APROBAR = tmp / "por-aprobar"
    servidor.CRITERIO.marcas = None
    servidor.CRITERIO.cargar()
    servidor.escribir_red_de_trato = lambda: None
    servidor.ARCHIVO_EXHIBICION = tmp / "exhibicion.json"
    red.ARCHIVO = tmp / "red.json"
    servidor.BITACORA = tmp / "bitacora.jsonl"
    servidor.ARCHIVO_RUTAS = tmp / "rutas.json"
    servidor.RUTAS.clear()
    recetas.ARCHIVO = tmp / "recetas.json"
    recetas.ESTADO.clear()
    criterio.ULTIMAS.clear()

    def modelo_falso(usuario, largo=None):
        yield MARCA_MODELO
        yield "Respuesta simulada del modelo."
    servidor.ollama = modelo_falso
    time.sleep = lambda segundos: None  # las respuestas fijas "escriben" palabra a palabra: aquí no hace falta esperar
    ingesta.pedir_directo = lambda *a, **k: "NO"
    servidor.INDICE.cargar()
    return tmp


def correr(esc, indice):
    """Ejecuta un escenario; devuelve (últimaEntrada, texto, fallos)."""
    cliente = f"prueba-{esc['id']}"
    ultimo, texto = None, ""
    for i, mensaje in enumerate(esc["entrada"]):
        piezas = []
        servidor.responder(mensaje, lambda o: piezas.append(o.get("t", "")) if o.get("tipo") == "texto" else None,
                           nueva=(i == 0), cliente=cliente)
        texto = "".join(piezas).strip()
    lineas = servidor.BITACORA.read_text(encoding="utf-8").splitlines()
    ultimo = json.loads(lineas[-1])
    return ultimo, texto


def comprobar(esc, ultimo, texto):
    fallos = []
    fuente, etiqueta = ultimo.get("fuente"), ultimo.get("etiqueta") or ""
    ruta = esc.get("ruta")
    if ruta and fuente != ruta:
        fallos.append(f"salió por «{fuente}/{etiqueta}», se esperaba «{ruta}»")
    marca = esc.get("marca")
    if marca and etiqueta != marca and not fallos:
        fallos.append(f"etiqueta «{etiqueta}», se esperaba «{marca}»")
    if esc.get("modelo") and MARCA_MODELO not in texto:
        fallos.append("tenía que llegar al modelo y se resolvió antes")
    for patron in esc.get("notas_no", []):  # notas que NO deben haber llegado al modelo
        if any(re.search(patron, n, re.I) for n in ultimo.get("notas", [])):
            fallos.append(f"llegó una nota prohibida /{patron}/")
    if not esc.get("modelo"):
        for patron in esc.get("contiene", []):
            if not re.search(patron, texto, re.I):
                fallos.append(f"debía contener /{patron}/")
    for patron in esc.get("no", []):
        if re.search(patron, texto, re.I):
            fallos.append(f"no debía contener /{patron}/")
    if not esc.get("modelo"):
        n = len(re.findall(r"\w+", texto))
        if esc.get("max") and n > esc["max"]:
            fallos.append(f"{n} palabras, máximo {esc['max']}")
        if esc.get("min") and n < esc["min"]:
            fallos.append(f"{n} palabras, mínimo {esc['min']}")
    return fallos


def _portal(cliente, host):
    """¿El servidor mandaría al chat a un equipo con esa dirección que pide ese sitio?"""
    m = servidor.Manejador.__new__(servidor.Manejador)
    m.client_address = (cliente, 50000)
    m.headers = {"Host": host}
    m.headers = type("H", (), {"get": lambda self, k, d=None: {"Host": host}.get(k, d)})()
    return m.para_otro_nombre()


def _exhibicion():
    servidor.poner_exhibicion({"silencio": True, "bloqueado": True})
    activo = servidor.EXHIBICION == {"silencio": True, "bloqueado": True} and json.loads(servidor.ARCHIVO_EXHIBICION.read_text())["bloqueado"] is True
    servidor.poner_exhibicion({"silencio": False, "bloqueado": False})
    return activo and servidor.EXHIBICION == {"silencio": False, "bloqueado": False}


def _nube():
    """La nube gratis contra un servidor falso con el protocolo de OpenAI: acierto, límite, clave mala, privacidad y respaldo."""
    import http.server
    import threading
    modo = {"v": "ok"}
    recibido = []

    class Falso(http.server.BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def do_POST(self):
            cuerpo = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            recibido.append(cuerpo)
            if modo["v"] == "limite":
                self.send_response(429); self.send_header("Retry-After", "30"); self.end_headers(); self.wfile.write(b"rate limit"); return
            if modo["v"] == "clave":
                self.send_response(401); self.end_headers(); self.wfile.write(b"bad key"); return
            self.send_response(200); self.send_header("Content-Type", "text/event-stream"); self.end_headers()
            for t in ("Hola, ", "desde la nube."):
                self.wfile.write(("data: " + json.dumps({"choices": [{"delta": {"content": t}}]}) + "\n\n").encode())
            self.wfile.write(b"data: [DONE]\n\n")

    caja = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Falso)
    threading.Thread(target=caja.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{caja.server_address[1]}/v1/chat/completions"
    viejos = (nube.ARCHIVO, nube.USO, nube.PROVEEDORES, dict(nube._pausa), nube._cache.copy())
    tmp = Path(tempfile.mkdtemp())
    nube.ARCHIVO, nube.USO = tmp / "nube.json", tmp / "uso.json"
    nube._cache.update(mtime=None, datos={})
    nube._pausa.clear()
    nube.PROVEEDORES = [dict(p, url=url) for p in viejos[2]]
    parar, curso = threading.Event(), {"conexion": None}

    def correr(usuario="Pregunta: ¿Quién es Thor?", mensajes=()):
        quien = []
        try:
            return "".join(nube.generar("sistema", list(mensajes), usuario, 100, 0.2, parar, curso, quien.append)), quien
        except nube.SinNube:
            return None, quien

    r = []
    r.append(("nube: sin clave no se intenta", not nube.disponible("Pregunta: hola") and correr()[0] is None))
    nube.poner_clave("groq", "gsk_" + "a" * 30)
    r.append(("nube: con clave está disponible y apagada no", nube.disponible("Pregunta: hola") and not (nube.poner_activa(False) or nube.disponible("Pregunta: hola"))))
    nube.poner_activa(True)
    texto, quien = correr()
    r.append(("nube: responde por streaming y dice quién", texto == "Hola, desde la nube." and quien == ["groq-120b"]))
    r.append(("nube: llega el modelo y la temperatura pedidos", recibido[-1]["model"] == "openai/gpt-oss-120b" and recibido[-1]["reasoning_effort"] == "low" and recibido[-1]["max_tokens"] == 300 and recibido[-1]["stream"] is True))
    correr("Pregunta: escríbeme a a@b.com o al 829 555 1234, ve a https://x.org", [{"role": "user", "content": "Pregunta: mi correo es x@y.com"}])
    enviado = json.dumps(recibido[-1], ensure_ascii=False)
    r.append(("nube: correos, teléfonos y enlaces salen tachados", all(x not in enviado for x in ("a@b.com", "x@y.com", "555 1234", "x.org")) and "[correo]" in enviado))
    correr("Datos:\nFue en 1.000.000.000 años.\n\nPregunta: ¿cuánto?")
    r.append(("nube: las notas con cifras largas no se tocan", "1.000.000.000" in json.dumps(recibido[-1])))
    r.append(("nube: lo personal no sale", nube.privado("Pregunta: me llamo Ana y vivo en Santiago") and not nube.disponible("Pregunta: me llamo Ana")
              and not nube.privado("Pregunta: ¿Quién es Thor?")))
    modo["v"] = "limite"
    texto, quien = correr()
    r.append(("nube: límite 429 → pasa al siguiente proveedor y pausa", texto is None and nube._pausa["groq-120b"] > time.time() and "groq-qwen" in nube._pausa and "groq-20b" in nube._pausa))
    nube._pausa.clear()
    modo["v"] = "clave"
    correr()
    r.append(("nube: clave rechazada → se pausa y se explica", "clave" in nube.estado()["proveedores"][0]["error"] and nube._pausa["groq-120b"] > time.time() + 1800))
    nube._pausa.clear()
    modo["v"] = "ok"
    nube.USO.write_text(json.dumps({"dia": time.strftime("%Y-%m-%d"), "groq-120b": 1000, "groq-qwen": 1000, "groq-20b": 1000}))
    texto, quien = correr()
    r.append(("nube: cuota del día agotada → no se le pide más", texto is None and not nube._listos()))
    nube.USO.unlink()
    r.append(("nube: la clave nunca se devuelve entera", "a" * 12 not in json.dumps(nube.estado()) and nube.estado()["claves"]["groq"]["final"] == "a" * 4))
    r.append(("nube: clave mal formada se rechaza", nube.poner_clave("groq", "corta") is not None and nube.poner_clave("otra", "x" * 30) is not None))
    r.append(("nube: archivo de claves con permisos 600", (nube.ARCHIVO.stat().st_mode & 0o777) == 0o600))
    # Con la nube sin poder responder, el servidor cae al modelo local sin que se note
    viejo, viejo_internet = servidor.ollama_local, servidor.hay_internet
    servidor.hay_internet = lambda: True
    servidor.ollama_local = lambda usuario, largo=None: iter(["local ", "ok"])
    nube._pausa.clear()
    modo["v"] = "limite"
    r.append(("nube: sin nube responde el modelo local", "".join(OLLAMA_REAL("Pregunta: hola", 50)) == "local ok" and servidor.MOTOR[0] == "local"))
    servidor.ollama_local, servidor.hay_internet = viejo, viejo_internet
    caja.shutdown()
    nube.ARCHIVO, nube.USO, nube.PROVEEDORES = viejos[0], viejos[1], viejos[2]
    nube._pausa.clear(); nube._pausa.update(viejos[3]); nube._cache.update(viejos[4])
    return r


def _wifi_propia_con_cable():
    """En modo puente la Wi-Fi propia no se apaga sola; en otros modos, sin nadie conectado, sí intenta volver arriba."""
    # Estas pruebas corren en la Latitude: NADA de esto puede llegar a NetworkManager de verdad.
    r = object.__new__(red.Red)
    r.ultimo_intento_arriba, r.hotspot_pedido, r.tarjeta, r.eventos = 0.0, 0.0, None, []
    r.anotar = lambda texto: r.eventos.append(texto)
    llamadas = []
    r.volver_a_wifi = lambda: llamadas.append(1)
    r.estado = lambda fresco=False: {"wifi": {"conectado": False}}
    r.internet = lambda iface: "no"
    r._cambiar = lambda *a, **k: None
    viejos = (red._nm, red.time.sleep)
    red._nm = lambda *a, **k: (0, "")
    red.time.sleep = lambda s: None
    try:
        e = {"hotspot": {"activa": True}, "clientes": []}
        r.modo = "puente"
        r._volver_arriba(e)
        sin_tocar = not llamadas and not r.eventos
        r.modo = "local"
        r._volver_arriba(e)
        return sin_tocar and bool(llamadas)
    finally:
        red._nm, red.time.sleep = viejos


def unidades():
    """Pruebas de las funciones pequeñas (limpieza del texto del modelo, recorte, frases completas)."""
    L = servidor.limpiar
    casos = [
        ("limpiar: «mi señor»", "mi señor" not in L("No, mi señor, no puedo.").lower() and "señor" not in L("No, mi señor, no puedo.")),
        ("limpiar: «El señor Tony Stark»", L("El señor Tony Stark es un genio.") == "Tony Stark es un genio."),
        ("limpiar: respeta El Señor de los Anillos", "Señor de los Anillos" in L("Escribió El Señor de los Anillos.")),
        ("limpiar: «lamentablemente»", "lamentablemente" not in L("Es un hecho, lamentablemente no poseo datos.").lower()),
        ("limpiar: «según los Datos»", L("Según los Datos, una manzana tiene 95 calorías.") == "Una manzana tiene 95 calorías."),
        ("limpiar: «según los datos proporcionados»", L("Hubo seis, según los datos proporcionados.") == "Hubo seis."),
        ("limpiar: «debo añadir»", "debo" not in L("Es un genio, debo añadir, bastante raro.")),
        ("recorte: no corta antes del máximo", servidor.corte_palabras("Una dos tres. Cuatro cinco.", 10) is None),
        ("recorte: corta al final de la frase", servidor.corte_palabras("Una dos tres cuatro. Cinco seis siete ocho.", 4) == len("Una dos tres cuatro.")),
        ("como_frase: hermana", servidor.como_frase({"id": "¿Cómo se llama su hermana?", "resumen": "Nebula."}) == "Su hermana se llama Nebula."),
        ("como_frase: esposa", servidor.como_frase({"id": "¿Quién es la esposa de Tony Stark?", "resumen": "Pepper Potts."}) == "La esposa de Tony Stark es Pepper Potts."),
        ("como_frase: respuesta larga intacta", servidor.como_frase({"id": "¿Quién es X?", "resumen": "Es un titán que cree en equilibrar el universo."}) == "Es un titán que cree en equilibrar el universo."),
        ("voz: «M-Jarvis» se pronuncia", voz.preparar_texto("Soy M-Jarvis.") == "Soy Eme Jarvis."),
        ("voz: los avisos de cifras no se leen", "Aviso" not in voz.preparar_texto("Fue en 2018. (Aviso: la cifra 2018 no consta en mis notas.)")),
        ("voz: emojis, comillas y enlaces fuera", voz.preparar_texto("Hola «amigo» 😀 https://x.y fin") == "Hola amigo fin"),
        ("voz: el texto largo se recorta", len(voz.preparar_texto("a" * 5000)) <= voz.MAX_TEXTO),
        ("portal: un equipo de la Wi-Fi de M-Jarvis pide otro sitio → al chat", _portal("10.42.0.15", "connectivitycheck.gstatic.com") is True),
        ("portal: lo mismo desde el cable que ofrece la interfaz", _portal("10.44.0.9", "captive.apple.com") is True),
        ("portal: pedir la Latitude por su dirección no se desvía", _portal("10.42.0.15", "10.42.0.1:8080") is False),
        ("portal: ni por su nombre .local", _portal("10.42.0.15", "ferr-latitude-5590.local:8080") is False),
        ("portal: un túnel o equipo de fuera nunca se desvía", _portal("100.64.0.7", "ferr.ts.net") is False and _portal("127.0.0.1", "ejemplo.com") is False),
        ("exhibición: silenciar y bloquear se guardan", _exhibicion()),
        ("red: con el cable dando internet la Wi-Fi propia no se apaga sola", _wifi_propia_con_cable()),
        *_nube(),
        ("red: la foto de estado trae lo esperado", all(k in red.RED.estado(fresco=True) for k in ("modo", "wifi", "hotspot", "cable", "clientes", "direcciones", "eventos"))),
        ("aislamiento: lo aprendido y lo pendiente quedan intactos", _huella() == INSTANTANEA.get("antes", _huella())),
        ("rúbrica: señor", any(f["id"] == "tratamiento" for f in criterios.evaluar({"pregunta": "hola", "respuesta": "Buenas, señor.", "fuente": "trato", "etiqueta": "saludo"})["fallos"])),
        ("rúbrica: respuesta limpia", criterios.evaluar({"pregunta": "quien es thor", "respuesta": "Es el príncipe de Asgard, dios del trueno y un héroe del universo Marvel.", "fuente": "documentos", "etiqueta": "directa", "tipo": "identidad"})["puntaje"] == 100),
        ("rúbrica: tristeza sin empatía", any(f["id"] == "sin_empatía" for f in criterios.evaluar({"pregunta": "me siento triste", "respuesta": "Thor es el dios del trueno.", "fuente": "documentos", "etiqueta": "", "tipo": "general"})["fallos"])),
    ]
    return [{"id": f"unidad-{i + 1:02d}", "cat": "unidad", "entrada": [n], "texto": "", "fuente": None, "etiqueta": None, "receta": None,
             "fallos": [] if ok else ["falló"], "nota": ""} for i, (n, ok) in enumerate(casos)]


def streaming():
    """El texto que se muestra tiene que coincidir con el limpio aunque el modelo escriba letra a letra y la limpieza
    quite fragmentos a mitad de camino («, debo admitir,», «Según los Datos,»)."""
    textos = [
        "Ultrón, debo admitir, es un ejemplo lamentable de ambición. Según los Datos, su obsesión es la pureza. Un individuo propenso al exceso.",
        "El señor Tony Stark fue, lamentablemente, un genio. De acuerdo con los datos, construyó la armadura. Carezco de más detalles.",
    ]
    original = servidor.ollama
    resultados = []
    try:
        for i, texto in enumerate(textos):
            def modelo(usuario, largo=None, t=texto):
                yield from t  # carácter a carácter: el caso más difícil
            servidor.ollama = modelo
            piezas = []
            servidor.responder("que opinas de la vida", lambda o: piezas.append(o.get("t", "")) if o.get("tipo") == "texto" else None,
                               nueva=True, cliente=f"stream-{i}")
            mostrado = "".join(piezas).strip()
            registrado = json.loads(servidor.BITACORA.read_text(encoding="utf-8").splitlines()[-1])["respuesta"].strip()
            esperado = servidor.limpiar(texto).strip()
            fallos = []
            if mostrado != registrado:
                fallos.append(f"se mostró {mostrado[:80]!r} y se registró {registrado[:80]!r}")
            if re.search(r"debo admitir|según los datos|de acuerdo con los datos|lamentablemente|señor", mostrado, re.I):
                fallos.append(f"quedó una muletilla: {mostrado[:90]!r}")
            for palabra in ("propenso", "Carezco"):
                if palabra in esperado and palabra not in mostrado:
                    fallos.append(f"se corrompió «{palabra}»")
            resultados.append({"id": f"streaming-{i + 1:02d}", "cat": "streaming", "entrada": [texto[:40]], "texto": mostrado,
                               "fuente": None, "etiqueta": None, "receta": None, "fallos": fallos, "nota": ""})
    finally:
        servidor.ollama = original
    return resultados


def ejecutar(filtro_cat=None, filtro_id=None, limite=None):
    tmp = preparar()
    datos = json.loads(ESCENARIOS.read_text(encoding="utf-8"))["escenarios"]
    if filtro_cat:
        datos = [e for e in datos if e["cat"] == filtro_cat]
    if filtro_id:
        datos = [e for e in datos if e["id"] == filtro_id]
    if limite:
        datos = datos[:limite]
    resultados, inicio = [], time.time()
    for esc in datos:
        try:
            ultimo, texto = correr(esc, servidor.INDICE)
            fallos = comprobar(esc, ultimo, texto)
        except Exception as error:  # un escenario roto no tumba el banco
            ultimo, texto, fallos = {}, "", [f"error: {type(error).__name__}: {error}"]
        resultados.append({"id": esc["id"], "cat": esc["cat"], "entrada": esc["entrada"], "texto": texto,
                           "fuente": ultimo.get("fuente"), "etiqueta": ultimo.get("etiqueta"),
                           "receta": ultimo.get("receta"), "fallos": fallos, "nota": esc.get("nota", "")})
    if not filtro_cat and not filtro_id:
        resultados += unidades() + streaming()
    return {"total": len(resultados), "fallaron": sum(1 for r in resultados if r["fallos"]),
            "segundos": round(time.time() - inicio, 1), "resultados": resultados}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--cat")
    ap.add_argument("--id")
    ap.add_argument("-v", "--detalle", action="store_true")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    salida = ejecutar(a.cat, a.id)
    if a.json:
        print(json.dumps(salida, ensure_ascii=False))
        sys.exit(0)
    por_cat = {}
    for r in salida["resultados"]:
        por_cat.setdefault(r["cat"], [0, 0])
        por_cat[r["cat"]][0] += 1
        por_cat[r["cat"]][1] += bool(r["fallos"])
    for cat, (n, f) in por_cat.items():
        print(f"{'✔' if not f else '✘'} {cat:14s} {n - f}/{n}")
    print(f"\n{salida['total'] - salida['fallaron']}/{salida['total']} correctos en {salida['segundos']} s")
    if a.detalle or salida["fallaron"] <= 40:
        for r in salida["resultados"]:
            if r["fallos"]:
                print(f"\n✘ {r['id']}  {r['entrada'][-1][:70]!r}\n   → {r['texto'][:110]!r}  [{r['fuente']}/{r['etiqueta']}]")
                for f in r["fallos"]:
                    print("   -", f)
    sys.exit(1 if salida["fallaron"] else 0)
