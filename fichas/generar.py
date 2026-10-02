#!/usr/bin/env python3
"""Genera las fichas de películas (PDF) a partir de los archivos .json de esta carpeta.

Mismo formato que las fichas 01-06: ficha técnica, la historia por actos con una figura de los
momentos clave, personajes con una figura de relaciones, lugares y objetos, escenas poscréditos,
conexiones, preguntas frecuentes y curiosidades.

Uso: python generar.py <carpeta_json> <carpeta_salida>      (necesita PyMuPDF)
"""
import html
import json
import math
import sys
from pathlib import Path

import pymupdf

ROJO, AZUL, NEGRO, GRIS = (0.66, 0.11, 0.13), (0.16, 0.38, 0.72), (0.1, 0.1, 0.12), (0.45, 0.45, 0.5)
CSS = """
body { font-family: sans-serif; font-size: 10.5pt; line-height: 1.42; color: #1a1a1a; }
h1 { font-size: 26pt; margin: 0 0 3pt 0; }
.sub { font-size: 11pt; color: #666; margin: 0 0 14pt 0; }
h2 { font-size: 17pt; color: #a81c22; border-bottom: 1px solid #a81c22; margin: 16pt 0 8pt 0; padding-bottom: 3pt; }
h3 { font-size: 12pt; margin: 10pt 0 2pt 0; }
p { margin: 0 0 6pt 0; text-align: justify; }
.dato { margin: 0 0 3pt 0; text-align: left; }
.pie { font-size: 8.5pt; color: #666; font-style: italic; text-align: center; margin: 2pt 0 8pt 0; }
"""


def texto(hoja, x, y, t, tam=10, color=NEGRO, negrita=False, centro=True):
    fuente = "hebo" if negrita else "helv"
    if centro:
        x -= pymupdf.get_text_length(t, fontname=fuente, fontsize=tam) / 2
    hoja.insert_text((x, y), t, fontsize=tam, fontname=fuente, color=color)


def partir(frase, ancho, tam):
    """Corta una frase en líneas que quepan en el ancho dado."""
    lineas, actual = [], ""
    for palabra in frase.split():
        if actual and pymupdf.get_text_length(actual + " " + palabra, fontsize=tam) > ancho:
            lineas.append(actual)
            actual = palabra
        else:
            actual = (actual + " " + palabra).strip()
    return lineas + [actual] if actual else lineas


def figura_momentos(momentos, destino):
    hoja = pymupdf.open().new_page(width=560, height=190)
    hoja.draw_rect(hoja.rect, color=None, fill=(1, 1, 1))
    texto(hoja, 280, 20, "Estructura de la historia", 11, negrita=True)
    n, ancho = len(momentos), 92
    paso = (560 - 30) / n
    for i, (titulo, detalle) in enumerate(momentos):
        x = 15 + paso * i + (paso - ancho) / 2
        if i:
            hoja.draw_line((x - (paso - ancho), 62), (x, 62), color=(0.75, 0.75, 0.78), width=1.2)
        hoja.draw_rect(pymupdf.Rect(x, 42, x + ancho, 82), color=None, fill=ROJO if i % 2 == 0 else AZUL, radius=0.12)
        texto(hoja, x + ancho / 2, 68, str(i + 1), 16, (1, 1, 1), negrita=True)
        texto(hoja, x + ancho / 2, 100, titulo, 8.5, negrita=True)
        for j, linea in enumerate(partir(detalle, ancho + 8, 7.5)[:3]):
            texto(hoja, x + ancho / 2, 126 + j * 10, linea, 7.5, GRIS)
    hoja.get_pixmap(dpi=170).save(destino)


def figura_relaciones(relaciones, destino):
    hoja = pymupdf.open().new_page(width=560, height=330)
    hoja.draw_rect(hoja.rect, color=None, fill=(1, 1, 1))
    texto(hoja, 280, 20, "Relaciones entre los personajes principales", 11, negrita=True)
    nodos = relaciones["nodos"]
    centro, radio, lugar = (280, 180), (190, 105), {}
    for i, (sigla, _) in enumerate(nodos):  # el primero arriba, los demás alrededor
        angulo = -math.pi / 2 + 2 * math.pi * i / len(nodos)
        lugar[sigla] = (centro[0] + radio[0] * math.cos(angulo), centro[1] + radio[1] * math.sin(angulo))
    for a, b, _ in relaciones["enlaces"]:
        hoja.draw_line(lugar[a], lugar[b], color=(0.72, 0.72, 0.75), width=1.1)
    for a, b, etiqueta in relaciones["enlaces"]:
        x, y = (lugar[a][0] + lugar[b][0]) / 2, (lugar[a][1] + lugar[b][1]) / 2
        largo = pymupdf.get_text_length(etiqueta, fontsize=7) + 8
        hoja.draw_rect(pymupdf.Rect(x - largo / 2, y - 7, x + largo / 2, y + 5), color=(0.82, 0.82, 0.85),
                       fill=(1, 1, 1), width=0.5, radius=0.2)
        texto(hoja, x, y + 2, etiqueta, 7, (0.3, 0.3, 0.33))
    for i, (sigla, nombre) in enumerate(nodos):
        x, y = lugar[sigla]
        hoja.draw_circle((x, y), 15, color=None, fill=ROJO if i % 2 == 0 else AZUL)
        texto(hoja, x, y + 4, sigla, 10, (1, 1, 1), negrita=True)
        texto(hoja, x, y - 22 if y <= centro[1] else y + 30, nombre, 8.5, negrita=True)
    hoja.get_pixmap(dpi=170).save(destino)


