"""
PrecioPartes API — FastAPI
==========================
Endpoints:
    POST /api/listas/upload       — Sube un nuevo Excel, corre ETL, guarda en DB
    GET  /api/buscar              — Busca repuestos con comparación de precios
    GET  /api/proveedores         — Lista proveedores activos
    GET  /api/listas              — Historial de listas subidas
    DELETE /api/listas/{id}       — Desactiva una lista (no borra datos)
"""

import logging
import os
from datetime import date
from pathlib import Path
from typing import Optional

import asyncpg
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from api.deps import get_current_user, require_permission, require_roles
from api.db_init import init_users_table
from api.routes_auth import router as auth_router

# ETL propio
import sys
sys.path.append(str(Path(__file__).parent.parent / "etl"))
from etl import procesar_archivo, TIPO_DH, TIPO_CAJAS, TIPO_LISTA_E

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PrecioPartes API",
    description="Comparador de precios de repuestos automotrices",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://user:pass@localhost:5432/preciopartes")

# ---------------------------------------------------------------------------
# DB Pool
# ---------------------------------------------------------------------------

@app.on_event("startup")
async def startup():
    app.state.pool = await asyncpg.create_pool(DATABASE_URL, min_size=2, max_size=10)
    await init_users_table(app.state.pool)
    logger.info("DB pool creado")

@app.on_event("shutdown")
async def shutdown():
    await app.state.pool.close()


# ---------------------------------------------------------------------------
# Modelos de respuesta
# ---------------------------------------------------------------------------

class ResultadoBusqueda(BaseModel):
    referencia: str
    referencia_norm: str
    descripcion: str
    vehiculo: str
    precio: float
    precio_con_desc: float
    descuento_pct: float
    proveedor: str
    proveedor_id: int
    rank_precio: int
    precio_minimo: float
    diferencia_vs_minimo: float
    pct_sobre_minimo: float
    fecha_lista: Optional[date]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {"status": "ok", "service": "preciopartes"}


@app.get("/api/buscar")
async def buscar(
    q: str,
    proveedor_id: Optional[int] = None,
    vehiculo: Optional[str] = None,
    solo_mas_baratos: bool = False,
    limit: int = 50,
    _: dict = Depends(require_permission("buscar")),
):
    """
    Busca repuestos por descripción, referencia o vehículo.
    Retorna resultados ordenados por precio (más barato primero).

    Parámetros:
        q               — Texto a buscar (descripción, referencia, vehículo)
        proveedor_id    — Filtrar por proveedor específico
        vehiculo        — Filtrar por vehículo (ej: "AVEO", "KIA")
        solo_mas_baratos — Si true, retorna solo el más barato por referencia
        limit           — Máximo de resultados (default 50)
    """
    if not q or len(q.strip()) < 2:
        raise HTTPException(status_code=400, detail="El término de búsqueda debe tener al menos 2 caracteres")

    terminos = q.strip().split()

    # Construir condición de búsqueda multi-término
    # Busca en: descripcion, referencia, referencia_norm, vehiculo
    condiciones_texto = []
    params = []
    idx = 1

    for termino in terminos:
        t = f"%{termino.upper()}%"
        condiciones_texto.append(f"""(
            upper(p.descripcion)     LIKE ${idx}
            OR upper(p.referencia)      LIKE ${idx}
            OR upper(p.referencia_norm) LIKE ${idx}
            OR upper(p.vehiculo)        LIKE ${idx}
            OR upper(pr.nombre)         LIKE ${idx}
        )""")
        params.append(t)
        idx += 1

    where = " AND ".join(condiciones_texto)

    # Filtros adicionales
    if proveedor_id:
        where += f" AND p.proveedor_id = ${idx}"
        params.append(proveedor_id)
        idx += 1

    if vehiculo:
        where += f" AND upper(p.vehiculo) LIKE ${idx}"
        params.append(f"%{vehiculo.upper()}%")
        idx += 1

    if solo_mas_baratos:
        # Solo el más barato por referencia normalizada
        query = f"""
            SELECT DISTINCT ON (p.referencia_norm)
                p.referencia,
                p.referencia_norm,
                p.descripcion,
                p.vehiculo,
                p.precio::float,
                p.precio_con_desc::float,
                p.descuento_pct::float,
                pr.nombre           AS proveedor,
                pr.id               AS proveedor_id,
                1                   AS rank_precio,
                p.precio_con_desc::float AS precio_minimo,
                0.0                 AS diferencia_vs_minimo,
                0.0                 AS pct_sobre_minimo,
                p.fecha_lista
            FROM partes p
            JOIN proveedores pr ON pr.id = p.proveedor_id
            JOIN listas l       ON l.id  = p.lista_id
            WHERE l.activa = true AND pr.activo = true
              AND {where}
            ORDER BY p.referencia_norm, p.precio_con_desc ASC
            LIMIT ${idx}
        """
    else:
        query = f"""
            SELECT
                p.referencia,
                p.referencia_norm,
                p.descripcion,
                p.vehiculo,
                p.precio::float,
                p.precio_con_desc::float,
                p.descuento_pct::float,
                pr.nombre           AS proveedor,
                pr.id               AS proveedor_id,
                RANK() OVER (
                    PARTITION BY p.referencia_norm
                    ORDER BY p.precio_con_desc ASC
                )::int              AS rank_precio,
                MIN(p.precio_con_desc) OVER (
                    PARTITION BY p.referencia_norm
                )::float            AS precio_minimo,
                (p.precio_con_desc - MIN(p.precio_con_desc) OVER (
                    PARTITION BY p.referencia_norm
                ))::float           AS diferencia_vs_minimo,
                ROUND(
                    (p.precio_con_desc - MIN(p.precio_con_desc) OVER (
                        PARTITION BY p.referencia_norm
                    )) / NULLIF(MIN(p.precio_con_desc) OVER (
                        PARTITION BY p.referencia_norm
                    ), 0) * 100, 1
                )::float            AS pct_sobre_minimo,
                p.fecha_lista
            FROM partes p
            JOIN proveedores pr ON pr.id = p.proveedor_id
            JOIN listas l       ON l.id  = p.lista_id
            WHERE l.activa = true AND pr.activo = true
              AND {where}
            ORDER BY p.precio_con_desc ASC
            LIMIT ${idx}
        """

    params.append(min(limit, 200))

    async with app.state.pool.acquire() as conn:
        try:
            rows = await conn.fetch(query, *params)
        except Exception as e:
            logger.error(f"Error en búsqueda: {e} | query: {query} | params: {params}")
            raise HTTPException(status_code=500, detail="Error interno de búsqueda")

    return {
        "total": len(rows),
        "termino": q,
        "resultados": [dict(r) for r in rows],
    }


