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


class User(Base):
    """Cuenta de una persona que usa la web.

    No confundir con `Politician`: aquí viven los visitantes registrados, no los
    declarantes. El correo es el identificador, siempre guardado en minúsculas
    para que "Ana@ejemplo.com" y "ana@ejemplo.com" no sean dos cuentas.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    sessions: Mapped[list["UserSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    follows: Mapped[list["Follow"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class UserSession(Base):
    """Sesión abierta, con el token guardado como hash.

    En serverless no hay proceso vivo donde sostener las sesiones en memoria, así
    que viven en la base. Lo que se guarda es el SHA-256 del token, no el token:
    si alguien lee la tabla, no puede suplantar a nadie con lo que encuentre.

    La clase no puede llamarse `Session` porque ese nombre ya es el de la sesión
    de SQLAlchemy, que se importa en los mismos módulos que este.
    """

    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    # Acompaña a la cookie en los formularios ya autenticados. La cookie es
    # SameSite=Lax, que ya frena el POST desde otro sitio; esto cubre lo que esa
    # política deja fuera, como un subdominio comprometido.
    csrf_token: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped[User] = relationship(back_populates="sessions")


class Follow(Base):
    """Político al que un usuario sigue."""

    __tablename__ = "follows"
    __table_args__ = (
        UniqueConstraint("user_id", "politician_id", name="uq_follow_identity"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    politician_id: Mapped[int] = mapped_column(ForeignKey("politicians.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    user: Mapped[User] = relationship(back_populates="follows")
    politician: Mapped[Politician] = relationship()


class PriceQuote(Base):
    """Última cotización conocida de un valor, cacheada para no agotar la API."""

    __tablename__ = "price_quotes"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    symbol: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    currency: Mapped[str] = mapped_column(String(10), default="USD")
    previous_close: Mapped[float] = mapped_column(Float, default=0.0)
    fetched_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)


class LoginAttempt(Base):
    """Intento fallido de entrar o de darse de alta.

    El límite tiene que sobrevivir a la petición que lo cuenta, y en serverless
    no hay memoria compartida entre invocaciones donde llevar la cuenta: la
    lleva la base, como las sesiones.
    """

    __tablename__ = "login_attempts"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    # "login" o "signup": cada formulario tiene su propio cupo.
    scope: Mapped[str] = mapped_column(String(20), nullable=False)
    # Contra quién se cuenta. Hoy la dirección IP; el nombre no lo presupone
    # para poder añadir el correo como segunda cesta sin migrar la tabla.
    bucket: Mapped[str] = mapped_column(String(120), index=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, index=True, nullable=False)
