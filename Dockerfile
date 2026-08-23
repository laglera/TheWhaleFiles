FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY tests ./tests

EXPOSE 8000

# 0.0.0.0 y no la interfaz local: dentro del contenedor, escuchar sólo en
# localhost deja la aplicación inalcanzable desde fuera.
ENV HOST=0.0.0.0 \
    PORT=8000

CMD ["python", "-m", "app"]
