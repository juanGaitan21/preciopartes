"""Script para crear tabla users y usuario admin inicial."""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.auth import hash_password

DATABASE_URL = os.getenv(
    "DATABASE_URL", "postgresql://preciopartes:preciopartes@localhost:5432/preciopartes"
)

SCHEMA = """
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


async def main():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        await conn.execute(SCHEMA)
        admin_hash = hash_password("admin123")
        await conn.execute(
            """
            INSERT INTO users (nombre, email, password_hash, rol, activo)
            VALUES ($1, $2, $3, 'admin', true)
            ON CONFLICT (email) DO UPDATE SET
                activo = true,
                rol = 'admin',
                nombre = EXCLUDED.nombre
            """,
            "Administrador",
            "admin@preciopartes.com",
            admin_hash,
        )
        count = await conn.fetchval("SELECT COUNT(*) FROM users")
        admin = await conn.fetchrow(
            "SELECT email, activo, rol FROM users WHERE email = $1",
            "admin@preciopartes.com",
        )
        print(f"✅ Admin restaurado: {admin['email']} (activo={admin['activo']}, rol={admin['rol']})")
        print(f"   Contraseña: admin123")
        print(f"   Total usuarios: {count}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
