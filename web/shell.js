'use strict';
// El armazón de la interfaz única: la bola y el chat son la escena; Mapa, Conectar y Control se abren como láminas de cristal
// encima, sin cambiar de página (así la bola nunca desaparece). Las secciones largas viven en control.js.
// Pantallas del público (?vista=chat o ?vista=todo) no llevan barra ni láminas: ahí solo se ve la escena, como siempre.

// ---------- Utilidades compartidas ----------
const el = (tag, clase, texto) => { const e = document.createElement(tag); if (clase) e.className = clase; if (texto != null) e.textContent = texto; return e; };
const get = (ruta) => fetch(ruta, { cache: 'no-store' }).then(r => { if (!r.ok) throw new Error(r.status); return r.json(); });
const hace = (s) => { s = Math.max(0, Math.round(s)); return s < 90 ? `${s} s` : s < 5400 ? `${Math.round(s / 60)} min` : `${Math.round(s / 3600)} h`; };
const ICONOS = {
  jarvis: '<circle cx="12" cy="12" r="8.2"/><path d="M8 10.4A4.6 4.6 0 0 1 12.4 7.6"/><circle cx="14.6" cy="14.2" r="1.3"/>',
  mapa: '<circle cx="6" cy="7" r="2.2"/><circle cx="18" cy="6" r="2.2"/><circle cx="12" cy="18" r="2.2"/><path d="M7.9 8.2l3 7.8M16.2 7.4l-3 8.6M8.2 7h7.6"/>',
  conectar: '<path d="M2.8 9.6a13.6 13.6 0 0 1 18.4 0M5.9 13a9.2 9.2 0 0 1 12.2 0M8.9 16.3a4.8 4.8 0 0 1 6.2 0"/><path d="M12 19.6v.01"/>',
  control: '<path d="M4 7h9M17 7h3M4 17h3M11 17h9"/><circle cx="15" cy="7" r="2"/><circle cx="9" cy="17" r="2"/>',
  voz: '<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z"/><path d="M15.5 9a4.2 4.2 0 0 1 0 6M18.2 6.6a7.6 7.6 0 0 1 0 10.8"/>',
  vozno: '<path d="M4 9.5v5h3.5L12 18.5v-13L7.5 9.5z"/><path d="M16 9.5l5 5m0-5l-5 5"/>',
  teclado: '<rect x="3" y="6" width="18" height="12" rx="3"/><path d="M7 10h.01M11 10h.01M15 10h.01M7 14h10"/>',
  candado: '<rect x="5" y="11" width="14" height="9" rx="2.5"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
  nube: '<path d="M7 18a4 4 0 0 1-.6-7.95A5.5 5.5 0 0 1 17 8.5a4.75 4.75 0 0 1 0 9.5z"/>',
  parar: '<rect x="6.5" y="6.5" width="11" height="11" rx="2.5"/>',
  ahora: '<path d="M3 12h4l2.5-7 5 14 2.5-7H21"/>',
  escenario: '<path d="M4 6h16v10H9.5L5 20v-4H4z"/><path d="M8 10.5h8"/>',
  aprender: '<path d="M4 5.5C4 4.7 4.7 4 5.5 4H11v15H5.5C4.7 19 4 18.3 4 17.5zM20 5.5c0-.8-.7-1.5-1.5-1.5H13v15h5.5c.8 0 1.5-.7 1.5-1.5z"/>',
  red: '<circle cx="12" cy="5" r="2.2"/><circle cx="5" cy="18" r="2.2"/><circle cx="19" cy="18" r="2.2"/><path d="M11 7l-5 9M13 7l5 9M7.3 18h9.4"/>',
  sistema: '<path d="M4 16a8 8 0 1 1 16 0M12 16l4-5"/>',
  enviar: '<path d="M12 19V5M6 11l6-6 6 6"/>',
  ok: '<path d="M5 12.5l4.5 4.5L19 7.5"/>', x: '<path d="M6 6l12 12M18 6L6 18"/>',
  celular: '<rect x="7" y="3" width="10" height="18" rx="2.5"/><path d="M11 18h2"/>',
  compu: '<rect x="3" y="4" width="18" height="12" rx="2"/><path d="M8 20h8M12 16v4"/>',
  cable: '<path d="M8 3v5M16 3v5M6 8h12v4a6 6 0 0 1-12 0zM12 18v3"/>',
  copiar: '<rect x="9" y="9" width="11" height="11" rx="2.5"/><path d="M5 15V6.5A2.5 2.5 0 0 1 7.5 4H15"/>',
  chip: '<rect x="7" y="7" width="10" height="10" rx="2"/><path d="M10 3v4M14 3v4M10 17v4M14 17v4M3 10h4M3 14h4M17 10h4M17 14h4"/>',
  descargar: '<path d="M12 4v11M7 11l5 5 5-5M5 20h14"/>',
  carpeta: '<path d="M3.5 7.5a2 2 0 0 1 2-2H10l2 2.5h6.5a2 2 0 0 1 2 2V17a2 2 0 0 1-2 2h-13a2 2 0 0 1-2-2z"/>',
};
const icono = (n, clase = 'icono') => { const t = document.createElement('template'); t.innerHTML = `<svg class="${clase}" viewBox="0 0 24 24" aria-hidden="true">${ICONOS[n] || ''}</svg>`; return t.content.firstChild; };
const ciclos = [];
const ciclo = (ms, f) => { f(); ciclos.push(setInterval(() => { if (!document.hidden) f(); }, ms)); };   // en una pestaña oculta no se consulta nada
const limpiarCiclos = () => { ciclos.forEach(clearInterval); ciclos.length = 0; };

