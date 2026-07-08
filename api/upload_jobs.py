"""
Carga de listas en background con persistencia y reanudacion tras reinicio.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from api.serialize import json_safe, safe_json, to_int

logger = logging.getLogger(__name__)

JOB_DATA_DIR = Path(os.getenv("UPLOAD_JOB_DIR", "/app/data/jobs"))
ETL_SEMAPHORE = asyncio.Semaphore(1)

JOB_SCHEMA = """
CREATE TABLE IF NOT EXISTS upload_jobs (
    id              TEXT PRIMARY KEY,
    estado          TEXT NOT NULL DEFAULT 'queued'
                    CHECK (estado IN ('queued', 'processing', 'completed', 'failed')),
    subido_por      TEXT NOT NULL,
    user_id         INTEGER REFERENCES users(id),
    total_archivos  INTEGER NOT NULL DEFAULT 0,
    archivos_ok     INTEGER NOT NULL DEFAULT 0,
    archivos_error  INTEGER NOT NULL DEFAULT 0,
    total_registros INTEGER NOT NULL DEFAULT 0,
    mensaje         TEXT DEFAULT '',
    directorio      TEXT NOT NULL,
    listo_para_procesar BOOLEAN NOT NULL DEFAULT false,
    creado_en       TIMESTAMP DEFAULT now(),
    iniciado_en     TIMESTAMP,
    finalizado_en   TIMESTAMP
);

CREATE TABLE IF NOT EXISTS upload_job_archivos (
    id                  SERIAL PRIMARY KEY,
    job_id              TEXT NOT NULL REFERENCES upload_jobs(id) ON DELETE CASCADE,
    archivo_nombre      TEXT NOT NULL,
    orden               INTEGER NOT NULL,
    estado              TEXT NOT NULL DEFAULT 'pending'
                        CHECK (estado IN ('pending', 'processing', 'completed', 'failed')),
    lista_id            INTEGER REFERENCES listas(id),
    registros_cargados  INTEGER DEFAULT 0,
    resultado           JSONB,
    error               JSONB,
    iniciado_en         TIMESTAMP,
    finalizado_en       TIMESTAMP,
    UNIQUE (job_id, orden)
);

