from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, DeclarativeBase, mapped_column, relationship

from app.money import ZERO, Money, Price, Shares


class Base(DeclarativeBase):
    pass


class Politician(Base):
    __tablename__ = "politicians"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Para los insiders corporativos, chamber guarda el cargo y state la empresa.
    chamber: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(80), nullable=False)
    party: Mapped[str] = mapped_column(String(60), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(20), nullable=False, default="congress")
    # CIK personal en EDGAR, sólo para los directivos. Identifica a la persona
    # mejor que el nombre, que EDGAR escribe a su manera ("Jen Hsun Huang").
    cik: Mapped[Optional[str]] = mapped_column(String(10), nullable=True, index=True)

    # Perfil biográfico traído de Wikipedia. Se guarda en los dos idiomas de la
    # interfaz y con la URL de origen, que la licencia CC BY-SA obliga a citar.
    bio_es: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bio_en: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bio_headline_es: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bio_headline_en: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    bio_source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    # Retrato de Wikimedia Commons, con los datos que exige su licencia.
    photo_remote_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    photo_author: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    photo_license: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    photo_source_url: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)

    profile_fetched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    trades: Mapped[list["Trade"]] = relationship(back_populates="politician")
    holdings: Mapped[list["Holding"]] = relationship(
        back_populates="politician", cascade="all, delete-orphan"
    )
    derivatives: Mapped[list["DerivativeHolding"]] = relationship(
        back_populates="politician", cascade="all, delete-orphan"
    )


class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    trades: Mapped[list["Trade"]] = relationship(back_populates="ticker")
    holdings: Mapped[list["Holding"]] = relationship(back_populates="ticker")


