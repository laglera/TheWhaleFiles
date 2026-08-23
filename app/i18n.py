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
        "nav_back_index": "Volver al índice",
        "nav_ranking": "Clasificación",
        # Hero
        "hero_claim_1": "Legislan sobre unos mercados en los que también invierten.",
        "hero_claim_2": "Mira lo que declaran.",
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
        "wealth_no_key": (
            "Cotizaciones no disponibles: falta configurar la clave de la API de precios."
        ),
        "wealth_congress_note": (
            "Los congresistas declaran sus operaciones en tramos de importe, sin número "
            "de acciones ni posiciones, así que no es posible calcular su patrimonio."
        ),
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
        # Cuentas
        "nav_login": "Entrar",
        "nav_account": "Mi cuenta",
        "nav_logout": "Salir",
        "auth_login_title": "Entra en tu cuenta",
        "auth_login_sub": "Recupera a quién sigues y su actividad reciente.",
        "auth_signup_title": "Crea tu cuenta",
        "auth_signup_sub": "Sigue a quien te interese y ten sus operaciones a mano.",
        "auth_email": "Correo electrónico",
        "auth_password": "Contraseña",
        "auth_password_hint": "Mínimo 8 caracteres.",
        "auth_name": "Nombre",
        "auth_name_ph": "Cómo quieres que te llamemos",
        "auth_name_optional": "Opcional",
        "auth_submit_login": "Entrar",
        "auth_submit_signup": "Crear cuenta",
        "auth_to_signup": "¿Aún no tienes cuenta? Créala",
        "auth_to_login": "¿Ya tienes cuenta? Entra",
        "auth_error_email": "Escribe una dirección de correo válida.",
        "auth_error_short": "La contraseña necesita al menos 8 caracteres.",
        "auth_error_long": "La contraseña es demasiado larga.",
        "auth_error_taken": "Ya existe una cuenta con ese correo.",
        "auth_error_credentials": "El correo o la contraseña no son correctos.",
        "account_title": "Tu cuenta",
        "account_since": "Registrado el {date}",
        "account_following": "A quién sigues",
        "account_following_sub": "Tus perfiles guardados, con el capital que han declarado.",
        "account_empty": "Todavía no sigues a nadie.",
        "account_empty_cta": "Explorar perfiles",
        "account_recent": "Actividad reciente",
        "account_recent_sub": "Últimas operaciones declaradas por los perfiles que sigues.",
        "account_recent_empty": "Quienes sigues no tienen operaciones registradas.",
        "auth_error_throttled": (
            "Demasiados intentos desde esta conexión. Inténtalo de nuevo dentro de un rato."
        ),
        # Baja de la cuenta
        "account_danger": "Cerrar la cuenta",
        "account_danger_sub": (
            "Se borran tu correo, tu contraseña y los perfiles que sigues. "
            "No se puede deshacer."
        ),
        "account_delete": "Borrar mi cuenta",
        "account_delete_confirm": (
            "Se borrará tu cuenta y todo lo que sigues, sin vuelta atrás. ¿Continuar?"
        ),
        # Errores
        "error_404": "Esta página no existe.",
        "error_generic": "Algo ha fallado por nuestro lado.",
        "error_home": "Volver a la portada",
        # Pie legal
        "footer_legal": "Legal",
        "legal_notice": "Aviso legal",
        "legal_privacy": "Privacidad",
        "legal_terms": "Condiciones de uso",
        "legal_cookies": "Cookies",
        "legal_updated": "Última actualización: agosto de 2026",
        "legal_contact_intro": "Contacto:",
        "legal_entity_missing": "titular del sitio",
        "disclaimer_title": "Esto no es asesoramiento financiero",
        "disclaimer_body": (
            "TheWhaleFiles recopila y ordena declaraciones públicas. No es un asesor de "
            "inversiones, no recomienda comprar ni vender nada, y no garantiza que los "
            "datos estén completos ni actualizados. Cualquier decisión de inversión que "
            "tomes es tuya y de nadie más."
        ),
        "legal_notice_body": [
            (
                "Titularidad",
                "TheWhaleFiles es un proyecto personal operado por {entity}. Se ofrece tal cual, "
                "sin ánimo de lucro y sin relación con ninguna institución pública ni con las "
                "personas cuyos datos se muestran.",
            ),
            (
                "Objeto del sitio",
                "El sitio recopila, normaliza y presenta declaraciones de transparencia "
                "financiera que ya son públicas: los Periodic Transaction Reports que la STOCK "
                "Act obliga a presentar a los miembros del Congreso de Estados Unidos y los "
                "formularios 4 que los directivos presentan ante la SEC.",
            ),
            (
                "Sobre las personas mencionadas",
                "Los nombres que aparecen corresponden a cargos públicos y directivos, y los "
                "datos proceden de sus propias declaraciones oficiales. El sitio muestra lo "
                "declarado sin atribuir intenciones, sin afirmar que ninguna operación sea "
                "ilegal y sin acusar a nadie de nada. Si detectas un dato erróneo sobre ti, "
                "escríbenos y lo corregimos o lo retiramos.",
            ),
            (
                "Propiedad intelectual",
                "Las declaraciones oficiales son documentos públicos del gobierno de Estados "
                "Unidos. Las biografías y los retratos proceden de Wikipedia y Wikimedia "
                "Commons, bajo licencia CC BY-SA, y se acreditan en cada ficha. El código de "
                "la plataforma se publica bajo licencia MIT.",
            ),
            (
                "Responsabilidad",
                "Los datos pueden contener errores de origen o de procesamiento, y llegan con "
                "el retraso legal de hasta 45 días que marca la propia STOCK Act. No se asume "
                "responsabilidad por decisiones tomadas a partir de ellos.",
            ),
        ],
        "legal_privacy_body": [
            (
                "Qué datos se recogen",
                "Si no creas una cuenta, ninguno que te identifique: no hay analítica, ni "
                "rastreadores, ni publicidad. Si creas una cuenta, se guardan tu correo "
                "electrónico, el hash de tu contraseña (bcrypt, nunca la contraseña en claro), "
                "el nombre que elijas mostrar, la fecha de alta y los perfiles que sigues.",
            ),
            (
                "Para qué se usan",
                "Únicamente para sostener tu sesión y mostrarte a quién sigues. No se venden, "
                "no se ceden a terceros y no se usan para enviarte correo comercial.",
            ),
            (
                "Base legal y conservación",
                "El tratamiento se basa en la ejecución de la relación que solicitas al "
                "registrarte. Los datos se conservan mientras la cuenta exista. Los registros "
                "temporales de intentos de acceso, que sólo guardan una dirección IP y una "
                "fecha para frenar ataques de fuerza bruta, se borran automáticamente a las "
                "24 horas.",
            ),
            (
                "Tus derechos",
                "Puedes acceder a tus datos desde tu cuenta y borrarlos por completo en "
                "cualquier momento con el botón «Borrar mi cuenta», que elimina tu correo, tu "
                "contraseña y tus seguimientos sin dejar copia. Para acceder, rectificar, "
                "oponerte o portar tus datos, escríbenos.",
            ),
            (
                "Encargados del tratamiento",
                "El sitio se aloja en Vercel y la base de datos en un proveedor de PostgreSQL "
                "gestionado; ambos actúan como encargados del tratamiento. Los precios de "
                "mercado se consultan a un proveedor externo de cotizaciones, al que no se le "
                "envía ningún dato tuyo.",
            ),
        ],
        "legal_terms_body": [
            (
                "Uso del servicio",
                "El acceso es libre y gratuito. Al usar el sitio aceptas estas condiciones. "
                "Puedes consultar los datos, enlazarlos y citarlos indicando la fuente.",
            ),
            (
                "Uso prohibido",
                "No está permitido usar el sitio para acosar a las personas mencionadas, ni "
                "raspar la web de forma que degrade el servicio, ni presentar los datos como "
                "prueba de un delito. Para uso automatizado, la API pública está paginada y "
                "documentada: úsala en lugar de raspar las páginas.",
            ),
            (
                "Cuentas",
                "Eres responsable de la contraseña que elijas. Podemos cerrar cuentas que "
                "usen el servicio en contra de estas condiciones.",
            ),
            (
                "Sin garantías",
                "El servicio se ofrece tal cual, sin garantía de disponibilidad, exactitud ni "
                "continuidad. Puede cambiar o dejar de funcionar en cualquier momento.",
            ),
        ],
        "legal_cookies_body": [
            (
                "Qué se guarda en tu navegador",
                "Sólo lo imprescindible para que el sitio funcione. No hay cookies de "
                "analítica, de publicidad ni de terceros, así que no hace falta pedirte "
                "consentimiento para ellas: no existen.",
            ),
            (
                "twf_session",
                "Cookie técnica. Guarda el testigo aleatorio de tu sesión mientras estás "
                "dentro. Sólo se crea si inicias sesión, dura 30 días y desaparece al salir. "
                "Es HttpOnly, así que ningún script puede leerla.",
            ),
            (
                "twf_lang",
                "Cookie técnica. Recuerda si prefieres la web en español o en inglés. Dura un "
                "año y no identifica a nadie.",
            ),
            (
                "twf:theme",
                "No es una cookie sino un valor en el almacenamiento local de tu navegador: "
                "recuerda si prefieres el modo claro o el modo noche. No sale de tu equipo.",
            ),
        ],
        "follow_undo": "Dejar de seguir",
        "follow_login": "Entra para seguirle",
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
        "nav_back_index": "Back to index",
        "nav_ranking": "Ranking",
        # Hero
        "hero_claim_1": "They legislate on markets they also invest in.",
        "hero_claim_2": "See what they declare.",
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
        "wealth_no_key": "Quotes unavailable: the price API key is not configured.",
        "wealth_congress_note": (
            "Members of Congress declare trades in amount brackets, without share counts "
            "or positions, so their holdings cannot be calculated."
        ),
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
        # Accounts
        "nav_login": "Log in",
        "nav_account": "My account",
        "nav_logout": "Log out",
        "auth_login_title": "Log in to your account",
        "auth_login_sub": "Get back the profiles you follow and their recent activity.",
        "auth_signup_title": "Create your account",
        "auth_signup_sub": "Follow whoever interests you and keep their trades at hand.",
        "auth_email": "Email address",
        "auth_password": "Password",
        "auth_password_hint": "At least 8 characters.",
        "auth_name": "Name",
        "auth_name_ph": "What we should call you",
        "auth_name_optional": "Optional",
        "auth_submit_login": "Log in",
        "auth_submit_signup": "Create account",
        "auth_to_signup": "No account yet? Create one",
        "auth_to_login": "Already have an account? Log in",
        "auth_error_email": "Enter a valid email address.",
        "auth_error_short": "The password needs at least 8 characters.",
        "auth_error_long": "That password is too long.",
        "auth_error_taken": "An account with that email already exists.",
        "auth_error_credentials": "That email or password is not correct.",
        "account_title": "Your account",
        "account_since": "Joined on {date}",
        "account_following": "Who you follow",
        "account_following_sub": "Your saved profiles, with the capital they have declared.",
        "account_empty": "You are not following anyone yet.",
        "account_empty_cta": "Browse profiles",
        "account_recent": "Recent activity",
        "account_recent_sub": "Latest trades declared by the profiles you follow.",
        "account_recent_empty": "The profiles you follow have no recorded trades.",
        "auth_error_throttled": (
            "Too many attempts from this connection. Try again in a little while."
        ),
        # Closing the account
        "account_danger": "Close your account",
        "account_danger_sub": (
            "This deletes your email, your password and the profiles you follow. "
            "It cannot be undone."
        ),
        "account_delete": "Delete my account",
        "account_delete_confirm": (
            "This deletes your account and everything you follow, permanently. Continue?"
        ),
        # Errors
        "error_404": "This page does not exist.",
        "error_generic": "Something broke on our side.",
        "error_home": "Back to the home page",
        # Legal footer
        "footer_legal": "Legal",
        "legal_notice": "Legal notice",
        "legal_privacy": "Privacy",
        "legal_terms": "Terms of use",
        "legal_cookies": "Cookies",
        "legal_updated": "Last updated: August 2026",
        "legal_contact_intro": "Contact:",
        "legal_entity_missing": "the site operator",
        "disclaimer_title": "This is not financial advice",
        "disclaimer_body": (
            "TheWhaleFiles collects and organises public disclosures. It is not an investment "
            "adviser, it does not recommend buying or selling anything, and it does not "
            "guarantee that the data is complete or current. Any investment decision you make "
            "is yours alone."
        ),
        "legal_notice_body": [
            (
                "Ownership",
                "TheWhaleFiles is a personal project operated by {entity}. It is offered as is, "
                "not for profit, and is unaffiliated with any public institution or with the "
                "people whose data it shows.",
            ),
            (
                "What the site does",
                "The site collects, normalises and presents financial transparency disclosures "
                "that are already public: the Periodic Transaction Reports the STOCK Act "
                "requires from members of the US Congress, and the Form 4 filings corporate "
                "insiders submit to the SEC.",
            ),
            (
                "About the people listed",
                "The names shown belong to public officials and corporate insiders, and the "
                "data comes from their own official filings. The site shows what was declared "
                "without ascribing intent, without claiming any trade is illegal and without "
                "accusing anyone of anything. If you spot wrong data about yourself, write to "
                "us and we will correct or remove it.",
            ),
            (
                "Intellectual property",
                "The official filings are public documents of the United States government. "
                "Biographies and portraits come from Wikipedia and Wikimedia Commons under a "
                "CC BY-SA licence and are credited on each profile. The platform's source code "
                "is published under the MIT licence.",
            ),
            (
                "Liability",
                "The data may contain errors at the source or in processing, and arrives with "
                "the legal lag of up to 45 days that the STOCK Act itself allows. No liability "
                "is accepted for decisions made on the basis of it.",
            ),
        ],
        "legal_privacy_body": [
            (
                "What data is collected",
                "If you do not create an account, nothing that identifies you: there is no "
                "analytics, no trackers and no advertising. If you create an account, we store "
                "your email address, your password hash (bcrypt, never the plain password), the "
                "display name you choose, your sign-up date and the profiles you follow.",
            ),
            (
                "What it is used for",
                "Only to keep your session and show you who you follow. It is never sold, never "
                "shared with third parties and never used to send you marketing email.",
            ),
            (
                "Legal basis and retention",
                "Processing is based on performing the relationship you request when you sign "
                "up. Data is kept for as long as the account exists. The temporary log of "
                "sign-in attempts, which stores only an IP address and a timestamp to stop "
                "brute-force attacks, is deleted automatically after 24 hours.",
            ),
            (
                "Your rights",
                "You can see your data from your account page and delete all of it at any time "
                "with the \u201cDelete my account\u201d button, which removes your email, your "
                "password and your follows without keeping a copy. To access, rectify, object "
                "to or port your data, write to us.",
            ),
            (
                "Processors",
                "The site is hosted on Vercel and the database on a managed PostgreSQL "
                "provider; both act as data processors. Market prices are requested from an "
                "external quote provider, which receives no data about you.",
            ),
        ],
        "legal_terms_body": [
            (
                "Using the service",
                "Access is free and open. By using the site you accept these terms. You may "
                "consult, link to and quote the data as long as you credit the source.",
            ),
            (
                "Prohibited use",
                "You may not use the site to harass the people listed, scrape it in ways that "
                "degrade the service, or present the data as proof of a crime. For automated "
                "use, the public API is paginated and documented: use it instead of scraping "
                "the pages.",
            ),
            (
                "Accounts",
                "You are responsible for the password you choose. We may close accounts that "
                "use the service against these terms.",
            ),
            (
                "No warranty",
                "The service is provided as is, with no guarantee of availability, accuracy or "
                "continuity. It may change or stop working at any time.",
            ),
        ],
        "legal_cookies_body": [
            (
                "What is stored in your browser",
                "Only what the site needs to work. There are no analytics, advertising or "
                "third-party cookies, so there is no consent to ask for: they do not exist.",
            ),
            (
                "twf_session",
                "Technical cookie. Holds the random token for your session while you are "
                "signed in. It is only created if you log in, lasts 30 days and disappears when "
                "you log out. It is HttpOnly, so no script can read it.",
            ),
            (
                "twf_lang",
                "Technical cookie. Remembers whether you prefer the site in Spanish or English. "
                "It lasts a year and identifies nobody.",
            ),
            (
                "twf:theme",
                "Not a cookie but a value in your browser's local storage: it remembers whether "
                "you prefer light or dark mode. It never leaves your device.",
            ),
        ],
        "follow_undo": "Unfollow",
        "follow_login": "Log in to follow",
    },
}


def normalise_lang(value: str | None) -> str:
    return value if value in LANGS else DEFAULT_LANG


def get_translations(lang: str) -> dict[str, Any]:
    return TRANSLATIONS[normalise_lang(lang)]
