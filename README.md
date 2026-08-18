# TheWhaleFiles

Proyecto MVP para seguir y analizar carteras declaradas por políticos estadounidenses.

## Objetivo

Mostrar operaciones recientes y el historial de un político a partir de declaraciones públicas y datos estructurados.

## Stack

- FastAPI
- SQLAlchemy
- SQLite en local, Postgres en el despliegue
- Jinja2 + HTML/CSS para la interfaz básica

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

## Configuración

Copiar `.env.example` a `.env`. En local todo es opcional: la base es un
SQLite en el propio directorio y las cotizaciones salen de Yahoo Finance, que
no pide registro. Configurar `FINNHUB_API_KEY` cambia el proveedor a Finnhub.

## Despliegue en Vercel

Vercel ejecuta funciones que nacen y mueren con cada petición: no hay disco
donde escribir ni proceso que sostenga el polling. Por eso allí la base es un
Postgres externo y los datos se preparan desde local.

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

3. **Importar el repositorio en Vercel** y definir una sola variable de
   entorno: `DATABASE_URL`, con esa misma cadena. Las demás del `.env.example`
   son opcionales y tienen valor por defecto en el código.

4. **Desplegar.** `vercel.json` manda todas las rutas a `api/index.py`, que
   sirve la aplicación FastAPI entera, estáticos incluidos.

Las tareas de datos siguen ejecutándose a mano y fuera de Vercel, apuntando a
la base de producción:

```bash
DATABASE_URL="postgresql://..." python -m app.insiders   # nuevas operaciones
DATABASE_URL="postgresql://..." python -m app.prices     # refresca cotizaciones
```

La segunda importa más de lo que parece: en serverless las fichas sirven las
cotizaciones ya guardadas y no llaman al proveedor: Yahoo devuelve 429 con
frecuencia y sus reintentos esperan hasta medio minuto por valor, mucho más de
lo que dura una función. Sin este refresco periódico, el patrimonio se muestra
con precios cada vez más viejos —la ficha indica siempre de cuándo son.

## Cuentas

Registro en `/signup` y entrada en `/login`, con correo y contraseña. Una cuenta
sirve para seguir perfiles: el botón de la ficha guarda el seguimiento y
`/account` reúne a quién sigues y sus últimas operaciones.

No hace falta contratar nada para esto. Los usuarios viven en la misma base que
el resto —`users`, `sessions` y `follows`, creadas solas en el primer arranque—
y no hay ninguna variable de entorno nueva que configurar.

La sesión es un token aleatorio: el navegador lo guarda en una cookie y la tabla
`sessions` sólo conserva su hash. En serverless no hay proceso vivo donde
sostener sesiones en memoria, y guardarlas en la base tiene además la ventaja de
que salir las revoca de verdad, cosa que un token autofirmado no permite.

Queda fuera por ahora la verificación del correo, recuperar la contraseña y
limitar los intentos de entrada.

## Estado actual

- Cuentas de usuario y seguimiento de perfiles.
- Operaciones del Congreso (House Stock Watcher) y de directivos (SEC Form 4).
- Ranking, tendencias, filtros y fichas individuales, en español e inglés.
- Biografías y retratos de Wikipedia/Wikimedia Commons, con su atribución.
- Patrimonio en acciones de los directivos, valorado a precio de mercado.
- Polling periódico de las fuentes, con deduplicación por operación.

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
