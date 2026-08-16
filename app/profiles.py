"""Biografías y retratos de las personas del catálogo.

Las fichas explicaban qué había invertido cada persona, no quién era. Este
módulo trae la biografía real desde Wikipedia y el retrato desde Wikimedia
Commons.

La identidad se resuelve contra Wikidata, no buscando texto en Wikipedia: una
búsqueda por nombre devuelve el libro sobre Elon Musk antes que Elon Musk, y
para un congresista poco conocido devuelve cualquier artículo que mencione su
apellido. Wikidata permite exigir que la entidad sea una persona y que su
ocupación encaje con el catálogo, que es lo que evita colgar la biografía de
otro en una ficha.

Las dos fuentes obligan a citar: el texto de Wikipedia es CC BY-SA (hay que
enlazar el artículo) y cada foto de Commons lleva su autor y su licencia, que
se guardan junto a la imagen para poder mostrarlos.

Wikimedia exige un User-Agent identificable y penaliza las ráfagas, así que
todas las llamadas pasan por `_fetch`, que espacia las peticiones.
"""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any, Optional

from sqlalchemy import select

from app.database import SessionLocal, prepare_database
from app.models import Politician
from app.names import clean_person_name, short_name

USER_AGENT = "TheWhaleFiles/0.1 (contacto: alejandro.web00@gmail.com)"
REQUEST_PAUSE = 0.15
LANGUAGES = ("es", "en")

# Identificadores de Wikidata usados para validar a quién hemos encontrado.
HUMAN = "Q5"
UNITED_STATES = "Q30"
POLITICAL_OCCUPATIONS = {
    "Q82955",    # político
    "Q10669499", # miembro de la Cámara de Representantes
    "Q13217683", # senador de los Estados Unidos
    "Q1930187",  # periodista/legislador en algunas fichas
}
BUSINESS_OCCUPATIONS = {
    "Q2961975", # ejecutivo de empresa (el más común entre los CEO del catálogo)
    "Q131524",  # empresario
    "Q43845",   # hombre/mujer de negocios
    "Q484876",  # consejero delegado
    "Q806798",  # banquero
    "Q188094",  # economista
    "Q81096",   # ingeniero
    "Q1662561", # financiero
}

# El estado que guarda la ficha del congresista viene como código de dos letras
# y sirve para desambiguar homónimos: "David Taylor" hay muchos, "David Taylor
# Ohio politician" sólo uno.
US_STATES = {
    "AL": "Alabama", "AK": "Alaska", "AZ": "Arizona", "AR": "Arkansas",
    "CA": "California", "CO": "Colorado", "CT": "Connecticut", "DE": "Delaware",
    "FL": "Florida", "GA": "Georgia", "HI": "Hawaii", "ID": "Idaho",
    "IL": "Illinois", "IN": "Indiana", "IA": "Iowa", "KS": "Kansas",
    "KY": "Kentucky", "LA": "Louisiana", "ME": "Maine", "MD": "Maryland",
    "MA": "Massachusetts", "MI": "Michigan", "MN": "Minnesota", "MS": "Mississippi",
    "MO": "Missouri", "MT": "Montana", "NE": "Nebraska", "NV": "Nevada",
    "NH": "New Hampshire", "NJ": "New Jersey", "NM": "New Mexico", "NY": "New York",
    "NC": "North Carolina", "ND": "North Dakota", "OH": "Ohio", "OK": "Oklahoma",
    "OR": "Oregon", "PA": "Pennsylvania", "RI": "Rhode Island", "SC": "South Carolina",
    "SD": "South Dakota", "TN": "Tennessee", "TX": "Texas", "UT": "Utah",
    "VT": "Vermont", "VA": "Virginia", "WA": "Washington", "WV": "West Virginia",
    "WI": "Wisconsin", "WY": "Wyoming", "DC": "Washington, D.C.",
}

def _fetch(url: str) -> Any:
    time.sleep(REQUEST_PAUSE)
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.loads(response.read())


def _claim_ids(claims: dict[str, Any], prop: str) -> list[str]:
    """Identificadores referenciados por una propiedad de la entidad."""
    found = []
    for claim in claims.get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value", {})
        if isinstance(value, dict) and "id" in value:
            found.append(value["id"])
    return found


def _claim_string(claims: dict[str, Any], prop: str) -> Optional[str]:
    for claim in claims.get(prop, []):
        value = claim.get("mainsnak", {}).get("datavalue", {}).get("value")
        if isinstance(value, str):
            return value
    return None