class Trade(Base):
    __tablename__ = "trades"
    # Una operación declarada queda identificada por quién, qué, cómo, cuánto y
    # cuándo. Sin esto, cada pasada del polling reinsertaría el dataset entero.
    #
    # Las dos fechas entran en la identidad porque un mismo filing puede
    # declarar dos compras iguales del mismo valor ejecutadas en días
    # distintos: sin la fecha de operación, la segunda se descartaría como
    # duplicada. Cuando la fuente no da fecha de operación la columna queda a
    # NULL y el índice deja de proteger esas filas —dos NULL no colisionan en
    # SQL—, así que el filtro que de verdad evita duplicados es el de
    # `load_trade_records_into_db`, que compara en memoria.
    __table_args__ = (
        UniqueConstraint(
            "politician_id",
            "ticker_id",
            "trade_type",
            "amount",
            "reported_date",
            "transaction_date",
            name="uq_trade_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), nullable=False)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("tickers.id"), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(30), nullable=False)
    # NUMERIC(19,4) en Postgres y `Decimal` en Python: ver app/money.py.
    amount: Mapped[Decimal] = mapped_column(Money, nullable=False, default=ZERO)
    # Fecha en que el filing se hizo público. Es la que ordena la web: lo que
    # esta plataforma mide es cuándo se pudo saber, no cuándo se operó.
    reported_date: Mapped[date] = mapped_column(Date, nullable=False)
    # Fecha en que se ejecutó la operación, según el propio filing. Nula cuando
    # la fuente no la trae o cuando el dato es imposible (posterior a su propia
    # publicación): antes que enseñar una fecha falsa, no se enseña ninguna.
    transaction_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(String(500), default="")

    politician: Mapped[Politician] = relationship(back_populates="trades")
    ticker: Mapped[Ticker] = relationship(back_populates="trades")


class Holding(Base):
    """Acciones que una persona posee de una empresa, en una fecha concreta.

    Solo se puede rellenar para insiders corporativos: el Form 4 de la SEC
    declara `sharesOwnedFollowingTransaction`, el número exacto de títulos que
    quedan en manos del declarante. Los PTR del Congreso no declaran ni
    posiciones ni número de acciones, así que los políticos no tienen holdings.
    """

    __tablename__ = "holdings"
    __table_args__ = (
        UniqueConstraint("politician_id", "ticker_id", name="uq_holding_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), nullable=False)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("tickers.id"), nullable=False)
    shares: Mapped[Decimal] = mapped_column(Shares, nullable=False, default=ZERO)
    # La parte de `shares` que no está a su nombre sino en trusts, sociedades o
    # fundaciones. Se suma en el total —el Form 4 la declara como suya—, pero
    # la ficha la enseña aparte: no es lo mismo controlar que poseer.
    shares_indirect: Mapped[Decimal] = mapped_column(Shares, nullable=False, default=ZERO)
    # Fecha de la operación que dejó esta posición: mide cómo de viejo es el dato.
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="SEC Form 4")

    politician: Mapped[Politician] = relationship(back_populates="holdings")
    ticker: Mapped[Ticker] = relationship(back_populates="holdings")


class DerivativeHolding(Base):
    """Opciones, warrants, convertibles y demás derechos sobre acciones.

    La tabla II del Form 4. Sin ella, un directivo con un millón de opciones
    dentro del dinero —o Zuckerberg, cuya clase B convertible está toda aquí—
    aparecía muy por debajo de lo que de verdad tiene. Se guarda en cuántas
    acciones del subyacente se traduce cada línea y a qué precio, para
    valorarla por su valor intrínseco.
    """

    __tablename__ = "derivative_holdings"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), nullable=False)
    # El valor subyacente: lo que se recibe al ejercer o convertir.
    ticker_id: Mapped[int] = mapped_column(ForeignKey("tickers.id"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    underlying_shares: Mapped[Decimal] = mapped_column(Shares, nullable=False, default=ZERO)
    # Nulo en las convertibles sin precio de conversión: se reciben gratis.
    exercise_price: Mapped[Optional[Decimal]] = mapped_column(Price, nullable=True)
    expiration: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="SEC Form 4")

    politician: Mapped[Politician] = relationship(back_populates="derivatives")
    ticker: Mapped[Ticker] = relationship()


class PriceQuote(Base):
    """Última cotización conocida de un valor, cacheada para no agotar la API."""

    __tablename__ = "price_quotes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    price: Mapped[Decimal] = mapped_column(Price, nullable=False, default=ZERO)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    previous_close: Mapped[Decimal] = mapped_column(Price, default=ZERO)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class PriceHistory(Base):
    """Cierres diarios ajustados de un valor, en una sola fila.

    Ajustados por splits y dividendos: la rentabilidad que se calcula con
    ellos es la total, la de quien hubiera cobrado y reinvertido. Se guardan
    comprimidos en JSON —una fila por valor y no una por día— porque son
    cientos de valores y años de sesiones: como filas sueltas serían cerca de
    un millón en un Postgres gratuito.
    """

    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    # {"d": ["2024-01-02", …], "c": ["187.15", …]}: fechas y cierres en texto,
    # para no pasar por coma flotante.
    closes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    first_day: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    last_day: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    # Cuándo se intentó por última vez, haya habido datos o no: los símbolos que
    # Yahoo no conoce no se reintentan antes que los demás.
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class CorporateAction(Base):
    """Splits y dividendos de un valor, según Yahoo Finance.

    Sirven para que una posición declarada antes de un split no se valore con
    los títulos de antes —tras el 10 por 1 de NVIDIA, un saldo de 2023 contado
    sin ajustar valía la décima parte— y para estimar los dividendos cobrados
    desde la fecha del saldo.
    """

    __tablename__ = "corporate_actions"
    __table_args__ = (UniqueConstraint("symbol", "day", "kind", name="uq_corporate_action"),)

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    day: Mapped[date] = mapped_column(Date, nullable=False)
    # "split" o "dividend".
    kind: Mapped[str] = mapped_column(String(10), nullable=False)
    # Títulos nuevos por cada título viejo (10 en un 10 por 1).
    ratio: Mapped[Optional[Decimal]] = mapped_column(Price, nullable=True)
    # Dividendo por acción, en la divisa de cotización.
    amount: Mapped[Optional[Decimal]] = mapped_column(Price, nullable=True)
