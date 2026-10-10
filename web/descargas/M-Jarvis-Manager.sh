#!/usr/bin/env bash
# M-Jarvis Manager — abre la consola de M-Jarvis como una aplicación y busca a la Latitude donde esté.
# Funciona sin instalar nada. Si no la encuentra, pide su dirección (se ve en la Latitude: M-Jarvis → Compartir).
CARPETA="${XDG_CONFIG_HOME:-$HOME/.config}/mjarvis"; mkdir -p "$CARPETA"; GUARDADA="$CARPETA/direccion.txt"
probar() { curl -s -m 3 -o /dev/null "http://$1:8080/api/estado"; }
encontrar() {
  for h in "$(cat "$GUARDADA" 2>/dev/null)" ferr-latitude-5590.local 10.42.0.1 10.44.0.1; do
    [ -n "$h" ] && probar "$h" && { HOST="$h"; echo "$h" > "$GUARDADA"; return 0; }
  done
  # al compartirle internet desde esta computadora, la Latitude recibe una dirección de este equipo: se busca entre los vecinos
  for h in $(ip -4 neigh 2>/dev/null | awk '{print $1}') $(arp -an 2>/dev/null | sed -E 's/.*\(([0-9.]+)\).*/\1/'); do
    probar "$h" && { HOST="$h"; echo "$h" > "$GUARDADA"; return 0; }
  done
  return 1
}
until encontrar; do
  printf "No encuentro a M-Jarvis. Revise que esté encendida y conectada (Wi-Fi o cable).\nEscriba su dirección (Enter para reintentar): "; read -r r
  [ -n "$r" ] && echo "$r" > "$GUARDADA"
done
URL="http://$HOST:8080/#control"
abrir() {
  case "$(uname)" in
    Darwin) for app in "Google Chrome" "Microsoft Edge" "Brave Browser" "Chromium"; do
              [ -d "/Applications/$app.app" ] && { open -na "$app" --args --app="$URL" --user-data-dir="$CARPETA/navegador"; return; }
            done; open "$URL" ;;
    *)      for n in google-chrome chrome chromium chromium-browser microsoft-edge brave-browser; do
              command -v "$n" >/dev/null && { "$n" --app="$URL" --user-data-dir="$CARPETA/navegador" >/dev/null 2>&1 & return; }
            done; xdg-open "$URL" >/dev/null 2>&1 ;;
  esac
}
abrir
