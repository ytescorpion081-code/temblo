#!/usr/bin/env python3
"""Descarga el listado de sismos del IGC-UP y lo guarda como igc.json (para la app).
Se ejecuta cada 5 minutos con GitHub Actions (igc.yml). Solo usa la librería estándar."""
import json, os, urllib.request
from igc_lib import URL, parse_igc

req = urllib.request.Request(URL, headers={"User-Agent": "temblo-panama-igc"})
try:
    with urllib.request.urlopen(req, timeout=40) as r:
        datos = parse_igc(r.read().decode("utf-8", "replace"))
except Exception as e:
    raise SystemExit(f"No se pudo leer el IGC-UP: {e}")
if not datos:
    raise SystemExit("La página no devolvió filas; no se modifica igc.json")
datos.sort(key=lambda q: -q["t"])
nuevo = json.dumps(datos, ensure_ascii=False, separators=(",", ":"))
viejo = open("igc.json", encoding="utf-8").read() if os.path.exists("igc.json") else ""
if nuevo != viejo:
    open("igc.json", "w", encoding="utf-8").write(nuevo)
print(f"{len(datos)} sismos del IGC-UP", "(actualizado)" if nuevo != viejo else "(sin cambios)")
