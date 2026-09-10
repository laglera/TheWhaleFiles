"""Partido de los congresistas, a partir del registro público de legisladores.

El dataset de operaciones de la Cámara no trae el partido, así que los 259
congresistas se guardaban como "Unknown": el filtro por partido no aparecía y
ninguna ficha lo decía. El proyecto `unitedstates/congress-legislators`
(dominio público) lo tiene para cada legislador, con su identificador del
Congreso (bioguide), que es el mismo que ya nombra los retratos oficiales.

La identificación va de más a menos segura: el retrato (bioguide exacto), el
nombre y apellido en su estado, y por último el apellido en su estado cuando
sólo hay una persona que encaje, para quien firma con el nombre formal y es
conocido por el apodo ("James Jordan" es Jim Jordan).
"""
from __future__ import annotations

import json
import re
import unicodedata
import urllib.request
from pathlib import Path
from typing import Any, Iterable, Optional

from sqlalchemy import select

from app.database import SessionLocal, prepare_database
from app.models import Politician

LEGISLATOR_URLS = (
    "https://unitedstates.github.io/congress-legislators/legislators-current.json",
    "https://unitedstates.github.io/congress-legislators/legislators-historical.json",
)
USER_AGENT = "TheWhaleFiles/0.1 (contacto: alejandro.web00@gmail.com)"
PHOTO_INDEX = Path(__file__).resolve().parent / "data" / "politician_photos.json"
# El dataset de operaciones empieza en 2012: quien dejó el Congreso antes no
# puede estar en él, y descartarlo evita homónimos del siglo XIX.
FIRST_RELEVANT_TERM = "2011"
UNKNOWN_PARTIES = {"", "Unknown"}


def _tokens(text: str) -> list[str]:
    # El apóstrofo se quita antes de pasar a ASCII: el registro escribe
    # "O’Halleran" con el tipográfico y el dataset "O'Halleran" con el recto.
    text = re.sub(r"['’‘`]", "", text or "")
    ascii_text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z ]", " ", ascii_text.lower()).split()


def fetch_legislators(urls: Iterable[str] = LEGISLATOR_URLS) -> list[dict[str, Any]]:
    people: list[dict[str, Any]] = []
    for url in urls:
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        with urllib.request.urlopen(request, timeout=60) as response:
            people.extend(json.loads(response.read()))
    return people


class LegislatorIndex:
    def __init__(self, legislators: list[dict[str, Any]]):
        self.by_bioguide: dict[str, dict[str, Any]] = {}
        self.by_full: dict[tuple[str, str, str], set[str]] = {}
        self.by_last: dict[tuple[str, str], set[str]] = {}

        for person in legislators:
            terms = person.get("terms") or []
            bioguide = (person.get("id") or {}).get("bioguide")
            if not bioguide or not terms:
                continue
            self.by_bioguide[bioguide] = person
            if not any(term.get("end", "") >= FIRST_RELEVANT_TERM for term in terms):
                continue

            name = person.get("name") or {}
            last = " ".join(_tokens(name.get("last", "")))
            firsts = {name.get("first", ""), name.get("nickname", "")}
            official = (name.get("official_full") or "").split()
            if official:
                firsts.add(official[0])
            for state in {term.get("state", "") for term in terms}:
                self.by_last.setdefault((last, state), set()).add(bioguide)
                for first in firsts:
                    first_tokens = _tokens(first)
                    if first_tokens:
                        key = (first_tokens[0], last, state)
                        self.by_full.setdefault(key, set()).add(bioguide)

    def find(self, name: str, state: str, bioguide: Optional[str] = None) -> Optional[dict]:
        if bioguide and bioguide in self.by_bioguide:
            return self.by_bioguide[bioguide]

        tokens = _tokens(name)
        if len(tokens) < 2:
            return None
        # Nombre de pila y cualquier final del nombre como apellido: "Donald
        # Sternoff Beyer" es Beyer, "Debbie Wasserman Schultz" es Wasserman
        # Schultz.
        candidates: set[str] = set()
        for start in range(1, len(tokens)):
            candidates |= self.by_full.get((tokens[0], " ".join(tokens[start:]), state), set())
        if len(candidates) != 1:
            # Por apellido solo, si nadie más de su estado lo comparte. El
            # apellido puede ser compuesto ("Matthew Robert Van Epps").
            candidates = set()
            for start in range(1, len(tokens)):
                for end in range(start + 1, len(tokens) + 1):
                    last = " ".join(tokens[start:end])
                    candidates |= self.by_last.get((last, state), set())
        if len(candidates) == 1:
            return self.by_bioguide[candidates.pop()]
        return None


def party_of(person: dict[str, Any]) -> Optional[str]:
    """El partido de su último mandato: el que tiene hoy o con el que se fue."""
    terms = person.get("terms") or []
    return terms[-1].get("party") if terms else None


def refresh_congress_parties(db, legislators: list[dict[str, Any]]) -> dict[str, int]:
    photos: dict[str, str] = {}
    if PHOTO_INDEX.exists():
        photos = json.loads(PHOTO_INDEX.read_text(encoding="utf-8"))
    index = LegislatorIndex(legislators)

    stats = {"updated": 0, "unmatched": 0}
    for person in db.scalars(select(Politician).where(Politician.category == "congress")).all():
        filename = photos.get(person.name) or ""
        bioguide = filename.rsplit(".", 1)[0] if filename else None
        found = index.find(person.name, person.state, bioguide)
        party = party_of(found) if found else None
        if not party:
            stats["unmatched"] += 1
            continue
        if person.party != party:
            person.party = party
            stats["updated"] += 1
    db.commit()
    return stats


def run(legislators: Optional[list[dict[str, Any]]] = None) -> dict[str, int]:
    prepare_database()
    legislators = legislators if legislators is not None else fetch_legislators()
    with SessionLocal() as db:
        return refresh_congress_parties(db, legislators)


if __name__ == "__main__":
    print("Asignando partido a los congresistas...")
    print(run())
