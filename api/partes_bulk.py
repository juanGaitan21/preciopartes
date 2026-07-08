"""Insercion masiva de partes con COPY (mucho mas rapido que executemany)."""

PARTES_COLUMNS = [
    "lista_id",
    "proveedor_id",
    "referencia",
    "referencia_norm",
    "equivalencia",
    "descripcion",
    "vehiculo",
    "marca_vehiculo",
    "precio",
    "precio_con_desc",
    "descuento_pct",
    "moneda",
    "fecha_lista",
    "archivo_origen",
    "sheet_origen",
]

CHUNK_SIZE = 8000


async def insert_partes_bulk(conn, lista_id: int, proveedor_id: int, registros: list) -> int:
    if not registros:
        return 0

    rows = [
        (
            lista_id,
            proveedor_id,
            r["referencia"],
            r["referencia_norm"],
            r.get("equivalencia") or "",
            r["descripcion"],
            r.get("vehiculo") or "",
            r.get("marca_vehiculo") or "",
            r["precio"],
            r["precio_con_desc"],
            r.get("descuento_pct") or 0,
            r.get("moneda") or "COP",
            r.get("fecha_lista"),
            r.get("archivo_origen") or "",
            r.get("sheet_origen") or "",
        )
        for r in registros
    ]

    for i in range(0, len(rows), CHUNK_SIZE):
        await conn.copy_records_to_table(
            "partes",
            records=rows[i : i + CHUNK_SIZE],
            columns=PARTES_COLUMNS,
        )

    return len(rows)
