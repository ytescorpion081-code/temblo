// Avisos de sismos en Panamá para Cloudflare Workers (gratis, se ejecuta cada minuto).
// Revisa IGC-UP (Universidad de Panamá), USGS y EMSC y manda notificaciones push con ntfy.sh
// (llegan al celular aunque la app esté cerrada y la pantalla bloqueada).
//
// Configuración en Cloudflare:
//   Variable  NTFY_TOPIC   tema de ntfy (nombre difícil de adivinar)           [obligatoria]
//   Variable  MIN_MAG      magnitud mínima a avisar (por defecto 2.5)           [opcional]
//   KV        ESTADO       almacén donde se recuerda qué sismos ya se avisaron  [obligatoria]
//   Cron      * * * * *    (cada minuto)
const BOX = { la1: 5.5, la2: 10.5, lo1: -84, lo2: -76.5 };
const IGC = "https://sismosgeociencias.up.ac.pa/";
const MAX_INDIVIDUALES = 5;

const s0 = (q) => String(q.src || "").split(" ")[0];

export function igcT(f, h) {
  const m = String(h).match(/^(\d{1,2}):(\d\d):(\d\d)\s*([AP]M)$/i);
  if (!m || !/^\d{4}-\d\d-\d\d$/.test(f)) return NaN;
  const H = (+m[1]) % 12 + (/P/i.test(m[4]) ? 12 : 0);
  return Date.parse(`${f}T${String(H).padStart(2, "0")}:${m[2]}:${m[3]}-05:00`);
}

const limpia = (x) => x.replace(/<[^>]*>/g, "").replace(/&amp;/g, "&").replace(/&nbsp;/g, " ").trim();

export function parseIGC(html, desde = 0) {
  const out = [], seen = new Set();
  for (const tr of html.split(/<tr[\s>]/i).slice(1)) {
    const c = [...tr.matchAll(/<td[^>]*>([\s\S]*?)<\/td>/gi)].map((m) => limpia(m[1]));
    if (c.length < 8) continue;
    const t = igcT(c[1], c[2]), la = +c[3], lo = +c[4], mag = +c[6];
    if (![t, la, lo, mag].every(Number.isFinite) || t < desde) continue;
    const k = `${t}|${c[3]}|${c[4]}`;
    if (seen.has(k)) continue;           // el sitio a veces repite filas
    seen.add(k);
    const h = tr.match(/href\s*=\s*["']([^"']+)["']/i);
    let url = IGC;
    try { if (h) url = new URL(h[1].replace(/&amp;/g, "&"), IGC).href; } catch (e) {}
    out.push({ mag, place: c[7].replace(/^Localizado en\s*/i, ""), t, lo, la, z: parseFloat(c[5]) || 0,
               url, src: "IGC-UP", est: c[0] });
  }
  return out;
}

async function igc(minMag, desde) {
  const r = await fetch(IGC, { headers: { "User-Agent": "monitor-sismico-panama" } });
  if (!r.ok) throw new Error("IGC " + r.status);
  return parseIGC(await r.text(), desde).filter((q) => q.mag >= minMag && enCaja(q));
}
const enCaja = (q) => q.la >= BOX.la1 && q.la <= BOX.la2 && q.lo >= BOX.lo1 && q.lo <= BOX.lo2;

async function usgs(minMag, desde) {
  const ini = new Date(desde).toISOString().slice(0, 19);
  const r = await fetch("https://earthquake.usgs.gov/fdsnws/event/1/query?format=geojson&orderby=time&limit=200" +
    `&minmagnitude=${minMag}&starttime=${ini}&minlatitude=${BOX.la1}&maxlatitude=${BOX.la2}&minlongitude=${BOX.lo1}&maxlongitude=${BOX.lo2}`);
  if (!r.ok) throw new Error("USGS " + r.status);
  return (await r.json()).features.filter((f) => f.properties.mag != null).map((f) => ({
    mag: f.properties.mag, place: f.properties.place || "Panamá", t: f.properties.time,
    lo: f.geometry.coordinates[0], la: f.geometry.coordinates[1], z: f.geometry.coordinates[2],
    url: f.properties.url || "", src: "USGS" }));
}

