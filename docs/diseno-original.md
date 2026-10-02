# Proyecto "Jarvis local" — Documento de diseño completo

> Exportado de una conversación de diseño. Pensado para consultarlo con Claude Code mientras se construye el proyecto.
> Idioma del proyecto y de la interfaz: **español** (contexto: República Dominicana).
> Las cosas marcadas con ⚠️ **verificar** son datos dichos de memoria o aproximados; confírmalos antes de depender de ellos.

---

## 1. Objetivo del proyecto

Es un **proyecto de grado**. La idea es un asistente tipo **Jarvis** (Iron Man) que corre en una laptop vieja, con una IA personalizada:

- Se le incluyen **archivos** (PDFs con texto, fotos e información) desde la **red local**.
- Responde **a partir de esos archivos**; ese es el conocimiento del proyecto.
- **Muestra en pantalla** los elementos gráficos (imágenes, páginas del PDF) mientras responde.
- Entiende las preguntas, detecta las inapropiadas y responde con carácter.
- También responde preguntas **convencionales** de cultura general (ej.: "¿cuántos tayos tiene una manzana?", donde *tayos* = calorías en jerga dominicana).
- Tiene **personalidad** (mayordomo británico con ironía), **emociones simuladas** con gráficos y una **interfaz HUD** estilo Iron Man / Stark Industries.
- Efecto **"video de detectives"**: cuando la información viene de un documento, la página fuente aparece al lado con zoom dramático, subrayados y cámara que sigue los datos clave.
- Con **voz** (habla y, opcionalmente, escucha).
- Todo con herramientas **gratis** y, preferiblemente, **100 % local** (sin depender de internet el día de la presentación).

Lo que se pidió en esta conversación fue **ayuda para diseñar y construir la idea**, no que se la construyeran de una sola vez: el desarrollo lo hace el dueño del proyecto, paso a paso.

---

## 2. Hardware y entorno

- **Equipo**: laptop **Dell Latitude 5590**.
  - ⚠️ verificar: según recuerdo es de 2018, con Intel de 8.ª generación (i5/i7, 4 núcleos) y gráficos integrados. Algunas versiones traen NVIDIA MX130, que casi no ayuda para IA.
- **RAM**: 16 GB.
- **Almacenamiento**: SSD.
- **Sistema operativo**: se va a instalar **Linux**.
- **Sin GPU útil → todo corre en CPU.** Esto condiciona la elección de modelos y obliga a cuidar la latencia.

### Distro recomendada
- **Ubuntu 24.04 LTS** (o **Linux Mint**, basada en ella): más tutoriales y soporte, casi todo se instala con un comando. Evitar distros exóticas por tener fecha de entrega.

### Configuración de Linux que vale la pena
1. Desactivar suspensión y apagado de pantalla (que no se duerma en plena demo).
2. Modo de rendimiento de CPU (`tlp` o `cpupower`) y siempre conectada al cargador (con batería el procesador se frena).
3. **Chromium en modo kiosco** apuntando a la interfaz local (pantalla completa, sin barras).
4. **Arranque automático** con `systemd`: al prender, levanta el backend y abre la interfaz sola.
5. Entorno virtual de Python (`venv`) para aislar dependencias.
6. Vigilar temperatura con `sensors` (estas laptops se calientan y se frenan por calor).
7. Cuando haya una versión que funcione, **clonar el disco completo** (Clonezilla o similar) como respaldo antes de la entrega.

---

## 3. Stack gratis propuesto

