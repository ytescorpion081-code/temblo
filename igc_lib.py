# Lector del listado de sismos del IGC-UP (https://sismosgeociencias.up.ac.pa/)
import re
from datetime import datetime, timezone, timedelta
from html.parser import HTMLParser
from urllib.parse import urljoin

URL = "https://sismosgeociencias.up.ac.pa/"
PANAMA = timezone(timedelta(hours=-5))


class _Tabla(HTMLParser):
    def __init__(self):
        super().__init__()
        self.filas, self.fila, self.celda = [], None, None

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.fila = {"c": [], "href": None}
        elif tag == "td" and self.fila is not None:
            self.celda = ""
        elif tag == "a" and self.fila is not None and not self.fila["href"]:
            self.fila["href"] = dict(attrs).get("href")

    def handle_data(self, d):
        if self.celda is not None:
            self.celda += d

    def handle_endtag(self, tag):
        if tag == "td" and self.fila is not None and self.celda is not None:
            self.fila["c"].append(self.celda.strip())
            self.celda = None
        elif tag == "tr" and self.fila is not None:
            self.filas.append(self.fila)
            self.fila = None


def parse_igc(html):
    t = _Tabla()
    t.feed(html)
    out, vistos = [], set()
    for f in t.filas:
        c = f["c"]
        if len(c) < 8 or not re.fullmatch(r"\d{4}-\d\d-\d\d", c[1]):
            continue
        m = re.fullmatch(r"(\d{1,2}):(\d\d):(\d\d)\s*([AP]M)", c[2], re.I)
        if not m:
            continue
        h = int(m[1]) % 12 + (12 if m[4].upper() == "PM" else 0)
        dt = datetime.fromisoformat(f"{c[1]}T{h:02d}:{m[2]}:{m[3]}").replace(tzinfo=PANAMA)
        try:
            la, lo, mag = float(c[3]), float(c[4]), float(c[6])
        except ValueError:
            continue
        z = re.match(r"[\d.]+", c[5])
        ms = int(dt.timestamp() * 1000)
        if (ms, la, lo) in vistos:          # el sitio a veces repite filas
            continue
        vistos.add((ms, la, lo))
        out.append(dict(id=f"i{ms}|{c[3]}|{c[4]}", mag=mag, place=re.sub(r"^Localizado en\s*", "", c[7]),
                        t=ms, lo=lo, la=la, z=float(z[0]) if z else 0.0,
                        url=urljoin(URL, f["href"]) if f["href"] else URL, est=c[0], src="IGC-UP"))
    return out
