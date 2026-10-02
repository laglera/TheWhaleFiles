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
        "theme_light": "Modo día",
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
        "hero_cta_alt": "Últimas operaciones",
        "hero_badge": "Declaraciones oficiales de la Cámara y la SEC",
        "hero_lede": (
            "Cada compra y cada venta que un congresista o un alto directivo está "
            "obligado a declarar, reunida en un mismo sitio y con el nombre de "
            "quien la firma."
        ),
        "hero_feed_title": "Recién declarado",
        "hero_feed_empty": "Aún no hay operaciones cargadas.",
        "hero_feed_all": "Ver las últimas operaciones",
        "hero_sources": "Fuentes: House Clerk (STOCK Act) · SEC EDGAR (Formulario 4)",
        # Métricas
        "stat_trades": "Operaciones",
        "stat_capital": "Volumen declarado",
        "stat_capital_sub": "Compras más ventas, sin concesiones ni donaciones",
        "stat_last_sub": "Fecha del filing más reciente",
        "stat_range": "Por tramos: entre {min} y {max}",
        "stat_range_open": "Por tramos: más de {min}",
        "stat_lag": "Declara de media {days} días después de operar",
        "stat_late": "{n} fuera del plazo de 45 días",
        "trade_lag": "declarada {days} días después",
        # Los mismos números que antes ocupaban el hero, ahora en una línea de
        # contexto encima de las fichas.
        "facts_people": "perfiles",
        "facts_trades": "operaciones",
        "facts_capital": "en compras y ventas",
        "facts_last": "último filing",
        "stat_ops_declared": "Declaradas en filings oficiales",
        "stat_split": "Compras / ventas",
        "stat_split_sub": "Reparto de la actividad declarada",
        "stat_last_trade": "Última publicación",
        # Fichas-resumen
        "digest_title": "Qué compra y vende cada uno",
        "digest_sub": (
            "Una ficha por persona, ordenadas por el volumen que declaran en compras y "
            "ventas. Cada una resume en qué valores lo concentra, si está comprando o "
            "vendiendo y cuál fue su última operación."
        ),
        "digest_capital": "Volumen",
        "digest_ops": "Ops",
        "digest_bias": "Sesgo",
        "digest_bias_hint": "Según el número de compras y de ventas declaradas",
        "digest_buying": "compras",
        "digest_selling": "ventas",
        "digest_positions": "Dónde concentra su volumen",
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
        "trends_top_sub": "Compras y ventas declaradas por ticker · top {n}",
        "trends_split_title": "Compras frente a ventas",
        "trends_split_sub": "Reparto de las operaciones filtradas",
        "trends_split_sub_profile": "Reparto sobre {n} operaciones",
        "side_buy": "Compra",
        "side_sell": "Venta",
        "side_other": "Otros tipos",
        "kind_exchange": "Canje",
        "kind_grant": "Concesión",
        "kind_option": "Ejercicio de opciones",
        "kind_tax": "Retención fiscal",
        "kind_gift": "Donación",
        "kind_conversion": "Conversión",
        "kind_disposition": "Transmisión",
        "kind_other": "Otra",
        "side_buys": "Compras",
        "side_sells": "Ventas",
        "ops_short": "ops",
        "people_empty": "No hay políticos que coincidan con esta búsqueda.",
        "people_more": "Mostrando los 24 con más volumen declarado · {n} más disponibles vía",
        "people_more_link": "API",
        # Ficha
        "profile_back": "Todos los perfiles",
        "profile_bio_empty": "Todavía no hay una biografía disponible para esta persona.",
        "profile_bio_more": "Leer más",
        "profile_bio_less": "Leer menos",
        "profile_bio_source": "Biografía de {source}, bajo licencia CC BY-SA.",
        "profile_bio_other_lang": "Biografía disponible sólo en inglés.",
        "profile_photo_credit": "Foto: {author} · {license}",
        "profile_top_sub": "Volumen de compras y ventas por valor · top {n}",
        "profile_dormant": (
            "Sin Formularios 4 desde el {date}: puede haber dejado el cargo, y sus cifras "
            "son las de entonces."
        ),
        # Patrimonio (sólo perfiles empresariales)
        "wealth_title": "Acciones declaradas",
        "wealth_sub": (
            "Títulos que declara poseer —a su nombre o a través de trusts y sociedades— "
            "en sus Formularios 4 más recientes, valorados a precio de mercado."
        ),
        "wealth_total": "Valor de mercado",
        "wealth_positions": "Posiciones",
        "wealth_shares": "Acciones",
        "wealth_price": "Precio",
        "wealth_value": "Valor",
        "wealth_as_of": "Declarado",
        "wealth_updated": "Cotizaciones de {source}; la más antigua, del {when}",
        "wealth_stale": (
            "Atención: hay cotizaciones de hace {hours} horas. El refresco automático "
            "no ha podido actualizarlas y el valor puede no ser el del mercado."
        ),
        "wealth_no_fx": "Sin tipo de cambio",
        "wealth_converted": (
            "{n} posiciones cotizan en otra divisa y se convierten a {currency} al tipo "
            "de cambio del día."
        ),
        "wealth_no_price": "Sin cotización",
        "wealth_missing": "{n} sin cotización, fuera del total.",
        "wealth_missing_short": "{n} sin cotizar",
        "wealth_unavailable": "No disponible",
        "wealth_disclaimer": (
            "No es su patrimonio total: sólo cuenta acciones de empresas donde está "
            "obligado a declarar ante la SEC. Las opciones, warrants y convertibles van "
            "aparte. La propiedad indirecta —trusts, sociedades, fundaciones— se suma "
            "porque el Form 4 la declara como suya, pero puede ser control y no inversión "
            "propia: cada fila dice cuánta es."
        ),
        "wealth_indirect": "{n} indirectas",
        "wealth_split": "declaradas {declared}, ajustadas por split ×{factor}",
        "wealth_dividends": (
            "Desde la fecha de cada saldo han repartido unos {amount} en dividendos, que no "
            "se suman al total: no consta si se reinvirtieron."
        ),
        "derivatives_title": "Opciones y convertibles",
        "derivatives_sub": (
            "Derechos sobre acciones que declara en la tabla II de sus Formularios 4: "
            "opciones, warrants, unidades restringidas y acciones convertibles."
        ),
        "derivatives_total": "Valor intrínseco",
        "derivatives_security": "Derecho",
        "derivatives_underlying": "Acciones",
        "derivatives_strike": "Ejercicio",
        "derivatives_expiration": "Vence",
        "derivatives_value": "Intrínseco",
        "derivatives_no_strike": "Sin coste",
        "derivatives_out_of_money": "Fuera de dinero",
        "derivatives_disclaimer": (
            "Valor intrínseco: lo que daría ejercer hoy (precio menos precio de ejercicio, "
            "por acciones), sin el valor temporal que les da el mercado ni impuestos. No se "
            "suma al valor de las acciones: ejercer cuesta dinero y muchas aún no se pueden "
            "ejercer. Las vencidas no aparecen."
        ),
        "wealth_congress_note": (
            "Los congresistas declaran sus operaciones en tramos de importe, sin número "
            "de acciones ni posiciones, así que no es posible calcular su patrimonio. "
            "Cada importe es el tramo declarado; el volumen suma el punto medio de cada uno."
        ),
        # Rentabilidad de copiar
        "perf_title": "¿Y si le hubieras copiado?",
        "perf_sub": (
            "Una cartera que compra cada valor al cierre de la sesión siguiente a la "
            "publicación de su compra y lo vende tras su venta publicada o a las {hold} "
            "sesiones, a pesos iguales, con {cost} puntos básicos de coste por operación. "
            "Comparada con {benchmark} en las mismas sesiones."
        ),
        "perf_total": "Rentabilidad total",
        "perf_vs_benchmark": "{benchmark} en el mismo periodo: {value}",
        "perf_alpha": "Alfa anual",
        "perf_alpha_sub": "Frente al índice, ajustada por beta ({beta})",
        "perf_sharpe_sub": "Rentabilidad por unidad de riesgo; tipo sin riesgo {rf}",
        "perf_drawdown": "Peor caída",
        "perf_drawdown_sub": "{benchmark}: {value}",
        "perf_cagr": "Rentabilidad anualizada",
        "perf_volatility": "Volatilidad anual",
        "perf_correlation": "Correlación con el índice",
        "perf_tracking": "Tracking error",
        "perf_ir": "Information ratio",
        "perf_win_rate": "Operaciones que baten al índice",
        "perf_avg_win_loss": "Exceso medio al ganar / al perder",
        "perf_payoff": "Ratio de pago",
        "perf_ic": "Coeficiente de información (21 sesiones)",
        "perf_sample": "Muestra",
        "perf_sample_value": "{trades} operaciones copiadas, {sessions} sesiones ({start} a {end})",
        "perf_unavailable": (
            "No hay datos suficientes para medirlo: {signals} compras y ventas en el "
            "periodo, {priced} con histórico de precios y {trades} operaciones copiables. "
            "Hacen falta al menos cinco y tres meses de sesiones."
        ),
        "perf_disclaimer": (
            "Simulación retrospectiva con datos públicos, no una recomendación. Rentabilidad "
            "total con dividendos, antes de impuestos. Con pocas operaciones las métricas "
            "son muy inestables, y rentabilidades pasadas no garantizan las futuras."
        ),
        "perf_computed": "Calculado el {when}",
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
        # Aviso permanente, encima de la navegación en todas las páginas.
        "disclaimer_bar_lead": "No es asesoramiento financiero.",
        "disclaimer_bar_body": (
            "Datos declarados con hasta 45 días de retraso, que pueden estar "
            "incompletos o contener errores de la fuente. Compruébalos en la fuente "
            "oficial y con un profesional antes de invertir."
        ),
        "disclaimer_bar_link": "Aviso legal",
        "footer_legal": "Legal",
        "footer_disclaimer": "Aviso legal",
        "footer_terms": "Términos de uso",
        "footer_privacy": "Privacidad",
        "legal_title": "Aviso legal, términos y privacidad",
        # Footer
        "footer_about": (
            "Datos públicos extraídos de las declaraciones de la Cámara de Representantes "
            "(STOCK Act) y de los Formularios 4 de la SEC. Mostramos lo declarado, sin "
            "interpretar intenciones."
        ),
        "footer_sources": "Fuentes",
        "footer_sec": "SEC — EDGAR",
        "footer_house": "Cámara — House Clerk",
        "footer_data": "Datos",
        "footer_trades_json": "Operaciones (JSON)",
        "footer_people_json": "Políticos (JSON)",
        "footer_trades_csv": "Operaciones (CSV)",
        "footer_feed": "Avisos de nuevas operaciones (Atom)",
        "footer_health": "Estado del servicio",
        "footer_note": (
            "Los PTR se publican hasta 45 días después de la operación: esta plataforma reduce "
            "la latencia entre la publicación del filing y su lectura, no la del mercado."
        ),
        "meta_description": (
            "Seguimiento de las operaciones bursátiles declaradas por políticos y figuras "
            "públicas de EEUU."
        ),
        # Lo que la base guarda tal cual lo trae la fuente (cámara, cargo,
        # partido) y la interfaz tiene que decir en su idioma.
        "labels": {
            "House": "Cámara",
            "Senate": "Senado",
            "Democrat": "Demócrata",
            "Republican": "Republicano",
            "Independent": "Independiente",
            "Libertarian": "Libertario",
        },
        # Errores
        "error_404": "Esta página no existe.",
        "error_generic": "Algo ha fallado por nuestro lado.",
        "error_home": "Volver a la portada",
    },
    "en": {
        "lang_switch": "Español",
        "theme_dark": "Night mode",
        "theme_light": "Day mode",
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
        "hero_cta_alt": "Latest trades",
        "hero_badge": "Official House and SEC disclosures",
        "hero_lede": (
            "Every purchase and every sale a member of Congress or a corporate "
            "officer is required to declare, gathered in one place and signed "
            "with a name."
        ),
        "hero_feed_title": "Just declared",
        "hero_feed_empty": "No trades loaded yet.",
        "hero_feed_all": "See the latest trades",
        "hero_sources": "Sources: House Clerk (STOCK Act) · SEC EDGAR (Form 4)",
        # Stats
        "stat_trades": "Trades",
        "stat_capital": "Declared volume",
        "stat_capital_sub": "Buys plus sells, excluding grants and gifts",
        "stat_last_sub": "Date of the most recent filing",
        "stat_range": "By brackets: between {min} and {max}",
        "stat_range_open": "By brackets: over {min}",
        "stat_lag": "Discloses {days} days after trading on average",
        "stat_late": "{n} past the 45-day deadline",
        "trade_lag": "disclosed {days} days later",
        "facts_people": "profiles",
        "facts_trades": "trades",
        "facts_capital": "in buys and sells",
        "facts_last": "latest filing",
        "stat_ops_declared": "Declared in official filings",
        "stat_split": "Buys / sells",
        "stat_split_sub": "Split of the declared activity",
        "stat_last_trade": "Latest filing",
        # Digest cards
        "digest_title": "What each of them buys and sells",
        "digest_sub": (
            "One card per person, sorted by the volume they declare in buys and sells. "
            "Each one sums up which securities it goes into, whether they are buying or "
            "selling, and what their latest trade was."
        ),
        "digest_capital": "Volume",
        "digest_ops": "Trades",
        "digest_bias": "Bias",
        "digest_bias_hint": "Based on the number of declared buys and sells",
        "digest_buying": "buys",
        "digest_selling": "sells",
        "digest_positions": "Where their volume goes",
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
        "trends_top_sub": "Declared buys and sells per ticker · top {n}",
        "trends_split_title": "Buys versus sells",
        "trends_split_sub": "Split of the filtered trades",
        "trends_split_sub_profile": "Split across {n} trades",
        "side_buy": "Buy",
        "side_sell": "Sell",
        "side_other": "Other types",
        "kind_exchange": "Exchange",
        "kind_grant": "Grant",
        "kind_option": "Option exercise",
        "kind_tax": "Tax withholding",
        "kind_gift": "Gift",
        "kind_conversion": "Conversion",
        "kind_disposition": "Disposition",
        "kind_other": "Other",
        "side_buys": "Buys",
        "side_sells": "Sells",
        "ops_short": "trades",
        "people_empty": "No politicians match this search.",
        "people_more": "Showing the 24 with the most declared volume · {n} more available through the",
        "people_more_link": "API",
        # Profile
        "profile_back": "All profiles",
        "profile_bio_empty": "No biography is available for this person yet.",
        "profile_bio_more": "Read more",
        "profile_bio_less": "Read less",
        "profile_bio_source": "Biography from {source}, licensed CC BY-SA.",
        "profile_bio_other_lang": "Biography available in Spanish only.",
        "profile_photo_credit": "Photo: {author} · {license}",
        "profile_top_sub": "Buy and sell volume per security · top {n}",
        "profile_dormant": (
            "No Form 4 filings since {date}: they may have left the post, and their figures "
            "date from then."
        ),
        # Wealth (business profiles only)
        "wealth_title": "Declared holdings",
        "wealth_sub": (
            "Shares they declare owning —directly or through trusts and companies— in "
            "their most recent Form 4 filings, valued at market price."
        ),
        "wealth_total": "Market value",
        "wealth_positions": "Positions",
        "wealth_shares": "Shares",
        "wealth_price": "Price",
        "wealth_value": "Value",
        "wealth_as_of": "Declared",
        "wealth_updated": "Quotes from {source}; the oldest from {when}",
        "wealth_stale": (
            "Warning: some quotes are {hours} hours old. The automatic refresh could not "
            "update them and the value may not match the market."
        ),
        "wealth_no_fx": "No exchange rate",
        "wealth_converted": (
            "{n} positions trade in another currency and are converted to {currency} at "
            "the day's exchange rate."
        ),
        "wealth_no_price": "No quote",
        "wealth_missing": "{n} without a quote, excluded from the total.",
        "wealth_missing_short": "{n} unpriced",
        "wealth_unavailable": "Unavailable",
        "wealth_disclaimer": (
            "This is not their total net worth: it only counts shares in companies where "
            "they must report to the SEC. Options, warrants and convertibles are listed "
            "separately. Indirect ownership —trusts, companies, foundations— is added because "
            "Form 4 declares it as theirs, but it may be control rather than their own "
            "investment: each row says how much it is."
        ),
        "wealth_indirect": "{n} indirect",
        "wealth_split": "{declared} declared, split-adjusted ×{factor}",
        "wealth_dividends": (
            "Since the date of each balance they have paid out about {amount} in dividends, "
            "not added to the total: it is unknown whether they were reinvested."
        ),
        "derivatives_title": "Options and convertibles",
        "derivatives_sub": (
            "Rights over shares declared in table II of their Form 4 filings: options, "
            "warrants, restricted units and convertible shares."
        ),
        "derivatives_total": "Intrinsic value",
        "derivatives_security": "Right",
        "derivatives_underlying": "Shares",
        "derivatives_strike": "Exercise",
        "derivatives_expiration": "Expires",
        "derivatives_value": "Intrinsic",
        "derivatives_no_strike": "No cost",
        "derivatives_out_of_money": "Out of the money",
        "derivatives_disclaimer": (
            "Intrinsic value: what exercising today would yield (price minus exercise price, "
            "times shares), without the time value the market gives them or taxes. It is "
            "not added to the value of the shares: exercising costs money and many cannot "
            "be exercised yet. Expired ones are not shown."
        ),
        "wealth_congress_note": (
            "Members of Congress declare trades in amount brackets, without share counts "
            "or positions, so their holdings cannot be calculated. Each amount is the "
            "declared bracket; volume adds up the midpoint of each one."
        ),
        # Copy performance
        "perf_title": "What if you had copied them?",
        "perf_sub": (
            "A portfolio that buys each security at the close of the session after its "
            "purchase is published and sells it after a published sale or after {hold} "
            "sessions, equally weighted, with {cost} basis points of cost per trade. "
            "Compared with {benchmark} over the same sessions."
        ),
        "perf_total": "Total return",
        "perf_vs_benchmark": "{benchmark} over the same period: {value}",
        "perf_alpha": "Annual alpha",
        "perf_alpha_sub": "Versus the index, beta-adjusted ({beta})",
        "perf_sharpe_sub": "Return per unit of risk; risk-free rate {rf}",
        "perf_drawdown": "Max drawdown",
        "perf_drawdown_sub": "{benchmark}: {value}",
        "perf_cagr": "Annualised return",
        "perf_volatility": "Annual volatility",
        "perf_correlation": "Correlation with the index",
        "perf_tracking": "Tracking error",
        "perf_ir": "Information ratio",
        "perf_win_rate": "Trades that beat the index",
        "perf_avg_win_loss": "Average excess when winning / losing",
        "perf_payoff": "Payoff ratio",
        "perf_ic": "Information coefficient (21 sessions)",
        "perf_sample": "Sample",
        "perf_sample_value": "{trades} copied trades, {sessions} sessions ({start} to {end})",
        "perf_unavailable": (
            "Not enough data to measure it: {signals} buys and sells in the period, {priced} "
            "with price history and {trades} copyable trades. At least five and three months "
            "of sessions are needed."
        ),
        "perf_disclaimer": (
            "Backward-looking simulation on public data, not a recommendation. Total return "
            "with dividends, before taxes. With few trades the metrics are very unstable, and "
            "past returns do not guarantee future ones."
        ),
        "perf_computed": "Computed {when}",
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
        # Permanent notice, above the navigation on every page.
        "disclaimer_bar_lead": "Not financial advice.",
        "disclaimer_bar_body": (
            "Declared data, up to 45 days late, which may be incomplete or carry "
            "errors from the source. Check it against the official source and with a "
            "professional before investing."
        ),
        "disclaimer_bar_link": "Legal notice",
        "footer_legal": "Legal",
        "footer_disclaimer": "Legal notice",
        "footer_terms": "Terms of use",
        "footer_privacy": "Privacy",
        "legal_title": "Legal notice, terms and privacy",
        # Footer
        "footer_about": (
            "Public data extracted from House of Representatives disclosures (STOCK Act) "
            "and SEC Form 4 filings. We show what was declared, without interpreting intent."
        ),
        "footer_sources": "Sources",
        "footer_sec": "SEC — EDGAR",
        "footer_house": "House — Clerk",
        "footer_data": "Data",
        "footer_trades_json": "Trades (JSON)",
        "footer_people_json": "Politicians (JSON)",
        "footer_trades_csv": "Trades (CSV)",
        "footer_feed": "New trade alerts (Atom)",
        "footer_health": "Service status",
        "footer_note": (
            "PTRs are published up to 45 days after the trade: this platform reduces the lag "
            "between a filing going public and you reading it, not the market's."
        ),
        "meta_description": (
            "Tracking the stock trades declared by US politicians and public figures."
        ),
        "labels": {
            "Fundador": "Founder",
            "Presidente": "Chair",
            "Ex-CEO": "Former CEO",
        },
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
