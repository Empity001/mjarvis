# M-Jarvis — notas de trabajo

Fuente: [docs/diseno-original.md](docs/diseno-original.md) (documento de diseño exportado, 2026-09-30).
Las evaluaciones de abajo salen de conocimiento previo, **no de pruebas en la laptop**. Lo marcado "medir" hay que comprobarlo en el equipo real.

## 1. Qué es

Proyecto de grado: asistente tipo Jarvis, 100 % local y gratis, en una Dell Latitude 5590 (16 GB, SSD, sin GPU útil) con Linux.
Responde desde PDFs/fotos propios (RAG), muestra la página fuente con efecto "detective", tiene personalidad de mayordomo, emociones en un orbe HUD, voz y (opcional) oído.

## 2. Lo útil (se queda tal cual)

- **RAG, no fine-tuning.** Correcto para este hardware.
- **Filtro por capas sin depender del modelo**: normalización + lista, banco de frases con embeddings, bitácora que alimenta el banco.
- **Regaños fijos escritos a mano**, elegidos al azar. Cero sorpresas ante el jurado.
- **"La broma va en la forma, nunca en el dato."** Regla de oro.
- **Etiqueta de origen en pantalla** (documentos vs. conocimiento general).
- **Efecto detective = página renderizada una vez + cámara con `transform`**, no video. Coordenadas por palabra con PyMuPDF `get_text("words")`.
- **Palabras a resaltar por reglas** (números, mayúsculas, coincidencias), no por el modelo. Máx. 3–4 por respuesta.
- **Hablar por frases** (streaming a la voz) y sincronizar resaltados por frase.
- **Animar solo `transform` y `opacity`**, sin blur ni sombras grandes.
- **Cachear preguntas típicas, calentar el modelo, cargador conectado, clonar el disco.**
- **Orden de construcción por etapas demostrables** (sección 15 del original).
- Paquete WebSocket `texto / emocion / fuente / medios[timeline]` como contrato backend ↔ interfaz.

## 3. Evaluación: huecos y riesgos

### Críticos (cambian el diseño)

1. **El cuello de botella es leer el contexto, no escribir la respuesta.**
   El documento solo estima palabras/s de salida. En CPU, cada pregunta RAG obliga al modelo a procesar primero el prompt (personalidad + fragmentos); con ~1000 tokens de contexto eso puede ser 20–40 s de silencio antes de la primera palabra. Medir.
   Mitigación: 2–3 fragmentos cortos (150–250 tokens), prompt fijo al inicio para que quede en caché, `keep_alive` permanente, frase de relleno inmediata ("Un momento, señor…") con el orbe en "pensando".

2. **La capa 4 del filtro choca con el conocimiento general.**
   "Si no se parece a los documentos → rechazo" bloquea también "¿cuántas calorías tiene una manzana?". Hace falta una regla explícita de desempate. Propuesta: similitud alta → `CONSULTA_PROYECTO`; baja → pasa por filtro de inapropiadas y lista de "no puedo saberlo" (hoy, clima, precio, noticias); lo que sobreviva → `CONOCIMIENTO_GENERAL`.

3. **El modelo de embeddings sugerido corta a 128 tokens.**
   `paraphrase-multilingual-MiniLM-L12-v2` trunca el texto largo, así que fragmentos normales de RAG quedan a medio indexar. Usar `multilingual-e5-small` (512 tokens, requiere prefijos `query:` / `passage:`) o fragmentos muy cortos.

4. **Streaming vs. línea de tiempo por carácter.**
   `en_caracter` exige conocer la respuesta completa, pero el texto llega en streaming. Resolver por frase: al cerrar cada frase se calculan sus resaltados y se envían como evento aparte.

### Importantes

5. **El modelo de 7B no sirve para demo con voz** (lento al leer contexto y al escribir). Comparar solo modelos de 3–4B: Llama 3.2 3B, Qwen2.5 3B, Gemma 3 4B, Qwen3 4B (con el modo "thinking" apagado). Medir con las mismas 10 preguntas en español.
6. **Oído en una sala con público**: ruido, eco y Jarvis oyéndose a sí mismo. Silenciar el micrófono mientras habla y tener **botón de pulsar-para-hablar + teclado** como respaldo. La palabra de activación "hey jarvis" de openWakeWord está entrenada con pronunciación inglesa.
7. **Vosk con acento dominicano** probablemente falle bastante; faster-whisper `base`/`small` en int8 es mejor candidato. Medir.
8. **GraphRAG con un modelo de 3B**: la extracción de conceptos sale pobre y tarda. Si se quiere el grafo por lo visual, armarlo por co-ocurrencia de términos clave o a mano, sin LLM.
9. **Carpeta en red (SMB)** añade configuración y un punto de fallo. Una página de subida en la misma interfaz web cumple "incluir archivos desde la red local" con menos riesgo.
10. **Audio en Chromium kiosco**: sin gesto del usuario el navegador bloquea el sonido. Lanzar con `--autoplay-policy=no-user-gesture-required` o reproducir el audio desde el backend.
11. **El prompt del clasificador del original tiene 3 etiquetas**; el diseño final usa 4. Reescribirlo, o mejor no usar LLM para clasificar (ver punto 2).
12. **Emoción por etiqueta `[divertido]` emitida por el modelo**: los modelos pequeños la olvidan o la inventan. Derivar la emoción de la ruta (etiqueta + resultado de búsqueda) y dejar esto como extra.

### Datos ⚠️ del original, revisados

| Dato | Estado |
|---|---|
| Latitude 5590 = 2018, Intel 8.ª gen, 4 núcleos, UHD 620, MX130 opcional | Coincide con lo que sé. Hay variantes con i3/i5 de 7.ª gen (2 núcleos): confirmar el procesador exacto del equipo. |
| Piper tiene voces en español | Sí: es_ES (davefx, sharvard, carlfm), es_MX (ald, claude), es_AR. No hay dominicana. El repo original quedó archivado; el desarrollo sigue en `OHF-Voice/piper1-gpl` (licencia GPL). |
| Edge-TTS con voces es-DO | Sí existían: `es-DO-EmilioNeural` y `es-DO-RamonaNeural`. Requiere internet y no es oficial; confirmar que sigue vivo. |
| Kokoro "más pesada" | Corre en CPU, pero su español es limitado (pocas voces). Probar antes de contar con ella. |
| 3B ≈ 5–10 palabras/s, 7B ≈ 2–3 | Orden de magnitud razonable para la salida. Falta el tiempo de lectura del prompt (punto 1). Medir. |
| Qwen2.5 3B | Licencia de investigación (no comercial). Para un proyecto de grado no estorba. |

## 4. Decisiones tomadas (2026-09-30)

- **Nombre**: M-Jarvis.
- **Tema**: universo Marvel + los proyectos del taller (alas, guantelete de Thanos impreso en 3D, escudo del Capitán América…). Cada proyecto tendrá su documento con todo el proceso; Jarvis lo explica.
- **Evento**: feria científica, febrero–marzo de 2027. Área ruidosa, el jurado y el público preguntan libremente, se puede poner internet.
- **PDFs**: 100 % digitales. Sin OCR.
- **Laptop**: i5 de 8.ª gen (modelo exacto se lee por SSH), **8 GB de RAM** (un módulo murió; se intentará conseguir otro), pantalla dañada, sin Linux todavía (hay USB de instalación).
- **Entrada**: micrófono opcional (teléfono como micrófono con WO Mic, o micrófono externo); teclado siempre disponible. Escriba o hable, la respuesta sale con voz.
- **Tono**: británico clásico.
- **Visual** (orbe o cara, lado de los medios): se decide al final.
- **Trabajo**: se construye en conjunto. Laptop en la red de la casa y Claude trabaja en ella por SSH desde esta PC.
- **Distro**: Xubuntu 26.04.1 LTS (es la que se descargó el 2026-10-01; LTS vigente, sirve igual que la 24.04) (base Ubuntu, escritorio XFCE liviano; con 8 GB cada 800 MB cuentan).

### Laptop real, leída por SSH (2026-10-01)

- Xubuntu 26.04.1, kernel 7.0, sesión X11 con lightdm. IP `192.168.88.10`, usuario `ferr`.
- CPU: i5-8250U, pero el sistema solo ve **3 núcleos / 6 hilos** (debería ser 4 / 8). Revisar en el BIOS (F2) "Multi Core Support" = All; si ya está en All, un núcleo está fallando.
- RAM: 7.6 GB útiles. Ranura A vacía/no detectada; ranura B con un Micron de 8 GB DDR4 a 2133 MT/s (pieza `16ATF1G64HZ-2G1A2`). Canal simple.
- Gráficos: solo Intel UHD 620 (sin MX130). Disco: 233 GB, 210 libres. Reposo: ~1.1 GB de RAM usados, ~40 °C.
- Acceso: `ssh mjarvis` (llave dedicada, sudo sin contraseña). Escritorio remoto: x11vnc + noVNC como servicios de usuario, solo en localhost de la laptop; se abre con [escritorio-laptop.bat](escritorio-laptop.bat) (túnel SSH → `http://localhost:6080`).
- Inicio de sesión automático activado (`/etc/lightdm/lightdm.conf.d/50-autologin.conf`). Suspensión e hibernación desactivadas; cerrar la tapa no la duerme (`/etc/systemd/logind.conf.d/mjarvis.conf`).
- Ollama 0.35.0 instalado como servicio (arranca solo). El dueño dio control total de la laptop a Claude.

### Velocidades medidas (2026-10-01, 3 núcleos, canal simple)

