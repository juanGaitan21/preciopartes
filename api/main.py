"""
PrecioPartes API — FastAPI
==========================
Endpoints:
    POST /api/listas/upload       — Sube un nuevo Excel, corre ETL, guarda en DB
    GET  /api/buscar              — Busca repuestos con comparación de precios
    GET  /api/proveedores         — Lista proveedores activos
    GET  /api/listas              — Historial de listas subidas
    DELETE /api/listas/{id}       — Desactiva una lista (no borra datos)
    DELETE /api/listas/{id}/eliminar — Elimina lista y repuestos de forma permanente
    POST   /api/listas/{id}/activar — Reactiva una lista (desactiva las demas del mismo proveedor)
"""

import asyncio
import json
import logging
import os
import time
from datetime import date
from pathlib import Path
from typing import List, Optional

import asyncpg
from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from api.deps import get_current_user, require_permission, require_roles
from api.db_init import init_database
from api.partes_bulk import insert_partes_bulk
from api.routes_auth import router as auth_router
from api.upload_jobs import (
    ListaUploadError,
    append_file_to_upload_job,
    cancel_upload_job,
    create_empty_upload_job,
    create_upload_job,
    ensure_upload_job_tables,
    get_upload_job_status,
    resume_pending_jobs,
    schedule_upload_job,
    start_upload_job,
)

# ETL propio
import sys
sys.path.append(str(Path(__file__).parent.parent / "etl"))
from etl import EXTENSIONES_EXCEL, procesar_archivo_detallado, TIPO_DH, TIPO_CAJAS, TIPO_LISTA_E

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
    await init_database(app.state.pool)
    await ensure_upload_job_tables(app.state.pool)
    await resume_pending_jobs(app.state.pool, _guardar_lista_desde_path)
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
            OR upper(p.marca_vehiculo)  LIKE ${idx}
            OR upper(p.equivalencia)    LIKE ${idx}
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
                p.equivalencia,
                p.descripcion,
                p.vehiculo,
                p.marca_vehiculo,
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
                p.equivalencia,
                p.descripcion,
                p.vehiculo,
                p.marca_vehiculo,
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
        "resultados": [_enriquecer_busqueda(dict(r)) for r in rows],
    }


def _enriquecer_busqueda(row: dict) -> dict:
    from display import enriquecer_resultado
    return enriquecer_resultado(row)


async def get_or_create_proveedor(conn, nombre: str) -> int:
    """Obtiene el ID del proveedor o lo crea si no existe."""
    pid = await conn.fetchval(
        "SELECT id FROM proveedores WHERE nombre = $1", nombre
    )
    if pid:
        return pid
    return await conn.fetchval(
        "INSERT INTO proveedores (nombre) VALUES ($1) RETURNING id", nombre
    )


async def _set_job_file_fase(pool, file_id: Optional[int], fase: str, detalle: str = "") -> None:
    if file_id is None:
        return
    async with pool.acquire() as conn:
        await conn.execute(
            "UPDATE upload_job_archivos SET resultado = $2::jsonb WHERE id = $1",
            file_id,
            json.dumps({"fase": fase, "detalle": detalle}),
        )


