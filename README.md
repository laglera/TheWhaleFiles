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
Congreso. Para arrancar sin red —o en integración continua— basta con
`SEED_REAL_DATASET=0`, que siembra en su lugar cuatro registros de ejemplo.

## Configuración

Copiar `.env.example` a `.env`. En local todo es opcional: la base es un
SQLite en el propio directorio y las cotizaciones salen de Yahoo Finance, que
no pide registro.

Antes de publicar el sitio hay tres variables que sí importan:

| Variable | Para qué |
| --- | --- |
| `DATABASE_URL` | Postgres de producción. Sin ella se usaría un SQLite que en serverless no existe. |
| `LEGAL_ENTITY` y `LEGAL_CONTACT_EMAIL` | Quién opera el sitio y dónde escribirle. Salen en el aviso legal y en la política de privacidad. Sin rellenar, esas páginas dicen que falta configurarlo. |
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

3. **Importar el repositorio en Vercel** y definir `DATABASE_URL`,
   `LEGAL_ENTITY` y `LEGAL_CONTACT_EMAIL`. Las demás tienen valor por defecto.

4. **Desplegar.** `vercel.json` manda todas las rutas a `api/index.py`, que
   sirve la aplicación FastAPI entera, estáticos incluidos.

### Mantener los datos vivos

Con el polling apagado en serverless, algo tiene que refrescar la base o el
sitio envejece solo. De eso se encarga `.github/workflows/data-refresh.yml`,
que cada seis horas ingiere las operaciones nuevas y refresca las cotizaciones
contra la base de producción. Requiere dos secretos en el repositorio de
GitHub: `DATABASE_URL` y, si se usa Finnhub, `FINNHUB_API_KEY`.

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

## Cuentas

Registro en `/signup` y entrada en `/login`, con correo y contraseña. Una cuenta
sirve para seguir perfiles: el botón de la ficha guarda el seguimiento y
`/account` reúne a quién sigues, sus últimas operaciones y el botón de baja.

No hace falta contratar nada para esto. Los usuarios viven en la misma base que
el resto —`users`, `sessions`, `follows` y `login_attempts`, creadas solas en el
primer arranque— y no hay ninguna variable de entorno nueva que configurar.

La sesión es un token aleatorio: el navegador lo guarda en una cookie y la tabla
`sessions` sólo conserva su hash. En serverless no hay proceso vivo donde
sostener sesiones en memoria, y guardarlas en la base tiene además la ventaja de
que salir las revoca de verdad, cosa que un token autofirmado no permite.

Borrar la cuenta elimina el correo, la contraseña y los seguimientos sin dejar
copia. Queda fuera por ahora la verificación del correo y recuperar la
contraseña.

## Seguridad

- **Contraseñas** con bcrypt. Nunca se guarda la contraseña en claro.
- **CSRF** con testigo por sesión en todos los formularios autenticados, sobre
  una cookie `SameSite=Lax`.
- **Límite de intentos** por dirección IP: diez entradas fallidas cada cuarto de
  hora y cinco altas por hora. Se cuenta en la tabla `login_attempts`, que se
  purga sola a las 24 horas, porque en serverless no hay memoria compartida
  entre invocaciones donde llevar la cuenta.
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

## Estado actual

- Cuentas de usuario, seguimiento de perfiles y baja de la cuenta.
- Operaciones del Congreso (House Stock Watcher) y de directivos (SEC Form 4).
- Ranking, tendencias, filtros y fichas individuales, en español e inglés.
- Biografías y retratos de Wikipedia/Wikimedia Commons, con su atribución.
- Patrimonio en acciones de los directivos, valorado a precio de mercado.
- Polling periódico de las fuentes, con deduplicación por operación.
- Páginas legales, `robots.txt` y `sitemap.xml`.

## Tareas de datos

Se ejecutan a mano, no forman parte del arranque:

```bash
python -m app.profiles    # biografías y retratos
python -m app.insiders    # Form 4 de la SEC: operaciones y posiciones
python -m app.prices      # precarga las cotizaciones en caché
python -m app.backfill    # normaliza nombres y corrige cámara/estado
```

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

## Licencia

Código bajo licencia MIT (ver [LICENSE](LICENSE)). Los datos no son del
proyecto: las declaraciones son documentos públicos del gobierno de Estados
Unidos y las biografías y retratos vienen de Wikimedia bajo CC BY-SA, con la
atribución que cada ficha incluye.
