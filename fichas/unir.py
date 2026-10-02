"""Une las fichas sueltas en un PDF maestro con portada, índice y marcadores.

Uso: python unir.py <carpeta con NN-*.pdf> <salida.pdf> [tope en MB]

Si el resultado pasa del tope (60 MB por defecto), se divide en varias partes:
salida - parte 1.pdf, salida - parte 2.pdf, etc.
"""
import re
import sys
from pathlib import Path

import pymupdf

AZUL, GRIS, NEGRO = (0.10, 0.32, 0.62), (0.42, 0.45, 0.50), (0.10, 0.11, 0.13)
ANCHO, ALTO = pymupdf.paper_size("letter")
POR_HOJA = 38  # títulos por página de índice


def titulo_de(pdf):
    """El título de la ficha: el primer bloque de texto de su primera página (puede ocupar dos líneas)."""
    for bloque in pdf[0].get_text("blocks"):
        texto = " ".join(bloque[4].split()).replace("ﬁ", "fi").replace("ﬂ", "fl")
        if texto:
            return re.sub(r" Pág\. \d+$", "", texto.removeprefix("M-Jarvis · "))
    return "Sin título"


def unir(fichas, salida, nombre):
    titulos = [titulo_de(pymupdf.open(f)) for f in fichas]
    hojas_indice = -(-len(fichas) // POR_HOJA)
    libro = pymupdf.open()

    portada = libro.new_page(width=ANCHO, height=ALTO)
    portada.insert_textbox((60, 250, ANCHO - 60, 330), "Universo Marvel", fontsize=40, fontname="hebo", color=AZUL, align=1)
    portada.insert_textbox((60, 330, ANCHO - 60, 370), nombre, fontsize=17, fontname="helv", color=NEGRO, align=1)
    portada.insert_textbox((90, 390, ANCHO - 90, 470),
                           f"Guía de consulta de M-Jarvis. {len(fichas)} fichas: la historia completa de cada película y serie, "
                           "con personajes, lugares, objetos, conexiones y preguntas frecuentes.",
                           fontsize=11.5, fontname="helv", color=GRIS, align=1)
    for _ in range(hojas_indice):
        libro.new_page(width=ANCHO, height=ALTO)

    marcadores, inicio = [], []
    for ficha, titulo in zip(fichas, titulos):
        pdf = pymupdf.open(ficha)
        inicio.append(libro.page_count + 1)
        marcadores.append([1, f"{ficha.name[:2]} · {titulo}", libro.page_count + 1])
        libro.insert_pdf(pdf)

    for i, (ficha, titulo, pagina) in enumerate(zip(fichas, titulos, inicio)):
        hoja = libro[1 + i // POR_HOJA]
        if i % POR_HOJA == 0:
            hoja.insert_text((60, 70), "Índice", fontsize=22, fontname="hebo", color=AZUL)
        y = 105 + (i % POR_HOJA) * 17
        hoja.insert_text((60, y), ficha.name[:2], fontsize=10.5, fontname="hebo", color=AZUL)
        hoja.insert_text((84, y), titulo[:78], fontsize=10.5, fontname="helv", color=NEGRO)
        hoja.insert_text((ANCHO - 84, y), str(pagina), fontsize=10.5, fontname="helv", color=GRIS)
        hoja.insert_link({"kind": pymupdf.LINK_GOTO, "from": pymupdf.Rect(58, y - 11, ANCHO - 58, y + 4), "page": pagina - 1})

    libro.set_toc(marcadores)
    libro.set_metadata({"title": f"M-Jarvis · Universo Marvel · {nombre}", "author": "M-Jarvis"})
    libro.save(salida, garbage=4, deflate=True)
    return libro.page_count


if __name__ == "__main__":
    carpeta, salida = Path(sys.argv[1]), Path(sys.argv[2])
    tope = float(sys.argv[3]) if len(sys.argv) > 3 else 60
    fichas = sorted(carpeta.glob("[0-9][0-9]-*.pdf"))
    paginas = unir(fichas, salida, "Guía maestra")
    peso = salida.stat().st_size / 1e6
    print(f"{salida.name}: {len(fichas)} fichas, {paginas} páginas, {peso:.1f} MB")
    if peso > tope:
        partes = int(peso // tope) + 1
        tramo = -(-len(fichas) // partes)
        salida.unlink()
        for n in range(partes):
            grupo = fichas[n * tramo:(n + 1) * tramo]
            destino = salida.with_name(f"{salida.stem} - parte {n + 1}.pdf")
            paginas = unir(grupo, destino, f"Guía maestra, parte {n + 1} de {partes}")
            print(f"{destino.name}: {len(grupo)} fichas, {paginas} páginas, {destino.stat().st_size / 1e6:.1f} MB")
