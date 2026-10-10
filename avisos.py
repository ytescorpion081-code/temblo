#!/usr/bin/env python3
"""Envía un mensaje a un canal de Telegram cuando hay un sismo nuevo en la región (app cerrada).

Es OPCIONAL: si no existen los secretos TELEGRAM_TOKEN y TELEGRAM_CHAT, no hace nada.
Se ejecuta desde .github/workflows/igc.yml (cada 5 minutos o más; GitHub no garantiza la puntualidad).
Usa USGS, EMSC y el igc.json que genera igc.py. Solo usa la librería estándar.

Variables de entorno:
  TELEGRAM_TOKEN   token del bot (BotFather)
  TELEGRAM_CHAT    canal, p. ej. @temblo_panama
  AVISO_MAGNITUD   magnitud mínima (por defecto 4.0)
  AVISO_EDAD_MIN   no avisar de sismos con más de N minutos (por defecto 60)
"""
import json, os, sys, time, urllib.parse, urllib.request
from datetime import datetime, timedelta, timezone

LA1, LA2, LO1, LO2 = 5.5, 10.5, -84.0, -76.5      # misma región que la app
ESTADO = "avisos_estado.json"
TOKEN = os.environ.get("TELEGRAM_TOKEN", "").strip()
CHAT = os.environ.get("TELEGRAM_CHAT", "").strip()
MIN_MAG = float(os.environ.get("AVISO_MAGNITUD") or 4.0)
MAX_EDAD = int(os.environ.get("AVISO_EDAD_MIN") or 60) * 60 * 1000
PRIORIDAD = {"IGC-UP": 0, "USGS": 1, "EMSC": 2}


def get_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "temblo-panama-avisos"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def desde_iso(dias=1):
    return (datetime.now(timezone.utc) - timedelta(days=dias)).strftime("%Y-%m-%dT%H:%M:%S")


def usgs():
    j = get_json("https://earthquake.usgs.gov/fdsnws/event/1/query?" + urllib.parse.urlencode({
        "format": "geojson", "orderby": "time", "limit": 200, "minmagnitude": MIN_MAG,
        "starttime": desde_iso(), "minlatitude": LA1, "maxlatitude": LA2, "minlongitude": LO1, "maxlongitude": LO2}))
    return [dict(mag=f["properties"]["mag"], t=f["properties"]["time"], la=f["geometry"]["coordinates"][1],
                 lo=f["geometry"]["coordinates"][0], z=f["geometry"]["coordinates"][2] or 0,
                 place=f["properties"].get("place") or "Panamá", url=f["properties"].get("url") or "", src="USGS")
            for f in j["features"] if f["properties"].get("mag") is not None]


def emsc():
    j = get_json("https://www.seismicportal.eu/fdsnws/event/1/query?" + urllib.parse.urlencode({
        "format": "json", "orderby": "time", "limit": 200, "minmag": MIN_MAG,
        "start": desde_iso(), "minlat": LA1, "maxlat": LA2, "minlon": LO1, "maxlon": LO2}))
    out = []
    for f in j["features"]:
        p = f["properties"]
        if p.get("mag") is None:
            continue
        t = int(datetime.fromisoformat(p["time"].replace("Z", "+00:00")).timestamp() * 1000)
        out.append(dict(mag=p["mag"], t=t, la=p["lat"], lo=p["lon"], z=p.get("depth") or 0,
                        place=p.get("flynn_region") or "Panamá",
                        url="https://www.seismicportal.eu/eventdetails.html?unid=" + str(p.get("unid", "")), src="EMSC"))
    return out


def igc():
    if not os.path.exists("igc.json"):
        return []
    ini = int(time.time() * 1000) - 86400000
    return [dict(mag=q["mag"], t=q["t"], la=q["la"], lo=q["lo"], z=q.get("z", 0), place=q.get("place") or "Panamá",
                 url=q.get("url") or "", src="IGC-UP")
            for q in json.load(open("igc.json", encoding="utf-8"))
            if q["mag"] >= MIN_MAG and q["t"] >= ini and LA1 <= q["la"] <= LA2 and LO1 <= q["lo"] <= LO2]


