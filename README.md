# M-Jarvis

Asistente de Marvel para la feria científica: corre en una Dell Latitude 5590 (Xubuntu), con el modelo local `gemma3:4b` (Ollama) y, cuando hay internet, una nube gratis (Groq) como apoyo. Chat con voz y oído, mapa de conocimiento y una consola de control, todo en una sola interfaz web.

**Cómo se arranca:** en la Latitude es el servicio `mjarvis-web` (`systemctl --user restart mjarvis-web`), en el puerto 8080. La pantalla del público abre `/?vista=chat`; la consola, `/#control` (pide la clave de gestión).

**Cómo se compila:** no se compila. Se edita aquí y se envía a la Latitude: `windows\probar.cmd` → `windows\desplegar.cmd -y` → `windows\humo.cmd` (en Linux, `linux/probar.sh` y `linux/desplegar.sh -y`).

Más: `CLAUDE.md` (mapa y reglas), `NOTAS.md` (todo lo decidido, por fecha), `windows/LEEME.md` y `docs/EMPEZAR.md`.
