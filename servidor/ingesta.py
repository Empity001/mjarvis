#!/usr/bin/env python3
"""Ingesta: convierte un documento cualquiera en notas del mapa de M-Jarvis.

Acepta PDF, Word (.docx), texto (.txt, .md) e imágenes sueltas (.png, .jpg, .webp).
- Parte el documento por sus títulos; si no tiene, lo corta en trozos y le pide al modelo
  un título para cada uno.
- Cada sección queda como una nota con el texto original (no resumido: las cifras no se tocan),
  la página de donde salió y las imágenes de esa página.
- Las imágenes sueltas las describe el propio modelo, que también ve.
- Las conexiones del mapa salen solas: grafo/build.py une las notas que se nombran entre sí.

Uso manual: python ingesta.py <archivo>      (dentro del entorno con PyMuPDF)
"""
import base64
import html
import json
import re
import shutil
import sys
import unicodedata
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
NOTAS = RAIZ / "conocimiento"
MEDIOS = RAIZ / "web" / "medios"
TOPE_NOTA = 900          # caracteres por nota: lo que el modelo lee cómodo de una vez
LADO_MINIMO = 150        # imágenes más pequeñas que esto son adornos (iconos, líneas)
TIPOS = {".pdf", ".docx", ".txt", ".md", ".png", ".jpg", ".jpeg", ".webp"}


def seguro(nombre, largo=70):
    """Nombre válido para archivo y para título de nota."""
    nombre = unicodedata.normalize("NFKC", nombre)
    nombre = re.sub(r'[\\/:*?"<>|#\[\]\n\r\t]+', " ", nombre)
    return " ".join(nombre.split())[:largo].strip(" .") or "Sin título"


def limpiar(texto):
    texto = unicodedata.normalize("NFKC", texto)  # deshace ligaduras ("ﬁ" -> "fi")
    return " ".join(texto.split())


def pedir_directo(mensaje, imagen=None):
    """Pregunta suelta al modelo (sin conversación). El servidor pasa su propia versión con turno."""
    cuerpo = {"model": "gemma3:4b", "stream": False, "keep_alive": -1,
              "options": {"temperature": 0.2, "num_predict": 170, "num_ctx": 4096},
              "messages": [{"role": "user", "content": mensaje, **({"images": [imagen]} if imagen else {})}]}
    peticion = urllib.request.Request("http://127.0.0.1:11434/api/chat", json.dumps(cuerpo).encode(),
                                      {"Content-Type": "application/json"})
    with urllib.request.urlopen(peticion, timeout=600) as r:
        return json.loads(r.read())["message"]["content"].strip()


# ---- Lectores: cada uno devuelve una lista de secciones {titulo, pagina, parrafos, imagenes} ----

