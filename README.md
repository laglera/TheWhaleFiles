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

## Estado actual

La base del MVP ya está creada con:

- estructura de datos para políticos, operaciones y tickers,
- API mínima con listados,
- página de inicio con muestra de trades recientes,
- base de datos SQLite con datos de ejemplo.

## Nota

La ejecución completa requiere acceso a PyPI para instalar las dependencias. En este entorno actual hubo un bloqueo de red al instalar paquetes externos, pero la estructura del proyecto y la lógica base ya están preparadas para seguir desarrollando.
