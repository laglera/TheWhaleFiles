from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
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

    trades: Mapped[list["Trade"]] = relationship(back_populates="politician")


class Ticker(Base):
    __tablename__ = "tickers"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)

    trades: Mapped[list["Trade"]] = relationship(back_populates="ticker")


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