Prueba: [bench/bench.py](bench/bench.py), resultados en [bench/resultado-2026-10-01.txt](bench/resultado-2026-10-01.txt). Prompt de Jarvis + contexto + pregunta, 4 preguntas por modelo.

| Modelo | 1.ª palabra, contexto corto (~260 tok) | 1.ª palabra, contexto largo (~570 tok) | Escribe | Datos correctos | RAM total usada |
|---|---|---|---|---|---|
| Llama 3.2 3B | 5.0 s | 13.9 s | 6.5 tok/s | 2 de 4 (inventó pesos y tiempos) | 4.0 GB |
| Qwen2.5 3B | 5.2 s | 15–17 s | 7.2 tok/s | 3 de 4, seco, sin personalidad | 3.5 GB |
| Gemma 3 4B | 7.7 s | 19 s | 5.5 tok/s | 4 de 4, mejor tono; soltó una palabra basura ("puluhún") | 5.2 GB |

- Lee a 30–50 tok/s y escribe a 5–7 tok/s (unas 4–5 palabras por segundo). Primera carga del modelo: 5–12 s extra. Temperatura máxima 67 °C.
- **Consecuencias de diseño**: el contexto que se le pasa al modelo debe quedar en ~250 tokens (1–2 fragmentos cortos) para responder en ~5 s; los números se muestran desde el documento (efecto detective), no se confían al modelo; hace falta frase de relleno inmediata.
- Candidato actual: **Gemma 3 4B** por exactitud y tono; Qwen2.5 3B como alternativa rápida. Repetir la medida si se recupera el cuarto núcleo o el segundo módulo de RAM.

### Mapa de conocimiento (2026-10-01)

- **La base de conocimiento es una carpeta de notas** en formato Obsidian: [conocimiento/](conocimiento/). Una nota = un concepto corto (30–70 palabras); cada `[[enlace]]` = una conexión. Se puede abrir y editar con Obsidian.
- Estado: 68 notas, 161 conexiones, 8 temas. `conocimiento/marvel/` (56, Universo Cinematográfico, escritas por Claude) y `conocimiento/taller/` (12, **datos de ejemplo inventados**, marcados `ejemplo: true`; hay que sustituirlos por los reales).
- [grafo/build.py](grafo/build.py) convierte las notas en `graph.json` y detecta los temas (comunidades por modularidad). [grafo/sembrar.py](grafo/sembrar.py) solo sirvió para crear las notas iniciales; no pisa notas existentes.
- Visor estilo InfraNodus en [web/grafo/index.html](web/grafo/index.html): temas por color, líneas curvas, panel de temas y conceptos influyentes, búsqueda. Sin librerías externas (funciona sin internet). Queda quieto cuando termina de acomodarse, así que no gasta CPU. Expone `window.iluminar([ids])` para encender nodos cuando Jarvis responda.
- Servido en la laptop: `http://192.168.88.10:8080/grafo/` (servicio de usuario `mjarvis-web`, ~23 MB de RAM). Alojarlo en internet no ahorra RAM: la memoria la gasta el navegador que lo dibuja, no el servidor.
- **Por qué acelera**: el modelo recibe solo la nota encontrada más una línea de sus vecinas (~150–250 tokens), justo el tamaño que da ~5 s de espera. El trabajo pesado (resumir y enlazar) se hace antes, una sola vez.
- PDF de prueba: [documentos/marvel-basico.pdf](documentos/marvel-basico.pdf), 7 páginas, generado desde las notas de Marvel con [grafo/notas_a_pdf.py](grafo/notas_a_pdf.py). Ojo al ingerir: el texto extraído trae ligaduras ("ﬁ"); normalizar con NFKC.
- En la laptop: todo en `~/mjarvis/`, con entorno Python en `~/mjarvis/venv` (PyMuPDF 1.28).

### M-Jarvis v0 funcionando (2026-10-01)

- [servidor/servidor.py](servidor/servidor.py) (solo biblioteca estándar): sirve `web/`, busca en las notas y le pide la respuesta a Gemma 3 4B por Ollama, en streaming. Servicio de usuario `mjarvis-web`, puerto 8080; arranca solo con la laptop y precarga el modelo.
- Interfaz en [web/index.html](web/index.html): mapa a la izquierda, conversación a la derecha, indicador de estado, etiqueta de origen ("De mis archivos: …" o "Conocimiento general") y tiempo de cada respuesta. Al responder enciende en el mapa las notas usadas y las mencionadas.
- En la laptop se abre a pantalla completa con Firefox en modo kiosco (unidad `mjarvis-pantalla`; se cierra con Alt+F4). Desde otra PC de la red: `http://192.168.88.10:8080/`.
- Búsqueda actual: por palabras (BM25 + peso al título), sin modelo de embeddings para ahorrar RAM. Acierta cuando la pregunta nombra el concepto; falla con sinónimos o verbos conjugados ("¿cuánto costó todo?" no encuentra Presupuesto). Si nada supera el umbral, responde de conocimiento general.
- Medido: ~7 s a la primera palabra con el modelo caliente, 13 s en total para dos frases; 4.9 GB de RAM usados con modelo + Firefox.
- Cada pregunta queda en `~/mjarvis/bitacora.jsonl` (pregunta, ruta, notas, tiempos, respuesta).
- **Falta**: filtro de inapropiadas y regaños fijos, búsqueda por significado, voz, efecto detective con el PDF, emociones/orbe, arranque automático del kiosco, datos reales del taller.

### Añadido el mismo día (trato, memoria, zoom)

- **Trato básico sin modelo** (`TRATO` en el servidor): saludos, cómo estás, gracias, despedidas, quién eres, qué puedes hacer, quién te creó, hora y fecha. Frases fijas al azar, respuesta instantánea, tolera erratas en mensajes cortos ("Hols4" → saludo). Las frases se editan en `servidor.py`.
- **Memoria de conversación**: se reenvían los turnos anteriores al modelo (tope 6000 caracteres; al pasarse conserva solo el último) y se olvida tras 5 min sin hablar o al recargar la página. Un mensaje que no nombra nada nuevo ("háblame de ellas", "¿y de dónde es?", "sí") sigue el tema anterior: si es abierto trae notas vecinas, si pregunta algo concreto trae solo las vecinas afines o ninguna.
- **Un solo mensaje de sistema** para todas las rutas, para que el modelo reutilice lo ya leído: los seguimientos salen en ~3 s a la primera palabra; un tema nuevo, 5–10 s.
- **Tope de 3 frases** aplicado por el servidor (corta la generación), porque Gemma ignora el límite pedido y se alargaba a 30–40 s.
- **Fuga de memoria resuelta**: el servidor del modelo guardaba hasta 32 puntos de control de contexto (~116 MB c/u) y llegó a 7,2 GB con swap. Limitado en `/etc/systemd/system/ollama.service.d/mjarvis.conf` (`LLAMA_ARG_CTX_CHECKPOINTS=3`, `LLAMA_ARG_CACHE_RAM=256`, un solo modelo y una sola petición a la vez). Ahora ~5,1–5,5 GB usados en total con Firefox abierto.
- **Zoom del mapa**: botones −, + y "Ver todo"; teclas + y − (con el campo de texto vacío) y 0; rueda del ratón; y órdenes a Jarvis ("acerca el mapa", "zoom out", "ver todo").
- [servidor/probar.py](servidor/probar.py) manda una conversación de prueba y muestra tiempos.
- Límites vistos: al pedir "¿qué más sabes de él?" Gemma mezcló datos de notas vecinas (dijo que Thanos "intentó robar" el guantelete). El primer mensaje tras reiniciar el servicio tarda ~10 s.

### Segunda tanda del 2026-10-01 (decisiones del dueño)

- **Trato neutro**: Jarvis no llama a nadie «señor/señora» ni usa «usted» como vocativo (pregunta gente de cualquier género). Va en el mensaje de sistema y además un filtro (`TRATAMIENTO`) lo quita del texto si al modelo se le escapa. Las frases fijas ya no llevan tratamiento.
- **Jarvis vive en "el sistema del taller"**, una red; nunca dice que está en una laptop o computadora.
- **Frases mientras piensa** (`PENSANDO` en `web/index.html`): rotan cada ~3 s hasta la primera palabra; usan el nombre de la nota encontrada ("Veamos qué tengo sobre Thanos…").
- **Mapa "pensando de verdad"**: nada de impulsos al azar. Destello breve en las notas que la búsqueda consideró; las elegidas se encienden; sus vecinas reales quedan a media luz y los impulsos recorren solo esas relaciones; mientras responde se enciende cada nota que la respuesta nombra. Si la pregunta no toca ninguna nota, el mapa no se mueve. Base del mapa cacheada en una capa y animación a 30 cuadros/s.
- **El mapa sigue la conversación solo**, por un canal en vivo del servidor (`/api/eventos`, Server-Sent Events). Por eso puede ir en otra pantalla: `http://192.168.88.10:8080/grafo/` muestra el mapa con subtítulos de pregunta y respuesta, y `/?vista=chat` deja solo la conversación.
- **Dos pantallas**: Latitude con solo chat; segundo monitor de esta PC con el mapa, abierto con [segunda-pantalla.bat](segunda-pantalla.bat) (Edge a pantalla completa en x=1920). No es un monitor extendido por VNC: es la misma página servida por la laptop, dibujada por esta PC (le quita trabajo a la laptop).
- **Accesos directos en el escritorio de la Latitude**: "M-Jarvis" (chat + mapa) y "M-Jarvis (solo chat)".
- **Memoria mejorada**: tope 9000 caracteres y contexto 4096; errata `antes → ant` corregida (activaba Ant-Man); nombres pegados o con erratas ("ironman", "vibranio", "tanos") encuentran su nota; si el mensaje no *nombra* una nota se sigue el tema anterior; preguntas sobre la propia charla ("¿qué te pregunté primero?", "repite lo último") reciben el registro exacto de la conversación.