def leer_pdf(ruta, carpeta_medios):
    import pymupdf
    doc = pymupdf.open(ruta)
    # Se mira línea por línea (no por bloque): un título puede venir pegado al párrafo siguiente.
    lineas, tamanos = [], Counter()
    for pagina in doc:
        for n_bloque, bloque in enumerate(pagina.get_text("dict")["blocks"]):
            if bloque["type"] != 0:
                continue
            for linea in bloque["lines"]:
                tramos = [t for t in linea["spans"] if t["text"].strip()]
                texto = limpiar("".join(t["text"] for t in linea["spans"]))
                if not tramos or not texto:
                    continue
                tam = max(t["size"] for t in tramos)
                tamanos[round(tam)] += len(texto)
                lineas.append((pagina.number + 1, (pagina.number, n_bloque), texto, tam,
                               all(t["flags"] & 16 for t in tramos), linea["bbox"][1]))
    cuerpo = tamanos.most_common(1)[0][0] if tamanos else 11
    # Encabezados y pies que se repiten en casi todas las páginas ("Guía X · Pág. 3") no son contenido.
    if doc.page_count >= 3:
        molde = lambda t: re.sub(r"\d+", "#", t)
        paginas_con = Counter()
        for clave in {(l[0], molde(l[2])) for l in lineas}:
            paginas_con[clave[1]] += 1
        repetidas = {m for m, n in paginas_con.items() if n >= max(3, doc.page_count * 0.6)}
        lineas = [l for l in lineas if molde(l[2]) not in repetidas]

    def es_titulo(texto, tam, negrita):
        if len(texto) > 90 or len(texto) < 2 or texto.isdigit() or texto.endswith((".", ",", ";")):
            return False
        return tam >= cuerpo * 1.12 or (negrita and len(texto.split()) <= 10)

    # "donde" = (página, altura en la página) en que empieza la sección: sirve para saber a cuál
    # pertenece cada imagen.
    secciones = [{"titulo": None, "pagina": 1, "donde": (1, 0), "parrafos": [], "imagenes": []}]
    parrafo, bloque_actual, tras_titulo, tam_titulo = "", None, False, 0

    def cerrar_parrafo():
        nonlocal parrafo
        if len(parrafo) > 3 and not parrafo.isdigit():  # fuera números de página y restos
            secciones[-1]["parrafos"].append(parrafo)
        parrafo = ""

    for pagina, bloque, texto, tam, negrita, altura in lineas:
        if bloque != bloque_actual:
            cerrar_parrafo()
            bloque_actual = bloque
        if es_titulo(texto, tam, negrita):
            cerrar_parrafo()
            if tras_titulo and abs(tam - tam_titulo) < 0.5:  # mismo tamaño: un título en dos líneas
                secciones[-1]["titulo"] += " " + texto.rstrip(":")
            else:  # otro tamaño: capítulo seguido de apartado; el capítulo queda vacío y se descarta
                secciones.append({"titulo": texto.rstrip(":"), "pagina": pagina, "donde": (pagina, altura),
                                  "parrafos": [], "imagenes": []})
            tras_titulo, tam_titulo = True, tam
            continue
        tras_titulo = False
        if not secciones[-1]["titulo"] and not secciones[-1]["parrafos"] and not parrafo:
            secciones[-1]["pagina"] = pagina
        # Une líneas; si una termina en guion, la palabra sigue en la otra.
        parrafo = parrafo[:-1] + texto if parrafo.endswith("-") else (parrafo + " " + texto).strip()
    cerrar_parrafo()
    # Imágenes: cada una va con la sección dentro de la cual aparece (la última que empezó antes).
    vistos = set()
    for pagina in doc:
        n = 0
        for imagen in pagina.get_images(full=True):
            xref = imagen[0]
            if xref in vistos:
                continue
            vistos.add(xref)
            try:
                pix = pymupdf.Pixmap(doc, xref)
                if pix.width < LADO_MINIMO or pix.height < LADO_MINIMO:
                    continue
                if pix.colorspace is None or pix.colorspace.n > 3 or pix.alpha:
                    pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
                n += 1
                carpeta_medios.mkdir(parents=True, exist_ok=True)
                destino = carpeta_medios / f"p{pagina.number + 1}_{n}.png"
                pix.save(destino)
            except Exception:  # una imagen rara no debe tumbar todo el documento
                continue
            marcos = pagina.get_image_rects(xref)
            lugar = (pagina.number + 1, marcos[0].y0 if marcos else 0)
            duenas = [s for s in secciones if s["donde"] <= lugar and (s["parrafos"] or s["titulo"])]
            (duenas[-1] if duenas else secciones[0])["imagenes"].append(destino.relative_to(RAIZ / "web").as_posix())
    return secciones