// Cuando algo aparece como lista, cada elemento entra 40 ms después del anterior (tope: 6). Solo se llama en el primer dibujo.
function escalonar(contenedor, tope = 6) {
  [...contenedor.children].forEach((h, i) => h.style.setProperty('--i', Math.min(i, tope)));
  contenedor.classList.add('esc'); setTimeout(() => contenedor.classList.remove('esc'), 900);
}
let relojAviso = 0;
function avisar(texto, mal) {
  let a = document.getElementById('aviso');
  if (!a) { a = el('div', 'vidrio'); a.id = 'aviso'; a.setAttribute('role', 'status'); a.setAttribute('aria-live', 'polite'); document.body.append(a); }
  a.textContent = texto; a.className = 'vidrio visible' + (mal ? ' mal' : ''); clearTimeout(relojAviso); relojAviso = setTimeout(() => { a.className = 'vidrio'; }, 3400);
}

// Segmentos: el cristal que se desliza bajo la opción elegida.
function segmentos(opciones, activo, cambio) {
  const caja = el('div', 'segmentos' + (opciones.every(o => o.icono && o.compacta) ? ' compactos' : '')), lente = el('i', 'lente'); caja.append(lente); caja.setAttribute('role', 'group');
  const botones = new Map();
  const mover = () => {
    const b = botones.get(caja.activo); if (!b || !b.offsetWidth) return; const primera = !caja.colocada;
    if (primera) lente.classList.add('quieta');   // la primera colocación es un salto, no un deslizamiento
    lente.style.width = b.offsetWidth + 'px'; lente.style.transform = `translateX(${b.offsetLeft}px)`;
    if (primera) { caja.colocada = true; void lente.offsetWidth; requestAnimationFrame(() => lente.classList.remove('quieta')); }
  };
  caja.poner = (id) => { caja.activo = id; botones.forEach((b, k) => b.setAttribute('aria-pressed', String(k === id))); mover(); const b = botones.get(id); if (b) b.scrollIntoView({ inline: 'nearest', block: 'nearest' }); };
  for (const o of opciones) {
    const b = el('button'); b.type = 'button'; if (o.icono) b.append(icono(o.icono)); b.append(el('span', null, o.texto));
    if (o.cuenta) { const c = el('span', 'punto', o.cuenta); c.id = 'cuenta-' + o.id; b.append(c); } else if (o.id) { const c = el('span', 'punto'); c.id = 'cuenta-' + o.id; c.hidden = true; b.append(c); }
    b.onclick = () => { if (caja.activo !== o.id) { caja.poner(o.id); cambio(o.id); } }; botones.set(o.id, b); caja.append(b);
  }
  caja.activo = activo; botones.forEach((b, k) => b.setAttribute('aria-pressed', String(k === activo)));
  new ResizeObserver(mover).observe(caja); requestAnimationFrame(mover);
  return caja;
}
function interruptor(valor, cambio, etiqueta) {
  const b = el('button', 'interruptor'); b.type = 'button'; b.setAttribute('role', 'switch'); b.setAttribute('aria-label', etiqueta); b.setAttribute('aria-checked', String(!!valor));
  b.onclick = () => { const nuevo = b.getAttribute('aria-checked') !== 'true'; b.setAttribute('aria-checked', String(nuevo)); cambio(nuevo); };
  return b;
}
const copiar = (texto) => (navigator.clipboard ? navigator.clipboard.writeText(texto) : Promise.reject()).then(() => avisar('Copiado.')).catch(() => avisar(texto));

