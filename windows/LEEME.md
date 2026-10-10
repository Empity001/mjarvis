# Flujo de M-Jarvis en Windows

Es el mismo de Linux (`linux/*.sh`), pero en PowerShell y sin `rsync`: cada archivo se compara por su huella (SHA1) con la
Latitude y solo se manda lo que cambió, con `tar` por SSH. Nunca borra nada allá. Todo se lanza con los `.cmd` (no hace falta
tocar la política de scripts de PowerShell).

| Para… | Comando (desde la raíz del proyecto) |
|---|---|
| Dejar listo el equipo (una vez) | `windows\instalar.cmd` |
| Probar los cambios en la Latitude sin tocar el servicio | `windows\probar.cmd` (`-v` para el detalle de cada fallo) |
| Ver qué se enviaría | `windows\desplegar.cmd` |
| Enviar y reiniciar si hace falta | `windows\desplegar.cmd -y` |
| Prueba de humo con navegador (Edge) | `windows\humo.cmd` |
| Abrir o cerrar el túnel a mano | `windows\tunel.cmd` / `windows\tunel.cmd -Cerrar` |

Orden de siempre: `probar` → `desplegar -y` → `humo`. Correr `humo` siempre que se toque `index.html`, `shell.js` o `control.js`.

## Cosas propias de Windows

- **El nombre `ferr-latitude-5590.local` falla a ratos en Windows** (mDNS) y además resuelve a direcciones IPv6 que no responden.
  `~/.ssh/config` fuerza IPv4 (`AddressFamily inet`) y los scripts recuerdan la última dirección buena en
  `%LOCALAPPDATA%\mjarvis\ip-latitude.txt`; si no responde, buscan entre los vecinos de la red y prueban las direcciones fijas
  de M-Jarvis (`10.42.0.1`, `10.44.0.1`, `10.43.0.218`). Siempre comprueban la huella guardada del host (`HostKeyAlias`).
- Cada conexión SSH tarda 1-3 s: los scripts hacen pocas (por eso simular un despliegue tarda ~5 s).
- Playwright vive en `%USERPROFILE%\mjarvis-tools` (fuera de OneDrive) y usa el Edge instalado: no descarga ningún navegador.
- `desplegar` trae antes `personalidad.json` y `reacciones.json` de la Latitude si allá son más nuevos (lo aprobado en Control),
  guardando antes una copia en `comportamiento\_respaldos`.
- Además de `m-jarvis.sh`, `desplegar` envía `wifi-propia.sh` (el script de Linux no lo hacía, y su corrección nunca llegó).
- El túnel se cierra solo por su PID exacto y solo si es un `ssh`.