### Apagón del 2026-10-01 a las 14:03 y blindaje

- El registro del arranque anterior se corta en seco a las 14:03:49, sin secuencia de apagado ni error del núcleo: fue un corte brusco (botón mantenido, corriente o protección térmica), no una decisión de Linux. Causa exacta desconocida.
- Hallazgos: la pantalla se ponía en negro a los 15 min y se bloqueaba (parecía apagada); y **bajo carga el procesador llega a 87–92 °C** (el "67 °C máximo" anotado antes estaba mal: se midió al terminar la carga, y enfría en segundos). El ventilador sí funciona (0 RPM en reposo, ~2600–3000 bajo carga).
- Medido con Gemma 3 4B: sin tope 87–92 °C; **tope de potencia al 80 % → misma velocidad (26 tok/s leyendo, 5,5 escribiendo) y 74 °C máximo**; al 65 % → 21 tok/s y 64 °C; turbo apagado → 14,5 tok/s y 62 °C. Queda fijo el 80 % en `/etc/tmpfiles.d/mjarvis.conf` (`intel_pstate/max_perf_pct`).
- Blindaje aplicado (solo enchufada): pantalla nunca se apaga ni se bloquea (xfce4-power-manager en modo presentación, DPMS y salvapantallas fuera, `xset` al iniciar sesión), suspensión e hibernación enmascaradas, tapa y botón de encendido ignorados en `logind` y en XFCE (pulsación corta no hace nada; mantenerlo 4 s sigue apagando, eso es del hardware).
- Recuperación sola: servidor y Ollama arrancan con el equipo, sesión automática, y `~/.config/autostart/mjarvis-pantalla.desktop` abre el kiosco (solo chat) cuando el servidor responde.
- `~/mjarvis/salud.log`: una línea por minuto con temperatura, carga, memoria libre, si está enchufada y batería (timer de usuario `mjarvis-salud`). Si vuelve a apagarse, las últimas líneas dicen qué pasaba.
- Pendiente del dueño en el BIOS (F2): "AC Recovery → Power On" para que encienda sola al volver la corriente, y "Multi Core Support → All" por el núcleo que falta. Limpiar las rejillas del ventilador ayudaría.

### Tercera tanda del 2026-10-01: comportamiento e ingesta (desplegada y probada a las 14:26–14:53)

Probado con la batería de 33 mensajes ([servidor/bateria.txt](servidor/bateria.txt)) y con un PDF, un texto sin títulos y una imagen de prueba (ya borrados). El servicio `mjarvis-web` corre ahora con `venv/bin/python` (la ingesta necesita PyMuPDF). Describir una imagen suelta le toma ~66 s a Gemma. Fallos vistos: "¿quién mató a Thanos?" respondió mal (la nota de Thanos no lo dice y la búsqueda no trajo la de la batalla final); algunas respuestas salen con tres frases muy largas (30 s).

- **Decisiones del dueño**: de momento Jarvis solo sabe de Marvel (se borraron las notas de ejemplo del taller y `sembrar.py`); puede contar el estado real del equipo pero con estética de "sistema" (porcentajes y núcleo, nunca "laptop"; la cifra total de memoria es "clasificada"); ante groserías y rarezas responde jocoso.
- [comportamiento/reacciones.json](comportamiento/reacciones.json): reacciones fijas por categoría (cuidado, odio, peligro, sexual, insulto, pulla, provocación, coqueteo, chiste, canto, fuera de alcance), interjecciones leves ("coño", "diablo": no bloquean, solo comentario) y rarezas (risa, teclazos, vacío). Editable sin reiniciar. "cuidado" (autolesión) responde en serio y remite al 911; "odio" responde firme sin chiste.
- [comportamiento/jerga.json](comportamiento/jerga.json): ~150 términos dominicanos con significado, que se le pasan al modelo cuando aparecen en la pregunta, y la lista de apelativos (manito, loco, pana…).
- [servidor/criterio.py](servidor/criterio.py): normaliza disfraces ("p3nd3jo", "p*ta", "puuuta", "p.u.t.a"), aplica las reacciones, saca la glosa de jerga y lee temperatura, memoria, disco, carga, batería y tiempo encendido.
- Orden de decisión en el servidor: orden de mapa → inadmisible → interjección → estado del sistema → trato básico (con saludos dominicanos) → búsqueda en notas → reacciones suaves (solo si la pregunta no nombra una nota: "¿Hulk es bruto?" pasa) → erratas de trato → seguimiento → rarezas → modelo.
- **Ingesta** ([servidor/ingesta.py](servidor/ingesta.py)): PDF, .docx, .txt/.md e imágenes. Parte por títulos (tamaño de letra o negrita); sin títulos, trocea y le pide un título al modelo. Guarda el texto original (no resume, para no tocar cifras), la página y las imágenes de cada sección en `web/medios/`. Las imágenes sueltas las describe Gemma (es multimodal). Las conexiones salen solas: `grafo/build.py` ahora une notas que se nombran entre sí.
- Se sube desde cualquier equipo de la red en `http://192.168.88.10:8080/subir.html` (arrastrar y soltar; muestra el progreso y recarga el mapa al terminar). Los originales quedan en `documentos/`.
- Sin probar todavía: detección de títulos con PDFs reales del taller (solo se probó con uno generado), Word (.docx) e imágenes fotográficas.

### Dónde vive cada cosa

- **Todo corre en la laptop**: modelo (Ollama, `/usr/share/ollama/.ollama/models`), servidor, búsqueda, filtro, ingesta. Carpeta `~/mjarvis/`: `servidor/`, `web/`, `grafo/`, `comportamiento/`, `conocimiento/`, `documentos/` (originales subidos), `web/medios/` (imágenes extraídas), `bitacora.jsonl`, `salud.log`, `venv/`.
- **Esta PC** guarda la copia fuente del proyecto (esta carpeta, dentro de OneDrive) y solo hace de visor (segundo monitor) y de puesto de trabajo por SSH. Aquí no corre nada.
- **Nube: nada.** No hace falta internet para funcionar.
- **Cuidado al desplegar**: los documentos que el dueño suba por `/subir.html` existen solo en la laptop. No volver a hacer `rm -rf ~/mjarvis/conocimiento` antes de copiar: copiar solo `conocimiento/marvel` (o traer primero las carpetas nuevas a esta PC).
- Nombre en red local: `http://ferr-latitude-5590.local:8080/` (avahi activo), útil cuando la IP cambie en otra red.
- PDF de prueba nuevo: [documentos/marvel-fases-y-multiverso.pdf](documentos/marvel-fases-y-multiverso.pdf) (7 páginas, 6 figuras propias). En ensayo, la ingesta lo parte en 34 secciones con cada imagen en la suya. Aún no está subido a Jarvis: lo sube el dueño para probar la herramienta.
- Para llevarlo al taller falta: probar un arranque sin Wi-Fi, y un modo que ponga el mapa en un monitor conectado por HDMI (hoy el mapa en segunda pantalla depende de otra máquina en la misma red).

### Una sola aplicación, dos protocolos (2026-10-01, tarde)

- **Protocolo local (en la Latitude)**: icono "M-Jarvis" del escritorio → [latitude/m-jarvis.sh](latitude/m-jarvis.sh) (en la laptop: `~/mjarvis/m-jarvis.sh`), menú con zenity: Todo junto, Solo chat, Solo red neuronal, Panel, Compartir (direcciones y clave), Cerrar pantalla. Abre cada vista en Firefox a pantalla completa; al cerrarla con Alt+F4 vuelve el menú. Arranca solo con el equipo en "Solo chat". Una sola copia a la vez (flock).
- **Protocolo compartido (otro equipo)**: [M-Jarvis.bat](M-Jarvis.bat) (acceso directo en el escritorio de esta PC). Busca la Latitude por dirección guardada, por nombre (`ferr-latitude-5590.local`) o por la IP de casa; si no la halla, pregunta la dirección. Menú: panel, chat, red neuronal, todo junto, red neuronal en el segundo monitor (lo detecta solo), escritorio remoto (solo donde está la llave SSH). No instala nada: la Latitude lo sirve todo, incluido el propio lanzador (`/descargas/M-Jarvis.bat`, enlace en el panel).
- **Panel** ([web/panel.html](web/panel.html)): abrir vistas, estado del sistema en vivo, red neuronal en vivo con lo que se pregunta, archivos (ver notas e imágenes, bajar el original, subir, borrar lo subido) y últimas preguntas. Indica si está en protocolo local o compartido.
- **Clave de gestión**: subir y borrar desde otro equipo pide una clave de 6 dígitos (`~/mjarvis/clave.txt`, se genera sola; vaciar el archivo la desactiva). Desde la propia Latitude no se pide. Se ve en el menú local → Compartir. Ver, chatear y mirar el mapa no piden clave. Motivo: en una feria con Wi-Fi compartido cualquiera podría borrar el conocimiento.
- Servicios nuevos del servidor: `/api/estado`, `/api/notas`, `/api/borrar`, `/api/bitacora`, `/api/clave` (solo local), `/api/detener`, `/originales/<archivo>`.
- **Cable directo**: perfil de red `mjarvis-cable` en la Latitude (Ethernet con dirección automática de enlace local). Con un cable de red entre las dos máquinas debería bastar el nombre `.local`; **sin probar** con cable real. Windows tarda cerca de un minuto en asignarse dirección.
- **Respuestas claras y a medida**: mensaje de sistema corto con reglas; cada pregunta lleva una línea «Extensión» según su tipo (`medida()`): dato → 1 frase (~10–14 s), normal → 2 frases (~23–28 s), explicar/háblame → 3–4 frases (~30–40 s). Temperatura 0,25. Siglas ("AVT") y palabras raras del texto ya encuentran su nota. Sigue inventando algún detalle de vez en cuando.
- **Detener**: botón aparte (y tecla Esc); corta también mientras piensa (2 s en la prueba). **Cola**: las preguntas que llegan mientras responde esperan turno (hasta 6) y se contestan en orden; antes respondía "estoy ocupado".
- El dueño ya subió por su cuenta 01-iron-man, 02-el-increible-hulk, 03-iron-man-2, 04-thor, 06-los-vengadores y personalidad-m-jarvis (229 notas en total). Esos documentos viven solo en la Latitude.

