"""Cadenas de interfaz en español e inglés.

El idioma se elige con `?lang=en` y se recuerda en una cookie.
"""
from __future__ import annotations

from typing import Any

DEFAULT_LANG = "es"
LANGS = ("es", "en")

TRANSLATIONS: dict[str, dict[str, Any]] = {
    "es": {
        "lang_label": "ES",
        "lang_switch": "English",
        "theme_light": "Modo claro",
        "theme_dark": "Modo noche",
        # Navegación
        "nav_trades": "Operaciones",
        "nav_trends": "Tendencias",
        "nav_people": "Perfiles",
        "nav_sources": "Fuentes oficiales",
        "nav_load_sample": "Cargar ejemplo",
        "nav_loading": "Cargando...",
        "nav_load_error": "No se pudo cargar el filing de prueba.",
        "nav_back_index": "Volver al índice",
        # Hero
        "hero_claim_1": "Ellos operan con información privilegiada.",
        "hero_claim_2": "¿Por qué tú no?",
        "hero_cta": "Ver la clasificación",
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
        "stat_last_trade": "Última operación",
        # Clasificación
        "rank_title": "Conoce las inversiones de los más poderosos",
        "rank_sub": "Clasificación por capital declarado dentro de la selección actual.",
        "rank_investor": "Inversor",
        "rank_capital": "Capital declarado",
        "rank_ops": "ops",
        # Operaciones
        "trades_title": "Operaciones recientes",
        "trades_sub": "Las últimas doce publicaciones que encajan con tu búsqueda.",
        "filter_search": "Buscar",
        "filter_search_ph": "Nombre, ticker o tipo",
        "filter_category": "Perfil",
        "cat_all": "Todos",
        "cat_congress": "Congreso",
        "cat_business": "Empresa",
        "badge_congress": "Congreso",
        "badge_business": "Empresa",
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
        # Políticos
        "people_title": "Políticos y directivos",
        "people_sub": "Congresistas y directivos de grandes empresas, ordenados por volumen declarado.",
        "people_active": "{n} con actividad",
        "people_empty": "No hay políticos que coincidan con esta búsqueda.",
        "people_more": "Mostrando los 24 con más actividad · {n} más disponibles vía",
        "people_more_link": "API",
        "people_ops": "ops",
        # Ficha
        "profile_back": "Todos los perfiles",
        "profile_follow": "Seguir",
        "profile_following": "Siguiendo",
        "profile_no_party": "Sin partido declarado",
        "profile_bio": (
            "Ha declarado <b>{trades} operaciones</b> sobre <b>{tickers} valores</b> distintos "
            "entre {first} y {last}, por un total de <b>{total}</b>. El <b>{ratio}%</b> de sus "
            "operaciones clasificadas son compras{favourite}."
        ),
        "profile_bio_fav": " y su valor más repetido es <b>{symbol}</b> ({ops} operaciones)",
        "profile_bio_empty": "Todavía no hay operaciones declaradas para este perfil.",
        "profile_top_sub": "Operaciones declaradas por ticker · top {n}",
        "history_title": "Últimas inversiones",
        "history_sub": "Ordenadas por fecha de publicación del filing, de más reciente a más antigua.",
        "history_type": "Tipo",
        "history_security": "Valor",
        "history_date": "Fecha",
        "history_amount": "Importe",
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
    },
    "en": {
        "lang_label": "EN",
        "lang_switch": "Español",
        "theme_light": "Light mode",
        "theme_dark": "Night mode",
        # Navigation
        "nav_trades": "Trades",
        "nav_trends": "Trends",
        "nav_people": "Profiles",
        "nav_sources": "Official sources",
        "nav_load_sample": "Load sample",
        "nav_loading": "Loading...",
        "nav_load_error": "The sample filing could not be loaded.",
        "nav_back_index": "Back to index",
        # Hero
        "hero_claim_1": "They trade on privileged information.",
        "hero_claim_2": "Why shouldn't you?",
        "hero_cta": "See the leaderboard",
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
        "stat_last_trade": "Latest trade",
        # Leaderboard
        "rank_title": "See what the most powerful are investing in",
        "rank_sub": "Ranked by declared capital within the current selection.",
        "rank_investor": "Investor",
        "rank_capital": "Declared capital",
        "rank_ops": "trades",
        # Trades
        "trades_title": "Recent trades",
        "trades_sub": "The last twelve filings matching your search.",
        "filter_search": "Search",
        "filter_search_ph": "Name, ticker or type",
        "filter_category": "Profile",
        "cat_all": "All",
        "cat_congress": "Congress",
        "cat_business": "Business",
        "badge_congress": "Congress",
        "badge_business": "Business",
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
        # Politicians
        "people_title": "Politicians & executives",
        "people_sub": "Members of Congress and corporate executives, sorted by declared volume.",
        "people_active": "{n} with activity",
        "people_empty": "No politicians match this search.",
        "people_more": "Showing the 24 most active · {n} more available through the",
        "people_more_link": "API",
        "people_ops": "trades",
        # Profile
        "profile_back": "All profiles",
        "profile_follow": "Follow",
        "profile_following": "Following",
        "profile_no_party": "No party declared",
        "profile_bio": (
            "Has declared <b>{trades} trades</b> across <b>{tickers} different securities</b> "
            "between {first} and {last}, totalling <b>{total}</b>. <b>{ratio}%</b> of their "
            "classified trades are buys{favourite}."
        ),
        "profile_bio_fav": " and their most repeated security is <b>{symbol}</b> ({ops} trades)",
        "profile_bio_empty": "No trades have been declared for this profile yet.",
        "profile_top_sub": "Declared trades per ticker · top {n}",
        "history_title": "Latest investments",
        "history_sub": "Sorted by filing publication date, most recent first.",
        "history_type": "Type",
        "history_security": "Security",
        "history_date": "Date",
        "history_amount": "Amount",
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
    },
}


def normalise_lang(value: str | None) -> str:
    return value if value in LANGS else DEFAULT_LANG


def get_translations(lang: str) -> dict[str, Any]:
    return TRANSLATIONS[normalise_lang(lang)]
