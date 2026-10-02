#!/usr/bin/env python3
"""Mide en la laptop lo que importa para M-Jarvis: cuanto tarda el modelo en
leer el contexto (tiempo hasta la primera palabra) y a que velocidad escribe.

Uso: python3 bench.py modelo1 modelo2 ...
"""
import json
import sys
import time
import urllib.request

URL = "http://localhost:11434/api/generate"

SISTEMA = (
    "Eres JARVIS. Hablas con educación británica, ironía seca y humor sutil. "
    "Tratas al usuario de \"señor\". Respuestas de máximo 2 frases. "
    "Responde solo con el contexto dado; si no está ahí, admítelo con ingenio."
)

PARRAFOS = [
    "Las alas del taller se construyeron en tres etapas. Primero se cortó el armazón en tubo de aluminio de 12 mm, con una envergadura total de 2,4 metros y un peso de 3,1 kilogramos.",
    "La segunda etapa fue el mecanismo de apertura: dos actuadores lineales de 12 voltios, controlados por un Arduino Nano, despliegan cada ala en 1,8 segundos.",
    "Para las plumas se usó espuma EVA de 5 mm cortada con plantilla; en total se pegaron 146 plumas con cemento de contacto y se pintaron con aerógrafo en gris metálico.",
    "El arnés reparte el peso sobre los hombros y la cintura con correas de nailon de 40 mm; se probaron cuatro versiones antes de dar con una que no resbalara.",
    "La batería es un paquete de litio de 3 celdas y 2200 mAh que da unos 25 minutos de uso continuo; va en un bolsillo acolchado en la espalda baja.",
    "El guantelete de Thanos se imprimió en PLA en 38 piezas, con 61 horas de impresión en total, y las gemas se moldearon en resina epoxi con LED de 3 mm dentro.",
    "El escudo del Capitán América mide 60 centímetros de diámetro; es un disco de aluminio repujado sobre un molde de madera y pintado con tres capas de esmalte automotriz.",
    "El presupuesto total de los tres proyectos fue de 18 400 pesos dominicanos, de los cuales las alas se llevaron casi la mitad por los actuadores.",
    "El error más costoso fue quemar el primer controlador por invertir la polaridad; desde entonces cada conector lleva una marca roja en el positivo.",
    "El equipo trabajó los sábados durante cuatro meses; la pintura y el acabado tomaron las últimas tres semanas.",
]

PREGUNTAS = [
    "¿Cuánto pesan las alas y cuánto tardan en abrirse?",
    "¿Cuántas piezas tiene el guantelete y cuánto tardó en imprimirse?",
]


def prompt(n_parrafos, pregunta, desplazar):
    trozos = [PARRAFOS[(i + desplazar) % len(PARRAFOS)] for i in range(n_parrafos)]
    return "Contexto:\n" + "\n".join(trozos) + "\n\nPregunta: " + pregunta


def correr(modelo, texto):
    cuerpo = json.dumps({
        "model": modelo, "system": SISTEMA, "prompt": texto, "stream": True,
        "keep_alive": "30m", "options": {"num_predict": 80, "temperature": 0.3},
    }).encode()
    pet = urllib.request.Request(URL, cuerpo, {"Content-Type": "application/json"})
    t0 = time.time()
    primera = None
    salida = ""
    fin = {}
    with urllib.request.urlopen(pet, timeout=900) as r:
        for linea in r:
            d = json.loads(linea)
            if d.get("response") and primera is None:
                primera = time.time() - t0
            salida += d.get("response", "")
            if d.get("done"):
                fin = d
    return primera, time.time() - t0, fin, salida.strip()


def main():
    for modelo in sys.argv[1:]:
        print(f"\n=== {modelo} ===")
        casos = [("carga + 3 párrafos", 3, 0, 0), ("3 párrafos", 3, 1, 3),
                 ("10 párrafos", 10, 0, 5), ("10 párrafos (2)", 10, 1, 2)]
        for nombre, n, q, desp in casos:
            primera, total, fin, salida = correr(modelo, prompt(n, PREGUNTAS[q], desp))
            pt, pd = fin.get("prompt_eval_count", 0), fin.get("prompt_eval_duration", 1) / 1e9
            et, ed = fin.get("eval_count", 0), fin.get("eval_duration", 1) / 1e9
            print(f"{nombre:20s} 1a palabra {primera:5.1f}s | total {total:5.1f}s | "
                  f"lee {pt:4d} tok a {pt / pd:5.1f} tok/s | escribe {et:3d} tok a {et / ed:4.1f} tok/s | "
                  f"carga {fin.get('load_duration', 0) / 1e9:4.1f}s")
            print(f"    -> {salida[:230]}")


if __name__ == "__main__":
    main()
