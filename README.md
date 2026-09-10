# TheWhaleFiles

Plataforma web para seguir y analizar las carteras declaradas por políticos
estadounidenses y directivos de empresas cotizadas, a partir de sus
declaraciones oficiales de transparencia financiera.

Muestra lo declarado. No interpreta intenciones, no acusa a nadie y no es
asesoramiento de inversión.

## Stack

- FastAPI
- SQLAlchemy
- SQLite en local, Postgres en el despliegue
- Jinja2 + HTML/CSS para la interfaz

## Arranque rápido

1. Crear entorno virtual:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Instalar dependencias:
   ```bash
   python -m pip install -r requirements.txt
   ```

3. Ejecutar la app:
   ```bash
   python -m app
   ```

4. Abrir la app en el navegador:
   ```text
   http://localhost:8000
   ```

La primera vez la base se siembra sola descargando el dataset público del
Congreso. Con `SEED_REAL_DATASET=0` no se descarga nada y la base arranca
vacía, que es lo que hace la integración continua. Si la descarga falla, la
base también se queda vacía: nunca se rellena con datos de ejemplo, porque una
vez publicados serían indistinguibles de los declarados de verdad.

## Configuración

Copiar `.env.example` a `.env`. En local todo es opcional: la base es un
SQLite en el propio directorio y las cotizaciones salen de Yahoo Finance, que
no pide registro.

Antes de publicar el sitio hay dos variables que sí importan:

| Variable | Para qué |
| --- | --- |
| `DATABASE_URL` | Postgres de producción. Sin ella se usaría un SQLite que en serverless no existe. |
| `ADMIN_TOKEN` | Abre las rutas de administración. **Dejarla vacía en producción**, salvo que se vayan a usar: sin ella esas rutas responden 404. |

Ejecutar las pruebas:

```bash
python -m pytest -q
```

## Despliegue en Vercel

Vercel ejecuta funciones que nacen y mueren con cada petición: no hay disco
donde escribir ni proceso que sostenga el polling. Por eso allí la base es un
Postgres externo y la ingesta se lanza desde fuera.

1. **Crear la base.** Cualquier Postgres gestionado sirve (Neon, Vercel
   Postgres, Supabase). Copiar su cadena de conexión; si el proveedor ofrece
   una variante *pooled*, usar esa: cada invocación abre su propia conexión.

2. **Subir los datos** desde la máquina donde está la base local poblada:
   ```bash
   python -m scripts.migrate_to_postgres --target "postgresql://usuario:clave@host/basedatos"
   ```
   Copia personas, valores, operaciones, posiciones y cotizaciones conservando
   los identificadores, para que los enlaces `/politicians/278` sigan valiendo.
   Con `--replace` sobrescribe un destino que ya tuviera datos.

3. **Importar el repositorio en Vercel** y definir `DATABASE_URL`. Las demás
   variables tienen valor por defecto.

4. **Desplegar.** `vercel.json` manda todas las rutas a `api/index.py`, que
   sirve la aplicación FastAPI entera, estáticos incluidos.

### Mantener los datos vivos

Con el polling apagado en serverless, algo tiene que refrescar la base o el
sitio envejece solo. De eso se encarga `.github/workflows/data-refresh.yml`,
que cada seis horas ingiere las operaciones nuevas —del Congreso y de la SEC—
y refresca las cotizaciones contra la base de producción. Requiere dos secretos
en el repositorio de GitHub: `DATABASE_URL` y, si se usa Finnhub,
`FINNHUB_API_KEY`. El primer paso comprueba la conexión y, si falla, dice qué
revisar: el secreto tiene que ser la URL sola (`postgresql://…`).

Lanzado a mano (*Run workflow*), acepta la opción **Reparar fechas**, que
ejecuta `scripts.repair_dates` contra producción antes de la ingesta.

El refresco de precios importa más de lo que parece: en serverless las fichas
sirven las cotizaciones ya guardadas y no llaman al proveedor, porque Yahoo
devuelve 429 con frecuencia y sus reintentos esperan hasta medio minuto por
valor, mucho más de lo que dura una función. Sin ese refresco, el patrimonio se
muestra con precios cada vez más viejos —la ficha indica siempre de cuándo son.

Las mismas tareas se pueden lanzar a mano apuntando a producción:

```bash
DATABASE_URL="postgresql://..." python -m app.insiders   # nuevas operaciones
DATABASE_URL="postgresql://..." python -m app.prices     # refresca cotizaciones
```

## Seguridad

La web es de sólo lectura: no hay cuentas, ni sesiones, ni formularios que
escriban nada. Lo único que un visitante puede guardar es el idioma y el tema,
en su propio navegador.

- **Cabeceras**: política de seguridad de contenido con *nonce* por respuesta
  para los scripts en línea, `X-Content-Type-Options`, `Referrer-Policy`,
  `X-Frame-Options`, `Permissions-Policy` y HSTS donde hay TLS.
