"""Normalización de los nombres que llegan de las fuentes oficiales.

El dataset del Congreso escribe a la misma persona de varias formas —
"Scott Franklin", "C. Scott Franklin" y "Scott Mr Franklin" son el mismo
representante de Florida— e intercala tratamientos en mitad del nombre. Sin
unificarlos, cada variante crea una ficha distinta y ninguna se encuentra en
Wikidata.
"""
from __future__ import annotations

import re

# Tratamientos que el dataset intercala: "John J Mr McGuire".
NAME_NOISE = {
    "mr", "mrs", "ms", "miss", "dr", "hon", "honorable", "rep",
    "sen", "representative", "senator", "the",
}
# Titulaciones y sufijos pegados al apellido: "Neal Patrick Dunn FACS".
NAME_SUFFIXES = {
    "jr", "sr", "ii", "iii", "iv", "phd", "md", "facs", "esq",
    "dds", "dvm", "cpa", "ret", "usa", "usn", "jd",
}


def clean_person_name(raw_name: str) -> str:
    """Deja el nombre en su forma canónica: nombre y apellidos, sin adornos."""
    text = re.sub(r"\s+", " ", (raw_name or "").replace(",", " ")).strip()

    # Apodo entrecomillado: 'Robert "Bobby" Scott' se conoce como Bobby Scott,
    # que es además el título de su artículo.
    nickname = re.search(r'["“‘\']([A-Za-z][\w.-]*)["”’\']', text)
    if nickname:
        text = f"{nickname.group(1)} {text[nickname.end():].strip()}".strip()

    parts = []
    for token in text.split():
        bare = token.strip(".").lower()
        if bare in NAME_NOISE or bare in NAME_SUFFIXES:
            continue
        # Iniciales sueltas ("John J McGuire"): estorban al buscar a la persona.
        if len(token.strip(".")) == 1:
            continue
        # La fuente a veces repite el nombre: "Scott Scott Franklin".
        if parts and parts[-1].lower() == token.lower():
            continue
        parts.append(token)
    return " ".join(parts) or text


def short_name(name: str) -> str:
    """Sólo nombre y apellido, sin los intermedios: 'Donald Sternoff Beyer'.

    Wikipedia titula a la mayoría de personas así, de modo que sirve de segundo
    intento cuando el nombre completo no encuentra a nadie.
    """
    parts = (name or "").split()
    return f"{parts[0]} {parts[-1]}" if len(parts) > 2 else name
