"""Dibuja el icono de M-Jarvis (para el celular y la tableta) en los tamaños que piden Android y iOS.

Uso (en la Latitude): venv/bin/python icono.py ~/mjarvis/web
"""
import math
import sys
from pathlib import Path

import fitz  # PyMuPDF

FONDO, ANILLO, NUCLEO, TENUE = (0.051, 0.067, 0.09), (0.416, 0.663, 1), (0.31, 0.82, 0.77), (0.17, 0.27, 0.4)


def dibujar(lado, destino):
    doc = fitz.open()
    pagina = doc.new_page(width=lado, height=lado)
    pagina.draw_rect(pagina.rect, color=None, fill=FONDO)
    c = fitz.Point(lado / 2, lado / 2)
    # Un núcleo con sus neuronas alrededor, unidas por hilos: la red de M-Jarvis en pequeño.
    puntos = [fitz.Point(c.x + math.cos(a) * lado * 0.3, c.y + math.sin(a) * lado * 0.3)
              for a in (i * math.tau / 6 + 0.26 for i in range(6))]
    for i, p in enumerate(puntos):
        pagina.draw_line(c, p, color=TENUE, width=lado * 0.016)
        pagina.draw_line(p, puntos[(i + 1) % 6], color=TENUE, width=lado * 0.012)
    pagina.draw_circle(c, lado * 0.3, color=ANILLO, width=lado * 0.022)
    for i, p in enumerate(puntos):
        pagina.draw_circle(p, lado * (0.05 if i % 2 else 0.038), color=None, fill=ANILLO if i % 2 else NUCLEO)
    pagina.draw_circle(c, lado * 0.105, color=None, fill=NUCLEO)
    pagina.draw_circle(c, lado * 0.045, color=None, fill=(1, 1, 1))
    pagina.get_pixmap(alpha=False).save(destino)


if __name__ == "__main__":
    carpeta = Path(sys.argv[1])
    for lado in (180, 192, 512):
        dibujar(lado, carpeta / f"icono-{lado}.png")
    print("iconos listos")