CREATE INDEX IF NOT EXISTS idx_upload_jobs_estado ON upload_jobs (estado);
CREATE INDEX IF NOT EXISTS idx_upload_job_archivos_job ON upload_job_archivos (job_id);
"""


class ListaUploadError(Exception):
    def __init__(self, mensaje: str, codigo: str = "ERROR", **extra: Any):
        super().__init__(mensaje)
        self.mensaje = mensaje
        self.codigo = codigo
        self.extra = extra


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def ensure_upload_job_tables(pool) -> None:
    async with pool.acquire() as conn:
        await conn.execute(JOB_SCHEMA)
        await conn.execute(
            "ALTER TABLE upload_jobs ADD COLUMN IF NOT EXISTS listo_para_procesar BOOLEAN NOT NULL DEFAULT false"
        )
        has_col = await conn.fetchval(
            """SELECT COUNT(*) FROM information_schema.columns
               WHERE table_name = 'upload_jobs' AND column_name = 'listo_para_procesar'"""
        )
        if not has_col:
            logger.error("Columna listo_para_procesar no existe tras migracion")
        else:
            logger.info("Tablas upload_jobs OK (listo_para_procesar presente)")


def _job_dir(job_id: str) -> Path:
    path = JOB_DATA_DIR / job_id
    path.mkdir(parents=True, exist_ok=True)
    return path


async def create_empty_upload_job(
    pool,
    *,
    subido_por: str,
    user_id: Optional[int],
) -> dict:
    job_id = str(uuid.uuid4())
    job_path = _job_dir(job_id)

    async with pool.acquire() as conn:
        await conn.execute(
            """INSERT INTO upload_jobs
               (id, estado, subido_por, user_id, total_archivos, directorio, listo_para_procesar)
               VALUES ($1, 'queued', $2, $3, 0, $4, false)""",
            job_id,
            subido_por,
            user_id,
            str(job_path),
        )

    return {
        "job_id": job_id,
        "total_archivos": 0,
        "estado": "queued",
        "mensaje": "Job creado. Sube los archivos uno por uno y luego inicia el procesamiento.",
    }


async def append_file_to_upload_job(
    pool,
    job_id: str,
    filename: str,
    content: bytes,
) -> dict:
    safe_name = Path(filename).name
    if not safe_name:
        raise HTTPException(status_code=400, detail="Nombre de archivo invalido")

    async with pool.acquire() as conn:
        job = await _fetch_job_row(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        if job["estado"] != "queued":
            raise HTTPException(status_code=409, detail="El job ya esta en procesamiento")
        if job.get("listo_para_procesar"):
            raise HTTPException(status_code=409, detail="El job ya fue iniciado")

        orden = await conn.fetchval(
            "SELECT COUNT(*) FROM upload_job_archivos WHERE job_id = $1",
            job_id,
        )
        job_path = Path(job["directorio"])
        dest = job_path / safe_name
        dest.write_bytes(content)

        async with conn.transaction():
            await conn.execute(
                """INSERT INTO upload_job_archivos
                   (job_id, archivo_nombre, orden, estado)
                   VALUES ($1, $2, $3, 'pending')""",
                job_id,
                safe_name,
                orden,
            )
            total = await conn.fetchval(
                "SELECT COUNT(*) FROM upload_job_archivos WHERE job_id = $1",
                job_id,
            )
            await conn.execute(
                "UPDATE upload_jobs SET total_archivos = $2 WHERE id = $1",
                job_id,
                total,
            )

    return {
        "job_id": job_id,
        "archivo": safe_name,
        "orden": orden,
        "total_archivos": total,
        "mensaje": f"Archivo {safe_name} recibido ({orden + 1} de {total})",
    }


async def start_upload_job(pool, job_id: str, guardar_fn) -> dict:
    async with pool.acquire() as conn:
        job = await _fetch_job_row(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado")
        if job.get("listo_para_procesar"):
            return {
                "job_id": job_id,
                "estado": job["estado"],
                "mensaje": "El job ya fue iniciado",
            }
        if job["total_archivos"] == 0:
            raise HTTPException(status_code=400, detail="No hay archivos en el job")

        await conn.execute(
            "UPDATE upload_jobs SET listo_para_procesar = true WHERE id = $1",
            job_id,
        )

    schedule_upload_job(pool, job_id, guardar_fn)
    return {
        "job_id": job_id,
        "estado": "queued",
        "total_archivos": job["total_archivos"],
        "mensaje": f"Procesamiento iniciado para {job['total_archivos']} archivo(s)",
    }


async def create_upload_job(
    pool,
    *,
    subido_por: str,
    user_id: Optional[int],
    files: list[tuple[str, bytes]],
) -> dict:
    if not files:
        raise HTTPException(status_code=400, detail="No se enviaron archivos")

    job_id = str(uuid.uuid4())
    job_path = _job_dir(job_id)

    async with pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """INSERT INTO upload_jobs
                   (id, estado, subido_por, user_id, total_archivos, directorio, listo_para_procesar)
                   VALUES ($1, 'queued', $2, $3, $4, $5, true)""",
                job_id,
                subido_por,
                user_id,
                len(files),
                str(job_path),
            )

            for orden, (filename, content) in enumerate(files):
                safe_name = Path(filename).name
                dest = job_path / safe_name
                dest.write_bytes(content)
                await conn.execute(
                    """INSERT INTO upload_job_archivos
                       (job_id, archivo_nombre, orden, estado)
                       VALUES ($1, $2, $3, 'pending')""",
                    job_id,
                    safe_name,
                    orden,
                )

    return {
        "job_id": job_id,
        "total_archivos": len(files),
        "estado": "queued",
        "mensaje": (
            f"Job creado: {len(files)} archivo(s) en cola. "
            "Consulta el progreso con GET /api/listas/jobs/{job_id}"
        ),
    }


async def _fetch_job_row(conn, job_id: str):
    return await conn.fetchrow(
        """SELECT id, estado, subido_por, user_id, total_archivos,
                  archivos_ok, archivos_error, total_registros, mensaje,
                  directorio, listo_para_procesar,
                  creado_en, iniciado_en, finalizado_en
           FROM upload_jobs WHERE id = $1""",
        job_id,
    )


async def _fetch_job_files(conn, job_id: str):
    return await conn.fetch(
        """SELECT id, archivo_nombre, orden, estado, lista_id,
                  registros_cargados, resultado, error,
                  iniciado_en, finalizado_en
           FROM upload_job_archivos
           WHERE job_id = $1
           ORDER BY orden""",
        job_id,
    )


def _build_job_response(job, files) -> dict:
    archivos = []
    resultados = []
    errores = []

    completados = 0
    con_error = 0
    procesando = 0
    pendientes = 0
    total_registros = 0

    for row in files:
        estado = row["estado"]
        item = {
            "archivo": row["archivo_nombre"],
            "orden": to_int(row["orden"]),
            "estado": estado,
            "lista_id": to_int(row["lista_id"]) if row["lista_id"] else None,
            "registros_cargados": to_int(row["registros_cargados"]),
        }

        if estado == "completed":
            completados += 1
            total_registros += to_int(row["registros_cargados"])
            if row["resultado"]:
                res = json_safe(safe_json(row["resultado"]))
                resultados.append(res)
                item["resultado"] = res
        elif estado == "failed":
            con_error += 1
            if row["error"]:
                err = json_safe(safe_json(row["error"]))
                errores.append(err)
                item["error"] = err
        elif estado == "processing":
            procesando += 1
            if row["resultado"]:
                res = json_safe(safe_json(row["resultado"]))
                if res.get("fase"):
                    item["fase"] = res["fase"]
                if res.get("detalle"):
                    item["fase_detalle"] = res["detalle"]
        else:
            pendientes += 1

        archivos.append(item)

    total = to_int(job["total_archivos"]) or len(files)
    terminados = completados + con_error
    progreso_pct = round((terminados / total) * 100, 1) if total else 0.0

    mensaje = job["mensaje"] or ""
    if not mensaje:
        if job["estado"] == "queued":
            mensaje = "En cola, iniciara en breve..."
        elif job["estado"] == "processing":
            mensaje = f"Procesando archivo {terminados + 1} de {total}..."
        elif job["estado"] == "completed":
            mensaje = (
                f"{completados} archivo(s) cargados, {total_registros:,} repuestos"
                + (f", {con_error} con error" if con_error else "")
            )

    return {
        "job_id": job["id"],
        "estado": job["estado"],
        "total_archivos": total,
        "archivos_completados": completados,
        "archivos_error": con_error,
        "archivos_procesando": procesando,
        "archivos_pendientes": pendientes,
        "progreso_pct": progreso_pct,
        "total_registros": to_int(total_registros),
        "archivos": archivos,
        "resultados": resultados,
        "errores": errores,
        "mensaje": mensaje,
        "creado_en": job["creado_en"].isoformat() if job["creado_en"] else None,
        "iniciado_en": job["iniciado_en"].isoformat() if job["iniciado_en"] else None,
        "finalizado_en": job["finalizado_en"].isoformat() if job["finalizado_en"] else None,
        "ok": job["estado"] == "completed" and con_error == 0,
    }


async def get_upload_job_status(pool, job_id: str, user: Optional[dict] = None) -> dict:
    try:
        async with pool.acquire() as conn:
            job = await _fetch_job_row(conn, job_id)
            if not job:
                raise HTTPException(status_code=404, detail="Job no encontrado")

            if user and job["user_id"] and to_int(job["user_id"]) != to_int(user.get("id")):
                if user.get("rol") != "admin":
                    raise HTTPException(status_code=403, detail="No autorizado para ver este job")

            files = await _fetch_job_files(conn, job_id)

        return _build_job_response(job, files)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception("Error leyendo job %s: %s", job_id, e)
        raise HTTPException(status_code=500, detail=f"Error leyendo estado del job: {e}") from e


async def _update_job_counters(conn, job_id: str) -> None:
    stats = await conn.fetchrow(
        """SELECT
               COUNT(*) FILTER (WHERE estado = 'completed') AS ok,
               COUNT(*) FILTER (WHERE estado = 'failed') AS err,
               COALESCE(SUM(registros_cargados) FILTER (WHERE estado = 'completed'), 0) AS regs
           FROM upload_job_archivos
           WHERE job_id = $1""",
        job_id,
    )
    await conn.execute(
        """UPDATE upload_jobs
           SET archivos_ok = $2,
               archivos_error = $3,
               total_registros = $4
           WHERE id = $1""",
        job_id,
        stats["ok"],
        stats["err"],
        stats["regs"],
    )


async def _finalize_job(conn, job_id: str) -> None:
    pending = await conn.fetchval(
        """SELECT COUNT(*) FROM upload_job_archivos
           WHERE job_id = $1 AND estado IN ('pending', 'processing')""",
        job_id,
    )
    if pending:
        return

    stats = await conn.fetchrow(
        """SELECT archivos_ok, archivos_error, total_registros
           FROM upload_jobs WHERE id = $1""",
        job_id,
    )
    final_estado = "completed" if stats["archivos_error"] == 0 else "completed"
    mensaje = (
        f"{stats['archivos_ok']} archivo(s) procesados, "
        f"{stats['total_registros']:,} repuestos cargados"
        + (f", {stats['archivos_error']} con error" if stats["archivos_error"] else "")
    )

    await conn.execute(
        """UPDATE upload_jobs
           SET estado = $2,
               mensaje = $3,
               finalizado_en = $4
           WHERE id = $1""",
        job_id,
        final_estado,
        mensaje,
        _utcnow(),
    )


async def process_upload_job(pool, job_id: str, guardar_fn) -> None:
    """Procesa un job archivo por archivo. guardar_fn(path, filename, subido_por, job_file_id, conn)."""
    async with ETL_SEMAPHORE:
        async with pool.acquire() as conn:
            job = await _fetch_job_row(conn, job_id)
            if not job:
                logger.warning("Job %s no encontrado", job_id)
                return
            if job["estado"] == "completed":
                return
            if not job.get("listo_para_procesar"):
                logger.info("Job %s aun no listo para procesar", job_id)
                return

            await conn.execute(
                """UPDATE upload_jobs
                   SET estado = 'processing',
                       iniciado_en = COALESCE(iniciado_en, $2)
                   WHERE id = $1""",
                job_id,
                _utcnow(),
            )

        files = []
        async with pool.acquire() as conn:
            files = await _fetch_job_files(conn, job_id)

        job_path = Path(job["directorio"])
        subido_por = job["subido_por"]

        for file_row in files:
            if file_row["estado"] == "completed":
                continue

            async with pool.acquire() as conn:
                if await _job_fue_cancelado(conn, job_id):
                    logger.info("Job %s cancelado, deteniendo", job_id)
                    return

            file_id = file_row["id"]
            filename = file_row["archivo_nombre"]
            file_path = job_path / filename

            if not file_path.exists():
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute(
                            """UPDATE upload_job_archivos
                               SET estado = 'failed',
                                   error = $2::jsonb,
                                   finalizado_en = $3
                               WHERE id = $1""",
                            file_id,
                            json.dumps({
                                "archivo": filename,
                                "mensaje": "Archivo no encontrado en disco",
                                "codigo": "ARCHIVO_PERDIDO",
                            }),
                            _utcnow(),
                        )
                        await _update_job_counters(conn, job_id)
                continue

            async with pool.acquire() as conn:
                await conn.execute(
                    """UPDATE upload_job_archivos
                       SET estado = 'processing', iniciado_en = $2
                       WHERE id = $1""",
                    file_id,
                    _utcnow(),
                )

            try:
                result = await guardar_fn(
                    pool,
                    file_path,
                    filename,
                    subido_por,
                    file_id=file_id,
                )
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute(
                            """UPDATE upload_job_archivos
                               SET estado = 'completed',
                                   lista_id = $2,
                                   registros_cargados = $3,
                                   resultado = $4::jsonb,
                                   error = NULL,
                                   finalizado_en = $5
                               WHERE id = $1""",
                            file_id,
                            result["lista_id"],
                            result["registros_cargados"],
                            json.dumps(result, default=str),
                            _utcnow(),
                        )
                        await _update_job_counters(conn, job_id)

                logger.info(
                    "Job %s: %s OK (%s repuestos)",
                    job_id,
                    filename,
                    result["registros_cargados"],
                )

            except ListaUploadError as e:
                error_payload = {
                    "archivo": filename,
                    "mensaje": e.mensaje,
                    "codigo": e.codigo,
                    **e.extra,
                }
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute(
                            """UPDATE upload_job_archivos
                               SET estado = 'failed',
                                   error = $2::jsonb,
                                   finalizado_en = $3
                               WHERE id = $1""",
                            file_id,
                            json.dumps(error_payload),
                            _utcnow(),
                        )
                        await _update_job_counters(conn, job_id)
                logger.warning("Job %s: %s fallo: %s", job_id, filename, e.mensaje)

            except Exception as e:
                logger.exception("Job %s: error inesperado en %s", job_id, filename)
                error_payload = {
                    "archivo": filename,
                    "mensaje": str(e),
                    "codigo": "ERROR",
                }
                async with pool.acquire() as conn:
                    async with conn.transaction():
                        await conn.execute(
                            """UPDATE upload_job_archivos
                               SET estado = 'failed',
                                   error = $2::jsonb,
                                   finalizado_en = $3
                               WHERE id = $1""",
                            file_id,
                            json.dumps(error_payload),
                            _utcnow(),
                        )
                        await _update_job_counters(conn, job_id)

        async with pool.acquire() as conn:
            async with conn.transaction():
                await _finalize_job(conn, job_id)

        logger.info("Job %s finalizado", job_id)


def schedule_upload_job(pool, job_id: str, guardar_fn) -> None:
    asyncio.create_task(process_upload_job(pool, job_id, guardar_fn))


async def _job_fue_cancelado(conn, job_id: str) -> bool:
    row = await conn.fetchrow(
        "SELECT mensaje FROM upload_jobs WHERE id = $1 AND estado = 'completed'",
        job_id,
    )
    return bool(row and row["mensaje"] and "Cancelado" in row["mensaje"])


async def cancel_upload_job(pool, job_id: str, user: Optional[dict] = None) -> dict:
    async with pool.acquire() as conn:
        job = await _fetch_job_row(conn, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job no encontrado")

        if user and job["user_id"] and to_int(job["user_id"]) != to_int(user.get("id")):
            if user.get("rol") != "admin":
                raise HTTPException(status_code=403, detail="No autorizado")

        if job["estado"] == "completed":
            return {"ok": True, "mensaje": "El job ya habia terminado"}

        async with conn.transaction():
            await conn.execute(
                """UPDATE upload_job_archivos
                   SET estado = 'failed',
                       error = $2::jsonb,
                       finalizado_en = $3
                   WHERE job_id = $1 AND estado IN ('pending', 'processing')""",
                job_id,
                json.dumps({
                    "archivo": "",
                    "mensaje": "Cancelado por el usuario",
                    "codigo": "CANCELADO",
                }),
                _utcnow(),
            )
            await conn.execute(
                """UPDATE upload_jobs
                   SET estado = 'completed',
                       listo_para_procesar = false,
                       mensaje = 'Cancelado por usuario',
                       finalizado_en = $2
                   WHERE id = $1""",
                job_id,
                _utcnow(),
            )

    logger.info("Job %s cancelado por usuario", job_id)
    return {"ok": True, "job_id": job_id, "mensaje": "Carga cancelada"}


async def resume_pending_jobs(pool, guardar_fn) -> None:
    JOB_DATA_DIR.mkdir(parents=True, exist_ok=True)

    async with pool.acquire() as conn:
        await conn.execute(
            """UPDATE upload_job_archivos ja
               SET estado = 'failed',
                   error = '{"mensaje":"Interrumpido por reinicio del servidor","codigo":"INTERRUMPIDO"}'::jsonb,
                   finalizado_en = now()
               FROM upload_jobs j
               WHERE ja.job_id = j.id
                 AND ja.estado = 'processing'
                 AND j.iniciado_en < now() - interval '30 minutes'"""
        )
        await conn.execute(
            """UPDATE upload_jobs
               SET estado = 'completed',
                   mensaje = 'Job interrumpido. Vuelve a subir el archivo.',
                   finalizado_en = now()
               WHERE estado = 'processing'
                 AND iniciado_en < now() - interval '30 minutes'"""
        )
        await conn.execute(
            """UPDATE upload_jobs
               SET estado = 'completed',
                   mensaje = 'Job abandonado. Vuelve a subir el archivo.',
                   finalizado_en = now()
               WHERE estado = 'queued'
                 AND listo_para_procesar = false
                 AND creado_en < now() - interval '1 hour'"""
        )

        rows = await conn.fetch(
            """SELECT id FROM upload_jobs
               WHERE listo_para_procesar = true
                 AND estado IN ('queued', 'processing')
               ORDER BY creado_en"""
        )

        for row in rows:
            await conn.execute(
                """UPDATE upload_job_archivos
                   SET estado = 'pending'
                   WHERE job_id = $1 AND estado = 'processing'""",
                row["id"],
            )

    for row in rows:
        logger.info("Reanudando job pendiente: %s", row["id"])
        schedule_upload_job(pool, row["id"], guardar_fn)
