#!/usr/bin/env python3
"""Manda una conversación de prueba al servidor de M-Jarvis y muestra respuestas y tiempos.

Uso: python3 probar.py "pregunta 1" "pregunta 2" ...   (la primera empieza conversación nueva)
     python3 probar.py @archivo.txt                     (una pregunta por línea; '---' empieza otra conversación)
"""
import json
import sys
import time
import urllib.request
from pathlib import Path

URL = "http://localhost:8080/api/preguntar"

preguntas = sys.argv[1:]
if preguntas and preguntas[0].startswith("@"):
    preguntas = [l.strip() for l in Path(preguntas[0][1:]).read_text(encoding="utf-8").splitlines() if l.strip()]

nueva = True
for pregunta in preguntas:
    if pregunta == "---":
        nueva = True
        continue
    cuerpo = json.dumps({"pregunta": pregunta, "nueva": nueva}).encode()
    nueva = False
    inicio, primera, texto, cabeza, fin = time.time(), None, "", {}, {}
    with urllib.request.urlopen(urllib.request.Request(URL, cuerpo, {"Content-Type": "application/json"})) as r:
        for linea in r:
            d = json.loads(linea)
            if d["tipo"] == "inicio":
                cabeza = d
            elif d["tipo"] == "texto":
                primera = primera or time.time() - inicio
                texto += d["t"]
            else:
                fin = d
    ruta = cabeza.get("fuente", "?") + (f":{cabeza['etiqueta']}" if cabeza.get("etiqueta") else "")
    print(f"\n> {pregunta}\n  [{ruta} {cabeza.get('nodos')}] 1a palabra {primera or 0:.1f}s, total {fin.get('segundos')}s")
    print(f"  {texto.strip()}")