async def _guardar_lista_desde_path(
    pool,
    file_path: Path,
    filename: str,
    subido_por: str,
    proveedor_id: Optional[int] = None,
    tipo: Optional[str] = None,
    file_id: Optional[int] = None,
) -> dict:
    ext = Path(filename).suffix.lower()
    if ext not in EXTENSIONES_EXCEL:
        raise ListaUploadError(
            "Solo se aceptan archivos .xls, .xlsx o .xlsm",
            codigo="EXTENSION_INVALIDA",
        )

    t0 = time.monotonic()
    await _set_job_file_fase(pool, file_id, "leyendo_excel", "Leyendo y normalizando el Excel...")

    etl = await asyncio.to_thread(
        procesar_archivo_detallado,
        path=file_path,
        proveedor_nombre="",
        tipo=tipo,
    )
    t_etl = time.monotonic()
    logger.info("ETL %s: %.1fs", filename, t_etl - t0)

    if etl["codigo_error"]:
        raise ListaUploadError(
            etl["mensaje"],
            codigo=etl["codigo_error"],
            archivo=filename,
            tipo_detectado=etl["tipo_detectado"],
            requiere_reglas_etl=etl["codigo_error"] in ("FORMATO_DESCONOCIDO", "SIN_REGISTROS"),
        )

    registros = etl["registros"]
    proveedor_nombre = etl["proveedor_detectado"] or "Proveedor desconocido"
    tipo_detectado = etl["tipo_detectado"]
    n = len(registros)

    await _set_job_file_fase(
        pool,
        file_id,
        "guardando_bd",
        f"Guardando {n:,} repuestos en la base de datos...",
    )

    async with pool.acquire() as conn:
        async with conn.transaction():
            if proveedor_id is None:
                proveedor_id = await get_or_create_proveedor(conn, proveedor_nombre)

            await conn.execute(
                "UPDATE listas SET activa = false WHERE proveedor_id = $1",
                proveedor_id,
            )

            fecha_lista = registros[0].get("fecha_lista")
            lista_id = await conn.fetchval(
                """INSERT INTO listas (proveedor_id, archivo_nombre, fecha_lista, subido_por)
                   VALUES ($1, $2, $3, $4) RETURNING id""",
                proveedor_id, filename, fecha_lista, subido_por,
            )

            await insert_partes_bulk(conn, lista_id, proveedor_id, registros)

            await conn.execute(
                "UPDATE listas SET total_registros = $1 WHERE id = $2",
                n, lista_id,
            )

    t_db = time.monotonic()
    logger.info("BD %s: %s repuestos en %.1fs (total %.1fs)", filename, n, t_db - t_etl, t_db - t0)

    return {
        "ok": True,
        "lista_id": lista_id,
        "archivo": filename,
        "proveedor": proveedor_nombre,
        "tipo_detectado": tipo_detectado,
        "registros_cargados": n,
        "fecha_lista": str(fecha_lista) if fecha_lista else None,
        "estadisticas": etl.get("estadisticas", {}),
        "filas_descartadas": etl.get("filas_descartadas", 0),
        "mensaje": (
            f"{n:,} repuestos cargados "
            f"({proveedor_nombre}, formato {tipo_detectado})"
        ),
    }


async def _guardar_lista_desde_archivo(
    pool,
    content: bytes,
    filename: str,
    subido_por: str,
    proveedor_id: Optional[int] = None,
    tipo: Optional[str] = None,
) -> dict:
    ext = Path(filename).suffix.lower()
    if ext not in EXTENSIONES_EXCEL:
        raise HTTPException(status_code=400, detail="Solo se aceptan archivos .xls, .xlsx o .xlsm")

    tmp_path = Path(f"/tmp/{Path(filename).name}")
    try:
        tmp_path.write_bytes(content)
        return await _guardar_lista_desde_path(
            pool, tmp_path, filename, subido_por, proveedor_id, tipo
        )
    except ListaUploadError as e:
        raise HTTPException(
            status_code=422,
            detail={
                "mensaje": e.mensaje,
                "codigo": e.codigo,
                "archivo": filename,
                **e.extra,
            },
        )
    finally:
        if tmp_path.exists():
            tmp_path.unlink()


@app.post("/api/listas/upload")
async def upload_lista(
    archivo: UploadFile = File(...),
    proveedor_id: Optional[int] = Form(None),
    tipo: Optional[str] = Form(None),
    user: dict = Depends(require_permission("upload")),
):
    """
    Sube un Excel de lista de precios. Proveedor y formato se autodetectan si no se envian.
    """
    content = await archivo.read()
    return await _guardar_lista_desde_archivo(
        app.state.pool,
        content,
        archivo.filename,
        user["nombre"],
        proveedor_id=proveedor_id,
        tipo=tipo,
    )


@app.post("/api/listas/upload-batch")
async def upload_listas_batch(
    archivos: List[UploadFile] = File(...),
    user: dict = Depends(require_permission("upload")),
):
    """
    Sube varios Excel a la vez. Cada archivo: autodetecta proveedor, formato ETL y normaliza.
    """
    if not archivos:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    resultados = []
    errores = []

    for archivo in archivos:
        try:
            content = await archivo.read()
            res = await _guardar_lista_desde_archivo(
                app.state.pool,
                content,
                archivo.filename,
                user["nombre"],
            )
            resultados.append(res)
        except HTTPException as e:
            if isinstance(e.detail, dict):
                errores.append({"archivo": archivo.filename, **e.detail})
            else:
                errores.append({
                    "archivo": archivo.filename,
                    "mensaje": str(e.detail),
                    "codigo": "ERROR",
                    "requiere_reglas_etl": False,
                })
        except Exception as e:
            logger.exception(f"Error procesando {archivo.filename}: {e}")
            errores.append({
                "archivo": archivo.filename,
                "mensaje": str(e),
                "codigo": "ERROR",
                "requiere_reglas_etl": False,
            })

    total_registros = sum(r["registros_cargados"] for r in resultados)

    return {
        "ok": len(errores) == 0,
        "archivos_ok": len(resultados),
        "archivos_error": len(errores),
        "total_registros": total_registros,
        "resultados": resultados,
        "errores": errores,
        "mensaje": (
            f"{len(resultados)} archivo(s) procesados, {total_registros:,} repuestos cargados"
            + (f", {len(errores)} con error" if errores else "")
        ),
    }