### Fichas de películas, aprendizaje y red de trato (2026-10-01, última tanda)

- **Encargo grande del dueño** (hecho a medias por otro chat de Claude): una ficha detallada por cada título del universo Marvel, 70 en total (36 de la Saga del Infinito incluidas las series de Netflix, 32 de la Saga del Multiverso, 2 finales sin estrenar). El otro chat dejó 01–06. Aquí se hicieron **07–13** con [fichas/generar.py](fichas/generar.py) a partir de [fichas/datos/](fichas/datos/) (un .json por título, mismo formato: ficha, actos, personajes, cosas, poscréditos, conexiones, preguntas, curiosidades, dos figuras). PDFs en [documentos/fichas/](documentos/fichas/) y unidos en `documentos/M-Jarvis - Universo Marvel (maestro).pdf` (73 páginas). **Faltan 14 en adelante (57 títulos).** Numeración: la de la lista del dueño (orden cronológico). Títulos posteriores a junio de 2026 o sin estrenar hay que investigarlos en la web o marcarlos como sin datos.
- A Jarvis se le dan las fichas sueltas, **no el maestro** (duplicaba todo: se retiró). Conocimiento actual: 617 notas.
- El documento de personalidad que subió el dueño estaba sirviendo de "dato" y provocaba regaños sin motivo: movido a `conocimiento/_personalidad-m-jarvis` (las carpetas con `_` no entran al conocimiento ni al mapa).
- **Aprendizaje** (interruptor en el panel, apagado por defecto; estado en `comportamiento/aprendido.json`): con él encendido aprende respuestas ("cuando te digan X, responde Y"), correcciones ("eso no era ofensivo" → no vuelve a reaccionar a esa frase; solo categorías suaves) y datos ("aprende que…"), que quedan en `conocimiento/_por-aprobar/` hasta que el dueño los apruebe en el panel. Motivo de la aprobación: Gemma 4B no sirve de juez (o rechazaba datos ciertos o aceptaba "Thanos es el padre de Iron Man"). Nunca aprende nada con groserías.
- Apagado o encendido, ante "no te dije nada ofensivo" se disculpa y borra el regaño de su memoria; "¿por qué no respondiste lo de antes?" retoma la pregunta anterior; "huh?", "¿qué?", "no entiendo" ofrecen repetir (antes "huh" contaba como risa).
- **Red de trato**: segunda red dibujada a la derecha del mapa, sin conexión con la de conocimiento (`web/grafo/trato.json`, la genera el servidor): cortesía, límites, sistema y aprendizaje. Se enciende la regla que se usa en cada respuesta fija. No muestra groserías.
- Mapa con muchas notas: la repulsión ahora se calcula por celdas vecinas (8,6 ms por paso con 659 nodos, antes 19) y se asienta en ~6 s. Con las 70 fichas (~3000 notas) habrá que mostrar solo una parte.
- Si la respuesta se corta (reinicio del servidor), el chat ya no se queda en "Conectando los datos…": avisa y pide repetir.

### Efecto de quedar en 8 GB

- Capacidad: alcanza para modelo de 3–4B (≈2–3 GB) + embeddings + Piper + Chromium. Lo único que se pierde es el modelo de 7B, ya descartado.
- Velocidad: el golpe real es quedar con **un solo módulo (canal simple)**; la inferencia en CPU depende del ancho de banda de memoria y puede bajar un 30–40 %. Un segundo módulo importa por el doble canal, no por los gigas. Tipo: DDR4 SODIMM, igual al que queda.

### Decisión: 100 % local en la laptop vieja

- **Cerebro híbrido rechazado** (2026-09-30): toda nube tiene límite y el dueño no quiere depender de eso. Tampoco se usa la PC nueva como servidor; solo sirve de teclado para entrar por SSH.
- La velocidad se recupera con hardware: reasentar el módulo "muerto" y probarlo en la otra ranura; si de verdad murió, conseguir otro para volver a doble canal.
- La pantalla de la laptop volvió a dar imagen sola: instalar Linux y activar SSH cuanto antes, por si vuelve a fallar.
- Primer trabajo al entrar por SSH: medir tiempos reales (lectura de contexto y escritura) con modelos de 3–4B.

### Propuesta descartada: cerebro híbrido

- Lo pesado es el modelo de lenguaje; buscar en los documentos, la voz y la interfaz son livianos. Por eso la división útil es **información y búsqueda en la laptop, cerebro en la nube**. Al revés no ahorra nada.
- Cerebro en nube = API gratuita de un modelo grande (candidatos: Groq, Google AI Studio, Cerebras; revisar límites del plan gratis cuando toque). Respuesta en 1–2 s en vez de 20–40 s, y mucho menos invento en datos de Marvel.
- **Respaldo automático**: si no hay internet o la API falla, responde el modelo local de 3–4B con Ollama. Ambos hablan el mismo formato (API tipo OpenAI), así que es un solo código con dos destinos.
- Costos: depende del internet de la feria, los planes gratis tienen límite de peticiones y pueden cambiar, y el proyecto deja de ser "100 % local" (pasa a "local con acelerador en nube").

## 5. Por confirmar

### Siguen abiertas
- ¿Hay televisor o monitor con HDMI para instalar Linux? (sin eso no se puede empezar)
- ¿Qué distro tiene la USB ahora?
- ¿Se aprueba el cerebro híbrido?
- ¿Se consigue el segundo módulo de RAM?

### Lista original (ya respondida arriba, salvo lo visual)
1. Tema y cantidad de los documentos (¿cuántos PDFs, cuántas páginas?).
2. Fecha de entrega.
3. ¿PDFs digitales o escaneados?
4. Procesador exacto de la laptop y si ya tiene Linux instalado.
5. Formato de la presentación: ¿sala con jurado y ruido?, ¿pregunta el jurado libremente?, ¿hay proyector?, ¿hay internet?
6. ¿El oído (micrófono) es obligatorio o basta con teclado + voz de salida?
7. Tono: británico clásico o más dominicano.
8. Orbe abstracto o cara con expresiones.
9. Medios siempre por el mismo lado o según tipo.
10. Qué preguntas generales se esperan (¿vale la pena la mini base de datos?).
11. Distro: Ubuntu 24.04 LTS o Mint.
12. Reparto del trabajo: ¿Claude construye, o guía mientras el dueño construye? (el original dice lo segundo).
13. Dónde se desarrolla: ¿en este Windows y luego se pasa a la laptop, o directo en la laptop?

### Se resuelven midiendo en la laptop
- Tiempo hasta la primera palabra con contexto RAG real.
- Modelo ganador entre los de 3–4B.
- Voz de Piper elegida.
- Vosk vs. faster-whisper con acento dominicano.
- Temperatura y frenado por calor en una sesión de 20 minutos.
- Precisión de coordenadas palabra ↔ página con los PDFs reales.

## Tanda del 2026-10-01 (tarde-noche): fichas completas, mapa nuevo, respuestas al instante

**Conocimiento**
- Fichas 14-72 escritas (`fichas/datos/*.json`), generadas con `fichas/generar.py`, unidas con `fichas/unir.py` en `documentos/M-Jarvis - Universo Marvel (maestro).pdf` (72 fichas, 388 páginas, 6,7 MB; se divide solo si pasa de 60 MB) e ingeridas de golpe con `fichas/ingerir_todas.py` (sin modelo, 22 s). 71 y 72 son añadidos míos (Capitana Marvel, Moon Knight). 69 y 70 (Doomsday, Secret Wars) están marcadas como sin estrenar: sustituir cuando salgan. 60-68 se verificaron contra Wikipedia el 2026-10-01.
- `grafo/otros_universos.py`: 294 notas de personajes y franquicias que NO son de Marvel (DC, Star Wars, anime, Nintendo, Nickelodeon, Cartoon Network, Disney, Pixar...). Cada una dice quién es y que no pertenece a Marvel. Carpeta `conocimiento/otros-universos` (se regenera entera con el script).
- `grafo/datos_rapidos.py`: 81 preguntas con respuesta escrita (parentescos y nombres reales). Carpeta `conocimiento/datos-rapidos`.
- Total: 3.096 notas, 6.881 conexiones.