def score_entity(entity: dict[str, Any], category: str) -> int:
    """Puntúa cómo de bien encaja una entidad con la persona que buscamos."""
    claims = entity.get("claims", {})
    if HUMAN not in _claim_ids(claims, "P31"):
        return 0

    occupations = set(_claim_ids(claims, "P106"))
    positions = _claim_ids(claims, "P39")
    wanted = BUSINESS_OCCUPATIONS if category == "business" else POLITICAL_OCCUPATIONS

    score = 1  # es una persona
    if occupations & wanted:
        score += 3
    if positions:
        score += 2 if category != "business" else 1
    if UNITED_STATES in _claim_ids(claims, "P27"):
        score += 1
    return score


def resolve_entity(name: str, category: str) -> Optional[dict[str, Any]]:
    """Busca a la persona en Wikidata y devuelve la entidad más plausible."""
    search_url = (
        "https://www.wikidata.org/w/api.php?action=wbsearchentities&format=json"
        f"&language=en&limit=7&search={urllib.parse.quote(name)}"
    )
    try:
        candidates = [item["id"] for item in _fetch(search_url).get("search", [])]
    except (urllib.error.URLError, KeyError, json.JSONDecodeError):
        return None
    if not candidates:
        return None

    entities_url = (
        "https://www.wikidata.org/w/api.php?action=wbgetentities&format=json"
        "&props=claims|sitelinks|labels"
        f"&ids={'|'.join(candidates)}"
    )
    try:
        entities = _fetch(entities_url)["entities"]
    except (urllib.error.URLError, KeyError, json.JSONDecodeError):
        return None

    best, best_score = None, 0
    # `candidates` viene ordenado por relevancia; se recorre en ese orden para
    # que a igual puntuación gane el resultado mejor posicionado.
    for qid in candidates:
        entity = entities.get(qid)
        if not entity:
            continue
        score = score_entity(entity, category)
        if score > best_score:
            best, best_score = entity, score

    # Una persona suelta sin ocupación ni cargo reconocibles no basta: sería
    # colgar la biografía de un homónimo cualquiera.
    return best if best_score >= 4 else None


def get_entity(qid: str) -> Optional[dict[str, Any]]:
    url = (
        "https://www.wikidata.org/w/api.php?action=wbgetentities&format=json"
        f"&props=claims|sitelinks|labels&ids={urllib.parse.quote(qid)}"
    )
    try:
        return _fetch(url)["entities"].get(qid)
    except (urllib.error.URLError, KeyError, json.JSONDecodeError):
        return None


def resolve_via_wikipedia(name: str, context: str, category: str) -> Optional[dict[str, Any]]:
    """Segundo intento para nombres muy comunes.

    La búsqueda de Wikidata sólo mira etiquetas y alias, así que con "David
    Solomon" devuelve siete personas y ninguna es el banquero. La de Wikipedia
    busca en el texto completo y acepta contexto ("Goldman Sachs"); el artículo
    que encuentra se valida después contra Wikidata igual que en la vía normal.
    """
    query = urllib.parse.quote(f"{name} {context}".strip())
    url = (
        "https://en.wikipedia.org/w/api.php?action=query&format=json"
        f"&list=search&srsearch={query}&srlimit=3"
    )
    try:
        results = _fetch(url)["query"]["search"]
    except (urllib.error.URLError, KeyError, json.JSONDecodeError):
        return None

    for result in results:
        titles = urllib.parse.quote(result["title"])
        props_url = (
            "https://en.wikipedia.org/w/api.php?action=query&format=json"
            f"&prop=pageprops&ppprop=wikibase_item&titles={titles}"
        )
        try:
            pages = _fetch(props_url)["query"]["pages"]
        except (urllib.error.URLError, KeyError, json.JSONDecodeError):
            continue

        for page in pages.values():
            qid = (page.get("pageprops") or {}).get("wikibase_item")
            if not qid:
                continue
            entity = get_entity(qid)
            if entity and score_entity(entity, category) >= 4:
                return entity
    return None


def fetch_summary(title: str, lang: str) -> Optional[dict[str, Any]]:
    """Resumen introductorio del artículo, con retrato y URL de origen."""
    url = (
        f"https://{lang}.wikipedia.org/api/rest_v1/page/summary/"
        f"{urllib.parse.quote(title.replace(' ', '_'))}"
    )
    try:
        payload = _fetch(url)
    except (urllib.error.URLError, json.JSONDecodeError):
        return None
    if payload.get("type") == "disambiguation" or not payload.get("extract"):
        return None
    return payload


def commons_image_url(filename: str, width: int = 600) -> str:
    """URL estable de un fichero de Commons, sin depender de su hash interno."""
    quoted = urllib.parse.quote(filename.replace(" ", "_"))
    return f"https://commons.wikimedia.org/wiki/Special:FilePath/{quoted}?width={width}"