@app.post("/api/listas/upload")
async def upload_lista(
    archivo: UploadFile = File(...),
    proveedor_id: int = Form(...),
    tipo: Optional[str] = Form(None),
    user: dict = Depends(require_permission("upload")),
):
    """
    Sube un nuevo Excel de lista de precios.
    - Corre el ETL automáticamente
    - Guarda todos los registros en la DB
    - Desactiva la lista anterior del mismo proveedor
    - Retorna resumen del proceso
    """
    subido_por = user["nombre"]
    ext = Path(archivo.filename).suffix.lower()
    if ext not in (".xls", ".xlsx"):
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .xls o .xlsx")

    # Guardar temporalmente
    tmp_path = Path(f"/tmp/{archivo.filename}")
    try:
        content = await archivo.read()
        tmp_path.write_bytes(content)

        # Correr ETL
        registros = procesar_archivo(
            path=tmp_path,
            proveedor_nombre=f"proveedor_{proveedor_id}",  # nombre se toma de DB
            tipo=tipo,
        )

        if not registros:
            raise HTTPException(
                status_code=422,
                detail="El archivo no contiene registros válidos. Verifica el formato."
            )

        # Guardar en DB dentro de una transacción
        async with app.state.pool.acquire() as conn:
            async with conn.transaction():
                # Desactivar listas anteriores del proveedor
                await conn.execute(
                    "UPDATE listas SET activa = false WHERE proveedor_id = $1",
                    proveedor_id
                )

                # Crear nueva lista
                fecha_lista = registros[0].get("fecha_lista")
                lista_id = await conn.fetchval(
                    """INSERT INTO listas (proveedor_id, archivo_nombre, fecha_lista, subido_por)
                       VALUES ($1, $2, $3, $4) RETURNING id""",
                    proveedor_id, archivo.filename, fecha_lista, subido_por
                )

                # Insertar registros en batch
                await conn.executemany(
                    """INSERT INTO partes
                        (lista_id, proveedor_id, referencia, referencia_norm, equivalencia,
                         descripcion, vehiculo, marca_vehiculo, precio, precio_con_desc,
                         descuento_pct, moneda, fecha_lista, archivo_origen, sheet_origen)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                    [
                        (
                            lista_id,
                            proveedor_id,
                            r["referencia"],
                            r["referencia_norm"],
                            r["equivalencia"],
                            r["descripcion"],
                            r["vehiculo"],
                            r["marca_vehiculo"],
                            r["precio"],
                            r["precio_con_desc"],
                            r["descuento_pct"],
                            r["moneda"],
                            r["fecha_lista"],
                            r["archivo_origen"],
                            r["sheet_origen"],
                        )
                        for r in registros
                    ]
                )

                # Actualizar contador
                await conn.execute(
                    "UPDATE listas SET total_registros = $1 WHERE id = $2",
                    len(registros), lista_id
                )

        return {
            "ok": True,
            "lista_id": lista_id,
            "archivo": archivo.filename,
            "registros_cargados": len(registros),
            "fecha_lista": str(fecha_lista) if fecha_lista else None,
            "mensaje": f"✅ {len(registros):,} repuestos cargados correctamente",
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Error procesando {archivo.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando el archivo: {str(e)}")
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.get("/api/proveedores")
async def get_proveedores(_: dict = Depends(require_permission("buscar"))):
    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT id, nombre, contacto, email, activo FROM proveedores ORDER BY nombre"
        )
    return [dict(r) for r in rows]


@app.get("/api/listas")
async def get_listas(
    proveedor_id: Optional[int] = None,
    _: dict = Depends(require_permission("inventario")),
):
    where = "WHERE 1=1"
    params = []
    if proveedor_id:
        where += " AND l.proveedor_id = $1"
        params.append(proveedor_id)

    async with app.state.pool.acquire() as conn:
        rows = await conn.fetch(f"""
            SELECT l.id, l.archivo_nombre, l.fecha_lista, l.total_registros,
                   l.subido_en, l.activa, l.subido_por,
                   pr.nombre AS proveedor
            FROM listas l
            JOIN proveedores pr ON pr.id = l.proveedor_id
            {where}
            ORDER BY l.subido_en DESC
        """, *params)
    return [dict(r) for r in rows]


@app.delete("/api/listas/{lista_id}")
async def desactivar_lista(
    lista_id: int,
    _: dict = Depends(require_roles("admin")),
):
    async with app.state.pool.acquire() as conn:
        result = await conn.execute(
            "UPDATE listas SET activa = false WHERE id = $1", lista_id
        )
    if result == "UPDATE 0":
        raise HTTPException(status_code=404, detail="Lista no encontrada")
    return {"ok": True, "mensaje": f"Lista {lista_id} desactivada"}