def leer_docx(ruta, carpeta_medios):
    secciones = [{"titulo": None, "pagina": None, "parrafos": [], "imagenes": []}]
    with zipfile.ZipFile(ruta) as z:
        xml = z.read("word/document.xml").decode("utf-8")
        for parrafo in re.findall(r"<w:p[ >].*?</w:p>", xml, re.S):
            texto = limpiar(html.unescape("".join(re.findall(r"<w:t[^>]*>(.*?)</w:t>", parrafo, re.S))))
            if not texto:
                continue
            estilo = re.search(r'<w:pStyle w:val="([^"]+)"', parrafo)
            if estilo and re.match(r"(Heading|Ttulo|Titulo|Title|Subtitle|Subttulo)", estilo.group(1)) and len(texto) <= 90:
                secciones.append({"titulo": texto.rstrip(":"), "pagina": None, "parrafos": [], "imagenes": []})
            else:
                secciones[-1]["parrafos"].append(texto)
        for i, nombre in enumerate(n for n in z.namelist() if n.startswith("word/media/")):
            if Path(nombre).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                carpeta_medios.mkdir(parents=True, exist_ok=True)
                destino = carpeta_medios / f"imagen_{i + 1}{Path(nombre).suffix.lower()}"
                destino.write_bytes(z.read(nombre))
                secciones[0]["imagenes"].append(destino.relative_to(RAIZ / "web").as_posix())
    return secciones


def leer_texto(ruta, carpeta_medios):
    secciones = [{"titulo": None, "pagina": None, "parrafos": [], "imagenes": []}]
    bloques = re.split(r"\n\s*\n", ruta.read_text(encoding="utf-8", errors="replace").replace("\r\n", "\n"))
    for bloque in bloques:
        lineas = [l.strip() for l in bloque.strip().splitlines() if l.strip()]
        if not lineas:
            continue
        primera = lineas[0]
        suelto = len(lineas) == 1 and len(primera) <= 80 and not primera.endswith((".", ",", ";", ":"))
        if primera.startswith("#") or suelto:
            secciones.append({"titulo": limpiar(primera.lstrip("# ")), "pagina": None, "parrafos": [], "imagenes": []})
            lineas = lineas[1:]
        if lineas:
            secciones[-1]["parrafos"].append(limpiar(" ".join(lineas)))
    return secciones


# ---- De secciones a notas ----

def trocear(parrafos):
    """Agrupa párrafos en trozos de hasta TOPE_NOTA caracteres, sin cortar frases."""
    trozos, actual = [], ""
    for parrafo in parrafos:
        while len(parrafo) > TOPE_NOTA:  # párrafo enorme: se corta en el último punto que quepa
            corte = parrafo.rfind(". ", 0, TOPE_NOTA) + 1 or TOPE_NOTA
            if actual:
                trozos.append(actual)
                actual = ""
            trozos.append(parrafo[:corte].strip())
            parrafo = parrafo[corte:].strip()
        if actual and len(actual) + len(parrafo) + 1 > TOPE_NOTA:
            trozos.append(actual)
            actual = ""
        actual = (actual + " " + parrafo).strip()
    if actual:
        trozos.append(actual)
    return trozos


def titular(texto, pedir):
    """Título para un trozo sin encabezado: se lo pide al modelo; si falla, las primeras palabras."""
    try:
        titulo = pedir("Escribe solo un título de 2 a 6 palabras, en español y sin comillas ni punto final, "
                       "para este texto:\n\n" + texto[:700])
        titulo = seguro(titulo.splitlines()[0].strip(' "«».*#'), 60)
        if 2 <= len(titulo) <= 60:
            return titulo
    except Exception:
        pass
    return seguro(" ".join(texto.split()[:6]), 60)


def describir(ruta, pedir):
    """Le enseña una imagen al modelo y devuelve (título, descripción)."""
    import pymupdf
    pix = pymupdf.Pixmap(str(ruta))
    while max(pix.width, pix.height) > 1000:  # más pequeña = mucho más rápido en este equipo
        pix.shrink(1)
    if pix.alpha or pix.colorspace is None or pix.colorspace.n > 3:
        pix = pymupdf.Pixmap(pymupdf.csRGB, pix)
    respuesta = pedir("Mira la imagen. En la primera línea escribe solo un título de 2 a 6 palabras. Debajo, "
                      "describe en español, en dos o tres frases, lo que se ve, con los detalles que importan "
                      "(objetos, personas, texto visible, colores). No inventes lo que no se ve.",
                      base64.b64encode(pix.tobytes("png")).decode())
    lineas = [l.strip(' "«».*#') for l in respuesta.splitlines() if l.strip()]
    return seguro(lineas[0], 60), limpiar(" ".join(lineas[1:]) or lineas[0])