def fetch_photo_credits(filename: str) -> dict[str, Optional[str]]:
    """Autor y licencia del retrato: sin esto no se puede publicar la foto."""
    empty: dict[str, Optional[str]] = {"author": None, "license": None, "source_url": None}
    if not filename:
        return empty

    url = (
        "https://commons.wikimedia.org/w/api.php?action=query&format=json"
        "&prop=imageinfo&iiprop=extmetadata|url"
        f"&titles={urllib.parse.quote('File:' + filename)}"
    )
    try:
        pages = _fetch(url)["query"]["pages"]
    except (urllib.error.URLError, KeyError, json.JSONDecodeError):
        return empty

    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        metadata = info.get("extmetadata") or {}
        author = metadata.get("Artist", {}).get("value")
        if author:
            # El campo de autor viene como HTML (enlaces al perfil del fotógrafo).
            author = re.sub(r"<[^>]+>", " ", author)
            author = re.sub(r"\s+", " ", author).strip()
        return {
            "author": author or None,
            "license": metadata.get("LicenseShortName", {}).get("value"),
            "source_url": info.get("descriptionurl"),
        }
    return empty


def build_profile(name: str, category: str, context: str = "") -> dict[str, Any]:
    """Reúne biografía en los dos idiomas y retrato acreditado de una persona.

    `context` es la empresa del directivo o el estado del congresista, y sólo
    entra en juego para deshacer homonimias.
    """
    clean = clean_person_name(name)
    entity = resolve_entity(clean, category)

    # Los nombres con varios intermedios ("Donald Sternoff Beyer") no coinciden
    # con la etiqueta de Wikidata, que suele ser la forma corta.
    if entity is None:
        brief = short_name(clean)
        if brief != clean:
            entity = resolve_entity(brief, category)

    if entity is None:
        entity = resolve_via_wikipedia(clean, context, category)

    if entity is None:
        return {}

    profile: dict[str, Any] = {}
    sitelinks = entity.get("sitelinks", {})

    for lang in LANGUAGES:
        title = (sitelinks.get(f"{lang}wiki") or {}).get("title")
        if not title:
            continue
        summary = fetch_summary(title, lang)
        if not summary:
            continue
        profile[f"bio_{lang}"] = summary["extract"]
        profile[f"bio_headline_{lang}"] = summary.get("description")
        profile.setdefault(
            "bio_source_url",
            (summary.get("content_urls") or {}).get("desktop", {}).get("page"),
        )

    # P18 es el retrato que la propia ficha de Wikidata declara como principal.
    filename = _claim_string(entity.get("claims", {}), "P18")
    if filename:
        credits = fetch_photo_credits(filename)
        # Sin licencia no se publica: no habría forma de acreditarla.
        if credits["license"]:
            profile["photo_remote_url"] = commons_image_url(filename)
            profile["photo_author"] = credits["author"]
            profile["photo_license"] = credits["license"]
            profile["photo_source_url"] = credits["source_url"]

    return profile


def import_profiles(
    limit: Optional[int] = None,
    only_missing: bool = True,
    category: Optional[str] = None,
    verbose: bool = True,
    retry_without_bio: bool = False,
) -> dict[str, int]:
    """Rellena biografías y retratos de las personas que aún no los tienen."""
    stats = {"checked": 0, "with_bio": 0, "with_photo": 0, "not_found": 0}
    prepare_database()

    with SessionLocal() as db:
        query = select(Politician).order_by(Politician.id)
        if category:
            query = query.where(Politician.category == category)
        if retry_without_bio:
            # Reintento tras mejorar la resolución: sólo quienes siguen sin
            # biografía, sin volver a pedir las que ya se encontraron.
            query = query.where(Politician.bio_es.is_(None), Politician.bio_en.is_(None))
        elif only_missing:
            query = query.where(Politician.profile_fetched_at.is_(None))
        if limit:
            query = query.limit(limit)

        for person in db.scalars(query).all():
            stats["checked"] += 1
            # Para un directivo, `state` guarda su empresa; para un congresista,
            # el código de su estado.
            context = (
                person.state
                if person.category == "business"
                else f"{US_STATES.get(person.state, person.state)} politician"
            )
            try:
                profile = build_profile(person.name, person.category, context)
            except Exception:
                profile = {}

            for field, value in profile.items():
                setattr(person, field, value)
            person.profile_fetched_at = datetime.utcnow()

            if profile.get("bio_es") or profile.get("bio_en"):
                stats["with_bio"] += 1
            else:
                stats["not_found"] += 1
            if profile.get("photo_remote_url"):
                stats["with_photo"] += 1

            if verbose:
                mark = "ok" if profile.get("bio_es") or profile.get("bio_en") else "--"
                print(f"  {mark} {person.name}")
            db.commit()

    return stats


if __name__ == "__main__":
    print("Importando biografías y retratos...")
    print(import_profiles())
