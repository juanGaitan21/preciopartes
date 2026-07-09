"""Analisis de mercado: mejor proveedor por categoria e insights."""

from __future__ import annotations

import logging
from typing import Any

from api.categorias import CATEGORIA_OTROS, CATEGORIAS, sql_categoria_expr

logger = logging.getLogger(__name__)

RESUMEN_SQL = """
SELECT
    (SELECT COUNT(*) FROM partes p
     JOIN listas l ON l.id = p.lista_id AND l.activa
     JOIN proveedores pr ON pr.id = p.proveedor_id AND pr.activo) AS total_repuestos,
    (SELECT COUNT(*) FROM listas WHERE activa) AS listas_activas,
    (SELECT COUNT(*) FROM proveedores WHERE activo) AS proveedores_activos
"""

COMPARABLES_SQL = f"""
WITH activas AS (
    SELECT
        p.referencia_norm,
        p.proveedor_id,
        pr.nombre AS proveedor,
        p.descripcion,
        p.precio_con_desc::float AS precio,
        p.marca_vehiculo,
        {sql_categoria_expr("p")} AS categoria
    FROM partes p
    JOIN listas l ON l.id = p.lista_id AND l.activa = true
    JOIN proveedores pr ON pr.id = p.proveedor_id AND pr.activo = true
),
comparables AS (
    SELECT referencia_norm
    FROM activas
    GROUP BY referencia_norm
    HAVING COUNT(DISTINCT proveedor_id) >= 2
),
ranked AS (
    SELECT
        a.*,
        ROW_NUMBER() OVER (PARTITION BY a.referencia_norm ORDER BY a.precio ASC) AS rn,
        MIN(a.precio) OVER (PARTITION BY a.referencia_norm) AS precio_min,
        MAX(a.precio) OVER (PARTITION BY a.referencia_norm) AS precio_max,
        COUNT(*) OVER (PARTITION BY a.referencia_norm) AS num_ofertas
    FROM activas a
    INNER JOIN comparables c ON c.referencia_norm = a.referencia_norm
)
SELECT
    referencia_norm,
    proveedor_id,
    proveedor,
    descripcion,
    precio,
    precio_min,
    precio_max,
    num_ofertas,
    categoria,
    marca_vehiculo,
    ROUND(((precio_max - precio_min) / NULLIF(precio_min, 0) * 100)::numeric, 1)::float AS spread_pct
FROM ranked
WHERE rn = 1
"""


def _pct(part: int, total: int) -> float:
    if total <= 0:
        return 0.0
    return round(part / total * 100, 1)


def _generar_insights(
    ranking_general: list[dict],
    por_categoria: list[dict],
    oportunidades: list[dict],
    total_comparables: int,
) -> list[str]:
    insights: list[str] = []
    if total_comparables == 0:
        insights.append(
            "Aun no hay suficientes referencias repetidas entre proveedores para comparar. "
            "Sube mas listas que compartan las mismas referencias."
        )
        return insights

    if ranking_general:
        top = ranking_general[0]
        insights.append(
            f"{top['proveedor']} es el proveedor mas competitivo en general: "
            f"gana en {top['referencias_ganadas']:,} referencias "
            f"({_pct(top['referencias_ganadas'], total_comparables)}% del mercado comparable)."
        )

    if len(ranking_general) >= 2:
        segundo = ranking_general[1]
        diff = ranking_general[0]["referencias_ganadas"] - segundo["referencias_ganadas"]
        if diff <= total_comparables * 0.05:
            insights.append(
                f"Competencia muy pareja entre {ranking_general[0]['proveedor']} y "
                f"{segundo['proveedor']} (diferencia de solo {diff:,} referencias)."
            )

    cats_con_lider = [c for c in por_categoria if c.get("mejor_proveedor")]
    if cats_con_lider:
        mejor_cat = max(cats_con_lider, key=lambda c: c["referencias_comparables"])
        insights.append(
            f"En {mejor_cat['categoria']} hay {mejor_cat['referencias_comparables']:,} "
            f"referencias comparables; el mas barato suele ser {mejor_cat['mejor_proveedor']} "
            f"({_pct(mejor_cat['victorias'], mejor_cat['referencias_comparables'])}%)."
        )

    if oportunidades:
        top = oportunidades[0]
        insights.append(
            f"Mayor oportunidad de ahorro: {top['descripcion'][:60]}… "
            f"(diferencia de hasta {top['spread_pct']:.0f}% entre proveedores)."
        )

    solo = [c for c in por_categoria if c["referencias_comparables"] >= 10]
    for cat in sorted(solo, key=lambda c: c["referencias_comparables"], reverse=True)[:3]:
        if cat["mejor_proveedor"] and cat["victorias"] >= cat["referencias_comparables"] * 0.6:
            insights.append(
                f"Compra {cat['categoria']} principalmente en {cat['mejor_proveedor']} "
                f"({cat['victorias']:,} de {cat['referencias_comparables']:,} veces mas barato)."
            )

    return insights[:6]