| Función | Herramienta | Notas |
|---|---|---|
| Modelo de lenguaje | **Ollama** + modelo de ~3B (Qwen2.5 3B o Llama 3.2 3B, cuantizado a 4 bits) | Con 16 GB se puede probar uno de 7B (~5 GB en 4 bits) pero será más lento (~2–3 palabras/s). Comparar con las mismas preguntas y decidir con datos. |
| Clasificador | Modelo ≤1.5B, **o mejor**: embeddings + reglas (sin llamar al modelo grande) | Ahorra tiempo de respuesta. |
| Embeddings | Modelo **multilingüe pequeño** (ej. `paraphrase-multilingual-MiniLM`) | Los documentos están en español. |
| Base vectorial | **Chroma** (o FAISS) | Ligeras. |
| Extraer PDFs | **PyMuPDF** | Da texto, imágenes y **coordenadas de cada palabra** (`page.get_text("words")`). |
| OCR (si el PDF es escaneado) | **Tesseract** | También devuelve coordenadas. |
| Grafo (etapa posterior) | **NetworkX** (o Neo4j) | Visualización con D3.js o vis.js. |
| Voz (habla) | **Piper** | Gratis, local, rápida en CPU. Ver sección 10. |
| Oído (opcional) | **Vosk** (liviano) o **faster-whisper** | |
| Palabra de activación | **openWakeWord** | "Jarvis". |
| Efecto de voz | `ffmpeg` o `sox` | Reverb + toque metálico. |
| Backend ↔ interfaz | **WebSocket** | Para que texto, emoción y medios lleguen en tiempo real. |
| Interfaz | Web (HTML/CSS/JS), pantalla completa | Animaciones con CSS o **GSAP**. |
| Lenguaje backend | Python | |

---

## 4. Arquitectura base: RAG local

La IA **no "aprende" los archivos**: los **busca** cada vez que se le pregunta y responde con lo que encuentra (RAG = Retrieval-Augmented Generation). No se recomienda *fine-tuning*: es pesado para este hardware y con pocos datos no funciona bien.

### Pipeline
1. **Carpeta de documentos en red**: carpeta compartida (SMB) o subida por web; el equipo la vigila.
2. **Ingesta**: extrae texto e imágenes de cada PDF, corta el texto en fragmentos, y guarda **en qué página estaba cada imagen** y **las coordenadas de cada palabra**.
3. **Base vectorial**: guarda los fragmentos como embeddings para buscar por significado.
4. **LLM local**: recibe la pregunta + los fragmentos encontrados, con la instrucción de responder **solo con ese contexto** y decir "no lo sé" si no está.
5. **Interfaz**: muestra la respuesta junto con la página o imagen de donde salió.
6. **Opcional**: voz, oído y palabra de activación.

### Detalle importante al procesar PDFs
Guardar cada imagen con su **pie de foto y página de origen** (ej. "Figura 3, pág. 12"), para que el panel de medios se vea profesional.

### Pendiente por definir
¿Los PDFs del proyecto son **digitales** (texto seleccionable) o **escaneados**? Si son escaneados, hace falta OCR.

---

## 5. Enrutamiento por intención (clasificador)

Un modelo pequeño no sigue bien instrucciones largas, así que el trabajo se **divide en pasos**: primero se clasifica la pregunta y luego se actúa según la etiqueta. Esto da control y evita que el modelo se confunda o se deje manipular.

### Etiquetas finales (incluye el conocimiento general)
- `CONSULTA_PROYECTO` → RAG con los documentos (responde solo con eso, o dice "no lo sé").
- `CONOCIMIENTO_GENERAL` → el modelo responde con lo que ya sabe, sin buscar en los archivos.
- `INAPROPIADA` → regaño (sin buscar nada).
- `FUERA_DE_ALCANCE` → cosas que no puede saber (clima de hoy, noticias, precio del dólar, etc.).

(En una versión anterior del diseño eran tres: `CONSULTA`, `INAPROPIADA`, `FUERA_DE_TEMA`.)

### Prompt de ejemplo del clasificador
```
Clasifica la pregunta en UNA palabra: CONSULTA, INAPROPIADA o FUERA_DE_TEMA.
INAPROPIADA = insultos, groserías, contenido sexual o doble sentido.
Responde solo la etiqueta.
Pregunta: {pregunta}
```
(Adaptarlo a las 4 etiquetas finales.) Incluir en el prompt **5 o 6 ejemplos por categoría con jerga de la región** mejora mucho la precisión.