**Cerebro (servidor.py)**
- Tipos de pregunta (`TIPOS_PREGUNTA`, `medida`): muy amplia, hipotética, capciosa, comparación, opinión, lista, amplia, sí o no, dato, identidad. De cada tipo sale la indicación de extensión, el tope de frases y cuántas notas se consultan. Queda en la bitácora (`tipo`).
- Respuesta directa, sin modelo (`Indice.directa`, etiqueta `directa`): si la pregunta coincide con una pregunta frecuente ya escrita, o es «¿quién/qué es X?» y hay nota general corta de X, sale el texto de la nota en menos de 1 s. Es la mayor ganancia de velocidad y evita inventos del modelo.
- Película o serie entera (`Indice.titulo_entero`): «¿qué pasa en Endgame?» recibe los actos en orden, recortados.
- Preguntas sobre su propia red (`red_neuronal`): cuántas neuronas, la más conectada, con qué se conecta X, temas. Se responden con cifras reales y encienden el mapa.
- Otros universos colados en una pregunta de Marvel: la aclaración sale escrita de antemano («Una precisión antes de nada…») y el nombre ajeno se quita de lo que lee el modelo.
- Memoria: caduca a los 30 min (antes 5). Al llenarse no se olvida: se resume (pregunta + comienzo de la respuesta, 12 intercambios) y el modelo la relee en segundo plano (`repasar`). Preguntas sobre la charla («¿por qué lo mencionas?») reciben el registro de preguntas y respuestas.
- Búsqueda: el nombre de una nota ya no incluye la coletilla del documento; de cada nombre repetido entra solo la mejor; si la pregunta nombra a varios entra una nota de cada uno; las preguntas frecuentes genéricas de una ficha solo valen si se nombra su película.
- Filtros: muletillas iniciales («Entiendo su pregunta…»), títulos («Su Majestad»), y los vocativos solo se quitan cuando van como llamado (ya no rompe «El Señor de los Anillos» ni «Caballero de la Noche»). Las iniciales («J. R. R.») no cuentan como fin de frase.
- Órdenes de mapa nuevas: «forma de cerebro/esfera/dona/galaxia», «gira el mapa», «deja de girar», «mapa plano», «ponlo en 3D».

**Mapa (web/grafo/index.html)**
- Interfaz tipo InfraNodus: elegir nodos (varios), panel de notas, camino más corto entre dos, Solo esto / Ocultar / Limpiar (nada borra nada: es solo vista), buscador con resultados, barra de herramientas, panel de análisis.
- Formas 3D: cerebro, esfera, dona, galaxia. Puntos repartidos sin tocarse (`puntos`, distancia mínima) y dibujo ligero mientras se mueve (`apurado`).
- Cerebro como tejido: anatomía con lóbulos, cisura, surcos, cerebelo y tallo; solo se ven las fibras (cada conexión real es un axón curvo, `tender`), en haces por tema, cruzando por el cuerpo calloso; los impulsos viajan por la fibra.
- Nubes fuera del cerebro: trato (-1) y otros universos (-2).
- Plano: charcos rellenos a toda distancia.

**Medido en la Latitude**: `gemma3:4b` ya es Q4_K_M; swap de 4 GB ya activo; 3 núcleos de 4 visibles; un solo módulo de 8 GB a 2133 MT/s. Lo que más aceleraría: activar el cuarto núcleo en BIOS y poner un segundo módulo de RAM (doble canal).

**Red**: el acceso SSH (`ssh mjarvis`) apunta ahora a `ferr-latitude-5590.local`, no a una IP fija. El 2026-10-01 la casa cambió a la Wi-Fi 10.0.0.x.

**Pendiente**: nube «Taller» con su propia carga de archivos y desambiguación de menor a mayor; capa visual «cuerpo humano»; voz (STT/TTS); el modelo 4B aún adorna con inventos cuando redacta respuestas largas; «¿y es de Marvel?» tras un personaje ajeno responde bien pero empieza con «Sí».

## Tanda del 2026-10-01 (noche): el plan de optimización, aplicado

Viene de `Optimizacion_velocidad_memoria_Jarvis_MCU.md` (plan hecho en otro chat). Lo que se aplicó y lo que se midió:

- **Velocidad del modelo.** Gemma 3 4B ya era Q4_K_M. Probar 3, 4 y 6 hilos no cambia nada (lee ~25 tok/s, escribe ~5,8 tok/s). Ollama ignora `mlock`; en su lugar el servicio tiene `MemorySwapMax=0` y `MemoryLow=4600M` (el modelo no se va a swap) y `vm.swappiness=20`. Lo que de verdad daría velocidad es de hardware: el 4.º núcleo en la BIOS y un segundo módulo de RAM (doble canal).
- **Respuestas sin modelo.** Datos de ficha («¿quién dirigió…?», «¿cuánto dura…?») salen directos de la nota, en menos de 1 s. `grafo/datos_rapidos.py` genera 89 preguntas hechas: parentescos, nombres reales y 8 generales («¿Qué es el universo Marvel?», «¿Cuántas películas tiene?»).
- **Aviso de cifras.** Si la respuesta redactada trae un número que no está en las notas, añade un aviso de que conviene comprobarlo.
- **Nube del taller.** Lo que se sube desde el panel como «Nube del taller» queda aparte (`taller-…`), es otra bola en el mapa y, si un nombre existe en el taller y en Marvel, M-Jarvis pregunta de cuál se habla.
- **Memoria de rutas** (`~/mjarvis/rutas.json`). Guarda qué notas sirvieron para cada pregunta y las reutiliza si la pregunta vuelve (aunque cambie el orden de las palabras); si alguien dice que la respuesta estuvo mal, la ruta se borra. Medido: buscar cuesta 3 ms, así que **no ahorra tiempo apreciable**; lo que tarda es redactar. Sirve para que la misma pregunta vaya siempre por el mismo camino.
- **Vista «Nubes»** (tecla 6, «ponlo en forma de nubes»). Cada tema es una nube aparte con su nota más conectada en el centro; el tema mayor al medio; las notas que no forman tema (menos de 3) van juntas a «Notas sueltas», en la orilla.
- **Vista «Cuerpo»** (tecla 7, «ponlo en forma de cuerpo»). Figura humana: cabeza = Marvel en general (cerebro), corazón = red de trato, reactor en el pecho = Iron Man, escudo en el brazo = Capitán América, garras = Pantera Negra, Mjolnir en la mano = Thor, telaraña = Spider-Man, torso = Hulk, cintura = Viuda Negra y Ojo de Halcón, muslos = Guardianes/Thanos y Ant-Man, de rodillas a pies = héroes de la calle. Es solo otra manera de mirar: la búsqueda no cambia. El reparto está en `REPARTO` (por nombre de la nota y de su documento) dentro de `web/grafo/index.html`.

Sigue pendiente del plan: la voz (oír y hablar), que el propio plan deja para después de la velocidad. Por confirmar con el dueño: la fecha de la feria (el plan dice julio; aquí constaba febrero–marzo de 2027).

## Tanda del 2026-10-01 (cierre): rastro de la charla, celular y conexiones

- **Rastro de la charla** (`servidor.py`, bloque «El rastro de la charla»). Mientras se habla de alguien o de una obra, eso queda como `MEMORIA["sujeto"]` y `MEMORIA["obra"]`. Una pregunta corta que no nombra a nadie («¿y su esposa?», «¿cuál es su nombre real?», «¿cuánto dura?», «¿quién la dirigió?») se completa con el sujeto y, si hay respuesta escrita, sale sin modelo (etiqueta `rastro`). Medido: de 17–35 s a menos de 1 s. En los seguimientos que sí redacta el modelo, si lo que se pregunta ya está en las notas que tiene delante, no se le da nada nuevo que leer.
- Los parentescos de `datos_rapidos.py` se escriben con los dos nombres del héroe (Iron Man / Tony Stark): 117 preguntas hechas.
- **Celular y tableta.** `web/index.html`: en pantalla estrecha abre solo el chat; el botón «Red neuronal» muestra el mapa (no se carga hasta entonces). Mapa con pellizco de dos dedos. `app.webmanifest` + iconos (`latitude/icono.py`) para «Añadir a pantalla de inicio».
- **Conectar.** `web/conectar.html` (direcciones + QR; `/api/qr` usa `qrencode`). Menú de la Latitude: «Conectar» y «Wi-Fi propia» (`latitude/wifi-propia.sh`: la Latitude crea la red «M-Jarvis», canal 6, atiende en `10.42.0.1`; la contraseña la elige el dueño la primera vez). Probado con una red de prueba, ya borrada. El perfil de cable `mjarvis-cable` ahora pide dirección al router si lo hay y conserva la 169.254 para cable directo. `M-Jarvis.bat` prueba también `10.42.0.1`.
- **Guía:** `docs/Conectar M-Jarvis.pdf` (fuente `docs/conectar-m-jarvis.html`; se regenera con Edge `--headless --print-to-pdf`). También en `web/descargas/`.
- Falta probar con aparatos reales: celular/iPad en la Wi-Fi propia, cable a un router, dock por cable. El menú nuevo de la Latitude aparece al reabrir el lanzador (o al reiniciar).

### «Recalibrate» (2026-10-01, noche)

Decirle «recalibrate», «Jarvis, recalíbrate» o «recalibra tu red» hace una relectura real (`releer()` en `servidor.py`): vuelve a leer del disco todas las notas y rehace `graph.json`, recarga el índice, las reglas de criterio y jerga, las rutas, la red de trato, borra la conversación en curso y hace que el modelo repase sus instrucciones. Tarda 17–20 s en la Latitude. El mapa lo acompaña (`pintarRecal` en `web/grafo/index.html`): olas desde el centro mientras dura la lectura (las neuronas ya «leídas» quedan a media luz), y al terminar todo encendido, tres parpadeos y apagado; entonces responde con las cifras reales. Si la red cambió, el mapa se recarga solo.

Cada frase de trato enciende una sola neurona de trato (el mapa apaga la anterior): no hay frase que encienda varias.

### Lanzador de Windows: navegador predeterminado (2026-10-02)

