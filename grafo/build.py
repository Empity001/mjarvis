#!/usr/bin/env python3
"""Convierte la carpeta de notas (formato Obsidian) en graph.json.

Cada nota .md es un nodo. Hay conexión entre dos notas cuando una enlaza a la otra con
[[enlace]] o, simplemente, cuando el texto de una nombra el título de la otra: así los
documentos que Jarvis ingiere solo se conectan sin que nadie escriba los enlaces.

Uso: python3 build.py <carpeta_notas> <salida.json>
"""
import json
import re
import sys
import unicodedata
from pathlib import Path

ENLACE = re.compile(r"\[\[([^\]|#]+)(?:[|#][^\]]*)?\]\]")
FRONT = re.compile(r"\A---\n(.*?)\n---\n", re.S)


def plano(texto):
    t = unicodedata.normalize("NFKD", texto.lower())
    t = "".join(c for c in t if not unicodedata.combining(c))
    return " " + " ".join(re.findall(r"[a-z0-9]+", t)) + " "


def leer(ruta):
    """Devuelve (metadatos, cuerpo con enlaces, texto limpio) de una nota."""
    texto = ruta.read_text(encoding="utf-8").replace("\r\n", "\n")
    meta = {}
    m = FRONT.match(texto)
    if m:
        for linea in m.group(1).splitlines():
            if ":" in linea:
                k, v = linea.split(":", 1)
                meta[k.strip()] = v.strip()
        texto = texto[m.end():]
    cuerpo = "\n".join(l for l in texto.splitlines() if not l.startswith("#")).strip()
    limpio = " ".join(ENLACE.sub(lambda e: e.group(1).strip(), cuerpo).split())
    return meta, cuerpo, limpio


def main(carpeta, salida):
    nodos, enlaces, vistos, textos = {}, [], set(), {}

    def unir(a, b):
        par = tuple(sorted((a, b)))
        if a != b and par not in vistos:
            vistos.add(par)
            enlaces.append({"a": a, "b": b})

    for ruta in sorted(Path(carpeta).glob("**/*.md")):
        if any(parte.startswith("_") for parte in ruta.relative_to(carpeta).parts):
            continue  # carpetas que empiezan por "_" no son conocimiento (p. ej. reglas de personalidad)
        meta, cuerpo, limpio = leer(ruta)
        nombre = ruta.stem
        nodo = {"id": nombre, "tipo": meta.get("tipo", "dato"), "resumen": limpio}
        if meta.get("fuente"):
            nodo["fuente"] = meta["fuente"]
            nodo["pagina"] = int(meta["pagina"]) if meta.get("pagina", "").isdigit() else None
        if meta.get("imagenes"):
            nodo["imagenes"] = [i.strip() for i in meta["imagenes"].split(",") if i.strip()]
        nodos[nombre] = nodo
        textos[nombre] = plano(limpio)
        for destino in ENLACE.findall(cuerpo):
            unir(nombre, destino.strip())
    # Enlaces a notas que aún no existen: nodo fantasma, como en Obsidian.
    for e in enlaces:
        for extremo in (e["a"], e["b"]):
            nodos.setdefault(extremo, {"id": extremo, "tipo": "fantasma", "resumen": "(nota sin escribir)"})
    # Conexiones por mención: el texto de una nota nombra el título de otra.
    titulos = {n: plano(n) for n in textos if len(plano(n).strip()) >= 4}
    for nombre, texto in textos.items():
        for otro, titulo in titulos.items():
            if otro != nombre and titulo in texto:
                unir(nombre, otro)
    temas = agrupar(nodos, enlaces)
    Path(salida).parent.mkdir(parents=True, exist_ok=True)
    Path(salida).write_text(
        json.dumps({"nodos": list(nodos.values()), "enlaces": enlaces, "temas": temas}, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"{len(nodos)} nodos, {len(enlaces)} conexiones, {len(temas)} temas -> {salida}")


def agrupar(nodos, enlaces):
    """Detecta temas (comunidades) fusionando grupos mientras suba la modularidad.

    Deja en cada nodo su "grupo" y devuelve la lista de temas, del mayor al menor,
    nombrados por sus nodos más conectados.
    """
    grado = {n: 0 for n in nodos}
    for e in enlaces:
        grado[e["a"]] += 1
        grado[e["b"]] += 1
    m2 = 2 * len(enlaces) or 1
    grupo = {n: i for i, n in enumerate(nodos)}
    miembros = {i: [n] for n, i in grupo.items()}
    while True:
        entre, peso = {}, {g: sum(grado[n] for n in ns) for g, ns in miembros.items()}
        for e in enlaces:
            ga, gb = grupo[e["a"]], grupo[e["b"]]
            if ga != gb:
                par = (min(ga, gb), max(ga, gb))
                entre[par] = entre.get(par, 0) + 1
        mejor, ganancia = None, 1e-9
        for (ga, gb), n in sorted(entre.items()):
            dq = 2 * (n / m2 - peso[ga] * peso[gb] / (m2 * m2))
            if dq > ganancia:
                mejor, ganancia = (ga, gb), dq
        if not mejor:
            break
        ga, gb = mejor
        for n in miembros.pop(gb):
            grupo[n] = ga
            miembros[ga].append(n)
    temas = []
    orden = sorted(miembros.values(), key=lambda ns: (-len(ns), ns[0]))
    for i, ns in enumerate(orden):
        ns.sort(key=lambda n: (-grado[n], n))
        for n in ns:
            nodos[n]["grupo"] = i
        temas.append({"id": i, "nombre": ns[0], "clave": ns[:3], "nodos": len(ns),
                      "pct": round(100 * len(ns) / len(nodos))})
    return temas


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
