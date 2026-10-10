# Avisos por Telegram con la app cerrada (opcional)

La app solo puede sonar con la página abierta. Para recibir un mensaje en el teléfono cuando hay un sismo **aunque la app esté cerrada**, el repositorio puede publicar en un canal de Telegram. Es opcional: si no configuras nada, no pasa nada.

## Qué esperar (y qué no)
- Es **informativo**, no una alerta temprana. Llega **después** del sismo.
- Se revisa cada 5 minutos o más: GitHub no garantiza la puntualidad y a veces tarda decenas de minutos.
- Usa USGS, EMSC y el IGC‑UP; los catálogos pueden tardar en publicar un evento.
- Por seguridad usa un **canal** de Telegram donde solo tú publicas. No uses un tema público de ntfy: cualquiera podría enviar avisos falsos.

## Pasos
1. En Telegram abre **@BotFather** → `/newbot` → guarda el **token** que te da.
2. Crea un **canal público** (por ejemplo `@temblo_panama`) y agrega tu bot como **administrador** con permiso de publicar.
3. En GitHub, repositorio `temblo` → **Settings → Secrets and variables → Actions → Secrets** → crea:
   - `TELEGRAM_TOKEN` = el token del bot.
   - `TELEGRAM_CHAT` = el nombre del canal, p. ej. `@temblo_panama`.
4. (Opcional) En la pestaña **Variables** puedes crear `AVISO_MAGNITUD` (por defecto `4.0`) y `AVISO_EDAD_MIN` (por defecto `60`: no avisa de sismos con más de 60 minutos).
5. En **Actions → Actualizar listado IGC-UP y avisos → Run workflow** para probar.
6. Para que la app muestre el botón «Unirme al canal», agrega esto a `informe.json` (después de `"version": 2,`) y **sube el valor de `"actualizado"`** a una fecha mayor:

```json
"canal": { "nombre": "Telegram", "url": "https://t.me/temblo_panama", "minmag": 4 },
```

## Notas
- El estado de lo ya avisado se guarda en `avisos_estado.json` (se crea solo).
- Para apagar los avisos, borra los secretos `TELEGRAM_TOKEN` y `TELEGRAM_CHAT`.
- Si el canal se llena de mensajes, sube `AVISO_MAGNITUD`.