`M-Jarvis.bat` ya no fuerza Edge. Pregunta a Windows qué programa abre los enlaces http (función `AssocQueryString`, con la orden de PowerShell codificada en base64 dentro del .bat; el registro `UserChoice` guardaba un Brave que ya no existe y no sirve). Familia de Chrome: ventana de aplicación y segundo monitor automático. Familia de Firefox (incluye Zen, el predeterminado del dueño): ventana nueva; el segundo monitor hay que colocarlo a mano y F11. Si se edita el .bat, guardarlo en ASCII con CRLF.

### «Recalibrate», retirado (2026-10-02)

El dueño pidió quitarlo. Ya no existe ni la orden en `servidor.py` (`RECALIBRAR`, `releer()`) ni la animación del mapa (`pintarRecal`). La sección de arriba queda solo como historia.

## Tanda del 2026-10-02: carácter, emociones, conversación por pantalla, desactivar notas

Orden de pendientes acordado con el dueño: voz, de lo último; datos reales del taller, hasta abril de 2027; «modo feria» (web con botones por atracción) queda **pendiente** porque lo quiere hacer con su equipo.

- **Una conversación por pantalla.** El chat manda un identificador propio (`cliente`, guardado en su navegador); el servidor tiene una memoria por cada uno (`MEMORIAS`, hasta 16; `usar_memoria`). Lo que pregunta un celular ya no cambia el tema de otro. Coste: al alternar entre pantallas el modelo tiene que releer la charla de la otra, así que la primera respuesta redactada tras un cambio tarda algo más.
- **Carácter (cuestionario del dueño).** Humor seco; emociones sutiles; gustos propios (Tony Stark, Visión, Loki como villano; no soporta a Ultrón); a veces devuelve una pregunta; identidad aparte del JARVIS de las películas; le importan la exactitud y sus creadores; le molestan las comparaciones con otras IA, que alaben a Ultrón, que lo apuren y que confundan Marvel con DC.
- **Charla casual** (`CHARLA` en `servidor.py`): 23 temas con frases fijas, al instante (favoritos, otras IA, Ultrón, prisas, si siente, si está vivo, soledad, edad, cumplidos, cariño, creadores, taller, miedo, sueño, ánimo de la persona…) más «cuéntame algo curioso» (saca una frase real de las notas de curiosidades). Si él preguntó «¿y el suyo?», opina de la respuesta (`GUSTO_AJENO`). Una opinión que no nombra nada de Marvel («¿qué opinas de la vida?») ya no busca notas: conversa.
- **Emociones simuladas** (`EMOCIONES`, 12): serenidad, orgullo, afecto, diversión, curiosidad, entusiasmo, fastidio, celos, indignación, preocupación, melancolía, desconcierto. Cada respuesta sale con una (`ANIMO_DE` para las frases fijas, `animo_de_pregunta` para las de conocimiento). Se ve en tres sitios: su nodo se enciende en la bola «M-Jarvis» del mapa (rama Emociones), el filo de la respuesta en el chat toma su color, y «¿cómo estás?» responde según el ánimo en que quedó. Al modelo solo se le pide tono cuando conversa **sin** datos: con datos lo llevaba a adornar e inventar (medido), y ahí manda la exactitud.
- **Preguntas resueltas.** `datos_rapidos.py` genera 156 (parentescos, nombres reales, 48 generales: actores, gemas, villanos, taquilla, muertes…). Tienen su propia bola en el mapa, unida al cerebro. Se contestan desde ahí al instante, incluso si la pregunta pide explicar o comparar; si no está ahí, se busca en el cerebro como siempre.
- **Desactivar notas.** Botón «Desactivar/Activar» en el panel de cada nota del mapa (y para toda la selección). No borra: la lista está en `~/mjarvis/desactivadas.json`; el índice no las carga, y en el mapa salen del cerebro a la bola gris «Desactivadas». Desde otro equipo pide la clave de gestión. API: `GET /api/desactivadas`, `POST /api/desactivar`.
- Corregido de paso: «¿quiénes son tus creadores?» llegaba al modelo y se inventaba nombres; ahora es trato fijo.

## Tanda del 2026-10-04: migración a Linux y reconexión

- El proyecto pasó de Windows a la Fedora/Linux nueva. Carpeta: `~/Documents/Organizado/Proyectos/M-Jarvis`. La copia fuente coincide con lo desplegado en la Latitude (solo difieren archivos generados: `graph.json`, `trato.json`, `medios/`, `aprendido.json`).
- Latitude viva: 3.168 notas (el usuario subió más desde el 2026-10-02), `mjarvis-web`, `x11vnc` y `novnc` activos, 39 °C, enchufada.
- Acceso: `ssh mjarvis` (llave en `~/.ssh/mjarvis_ed25519`, copiada del respaldo) → `ferr-latitude-5590.local` (hoy `10.0.0.22` por Wi-Fi).
- **Cable directo probado y funcionando** (0,6 ms, web 200 en `169.254.229.12:8080`). En la PC nueva el perfil de red `mjarvis-cable` en `eno1` usa IPv4 link-local (con DHCP se quedaba en «getting IP configuration»).
- **Lanzador Linux** (reemplaza a `M-Jarvis.bat`): `linux/m-jarvis-linux.sh`, instalado como `~/.local/bin/m-jarvis` y acceso «M-Jarvis» en el menú de aplicaciones. Menú zenity: panel, chat, mapa, todo junto, escritorio remoto, terminal SSH, estado. Abre en Zen (Flatpak).
- **Control remoto**: túnel SSH con socket de control (`-M -S`) a `localhost:6080` (noVNC). Se cierra desde el menú. No se usan `pkill -f` para cerrarlo.
- **Flujo de trabajo**: se edita aquí y, cuando funciona, se envía a la Latitude con `linux/desplegar.sh` (simulación por defecto; `-y` aplica). Sin `--delete`; no toca `conocimiento/`, `documentos/`, `web/medios/`, `aprendido.json` ni los grafos generados. Reinicia `mjarvis-web` solo si cambió el servidor o `comportamiento/`.

## Tanda del 2026-10-04 (2): refuerzo desde la bitácora, extensión, personalidad y auto-entrenado

Diagnóstico completo en [ANALISIS_BITACORA.md](ANALISIS_BITACORA.md). Lo hecho:

**Habilidades (recetas)** — `servidor/recetas.py`. Destrezas sin modelo, con contador de usos y botón de apagar en el panel: `texto_largo`, `correccion_tema`, `animo_bajo` (acompañar sin soltar datos), `queja`, `silencio`, `que_aprendiste`, `pertenencia_marvel`, `que_es_marvel`, `aclarar_plural`, `sin_pregunta`. Se dibujan en la red de trato (rama «Habilidades»).

**Extensión** — `comportamiento/criterios.json` fija palabras mínimas/máximas por tipo de pregunta. El servidor corta al final de una frase al pasarse del máximo (`corte_palabras`) y, si se queda corto, suma de las notas el dato que falta (`completar`, nunca del modelo). Las respuestas copiadas de una nota se convierten en frase completa (`como_frase`: «Nebula.» → «Su hermana se llama Nebula.»). «Háblame de X» sale de la nota general de X.

**Rúbrica** — `servidor/criterios.py` + `criterios.json`: 14 reglas con peso (grosería sin filtrar, falta de empatía, regaño, respuesta cortada, tratamiento con género, extensión, «Sí/No» incoherente, primera persona, muletillas, nombres/cifras sin respaldo, lentitud, repetida, corregida por la persona). Cada respuesta queda en la bitácora con `calidad` y `fallos`.

**Personalidad** — `comportamiento/personalidad.json`: 59 categorías de charla nuevas (cómo funciona, privacidad, internet, proyecto, juegos, consejos, motivación, miedo/enojo/soledad/alegría del usuario, favoritos, filosofía, política/religión/salud, spoilers, recomendaciones…), 12 «guías de situación» que se le añaden al modelo en una línea (explicar más fácil, debate, capciosa, enojo, opinión…) y variantes extra de las frases fijas. Las frases fijas ya no repiten la última usada (`criterio.elegir`).

**Búsqueda sin ruido** — la nota solo cuenta como hallada si dice su nombre completo, o puntúa ≥16, o cubre la pregunta (`Indice.fuerza`). Ya no se mete «Cielo Negro» al preguntar por el cielo azul. «Quién es su hermano» tras Loki ya no trae a Pietro (`habla_del_sujeto`). Una pregunta capciosa nunca sale como dato suelto.

**Pruebas** — `servidor/pruebas_rutas.py` corre `comportamiento/escenarios.json` (294 escenarios) con un modelo simulado en ~3 s: `python3 pruebas_rutas.py -v` en la Latitude (`~/mjarvis/venv/bin/python`). Estado: 294/294. Cualquier cambio debe dejarlo en verde antes de desplegar.

**Auto-entrenado** — `servidor/autoentreno.py` + sección del panel. No reentrena el modelo: analiza la bitácora con la rúbrica, corre las pruebas, practica una muestra de escenarios con el modelo real (botón «Práctica completa») y propone cambios (palabras del filtro, variantes de frases escritas por el propio modelo y filtradas por la rúbrica). Cada propuesta la aprueba el dueño; al aplicarla se repiten las pruebas y, si empeoran, se deshace sola (respaldos en `comportamiento/_respaldos/`). Análisis rápido automático cada 6 h si hay calma. Estado en `~/mjarvis/autoentreno.json`.

**Despliegue** — `linux/desplegar.sh` ahora trae primero `reacciones.json` y `personalidad.json` de la Latitude si allá son más nuevos (lo aprobado en el panel) y no envía `recetas.json`, `propuestas.json` ni `_respaldos`.

Otros: lanzador Linux usa la IP (Zen en Flatpak no resuelve `.local`); «Detener» ya no cancela la pregunta siguiente; respuestas cortadas no entran a la memoria y se pueden retomar con «hazlo otra vez»; «enciende/apaga todas tus neuronas», «la menos conectada», «sigue» (paginación) funcionan.

