"""Tramos de importe de las declaraciones del Congreso.

La STOCK Act no pide la cifra exacta de cada operación sino el tramo en que cae
("$1,001 - $15,000", "$15,001 - $50,000"…). Los tramos son fijos por ley, así
que el límite inferior basta para saber de cuál se trata, aunque el documento
llegue recortado ("$15,001 -" o sólo "$15,001").

Para sumar volúmenes hace falta un número, y se usa el punto medio del tramo:
el mismo que publica el dataset de origen en `amount_mid`, para que la
identidad de las operaciones ya guardadas no cambie. Lo que no se hace es
enseñar ese punto medio como si fuera el importe: en pantalla va el tramo.
"""
from __future__ import annotations

import re
from typing import Any, Optional

# (límite inferior, límite superior, punto medio). El superior es None en el
# último tramo, que no tiene techo.
BRACKETS: tuple[tuple[int, Optional[int], int], ...] = (
    (1_001, 15_000, 8_000),
    (15_001, 50_000, 32_500),
    (50_001, 100_000, 75_000),
    (100_001, 250_000, 175_000),
    (250_001, 500_000, 375_000),
    (500_001, 1_000_000, 750_000),
    (1_000_001, 5_000_000, 3_000_000),
    (5_000_001, 25_000_000, 15_000_000),
    (25_000_001, 50_000_000, 37_500_000),
    (50_000_001, None, 50_000_001),
)
BY_LOWER = {lower: (lower, upper, mid) for lower, upper, mid in BRACKETS}
BY_MID = {mid: (lower, upper, mid) for lower, upper, mid in BRACKETS}

_NUMBER = re.compile(r"\$?\s*([0-9][0-9,]*(?:\.\d+)?)")


def congress_amount(raw_amount: Any, amount_mid: Any = None) -> float:
    """Importe con el que se guarda una operación del Congreso.

    El punto medio del tramo si el texto lo identifica —tenga o no el límite
    superior—. Si no es un tramo (algún filing declara un importe exacto), el
    `amount_mid` de la fuente, que es con lo que se guardaron las operaciones
    que ya hay: cambiarlo haría que la siguiente pasada las duplicara. La cifra
    del texto, sólo cuando la fuente no trae otra.
    """
    match = _NUMBER.search(str(raw_amount or ""))
    value = float(match.group(1).replace(",", "")) if match else None
    if value is not None and value.is_integer() and int(value) in BY_LOWER:
        return float(BY_LOWER[int(value)][2])
    try:
        if amount_mid is not None:
            return float(amount_mid)
    except (TypeError, ValueError):
        pass
    return value or 0.0


def bracket_for(amount: Any) -> Optional[tuple[int, Optional[int]]]:
    """Límites del tramo que representa un importe guardado, si lo es."""
    try:
        value = float(amount)
    except (TypeError, ValueError):
        return None
    if not value.is_integer():
        return None
    bracket = BY_MID.get(int(value))
    return (bracket[0], bracket[1]) if bracket else None


def short_money(value: float) -> str:
    """$1K, $15K, $1M: el formato de los límites de un tramo."""
    if value >= 1_000_000:
        millions = value / 1_000_000
        return f"${millions:,.0f}M" if millions.is_integer() else f"${millions:,.1f}M"
    if value >= 1_000:
        return f"${round(value / 1_000):,.0f}K"
    return f"${value:,.0f}"


def bracket_label(amount: Any) -> Optional[str]:
    """"$1K–$15K" para un punto medio de tramo; None si no lo es."""
    bracket = bracket_for(amount)
    if bracket is None:
        return None
    lower, upper = bracket
    if upper is None:
        return f">{short_money(lower - 1)}"
    return f"{short_money(lower - 1)}–{short_money(upper)}"


def volume_range(amounts: Any) -> Optional[dict[str, Any]]:
    """Horquilla real de un volumen sumado con puntos medios.

    El punto medio es sólo una convención para poder sumar: una operación de
    $1.001 cuenta como $8.000 y una de $14.999 también. La suma de los límites
    inferiores y superiores dice entre qué cifras está de verdad el volumen.
    `open_ended` indica que algún tramo no tiene techo (más de $50M).
    """
    lower = 0
    upper = 0
    open_ended = False
    counted = 0
    for amount in amounts:
        bracket = bracket_for(amount)
        if bracket is None:
            continue
        counted += 1
        lower += bracket[0]
        if bracket[1] is None:
            open_ended = True
        else:
            upper += bracket[1]
    if not counted:
        return None
    return {"min": lower, "max": None if open_ended else upper, "trades": counted}
