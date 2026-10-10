// Uso: desde una carpeta con Playwright instalado, con un túnel `ssh -L 8081:localhost:8080 mjarvis` abierto: node humo.js [http://localhost:8081]
// Correrla SIEMPRE después de tocar index.html, shell.js o control.js: probar.sh no ejecuta el JavaScript de las pantallas.
// Prueba de humo tras cada despliegue: ninguna pantalla debe dar errores de script y el chat debe poder preguntar y responder.
const { chromium } = require('playwright'); const base = process.argv[2] || 'http://localhost:8081';
(async () => {
  // En Windows se usa el Edge instalado (MJARVIS_CANAL=msedge); en Linux, el Chromium de Playwright sin tarjeta gráfica.
  const b = await chromium.launch(process.env.MJARVIS_CANAL ? { channel: process.env.MJARVIS_CANAL } : { args: ['--enable-unsafe-swiftshader', '--use-angle=swiftshader'] }); let mal = 0;
  const revisar = async (nombre, url, extra) => {
    const p = await (await b.newContext({ viewport: { width: 1280, height: 800 } })).newPage(); const errs = [];
    p.on('pageerror', e => errs.push(e.message)); p.on('console', m => { if (m.type() === 'error' && !/favicon/.test(m.text())) errs.push(m.text()); });
    await p.goto(base + url, { waitUntil: 'domcontentloaded', timeout: 60000 }); await p.waitForTimeout(2500); const extraRes = extra ? await extra(p) : '';
    const ok = !errs.length && (!extra || extraRes.ok); if (!ok) mal++;
    console.log(ok ? 'OK ' : 'MAL', nombre.padEnd(30), errs.length ? 'ERRORES: ' + errs.join(' | ') : '', extraRes.texto || ''); await p.context().close();
  };
  await revisar('vista=todo (mapa + chat)', '/?vista=todo', async p => ({ ok: await p.evaluate(() => !!document.getElementById('mapa') && !document.getElementById('dock')), texto: '(con mapa, sin barra)' }));
  await revisar('pantalla del público', '/?vista=chat', async p => ({ ok: !(await p.evaluate(() => document.getElementById('ambiente') || document.getElementById('dock'))), texto: '(sin barra ni ambiente)' }));
  await revisar('interfaz completa', '/', async p => ({ ok: await p.evaluate(() => !!document.getElementById('dock') && document.querySelectorAll('#dock a').length === 4), texto: '(barra con 4 secciones)' }));
  for (const h of ['#mapa', '#conectar', '#control/ahora', '#control/aprender', '#control/archivos', '#control/red', '#control/sistema']) await revisar('sección ' + h, '/' + h);
  // el chat debe responder
  await revisar('chat: pregunta y respuesta', '/?vista=chat', async p => {
    if (await p.evaluate(() => document.getElementById('campo').disabled)) return { ok: true, texto: '(teclado bloqueado desde Control: la pregunta no se probó)' };
    await p.fill('#campo', 'hola'); await p.keyboard.press('Enter'); await p.waitForFunction(() => document.querySelectorAll('.jarvis').length && !document.querySelector('.jarvis.esperando'), null, { timeout: 90000 }).catch(() => {});
    const t = await p.evaluate(() => [...document.querySelectorAll('.jarvis p')].map(x => x.textContent).pop() || ''); return { ok: t.length > 3 && !/^…$/.test(t), texto: '→ ' + t.slice(0, 60) };
  });
  console.log(mal ? `\n${mal} PANTALLA(S) CON PROBLEMAS` : '\nTODO BIEN'); await b.close(); process.exit(mal ? 1 : 0);
})();
