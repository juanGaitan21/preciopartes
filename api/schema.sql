-- PrecioPartes — Schema PostgreSQL
-- Ejecutar una sola vez al crear la base de datos

-- Extensión para búsqueda de texto en español
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- búsqueda difusa (fuzzy search)

-- -------------------------------------------------------
-- Proveedores
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS proveedores (
    id          SERIAL PRIMARY KEY,
    nombre      TEXT NOT NULL UNIQUE,
    contacto    TEXT,
    email       TEXT,
    telefono    TEXT,
    activo      BOOLEAN DEFAULT true,
    creado_en   TIMESTAMP DEFAULT now()
);

-- -------------------------------------------------------
-- Listas (cada archivo que se sube = una lista)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS listas (
    id              SERIAL PRIMARY KEY,
    proveedor_id    INTEGER NOT NULL REFERENCES proveedores(id),
    archivo_nombre  TEXT NOT NULL,
    fecha_lista     DATE,
    total_registros INTEGER DEFAULT 0,
    subido_en       TIMESTAMP DEFAULT now(),
    subido_por      TEXT,        -- usuario que subió el archivo
    activa          BOOLEAN DEFAULT true  -- false = lista antigua reemplazada
);

-- -------------------------------------------------------
-- Partes (repuestos normalizados)
-- -------------------------------------------------------
CREATE TABLE IF NOT EXISTS partes (
    id              SERIAL PRIMARY KEY,
    lista_id        INTEGER NOT NULL REFERENCES listas(id) ON DELETE CASCADE,
    proveedor_id    INTEGER NOT NULL REFERENCES proveedores(id),

    -- Identificación del repuesto
    referencia      TEXT NOT NULL,          -- tal como viene en el Excel
    referencia_norm TEXT NOT NULL,          -- normalizado para búsqueda cruzada
    equivalencia    TEXT DEFAULT '',        -- código alternativo

    -- Descripción
    descripcion     TEXT NOT NULL,
    vehiculo        TEXT DEFAULT '',
    marca_vehiculo  TEXT DEFAULT '',

    -- Precio
    precio          NUMERIC(14,2) NOT NULL,
    precio_con_desc NUMERIC(14,2) NOT NULL, -- precio aplicando descuento
    descuento_pct   NUMERIC(5,2) DEFAULT 0,
    moneda          CHAR(3) DEFAULT 'COP',

    -- Trazabilidad
    fecha_lista     DATE,
    archivo_origen  TEXT,
    sheet_origen    TEXT,
    creado_en       TIMESTAMP DEFAULT now()
);

-- -------------------------------------------------------
-- Índices para búsqueda rápida
-- -------------------------------------------------------

-- Búsqueda exacta por referencia normalizada (join entre proveedores)
CREATE INDEX IF NOT EXISTS idx_partes_ref_norm
    ON partes (referencia_norm);

-- Búsqueda de texto completo en descripción (español)
CREATE INDEX IF NOT EXISTS idx_partes_desc_fts
    ON partes USING gin (
        to_tsvector('spanish', unaccent(descripcion))
    );

-- Búsqueda difusa en descripción (LIKE %...%)
CREATE INDEX IF NOT EXISTS idx_partes_desc_trgm
    ON partes USING gin (descripcion gin_trgm_ops);

-- Búsqueda por vehículo
CREATE INDEX IF NOT EXISTS idx_partes_vehiculo
    ON partes USING gin (vehiculo gin_trgm_ops);

-- Filtrar por proveedor y lista activa
CREATE INDEX IF NOT EXISTS idx_partes_proveedor
    ON partes (proveedor_id);

CREATE INDEX IF NOT EXISTS idx_partes_lista
    ON partes (lista_id);

-- -------------------------------------------------------
-- Vista: comparador de precios (el core del negocio)
-- -------------------------------------------------------
CREATE OR REPLACE VIEW v_comparador AS
SELECT
    p.referencia_norm,
    p.descripcion,
    p.vehiculo,
    p.precio,
    p.precio_con_desc,
    p.descuento_pct,
    p.referencia,
    p.equivalencia,
    p.fecha_lista,
    pr.nombre          AS proveedor,
    pr.id              AS proveedor_id,
    -- Ranking por precio dentro del mismo repuesto
    RANK() OVER (
        PARTITION BY p.referencia_norm
        ORDER BY p.precio_con_desc ASC
    ) AS rank_precio,
    -- Precio mínimo del grupo
    MIN(p.precio_con_desc) OVER (
        PARTITION BY p.referencia_norm
    ) AS precio_minimo,
    -- Diferencia vs mínimo
    p.precio_con_desc - MIN(p.precio_con_desc) OVER (
        PARTITION BY p.referencia_norm
    ) AS diferencia_vs_minimo,
    -- % más caro que el mínimo
    ROUND(
        (p.precio_con_desc - MIN(p.precio_con_desc) OVER (PARTITION BY p.referencia_norm))
        / NULLIF(MIN(p.precio_con_desc) OVER (PARTITION BY p.referencia_norm), 0) * 100,
        1
    ) AS pct_sobre_minimo
FROM partes p
JOIN proveedores pr ON pr.id = p.proveedor_id
JOIN listas l ON l.id = p.lista_id
WHERE l.activa = true AND pr.activo = true;

-- -------------------------------------------------------
-- Datos iniciales de proveedores
-- -------------------------------------------------------
INSERT INTO proveedores (nombre) VALUES
    ('DH Repuestos Corea'),
    ('DH Soportes'),
    ('Cajas de Dirección'),
    ('Lista Precio E')
ON CONFLICT (nombre) DO NOTHING;

-- -------------------------------------------------------
-- Usuarios (autenticación JWT)
-- -------------------------------------------------------
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

-- Usuario admin inicial (contraseña: admin123 — cambiar en producción)
INSERT INTO users (nombre, email, password_hash, rol) VALUES
    ('Administrador', 'admin@preciopartes.com',
     '$2b$12$1QhyuKwyv.KMQTK5F84Jd.D0t6PwGY3dTtUUeCGDYGZJJBrhtz48S', 'admin')
ON CONFLICT (email) DO NOTHING;
