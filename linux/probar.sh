#!/usr/bin/env bash
# Prueba los cambios de esta carpeta en la Latitude SIN tocar el servicio en marcha:
# copia servidor/, comportamiento/ y grafo/ a ~/mjarvis-prueba y corre los 300+ escenarios con un modelo simulado.
# Uso:  probar.sh        -> resumen        probar.sh -v  -> detalle de cada fallo
# Si queda todo en verde, se envía con  desplegar.sh -y
set -u
cd "$(dirname "$0")/.." || exit 1
ssh mjarvis 'mkdir -p ~/mjarvis-prueba/web/grafo ~/mjarvis-prueba/conocimiento && cp ~/mjarvis/web/grafo/graph.json ~/mjarvis/web/grafo/trato.json ~/mjarvis-prueba/web/grafo/ 2>/dev/null; cp ~/mjarvis/clave.txt ~/mjarvis-prueba/ 2>/dev/null; true'
rsync -rt --exclude __pycache__ --exclude propuestas.json --exclude recetas.json servidor comportamiento grafo mjarvis:mjarvis-prueba/
ssh mjarvis "cd ~/mjarvis-prueba/servidor && ~/mjarvis/venv/bin/python pruebas_rutas.py ${1:-}"
