"""Inicializacion automatica de tablas al arrancar la API."""

import logging
import os

from api.auth import hash_password

logger = logging.getLogger(__name__)

CORE_SCHEMA = """
CREATE TABLE IF NOT EXISTS proveedores (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE,
    contacto    TEXT,
    email       TEXT,
    telefono    TEXT,
    activo      BOOLEAN DEFAULT true,
    creado_en   TIMESTAMP DEFAULT now()
);

CREATE TABLE IF NOT EXISTS listas (
    id              SERIAL PRIMARY KEY,
    proveedor_id    INTEGER NOT NULL REFERENCES proveedores(id),
    archivo_nombre  TEXT NOT NULL,
    fecha_lista     DATE,
    total_registros INTEGER DEFAULT 0,
    subido_en       TIMESTAMP DEFAULT now(),
    subido_por      TEXT,
    activa          BOOLEAN DEFAULT true
);

CREATE TABLE IF NOT EXISTS partes (
    id              SERIAL PRIMARY KEY,
    lista_id        INTEGER NOT NULL REFERENCES listas(id) ON DELETE CASCADE,
    proveedor_id    INTEGER NOT NULL REFERENCES proveedores(id),
    referencia      TEXT NOT NULL,
    referencia_norm TEXT NOT NULL,
    equivalencia    TEXT DEFAULT '',
    descripcion     TEXT NOT NULL,
    vehiculo        TEXT DEFAULT '',
    marca_vehiculo  TEXT DEFAULT '',
    precio          NUMERIC(14,2) NOT NULL,
    precio_con_desc NUMERIC(14,2) NOT NULL,
    descuento_pct   NUMERIC(5,2) DEFAULT 0,
    moneda          CHAR(3) DEFAULT 'COP',
    fecha_lista     DATE,
    archivo_origen  TEXT,
    sheet_origen    TEXT,
    creado_en       TIMESTAMP DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_partes_ref_norm ON partes (referencia_norm);
CREATE INDEX IF NOT EXISTS idx_partes_proveedor ON partes (proveedor_id);
CREATE INDEX IF NOT EXISTS idx_partes_lista ON partes (lista_id);
"""

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

PROVEEDORES_INICIALES = (
    "DH Repuestos Corea",
    "DH Soportes",
    "Cajas de Dirección",
    "Lista Precio E",
)

ADMIN_EMAIL = "admin@preciopartes.com"
ADMIN_PASSWORD = os.getenv("ADMIN_INITIAL_PASSWORD", "admin123")
ADMIN_NOMBRE = "Administrador"


def is_system_admin(email: str) -> bool:
    return email.lower().strip() == ADMIN_EMAIL


async def ensure_admin_user(conn) -> None:
    """Crea o reactiva el usuario admin por defecto si falta o fue desactivado."""
    row = await conn.fetchrow(
        "SELECT id, activo, rol FROM users WHERE email = $1",
        ADMIN_EMAIL,
    )
    if not row:
        await conn.execute(
            """INSERT INTO users (nombre, email, password_hash, rol, activo)
               VALUES ($1, $2, $3, 'admin', true)""",
            ADMIN_NOMBRE,
            ADMIN_EMAIL,
            hash_password(ADMIN_PASSWORD),
        )
        logger.info("Usuario admin creado: %s", ADMIN_EMAIL)
        return

    if not row["activo"] or row["rol"] != "admin":
        await conn.execute(
            """UPDATE users
               SET activo = true, rol = 'admin', nombre = $2
               WHERE email = $1""",
            ADMIN_EMAIL,
            ADMIN_NOMBRE,
        )
        logger.info("Usuario admin restaurado: %s", ADMIN_EMAIL)


async def init_database(pool) -> None:
    """Crea tablas core (proveedores, listas, partes) + users si no existen."""
    async with pool.acquire() as conn:
        for ext in ("unaccent", "pg_trgm"):
            try:
                await conn.execute(f"CREATE EXTENSION IF NOT EXISTS {ext}")
            except Exception as e:
                logger.warning("Extension %s no disponible: %s", ext, e)

        await conn.execute(CORE_SCHEMA)

        for nombre in PROVEEDORES_INICIALES:
            await conn.execute(
                "INSERT INTO proveedores (nombre) VALUES ($1) ON CONFLICT (nombre) DO NOTHING",
                nombre,
            )

        await conn.execute(USERS_SCHEMA)

        await ensure_admin_user(conn)

        n_prov = await conn.fetchval("SELECT COUNT(*) FROM proveedores")
        n_users = await conn.fetchval("SELECT COUNT(*) FROM users")
        logger.info("DB OK: %s proveedores, %s usuarios", n_prov, n_users)


# Alias por compatibilidad
async def init_users_table(pool) -> None:
    await init_database(pool)