// ---------- Órdenes: desde otro equipo piden la clave de gestión (en la Latitude no hace falta) ----------
let clave = guardado('mjarvis-clave') || '';
async function orden(ruta, cuerpo) {
  const r = await fetch(ruta, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Clave': clave }, body: JSON.stringify(cuerpo || {}) });
  if (r.status === 401 && !esPantalla) { clave = ''; guardado('mjarvis-clave', ''); if (vistaActual === 'control') montarVista(); }
  return r;
}
async function mandar(ruta, cuerpo, ok) {
  try { const r = await orden(ruta, cuerpo); const d = await r.json().catch(() => ({})); if (r.ok) { if (ok) avisar(ok); return d; } avisar(d.error || 'No se pudo.', true); }
  catch (e) { avisar('Sin conexión con la Latitude.', true); }
  return null;
}
async function claveValida(c) {   // POST vacío a una orden inocua: responde 200 si la clave sirve
  try { return (await fetch('api/exhibicion', { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-Clave': c }, body: '{}' })).ok; } catch (e) { return false; }
}
let desbloqueado = esPantalla;

// ---------- La barra ----------
const CON_DOCK = !new URLSearchParams(location.search).get('vista');
const SECCIONES = [['jarvis', 'Jarvis'], ['mapa', 'Mapa'], ['conectar', 'Conectar'], ['control', 'Control']];
const CON_VT = CON_DOCK && !!document.startViewTransition;   // sin ellas (Firefox antiguo) cada sección asoma con un fundido
if (CON_VT) document.documentElement.classList.add('con-vt');
const ORDEN = { vistas: ['mapa', 'conectar', 'control'], partes: ['ahora', 'escenario', 'aprender', 'archivos', 'red', 'sistema'] };
const posicion = (id, sub) => ORDEN.vistas.indexOf(id) * 10 + Math.max(0, ORDEN.partes.indexOf(sub));   // para saber hacia qué lado se desliza
let vistaActual = 'jarvis', subActual = '';
const dock = document.getElementById('dock'), lente = document.getElementById('lente'), hoja = document.getElementById('hoja');
function moverLente(estira) {
  const a = dock.querySelector('a[aria-current="page"]'); if (!a || !a.offsetWidth) return;
  const primera = !lente.dataset.lista; if (primera) lente.classList.add('quieta');
  lente.style.width = a.offsetWidth + 'px'; lente.style.transform = `translateX(${a.offsetLeft}px)`;
  if (primera) { lente.dataset.lista = '1'; void lente.offsetWidth; requestAnimationFrame(() => lente.classList.remove('quieta')); }
  if (estira && !primera) { lente.classList.remove('estira'); void lente.offsetWidth; lente.classList.add('estira'); }
}
function mostrarControlEnBarra() { const c = dock.querySelector('a[data-v="control"]'); if (c) { c.hidden = !(desbloqueado && clave) && !esPantalla && !location.hash.startsWith('#control'); requestAnimationFrame(() => moverLente()); } }
if (CON_DOCK) {
  document.body.classList.add('con-dock');
  for (const [id, texto] of SECCIONES) {
    const a = el('a'); a.href = '#' + id; a.dataset.v = id; a.append(icono(id), el('span', null, texto));
    if (id === 'control') a.hidden = true; dock.append(a);
  }
  new ResizeObserver(() => moverLente()).observe(dock);
  addEventListener('hashchange', montarVista); document.fonts && document.fonts.ready.then(() => moverLente());
}

// ---------- La lámina ----------
const VISTAS = { mapa: { titulo: 'Red neuronal', montar: montarMapa }, conectar: { titulo: 'Conectar', montar: montarConectar }, control: { titulo: 'Control', montar: (c, d, s) => montarControl(c, d, s) } };
let cierre = 0;
function cerrarHoja() {
  if (hoja.hidden) return; hoja.classList.remove('entra'); hoja.classList.add('sale'); document.body.classList.remove('hoja-abierta'); orbe.suave = false; limpiarCiclos();
  clearTimeout(cierre); cierre = setTimeout(() => { hoja.hidden = true; hoja.classList.remove('sale', 'mapa'); document.getElementById('hoja-cuerpo').replaceChildren(); }, 280);
}
async function montarVista() {
  if (!CON_DOCK) return;
  const [v, sub = ''] = (location.hash || '#jarvis').slice(1).split('/'); const id = VISTAS[v] ? v : 'jarvis';
  const misma = id === vistaActual, antes = posicion(vistaActual, subActual); vistaActual = id; subActual = sub;
  if (id === 'control' && !desbloqueado && clave) desbloqueado = await claveValida(clave);
  mostrarControlEnBarra();
  dock.querySelectorAll('a').forEach(a => { if (a.dataset.v === id) a.setAttribute('aria-current', 'page'); else a.removeAttribute('aria-current'); });
  moverLente(!misma);
  if (id === 'jarvis') { cerrarHoja(); return; }
  clearTimeout(cierre); limpiarCiclos();
  const cuerpo = document.getElementById('hoja-cuerpo'), titulo = document.getElementById('hoja-titulo'), derecha = document.getElementById('hoja-derecha');
  const abriendo = hoja.hidden || hoja.classList.contains('sale');
  const aplicar = async () => {
    hoja.classList.toggle('mapa', id === 'mapa'); titulo.textContent = VISTAS[id].titulo;
    if (!misma || !derecha.firstChild) derecha.replaceChildren();   // el selector de Control se conserva entre sus secciones: así el cristal se desliza
    cuerpo.replaceChildren(); cuerpo.scrollTop = 0;
    hoja.hidden = false; hoja.classList.remove('sale');
    if (abriendo) { hoja.classList.remove('entra'); void hoja.offsetWidth; hoja.classList.add('entra'); }
    document.body.classList.add('hoja-abierta'); orbe.suave = true;
    await VISTAS[id].montar(cuerpo, derecha, sub);
  };
  // Al abrir, la lámina emerge de la barra. Al cambiar de sección, el cuerpo se desliza hacia el lado donde está la sección nueva
  // (y no si hay que descargar control.js primero: la página no puede quedar congelada esperando).
  const deslizar = CON_VT && !abriendo && !(id === 'control' && typeof Control === 'undefined') && !matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (deslizar) {
    document.documentElement.style.setProperty('--vt-x', posicion(id, sub) >= antes ? 1 : -1);
    try { await document.startViewTransition(aplicar).updateCallbackDone; } catch (e) { /* interrumpida por otra navegación */ }
  } else await aplicar();
}

// ---------- Mapa ----------
function montarMapa(cuerpo) {
  const marco = el('div', 'marco-mapa'), f = el('iframe'); f.title = 'Mapa de conocimiento de M-Jarvis'; f.src = 'grafo/?embebido=1'; marco.append(f); cuerpo.append(marco); encuadrar(f);
}
// El mapa tarda un instante en acomodarse: cuando termina de cargar se le pide que se ajuste a la lámina.
function encuadrar(f) { f.addEventListener('load', () => [1200, 3200].forEach(ms => setTimeout(() => { try { f.contentWindow.zoomMapa('ajustar'); } catch (e) { /* aún no */ } }, ms))); }

// ---------- Conectar: pensado para quien no sabe nada de redes ----------
const DISPOSITIVOS = [['iphone', 'iPhone', 'celular'], ['android', 'Android', 'celular'], ['windows', 'Windows', 'compu'], ['mac', 'Mac', 'compu'], ['linux', 'Linux', 'compu']];
const DISPOSITIVOS_CORTO = [['iphone', 'iPhone', 'celular'], ['android', 'Android', 'celular'], ['windows', 'Laptop', 'compu']];   // en el celular cabrían mal cinco
function anfitrion(red) {
  if (red && red.hotspot && red.hotspot.activa && red.hotspot.ip) return red.hotspot.ip;
  if (!['localhost', '127.0.0.1'].includes(location.hostname)) return location.hostname;
  try { return new URL(red.direcciones[0].url).hostname; } catch (e) { return location.hostname; }
}
async function montarConectar(cuerpo) {
  const raiz = el('div', 'conectar'); cuerpo.append(raiz);
  let red = null, tipo = guardado('mjarvis-dispositivo') || ''; const corto = matchMedia('(max-width: 560px)').matches, lista = corto ? DISPOSITIVOS_CORTO : DISPOSITIVOS;
  if (corto && ['mac', 'linux'].includes(tipo)) tipo = 'windows';
  if (!lista.some(d => d[0] === tipo)) tipo = /iPhone|iPad/.test(navigator.userAgent) ? 'iphone' : /Android/.test(navigator.userAgent) ? 'android' : '';
  const pintar = () => {
    raiz.replaceChildren(); const host = anfitrion(red || {}), url = `http://${host}:8080`, propia = red && red.hotspot && red.hotspot.activa;
    raiz.append(el('h2', null, 'Abre M-Jarvis en tu dispositivo'));
    raiz.append(segmentos(lista.map(d => ({ id: d[0], texto: d[1], icono: d[2] })), tipo || 'iphone', (id) => { tipo = id; guardado('mjarvis-dispositivo', id); pintar(); }));
    const t = tipo || 'iphone', movil = t === 'iphone' || t === 'android';
    const pasos = el('ol', 'pasos'), paso = (a, b) => { const li = el('li'); li.append(a); if (b) li.append(el('small', null, b)); pasos.append(li); return li; };
    paso(propia ? 'Únete a la Wi-Fi «M-Jarvis»' : 'Únete a la misma Wi-Fi que la Latitude', propia ? 'La contraseña te la da quien tiene la Latitude.' : (red && red.wifi && red.wifi.red ? `Es la red «${red.wifi.red}».` : 'La que usa la Latitude.'));
    if (movil) {
      paso(t === 'iphone' ? 'Abre la Cámara y apunta al código' : 'Escanea el código con la cámara', 'Se abre el chat. Si no, escribe la dirección de abajo en el navegador.');
      paso('Habla o escribe', t === 'iphone' ? 'Para tenerlo como aplicación: Compartir → Añadir a pantalla de inicio.' : 'Para tenerlo como aplicación: menú ⋮ → Instalar aplicación.');
    } else {
      paso('Abre el navegador', 'Chrome, Edge, Safari o Firefox: el que uses.');
      paso('Escribe esta dirección', 'Con http:// delante. Algunas redes de colegios aíslan los equipos entre sí: si no abre, usa la Wi-Fi «M-Jarvis».');
    }
    const tarjeta = el('div', 'qr-tarjeta pieza');
    if (movil && !['localhost', '127.0.0.1'].includes(host)) { const q = el('img', 'qr'); q.alt = 'Código QR para abrir M-Jarvis'; q.width = q.height = 176; q.src = 'api/qr?d=' + encodeURIComponent(host); q.onerror = () => { q.remove(); tarjeta.style.gridTemplateColumns = '1fr'; }; tarjeta.append(q); }
    tarjeta.append(pasos); if (!tarjeta.querySelector('.qr')) tarjeta.style.gridTemplateColumns = '1fr'; raiz.append(tarjeta);
    const dir = el('div', 'direccion'), c = el('code', null, url), b = el('button', 'boton chico redondo'); b.type = 'button'; b.setAttribute('aria-label', 'Copiar la dirección'); b.append(icono('copiar')); b.onclick = () => copiar(url); dir.append(c, b); raiz.append(dir);
    const estado = red ? (red.modo === 'local' ? 'Jarvis está sin internet, solo para esta red.' : 'Jarvis está en línea.') : ''; if (estado) raiz.append(el('p', 'pie-nota', estado));
  };
  pintar();
  ciclo(7000, async () => { try { const nueva = await get('api/red'); const cambio = !red || anfitrion(nueva) !== anfitrion(red) || nueva.hotspot.activa !== red.hotspot.activa; red = nueva; if (cambio) pintar(); } catch (e) { /* sin red un momento */ } });
}

// ---------- Control: la puerta ----------
function puerta(cuerpo, intento) {
  cuerpo.replaceChildren(); const p = el('div', 'puerta'); const m = el('span', 'moneda'); m.append(icono('candado')); const f = el('form'), i = el('input'), e = el('div', 'mal'), b = el('button', 'boton principal', 'Entrar');
  i.type = 'password'; i.inputMode = 'numeric'; i.autocomplete = 'off'; i.placeholder = '••••••'; i.setAttribute('aria-label', 'Clave de gestión'); b.type = 'submit'; e.setAttribute('role', 'alert');
  f.append(i, b); p.append(m, el('h2', null, 'Control de M-Jarvis'), el('p', null, 'Para ver lo que pasa y mandar órdenes hace falta la clave. Se ve en la Latitude: menú M-Jarvis → Compartir.'), f, e); cuerpo.append(p);
  f.onsubmit = async (ev) => { ev.preventDefault(); const c = i.value.trim(); if (!c) return; b.disabled = true;
    if (await claveValida(c)) { clave = c; guardado('mjarvis-clave', c); desbloqueado = true; montarVista(); }
    else { b.disabled = false; e.textContent = 'Esa clave no es la correcta.'; p.classList.remove('sacude'); void p.offsetWidth; p.classList.add('sacude'); i.select(); } };
  i.focus({ preventScroll: true });
}
// Control es la parte más grande y los visitantes nunca la abren: se descarga solo cuando hace falta.
let controlCargado = null;
const cargarControl = () => controlCargado || (controlCargado = new Promise((ok, no) => {
  const s = document.createElement('script'); s.src = 'control.js'; s.onload = ok; s.onerror = () => { controlCargado = null; no(new Error('control.js')); }; document.head.append(s);
}));
async function montarControl(cuerpo, derecha, sub) {
  if (!desbloqueado) return puerta(cuerpo);
  try { await cargarControl(); } catch (e) { cuerpo.append(el('p', 'vacio', 'No se pudo cargar Control. Revisa la conexión con la Latitude.')); return; }
  Control.montar(cuerpo, derecha, sub);
}

if (CON_DOCK) { montarVista(); } else { dock.remove(); hoja.remove(); document.getElementById('ambiente') && document.getElementById('ambiente').remove(); }
