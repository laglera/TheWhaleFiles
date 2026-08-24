from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Float, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, DeclarativeBase, mapped_column, relationship


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
    __table_args__ = (
        UniqueConstraint(
            "politician_id",
            "ticker_id",
            "trade_type",
            "amount",
            "reported_date",
            name="uq_trade_identity",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), nullable=False)
    ticker_id: Mapped[int] = mapped_column(ForeignKey("tickers.id"), nullable=False)
    trade_type: Mapped[str] = mapped_column(String(30), nullable=False)
    amount: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    reported_date: Mapped[date] = mapped_column(Date, nullable=False)
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
    shares: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    # Fecha de la operación que dejó esta posición: mide cómo de viejo es el dato.
    as_of: Mapped[date] = mapped_column(Date, nullable=False)
    source: Mapped[str] = mapped_column(String(120), default="SEC Form 4")

    politician: Mapped[Politician] = relationship(back_populates="holdings")
    ticker: Mapped[Ticker] = relationship(back_populates="holdings")


class PriceQuote(Base):
    """Última cotización conocida de un valor, cacheada para no agotar la API."""

    __tablename__ = "price_quotes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    previous_close: Mapped[float] = mapped_column(Float, default=0.0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
