"""Router de autenticacion: registro, login y ruta protegida /me."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from typing import Annotated

from fastapi import Depends

from ..deps import CurrentUser, DbSession
from ..models import Usuario
from ..schemas import Token, UsuarioCreate, UsuarioLogin, UsuarioRead
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


# --- Helpers ---------------------------------------------------------------

def _autenticar(db, email: str, password: str) -> Usuario:
    """Valida credenciales y devuelve el Usuario, o levanta 401."""
    usuario = db.execute(select(Usuario).where(Usuario.email == email)).scalar_one_or_none()

    # Comparacion generica para no filtrar si el email existe o no
    # (evita user-enumeration attacks).
    if usuario is None or not verify_password(password, usuario.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales invalidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return usuario


# --- Endpoints -------------------------------------------------------------

@router.post(
    "/registro",
    response_model=UsuarioRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo usuario",
)
def registro(payload: UsuarioCreate, db: DbSession) -> Usuario:
    """Crea un usuario nuevo si el email no esta tomado."""
    # Chequeo previo — mas amigable que atrapar el IntegrityError.
    existe = db.execute(select(Usuario.id).where(Usuario.email == payload.email)).first()
    if existe is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya esta registrado",
        )

    usuario = Usuario(
        email=payload.email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError as exc:
        # Race condition: otro request registro el mismo email entre el SELECT y el COMMIT.
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El email ya esta registrado",
        ) from exc

    db.refresh(usuario)
    return usuario


@router.post(
    "/login",
    response_model=Token,
    summary="Login con JSON (email + password)",
)
def login(payload: UsuarioLogin, db: DbSession) -> Token:
    """Login para clientes que envian JSON."""
    usuario = _autenticar(db, payload.email, payload.password)
    return Token(access_token=create_access_token(subject=usuario.id))


@router.post(
    "/login/form",
    response_model=Token,
    summary="Login OAuth2 (form-urlencoded) — util para Swagger 'Authorize'",
)
def login_form(
    form: Annotated[OAuth2PasswordRequestForm, Depends()],
    db: DbSession,
) -> Token:
    """Login compatible con `OAuth2PasswordRequestForm` de FastAPI.

    Usa `username` (que en este dominio es el email) y `password` como
    `application/x-www-form-urlencoded`.
    """
    usuario = _autenticar(db, form.username, form.password)
    return Token(access_token=create_access_token(subject=usuario.id))


@router.get(
    "/me",
    response_model=UsuarioRead,
    summary="Datos del usuario autenticado (requiere Bearer token)",
)
def me(current_user: CurrentUser) -> Usuario:
    """Ruta protegida de prueba: retorna el usuario del token."""
    return current_user
