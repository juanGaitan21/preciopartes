"""Construccion de consultas de busqueda del comparador."""

from __future__ import annotations

from typing import Any, Optional

from api.categorias import sql_categoria_expr


def _like_pattern(term: str) -> str:
    return f"%{term.upper()}%"


def build_buscar_query(
    terminos: list[str],
    *,
    proveedor_id: Optional[int] = None,
    vehiculo: Optional[str] = None,
    marca: Optional[str] = None,
    categoria: Optional[str] = None,
    solo_mas_baratos: bool = False,
    match_all: bool = True,
    limit: int = 100,
) -> tuple[str, list[Any]]:
    """Arma WHERE y parametros. match_all=False usa OR entre terminos (mas resultados)."""
    params: list[Any] = []
    idx = 1

    condiciones_por_termino = []
    for termino in terminos:
        t = _like_pattern(termino)
        condiciones_por_termino.append(f"""(
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

    if not condiciones_por_termino:
        raise ValueError("Se requiere al menos un termino")

    joiner = " AND " if match_all else " OR "
    where = f"({joiner.join(condiciones_por_termino)})"

    if proveedor_id:
        where += f" AND p.proveedor_id = ${idx}"
        params.append(proveedor_id)
        idx += 1

    if vehiculo:
        v = _like_pattern(vehiculo.strip())
        where += f" AND (upper(p.vehiculo) LIKE ${idx} OR upper(p.descripcion) LIKE ${idx})"
        params.append(v)
        idx += 1

    if marca:
        m = _like_pattern(marca.strip())
        where += f" AND (upper(p.marca_vehiculo) LIKE ${idx} OR upper(p.vehiculo) LIKE ${idx} OR upper(p.descripcion) LIKE ${idx})"
        params.append(m)
        idx += 1

    if categoria:
        cat_expr = sql_categoria_expr("p")
        where += f" AND ({cat_expr}) = ${idx}"
        params.append(categoria)
        idx += 1

    base_from = """
        FROM partes p
        JOIN proveedores pr ON pr.id = p.proveedor_id
        JOIN listas l       ON l.id  = p.lista_id
        WHERE l.activa = true AND pr.activo = true
          AND {where}
    """

    if solo_mas_baratos:
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
            {base_from.format(where=where)}
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
            {base_from.format(where=where)}
            ORDER BY p.precio_con_desc ASC
            LIMIT ${idx}
        """

    params.append(min(limit, 200))
    return query, params
