# TheWhaleFiles

Proyecto MVP para seguir y analizar carteras declaradas por políticos estadounidenses.

## Objetivo

Mostrar operaciones recientes y el historial de un político a partir de declaraciones públicas y datos estructurados.

## Stack

- FastAPI
- SQLAlchemy
- SQLite para el MVP
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

Copiar `.env.example` a `.env`. Todo es opcional salvo la clave de cotizaciones,
que hace falta para valorar las posiciones de los directivos.

## Estado actual

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
python -m app.backfill    # normaliza nombres y corrige cámara/estado
```

## Origen de los datos

- **Congreso**: declaraciones bajo la STOCK Act. Sólo tramos de importe, sin
  número de acciones, así que no permiten calcular patrimonio.
- **Directivos**: Formulario 4 de la SEC, que sí declara títulos poseídos.
- **Biografías y fotos**: Wikipedia y Wikimedia Commons (CC BY-SA, con
  atribución en cada ficha).