async function emsc(minMag, desde) {
  const ini = new Date(desde).toISOString().slice(0, 19);
  const r = await fetch("https://www.seismicportal.eu/fdsnws/event/1/query?format=json&orderby=time&limit=200" +
    `&minmag=${minMag}&start=${ini}&minlat=${BOX.la1}&maxlat=${BOX.la2}&minlon=${BOX.lo1}&maxlon=${BOX.lo2}`);
  if (!r.ok) throw new Error("EMSC " + r.status);
  return (await r.json()).features.filter((f) => f.properties.mag != null).map((f) => ({
    mag: f.properties.mag, place: f.properties.flynn_region || "Panamá", t: Date.parse(f.properties.time),
    lo: f.properties.lon, la: f.properties.lat, z: f.properties.depth || 0,
    url: "https://www.seismicportal.eu/eventdetails.html?unid=" + f.properties.unid, src: "EMSC" }));
}

// Misma fuente: solo si es idéntico (o la versión preliminar y la revisada del mismo sismo).
// Fuentes distintas: mismo sismo si coincide hora, zona y magnitud parecida.
export function parecido(a, b) {
  if (a.src && s0(a) === s0(b)) {
    if (a.est && b.est && a.est !== b.est && a.mag != null && b.mag != null && Math.abs(a.t - b.t) < 18e4 &&
        Math.abs(a.la - b.la) < .2 && Math.abs(a.lo - b.lo) < .2 && Math.abs(a.mag - b.mag) < .35) return true;
    return Math.abs(a.t - b.t) < 1500 && Math.abs(a.la - b.la) < .002 && Math.abs(a.lo - b.lo) < .002;
  }
  return Math.abs(a.t - b.t) < 9e4 && Math.abs(a.la - b.la) < .7 && Math.abs(a.lo - b.lo) < .7 &&
    (a.mag == null || b.mag == null || Math.abs(a.mag - b.mag) < 1);
}

// Une las fuentes; el IGC-UP (red oficial) tiene prioridad y las demás quedan como "alt".
export function unir(lista) {
  const out = [];
  for (const q of lista.slice().sort((x, y) => y.t - x.t || (s0(y) === "IGC-UP") - (s0(x) === "IGC-UP"))) {
    let k = -1, mejor = 1e9;
    out.forEach((o, i) => {
      if (parecido(o, q)) {
        const sc = Math.abs(o.t - q.t) / 1000 + 60 * (Math.abs(o.la - q.la) + Math.abs(o.lo - q.lo));
        if (sc < mejor) { mejor = sc; k = i; }
      }
    });
    if (k < 0) { out.push({ ...q, alt: [] }); continue; }
    const o = out[k];
    if (s0(o) === s0(q)) { if (q.est === "REVISADO" && o.est !== "REVISADO") out[k] = { ...q, alt: o.alt }; continue; }
    const prim = (s0(q) === "IGC-UP" && s0(o) !== "IGC-UP") ? q : o, sec = prim === q ? o : q;
    const alt = {};
    (o.alt || []).forEach((a) => (alt[a.src] = a.mag));
    if (Math.abs(sec.mag - prim.mag) >= .05) alt[s0(sec)] = sec.mag;
    out[k] = { ...prim, alt: Object.entries(alt).map(([src, mag]) => ({ src, mag })) };
  }
  return out;
}

function texto(q, ahora) {
  const hora = new Date(q.t - 5 * 3600e3).toISOString().slice(11, 19);
  const min = Math.max(0, Math.round((ahora - q.t) / 60000));
  const otras = (q.alt || []).map((a) => ` · ${a.src} ${a.mag.toFixed(1)}`).join("");
  return `Sismo M ${q.mag.toFixed(1)} (${q.src}${otras})\n${q.place}\nOcurrió a las ${hora} (hora de Panama), hace ${min} min\n` +
    `Profundidad: ${Math.abs(q.z).toFixed(0)} km\n${q.url}\n\nSi sientes un temblor: agachate, cubrete y sujetate. Emergencias: 911`;
}

