"""Cuentas y sesiones.

La aplicación se sirve desde una función serverless: nace y muere con cada
petición, así que no hay memoria donde sostener las sesiones. Viven en la base,
identificadas por un token aleatorio que sólo existe en la cookie del navegador;
la tabla guarda su hash. Así no hace falta ninguna clave secreta que configurar
en el despliegue, y cerrar sesión borra la fila de verdad, cosa que un token
autofirmado no permite.

Aquí está la lógica; las rutas viven en `app.main`, como el resto.
"""

from __future__ import annotations

import hashlib
import re
import secrets
from datetime import timedelta
from typing import Optional

import bcrypt
from fastapi import Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Follow, User, UserSession
from app.runtime import utcnow
from app.security import is_https

__all__ = ["utcnow"]  # se sigue llamando auth.utcnow desde el resto del proyecto

SESSION_COOKIE = "twf_session"
SESSION_DAYS = 30

# bcrypt sólo mira los primeros 72 bytes y desde la versión 4 se niega a
# procesar más, en vez de recortar por lo bajo sin avisar.
MAX_PASSWORD_BYTES = 72
MIN_PASSWORD_LENGTH = 8

# No valida direcciones de correo —eso sólo lo hace enviando un mensaje—, sólo
# descarta lo que es evidente que no es una: sin arroba, sin punto, con espacios.
EMAIL_PATTERN = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


# --- Contraseñas -----------------------------------------------------------


def hash_password(raw: str) -> str:
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(raw: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(raw.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        # Hash con formato que bcrypt no reconoce, o contraseña de más de 72
        # bytes: en ninguno de los dos casos hay coincidencia posible.
        return False


def normalise_email(raw: str) -> str:
    return (raw or "").strip().lower()


def credential_errors(email: str, password: str, t: dict) -> list[str]:
    """Problemas del formulario, en el idioma activo.

    Devuelve una lista en vez de lanzar: el formulario los pinta todos juntos y
    quien se registra corrige de una vez, no de uno en uno.
    """
    errors = []
    if not EMAIL_PATTERN.match(normalise_email(email)):
        errors.append(t["auth_error_email"])
    if len(password) < MIN_PASSWORD_LENGTH:
        errors.append(t["auth_error_short"])
    elif len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        errors.append(t["auth_error_long"])
    return errors


# --- Sesiones --------------------------------------------------------------


def token_fingerprint(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> str:
    """Abre sesión y devuelve el token en claro, que no vuelve a estar disponible."""
    raw_token = secrets.token_urlsafe(32)
    now = utcnow()
    db.add(
        UserSession(
            token_hash=token_fingerprint(raw_token),
            user_id=user.id,
            csrf_token=secrets.token_urlsafe(24),
            created_at=now,
            expires_at=now + timedelta(days=SESSION_DAYS),
        )
    )
    db.commit()
    return raw_token


def resolve_session(db: Session, raw_token: Optional[str]) -> Optional[UserSession]:
    if not raw_token:
        return None

    session = db.scalar(
        select(UserSession).where(UserSession.token_hash == token_fingerprint(raw_token))
    )
    if session is None:
        return None

    if session.expires_at <= utcnow():
        # Caducada: se retira ahora, que es cuando se sabe, en lugar de dejar
        # basura en la tabla esperando una limpieza que nadie ejecuta.
        db.delete(session)
        db.commit()
        return None

    return session


def destroy_session(db: Session, raw_token: Optional[str]) -> None:
    session = resolve_session(db, raw_token)
    if session is not None:
        db.delete(session)
        db.commit()


# --- Dependencias ----------------------------------------------------------


def current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    """Usuario de la petición, o None si entra sin sesión.

    Depende de `get_db`, así que reutiliza la sesión de base que ya abrió la
    petición: con NullPool, resolverlo por su cuenta significaría una conexión
    nueva contra Postgres en cada carga de página.
    """
    session = resolve_session(db, request.cookies.get(SESSION_COOKIE))
    if session is None:
        return None

    # Las plantillas necesitan el testigo para los formularios, y `render` sólo
    # recibe la petición; dejarlo aquí evita arrastrarlo por todas las rutas.
    request.state.csrf_token = session.csrf_token
    return session.user


def require_user(user: Optional[User] = Depends(current_user)) -> User:
    if user is None:
        # 303 con Location: la página protegida no existe para quien no ha
        # entrado, y el navegador sigue la redirección al formulario.
        raise HTTPException(status_code=303, headers={"Location": "/login"})
    return user


def check_csrf(request: Request, submitted: str) -> None:
    """Contrasta el testigo del formulario con el de la sesión.

    La cookie es SameSite=Lax, así que un POST lanzado desde otro sitio ni
    siquiera la lleva. Esto cubre lo que esa política deja fuera.
    """
    expected = getattr(request.state, "csrf_token", "")
    if not expected or not secrets.compare_digest(expected, submitted or ""):
        raise HTTPException(status_code=403, detail="Invalid CSRF token")


# --- Cookie ----------------------------------------------------------------


def set_session_cookie(response, raw_token: str, request: Request) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        raw_token,
        max_age=SESSION_DAYS * 24 * 60 * 60,
        httponly=True,
        # Se decide por cómo llegó la petición y no por dónde está desplegada
        # la app: en local la web se sirve por http, donde una cookie Secure se
        # descarta sin más y nadie conseguiría entrar; en cualquier despliegue
        # con TLS —serverless o contenedor detrás de un proxy— tiene que viajar.
        secure=is_https(request),
        samesite="lax",
    )


def clear_session_cookie(response, request: Request) -> None:
    # Los atributos tienen que coincidir con los que se pusieron, o hay
    # navegadores que se quedan la cookie.
    response.delete_cookie(
        SESSION_COOKIE, httponly=True, samesite="lax", secure=is_https(request)
    )


# --- Seguimiento -----------------------------------------------------------


def is_following(db: Session, user: Optional[User], politician_id: int) -> bool:
    if user is None:
        return False
    return (
        db.scalar(
            select(Follow.id).where(
                Follow.user_id == user.id, Follow.politician_id == politician_id
            )
        )
        is not None
    )


def follow(db: Session, user: User, politician_id: int) -> None:
    if is_following(db, user, politician_id):
        return
    db.add(Follow(user_id=user.id, politician_id=politician_id, created_at=utcnow()))
    db.commit()


def unfollow(db: Session, user: User, politician_id: int) -> None:
    session_follow = db.scalar(
        select(Follow).where(Follow.user_id == user.id, Follow.politician_id == politician_id)
    )
    if session_follow is not None:
        db.delete(session_follow)
        db.commit()
