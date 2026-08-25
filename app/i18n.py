"""Cadenas de interfaz en español e inglés.

El idioma se elige con `?lang=en` y se recuerda en una cookie.
"""
from __future__ import annotations

from typing import Any

DEFAULT_LANG = "es"
LANGS = ("es", "en")

TRANSLATIONS: dict[str, dict[str, Any]] = {
    "es": {
        "lang_switch": "English",
        "theme_dark": "Modo noche",
        # Navegación
        "nav_trades": "Operaciones",
        "nav_trends": "Tendencias",
        "nav_people": "Perfiles",
        "nav_back_index": "Volver al índice",
        "nav_ranking": "Ver perfiles",
        # Hero
        "hero_claim_1": "Legislan sobre unos mercados en los que también invierten.",
        "hero_claim_2": "Mira lo que declaran.",
        "hero_cta": "Ver quién invierte en qué",
        # Métricas
        "stat_trades": "Operaciones",
        "stat_trades_sub": "Registros parseados de filings oficiales",
        "stat_capital": "Capital declarado",
        "stat_capital_sub": "Suma de los importes reportados",
        "stat_people": "Perfiles",
        "stat_people_sub": "Con al menos una operación declarada",
        "stat_last": "Última publicación",
        "stat_last_sub": "Fecha del filing más reciente",
        "stat_ops_declared": "Declaradas en filings oficiales",
        "stat_split": "Compras / ventas",
        "stat_split_sub": "Reparto de la actividad declarada",
        "stat_last_trade": "Última publicación",
        # Fichas-resumen
        "digest_title": "En qué invierte cada uno",
        "digest_sub": (
            "Una ficha por persona, ordenadas por el capital que declaran. Cada una "
            "resume dónde está concentrado ese dinero, si está comprando o vendiendo "
            "y cuándo fue la última vez que lo declaró."
        ),
        "digest_capital": "Capital",
        "digest_ops": "Ops",
        "digest_bias": "Sesgo",
        "digest_buying": "compras",
        "digest_selling": "ventas",
        "digest_positions": "Dónde está el dinero",
        "digest_more_positions": "y {n} valores más",
        "digest_last": "Última",
        # Operaciones
        "trades_title": "Operaciones recientes",
        "trades_sub": "Las últimas doce operaciones publicadas dentro de la selección actual.",
        "filter_search": "Buscar",
        "filter_search_ph": "Nombre, ticker o tipo",
        "filter_category": "Perfil",
        "cat_all": "Todos",
        "cat_congress": "Congreso",
        "cat_business": "Empresa",
        "filter_chamber": "Cámara o cargo",
        "filter_party": "Partido",
        "filter_all_f": "Todas",
        "filter_all_m": "Todos",
        "filter_submit": "Filtrar",
        "filter_clear": "Limpiar",
        "trade_amount": "Importe",
        "trades_empty": "No hay operaciones para estos filtros. Prueba a limpiar la búsqueda.",
        # Tendencias
        "trends_title": "Tendencias",
        "trends_sub": "Dónde se concentra la actividad declarada dentro de la selección actual.",
        "trends_top_title": "Valores más operados",
        "trends_top_sub": "Número de operaciones declaradas por ticker · top {n}",
        "trends_split_title": "Compras frente a ventas",
        "trends_split_sub": "Reparto de las operaciones filtradas",
        "trends_split_sub_profile": "Reparto sobre {n} operaciones",
        "side_buy": "Compra",
        "side_sell": "Venta",
        "side_other": "Sin clasificar",
        "side_buys": "Compras",
        "side_sells": "Ventas",
        "ops_short": "ops",
        "people_empty": "No hay políticos que coincidan con esta búsqueda.",
        "people_more": "Mostrando los 24 que más capital declaran · {n} más disponibles vía",
        "people_more_link": "API",
        # Ficha
        "profile_back": "Todos los perfiles",
        "profile_bio_empty": "Todavía no hay una biografía disponible para esta persona.",
        "profile_bio_more": "Leer más",
        "profile_bio_less": "Leer menos",
        "profile_bio_source": "Biografía de {source}, bajo licencia CC BY-SA.",
        "profile_bio_other_lang": "Biografía disponible sólo en inglés.",
        "profile_photo_credit": "Foto: {author} · {license}",
        "profile_top_sub": "Capital declarado por valor · top {n}",
        # Patrimonio (sólo perfiles empresariales)
        "wealth_title": "Patrimonio en acciones",
        "wealth_sub": (
            "Títulos que declara poseer en su Formulario 4 más reciente, valorados "
            "a precio de mercado."
        ),
        "wealth_total": "Valor de mercado",
        "wealth_positions": "Posiciones",
        "wealth_shares": "Acciones",
        "wealth_price": "Precio",
        "wealth_value": "Valor",
        "wealth_as_of": "Declarado",
        "wealth_updated": "Cotizaciones de {source}, actualizadas el {when}",
        "wealth_no_price": "Sin cotización",
        "wealth_missing": "{n} sin cotización, fuera del total.",
        "wealth_missing_short": "{n} sin cotizar",
        "wealth_unavailable": "No disponible",
        "wealth_disclaimer": (
            "Sólo cuenta las acciones de empresas donde es directivo o gran accionista "
            "y está obligado a declarar ante la SEC. No es su patrimonio total."
        ),
        "wealth_congress_note": (
            "Los congresistas declaran sus operaciones en tramos de importe, sin número "
            "de acciones ni posiciones, así que no es posible calcular su patrimonio."
        ),
        "history_title": "Últimas inversiones",
        "history_sub": "Ordenadas por fecha de publicación del filing, de más reciente a más antigua.",
        "history_type": "Tipo",
        "history_security": "Valor",
        "history_date": "Publicación",
        "history_amount": "Importe",
        # Las dos fechas de un filing son cosas distintas: cuándo se operó y
        # cuándo se pudo saber. La web las nombra por separado para que nadie
        # lea una como la otra.
        "trade_filed": "Publicado",
        "trade_executed": "Operación",
        "trade_date_missing": "sin fecha en el filing",
        "history_more": "Mostrando las 60 más recientes · {n} operaciones más disponibles vía",
        "history_empty": "Este político aún no tiene operaciones registradas.",
        # Footer
        "footer_about": (
            "Datos públicos extraídos de las declaraciones de transparencia financiera "
            "(STOCK Act). Mostramos lo declarado, sin interpretar intenciones."
        ),
        "footer_sources": "Fuentes",
        "footer_senate": "Senado — eFD",
        "footer_house": "Cámara — House Clerk",
        "footer_data": "Datos",
        "footer_trades_json": "Operaciones (JSON)",
        "footer_people_json": "Políticos (JSON)",
        "footer_health": "Estado del servicio",
        "footer_note": (
            "Los PTR se publican hasta 45 días después de la operación: esta plataforma reduce "
            "la latencia entre la publicación del filing y su lectura, no la del mercado."
        ),
        "meta_description": (
            "Seguimiento de las operaciones bursátiles declaradas por políticos y figuras "
            "públicas de EEUU."
        ),
        # Errores
        "error_404": "Esta página no existe.",
        "error_generic": "Algo ha fallado por nuestro lado.",
        "error_home": "Volver a la portada",
    },
    "en": {
        "lang_switch": "Español",
        "theme_dark": "Night mode",
        # Navigation
        "nav_trades": "Trades",
        "nav_trends": "Trends",
        "nav_people": "Profiles",
        "nav_back_index": "Back to index",
        "nav_ranking": "See profiles",
        # Hero
        "hero_claim_1": "They legislate on markets they also invest in.",
        "hero_claim_2": "See what they declare.",
        "hero_cta": "See who invests in what",
        # Stats
        "stat_trades": "Trades",
        "stat_trades_sub": "Records parsed from official filings",
        "stat_capital": "Declared capital",
        "stat_capital_sub": "Sum of all reported amounts",
        "stat_people": "Profiles",
        "stat_people_sub": "With at least one declared trade",
        "stat_last": "Latest filing",
        "stat_last_sub": "Date of the most recent filing",
        "stat_ops_declared": "Declared in official filings",
        "stat_split": "Buys / sells",
        "stat_split_sub": "Split of the declared activity",
        "stat_last_trade": "Latest filing",
        # Digest cards
        "digest_title": "What each of them invests in",
        "digest_sub": (
            "One card per person, sorted by the capital they declare. Each one sums up "
            "where that money is concentrated, whether they are buying or selling, and "
            "when they last declared it."
        ),
        "digest_capital": "Capital",
        "digest_ops": "Trades",
        "digest_bias": "Bias",
        "digest_buying": "buys",
        "digest_selling": "sells",
        "digest_positions": "Where the money is",
        "digest_more_positions": "and {n} more securities",
        "digest_last": "Latest",
        # Trades
        "trades_title": "Recent trades",
        "trades_sub": "The last twelve trades published within the current selection.",
        "filter_search": "Search",
        "filter_search_ph": "Name, ticker or type",
        "filter_category": "Profile",
        "cat_all": "All",
        "cat_congress": "Congress",
        "cat_business": "Business",
        "filter_chamber": "Chamber or role",
        "filter_party": "Party",
        "filter_all_f": "All",
        "filter_all_m": "All",
        "filter_submit": "Filter",
        "filter_clear": "Clear",
        "trade_amount": "Amount",
        "trades_empty": "No trades match these filters. Try clearing the search.",
        # Trends
        "trends_title": "Trends",
        "trends_sub": "Where the declared activity concentrates within the current selection.",
        "trends_top_title": "Most traded securities",
        "trends_top_sub": "Declared trades per ticker · top {n}",
        "trends_split_title": "Buys versus sells",
        "trends_split_sub": "Split of the filtered trades",
        "trends_split_sub_profile": "Split across {n} trades",
        "side_buy": "Buy",
        "side_sell": "Sell",
        "side_other": "Unclassified",
        "side_buys": "Buys",
        "side_sells": "Sells",
        "ops_short": "trades",
        "people_empty": "No politicians match this search.",
        "people_more": "Showing the 24 with the most declared capital · {n} more available through the",
        "people_more_link": "API",
        # Profile
        "profile_back": "All profiles",
        "profile_bio_empty": "No biography is available for this person yet.",
        "profile_bio_more": "Read more",
        "profile_bio_less": "Read less",
        "profile_bio_source": "Biography from {source}, licensed CC BY-SA.",
        "profile_bio_other_lang": "Biography available in Spanish only.",
        "profile_photo_credit": "Photo: {author} · {license}",
        "profile_top_sub": "Declared capital per security · top {n}",
        # Wealth (business profiles only)
        "wealth_title": "Equity holdings",
        "wealth_sub": (
            "Shares declared in their most recent Form 4, valued at market price."
        ),
        "wealth_total": "Market value",
        "wealth_positions": "Positions",
        "wealth_shares": "Shares",
        "wealth_price": "Price",
        "wealth_value": "Value",
        "wealth_as_of": "Declared",
        "wealth_updated": "Quotes from {source}, updated {when}",
        "wealth_no_price": "No quote",
        "wealth_missing": "{n} without a quote, excluded from the total.",
        "wealth_missing_short": "{n} unpriced",
        "wealth_unavailable": "Unavailable",
        "wealth_disclaimer": (
            "Only covers shares in companies where they are an officer or major "
            "shareholder and must report to the SEC. This is not their total net worth."
        ),
        "wealth_congress_note": (
            "Members of Congress declare trades in amount brackets, without share counts "
            "or positions, so their holdings cannot be calculated."
        ),
        "history_title": "Latest investments",
        "history_sub": "Sorted by filing publication date, most recent first.",
        "history_type": "Type",
        "history_security": "Security",
        "history_date": "Filed",
        "history_amount": "Amount",
        "trade_filed": "Filed",
        "trade_executed": "Trade date",
        "trade_date_missing": "not stated in the filing",
        "history_more": "Showing the 60 most recent · {n} more trades available through the",
        "history_empty": "This politician has no recorded trades yet.",
        # Footer
        "footer_about": (
            "Public data extracted from financial transparency disclosures (STOCK Act). "
            "We show what was declared, without interpreting intent."
        ),
        "footer_sources": "Sources",
        "footer_senate": "Senate — eFD",
        "footer_house": "House Clerk",
        "footer_data": "Data",
        "footer_trades_json": "Trades (JSON)",
        "footer_people_json": "Politicians (JSON)",
        "footer_health": "Service status",
        "footer_note": (
            "PTRs are published up to 45 days after the trade: this platform reduces the lag "
            "between a filing going public and you reading it, not the market's."
        ),
        "meta_description": (
            "Tracking the stock trades declared by US politicians and public figures."
        ),
        # Errors
        "error_404": "This page does not exist.",
        "error_generic": "Something broke on our side.",
        "error_home": "Back to the home page",
    },
}


def normalise_lang(value: str | None) -> str:
    return value if value in LANGS else DEFAULT_LANG


def get_translations(lang: str) -> dict[str, Any]:
    return TRANSLATIONS[normalise_lang(lang)]
