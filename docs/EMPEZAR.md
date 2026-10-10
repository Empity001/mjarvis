# Cómo empezar con M-Jarvis

M-Jarvis es un asistente del universo Marvel que corre **completo en la Latitude**, sin internet y sin enviar nada a la nube. Esta guía es para quien lo usa por primera vez. Elija su caso:

- [Quiero hablar con Jarvis](#1-hablar-con-jarvis) (visitantes, el público)
- [Voy a encargarme del equipo en la exhibición](#2-encender-y-preparar-la-latitude)
- [Quiero manejarlo a escondidas desde otra computadora o celular](#3-el-manager)
- [Quiero enseñarle cosas o revisar lo que aprendió](#4-enseñarle-y-revisar-lo-que-aprendió)

---

## 1. Hablar con Jarvis

1. Abra el chat. En la pantalla de la Latitude ya está abierto. Desde un celular o una laptop, conéctese a la Wi‑Fi **M‑Jarvis** (la contraseña se la da el dueño) y el chat se abre solo. Si no, entre a `http://10.42.0.1:8080`.
2. Escriba una pregunta abajo, por ejemplo *«¿Quién es Thanos?»*. También puede tocar una de las sugerencias.
3. Para **hablarle**, toque el micrófono, diga la pregunta y espere un momento. La voz y el micrófono funcionan en la pantalla de la Latitude; en celulares el micrófono se oculta por seguridad del navegador, pero se puede escribir.
4. Para **cortar** una respuesta larga, toque el botón de parar.

**Lo que sabe:** Marvel (personajes, películas, Gemas del Infinito, Vengadores, etc.) y las notas que tiene guardadas. **Lo que no hace:** buscar en internet ni saber de hoy. Si no sabe algo, lo dice.

**Consejos:**
- Preguntas cortas y claras funcionan mejor.
- Si pregunta algo personal o triste, le responde con cortesía y **no guarda** esa conversación.
- No le dé datos privados: lo que se le cuente puede quedar esperando aprobación para ser guardado (ver el punto 4).

---

## 2. Encender y preparar la Latitude

1. Conecte la Latitude a la corriente y enciéndala. Jarvis arranca solo con el sistema.
2. Haga doble clic en el icono **M‑Jarvis** del escritorio. Sale un menú:

| Opción | Para qué sirve |
|---|---|
| **Todo junto** | Chat y red neuronal en la misma pantalla |
| **Solo chat** | Solo la conversación (lo normal para la exhibición) |
| **Solo red neuronal** | El mapa a pantalla completa |
| **Panel** | Archivos, estado del sistema y últimas preguntas |
| **Conectar** | Códigos QR y direcciones para otros equipos |
| **Wi‑Fi propia** | Crea la red «M‑Jarvis» donde no hay red |
| **Manager** | La consola de control (punto 3) |
| **Compartir** | Direcciones y la clave de gestión |
| **Cerrar pantalla** | Cierra la ventana abierta |

3. Para exhibición, elija **Solo chat** y conecte la Latitude a la pantalla. Para volver al menú, cierre con **Alt+F4**.

**La red se acomoda sola.** La Latitude busca, en este orden: Wi‑Fi con internet → internet por cable (otra laptop que le preste) → una red sin internet → y, si no hay nada, crea su propia Wi‑Fi «M‑Jarvis». No necesita internet para funcionar; el internet solo sirve para actualizarla.

**Antes de la exhibición, revise:**
- [ ] Está enchufada (la batería no dura todo el evento).
- [ ] Responde una pregunta de prueba.
- [ ] La voz suena (si va a usarla) y el micrófono escucha.
- [ ] El Manager abre desde su celular o laptop (punto 3).
- [ ] Temperatura normal en la pestaña **Sistema** del Manager.

---

## 3. El Manager

Es una consola para vigilar y mandar **sin que nadie lo note**, desde otra computadora (Windows, Mac o Linux) o un celular.

**Cómo entrar:**
- Desde la misma red, abra `http://10.42.0.1:8080/manager.html` (o la dirección que muestre «Compartir»). En «Red → Conectar un dispositivo» elija su equipo y siga los pasos; también puede descargar un acceso directo que lo busca solo.
- La primera vez que mande una orden pide la **clave de gestión**: la ve en la Latitude, en el menú **Compartir**.

**Qué hay en cada pestaña:**
- **Ahora:** las preguntas y respuestas en vivo, con su calidad y los fallos. Botones: **Detener** (corta la respuesta), **Silenciar la voz** y **Bloquear el teclado** de la pantalla para que el público no escriba.
- **Red:** qué modo eligió la Latitude y por qué, quién está conectado y cómo conectar un celular o una computadora.
- **Aprender:** lo que quedó por aprobar y las respuestas que conviene revisar.
- **Decir:** haga que Jarvis diga algo en pantalla, o que la pantalla pregunte algo y Jarvis responda (para el teatro).
- **Sistema:** temperatura, memoria, procesador, disco y batería.

**Truco para la exhibición:** bloquee el teclado y silencie la voz si hay mucho ruido; use **Decir** para guiar la demostración.

---

## 4. Enseñarle y revisar lo que aprendió

Jarvis puede aprender de lo que le cuentan, pero **nada se vuelve cierto hasta que usted lo aprueba**.

1. Abra **Manager → Aprender** (o el **Panel**).
2. Revise los **datos por aprobar**: apruebe los correctos, descarte los demás.
3. Mire las **respuestas por revisar**: son las que sacaron mala nota o tuvieron algún fallo.
4. En el **Panel** está el **Auto‑entrenado**: Jarvis se evalúa solo y propone mejoras; usted decide cuáles aplicar y puede deshacerlas.
5. El **modo de aprendizaje** se apaga desde la misma pestaña si no quiere que guarde nada.

---

## Si algo falla

| Síntoma | Qué hacer |
|---|---|
| No abre el chat desde el celular | Confirme que está en la Wi‑Fi «M‑Jarvis»; revise en el Manager (Red) que esté encendida |
| No hay Wi‑Fi «M‑Jarvis» | En el menú de la Latitude, **Wi‑Fi propia** → encender (la primera vez pide una contraseña) |
| Responde lento | Es normal con preguntas largas; espere. Mire **Sistema** por si está caliente |
| No suena la voz | Revise que **Silenciar la voz** esté apagado en el Manager y el volumen de la Latitude |
| La pantalla no deja escribir | Está bloqueada desde el Manager: desactive **Bloquear el teclado** |
| Algo se trabó | **Detener** en el Manager; si sigue, cierre con Alt+F4 y abra de nuevo |
