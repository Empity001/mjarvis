'use strict';
// Control: ver lo que pasa y manejarlo a escondidas desde otro equipo. Se abre con la clave de gestión.
// Las órdenes llegan a la pantalla de la Latitude por el canal en vivo (/api/eventos).
const Control = (() => {
  const PARTES = [['ahora', 'Ahora', 'ahora'], ['escenario', 'Escenario', 'escenario'], ['aprender', 'Aprender', 'aprender'], ['archivos', 'Archivos', 'carpeta'], ['red', 'Red', 'red'], ['sistema', 'Sistema', 'sistema']];
  const RUTAS = { documentos: 'De mis notas', general: 'Conocimiento general', trato: 'Trato', filtro: 'Filtro', sistema: 'Sistema', memoria: 'Memoria', aprendizaje: 'Aprendizaje', ocupado: 'Ocupado' };
  const MOTORES = { 'groq-120b': 'GPT-OSS 120B', 'groq-qwen': 'Qwen 27B', 'groq-20b': 'GPT-OSS 20B', gemini: 'Gemini' };
  const MODOS = { nube: ['En línea por Wi-Fi', 'wifi', 'var(--ok)', 'Hay una Wi-Fi con internet: todo disponible.'], puente: ['En línea por el cable', 'cable', 'var(--ok)', 'No hay Wi-Fi, pero hay internet por el cable.'],
    lan: ['Red sin internet', 'red', 'var(--aviso)', 'Hay red, pero sin internet: M-Jarvis sirve solo a esa red.'], local: ['Con su propia red', 'conectar', '#b48cf2', 'No hay redes: M-Jarvis creó la suya.'],
    buscando: ['Buscando red…', 'conectar', 'var(--apagado)', 'Mirando qué redes hay.'] };
  const ICONO_MODO = { wifi: 'conectar', cable: 'cable', red: 'red', conectar: 'conectar' };
  let raiz = null, ex = { silencio: false, bloqueado: false }, nubeEstado = null, redEstado = null;
  let flujo = [], tarjeta = null, etapa = null, canal = null, enLinea = false;

  // ---------- Entrada ----------
  function montar(cuerpo, derecha, sub) {
    raiz = cuerpo; const parte = PARTES.some(p => p[0] === sub) ? sub : 'ahora';
    const previo = derecha.firstChild;   // si el selector ya está, solo se desliza el cristal hacia la sección nueva
    if (previo && previo.poner) previo.poner(parte);
    else derecha.append(segmentos(PARTES.map(p => ({ id: p[0], texto: p[1], icono: p[2], compacta: true })), parte, (id) => { location.hash = '#control/' + id; }));
    conectarCanal(); refrescarCuentas(); ciclo(20000, refrescarCuentas);
    ({ ahora, escenario, aprender, archivos, red, sistema })[parte](cuerpo);
  }

  // ---------- Canal en vivo ----------
  function conectarCanal() {
    if (canal) return;
    canal = new EventSource('api/eventos');
    canal.onopen = () => { enLinea = true; pintarEstado(); }; canal.onerror = () => { enLinea = false; pintarEstado(); };
    canal.onmessage = (m) => { try { evento(JSON.parse(m.data)); } catch (e) { console.error(e); } };
  }
  function evento(d) {
    if (d.tipo === 'pregunta') {
      const t = el('div', 'turno espera'), r = el('p', 'r', 'Pensando…'); t.append(el('p', 'q', d.texto), r); t.r = r; t.pregunta = d.texto; tarjeta = t; etapa = 'piensa';
      flujo.unshift(t); flujo.length = Math.min(flujo.length, 40); const f = document.getElementById('flujo'); if (f) { const v = document.getElementById('sin-flujo'); if (v) v.remove(); f.prepend(t); while (f.children.length > 40) f.lastChild.remove(); }
      pintarEstado('vivo');
    } else if (d.tipo === 'inicio' && tarjeta) { tarjeta.fuente = d.fuente; tarjeta.nodos = d.nodos || [];
    } else if (d.tipo === 'texto' && tarjeta) { if (etapa === 'piensa') { tarjeta.r.textContent = ''; tarjeta.classList.remove('espera'); etapa = 'texto'; } tarjeta.r.textContent += d.t;
    } else if (d.tipo === 'fin' && tarjeta) {
      const t = tarjeta; tarjeta = null; etapa = null; pintarEstado();
      const meta = el('div', 'meta'); t.append(meta); if (t.fuente) meta.append(ficha(RUTAS[t.fuente] || t.fuente)); if (d.segundos != null) meta.append(ficha(`${d.segundos} s`)); const m = chipMotor(d.motor); if (m) meta.append(m);
      setTimeout(() => enriquecer(t, meta), 400);
    } else if (d.tipo === 'orden' && d.accion === 'exhibicion') { ex = { silencio: !!d.silencio, bloqueado: !!d.bloqueado }; pintarMandos();
    } else if (d.tipo === 'ingesta') ingesta(d);
  }
  async function enriquecer(t, meta) {   // la bitácora ya trae la habilidad usada, la calidad y los fallos de esa respuesta
    try {
      const b = (await get('api/bitacora')).find(x => x.pregunta === t.pregunta); if (!b) return;
      if (b.receta) meta.append(ficha('habilidad: ' + b.receta.replace(/_/g, ' ')));
      if (b.calidad != null) meta.append(ficha(`calidad ${b.calidad}`, b.calidad >= 80 ? 'bien' : 'aviso'));
      (b.fallos || []).forEach(f => meta.append(ficha(f.replace(/_/g, ' '), 'aviso'))); refrescarCuentas();
    } catch (e) { /* no pasa nada */ }
  }
  const ficha = (texto, tono, ico) => { const f = el('span', 'ficha' + (tono ? ' ' + tono : '')); if (ico) f.append(icono(ico)); else if (tono) f.append(el('i')); f.append(el('span', null, texto)); return f; };
  function chipMotor(m) { if (!m) return null; const f = ficha(m === 'local' ? 'En la Latitude' : 'Nube · ' + (MOTORES[m] || m), m === 'local' ? '' : 'nube', m === 'local' ? 'chip' : 'nube'); return f; }
  async function refrescarCuentas() {
    try {
      const [ap, bit] = await Promise.all([get('api/aprendizaje'), get('api/bitacora')]);
      const pend = (ap.pendientes || []).length, dudosas = bit.filter(b => (b.fallos || []).length || (b.calidad != null && b.calidad < 80)).length;
      const c = document.getElementById('cuenta-aprender'); if (c) { c.hidden = !(pend + dudosas); c.textContent = pend + dudosas; }
      const av = document.getElementById('avisos-alertas'); if (av) { av.replaceChildren(); const a = el('a', 'ficha ' + (pend || dudosas ? 'aviso' : 'bien')); a.href = '#control/aprender'; a.append(el('i'), el('span', null, pend || dudosas ? `${pend + dudosas} por revisar` : 'Todo en orden')); av.append(a); }
    } catch (e) { /* sin red un momento */ }
  }
  function pintarEstado(modo) {
    const f = document.getElementById('estado-vivo'); if (!f) return; f.className = 'ficha ' + (modo === 'vivo' ? 'vivo' : enLinea ? 'bien' : 'mal'); f.lastChild.textContent = modo === 'vivo' ? 'Respondiendo…' : enLinea ? 'En vivo' : 'Reconectando…';
  }

  // ---------- Ahora ----------
  function mando(id, ico, titulo, accion) {
    const b = el('button', 'mando'); b.type = 'button'; b.id = id; const m = el('span', 'moneda'); m.append(icono(ico)); const t = el('span'); t.append(el('b', null, titulo), el('small')); b.append(m, t); b.onclick = accion; return b;
  }
  function pintarMandos() {
    const poner = (id, { activo, ico, texto, tono, alerta }) => { const b = document.getElementById(id); if (!b) return; b.setAttribute('aria-pressed', String(!!activo)); b.classList.toggle('alerta', !!alerta);
      b.style.setProperty('--tono', tono || ''); b.querySelector('small').textContent = texto; if (ico) { const m = b.querySelector('.moneda'); m.replaceChildren(icono(ico)); } };
    poner('m-voz', { activo: !ex.silencio, ico: ex.silencio ? 'vozno' : 'voz', texto: ex.silencio ? 'En silencio' : 'Se escucha' });
    poner('m-teclado', { activo: !ex.bloqueado, texto: ex.bloqueado ? 'Bloqueado' : 'Libre', tono: 'var(--ok)', alerta: ex.bloqueado });
    const n = nubeEstado, con = n && n.proveedores.some(p => p.con_clave);
    poner('m-nube', { activo: n && n.activo && con, texto: !n ? '…' : !con ? 'Falta la clave' : n.activo ? 'Activada' : 'Apagada' });
  }
  function ahora(cuerpo) {
    const mandos = el('div', 'mandos');
    mandos.append(mando('m-voz', 'voz', 'Voz', () => mandar('api/exhibicion', { silencio: !ex.silencio }).then(r => { if (r) { ex = r; pintarMandos(); } })),
      mando('m-teclado', 'teclado', 'Teclado', () => mandar('api/exhibicion', { bloqueado: !ex.bloqueado }).then(r => { if (r) { ex = r; pintarMandos(); } })),
      mando('m-nube', 'nube', 'Nube gratis', () => { const con = nubeEstado && nubeEstado.proveedores.some(p => p.con_clave); if (!con) { location.hash = '#control/sistema'; avisar('Primero hay que ponerle una clave.'); return; }
        mandar('api/nube', { activo: !nubeEstado.activo }).then(r => { if (r) { nubeEstado = r; pintarMandos(); } }); }),
      Object.assign(mando('m-parar', 'parar', 'Parar', () => mandar('api/detener', {}, 'Detenido.')), { className: 'mando parar' }));
    mandos.lastChild.querySelector('small').textContent = 'Corta la respuesta'; escalonar(mandos);
    const fichas = el('div', 'avisos'); const e = el('span', 'ficha'); e.id = 'estado-vivo'; e.append(el('i'), el('span', null, 'Conectando…')); fichas.append(e);
    const al = el('span'); al.id = 'avisos-alertas'; fichas.append(al); const rd = el('span'); rd.id = 'ficha-red'; fichas.append(rd); const tp = el('span'); tp.id = 'ficha-temp'; fichas.append(tp);
    const cols = el('div', 'ahora'), izq = el('div'); izq.append(el('h2', 'titulo-2', 'En vivo')); const fl = el('div'); fl.id = 'flujo'; izq.append(fl);
    if (flujo.length) flujo.forEach(t => fl.append(t)); else { fl.append(Object.assign(el('p', 'vacio', 'Esperando la primera pregunta…'), { id: 'sin-flujo' })); precargar(fl); }
    const der = el('div', 'mapa-vivo'); der.append(el('h2', 'titulo-2', 'Ruta de conexiones'));
    if (matchMedia('(min-width: 861px)').matches) { const f = el('iframe'); f.title = 'Ruta de conexiones en vivo'; der.append(f); encuadrar(f);
      const cargar = () => { f.src = 'grafo/?embebido=1'; };   // el mapa es lo más pesado (1,8 MB): después de lo importante, en un rato libre
      if (window.requestIdleCallback) requestIdleCallback(cargar, { timeout: 2500 }); else setTimeout(cargar, 1200); }
    cols.append(izq, der); cuerpo.append(mandos, fichas, cols);
    pintarMandos(); pintarEstado();
    get('api/exhibicion').then(r => { ex = r; pintarMandos(); }).catch(() => {}); get('api/nube').then(r => { nubeEstado = r; pintarMandos(); }).catch(() => {});
    ciclo(8000, cabecera);
  }
  async function cabecera() {
    try {
      const [e, r] = await Promise.all([get('api/estado'), get('api/red')]); redEstado = r; const t = e.lecturas.temperatura;
      const rd = document.getElementById('ficha-red'); if (rd) { const [txt, ico, color] = MODOS[r.modo] || MODOS.buscando; rd.replaceChildren(Object.assign(ficha(txt, '', ICONO_MODO[ico]), {})); rd.firstChild.style.setProperty('color', color); }
      const tp = document.getElementById('ficha-temp'); if (tp) tp.replaceChildren(ficha(t != null ? `${Math.round(t)} °C` : '—', t > 88 ? 'mal' : t > 75 ? 'aviso' : 'bien'));
      const eq = r.clientes.length; if (rd && eq) rd.append(ficha(`${eq} equipo${eq > 1 ? 's' : ''} conectado${eq > 1 ? 's' : ''}`, 'vivo'));
    } catch (e) { /* sin respuesta un momento */ }
  }
  async function precargar(fl) {   // para no empezar en blanco: las últimas respuestas que ya se dieron
    try {
      const previas = (await get('api/bitacora')).slice(0, 6).reverse(); if (!previas.length || flujo.length) return; const v = document.getElementById('sin-flujo'); if (v) v.remove();
      previas.forEach(b => {
        const t = el('div', 'turno'), meta = el('div', 'meta'); t.append(el('p', 'q', b.pregunta), el('p', 'r', b.respuesta), meta);
        meta.append(ficha(RUTAS[b.fuente] || b.fuente), ficha(`${b.total_s} s`)); const m = chipMotor(b.motor); if (m) meta.append(m);
        if (b.receta) meta.append(ficha('habilidad: ' + b.receta.replace(/_/g, ' ')));
        if (b.calidad != null) meta.append(ficha(`calidad ${b.calidad}`, b.calidad >= 80 ? 'bien' : 'aviso')); (b.fallos || []).forEach(f => meta.append(ficha(f.replace(/_/g, ' '), 'aviso')));
        t.pregunta = b.pregunta; flujo.unshift(t); fl.prepend(t);
      });
    } catch (e) { /* sin red un momento */ }
  }

  // ---------- Escenario: el teatro ----------
  function escenario(cuerpo) {
    let modo = 'decir';
    cuerpo.append(el('p', 'ayuda', 'Para el espectáculo. Lo que escribas aparece en la pantalla de la Latitude: o como si lo dijera Jarvis, o como si alguien se lo preguntara.'));
    const caja = el('div', 'pieza escenario'); const t = el('textarea'); t.setAttribute('aria-label', 'Texto'); const q = el('input'); q.type = 'text'; q.setAttribute('aria-label', 'Pregunta');
    const fila = el('div', 'entrada'), b = el('button', 'boton principal'); b.type = 'button'; b.append(icono('enviar'), el('span', null, 'Enviar'));
    const ver = () => { t.hidden = modo !== 'decir'; q.hidden = modo !== 'preguntar'; t.placeholder = 'Lo que Jarvis dirá (en voz alta también, si la voz está activa)'; q.placeholder = 'Una pregunta que se escribe sola en la pantalla'; };
    const frases = JSON.parse(guardado('mjarvis-frases') || '["Buenas. Soy M-Jarvis, y estoy a su servicio.", "¿Quién es Thanos?", "¿Qué son las Gemas del Infinito?"]');
    const enviar = async () => { const v = (modo === 'decir' ? t.value : q.value).trim(); if (!v) return; const r = await mandar(modo === 'decir' ? 'api/decir' : 'api/pantalla', { texto: v }, modo === 'decir' ? 'Enviado a la pantalla.' : 'La pantalla lo está preguntando.'); if (r) { t.value = q.value = ''; } };
    b.onclick = enviar; q.onkeydown = (e) => { if (e.key === 'Enter') enviar(); };
    const seg = segmentos([{ id: 'decir', texto: 'Que Jarvis diga' }, { id: 'preguntar', texto: 'Que pregunte' }], modo, (id) => { modo = id; ver(); });
    const at = el('div', 'fila-botones'), pintar = () => { at.replaceChildren(...frases.map((f, i) => { const x = el('button', 'boton chico', f.length > 40 ? f.slice(0, 38) + '…' : f); x.type = 'button'; x.title = f + ' (clic derecho para quitarla)';
      x.onclick = () => { t.value = q.value = f; (modo === 'decir' ? t : q).focus(); }; x.oncontextmenu = (e) => { e.preventDefault(); frases.splice(i, 1); guardado('mjarvis-frases', JSON.stringify(frases)); pintar(); }; return x; })); };
    const g = el('button', 'boton chico', 'Guardar como frase rápida'); g.type = 'button'; g.onclick = () => { const v = (modo === 'decir' ? t.value : q.value).trim(); if (v) { frases.push(v); guardado('mjarvis-frases', JSON.stringify(frases)); pintar(); avisar('Guardada. Clic derecho sobre una frase para quitarla.'); } };
    fila.append(q, b); caja.append(seg, t, fila, el('h2', 'titulo-2', 'Frases rápidas'), at, g); pintar(); ver(); cuerpo.append(caja);
  }

  // ---------- Aprender: lo que aprende, el auto-entrenado, las habilidades y el historial ----------
  let tabApr = 'datos', cicloApr = 0;
  const redondo = (ico, etiqueta, f, clase) => { const b = el('button', 'boton redondo ' + (clase || '')); b.type = 'button'; b.setAttribute('aria-label', etiqueta); b.title = etiqueta; b.append(icono(ico)); b.onclick = f; return b; };
  const sec = (t) => { const s = el('div'); s.append(el('h2', 'titulo-2', t)); return s; };
  const fila = (a, b, botones = []) => { const f = el('div'), c = el('div', 'cuerpo'); c.append(el('b', null, a)); if (b) c.append(el('small', null, b)); f.append(c); botones.forEach(x => f.append(x)); return f; };
  const refrescando = (ms, f) => { clearInterval(cicloApr); cicloApr = setInterval(() => { if (!document.getElementById('ap')) return clearInterval(cicloApr); if (!document.hidden) f(); }, ms); };
  function aprender(cuerpo) {
    const z = el('div'); z.id = 'ap';
    const seg = segmentos([{ id: 'datos', texto: 'Lo que aprende' }, { id: 'entreno', texto: 'Auto-entrenado' }, { id: 'habilidades', texto: 'Habilidades' }, { id: 'historial', texto: 'Historial' }], tabApr, (id) => { tabApr = id; pintarApr(); });
    seg.style.marginBottom = '14px'; cuerpo.append(seg, z); pintarApr();
  }
  function pintarApr() {
    const z = document.getElementById('ap'); if (!z) return; delete z.dataset.firma; z.replaceChildren(); clearInterval(cicloApr);
    ({ datos: pintarDatos, entreno: pintarEntreno, habilidades: pintarHabilidades, historial: pintarHistorial })[tabApr](z);
  }
  async function pintarDatos(z0) {
    const z = z0 || document.getElementById('ap'); if (!z) return; let ap, bit; try { [ap, bit] = await Promise.all([get('api/aprendizaje'), get('api/bitacora')]); } catch (e) { return; }
    const firma = JSON.stringify([ap, bit.slice(0, 12).map(b => b.hora)]); if (z.dataset.firma === firma) return; z.dataset.firma = firma;
    const cambiar = async (cuerpo, ok) => { await mandar('api/aprendizaje', cuerpo, ok); pintarDatos(); refrescarCuentas(); };
    const pend = sec(`Por aprobar (${(ap.pendientes || []).length})`); const lp = el('div', 'lista');
    if (!(ap.pendientes || []).length) pend.append(el('p', 'vacio', 'Nada por ahora. Lo que alguien le cuente a Jarvis esperará aquí; no lo da por cierto hasta que lo apruebes.'));
    (ap.pendientes || []).forEach(x => lp.append(fila(x.texto, null, [redondo('x', 'Descartar', () => cambiar({ descartar: x.archivo }, 'Descartado.'), 'peligro'), redondo('ok', 'Aprobar', () => cambiar({ aprobar: x.archivo }, 'Aprobado.'), 'principal')]))); pend.append(lp);
    const dudas = bit.filter(b => (b.fallos || []).length || (b.calidad != null && b.calidad < 80)); const rev = sec(`Por revisar (${dudas.length})`); const lr = el('div', 'lista');
    if (!dudas.length) rev.append(el('p', 'vacio', 'Las últimas respuestas cumplen las reglas.'));
    dudas.slice(0, 10).forEach(b => { const f = fila(b.pregunta, b.respuesta.slice(0, 150) + (b.respuesta.length > 150 ? '…' : '')); const m = el('div', 'meta'); m.style.marginTop = '8px'; (b.fallos || []).forEach(x => m.append(ficha(x.replace(/_/g, ' '), 'aviso'))); if (b.calidad != null) m.append(ficha(`calidad ${b.calidad}`)); f.firstChild.append(m); lr.append(f); }); rev.append(lr);
    const lista = (titulo, pares, vacio, accion) => { const s = sec(`${titulo} (${pares.length})`), l = el('div', 'lista'); if (!pares.length) s.append(el('p', 'vacio', vacio)); pares.forEach(([a, b, orden]) => l.append(fila(a, b, [redondo('x', 'Olvidar', () => cambiar(orden, 'Olvidado.'), 'peligro')]))); s.append(l); return s; };
    const resp = lista('Respuestas que aprendió', Object.entries(ap.respuestas || {}).map(([d, r]) => [`«${d}»`, r, { olvidar_respuesta: d }]), 'Ninguna todavía.');
    const perd = lista('Mensajes que aprendió a no tomar a mal', (ap.inofensivas || []).map(f => [`«${f}»`, null, { olvidar_inofensiva: f }]), 'Ninguno todavía.');
    const modo = sec('Aprender conversando'); const lm = el('div', 'lista');
    lm.append(fila(ap.activo ? 'Encendido' : 'Apagado', ap.activo ? 'Guarda respuestas («cuando te digan X, responde Y»), correcciones y datos («aprende que…»). Los datos esperan tu aprobación. Nunca aprende groserías.' : 'Conversa igual, pero no guarda nada.', [interruptor(ap.activo, (v) => cambiar({ activo: v }, v ? 'Aprendizaje encendido.' : 'Aprendizaje apagado.'), 'Aprender conversando')])); modo.append(lm);
    const g = el('div', 'dos'), c1 = el('div'), c2 = el('div'); c1.append(pend, rev); c2.append(modo, resp, perd); g.append(c1, c2); z.replaceChildren(g);
    refrescando(8000, () => pintarDatos());
  }
  const NOMBRES = { completa: 'Respuesta cortada', longitud: 'Extensión', tratamiento: 'Trato con género', 'regaño': 'Regaños', muletilla: 'Muletillas', primera_persona: 'Primera persona', si_no_incoherente: '«Sí/No» incoherente',
    nombre_dudoso: 'Nombres sin respaldo', aviso_cifras: 'Cifras sin respaldo', velocidad: 'Lentitud', 'grosería_sin_filtro': 'Grosería sin filtrar', 'sin_empatía': 'Falta de empatía', rechazada_por_usuario: 'Corregida por la persona',
    repetida: 'Frase repetida', esperado: 'No dijo lo esperado', prohibido: 'Dijo algo prohibido', ruta: 'Salió por otra ruta', error: 'Error' };
  const dato = (a, b, tono) => { const f = el('div', 'dato'), v = el('b', null, b); if (tono) v.style.color = tono; f.append(el('span', null, a), v); return f; };
  async function entrenoAccion(orden) {
    const r = await orden_('api/autoentreno', orden); if (r && r.error) avisar(r.error, true); delete (document.getElementById('ap') || {}).dataset?.firma; pintarEntreno();
  }
  const orden_ = (ruta, cuerpo) => mandar(ruta, cuerpo);
  async function pintarEntreno(z0) {
    const z = z0 || document.getElementById('ap'); if (!z) return; let e; try { e = await get('api/autoentreno'); } catch (x) { return; }
    const firma = JSON.stringify(e); if (z.dataset.firma === firma) return; z.dataset.firma = firma;
    const u = e.ultimo, ej = e.ejecutando, raiz = el('div');
    raiz.append(el('p', 'ayuda', 'Jarvis no reentrena su modelo (no se puede sin estropearlo en este equipo). Lo que hace es evaluarse con una rúbrica, practicar unos 300 escenarios y proponer cambios: palabras para el filtro y variantes de sus frases. Nada se aplica solo: tú apruebas cada propuesta, y si al aplicarla empeoran las pruebas, se deshace sola.'));
    const cab = el('div', 'fila-botones'); cab.style.cssText = 'align-items:center;margin-bottom:6px';
    cab.append(ficha(ej.corriendo ? 'Entrenando…' : u ? `Último: ${u.fecha} · ${u.cumple_meta ? 'cumple la meta' : 'aún no cumple la meta'}` : 'Aún no se ha ejecutado', ej.corriendo ? 'vivo' : u && u.cumple_meta ? 'bien' : u ? 'aviso' : ''));
    const bt = (t, f, clase, off) => { const b = el('button', 'boton chico ' + (clase || ''), t); b.type = 'button'; b.disabled = !!off; b.onclick = f; return b; };
    cab.append(bt('Rápido', () => entrenoAccion({ accion: 'rapido' }), 'principal', ej.corriendo), bt('Práctica completa (usa el modelo)', () => entrenoAccion({ accion: 'completo' }), '', ej.corriendo));
    if (ej.corriendo) cab.append(bt('Cancelar', () => entrenoAccion({ accion: 'cancelar' }), 'peligro'));
    raiz.append(cab);
    const auto = el('div', 'lista'); auto.append(fila('Análisis automático cada 6 horas', null, [interruptor(e.automatico, (v) => entrenoAccion({ accion: 'automatico', valor: v }), 'Análisis automático')])); raiz.append(auto);
    if (ej.corriendo) { const br = el('div', 'barra'), i = el('i'); i.style.transform = `scaleX(${ej.total ? ej.hecho / ej.total : .08})`; br.append(i); raiz.append(br, el('p', 'pie-nota', `${ej.paso} (${Math.round(ej.transcurrido)} s)`)); }
    const c1 = el('div'), c2 = el('div'), g = el('div', 'dos');
    if (u) {
      const calidad = (u.practica || u.bitacora || {}).puntaje_medio, meta = (e.reglas.meta || {}).puntaje_minimo_bueno || 80; const s1 = sec('Cómo va');
      s1.append(dato(`Calidad ${u.practica ? '(práctica)' : '(bitácora)'}`, calidad != null ? `${calidad}/100` : '—', calidad >= meta ? 'var(--ok)' : 'var(--aviso)'));
      if (u.pruebas) s1.append(dato('Pruebas de comportamiento', `${u.pruebas.total - u.pruebas.fallaron}/${u.pruebas.total}`, u.pruebas.fallaron ? 'var(--aviso)' : 'var(--ok)'));
      if (u.bitacora && u.bitacora.n) s1.append(dato(`Fallos críticos en ${u.bitacora.n} respuestas reales`, String(u.bitacora.criticos), u.bitacora.criticos ? 'var(--aviso)' : 'var(--ok)'));
      if (u.practica) { const x = u.practica.extension; s1.append(dato('Extensión adecuada', `${x.dentro}/${x.dentro + x.cortas + x.largas} (${x.cortas} cortas, ${x.largas} largas)`)); }
      s1.append(dato('Frente a la vez anterior', `${u.veredicto} · ${u.duracion_s} s`)); c1.append(s1);
    }
    const sp = sec(`Propuestas por aprobar (${e.propuestas.length})`), lp = el('div', 'lista'); if (!e.propuestas.length) sp.append(el('p', 'vacio', 'Ninguna por revisar.'));
    e.propuestas.forEach(p => lp.append(fila(p.tipo === 'filtro_palabra' ? `Añadir «${p.valor}» al filtro (${p.categoria})` : `Nueva frase para «${p.categoria}»: ${p.valor}`, p.motivo,
      [redondo('x', 'Descartar', () => entrenoAccion({ accion: 'descartar', id: p.id }), 'peligro'), redondo('ok', 'Aprobar', () => entrenoAccion({ accion: 'aprobar', id: p.id }), 'principal')]))); sp.append(lp); c1.append(sp);
    const fallos = u ? [...(u.bitacora.por_criterio || []).slice(0, 5).map(f => [`${NOMBRES[f.id] || f.id} · ${f.conteo} veces`, f.ejemplos[0] && `«${f.ejemplos[0].pregunta}» → ${f.ejemplos[0].detalle}`]),
      ...(u.practica ? (u.practica.peores || []).slice(0, 3).map(r => [`Práctica ${r.puntaje}/100 · «${r.pregunta}»`, r.fallos.join(' · ') || '—']) : []),
      ...(u.pruebas && u.pruebas.fallos ? u.pruebas.fallos.slice(0, 3).map(f => [`Prueba ${f.id} · «${f.entrada}»`, f.motivos.join(' · ')]) : [])] : [];
    const sf = sec('Lo que falló más'), lf = el('div', 'lista'); if (!fallos.length) sf.append(el('p', 'vacio', 'Nada que reportar.')); fallos.forEach(([a, b]) => lf.append(fila(a, b))); sf.append(lf); c2.append(sf);
    const det = (t, ...hijos) => { const d = el('details', 'plegable'); d.append(el('summary', null, t), ...hijos); return d; };
    const tend = el('div'); e.tendencia.forEach(x => tend.append(dato(x.fecha, `calidad ${x.calidad != null ? x.calidad : '—'} · pruebas ${x.pruebas_ok}/${x.pruebas}`)));
    const reglas = el('div'); e.reglas.principios.forEach(p => { const li = el('p', 'pie-nota', '· ' + p); reglas.append(li); });
    Object.entries(e.reglas.longitud).filter(([k]) => k[0] !== '_').forEach(([k, v]) => reglas.append(dato(`Extensión · ${k}`, `${v[0]}–${v[1]} palabras`)));
    c2.append(det('Evolución', tend), det('Reglas y criterios que sigue', reglas));
    g.append(c1, c2); raiz.append(g); z.replaceChildren(raiz);
    refrescando(ej.corriendo ? 2500 : 10000, () => pintarEntreno());
  }
  const ETAPAS = { antes: 'antes de los filtros', pre: 'antes de buscar', notas: 'con el rastro de la charla', modelo: 'justo antes del modelo' };
  async function pintarHabilidades(z0) {
    const z = z0 || document.getElementById('ap'); if (!z) return; let lista; try { lista = await get('api/recetas'); } catch (e) { return; }
    const firma = JSON.stringify(lista); if (z.dataset.firma === firma) return; z.dataset.firma = firma;
    const raiz = el('div'); raiz.append(el('p', 'ayuda', 'Destrezas que Jarvis resuelve sin el modelo: rápidas, exactas y con su carácter. Se pueden apagar una a una si alguna estorba.'));
    const l = el('div', 'lista');
    lista.forEach(r => { const f = fila(r.titulo, r.descripcion), c = f.firstChild; const m = el('div', 'meta'); m.style.marginTop = '8px'; m.append(ficha(ETAPAS[r.etapa] || r.etapa), ficha(`${r.usos} usos${r.ultima ? ' · última ' + r.ultima : ''}`)); c.append(m);
      f.append(interruptor(r.activa, async (v) => { const x = await mandar('api/recetas', { nombre: r.nombre, activa: v }); if (x) { delete z.dataset.firma; pintarHabilidades(); } }, r.titulo)); if (!r.activa) f.style.opacity = .6; l.append(f); });
    raiz.append(l); z.replaceChildren(raiz); refrescando(15000, () => pintarHabilidades());
  }
  async function pintarHistorial(z0) {
    const z = z0 || document.getElementById('ap'); if (!z) return; let filas; try { filas = await get('api/bitacora'); } catch (e) { return; }
    const firma = JSON.stringify(filas.map(f => f.hora)); if (z.dataset.firma === firma) return; z.dataset.firma = firma;
    const raiz = el('div'); raiz.append(el('p', 'ayuda', 'Las últimas respuestas. Toca una para verla completa.')); const l = el('div', 'lista hist');
    filas.forEach(f => { const it = el('div'), c = el('div', 'cuerpo'); c.append(el('b', null, f.pregunta)); const m = el('div', 'meta'); m.style.marginTop = '6px';
      m.append(ficha(RUTAS[f.fuente] || f.fuente), ficha(`${f.hora.slice(11, 16)} · ${f.total_s} s`)); const mo = chipMotor(f.motor); if (mo) m.append(mo); if (f.calidad != null) m.append(ficha(`calidad ${f.calidad}`, f.calidad >= 80 ? 'bien' : 'aviso'));
      c.append(m, el('small', 'resp', f.respuesta)); it.append(c); it.style.cursor = 'pointer'; it.onclick = () => it.classList.toggle('abierta'); l.append(it); });
    raiz.append(l); z.replaceChildren(raiz); refrescando(10000, () => pintarHistorial());
  }

  // ---------- Archivos: lo que Jarvis conoce ----------
  const peso = (b) => b > 1048576 ? (b / 1048576).toFixed(1) + ' MB' : Math.max(1, Math.round(b / 1024)) + ' KB';
  let destino = 'marvel';
  function archivos(cuerpo) {
    cuerpo.append(el('p', 'ayuda', 'Sube documentos y Jarvis los lee y los conecta solo con lo que ya sabe. Se pueden borrar los que subiste; los de base no.'));
    const dest = segmentos([{ id: 'marvel', texto: 'Cerebro de Marvel' }, { id: 'taller', texto: 'Nube del taller' }], destino, (id) => { destino = id; });
    const nota = el('p', 'pie-nota', 'Marvel: películas, series, personajes. Taller: proyectos, estudiantes, actividades.'); nota.style.margin = '8px 0 14px';
    const zona = el('label', 'zona-subida'); zona.tabIndex = 0; const t = el('b', null, 'Arrastra archivos aquí o toca para subirlos'), s = el('span', null, 'PDF, Word (.docx), texto e imágenes.'), inp = el('input'); inp.type = 'file'; inp.multiple = true; inp.accept = '.pdf,.docx,.txt,.md,.png,.jpg,.jpeg,.webp'; inp.setAttribute('aria-label', 'Elegir archivos'); zona.append(t, s, inp);
    zona.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); inp.click(); } };
    const subir = async (lista) => { for (const a of lista) { aviso(`Subiendo ${a.name}…`);
      try { const r = await fetch(`api/subir?nube=${destino}&nombre=${encodeURIComponent(a.name)}`, { method: 'POST', headers: { 'X-Clave': clave }, body: a }); const d = await r.json().catch(() => ({})); if (r.status === 401 && !esPantalla) { clave = ''; guardado('mjarvis-clave', ''); montarVista(); return; } if (!r.ok) aviso(`${a.name}: ${d.error || 'no se pudo'}`, 'mal'); }
      catch (e) { aviso(`${a.name}: no llegó a Jarvis.`, 'mal'); } } };
    inp.onchange = (e) => { subir([...e.target.files]); e.target.value = ''; };
    zona.ondragover = (e) => { e.preventDefault(); zona.classList.add('encima'); }; zona.ondragleave = () => zona.classList.remove('encima');
    zona.ondrop = (e) => { e.preventDefault(); zona.classList.remove('encima'); subir([...e.dataTransfer.files]); };
    const av = el('p', 'pie-nota'); av.id = 'archivos-aviso'; av.setAttribute('aria-live', 'polite'); av.style.minHeight = '1.4em';
    const buscar = el('input'); buscar.type = 'search'; buscar.placeholder = 'Buscar entre los archivos que conoce…'; buscar.setAttribute('aria-label', 'Buscar archivo'); buscar.autocomplete = 'off'; buscar.style.marginBottom = '6px';
    const cuenta = el('p', 'pie-nota'); cuenta.id = 'archivos-cuenta'; cuenta.style.margin = '0 0 4px'; const lista = el('div', 'lista docs'); lista.id = 'lista-docs';
    buscar.oninput = () => filtrarDocs(buscar.value); buscar.id = 'buscar-docs';
    cuerpo.append(dest, nota, zona, av, buscar, cuenta, lista); listarDocs();
  }
  function aviso(texto, tono) { const a = document.getElementById('archivos-aviso'); if (!a) return; a.textContent = texto; a.style.color = tono === 'mal' ? 'var(--mal)' : tono === 'bien' ? 'var(--ok)' : ''; }
  function filtrarDocs(q) {
    q = (q || '').trim().toLowerCase(); const filas = [...document.querySelectorAll('#lista-docs > div')]; let v = 0;
    filas.forEach(f => { const ok = !q || f.dataset.nombre.includes(q); f.hidden = !ok; if (ok) v++; });
    const c = document.getElementById('archivos-cuenta'); if (c) c.textContent = filas.length ? `Mostrando ${v} de ${filas.length} archivos` : '';
  }
  async function listarDocs() {
    let docs; try { docs = await get('api/documentos'); } catch (e) { return; } const l = document.getElementById('lista-docs'); if (!l) return;
    const primera = !l.dataset.listo; l.dataset.listo = '1';
    l.replaceChildren(...docs.map(d => {
      const f = el('div'), c = el('div', 'cuerpo'), delTaller = d.nombre.startsWith('taller-'); f.dataset.nombre = d.nombre.toLowerCase(); f.style.flexWrap = 'wrap';
      c.append(el('b', null, (delTaller ? 'Taller · ' : '') + d.nombre.replace(/^taller-/, '')), el('small', null, `${d.notas} notas` + (d.imagenes ? ` · ${d.imagenes} imágenes` : '') + (d.subido ? '' : ' · base')));
      const notas = el('div', 'notas'); const ver = el('button', 'boton chico', 'Ver notas'); ver.type = 'button';
      ver.onclick = async () => { if (!notas.childElementCount) { try { const n = await get('api/notas?doc=' + encodeURIComponent(d.nombre)); notas.replaceChildren(...n.map(x => { const k = el('div'); k.append(el('b', null, x.titulo), x.pagina ? el('small', null, ' · pág. ' + x.pagina) : '', el('p', null, x.texto)); (x.imagenes || []).forEach(src => { const im = el('img'); im.src = src; im.alt = 'Imagen de ' + x.titulo; im.loading = 'lazy'; k.append(im); }); return k; })); } catch (e) { return; } }
        const ab = notas.classList.toggle('abierto'); ver.textContent = ab ? 'Ocultar notas' : 'Ver notas'; };
      f.append(c, ver);
      if (d.original) { const a = el('a', 'boton chico'); a.href = 'originales/' + encodeURIComponent(d.original); a.target = '_blank'; a.append(icono('descargar'), el('span', null, peso(d.peso))); a.title = 'Descargar el original'; f.append(a); }
      if (d.subido) f.append(Object.assign(el('button', 'boton chico peligro', 'Borrar'), { type: 'button', onclick: async () => {
        if (!confirm(`¿Borrar «${d.nombre}»? Jarvis olvidará sus ${d.notas} notas y se eliminará el archivo original.`)) return;
        const r = await mandar('api/borrar', { documento: d.nombre }, `«${d.nombre}» borrado.`); if (r) listarDocs(); } }));
      f.append(notas); return f;
    }));
    if (primera) escalonar(l);   // solo la primera vez: al volver a listar tras subir o borrar no vuelve a entrar todo
    filtrarDocs((document.getElementById('buscar-docs') || {}).value);
  }
  function ingesta(d) { aviso(d.estado, d.fin ? (d.error ? 'mal' : 'bien') : ''); if (d.fin) listarDocs(); }

  // ---------- Red ----------
  const GUIAS = { Windows: 'Propiedades de tu Wi-Fi → pestaña «Uso compartido» → permitir que otros usuarios se conecten, y elegir el adaptador Ethernet.', Mac: 'Ajustes del Sistema → General → Compartir → «Compartir Internet»: desde Wi-Fi, hacia Ethernet.', Linux: 'En la conexión del cable (NetworkManager): IPv4 → «Compartida con otros equipos».' };
  function red(cuerpo) { const z = el('div'); z.id = 'zona-red'; cuerpo.append(z); ciclo(5000, async () => { try { redEstado = await get('api/red'); pintarRed(); } catch (e) { /* sin red un momento */ } }); }
  function pintarRed() {
    const z = document.getElementById('zona-red'); if (!z || !redEstado) return; const r = redEstado, [titulo, ico, color, texto] = MODOS[r.modo] || MODOS.buscando;
    if (z.querySelector('details[open]') && z.dataset.listo) { const reg = z.querySelector('.registro'); if (reg) { reg.replaceChildren(...registro(r)); } return; }
    z.dataset.listo = '1';
    const hero = el('div', 'estado-red pieza'); hero.style.setProperty('--tono', color); const m = el('span', 'moneda'); m.append(icono(ICONO_MODO[ico])); const c = el('div'); c.append(el('h2', null, titulo), el('p', null, r.modo_texto || texto)); hero.append(m, c);
    const esc = el('div', 'escalera'); esc.style.setProperty('--tono', color);
    [['nube', 'Wi-Fi con internet'], ['puente', 'Cable con internet'], ['lan', 'Red sin internet'], ['local', 'Su propia red']].forEach(([k, t], i) => { const f = el('span', 'ficha'); if (k === r.modo) f.setAttribute('aria-current', 'step'); f.append(el('span', 'num', String(i + 1)), el('span', null, t)); esc.append(f); });
    const acc = el('div', 'fila-botones'); acc.style.marginTop = '16px';
    const boton = (t, a, clase, ok) => { const b = el('button', 'boton ' + (clase || ''), t); b.type = 'button'; b.onclick = async () => { b.disabled = true; await mandar('api/red', { accion: a }, ok || 'Hecho.'); setTimeout(() => { b.disabled = false; }, 4000); }; return b; };
    if (r.hotspot.existe) acc.append(boton(r.hotspot.activa ? 'Apagar la Wi-Fi «M-Jarvis»' : 'Encender la Wi-Fi «M-Jarvis»', r.hotspot.activa ? 'hotspot_off' : 'hotspot_on', r.hotspot.activa ? '' : 'principal', r.hotspot.activa ? 'Apagando… la Latitude buscará la Wi-Fi de siempre.' : 'Encendiendo la Wi-Fi «M-Jarvis»…'));
    acc.append(boton(r.manual ? 'Volver a automático' : 'Forzar modo local', r.manual ? 'auto' : 'local', '', r.manual ? 'De vuelta en automático.' : 'Modo local.'), boton('Revisar de nuevo', 'reevaluar', '', 'Revisando…'));
    const eq = el('div'); eq.append(el('h2', 'titulo-2', `Equipos conectados (${r.clientes.length})`)); const le = el('div', 'lista');
    if (!r.clientes.length) eq.append(el('p', 'vacio', 'Nadie por ahora. Quien se una a la Wi-Fi «M-Jarvis» o al cable aparece aquí, y su pantalla abre el chat sola.'));
    r.clientes.forEach(k => { const f = el('div'), cu = el('div', 'cuerpo'); cu.append(el('b', null, k.nombre || 'Equipo sin nombre'), el('small', null, `${k.ip} · ${k.via}`)); f.append(cu); le.append(f); }); eq.append(le);
    const cab = el('div'); cab.append(el('h2', 'titulo-2', 'Cable'), el('p', 'ayuda', 'En automático, al enchufar un cable la Latitude pide internet al otro equipo y, si nadie le contesta en unos 15 s, ofrece su propia interfaz. «Recibir» fuerza lo primero; «Ofrecer», lo segundo.'));
    const sc = segmentos([{ id: 'cable_auto', texto: 'Automático' }, { id: 'cable_cliente', texto: 'Recibir' }, { id: 'cable_servidor', texto: 'Ofrecer' }], { 'enlace-local': 'cable_servidor', servidor: 'cable_servidor', cliente: 'cable_cliente' }[r.cable.rol] || 'cable_auto', (id) => mandar('api/red', { accion: id }, 'Hecho.')); cab.append(sc);
    const atajo = el('div'); atajo.append(el('h2', 'titulo-2', 'Acceso directo del manager'), el('p', 'ayuda', 'Para abrir este Control como una aplicación desde otro equipo, buscando a la Latitude donde esté.'));
    const ab = el('div', 'fila-botones'); [['Windows', 'bat'], ['Mac', 'command'], ['Linux', 'sh']].forEach(([so, ext]) => { const a = el('a', 'boton'); a.href = `descargas/M-Jarvis-Manager.${ext}`; a.download = ''; a.append(icono('descargar'), el('span', null, so)); ab.append(a); }); atajo.append(ab);
    const pres = el('details', 'plegable'); const s = el('summary', null, 'Prestarle internet a la Latitude por cable'); pres.append(s, el('p', 'ayuda', 'Conecta un cable de red entre esa computadora y la Latitude y comparte el internet de la computadora por ese cable. La Latitude lo detecta sola.'));
    const seg2 = el('div', 'fila-botones'), caja = el('p', 'pie-nota'); caja.textContent = 'Elige el sistema de esa computadora.'; Object.entries(GUIAS).forEach(([k, v]) => { const b = el('button', 'boton chico', k); b.type = 'button'; b.onclick = () => { caja.textContent = v; }; seg2.append(b); }); pres.append(seg2, caja);
    const reg = el('details', 'plegable'); reg.append(el('summary', null, 'Qué ha ido decidiendo y por qué')); const lr = el('div', 'registro'); lr.append(...registro(r)); reg.append(lr);
    const g = el('div', 'dos'); const c1 = el('div'), c2 = el('div'); c1.append(eq, cab); c2.append(atajo, pres, reg); g.append(c1, c2);
    z.replaceChildren(hero, esc, acc, g);
  }
  const registro = (r) => r.eventos.length ? r.eventos.map(e => { const f = el('div'); f.append(el('span', 'hora', e.hora), el('span', null, e.texto)); return f; }) : [el('p', 'vacio', 'Todavía nada.')];

  // ---------- Sistema ----------
  function sistema(cuerpo) {
    cuerpo.append(el('p', 'ayuda', 'La salud de la Latitude: que no se caliente, que le sobre memoria y que siga encendida todo el evento.'));
    const z = el('div'); z.id = 'sis'; cuerpo.append(z); const n = el('div'); n.id = 'nube-zona'; cuerpo.append(n); nubeConstruida = false;
    ciclo(4000, pintarSistema); ciclo(5000, pintarNube);
  }
  let claveLocal = null;   // la clave de gestión solo se muestra en la propia Latitude
  const nivel = (v, a, m) => v >= m ? 'var(--mal)' : v >= a ? 'var(--aviso)' : 'var(--animo)';
  // Los anillos se crean una vez (se dibujan desde cero) y después solo cambian de valor: el arco se mueve, no se vuelve a dibujar.
  const L_ANILLO = 2 * Math.PI * 38;
  function anillo(nombre, texto, valor, color) {
    const a = el('div', 'anillo pieza');
    a.innerHTML = `<svg viewBox="0 0 92 92" aria-hidden="true"><circle class="fondo" cx="46" cy="46" r="38"/><circle class="valor" cx="46" cy="46" r="38" stroke-dasharray="${L_ANILLO.toFixed(1)}" stroke-dashoffset="${L_ANILLO.toFixed(1)}"/></svg>`;
    const cifra = el('div', 'cifra'), rotulo = el('small'); a.append(cifra, rotulo);
    a.poner = (n, t, v, c) => { a.style.setProperty('--tono', c); cifra.textContent = t; rotulo.textContent = n; a.querySelector('.valor').style.strokeDashoffset = (L_ANILLO * (1 - Math.min(100, Math.max(0, v)) / 100)).toFixed(1); };
    a.poner(nombre, texto, 0, color); requestAnimationFrame(() => requestAnimationFrame(() => a.poner(nombre, texto, valor, color)));
    return a;
  }
  let anillos = null, infoSistema = null;
  async function pintarSistema() {
    const z = document.getElementById('sis'); if (!z) return; let e, v, a; try { [e, v, a] = await Promise.all([get('api/estado'), get('api/voz/estado'), get('api/autoentreno')]); } catch (x) { return; }
    const l = e.lecturas, t = l.temperatura;
    const datos = [['temp', 'Temperatura', t != null ? `${Math.round(t)}°` : '—', t || 0, nivel(t || 0, 75, 88)], ['mem', 'Memoria', `${l.memoria}%`, l.memoria, nivel(l.memoria, 85, 95)],
      ['cpu', 'Procesador', `${l.carga}%`, l.carga, nivel(l.carga, 85, 98)], ['disco', 'Almacenamiento', `${l.almacenamiento}%`, l.almacenamiento, nivel(l.almacenamiento, 85, 95)]];
    if (l.bateria != null) datos.push(['bat', l.enchufado ? 'Batería · enchufada' : 'Batería · ¡no enchufada!', `${l.bateria}%`, l.bateria, !l.enchufado && l.bateria < 25 ? 'var(--mal)' : !l.enchufado && l.bateria < 50 ? 'var(--aviso)' : 'var(--ok)']);
    if (!anillos || !z.contains(anillos)) { anillos = el('div', 'anillos'); anillos.mapa = new Map(); infoSistema = el('div'); z.replaceChildren(anillos, infoSistema); }
    const primera = !anillos.mapa.size;
    for (const [k, n, tx, val, col] of datos) { const viejo = anillos.mapa.get(k); if (viejo) viejo.poner(n, tx, val, col); else { const nuevo = anillo(n, tx, val, col); anillos.mapa.set(k, nuevo); anillos.append(nuevo); } }
    if (primera) escalonar(anillos);
    const info = infoSistema; info.replaceChildren(); info.append(el('h2', 'titulo-2', 'M-Jarvis'));
    [['Encendida desde hace', hace(l.horas * 3600)], ['Modelo de la Latitude', e.modelo], ['Notas que conoce', String(e.notas)], ['Pensando ahora', e.ocupado ? 'sí' : 'no'], ['Voz', v.voz ? 'disponible' : 'no disponible'], ['Oído', v.oido ? 'disponible' : 'no disponible'],
      ['Auto-entrenado', a.ultimo ? `${a.ultimo.fecha} · ${a.ultimo.cumple_meta ? 'cumple la meta' : 'no cumple la meta'}` : 'sin ejecutar']].forEach(([x, y]) => { const f = el('div', 'dato'); f.append(el('span', null, x), el('b', null, y)); info.append(f); });
    (e.direcciones || []).forEach(d => info.append(dato('Dirección', `http://${d}:8080`)));
    if (esPantalla && claveLocal === null) { claveLocal = ''; fetch('api/clave').then(r => r.json()).then(c => { claveLocal = c.clave || ''; }).catch(() => {}); }
    if (claveLocal) info.append(dato('Clave de gestión', claveLocal));
  }
  let nubeConstruida = false;
  const AYUDA = { groq: ['Groq', 'console.groq.com → API Keys → Create API Key. Gratis, sin tarjeta.'], gemini: ['Google Gemini (opcional)', 'aistudio.google.com → Get API key. Gratis, pero Google puede usar lo que se le envía para mejorar sus productos.'] };
  async function pintarNube() {   // se arma una sola vez (para no borrar lo que se está escribiendo) y luego solo se actualizan los datos
    const z = document.getElementById('nube-zona'); if (!z) return; let n; try { n = await get('api/nube'); } catch (e) { return; } nubeEstado = n; pintarMandos();
    if (!nubeConstruida) {
      nubeConstruida = true; z.replaceChildren(el('h2', 'titulo-2', 'Nube gratis'),
        el('p', 'ayuda', 'Un modelo más grande en la nube escribe las respuestas cuando hay internet; lo demás sigue en la Latitude. Si la nube falla o se acaba la cuota del día, responde el modelo local sin que se note. Las preguntas con datos personales nunca salen, y los correos, teléfonos y enlaces se tachan antes de enviar.'));
      const g = el('div', 'dos'), izq = el('div'), der = el('div'); izq.id = 'nube-prov';
      for (const [k, [nombre, ayuda]] of Object.entries(AYUDA)) {
        const c = el('div'); c.style.marginBottom = '22px'; c.append(el('b', null, 'Clave de ' + nombre), el('p', 'pie-nota', ayuda)); const i = el('input'); i.type = 'password'; i.autocomplete = 'off'; i.placeholder = 'Pega la clave aquí'; i.setAttribute('aria-label', 'Clave de ' + nombre);
        const f = el('div', 'fila-botones'); f.style.marginTop = '10px'; const b = el('button', 'boton principal', 'Guardar'); b.type = 'button'; const q = el('button', 'boton', 'Quitar'); q.type = 'button'; const es = el('span', 'pie-nota'); es.id = 'ke-' + k; es.style.alignSelf = 'center';
        b.onclick = async () => { if (!i.value.trim()) return; const r = await mandar('api/nube', { clave: k, valor: i.value.trim() }, 'Clave guardada.'); if (r) { i.value = ''; pintarNube(); } };
        q.onclick = async () => { const r = await mandar('api/nube', { clave: k, valor: '' }, 'Clave quitada.'); if (r) pintarNube(); }; f.append(b, q, es); c.append(i, f); der.append(c);
      }
      g.append(izq, der); z.append(g);
    }
    const prov = document.getElementById('nube-prov'); if (!prov) return;
    prov.replaceChildren(el('h2', 'titulo-2', 'Proveedores, en orden de preferencia'), ...n.proveedores.map(p => {
      const f = el('div', 'dato'); f.style.display = 'block'; const a = el('div'); a.style.cssText = 'display:flex;justify-content:space-between;gap:12px;align-items:center'; const t = el('b', null, p.nombre); const pr = el('button', 'boton chico', 'Probar'); pr.type = 'button'; pr.disabled = !p.con_clave;
      pr.onclick = async () => { pr.disabled = true; pr.textContent = 'Probando…'; const r = await mandar('api/nube', { probar: p.id }, null); pr.textContent = 'Probar'; pr.disabled = false; if (r && r.prueba) avisar(r.prueba.ok ? `${p.nombre}: funciona (${r.prueba.ms} ms).` : `${p.nombre}: ${r.prueba.mensaje}`, !r.prueba.ok); pintarNube(); };
      a.append(t, pr); const pct = Math.min(100, p.usos_hoy / p.limite_dia * 100), barra = el('div', 'barra' + (pct > 90 ? ' mal' : pct > 70 ? ' aviso' : '')); barra.append(Object.assign(el('i'), { style: `transform:scaleX(${Math.max(pct, p.usos_hoy ? 2 : 0) / 100})` }));
      const estado = !p.con_clave ? 'sin clave' : p.pausa_s ? `en pausa ${hace(p.pausa_s)} · ${p.error}` : p.ultimo_ok != null ? `funcionó hace ${hace(p.ultimo_ok)}` : 'lista'; const s = el('small', null, `${p.usos_hoy} de ${p.limite_dia} usos hoy · ${estado}`); s.style.cssText = 'display:block;color:var(--apagado);margin-top:6px'; f.append(a, barra, s); return f;
    }));
    for (const [k, v] of Object.entries(n.claves)) { const e = document.getElementById('ke-' + k); if (e) e.textContent = v.puesta ? `guardada (termina en ${v.final})` : 'sin clave'; }
  }

  return { montar };
})();