def procesar(ruta, pedir=pedir_directo, avisar=print):
    """Ingiere un archivo y devuelve un resumen de lo creado."""
    ruta = Path(ruta)
    extension = ruta.suffix.lower()
    if extension not in TIPOS:
        raise ValueError(f"No sé leer archivos {extension}")
    nombre = seguro(ruta.stem)
    carpeta, carpeta_medios = NOTAS / nombre, MEDIOS / nombre
    for vieja in (carpeta, carpeta_medios):  # volver a subir un documento lo reemplaza
        if vieja.exists():
            shutil.rmtree(vieja)
    ocupados = {p.stem.lower() for p in NOTAS.glob("**/*.md")}
    notas = []

    if extension in {".png", ".jpg", ".jpeg", ".webp"}:
        avisar(f"Mirando la imagen {ruta.name}…")
        carpeta_medios.mkdir(parents=True, exist_ok=True)
        copia = carpeta_medios / ruta.name
        shutil.copy(ruta, copia)
        try:
            titulo, texto = describir(ruta, pedir)
        except Exception as error:
            titulo, texto = nombre, f"Imagen {ruta.name} (no pude describirla: {error})."
        notas.append({"titulo": titulo, "texto": texto, "pagina": None,
                      "imagenes": [copia.relative_to(RAIZ / "web").as_posix()], "tipo": "imagen"})
    else:
        avisar(f"Leyendo {ruta.name}…")
        lector = {".pdf": leer_pdf, ".docx": leer_docx}.get(extension, leer_texto)
        secciones = [s for s in lector(ruta, carpeta_medios) if s["parrafos"] or s["imagenes"]]
        for s in secciones:
            trozos = trocear(s["parrafos"]) or ["(Sección sin texto, solo imágenes.)"]
            for i, trozo in enumerate(trozos):
                titulo = s["titulo"]
                if not titulo:
                    avisar("Poniéndole título a un trozo sin encabezado…")
                    titulo = titular(trozo, pedir)
                elif i:
                    titulo = f"{titulo} ({i + 1})"
                notas.append({"titulo": titulo, "texto": trozo, "pagina": s["pagina"],
                              "imagenes": s["imagenes"] if i == 0 else [], "tipo": "documento"})

    carpeta.mkdir(parents=True, exist_ok=True)
    creadas = []
    for nota in notas:
        titulo, n = seguro(nota["titulo"]), 2
        if titulo.lower() in ocupados:  # ya existe una nota con ese nombre: se distingue por el documento
            titulo = seguro(f"{titulo} ({nombre})")
        base = titulo
        while titulo.lower() in ocupados:
            titulo, n = f"{base} {n}", n + 1
        ocupados.add(titulo.lower())
        cabecera = [f"tipo: {nota['tipo']}", f"fuente: {ruta.name}"]
        if nota["pagina"]:
            cabecera.append(f"pagina: {nota['pagina']}")
        if nota["imagenes"]:
            cabecera.append("imagenes: " + ", ".join(nota["imagenes"]))
        (carpeta / f"{titulo}.md").write_text(
            "---\n" + "\n".join(cabecera) + "\nauto: true\n---\n" + nota["texto"] + "\n", encoding="utf-8")
        creadas.append(titulo)
    imagenes = sum(len(n["imagenes"]) for n in notas)
    avisar(f"{ruta.name}: {len(creadas)} notas y {imagenes} imágenes.")
    return {"documento": nombre, "notas": len(creadas), "imagenes": imagenes, "titulos": creadas}


if __name__ == "__main__":
    for archivo in sys.argv[1:]:
        print(json.dumps(procesar(archivo), ensure_ascii=False, indent=1))
