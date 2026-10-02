#!/bin/bash
# M-Jarvis - Wi-Fi propia de la Latitude.
# Hace que este equipo cree su propia red Wi-Fi, «M-Jarvis», para llevarlo a donde no hay red (o donde
# la red del lugar no deja que los equipos se vean entre sí). Los celulares, tabletas y computadoras se
# conectan a esa Wi-Fi y abren http://10.42.0.1:8080 . Mientras está encendida, este equipo deja la
# Wi-Fi de la casa; al apagarla (o al reiniciar) vuelve a ella solo.
#
# Uso: wifi-propia.sh estado | crear (lee la contraseña por la entrada) | encender | apagar
PERFIL=${PERFIL:-mjarvis-wifi}
NOMBRE=${NOMBRE:-M-Jarvis}

tarjeta() { nmcli -t -f DEVICE,TYPE dev | awk -F: '$2 == "wifi" { print $1; exit }'; }

case "$1" in
  estado)
    if nmcli -t -f NAME con show --active | grep -qx "$PERFIL"; then echo encendida
    elif nmcli -t -f NAME con show | grep -qx "$PERFIL"; then echo apagada
    else echo sin-crear; fi ;;
  crear)
    IFS= read -r clave
    [ ${#clave} -ge 8 ] || { echo "La contraseña debe tener 8 caracteres o más." >&2; exit 2; }
    nmcli con add type wifi ifname "$(tarjeta)" con-name "$PERFIL" autoconnect no ssid "$NOMBRE" \
      802-11-wireless.mode ap 802-11-wireless.band bg 802-11-wireless.channel 6 ipv4.method shared ipv6.method disabled \
      wifi-sec.key-mgmt wpa-psk wifi-sec.psk "$clave" >/dev/null ;;
  encender)
    nmcli con up "$PERFIL" >/dev/null ;;
  apagar)
    nmcli con down "$PERFIL" >/dev/null 2>&1
    nmcli device connect "$(tarjeta)" >/dev/null 2>&1 ;;
  *)
    echo "Uso: $0 estado|crear|encender|apagar" >&2; exit 1 ;;
esac