async function enviar(env, titulo, cuerpo, mag, click) {
  if (env.NTFY_TOPIC) {
    const prio = mag >= 5 ? "urgent" : mag >= 4 ? "high" : "default";
    await fetch(`https://ntfy.sh/${encodeURIComponent(env.NTFY_TOPIC)}`, {
      method: "POST", body: cuerpo,
      headers: { Title: titulo, Priority: prio, Tags: "rotating_light,earthquake", Click: click || IGC } });
  }
  if (env.TELEGRAM_TOKEN && env.TELEGRAM_CHAT_ID) {
    await fetch(`https://api.telegram.org/bot${env.TELEGRAM_TOKEN}/sendMessage`, {
      method: "POST", headers: { "content-type": "application/json" },
      body: JSON.stringify({ chat_id: env.TELEGRAM_CHAT_ID, text: "🌋 " + cuerpo, disable_web_page_preview: true }) });
  }
}

export async function revisar(env, ahora = Date.now()) {
  const minMag = +(env.MIN_MAG || 2.5), desde = ahora - 24 * 3600e3;
  const r = await Promise.allSettled([igc(minMag, desde), usgs(minMag, desde), emsc(minMag, desde)]);
  const todos = r.flatMap((x) => (x.status === "fulfilled" ? x.value : []));
  r.forEach((x, i) => x.status === "rejected" && console.log("Fuente caída:", ["IGC-UP", "USGS", "EMSC"][i], x.reason));
  if (!todos.length) return "sin datos";
  let vistos = await env.ESTADO.get("vistos", "json");
  const primera = !vistos;
  vistos = (vistos || []).filter((v) => v.t > ahora - 48 * 3600e3);
  const nuevos = unir(todos).filter((q) => !vistos.some((v) => parecido(q, v)));
  if (primera) {
    await enviar(env, "Alertas de sismos activadas", "Alertas de sismos de Panama activadas. Te avisare cuando haya un sismo nuevo.\n\nNo sustituye las alertas oficiales de SINAPROC ni del IGC-UP.", 0);
  } else if (nuevos.length > MAX_INDIVIDUALES) {
    const top = nuevos.slice().sort((a, b) => b.mag - a.mag).slice(0, 3);
    await enviar(env, `${nuevos.length} sismos nuevos en Panama`,
      `${nuevos.length} sismos nuevos en Panama (mayores):\n` + top.map((q) => `- M ${q.mag.toFixed(1)} · ${q.place}`).join("\n") + `\n\nMas detalle: ${IGC}`, top[0].mag);
  } else {
    for (const q of nuevos.sort((a, b) => a.t - b.t)) await enviar(env, `Sismo M${q.mag.toFixed(1)} en Panama`, texto(q, ahora), q.mag, q.url);
  }
  if (primera || nuevos.length) {
    await env.ESTADO.put("vistos", JSON.stringify(vistos.concat(nuevos.map((q) => ({ t: q.t, la: q.la, lo: q.lo, src: q.src, est: q.est, mag: q.mag })))));
  }
  return `${todos.length} eventos, ${nuevos.length} nuevos${primera ? " (primera ejecución)" : ""}`;
}

export default {
  async scheduled(event, env, ctx) { ctx.waitUntil(revisar(env)); },
  async fetch(req, env) {
    if (new URL(req.url).searchParams.has("probar")) {
      await enviar(env, "Prueba de aviso", "✅ Prueba: si ves esto en tu celular con la pantalla bloqueada, los avisos con la app cerrada funcionan.", 3);
      return new Response("Prueba enviada. Revisa tu celular.");
    }
    return new Response("Monitor sismico de Panama: activo. Agrega /?probar para enviar un aviso de prueba.");
  },
};
