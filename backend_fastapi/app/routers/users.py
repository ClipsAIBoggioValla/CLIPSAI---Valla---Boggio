"""Router de perfil /users/me (Issue 17)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy import select

from ..deps import CurrentUser, DbSession
from ..models import Usuario
from ..schemas.usuario import PasswordChange, UserResponse, UserUpdate, UserUpdateSimple
from ..core.session import set_session_cookie
from ..security import create_access_token, hash_password, verify_password

router = APIRouter(tags=["users"])


def _to_user_response(user: Usuario) -> UserResponse:
    data = {
        "id": user.id,
        "email": user.email,
        "full_name": user.full_name,
        "name": user.full_name,
        "avatar_url": getattr(user, "avatar_url", None),
        "theme_preference": getattr(user, "theme_preference", "dark") or "dark",
        "is_admin": bool(getattr(user, "is_admin", False)),
        "created_at": user.created_at,
    }
    return UserResponse.model_validate(data)


@router.get("/users/me", response_model=UserResponse, summary="Obtener perfil del usuario autenticado")
@router.get("/users/me/", response_model=UserResponse, include_in_schema=False)
@router.get("/me", response_model=UserResponse, include_in_schema=False)
@router.get("/me/", response_model=UserResponse, include_in_schema=False)
def get_me(current_user: CurrentUser) -> UserResponse:
    return _to_user_response(current_user)


def _actualizar_email(current_user: Usuario, payload: dict, db: DbSession) -> None:
    """Cambia el email si viene en el payload, validando disponibilidad."""
    if "email" not in payload or payload["email"] is None:
        return
    new_email = payload["email"]
    exists = db.execute(select(Usuario.id).where(Usuario.email == new_email).where(Usuario.id != current_user.id)).first()
    if exists is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El email ya está registrado")
    current_user.email = new_email


def _actualizar_nombre(current_user: Usuario, payload: dict) -> None:
    """Cambia el nombre si viene por full_name o nombre."""
    if "full_name" in payload or ("nombre" in payload and payload["nombre"] is not None):
        current_user.full_name = payload.get("full_name", payload.get("nombre"))


def _actualizar_avatar(current_user: Usuario, payload: dict) -> None:
    """Cambia el avatar si el modelo lo soporta y viene en el payload."""
    if "avatar_url" in payload and hasattr(current_user, "avatar_url"):
        setattr(current_user, "avatar_url", payload["avatar_url"])


def _actualizar_tema(current_user: Usuario, payload: dict) -> None:
    """Cambia el tema si el modelo lo soporta y viene un valor no nulo."""
    if "theme_preference" in payload and hasattr(current_user, "theme_preference") and payload["theme_preference"] is not None:
        setattr(current_user, "theme_preference", payload["theme_preference"])


def _apply_update(current_user: Usuario, payload: dict, db: DbSession) -> UserResponse:
    """Aplica el payload al usuario y devuelve la respuesta actualizada."""
    if not payload:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nada para actualizar")

    _actualizar_email(current_user, payload, db)
    _actualizar_nombre(current_user, payload)
    _actualizar_avatar(current_user, payload)
    _actualizar_tema(current_user, payload)

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return _to_user_response(current_user)


@router.put("/users/me", response_model=UserResponse, summary="Actualizar perfil (nombre y/o email)")
@router.put("/users/me/", response_model=UserResponse, include_in_schema=False)
@router.put("/me", response_model=UserResponse, include_in_schema=False)
@router.put("/me/", response_model=UserResponse, include_in_schema=False)
def put_me(payload: UserUpdateSimple, current_user: CurrentUser, db: DbSession) -> UserResponse:
    data = payload.model_dump(exclude_unset=True, by_alias=False)
    # Normalize alias handling: if nombre provided without full_name
    if "nombre" in data and data["nombre"] is not None and "full_name" not in data:
        data["full_name"] = data.pop("nombre")
    elif "nombre" in data:
        data.pop("nombre", None)
    # Remove None email if not provided? keep only set fields
    return _apply_update(current_user, data, db)


@router.patch("/me", response_model=UserResponse, summary="Actualizar perfil (patch alias)")
@router.patch("/me/", response_model=UserResponse, include_in_schema=False)
def patch_me(payload: UserUpdate, current_user: CurrentUser, db: DbSession) -> UserResponse:
    data = payload.model_dump(exclude_unset=True)
    return _apply_update(current_user, data, db)


@router.post("/users/me/change-password", status_code=status.HTTP_200_OK, summary="Cambiar contraseña")
@router.post("/users/me/change-password/", status_code=status.HTTP_200_OK, include_in_schema=False)
@router.post("/me/change-password", status_code=status.HTTP_200_OK, include_in_schema=False)
@router.post("/me/change-password/", status_code=status.HTTP_200_OK, include_in_schema=False)
def change_password_post(payload: PasswordChange, current_user: CurrentUser, db: DbSession, response: Response) -> dict[str, str]:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual es incorrecta")
    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La nueva contraseña debe ser diferente")
    current_user.hashed_password = hash_password(payload.new_password)
    current_user.token_version = int(getattr(current_user, "token_version", 0) or 0) + 1
    db.add(current_user)
    db.commit()
    token = create_access_token(subject=current_user.id, token_version=current_user.token_version)
    set_session_cookie(response, token)
    return {"detail": "Contraseña actualizada correctamente"}


@router.put("/me/password", status_code=status.HTTP_200_OK, summary="Cambiar contraseña alias PUT")
@router.put("/me/password/", status_code=status.HTTP_200_OK, include_in_schema=False)
def change_password_put(payload: PasswordChange, current_user: CurrentUser, db: DbSession, response: Response) -> dict[str, str]:
    return change_password_post(payload, current_user, db, response)