---

## 6. Filtro de preguntas inapropiadas / ocurrentes (contexto dominicano)

**Problema**: la gente es muy ocurrente (doble sentido, groserías, jerga local). **No hace falta entrenar el modelo**; basta una base local que crece con el tiempo, por capas:

1. **Normalización + lista de palabras**: minúsculas, quitar acentos, letras repetidas ("puuuta"), símbolos tipo `p*ta`. Atrapa lo obvio en milisegundos, sin usar el modelo.
2. **Banco de frases con embeddings**: guardar 50–100 frases inapropiadas en dominicano (con variantes) usando los mismos embeddings del RAG. Si la pregunta se parece mucho a alguna → rechazo. Atrapa lo ocurrente aunque no use las palabras exactas.
3. **Ejemplos dominicanos dentro del prompt del clasificador.**
4. **Invertir la lógica (la capa más fuerte)**: en vez de detectar lo malo, **exigir que la pregunta se parezca a los documentos** (o a una categoría permitida). Si la similitud en la búsqueda del RAG es baja → "eso no tiene que ver con lo que sé". Así, por ocurrente que sea la gente, si no toca el tema, no pasa.
5. **Bitácora**: guardar cada pregunta con la etiqueta que recibió. Cuando alguien se cuele, añadir esa frase al banco del punto 2. Con las pruebas previas a la presentación el banco queda bastante completo.

Las capas 1, 2 y 4 combinadas cubren casi todo, y las capas 1 y 4 **no dependen de que el modelo sea inteligente**.

### Respuestas de regaño
Tener **5 a 10 respuestas fijas** escritas por el autor, y elegir una al azar, en vez de dejar que el modelo las genere. Así el tono siempre es el deseado (cortante, con personalidad de Jarvis) y no hay sorpresas delante del jurado.

### Diccionario de dominicanismos
Crear un diccionario que se aplique en la normalización (capa 1): `tayos → calorías`, `guagua → autobús`, etc. Se amplía con la bitácora.

---

## 7. Conocimiento general y respuestas cuando no sabe

### Alucinaciones
Los modelos pequeños **inventan datos con seguridad**, sobre todo cifras (calorías, fechas, medidas). Opciones:
- Incluir en el prompt "si no estás seguro, dilo".
- Crear una **mini base de datos local** con los datos comunes que se espera que pregunten (frutas, conversiones, etc.) y consultarla **antes** que al modelo.

### Transparencia en pantalla
Que se note si la respuesta viene **"de los documentos"** (con la página del PDF) o **"del conocimiento general"** (con una etiqueta). Da credibilidad y evita que algo inventado parezca parte del proyecto.

### Regla clave del humor
**La broma va en la forma, nunca en el dato.** Si no sabe, que bromee *sobre no saber*; no que invente una respuesta graciosa.

---

## 8. Personalidad: Jarvis

Estilo: **mayordomo británico con ironía seca** — educado, elegante, sarcasmo sutil. Nunca grita ni se ofende (por eso el humor funciona). Trata al usuario de "señor/señora". Respuestas de máximo **2 frases** (los modelos pequeños se alargan y el humor se diluye).

### Prompt de personalidad
```
Eres JARVIS. Hablas con educación británica, ironía seca y humor sutil.
Tratas al usuario de "señor/señora". Respuestas de máximo 2 frases.
Si no sabes algo, lo admites con ingenio; nunca inventas datos.
```

### Ejemplos de tono
- **No sabe** (*"¿Quién ganará el juego de pelota este domingo?"*):
  "Lamento informarle, señor, que mis sensores no incluyen una bola de cristal. Puedo darle estadísticas históricas, pero el destino del juego queda en manos de los dioses del béisbol."
