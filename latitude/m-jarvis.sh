#!/bin/bash
# M-Jarvis - lanzador en la Latitude (protocolo local).
# Muestra un menú para abrir cada parte por separado. Al cerrar una pantalla (Alt+F4) el menú vuelve.
# Uso: m-jarvis.sh [chat|todo|mapa|panel]   (con argumento abre esa vista antes de mostrar el menú)

URL=http://localhost:8080

# Una sola copia del lanzador a la vez: abrirlo dos veces dejaba dos menus peleando por la pantalla.
exec 9>/tmp/mjarvis-lanzador.candado
flock -n 9 || exit 0

esperar_servidor() {
  for _ in $(seq 1 60); do curl -s -o /dev/null "$URL/api/estado" && return 0; sleep 2; done
  zenity --error --title="M-Jarvis" --text="El servidor de M-Jarvis no responde. Reinicie el equipo." 2>/dev/null
  return 1
}

cerrar_pantalla() {
  pkill -TERM -x firefox 2>/dev/null
  for _ in $(seq 1 15); do pgrep -x firefox >/dev/null || return 0; sleep 0.2; done
}

# Abre una vista a pantalla completa y espera a que la cierren.
pantalla() { cerrar_pantalla; firefox --kiosk "$URL$1" >/dev/null 2>&1; }

# Abre una vista en ventana normal (para el panel, donde hay que moverse entre cosas).
ventana() { cerrar_pantalla; firefox --new-window "$URL$1" >/dev/null 2>&1; }

compartir() {
  local datos
  datos=$(python3 - <<'EOF'
import json, urllib.request
leer = lambda ruta: json.loads(urllib.request.urlopen("http://localhost:8080" + ruta, timeout=5).read())
estado, clave = leer("/api/estado"), leer("/api/clave").get("clave", "")
lineas = ["Para conectar otro equipo (protocolo compartido):", "",
          "1. Póngalo en la misma red Wi-Fi que este, o únalos con un cable de red.",
          "2. En ese equipo abra el navegador en una de estas direcciones:", ""]
lineas += ["      http://%s:8080/panel.html" % d for d in estado["direcciones"]]
lineas += ["      http://%s.local:8080/panel.html" % estado["nombre"].lower(), "",
           "En Windows también puede usar el lanzador M-Jarvis.bat (se descarga desde el panel).", ""]
lineas += ["Clave para subir o borrar archivos desde otro equipo:  " + clave] if clave else ["No se pide clave para gestionar archivos."]
print("\n".join(lineas))
EOF
)
  zenity --info --title="M-Jarvis · Compartir" --width=560 --text="$datos" 2>/dev/null
}

# Wi-Fi propia: este equipo crea la red «M-Jarvis» para que celulares y otras computadoras se conecten
# a él donde no hay red. La contraseña la elige quien lo usa, la primera vez.
wifi_propia() {
  local guion="$HOME/mjarvis/wifi-propia.sh" clave
  case "$("$guion" estado)" in
    encendida)
      zenity --question --title="M-Jarvis · Wi-Fi propia" --width=460 \
        --text="La Wi-Fi «M-Jarvis» está encendida.\n\n¿Apagarla y volver a la Wi-Fi normal?" 2>/dev/null || return
      "$guion" apagar
      return ;;
    sin-crear)
      clave=$(zenity --entry --title="M-Jarvis · Wi-Fi propia" --width=460 \
        --text="Elija la contraseña de la Wi-Fi «M-Jarvis» (8 caracteres o más).\nEs la que escribirán los celulares y equipos que se conecten.") || return
      if ! printf '%s\n' "$clave" | "$guion" crear; then
        zenity --error --title="M-Jarvis" --text="No se pudo crear la Wi-Fi. La contraseña debe tener 8 caracteres o más." 2>/dev/null
        return
      fi ;;
  esac
  if "$guion" encender; then
    zenity --info --title="M-Jarvis · Wi-Fi propia" --width=520 \
      --text="Wi-Fi «M-Jarvis» encendida.\n\n1. En el celular, la tableta o la otra computadora, conéctese a la Wi-Fi «M-Jarvis».\n2. Abra el navegador en:   http://10.42.0.1:8080\n\nEn «Conectar» hay un código QR para abrirlo con la cámara.\nMientras esté encendida, este equipo no tiene internet (no lo necesita)." 2>/dev/null
  else
    zenity --error --title="M-Jarvis" --text="No se pudo encender la Wi-Fi propia." 2>/dev/null
  fi
}

abrir() {
  case "$1" in
    "Conectar") ventana "/conectar.html" ;;
    "Wi-Fi propia") wifi_propia ;;
    todo|"Todo junto") pantalla "/" ;;
    chat|"Solo chat") pantalla "/?vista=chat" ;;
    mapa|"Solo red neuronal") pantalla "/grafo/" ;;
    panel|"Panel") ventana "/panel.html" ;;
    "Compartir") compartir ;;
    "Cerrar pantalla") cerrar_pantalla ;;
  esac
}

esperar_servidor || exit 1
[ -n "$1" ] && abrir "$1"

while true; do
  opcion=$(zenity --list --title="M-Jarvis" --width=660 --height=460 \
    --text="Protocolo local · elija qué abrir. Para volver a este menú, cierre la pantalla con Alt+F4." \
    --column="Abrir" --column="Qué es" \
    "Todo junto" "Chat y red neuronal en esta pantalla" \
    "Solo chat" "La conversación con Jarvis" \
    "Solo red neuronal" "El mapa a pantalla completa, con subtítulos" \
    "Panel" "Archivos, estado del sistema y últimas preguntas" \
    "Conectar" "Códigos QR y direcciones para celulares y otros equipos" \
    "Wi-Fi propia" "Crea la red «M-Jarvis» para usarlo donde no hay red (encender o apagar)" \
    "Compartir" "Direcciones y la clave de gestión de archivos" \
    "Cerrar pantalla" "Cierra la ventana de M-Jarvis que esté abierta" 2>/dev/null) || exit 0
  abrir "$opcion"
done