def mismo(a, b):
    """Misma regla que la app: 2 min, 0,5° y hasta 1 de diferencia de magnitud."""
    return (abs(a["t"] - b["t"]) < 120000 and abs(a["la"] - b["la"]) < 0.5 and abs(a["lo"] - b["lo"]) < 0.5
            and abs(a["mag"] - b["mag"]) <= 1)


def unir(lista):
    lista.sort(key=lambda q: -q["t"])
    out = []
    for q in lista:
        i = next((k for k, r in enumerate(out) if mismo(r, q)), -1)
        if i < 0:
            q["otros"] = []
            out.append(q)
            continue
        r = out[i]
        ganador, perdedor = (q, r) if PRIORIDAD[q["src"]] < PRIORIDAD[r["src"]] else (r, q)
        otros = (ganador.get("otros") or []) + (perdedor.get("otros") or []) + [(perdedor["src"], perdedor["mag"])]
        ganador["otros"] = list({s: m for s, m in otros if s != ganador["src"]}.items())
        out[i] = ganador
    return out


def hace(ms):
    m = max(0, int((time.time() * 1000 - ms) / 60000))
    return "hace instantes" if m < 1 else f"hace {m} min" if m < 60 else f"hace {m // 60} h"


def texto(q):
    otras = ""
    if q["otros"]:
        otras = "\nOtras fuentes: " + " · ".join(f"{s} M {m:.1f}" for s, m in q["otros"])
    return (f"⚠️ Sismo M {q['mag']:.1f} · {q['place']}\n"
            f"{hace(q['t'])} · prof. {round(q['z'])} km · fuente: {q['src']}{otras}\n"
            f"{q['url']}\n\n"
            "Si sientes un temblor: agáchate, cúbrete y sujétate. Información referencial y automática; "
            "no es una alerta oficial. Sigue los avisos de SINAPROC (520‑4400) y del IGC‑UP.")


def enviar(msg):
    datos = urllib.parse.urlencode({"chat_id": CHAT, "text": msg, "disable_web_page_preview": "true"}).encode()
    with urllib.request.urlopen(urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/sendMessage", data=datos),
                                timeout=30) as r:
        if not json.loads(r.read().decode()).get("ok"):
            raise RuntimeError("Telegram rechazó el mensaje")


def main():
    if not TOKEN or not CHAT:
        print("Avisos desactivados (faltan TELEGRAM_TOKEN y TELEGRAM_CHAT).")
        return 0
    try:
        previo = json.load(open(ESTADO, encoding="utf-8"))
    except Exception:
        previo = []
    ahora = int(time.time() * 1000)
    previo = [p for p in previo if ahora - p["t"] < 3 * 86400000]

    fuentes, fallos = [], 0
    for f in (usgs, emsc, igc):
        try:
            fuentes += f()
        except Exception as e:
            fallos += 1
            print(f"Aviso: no se pudo leer {f.__name__}: {e}", file=sys.stderr)
    if fallos >= 2 and not fuentes:     # USGS y EMSC caídos y sin datos locales: avisar con un error visible en Actions
        print("No se pudo leer ninguna fuente.", file=sys.stderr)
        return 1

    enviados, error = 0, False
    for q in reversed(unir(fuentes)):                        # del más antiguo al más nuevo
        if q["mag"] < MIN_MAG or ahora - q["t"] > MAX_EDAD or ahora - q["t"] < -120000:
            continue
        if any(mismo(p, q) or (abs(p["t"] - q["t"]) < 120000 and abs(p["la"] - q["la"]) < 0.7
                               and abs(p["lo"] - q["lo"]) < 0.7) for p in previo):
            continue
        try:
            enviar(texto(q))
        except Exception as e:                               # se reintenta en la próxima corrida
            print(f"No se pudo enviar el aviso: {e}", file=sys.stderr)
            error = True
            continue
        previo.append(dict(t=q["t"], la=q["la"], lo=q["lo"], mag=q["mag"]))
        enviados += 1

    nuevo = json.dumps(previo, separators=(",", ":"))
    viejo = open(ESTADO, encoding="utf-8").read() if os.path.exists(ESTADO) else ""
    if enviados and nuevo != viejo:
        open(ESTADO, "w", encoding="utf-8").write(nuevo)
    print(f"{enviados} aviso(s) enviado(s).")
    return 1 if error else 0


if __name__ == "__main__":
    sys.exit(main())
