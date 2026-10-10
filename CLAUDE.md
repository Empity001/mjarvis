# M-Jarvis: mapa y reglas

Vive en `C:\Users\srelm\Proyectos\M-Jarvis\M-Jarvis` (guía de la carpeta: `Proyectos\ORDEN.md`). Nunca dentro de OneDrive.

## Mapa
- `servidor/` servidor Python (solo librería estándar): `servidor.py`, `nube.py` (nube gratis), `red.py` (cerebro de red y portal), `voz.py`, `recetas.py`, `autoentreno.py`. `pruebas_rutas.py` son las pruebas.
- `web/` interfaz única: `index.html` (chat y bola), `shell.js` (barra y láminas), `control.js` (consola), `vidrio.css` (diseño), `grafo/` (mapa de neuronas). `panel.html`, `manager.html` y `conectar.html` solo redirigen.
- `comportamiento/` personalidad, reacciones, rúbrica y escenarios. `conocimiento/` y `documentos/` son las notas y sus PDF.
- `windows/` y `linux/` el flujo de trabajo; `latitude/` lo que se instala en la Latitude; `bench/humo.js` prueba de humo con navegador; `docs/` guías.

## Flujo (siempre en este orden)
`probar` (corre en la Latitude, no toca el servicio) → `desplegar -y` (reinicia el servicio si cambió el servidor) → `humo`.
Correr `humo` cada vez que se toque `index.html`, `shell.js` o `control.js`: `probar` no ejecuta el JavaScript de las pantallas.

## Reglas
- Esta PC no es fuente de IA ni de datos: el cerebro corre en la Latitude (modelo local + nube gratis). Aquí solo se edita, se prueba y se despliega.
- Secretos fuera del repo: la clave de Groq vive en `~/.config/mjarvis/nube.json` de la Latitude; la clave de gestión, en `~/mjarvis/clave.txt`.
- Lo que la Latitude genera al funcionar (bitácora, lo aprendido, propuestas) vive allá. `desplegar` nunca lo pisa y trae antes `personalidad.json` y `reacciones.json` si allá son más nuevos.
- Las pruebas de `probar` corren EN la Latitude: nada que toque NetworkManager (`red._nm`) sin parchear, o enciende de verdad su Wi-Fi propia.
- La pantalla del público (`?vista=chat`, `?vista=todo`) no lleva barra ni láminas ni fondo animado: en la Latitude, sin tarjeta gráfica, el fondo cuesta ~35 % de CPU.
- Control se oculta a los visitantes y pide la clave. Las animaciones son de `transform` y `opacity`, con salida exponencial y alternativa para "reducir movimiento"; los avisos del detector de diseño que se silencian quedan con su motivo en `.impeccable/config.json`.
- Nunca cerrar procesos por su proceso padre ni por nombre: por su PID exacto, tras comprobar qué es.
- Los nombres de archivo con acentos se estropean al copiar entre sistemas (`Capit├ín Am├⌐rica.md`): si git ve notas "borradas", mirar primero si solo cambió el nombre.
