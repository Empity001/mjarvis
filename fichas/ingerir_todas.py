"""Ingiere de una vez varias fichas en M-Jarvis y reconstruye el mapa al final.

Uso (en la Latitude): ~/mjarvis/venv/bin/python ingerir_todas.py <carpeta con NN-*.pdf> [desde] [hasta]

Hace lo mismo que subirlas una a una desde el panel, pero sin reconstruir el mapa 59 veces.
El servidor recarga solo su índice cuando cambia graph.json: no hace falta reiniciarlo.
"""
import shutil
import sys
import time
from pathlib import Path

RAIZ = Path.home() / "mjarvis"
sys.path[:0] = [str(RAIZ / "servidor"), str(RAIZ / "grafo")]
import build  # noqa: E402
import ingesta  # noqa: E402

carpeta = Path(sys.argv[1])
desde = int(sys.argv[2]) if len(sys.argv) > 2 else 1
hasta = int(sys.argv[3]) if len(sys.argv) > 3 else 99
inicio, total = time.time(), 0
for pdf in sorted(carpeta.glob("[0-9][0-9]-*.pdf")):
    if not desde <= int(pdf.name[:2]) <= hasta:
        continue
    destino = RAIZ / "documentos" / pdf.name
    shutil.copy(pdf, destino)
    resumen = ingesta.procesar(destino, avisar=lambda *a, **k: None)
    total += resumen["notas"]
    print(f"{pdf.name}: {resumen['notas']} notas, {resumen['imagenes']} imágenes", flush=True)
build.main(str(RAIZ / "conocimiento"), str(RAIZ / "web" / "grafo" / "graph.json"))
print(f"Listo: {total} notas nuevas en {time.time() - inicio:.0f} s")
