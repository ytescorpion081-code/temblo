#!/usr/bin/env python3
"""Descarga titulares sobre el terremoto/réplicas en Panamá y los guarda en noticias.json."""
import json
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

CONSULTAS = [
    "terremoto Panamá",
    "sismo Panamá réplicas",
    "Sinaproc terremoto",
    "IGC-UP sismo",
]
MAX_TITULARES = 25
SALIDA = "noticias.json"


def bajar(consulta):
    q = urllib.parse.quote(consulta)
    url = f"https://news.google.com/rss/search?q={q}+when:3d&hl=es-419&gl=PA&ceid=PA:es-419"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as r:
        raiz = ET.fromstring(r.read())
    items = []
    for it in raiz.iter("item"):
        titulo = (it.findtext("title") or "").strip()
        enlace = (it.findtext("link") or "").strip()
        fuente = (it.findtext("source") or "").strip()
        fecha = it.findtext("pubDate") or ""
        try:
            dt = parsedate_to_datetime(fecha).astimezone(timezone.utc)
        except Exception:
            continue
        if fuente and titulo.endswith(" - " + fuente):
            titulo = titulo[: -len(fuente) - 3]
        if titulo and enlace:
            items.append({"t": titulo, "u": enlace, "f": fuente or "Google Noticias", "d": int(dt.timestamp() * 1000)})
    return items


def main():
    todos = {}
    for c in CONSULTAS:
        try:
            for n in bajar(c):
                todos[n["u"]] = n
        except Exception as e:
            print(f"Error con '{c}': {e}")
    lista = sorted(todos.values(), key=lambda n: n["d"], reverse=True)[:MAX_TITULARES]
    if not lista:
        print("Sin titulares; no se modifica el archivo.")
        return
    datos = {"actualizado": datetime.now(timezone.utc).isoformat(), "items": lista, "cifras": []}
    with open(SALIDA, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=1)
    print(f"{len(lista)} titulares guardados.")


if __name__ == "__main__":
    main()
