#!/usr/bin/env python3
"""Genera noticias.json: titulares recientes sobre el terremoto en Panamá y las cifras que mencionan.

Usa solo la librería estándar. Lee el buscador de noticias (RSS) de Google News, que reúne titulares de
medios de prensa y televisión. SOLO guarda titular, medio, enlace y hora (no copia el texto de las
notas). Las cifras se extraen automáticamente del titular y NO están verificadas.
Se ejecuta cada pocos minutos con GitHub Actions (datos.yml).
"""
import json, os, re, urllib.request, urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

CONSULTAS = ["terremoto Panamá", "sismo Panamá Sinaproc", "réplicas Panamá Tonosí"]
VENTANA_H = 72
RELEVANTE = re.compile(r"terremoto|sismo|temblor|réplica|replica|sinaproc", re.I)
LOCAL = re.compile(r"panam[aá]|tonos[ií]|coiba|son[aá]\b|penonom[eé]|sinaproc|azuero|veraguas|coclé|chitr[eé]|las tablas", re.I)

PAL = {"un": 1, "una": 1, "dos": 2, "tres": 3, "cuatro": 4, "cinco": 5, "seis": 6, "siete": 7, "ocho": 8,
       "nueve": 9, "diez": 10, "once": 11, "doce": 12}
CLAVES = [
    ("fallecidos", r"muertos|muertes|fallecidos|fallecidas|víctimas mortales|víctimas fatales"),
    ("heridos", r"heridos|heridas|lesionados|lesionadas"),
    ("desaparecidos", r"desaparecidos|desaparecidas"),
    ("viviendas", r"viviendas|casas|inmuebles"),
    ("escuelas", r"escuelas|centros educativos|planteles|colegios"),
    ("replicas", r"réplicas|replicas"),
]


def cifras(titulo):
    """Devuelve [(tipo, numero)] encontrados en el titular. Es solo una ayuda: no está verificado."""
    low = titulo.lower()
    out = []
    for tipo, pal in CLAVES:
        rx = (r"(?<![\w.,])(\d{1,3}(?:[.,]\d{3})+|\d+|" + "|".join(PAL) + r")\s+(?:[a-záéíóúñ]+\s+){0,2}?(?:" + pal + r")\b")
        for m in re.finditer(rx, low):
            tok = m.group(1)
            n = PAL[tok] if tok in PAL else int(re.sub(r"[.,]", "", tok))
            if 0 < n < 100000 and (tipo, n) not in out:
                out.append((tipo, n))
    return out


def leer_rss(xml_texto):
    items = []
    raiz = ET.fromstring(xml_texto)
    for it in raiz.iter("item"):
        titulo = (it.findtext("title") or "").strip()
        enlace = (it.findtext("link") or "").strip()
        fuente_el = it.find("source")
        fuente = (fuente_el.text or "").strip() if fuente_el is not None else ""
        try:
            fecha = int(parsedate_to_datetime(it.findtext("pubDate")).timestamp() * 1000)
        except Exception:
            continue
        if fuente and titulo.endswith(" - " + fuente):
            titulo = titulo[: -len(fuente) - 3].strip()
        elif " - " in titulo and not fuente:
            titulo, fuente = titulo.rsplit(" - ", 1)
        if titulo and enlace.startswith("https://"):
            items.append(dict(t=titulo, f=fuente or "Medio", u=enlace, d=fecha))
    return items


def descargar(q):
    url = "https://news.google.com/rss/search?" + urllib.parse.urlencode(
        {"q": f"{q} when:3d", "hl": "es-419", "gl": "PA", "ceid": "PA:es-419"})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (temblo-panama)"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", "replace")


def construir(todos, ahora_ms):
    corte = ahora_ms - VENTANA_H * 3600 * 1000
    vistos, items = set(), []
    for it in sorted(todos, key=lambda x: -x["d"]):
        clave = re.sub(r"\W+", " ", it["t"].lower()).strip()[:90]
        if it["d"] < corte or clave in vistos:
            continue
        if not (RELEVANTE.search(it["t"]) and LOCAL.search(it["t"])):
            continue          # descarta titulares de otros países o de otros temas
        vistos.add(clave)
        items.append(it)
    items = items[:40]
    cif = []
    for it in items:
        for tipo, n in cifras(it["t"]):
            cif.append(dict(k=tipo, n=n, t=it["t"], f=it["f"], u=it["u"], d=it["d"]))
    return items, cif


def main():
    ahora = int(datetime.now(timezone.utc).timestamp() * 1000)
    todos = []
    for q in CONSULTAS:
        try:
            todos += leer_rss(descargar(q))
        except Exception as e:
            print("Consulta fallida:", q, e)
    if not todos:
        raise SystemExit("Sin resultados; no se modifica noticias.json")
    items, cif = construir(todos, ahora)
    previo = {}
    if os.path.exists("noticias.json"):
        try:
            previo = json.load(open("noticias.json", encoding="utf-8"))
        except Exception:
            pass
    if previo.get("items") == items and previo.get("cifras") == cif:
        print(f"{len(items)} titulares (sin cambios)")
        return
    json.dump(dict(actualizado=datetime.now(timezone.utc).isoformat(), items=items, cifras=cif),
              open("noticias.json", "w", encoding="utf-8"), ensure_ascii=False, separators=(",", ":"))
    print(f"{len(items)} titulares, {len(cif)} cifras mencionadas (actualizado)")


if __name__ == "__main__":
    main()
