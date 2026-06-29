"""Inicializacion automatica de tablas al arrancar la API."""

import logging

from api.auth import hash_password

logger = logging.getLogger(__name__)

USERS_SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    id            SERIAL PRIMARY KEY,
    nombre        TEXT NOT NULL,
    email         TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    rol           TEXT NOT NULL DEFAULT 'consulta'
                  CHECK (rol IN ('admin', 'vendedor', 'consulta')),
    activo        BOOLEAN DEFAULT true,
    creado_en     TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_users_email ON users (email);
"""

ADMIN_EMAIL = "admin@preciopartes.com"
ADMIN_PASSWORD = "admin123"
ADMIN_NOMBRE = "Administrador"


async def init_users_table(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(USERS_SCHEMA)

        exists = await conn.fetchval(
            "SELECT 1 FROM users WHERE email = $1", ADMIN_EMAIL
        )
        if not exists:
            await conn.execute(
                """INSERT INTO users (nombre, email, password_hash, rol)
                   VALUES ($1, $2, $3, 'admin')""",
                ADMIN_NOMBRE,
                ADMIN_EMAIL,
                hash_password(ADMIN_PASSWORD),
            )
            logger.info("Usuario admin creado: %s", ADMIN_EMAIL)
        else:
            logger.info("Tabla users OK")