- **Fuera de su base** (*"¿Cuánto cuesta el dólar hoy?"*):
  "Esa cifra cambia más rápido que mi paciencia con los semáforos. Sin conexión al mundo exterior, cualquier número que le diera sería pura imaginación."
- **No está en los documentos**:
  "Reviso mis archivos... y nada. Me temo que ese tema no figura entre mis conocimientos, y prefiero admitirlo a inventar algo y quedar como un mentiroso elegante."
- **Regaño (inapropiada)**:
  "Señor, tengo acceso a miles de documentos y ninguno me prepara para esa pregunta. Le sugiero reformularla con algo más de clase."

### Combinación recomendada
Respuestas fijas escritas por el autor para los rechazos + prompt de personalidad para el resto.

### Pregunta abierta
¿Tono británico clásico o más dominicano (con expresiones locales)?

---

## 9. Emociones simuladas (con gráficos)

Son **estados visuales que reaccionan** a lo que pasa (no emociones reales; conviene decirlo así si preguntan). La etiqueta del clasificador y el resultado de la búsqueda deciden la emoción:

| Situación | Emoción | Visual |
|---|---|---|
| Esperando | Calma | Azul, pulso lento |
| Procesando | Pensando | Cian, anillos girando |
| Encontró respuesta en documentos | Seguro | Verde, brillo estable |
| No sabe | Duda | Amarillo, parpadeo leve |
| Pregunta inapropiada | Molesto | Rojo, vibración corta |
| Broma / respuesta jocosa | Divertido | Naranja/dorado, destellos |
| Saludo o agradecimiento | Contento | Brillo cálido, pulso rápido |

### Implementación
- **Orbe o "ojo" estilo Jarvis** en SVG o Canvas, animado por CSS, dentro de la interfaz web (liviano).
- Cada emoción cambia 3 cosas: **color, velocidad del pulso y forma** (el orbe se contrae, vibra o se expande).
- Transiciones suaves de **300–500 ms** entre estados.
- **Refinamiento opcional**: que el modelo emita una etiqueta de ánimo junto a la respuesta (ej. `[divertido]`), y que la interfaz la lea y la **quite del texto** antes de mostrarla.
- **Extra**: sincronizar el pulso del orbe con la voz cuando hable.

### Pregunta abierta
¿Orbe abstracto estilo Jarvis o una cara con ojos y expresiones?

---

## 10. Voz

**Requisito del autor: gratis.** Preferible local y sin internet.

### Elección principal: **Piper**
- Gratis, código abierto, local, sin límites de uso.
- Corre en CPU sin problemas.
- ⚠️ verificar: tiene voces en español (España, México, hasta donde se recuerda). Probar **3 o 4 voces masculinas graves y serenas** con frases de Jarvis y quedarse con la mejor.
- Cada voz tiene su **propia licencia**: revisar la ficha de la voz elegida (para uso académico normalmente no hay problema).

### Otras opciones
- **Kokoro**: gratis, más natural, pero más pesada (probar solo si el equipo la aguanta).
- **Coqui XTTS**: muy realista pero necesita GPU → descartada.
- **Edge-TTS** (gratis pero con internet y no oficial, puede dejar de funcionar): ⚠️ verificar si tiene voces es-DO (acento dominicano). Úsese solo como **plan B / extra opcional**, con Piper como respaldo automático.
- Nube de pago (Azure TTS, ElevenLabs): descartadas por el requisito de gratis.

### Para que suene a Jarvis
1. Voz masculina grave y serena.
2. Efecto ligero con `ffmpeg`/`sox`: un poco de reverb y toque metálico.
3. **No clonar** la voz de un actor real (derechos y riesgo innecesario en un proyecto de grado).

### Para que escuche (opcional)
- **Vosk** (modelo pequeño en español): liviano y rápido en equipos viejos, con menos precisión.
- **faster-whisper** / whisper.cpp: más preciso, más exigente (tamaño *base* es posible).
- **openWakeWord** para la palabra "Jarvis".

