#!/usr/bin/env python3
"""Descarga el listado de sismos del IGC-UP y lo guarda como igc.json (para la app).
Se ejecuta cada 5 minutos con GitHub Actions (.github/workflows/igc.yml). Solo usa la librería estándar.

Además escribe igc_estado.json (un "latido"): {"ok": <ms de la última lectura correcta>, "n": <filas>}.
Se reescribe como máximo una vez por hora (o si cambia el número de filas) para no llenar el
historial de commits; la app avisa si el latido tiene más de 3 horas."""
import json, os, time, urllib.request
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

# Latido: prueba de que la lectura sigue funcionando aunque no haya sismos nuevos
ahora = int(time.time() * 1000)
try:
    previo = json.load(open("igc_estado.json", encoding="utf-8"))
except Exception:
    previo = {}
if not previo or previo.get("n") != len(datos) or ahora - int(previo.get("ok", 0)) > 3600 * 1000:
    open("igc_estado.json", "w", encoding="utf-8").write(json.dumps({"ok": ahora, "n": len(datos)}))

print(f"{len(datos)} sismos del IGC-UP", "(actualizado)" if nuevo != viejo else "(sin cambios)")
