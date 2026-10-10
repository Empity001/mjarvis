#!/usr/bin/env bash
# Envia los cambios de esta carpeta a la Latitude (~/mjarvis) y reinicia el servicio si hace falta.
# Uso:  desplegar.sh        -> muestra que cambiaria (simulacion)
#       desplegar.sh -y     -> aplica
# Reglas: nunca borra nada alla (sin --delete) y no toca lo que sube el usuario
# (conocimiento/, documentos/, web/medios/, aprendido.json, desactivadas.json, grafos generados).
set -u
cd "$(dirname "$0")/.." || exit 1
DESTINO="mjarvis:mjarvis"
APLICAR=0; [ "${1:-}" = "-y" ] && APLICAR=1

OPC=(-rlt --itemize-changes --exclude __pycache__ --exclude '*.pyc')
[ "$APLICAR" -eq 0 ] && OPC+=(-n)

cambios=""
envia() {  # origen destino [exclusiones...]
  local o="$1" d="$2"; shift 2
  local ex=(); for e in "$@"; do ex+=(--exclude "$e"); done
  # Las líneas de rsync llevan el nombre relativo: se les antepone la carpeta para saber qué cambió.
  cambios+="$(rsync "${OPC[@]}" "${ex[@]}" "$o" "$DESTINO/$d" | grep '^<f' | sed -E "s|^(<f\S+ )|\1$d|")"$'\n'
}

# Lo que se aprueba en el panel (palabras del filtro, variantes de frases) se edita en la Latitude: antes de
# enviar, se trae lo que allá sea más nuevo para no pisarlo.
rsync -rtu --ignore-missing-args --itemize-changes mjarvis:mjarvis/comportamiento/reacciones.json mjarvis:mjarvis/comportamiento/personalidad.json comportamiento/ | grep '^>f' | sed 's/^/(traído de la Latitude) /'

envia servidor/       servidor/
envia web/            web/            medios graph.json trato.json
envia comportamiento/ comportamiento/ aprendido.json recetas.json propuestas.json _respaldos
envia grafo/          grafo/          graph.json
envia latitude/m-jarvis.sh ""

cambios="$(echo "$cambios" | sed '/^$/d')"
if [ -z "$cambios" ]; then echo "Nada que enviar: la Latitude ya esta al dia."; exit 0; fi
echo "$cambios"

if [ "$APLICAR" -eq 0 ]; then echo; echo "(simulacion) usa  desplegar.sh -y  para aplicar."; exit 0; fi

# Reiniciar solo si cambio el servidor o su configuracion; corta la pregunta en curso.
if echo "$cambios" | grep -qE ' (servidor/|comportamiento/)'; then
  ssh mjarvis 'systemctl --user restart mjarvis-web' && echo "Servicio mjarvis-web reiniciado."
else
  echo "Solo cambiaron archivos web: recarga la pagina, no hizo falta reiniciar."
fi