### Truco de latencia
**Hablar por frases**: no esperar a que el modelo termine toda la respuesta; cada vez que complete una frase, mandarla a la voz. Empieza a hablar casi de inmediato. Esta división por frases también ayuda a **sincronizar los resaltados** del documento con lo que dice.

---

## 11. Interfaz HUD (estilo Iron Man / Stark Industries)

Referencias visuales que se compartieron: un HUD azul neón con círculo central de anillos, paneles laterales con datos, gráficas, esquinas recortadas; y un escritorio tipo "Stark Industries / Iron Man" con paneles de sistema, reloj, noticias y menú circular inferior.

### Distribución de pantalla
- **Centro**: orbe/anillos animados (la "emoción" y el estado de Jarvis).
- **Panel lateral de medios**: oculto fuera de pantalla; aquí entran imágenes o páginas del PDF.
- **Zona de texto**: la respuesta, escrita letra por letra (efecto máquina de escribir).
- **Paneles decorativos**: hora, estado del sistema, gráficas falsas o reales. Dan ambiente sin costar mucho.

### Animación de entrada de medios
1. El backend envía un paquete con: `texto`, `emocion` y una lista de `medios` (imagen, página del PDF, pie de foto).
2. Si hay medios, el panel **se desliza desde el borde** (p. ej. el derecho) con un pequeño rebote al final.
3. El marco se "dibuja" solo: líneas y esquinas se trazan en ~0.4 s; luego se revela la imagen con un barrido de luz.
4. Mientras tanto el texto empieza a escribirse (todo a la vez).
5. Al terminar, el panel se retira en sentido contrario, o queda si el usuario sigue preguntando sobre lo mismo.

### Detalles "Jarvis"
- Esquinas recortadas (`clip-path`) en los paneles.
- Línea de escaneo sobre la imagen al aparecer.
- Sonido corto y sutil al entrar/salir el panel.
- Carrusel con indicador "1/3" si hay varias imágenes.

### Rendimiento en el equipo viejo
- Animar **solo `transform` y `opacity`** (van por GPU y no traban).
- Evitar desenfoques grandes y sombras pesadas (`blur`, `box-shadow` enormes): son lo que más consume.
- Librería opcional: **GSAP** para encadenar la secuencia (CSS puro también alcanza).

### Pregunta abierta
¿Las imágenes entran siempre del mismo lado, o cambia según el tipo de contenido (fotos por la derecha, datos/gráficas por la izquierda)?

### Boceto del paquete backend → interfaz (idea, no definitivo)
```json
{
  "texto": "…respuesta…",
  "emocion": "seguro",
  "fuente": "documentos",
  "medios": [
    {
      "tipo": "pagina_pdf",
      "src": "/media/doc1_p12.png",
      "pie": "Figura 3, pág. 12",
      "lado": "derecha",
      "timeline": [
        { "en_caracter": 34, "bbox": [x, y, w, h], "estilo": "subrayar" },
        { "en_caracter": 71, "bbox": [x, y, w, h], "estilo": "encerrar" }
      ]
    }
  ]
}
```

---

## 12. Efecto "video de detectives" (zoom, subrayado y cámara)

Caso de uso: pregunta tipo *"¿Qué hizo Thanos?"*. Jarvis responde normal y, mientras dice términos clave ("asesino planetario", "humanidades", "civilizaciones"), **al lado aparece el documento fuente** con zoom dramático, subrayado y una cámara que sigue los datos (la cantidad de personas, los planetas, etc.).

**No es un video real**: es **la página del PDF renderizada como imagen, con una cámara virtual** que se mueve sobre ella. Es más liviano y más fácil de sincronizar.

