"""Router de perfil /users/me (Issue 17)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status

from ..deps import CurrentUser, DbSession
from ..schemas.usuario import PasswordChange, UserResponse, UserUpdate
from ..security import hash_password, verify_password

router = APIRouter(prefix="/users", tags=["users"])


@router.get(
    "/me",
    response_model=UserResponse,
    summary="Obtener perfil del usuario autenticado",
)
def get_me(current_user: CurrentUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


@router.patch(
    "/me",
    response_model=UserResponse,
    summary="Actualizar perfil (full_name, avatar_url, theme_preference)",
)
def patch_me(
    payload: UserUpdate,
    current_user: CurrentUser,
    db: DbSession,
) -> UserResponse:
    data = payload.model_dump(exclude_unset=True)

    if not data:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Nada para actualizar")

    for field in ("full_name", "avatar_url", "theme_preference"):
        if field in data:
            setattr(current_user, field, data[field])

    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.put(
    "/me/password",
    status_code=status.HTTP_200_OK,
    summary="Cambiar contraseña del usuario autenticado",
)
def change_password(
    payload: PasswordChange,
    current_user: CurrentUser,
    db: DbSession,
) -> dict[str, str]:
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La contraseña actual es incorrecta")

    if payload.current_password == payload.new_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="La nueva contraseña debe ser diferente")

    current_user.hashed_password = hash_password(payload.new_password)
    db.add(current_user)
    db.commit()
    return {"detail": "Contraseña actualizada correctamente"}