async def obtener_analisis_mercado(pool) -> dict[str, Any]:
    async with pool.acquire() as conn:
        resumen_row = await conn.fetchrow(RESUMEN_SQL)
        rows = await conn.fetch(COMPARABLES_SQL)

    winners = [dict(r) for r in rows]
    total_comparables = len(winners)

    # Ranking general
    wins_por_proveedor: dict[str, dict] = {}
    for w in winners:
        prov = w["proveedor"]
        if prov not in wins_por_proveedor:
            wins_por_proveedor[prov] = {
                "proveedor": prov,
                "proveedor_id": w["proveedor_id"],
                "referencias_ganadas": 0,
                "ahorro_potencial_total": 0.0,
            }
        wins_por_proveedor[prov]["referencias_ganadas"] += 1
        wins_por_proveedor[prov]["ahorro_potencial_total"] += float(w["precio_max"] - w["precio_min"])

    ranking_general = sorted(
        wins_por_proveedor.values(),
        key=lambda x: x["referencias_ganadas"],
        reverse=True,
    )
    for r in ranking_general:
        r["participacion_pct"] = _pct(r["referencias_ganadas"], total_comparables)
        r["ahorro_potencial_total"] = round(r["ahorro_potencial_total"], 0)

    # Por categoria
    cats: dict[str, dict] = {}
    for w in winners:
        cat = w["categoria"] or CATEGORIA_OTROS
        if cat not in cats:
            cats[cat] = {"categoria": cat, "victorias": {}, "total": 0}
        cats[cat]["total"] += 1
        prov = w["proveedor"]
        cats[cat]["victorias"][prov] = cats[cat]["victorias"].get(prov, 0) + 1

    por_categoria = []
    for cat, data in sorted(cats.items(), key=lambda x: -x[1]["total"]):
        if not data["victorias"]:
            continue
        mejor = max(data["victorias"].items(), key=lambda x: x[1])
        por_categoria.append({
            "categoria": cat,
            "referencias_comparables": data["total"],
            "mejor_proveedor": mejor[0],
            "victorias": mejor[1],
            "participacion_pct": _pct(mejor[1], data["total"]),
            "ranking": sorted(
                [{"proveedor": p, "victorias": v, "pct": _pct(v, data["total"])} for p, v in data["victorias"].items()],
                key=lambda x: -x["victorias"],
            ),
        })

    # Oportunidades: mayor spread de precio
    oportunidades = sorted(winners, key=lambda w: w.get("spread_pct") or 0, reverse=True)[:15]
    oportunidades_out = [
        {
            "referencia_norm": o["referencia_norm"],
            "descripcion": o["descripcion"],
            "categoria": o["categoria"],
            "proveedor_mas_barato": o["proveedor"],
            "precio_min": o["precio_min"],
            "precio_max": o["precio_max"],
            "spread_pct": o.get("spread_pct") or 0,
            "num_ofertas": o["num_ofertas"],
        }
        for o in oportunidades
        if (o.get("spread_pct") or 0) >= 5
    ]

    # Marcas con mas comparables
    marcas: dict[str, int] = {}
    for w in winners:
        m = (w.get("marca_vehiculo") or "").strip().upper()
        if m:
            marcas[m] = marcas.get(m, 0) + 1
    top_marcas = sorted(
        [{"marca": k, "referencias": v} for k, v in marcas.items()],
        key=lambda x: -x["referencias"],
    )[:10]

    insights = _generar_insights(ranking_general, por_categoria, oportunidades_out, total_comparables)

    return {
        "resumen": {
            "total_repuestos": resumen_row["total_repuestos"],
            "listas_activas": resumen_row["listas_activas"],
            "proveedores_activos": resumen_row["proveedores_activos"],
            "referencias_comparables": total_comparables,
        },
        "ranking_general": ranking_general,
        "por_categoria": por_categoria,
        "oportunidades_ahorro": oportunidades_out[:10],
        "top_marcas": top_marcas,
        "insights": insights,
    }


async def obtener_opciones_filtro(pool) -> dict[str, Any]:
    async with pool.acquire() as conn:
        proveedores = await conn.fetch(
            """SELECT id, nombre FROM proveedores WHERE activo ORDER BY nombre"""
        )
        marcas = await conn.fetch(
            """SELECT DISTINCT upper(trim(marca_vehiculo)) AS marca
               FROM partes p
               JOIN listas l ON l.id = p.lista_id AND l.activa
               WHERE trim(coalesce(marca_vehiculo, '')) <> ''
               ORDER BY 1
               LIMIT 200"""
        )
        categorias = [c[0] for c in CATEGORIAS]
        categorias.append(CATEGORIA_OTROS)

    return {
        "proveedores": [dict(r) for r in proveedores],
        "marcas": [r["marca"] for r in marcas if r["marca"]],
        "categorias": categorias,
    }
