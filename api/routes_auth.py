"""Rutas de autenticación y gestión de usuarios."""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr

from .auth import (
    ROLES,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from .deps import get_current_user, require_roles

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    email: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    nombre: str
    email: str
    rol: str
    activo: bool


class UserCreate(BaseModel):
    nombre: str
    email: EmailStr
    password: str
    rol: str = "consulta"


class UserUpdate(BaseModel):
    nombre: Optional[str] = None
    email: Optional[EmailStr] = None
    password: Optional[str] = None
    rol: Optional[str] = None
    activo: Optional[bool] = None


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, request: Request):
    async with request.app.state.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, password_hash, rol, activo FROM users WHERE email = $1",
            body.email.lower().strip(),
        )

    if not row or not row["activo"]:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    if not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Credenciales inválidas")

    return TokenResponse(
        access_token=create_access_token(row["id"], row["email"], row["rol"]),
        refresh_token=create_refresh_token(row["id"]),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh(body: RefreshRequest, request: Request):
    payload = decode_token(body.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=401, detail="Refresh token inválido")

    user_id = int(payload["sub"])
    async with request.app.state.pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT id, email, rol, activo FROM users WHERE id = $1",
            user_id,
        )

    if not row or not row["activo"]:
        raise HTTPException(status_code=401, detail="Usuario no encontrado o inactivo")

    return TokenResponse(
        access_token=create_access_token(row["id"], row["email"], row["rol"]),
        refresh_token=create_refresh_token(row["id"]),
    )


@router.get("/me", response_model=UserResponse)
async def me(user: dict = Depends(get_current_user)):
    return UserResponse(**user)


@router.get("/users", response_model=List[UserResponse])
async def list_users(
    request: Request,
    _: dict = Depends(require_roles("admin")),
):
    async with request.app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, nombre, email, rol, activo FROM users ORDER BY nombre"
        )
    return [UserResponse(**dict(r)) for r in rows]


@router.post("/users", response_model=UserResponse, status_code=201)
async def create_user(
    body: UserCreate,
    request: Request,
    _: dict = Depends(require_roles("admin")),
):
    if body.rol not in ROLES:
        raise HTTPException(status_code=400, detail=f"Rol inválido. Usar: {', '.join(ROLES)}")

    pw_hash = hash_password(body.password)
    try:
        async with request.app.state.pool.acquire() as conn:
            row = await conn.fetchrow(
                """INSERT INTO users (nombre, email, password_hash, rol)
                   VALUES ($1, $2, $3, $4)
                   RETURNING id, nombre, email, rol, activo""",
                body.nombre,
                body.email.lower().strip(),
                pw_hash,
                body.rol,
            )
    except Exception:
        raise HTTPException(status_code=409, detail="El email ya está registrado")

    return UserResponse(**dict(row))


@router.put("/users/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UserUpdate,
    request: Request,
    current: dict = Depends(require_roles("admin")),
):
    if body.rol and body.rol not in ROLES:
        raise HTTPException(status_code=400, detail=f"Rol inválido. Usar: {', '.join(ROLES)}")

    fields = []
    params = []
    idx = 1

    for field, value in [
        ("nombre", body.nombre),
        ("email", body.email.lower().strip() if body.email else None),
        ("rol", body.rol),
        ("activo", body.activo),
    ]:
        if value is not None:
            fields.append(f"{field} = ${idx}")
            params.append(value)
            idx += 1

    if body.password:
        fields.append(f"password_hash = ${idx}")
        params.append(hash_password(body.password))
        idx += 1

    if not fields:
        raise HTTPException(status_code=400, detail="Nada que actualizar")

    params.append(user_id)
    query = f"""
        UPDATE users SET {', '.join(fields)}
        WHERE id = ${idx}
        RETURNING id, nombre, email, rol, activo
    """

    async with request.app.state.pool.acquire() as conn:
        row = await conn.fetchrow(query, *params)

    if not row:
        raise HTTPException(status_code=404, detail="Usuario no encontrado")

    return UserResponse(**dict(row))