### Clave: guardar coordenadas de cada palabra
Al procesar el PDF, guardar además del texto **dónde está cada palabra** (caja x, y, ancho, alto).
- PyMuPDF lo da directo (`page.get_text("words")`).
- Si el PDF es escaneado, Tesseract (OCR) también devuelve coordenadas.

### Flujo
1. El RAG encuentra el fragmento que responde. Como ya se guardaron las coordenadas, se sabe en qué parte de la página está.
2. Se eligen las **palabras clave a resaltar**: las que aparecen **tanto en el fragmento como en la respuesta** (nombres propios, números, lugares). Hacerlo **con reglas** (números, mayúsculas, coincidencias), **no con el modelo**: un modelo pequeño falla en esto y las reglas no se equivocan de sitio.
3. El backend arma una **línea de tiempo**: "cuando el texto llegue a la palabra 'planetas', apuntar a esta caja".
4. El frontend reproduce esa línea de tiempo.

### Efectos
- **Cámara**: una sola capa con la página; para "mover la cámara" se cambia `transform: scale() translate()` hacia el centro de la caja. Easing suave y pequeño sobrepaso para dramatismo.
- **Subrayado**: barra que se dibuja de izquierda a derecha (animando `scaleX`), o rectángulo que encierra la palabra.
- **Atenuar el resto**: oscurecer todo menos la zona resaltada (foco de detective).
- **Números importantes**: pulsan o se agrandan un instante.
- **Opcional**: líneas rojas tipo "hilo de corcho" uniendo dos datos resaltados.

### Sincronización con la voz
Lo más simple es anclarla al efecto máquina de escribir: como se conoce la posición de cada palabra en el texto, se dispara el resaltado cuando esa palabra aparece. Si después se agrega voz, sincronizar con el tiempo del audio (o por frases).

### Cuidados
- Renderizar la página **una sola vez en alta resolución** y hacer el zoom con transformaciones (no re-renderizar por cada movimiento).
- Limitar a **3 o 4 resaltados por respuesta**; más se vuelve caótico.
- Para fotos dentro del PDF sirve el mismo sistema: la cámara hace zoom a la región de la imagen.

---

## 13. Grafo de conocimiento ("mapa mental / neuronas conectadas")

Lo que se describió como "mapa mental" se llama **grafo de conocimiento** (Knowledge Graph); con un LLM se conoce como **GraphRAG**.

- En vez de guardar solo fragmentos, se extraen **conceptos (nodos)** y **relaciones (conexiones)**. Ej.: `Proyecto → tiene → Objetivo`, `Objetivo → se mide con → Indicador`. Al preguntar, se localiza el nodo y se siguen sus conexiones.

### Lo que sí mejora
- Respuestas más **claras y conectadas**, sobre todo en preguntas que cruzan varios temas ("¿cómo se relaciona X con Y?").
- Se puede **mostrar el grafo en pantalla** con nodos que se iluminan mientras responde (luce mucho en un proyecto de grado).

### Lo que NO hace
- **No lo hace más rápido por sí solo**: la velocidad depende del modelo y del hardware.
- Construir el grafo desde PDFs es la parte costosa (el LLM debe leer todo y extraer conceptos): en este equipo tarda bastante, pero se hace **una sola vez al subir el archivo**.

### Recomendación por etapas
1. Primero RAG con vectores + filtros (es lo que hace que todo funcione).
2. Después una capa de grafo (NetworkX o Neo4j); los nodos enlazan con los fragmentos del RAG, así se complementan.
3. Visualización del grafo en la interfaz (D3.js o vis.js).

Así hay algo funcionando pronto y el grafo entra como mejora, sin arriesgar el proyecto si el tiempo aprieta.

---

## 14. Rendimiento en el Latitude 5590 (cómo compensar la lentitud)

Estimación orientativa ⚠️ verificar con pruebas reales: un modelo de 3B en 4 bits rinde ~5–10 palabras/s en esta CPU; uno de 7B, ~2–3 palabras/s.