**Flujo recomendado ahora:** editar aquí → `linux/probar.sh -v` (copia a `~/mjarvis-prueba` en la Latitude y corre los 315 escenarios; no toca el servicio) → `linux/desplegar.sh` (simulación) → `linux/desplegar.sh -y`.
**Lección:** al mostrar el texto del modelo se retienen los últimos `RETENER` (30) caracteres, porque `limpiar()` puede quitar fragmentos ya escritos («, debo admitir,», «según los Datos,»). Con 14 se mostraba «ln genio» y «De acuerd la armadura»; la prueba `streaming-*` lo vigila. Si se añade una limpieza más larga que 30 caracteres, subir `RETENER`.
**Pendiente / límites conocidos:** el modelo de 4B sigue inventando a veces (p. ej. «Hércules» al comparar fuerzas) y tarda 15–45 s en redactar; «debo admitir que…» (con «que») no se filtra; falta cargar los datos reales del taller (hasta abril de 2027), la voz y el modo feria.

## Tanda del 2026-10-04 (3): cuerpo, voz y oído

**Cuerpo (`web/index.html`).** Rediseño del chat: la bola de plasma (shader WebGL propio, `Orbe`) en primer plano arriba y la conversación abajo; los mensajes suben por detrás de la bola y se desenfocan al pasar (cinco capas de `backdrop-filter` en `#velo` + máscara de desvanecido). La bola tiene cuatro estados (espera, escucha, piensa, habla), cambia de color con el ánimo de cada respuesta (los 12 colores de `ANIMOS`) y reacciona al nivel de la voz y del micrófono. A 15 cuadros/s en reposo y hasta 30 activa (consume ~25–35 % de un núcleo en la Latitude); si la gráfica no da abasto baja la resolución sola; sin WebGL cae a una bola de CSS. Tipografías propias en `web/fuentes/` (Newsreader para la voz de Jarvis, Instrument Sans para la interfaz). Antes de la primera pregunta muestra cuatro invitaciones. Funciona igual en `?vista=chat`, en la pantalla dividida y en el celular.

**Voz (`servidor/voz.py`).** Piper, en local. Voz por defecto `es_MX-claude-high` (instaladas también `es_MX-ald-medium` y `es_ES-davefx-medium`; se cambia en `comportamiento/voz.json`). `POST /api/voz {texto}` → WAV (~0,3–2 s por frase; caché de 48 frases). El navegador pide cada frase en cuanto Jarvis la termina de escribir y las encadena; la bola late con el nivel real del audio. Encendida por defecto solo en el kiosco (`localhost`); en los celulares empieza apagada (botón del altavoz). Si la espera es larga, dice una vez su frase de relleno.

**Oído (`servidor/voz.py`).** faster-whisper `small` int8, en local. `POST /api/oir` (audio del navegador) → texto, ~3 s por frase de 8 s. Se guía con un texto de vocabulario (Marvel, Jarvis…) para acertar nombres. Se descarga de memoria tras 10 min sin uso. El botón de micrófono solo aparece donde el navegador lo permite (`localhost` o https): en el kiosco sí; en celulares por http no. Graba hasta que quien habla se calla (umbral adaptado al ruido de la sala), corta a los 6,5 s si nadie habló y manda el texto como pregunta.

**Instalación (la Latitude no tiene internet en modo Wi-Fi propia).** Ruedas de Python 3.14 descargadas en la PC y copiadas a `~/rueda-voz` en la Latitude; modelos en `~/mjarvis/modelos/` (Piper y Whisper). `faster-whisper` 1.2.1 no abre archivos con PyAV 19: el audio se decodifica con `Oido.decodificar`. Permisos de sonido y micrófono para el kiosco en `user.js` del perfil de Firefox (surten efecto al reabrir el kiosco).

**Pendiente de esta línea:** escucha continua con palabra de activación («Jarvis»), voz de Jarvis más acorde (probar `ald` y `claude` por oído), el mapa en la bola de la vista dividida.

## Puente de internet por el cable (2026-10-04)

Esta PC le comparte su internet a la Latitude por el cable Ethernet, para cuando la Latitude no tenga Wi-Fi (taller, feria).
- **PC:** perfil `puente-internet` en `eno1` (NetworkManager, modo «compartida»): `10.43.0.1/24`, DHCP + NAT hacia el Wi-Fi de la PC. Se activa solo al enchufar el cable. El perfil antiguo `mjarvis-cable` (dirección de enlace local 169.254, sin internet) queda como respaldo de menor prioridad.
- **Latitude:** perfil `puente-internet` en `enp0s31f6` (DHCP, métrica 700, tiempo de espera 15 s) con prioridad 20; `mjarvis-cable` con prioridad 5. Con Wi-Fi y cable a la vez, el Wi-Fi (métrica 600) sigue siendo la ruta por defecto: el cable solo se usa si el Wi-Fi falta.
- **Probado:** con el Wi-Fi de la Latitude apagado, `example.com` y `huggingface.co` responden por el cable (0,18 s) y el panel se alcanza en `http://10.43.0.218:8080/` (la dirección la asigna el DHCP; el nombre `ferr-latitude-5590.local` también sirve).
- **Deshacer:** `nmcli con down puente-internet` en la PC (la Latitude vuelve sola a enlace local tras 15 s).
- **Requisito:** la PC debe tener internet por su Wi-Fi; si la PC está apagada o sin red, la Latitude queda como hoy (todo local).

## 2026-10-04 (4) · Cerebro de red, portal cautivo y Manager

**Cerebro de red** (`servidor/red.py`): decide solo, en este orden, nube (Wi‑Fi con internet) → puente (internet por cable) → lan (red sin internet) → local (crea su Wi‑Fi «M-Jarvis»). Tiene tiempos de gracia, un reintento periódico para volver a una red mejor y un registro de decisiones. Si el dueño enciende la Wi‑Fi propia a propósito, no se apaga sola durante una hora. Para volver a la Wi‑Fi de casa se nombra el perfil conocido (`volver_a_wifi`): `nmcli device connect` volvía a elegir la propia. `latitude/wifi-propia.sh` tenía el mismo defecto y está corregido.

**Portal cautivo**: toda red de M-Jarvis (10.42/10.44) manda cualquier nombre de dominio a 10.99.99.1 (`/etc/NetworkManager/dnsmasq-shared.d/mjarvis-portal.conf`), el puerto 80 se redirige al 8080 (`/etc/mjarvis/portal.nft`, servicio `mjarvis-portal`) y el servidor responde a las pruebas de Android, iOS y Windows con una redirección al chat. Probado con cable y con la Wi‑Fi propia.

**Manager** (`web/manager.html`, instalable como app): consola para otro equipo (Windows, Mac, Linux o celular).
- Ahora: respuestas en vivo con su ruta, habilidad, calidad y fallos; mapa de conexiones; Detener, Silenciar la voz y Bloquear el teclado.
- Red: modo actual, equipos conectados, registro de decisiones, acciones y guía por dispositivo con QR.
- Aprender: datos por aprobar, respuestas aprendidas y respuestas por revisar.
- Decir: hace que Jarvis diga algo o que la pantalla pregunte algo (teatro).
- Sistema: temperatura, memoria, procesador, disco y batería.

Las órdenes piden la clave de gestión (`X-Clave`) desde otros equipos. Solo la pantalla de la propia Latitude (localhost) obedece las órdenes `orden` (exhibicion, callar, decir, preguntar) que llegan por `/api/eventos`.

Accesos directos para abrir el Manager como app, buscando a la Latitude (`descargas/M-Jarvis-Manager.{bat,command,sh}`). Menú de la Latitude: entrada «Manager». Pruebas: 349/349.

Pendiente: la nube como cerebro (decidir privacidad), copias a Drive, túnel remoto y escucha continua por palabra clave.

## 2026-10-04 (5) · Nube gratis como apoyo (`servidor/nube.py`)

Cuando está encendida y hay internet, un modelo más grande en la nube escribe la respuesta; el resto (recetas, filtros, notas, límites de longitud, avisos de cifras) sigue local. Si falla, se agota la cuota o no hay internet, responde `gemma3:4b` como siempre. Esta PC no interviene: solo sirve para probar y desplegar.

- **Cadena:** Groq GPT-OSS 120B → Qwen 3.8 27B → GPT-OSS 20B (~1000/día cada uno; los Llama de Groq ya no existen) → Gemini Flash-Lite (~1000/día, y Google puede usar lo enviado en el plan gratis: por eso va último y es opcional) → modelo local. Límites tomados de búsquedas del 2026-10-04; cambian, y los nombres de modelo se editan en `PROVEEDORES`.
- **Claves:** `~/.config/mjarvis/nube.json` en la Latitude (permisos 600, fuera del proyecto: no se despliegan). Se ponen en Manager → Sistema → Nube gratis. Nunca se devuelven enteras.
- **Privacidad:** las preguntas con datos personales (`PRIVADO` en nube.py) no salen nunca; en lo que sale, correos, teléfonos y enlaces se tachan. Las notas no se tocan.
- **Fallos:** 429 → pausa (Retry-After, o 1 h si es el límite diario); clave rechazada → pausa 1 h con el motivo visible; sin red → pausa 60 s. «Detener» corta también la espera de la nube.
- **Control:** mando «Nube gratis» en Manager → Ahora (apagado = todo local, para enseñar «100 % local»). Cada respuesta dice su motor (`motor` en la bitácora y en la etiqueta del Manager).
- Pruebas: 14 nuevas con un servidor falso del protocolo de OpenAI (363/363). Alcance real comprobado: la Latitude llega a Groq (rechazó una clave falsa con 401).

