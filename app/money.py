"""Importes, títulos y precios como `Decimal`, guardados en NUMERIC.

Con `Float` cada importe era un binario aproximado: 1234,56 se guardaba como
1234,5599999999999…, y la valoración multiplicaba esos restos por millones de
títulos. En Postgres —la base de producción— las columnas son NUMERIC con una
escala fija y en Python se opera con `Decimal`, que es lo que exige el dinero.

SQLite no tiene un tipo decimal propio: SQLAlchemy lo convertiría a coma
flotante avisando de que pierde precisión. Allí, que sólo es la base de
desarrollo, la columna sigue siendo REAL y el valor se redondea a la escala al
entrar y al salir, de modo que el código ve siempre el mismo `Decimal` en las
dos bases.
"""
from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Optional

from sqlalchemy import Float, Numeric
from sqlalchemy.types import TypeDecorator

# Escalas de cada magnitud. Los importes, al diezmilésimo como pide el estándar
# contable (NUMERIC(19,4)); los títulos admiten fracciones de reinversión de
# dividendos; los precios, los seis decimales de los valores de céntimos.
MONEY_PRECISION, MONEY_SCALE = 19, 4
SHARES_PRECISION, SHARES_SCALE = 24, 6
PRICE_PRECISION, PRICE_SCALE = 19, 6

ZERO = Decimal(0)
CENT = Decimal("0.01")


def to_decimal(value: Any, scale: Optional[int] = None) -> Optional[Decimal]:
    """Convierte cualquier cifra a `Decimal`; None si no es un número.

    Los float pasan por su representación decimal más corta (`str`), no por
    su binario: `Decimal(0.1)` arrastraría 55 decimales de ruido.
    """
    if value is None or isinstance(value, bool):
        return None
    try:
        number = value if isinstance(value, Decimal) else Decimal(str(value).strip().replace(",", ""))
    except (InvalidOperation, ValueError):
        return None
    if not number.is_finite():
        return None
    if scale is not None:
        number = number.quantize(Decimal(1).scaleb(-scale), rounding=ROUND_HALF_UP)
    return number


def money(value: Any) -> Decimal:
    """Importe al céntimo, que es como se declara y se compara."""
    return to_decimal(value, 2) or ZERO


class _Decimal(TypeDecorator):
    """NUMERIC(p, s) en Postgres; REAL en SQLite. `Decimal` en los dos."""

    impl = Numeric
    cache_ok = True
    precision = MONEY_PRECISION
    scale = MONEY_SCALE

    def __init__(self) -> None:
        super().__init__(self.precision, self.scale, asdecimal=True)

    def load_dialect_impl(self, dialect):
        if dialect.name == "sqlite":
            return dialect.type_descriptor(Float())
        return dialect.type_descriptor(Numeric(self.precision, self.scale, asdecimal=True))

    def process_bind_param(self, value, dialect):
        number = to_decimal(value, self.scale)
        if number is None:
            return None
        return float(number) if dialect.name == "sqlite" else number

    def process_result_value(self, value, dialect):
        return to_decimal(value, self.scale)

    @property
    def python_type(self):
        return Decimal


class Money(_Decimal):
    # SQLAlchemy lo exige en cada subclase, no lo hereda.
    cache_ok = True
    precision, scale = MONEY_PRECISION, MONEY_SCALE


class Shares(_Decimal):
    cache_ok = True
    precision, scale = SHARES_PRECISION, SHARES_SCALE


class Price(_Decimal):
    cache_ok = True
    precision, scale = PRICE_PRECISION, PRICE_SCALE
