"""Dependencias FastAPI: usuario autenticado y control de roles."""

from typing import Callable, List

from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth import decode_token, has_permission

security = HTTPBearer(auto_error=False)


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> dict:
    if not credentials:
        raise HTTPException(status_code=401, detail="Token requerido")

    payload = decode_token(credentials.credentials)
    if not payload or payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Token inválido o expirado")

    user_id = int(payload["sub"])
    async with request.app.state.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, nombre, email, rol, activo FROM users WHERE id = $1",
            user_id,
        )

    if not row or not row["activo"]:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")

    return dict(row)


def require_roles(*roles: str) -> Callable:
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user["rol"] not in roles:
            raise HTTPException(status_code=403, detail="No tienes permiso para esta acción")
        return user

    return checker


def require_permission(permission: str) -> Callable:
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if not has_permission(user["rol"], permission):
            raise HTTPException(status_code=403, detail="No tienes permiso para esta acción")
        return user

    return checker