- **Wi-Fi propia + cable a la vez (2026-10-04):** con el cable dando internet (modo puente) la Wi-Fi «M-Jarvis» y el internet conviven: la Latitude reparte el internet del cable a los celulares (NAT de NetworkManager) y sigue usando la nube. Ya no se apaga sola para buscar otra Wi-Fi mientras el modo sea puente (`_volver_arriba` en red.py). Pendiente de probar con un celular real. Las pruebas de `probar.sh` corren EN la Latitude: nada que toque `red._nm` sin parchear.

## 2026-10-04 (6) · Interfaz única con «vidrio»

Una sola interfaz en `index.html`: la bola y el chat son la escena y nunca desaparecen; **Mapa**, **Conectar** y **Control** se abren como láminas de cristal encima (sin cambiar de página), con una barra flotante abajo (icono + nombre, con un cristal que se desliza bajo la sección activa).
- `web/vidrio.css`: el sistema visual (material de cristal con borde brillante, ambiente de color detrás, mandos tipo Centro de control de iPhone, interruptores, segmentos, anillos).
- `web/shell.js`: navegación por hash (`#mapa`, `#conectar`, `#control/ahora|escenario|aprender|red|sistema`), la barra, la lámina, Mapa, Conectar (por dispositivo: iPhone, Android, Windows, Mac, Linux) y la puerta de Control.
- `web/control.js`: Control (antes Manager): mandos Voz / Teclado / Nube / Parar, lo que pasa en vivo, Escenario, Aprender, Red, Sistema (incluye las claves de la nube).
- **Control está oculto para los visitantes**: no aparece en la barra y, si se entra por `/#control`, pide la clave (menú M-Jarvis → Compartir). Desde la propia Latitude (localhost) no la pide.
- Las pantallas del público no cambian: `/?vista=chat` (solo la escena) y `/?vista=todo` (mapa a un lado), sin barra ni láminas. «Todo junto» del menú de la Latitude usa `?vista=todo`.
- `manager.html` y `conectar.html` ahora solo redirigen a `/#control` y `/#conectar`; los accesos directos descargables abren `/#control`. Se eliminó `manager.webmanifest`.
- Pendiente: `panel.html` (archivos y registros) conserva su estilo anterior; la guía PDF menciona `manager.html` (sigue funcionando por la redirección).

## 2026-10-04 (7) · Fase de optimización

Medido en la Latitude (pantalla del público, `?vista=chat`, sin conversación): Firefox pasó de **33 % a 11–12 % de un procesador en reposo** (ese procesador lo necesita el modelo). Carga repetida de la interfaz: de ~430 KB en 6+ descargas a **30 KB en 119 ms**.
- **Servidor** (`servidor.py`, `Manejador.servir_estatico`): ETag + `no-cache` (revalidar siempre, así cada despliegue llega al instante), gzip guardado en memoria (mapa 1,8 MB → 349 KB, página 48 → 17 KB, CSS 23,5 → 6,3 KB), fuentes e imágenes con caché largo. `ultimas_preguntas` lee solo el final de la bitácora y recuerda el resultado; `estado_general` recuerda lecturas y direcciones 3–4 s (`recordado`). El cerebro de red ya no lee los clientes DHCP (un `sudo`) si la máquina no reparte red.
- **Pantalla**: el bucle `latido` solo escribe en la página si algo cambió y mira 3 veces por segundo en reposo (20 si hay algo vivo); la bola dibuja a 8 cuadros por segundo en reposo (4 con una lámina encima); el velo de desenfoque solo funciona cuando hay texto cerca de la bola; `control.js` se descarga solo si alguien abre Control; el mapa de Control espera un rato libre; las consultas de Control se detienen con la pestaña oculta; los turnos del feed usan `content-visibility`.
- **Lecciones**: (1) las manchas de fondo (`#ambiente`) cuestan ~35 % de CPU en la Latitude (Firefox sin GPU): por eso la pantalla del público no las lleva, y el resto de equipos las pausan con una lámina abierta o si la bola baja su resolución (`body.ahorro`). (2) Una optimización rompió el chat (usaba `Voz` antes de declararla) y `probar.sh` no lo vio: ahora hay `bench/humo.js`, una prueba de humo con navegador que recorre todas las pantallas y hace una pregunta. Correrla tras tocar la interfaz. (3) Con una sesión de escritorio remoto abierta, x11vnc + Xorg suman ~17 % más.

## 2026-10-04 (8) · Panel y mapa en el mismo cristal
- `panel.html` ya no existe como página: sus funciones viven en **Control** (`#control/archivos`, `#control/aprender`). Nueva sección **Archivos** (subir con arrastrar y soltar, elegir Marvel/taller, buscar, ver notas, descargar el original, borrar) y **Aprender** con cuatro pestañas (Lo que aprende, Auto-entrenado con sus propuestas, Habilidades con interruptores, Historial). Sistema muestra además las direcciones y, solo en la Latitude, la clave de gestión. `panel.html` y `subir.html` redirigen; los lanzadores (menú de la Latitude, `M-Jarvis.bat`, `m-jarvis-linux.sh`) apuntan a `/#control/archivos`.
- `grafo/index.html` (el mapa suelto y el que va dentro de Mapa/Control): bloque `<style id="vidrio">` con el cristal de `vidrio.css` para sus botones, buscador, paneles y temas. No enlaza `vidrio.css` porque comparten ids (`#aviso`).
- Pendiente: la guía PDF `Conectar M-Jarvis` y `docs/EMPEZAR.md` aún dicen «Manager», `manager.html` y los nombres antiguos de las pestañas (funciona por la redirección).

## 2026-10-05 · Pulido de animaciones
Criterio: la interfaz es de operación, así que el movimiento explica estado y continuidad y no hace esperar. Todo en `transform`, `opacity` y desenfoque acotado; el cristal de la lámina ya desenfoca el fondo, por eso la lámina **no** anima desenfoque propio (era lo más caro y colgaba las capturas en software).
- **Duraciones**: lámina 0,45 s (antes 0,7) y sale en 0,2 s por donde entró, sin `ease-in`; cristal de barra y selectores 0,4–0,45 s; mandos 0,25 s; interruptor 0,32 s; turnos y mensajes 0,38–0,4 s. Curva `--salida` (exponencial) y `--salida-rapida`; el rebote del cristal bajó de 1,45 a 1,25.
- **Continuidad**: al cambiar de sección (y entre las de Control) el cuerpo de la lámina se desliza hacia el lado donde está la sección nueva, con View Transitions (`html.con-vt`; sin ellas, un fundido). No se usa si hay que descargar `control.js` primero.
- **Detalles**: el cristal de la barra y de los selectores ya no nace deslizándose desde la izquierda (`.quieta`); el selector de Control se conserva entre sus secciones (el cristal se desliza); los anillos del sistema se dibujan una vez y luego se mueven; las listas entran escalonadas (40 ms, tope 6) solo la primera vez (`escalonar`); las sugerencias del chat entran una tras otra.
- **Movimiento reducido**: sin desplazamientos, rebote ni desenfoque, pero la lámina, los cambios y los mandos siguen con un fundido corto.
- Sin comprobar a ojo: cómo se **siente** (el navegador de pruebas no tiene GPU y no capta el movimiento). Revisar en un teléfono y a cámara lenta.

## 2026-10-05 (2) · Formas del mapa: fuera «Cuerpo», nubes y galaxia nuevas
- **Cuerpo eliminado** (botón, tecla 7, código de la figura, rótulos con línea y la orden de voz «forma de cuerpo»). Las frases de Jarvis que la ofrecían ahora ofrecen la galaxia. Las teclas 1–6 son: plano, cerebro, esfera, dona, galaxia, nubes.
- **Nubes** (`formarNubes`, `bultosDe`, `contornoDe`, `vapor`): cada tema es un cúmulo —bultos que se montan, base casi plana— con las notas repartidas dentro (las más conectadas, al corazón), vapor suave del color del tema detrás y un borde festoneado. La forma de cada nube sale de una semilla del tema: siempre es la misma. Las tres de fuera (M-Jarvis, Otros universos, Preguntas resueltas) también son cúmulos en esta vista; las que no tienen notas no se dibujan.
- **Galaxia** (`galaxiaPunto`, `estrellasDeGalaxia`, `resplandorGalaxia`): bulbo central denso, dos brazos en espiral logarítmica que se abren y se ensanchan, disco fino y halo; ~4 200 estrellas tenues (cálidas en el bulbo, azuladas en los brazos), núcleo cálido y neblina siguiendo la espiral. Se mira muy inclinada al llegar y las neuronas son más pequeñas para que no tapen los brazos.
- Sin cambios: plano, cerebro, esfera y dona.

## 2026-10-10 · Flujo de trabajo en Windows
Se cambió de sistema operativo (Linux a Windows). La copia buena del proyecto es la de OneDrive (Documents\Organizado\Proyectos\M-Jarvis); C:\Users\srelm\mjarvis-pc es la copia temporal que se usó para ejecutar Jarvis en la PC (obsoleta) y _Duplicados-verificados es la copia del 1 de octubre. Se recreó el flujo de linux/*.sh en windows/ (ver windows/LEEME.md): probar, desplegar, tunel, humo. Comprobado de punta a punta: 365/365 escenarios, despliegue real con reinicio, prueba de humo con Edge y chmod +x de los .sh. Se desplegaron de paso las opciones MJARVIS_SIN_RED y MJARVIS_ESCUCHA del servidor y la corrección de wifi-propia.sh.