- **Rutas de administración** (`/api/poll-sources`, `/api/load-sample-filing`):
  escriben en la base o salen a la red, así que exigen la cabecera
  `X-Admin-Token`. Sin `ADMIN_TOKEN` configurado responden 404.

## API pública

Paginada, con `limit` (máximo 500) y `offset`:

```text
GET /api/trades?limit=100&offset=0
GET /api/politicians?limit=100&offset=0
GET /api/politicians/{id}?limit=100&offset=0
```

Cada respuesta trae `total`, `limit`, `offset` y `results`. La documentación
interactiva que genera FastAPI está en `/docs`.

Cada operación lleva las dos fechas del filing, que no son la misma cosa:

| Campo | Qué es |
| --- | --- |
| `reported_date` | Cuándo se hizo público el documento. Es la que ordena la web. |
| `transaction_date` | Cuándo se ejecutó la operación, según el propio documento. `null` si el filing no la trae o si es imposible. |

Los congresistas no declaran importes exactos sino tramos fijados por ley
(`$1,001 - $15,000`, `$15,001 - $50,000`…). En sus operaciones `amount` es el
punto medio del tramo —lo que permite sumar volúmenes— y `amount_range` trae
los límites `[mínimo, máximo]` (`máximo` es `null` en el tramo sin techo). En
las de la SEC, que sí declaran precio y número de títulos, `amount_range` es
`null` y `amount` es la cifra exacta.

Una fecha de operación es imposible cuando cae después de la publicación que la
declara: eso sólo puede ser un error de escritura en el documento original —lo
habitual, un año equivocado en enero— y no hay forma de saber cuál era la
buena. En ese caso la operación se guarda con su fecha de publicación, que sí
consta, y sin fecha de operación. Un filing fechado en el futuro se descarta
entero.

## Estado actual

- Operaciones del Congreso (House Stock Watcher) y de directivos (SEC Form 4).
- Fichas-resumen por persona, tendencias, filtros y perfiles individuales, en
  español e inglés.
- Biografías y retratos de Wikipedia/Wikimedia Commons, con su atribución.
- Patrimonio en acciones de los directivos, valorado a precio de mercado.
- Polling periódico de las fuentes, con deduplicación por operación.
- `robots.txt` y `sitemap.xml`.

## Tareas de datos

Se ejecutan a mano, no forman parte del arranque:

```bash
python -m app.profiles    # biografías y retratos
python -m app.insiders    # Form 4 de la SEC: operaciones y posiciones
python -m app.prices      # precarga las cotizaciones en caché
python -m app.backfill    # normaliza nombres y corrige cámara/estado
```

Sobre una base creada antes de que existiera `transaction_date`, todas las
operaciones guardan en `reported_date` la fecha en que se operó, no la de
publicación. El esquema se migra solo al arrancar, pero la fecha que falta hay
que volver a leerla de la fuente:

```bash
python -m scripts.repair_dates                  # Congreso + SEC (relee EDGAR, tarda)
python -m scripts.repair_dates --skip-insiders  # sólo el dataset del Congreso
```

Borra lo importado y lo reingiere con las dos fechas separadas. Conserva los
identificadores de las personas, así que los enlaces `/politicians/{id}` siguen
valiendo. Contra producción, con `DATABASE_URL` delante.

## Origen de los datos

- **Congreso**: declaraciones bajo la STOCK Act. Sólo tramos de importe, sin
  número de acciones, así que no permiten calcular patrimonio.
- **Directivos**: Formulario 4 de la SEC, que sí declara títulos poseídos.
- **Biografías y fotos**: Wikipedia y Wikimedia Commons (CC BY-SA, con
  atribución en cada ficha).
- **Cotizaciones**: Yahoo Finance por defecto, Finnhub si se configura
  `FINNHUB_API_KEY`. Yahoo no ofrece un endpoint público con condiciones de uso
  para esto, así que en producción lo recomendable es Finnhub.

## Latencia de los datos

La STOCK Act da a los congresistas hasta 45 días para declarar una operación, y
no existe ningún mecanismo legal de reporte en tiempo real. Ninguna plataforma
—ni esta ni las de pago— puede ver la operación antes de que se declare. Lo que
se puede reducir es el tiempo entre que la fuente oficial publica el documento y
que aparece aquí, y en eso consiste el polling.

Por eso la web ordena y mide por fecha de publicación, y enseña la de la
operación como un dato aparte: entre una y otra pueden pasar semanas, y
confundirlas haría creer que se sabe antes de lo que se puede saber.

## Licencia

Código bajo licencia MIT (ver [LICENSE](LICENSE)). Los datos no son del
proyecto: las declaraciones son documentos públicos del gobierno de Estados
Unidos y las biografías y retratos vienen de Wikimedia bajo CC BY-SA, con la
atribución que cada ficha incluye.