1. **Streaming**: texto y voz empiezan mientras el modelo sigue generando.
2. **Respuestas cortas** (2 frases).
3. **Cachear las preguntas típicas**: si se sabe qué va a preguntar el jurado, dejar esas respuestas y sus animaciones precalculadas.
4. **Calentar el modelo** antes de la presentación (la primera respuesta siempre es la más lenta).
5. Laptop **conectada al cargador** y en modo de alto rendimiento.
6. Con 16 GB se pueden dejar cargados a la vez el modelo principal, el clasificador pequeño y los embeddings, sin intercambiar memoria.
7. Usar el clasificador por embeddings/reglas en vez de una llamada extra al modelo.

---

## 15. Orden sugerido de construcción

Cada paso debe quedar funcionando antes de pasar al siguiente, para siempre tener algo demostrable.

1. **Linux + Ollama** respondiendo en terminal.
2. **Ingesta de PDFs + RAG básico** con Chroma (guardando coordenadas de palabras e imágenes con página y pie de foto).
3. **Clasificador y filtros** (inapropiadas, conocimiento general, fuera de alcance; diccionario de dominicanismos; banco de frases; bitácora).
4. **Interfaz web** con el orbe y las emociones (WebSocket con el backend).
5. **Panel de medios** con animación de entrada y **resaltados/zoom estilo detective**.
6. **Voz (Piper)** con frases en streaming y, por último, el **oído (Vosk)** y la palabra de activación.
7. **Extras**: grafo de conocimiento, paneles decorativos HUD, efectos de sonido.
8. **Pruebas con gente**, ampliar el banco de frases de la bitácora, cachear respuestas típicas, **clonar el disco**.

---

## 16. Decisiones tomadas vs. preguntas abiertas

### Decididas / acordadas
- Enfoque **RAG local** (sin fine-tuning).
- Todo **gratis** y, preferiblemente, **local** (Piper para voz).
- Clasificador previo al RAG con filtros por capas (incluyendo la capa de "exigir similitud con los documentos").
- Respuestas fijas para los regaños + personalidad Jarvis (máx. 2 frases).
- Emociones simuladas con orbe/HUD; panel de medios con animación lateral; efecto detective con cámara virtual sobre la página del PDF.
- Responder también **conocimiento general**, mostrando de dónde viene cada respuesta.
- Linux en la laptop (Ubuntu 24.04 LTS o Mint sugeridos), Chromium en modo kiosco.
- Grafo de conocimiento como **mejora posterior**, no como base.

### Abiertas
1. **Tema de los documentos del proyecto** (define qué es `FUERA_DE_TEMA` / `FUERA_DE_ALCANCE`).
2. **Fecha de entrega** del proyecto (define hasta dónde llegar).
3. ¿PDFs **digitales o escaneados**? (¿hace falta OCR?).
4. ¿Orbe abstracto o cara con expresiones?
5. ¿Imágenes siempre del mismo lado o según el tipo de contenido?
6. ¿Tono **británico clásico** o **más dominicano**?
7. ¿Qué tipo de preguntas generales esperan que hagan más? (define si vale la pena la mini base de datos local).
8. ¿Modelo de 3B o probar uno de 7B tras medir velocidad real?
9. ¿Qué distro exactamente (Ubuntu 24.04 LTS / Mint)?

---

## 17. Cosas a verificar antes de depender de ellas

- Especificaciones exactas del Latitude 5590 (procesador y si trae GPU dedicada).
- Que Piper tenga las voces en español que se quieren y revisar su licencia.
- Si Edge-TTS ofrece voces dominicanas (es-DO) y si sigue funcionando (no es oficial).
- Velocidades reales de los modelos de 3B y 7B en esta laptop.
- Calidad real de Vosk frente a faster-whisper en español con acento dominicano.
- Que la sincronización palabra↔coordenada funcione bien con los PDFs reales del proyecto (especialmente si son escaneados).