def generar(datos, salida, temporal):
    e = html.escape
    nombre = f"{datos['titulo']} ({datos['anio']})"
    figura_momentos(datos["momentos"], temporal / "momentos.png")
    figura_relaciones(datos["relaciones"], temporal / "relaciones.png")
    # Cada apartado lleva el nombre de la película en el título: así cada nota se entiende sola.
    obra = "serie" if any(k.startswith("Episodios") for k, _ in datos["ficha"]) else "película"
    h = [f"<h1>{e(nombre)}</h1>",
         f"<p class='sub'>Guía de consulta de M-Jarvis · {e(datos['saga'])}. Información completa de la {obra}, "
         "parte por parte, con personajes, lugares, objetos y preguntas frecuentes.</p>",
         f"<h2>Ficha técnica de {e(datos['titulo'])}</h2>"]
    h += [f"<p class='dato'>{e(k)}: {e(v)}</p>" for k, v in datos["ficha"]]
    h += [f"<h2>La historia de {e(datos['titulo'])}</h2>",
          "<p style='text-align:center'><img src='momentos.png' width='480'></p>",
          f"<p class='pie'>Figura 1. Los grandes momentos de la {obra}, en orden.</p>"]
    for titulo, parrafos in datos["actos"]:
        h.append(f"<h3>{e(titulo)}</h3>")
        h += [f"<p>{e(p)}</p>" for p in parrafos]
    h += [f"<h2>Personajes de {e(datos['titulo'])}</h2>",
          "<p style='text-align:center'><img src='relaciones.png' width='480'></p>",
          "<p class='pie'>Figura 2. Cómo se conectan los personajes principales.</p>"]
    h += [f"<h3>{e(n)}</h3><p>{e(t)}</p>" for n, t in datos["personajes"]]
    h.append(f"<h2>Lugares, objetos y tecnología de {e(datos['titulo'])}</h2>")
    h += [f"<h3>{e(n)}</h3><p>{e(t)}</p>" for n, t in datos["cosas"]]
    h += [f"<h2>Escenas poscréditos de {e(datos['titulo'])}</h2><p>{e(datos['creditos'])}</p>",
          f"<h2>Conexiones de {e(datos['titulo'])} con otras películas y series</h2>"]
    h += [f"<p>{e(c)}</p>" for c in datos["conexiones"]]
    h.append(f"<h2>Preguntas frecuentes sobre {e(datos['titulo'])}</h2>")
    h += [f"<h3>{e(p)}</h3><p>{e(r)}</p>" for p, r in datos["preguntas"]]
    h.append(f"<h2>Curiosidades de {e(datos['titulo'])}</h2>")
    h += [f"<p>{e(c)}</p>" for c in datos["curiosidades"]]

    historia = pymupdf.Story(html="".join(h), user_css=CSS, archive=pymupdf.Archive(str(temporal)))
    hoja = pymupdf.paper_rect("letter")
    zona = hoja + (65, 62, -65, -62)
    escritor = pymupdf.DocumentWriter(str(salida))
    sigue = True
    while sigue:
        pagina = escritor.begin_page(hoja)
        sigue, _ = historia.place(zona)
        historia.draw(pagina)
        escritor.end_page()
    escritor.close()
    return pymupdf.open(salida).page_count


if __name__ == "__main__":
    origen, destino = Path(sys.argv[1]), Path(sys.argv[2])
    destino.mkdir(parents=True, exist_ok=True)
    temporal = destino / "_figuras"
    temporal.mkdir(exist_ok=True)
    for archivo in sorted(origen.glob("*.json")):
        datos = json.loads(archivo.read_text(encoding="utf-8"))
        paginas = generar(datos, destino / f"{archivo.stem}.pdf", temporal)
        print(f"{archivo.stem}.pdf: {paginas} páginas")
