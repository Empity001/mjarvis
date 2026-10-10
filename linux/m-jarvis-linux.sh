#!/usr/bin/env bash
# M-Jarvis - lanzador para Linux (protocolo compartido), equivalente a M-Jarvis.bat.
# Busca la Latitude (Wi-Fi, nombre .local o cable directo) y abre sus vistas en el navegador.
# No instala nada en la Latitude: ella sirve todo. Escritorio remoto = tunel SSH -> noVNC.

CARPETA="${XDG_CONFIG_HOME:-$HOME/.config}/mjarvis"
mkdir -p "$CARPETA"
GUARDADA="$CARPETA/direccion.txt"

LOG="$CARPETA/lanzador.log"

navegador() {
  # Zen (Flatpak) es el navegador del usuario; si no abre, se usa el predeterminado.
  if flatpak info app.zen_browser.zen >/dev/null 2>&1; then
    flatpak run app.zen_browser.zen --new-window "$1" >>"$LOG" 2>&1 &
  else
    xdg-open "$1" >>"$LOG" 2>&1 &
  fi
}

probar() { curl -s -m 4 -o /dev/null "http://$1:8080/api/estado"; }

buscar() {
  local candidatos=()
  # El cable va primero: responde en menos de 1 ms (la Wi-Fi, en ~8 ms con picos) y el escritorio remoto se nota mucho.
  for ip in $(ip -4 neigh show dev eno1 2>/dev/null | awk '$1 ~ /^(169\.254\.|10\.43\.0\.)/ {print $1}') \
            $(ip -4 neigh show nud reachable nud stale 2>/dev/null | awk '$1 ~ /^(169\.254\.|10\.43\.0\.)/ {print $1}'); do
    candidatos+=("$ip")
  done
  [ -r "$GUARDADA" ] && candidatos+=("$(cat "$GUARDADA")")
  candidatos+=("ferr-latitude-5590.local" "10.42.0.1")
  for h in "${candidatos[@]}"; do
    [ -n "$h" ] && probar "$h" && { HOST="$h"; echo "$h" >"$GUARDADA"; return 0; }
  done
  return 1
}

until buscar; do
  r=$(zenity --entry --title="M-Jarvis" --text="No encuentro a M-Jarvis.\nRevisa que la Latitude este encendida y en la misma red (o por cable).\n\nEscribe su direccion o deja vacio para reintentar:" 2>/dev/null) || exit 1
  [ -n "$r" ] && echo "$r" >"$GUARDADA"
done
# Zen corre en Flatpak y no resuelve nombres .local: a los navegadores se les da la IP.
IP=$(getent ahostsv4 "$HOST" 2>/dev/null | awk 'NR==1{print $1}')
BASE="http://${IP:-$HOST}:8080"

SOCKET="$CARPETA/tunel.sock"

# El tunel va por la misma direccion que se eligio arriba (el cable si esta enchufado), no por el nombre .local,
# que casi siempre resuelve a la Wi-Fi. Sin compresion en SSH: en cable sobra ancho de banda y comprimir solo suma retraso.
escritorio_remoto() {
  ssh -S "$SOCKET" -O check mjarvis >/dev/null 2>&1 || \
    ssh -M -S "$SOCKET" -f -N -o ExitOnForwardFailure=yes -o HostName="${IP:-$HOST}" -o Compression=no \
        -o IPQoS=throughput -c aes128-gcm@openssh.com -L 6080:localhost:6080 mjarvis
  navegador "http://localhost:6080/vnc.html?autoconnect=1&resize=scale&quality=8&compression=1&show_dot=1"
}

cerrar_tunel() { ssh -S "$SOCKET" -O exit mjarvis >/dev/null 2>&1; }

while true; do
  op=$(zenity --list --title="M-Jarvis" --width=460 --height=420 \
    --text="Conectado a $HOST" --column="Opcion" --hide-header \
    "Panel" "Chat" "Red neuronal (mapa)" "Todo junto (chat + mapa)" \
    "Escritorio remoto de la Latitude" "Terminal SSH" "Estado del sistema" \
    "Cerrar escritorio remoto" "Salir" 2>/dev/null) || exit 0
  case "$op" in
    "Panel") navegador "$BASE/#control/archivos" ;;
    "Chat") navegador "$BASE/?vista=chat" ;;
    "Red neuronal (mapa)") navegador "$BASE/grafo/" ;;
    "Todo junto (chat + mapa)") navegador "$BASE/" ;;
    "Escritorio remoto de la Latitude") escritorio_remoto ;;
    "Terminal SSH") (command -v ptyxis >/dev/null && ptyxis -- ssh mjarvis || \
                     command -v gnome-terminal >/dev/null && gnome-terminal -- ssh mjarvis || \
                     xterm -e ssh mjarvis) >/dev/null 2>&1 & ;;
    "Estado del sistema")
      curl -s -m 5 "$BASE/api/estado" | python3 -m json.tool | zenity --text-info --title="Estado" --width=480 --height=420 ;;
    "Cerrar escritorio remoto") cerrar_tunel ;;
    "Salir") exit 0 ;;
  esac
done
