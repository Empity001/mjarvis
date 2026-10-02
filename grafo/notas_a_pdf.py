#!/usr/bin/env python3
"""Arma un PDF legible a partir de una carpeta de notas.

Uso: python3 notas_a_pdf.py <carpeta_notas> <salida.pdf> "<título>" "<subtítulo>"
Requiere PyMuPDF.
"""
import html
import sys
from pathlib import Path

import pymupdf as fitz

from build import leer

SECCIONES = [
    ("dato", "El universo"), ("personaje", "Personajes"), ("organización", "Equipos y organizaciones"),
    ("objeto", "Objetos y tecnología"), ("lugar", "Lugares"), ("evento", "Grandes eventos"),
    ("proyecto", "Proyectos"), ("pieza", "Piezas"),
]
CSS = """
body { font-family: sans-serif; font-size: 11pt; line-height: 1.45; color: #1a1a1a; }
h1 { font-size: 26pt; margin: 0 0 4pt 0; }
.sub { font-size: 12pt; color: #555; margin: 0 0 22pt 0; }
h2 { font-size: 16pt; color: #9a1b1b; border-bottom: 1px solid #9a1b1b; margin: 20pt 0 8pt 0; padding-bottom: 3pt; }
h3 { font-size: 12.5pt; margin: 12pt 0 2pt 0; }
p { margin: 0 0 6pt 0; text-align: justify; }
"""


def main(carpeta, salida, titulo, subtitulo):
    por_tipo = {}
    for ruta in sorted(Path(carpeta).glob("**/*.md")):
        meta, _, resumen = leer(ruta)
        por_tipo.setdefault(meta.get("tipo", "dato"), []).append((ruta.stem, resumen))
    partes = [f"<h1>{html.escape(titulo)}</h1><p class='sub'>{html.escape(subtitulo)}</p>"]
    for tipo, nombre in SECCIONES:
        if tipo not in por_tipo:
            continue
        partes.append(f"<h2>{nombre}</h2>")
        for nota, texto in por_tipo[tipo]:
            partes.append(f"<h3>{html.escape(nota)}</h3><p>{html.escape(texto)}</p>")
    historia = fitz.Story(html="".join(partes), user_css=CSS)
    hoja = fitz.paper_rect("letter")
    zona = hoja + (62, 62, -62, -62)
    escritor = fitz.DocumentWriter(salida)
    sigue = True
    while sigue:
        pagina = escritor.begin_page(hoja)
        sigue, _ = historia.place(zona)
        historia.draw(pagina)
        escritor.end_page()
    escritor.close()
    print(f"{fitz.open(salida).page_count} páginas -> {salida}")


if __name__ == "__main__":
    main(*sys.argv[1:5])