@app.post("/api/listas/jobs")
async def create_lista_upload_job(
    user: dict = Depends(require_permission("upload")),
):
    """Crea un job vacio para subir archivos uno por uno (evita timeout)."""
    return await create_empty_upload_job(
        app.state.pool,
        subido_por=user["nombre"],
        user_id=user.get("id"),
    )


@app.post("/api/listas/jobs/{job_id}/archivos")
async def add_archivo_to_upload_job(
    job_id: str,
    archivo: UploadFile = File(...),
    user: dict = Depends(require_permission("upload")),
):
    """Agrega un archivo al job. Subir de a uno evita timeouts con archivos grandes."""
    await get_upload_job_status(app.state.pool, job_id, user)
    content = await archivo.read()
    return await append_file_to_upload_job(
        app.state.pool,
        job_id,
        archivo.filename,
        content,
    )


@app.post("/api/listas/jobs/{job_id}/start")
async def start_lista_upload_job(
    job_id: str,
    user: dict = Depends(require_permission("upload")),
):
    """Inicia el procesamiento ETL del job en background."""
    await get_upload_job_status(app.state.pool, job_id, user)
    return await start_upload_job(app.state.pool, job_id, _guardar_lista_desde_path)


@app.post("/api/listas/upload-batch-async")
async def upload_listas_batch_async(
    archivos: List[UploadFile] = File(...),
    user: dict = Depends(require_permission("upload")),
):
    """
    Sube varios Excel y los procesa en background.
    Retorna de inmediato un job_id para consultar progreso sin riesgo de timeout.
    """
    saved: list[tuple[str, bytes]] = []
    for archivo in archivos:
        content = await archivo.read()
        saved.append((archivo.filename, content))

    job = await create_upload_job(
        app.state.pool,
        subido_por=user["nombre"],
        user_id=user.get("id"),
        files=saved,
    )
    schedule_upload_job(app.state.pool, job["job_id"], _guardar_lista_desde_path)
    return job


@app.post("/api/listas/jobs/{job_id}/cancel")
async def cancel_lista_upload_job(
    job_id: str,
    user: dict = Depends(require_permission("upload")),
):
    """Cancela un job de carga atascado o en curso."""
    return await cancel_upload_job(app.state.pool, job_id, user)


@app.get("/api/listas/jobs/{job_id}")
async def get_lista_upload_job(
    job_id: str,
    user: dict = Depends(require_permission("upload")),
):
    """Estado del job de carga: progreso por archivo y resultados parciales."""
    return await get_upload_job_status(app.state.pool, job_id, user)


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


@app.delete("/api/listas/{lista_id}/eliminar")
async def eliminar_lista(
    lista_id: int,
    _: dict = Depends(require_roles("admin")),
):
    """Elimina permanentemente la lista y sus repuestos (CASCADE en partes)."""
    async with app.state.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                """SELECT l.id, l.archivo_nombre, l.total_registros, l.proveedor_id,
                          pr.nombre AS proveedor
                   FROM listas l
                   JOIN proveedores pr ON pr.id = l.proveedor_id
                   WHERE l.id = $1""",
                lista_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Lista no encontrada")

            await conn.execute(
                "UPDATE upload_job_archivos SET lista_id = NULL WHERE lista_id = $1",
                lista_id,
            )
            await conn.execute("DELETE FROM listas WHERE id = $1", lista_id)

    return {
        "ok": True,
        "mensaje": (
            f"Lista '{row['archivo_nombre']}' eliminada "
            f"({row['total_registros']:,} repuestos de {row['proveedor']})"
        ),
    }


@app.post("/api/listas/{lista_id}/activar")
async def activar_lista(
    lista_id: int,
    _: dict = Depends(require_roles("admin")),
):
    async with app.state.pool.acquire() as conn:
        async with conn.transaction():
            row = await conn.fetchrow(
                "SELECT id, proveedor_id, archivo_nombre FROM listas WHERE id = $1",
                lista_id,
            )
            if not row:
                raise HTTPException(status_code=404, detail="Lista no encontrada")

            await conn.execute(
                "UPDATE listas SET activa = false WHERE proveedor_id = $1",
                row["proveedor_id"],
            )
            await conn.execute(
                "UPDATE listas SET activa = true WHERE id = $1",
                lista_id,
            )

    return {
        "ok": True,
        "mensaje": f"Lista '{row['archivo_nombre']}' activada (otras del mismo proveedor quedaron inactivas)",
    }
