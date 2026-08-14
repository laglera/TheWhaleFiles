# TheWhaleFiles

## Descripción

Plataforma web para trackear y analizar las carteras de inversión declaradas por políticos estadounidenses (Congreso, Senado) y otras figuras públicas, a partir de sus declaraciones oficiales de transparencia financiera (financial disclosures).

Referencias de producto: Capitol Trades, Quiver Quantitative (Congress Trading).

## Objetivo del proyecto

Plataforma para rastrear y analizar las carteras de inversión declaradas por políticos estadounidenses y otras figuras públicas.

## Sobre la latencia de los datos (importante)

La STOCK Act obliga a los congresistas de EEUU a presentar su Periodic Transaction Report (PTR) en un plazo de 30 días desde que reciben notificación de la operación, y nunca más tarde de 45 días desde la transacción. **No existe ningún mecanismo legal de reporte en tiempo real**, y esto aplica a cualquier fuente (web oficial, Quiver, Capitol Trades, cuentas de X, etc.) — nadie tiene acceso a la operación real antes de que se declare.

Lo que hacen plataformas y cuentas que parecen "al momento" (Unusual Whales, Quiver, etc.) es ser muy rápidas parseando la declaración justo cuando se publica, no cuando ocurre la operación real:

1. El político compra/vende → Día 0 (esto nunca es público hasta el paso 3)
2. Presenta el PTR → entre el día 1 y el día 45, a su elección
3. El PTR se publica en la web oficial (Senado/House Clerk)
4. Bot/scraper detecta el filing recién publicado y notifica → esto es lo que parece "en tiempo real"

**Objetivo realista para este proyecto**: minimizar la latencia entre la publicación del filing (paso 3) y la notificación al usuario (paso 4), mediante polling frecuente de las fuentes oficiales. No es posible ni para este proyecto ni para ningún competidor acceder a la operación antes de que se declare.

## Fuentes de datos

- **Senado (EEUU)**: eFD system — efdsearch.senate.gov
- **Cámara de Representantes (EEUU)**: House Clerk — disclosures-clerk.house.gov
- **Alternativa/apoyo**: API de Quiver Quantitative (api.quiverquant.com) para prototipar rápido antes de tener el scraper propio completo

Los datos oficiales suelen venir en PDF/HTML poco estructurado, por lo que hace falta scraping + parsing. La estrategia de polling frecuente sobre estas fuentes es clave para minimizar la latencia descrita arriba.

## Stack técnico propuesto

- **Backend**: FastAPI + PostgreSQL
- **Scraper/ETL**: Python, con scheduler periódico (APScheduler o cron) para ingestar nuevas declaraciones
- **Frontend**: por decidir (sin Streamlit)
- **Despliegue**: web (no app nativa), pensado para desplegar gratis en Vercel/Render y compartir como link en el portfolio

## Alcance del MVP

- [ ] Scraper/parser de declaraciones (empezar por una fuente: Senado o House Clerk)
- [ ] Modelo de datos: políticos, transacciones, tickers
- [ ] Almacenamiento en PostgreSQL
- [ ] API con FastAPI para exponer: trades recientes, trades por político, trades por ticker
- [ ] Frontend mínimo mostrando listado de trades y ficha de político con su histórico

## Ideas de extensión (post-MVP)

- Análisis simple de patrones (ej. correlación entre comité del político y sector de la operación)
- Leaderboard de rendimiento de carteras por político
- Integración con bot de Twitter/X existente para publicar alertas de nuevas operaciones relevantes

## Naming

- Nombre elegido: **TheWhaleFiles**
- Descripción para el repo de GitHub:
  > Rastrea y analiza las carteras de inversión declaradas por políticos y figuras públicas de EEUU, extraídas de las declaraciones oficiales de transparencia.

## Notas legales/éticas

Los datos son públicos (STOCK Act). Evitar enmarcar el análisis como acusaciones directas (ej. "esto es insider trading"); limitarse a mostrar los datos declarados y análisis objetivo.
