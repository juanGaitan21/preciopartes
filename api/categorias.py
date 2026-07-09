"""Clasificacion de repuestos por palabras clave en la descripcion."""

from __future__ import annotations

import re
from typing import Optional

# Orden importa: la primera coincidencia gana.
CATEGORIAS: list[tuple[str, re.Pattern[str]]] = [
    ("Filtros", re.compile(r"FILTRO|ACEITE|AIRE|COMBUST|HABITACUL", re.I)),
    ("Frenos", re.compile(r"FRENO|DISCO|PASTILL|ZAPATA|TAMBOR|BOMBA.*FRENO", re.I)),
    ("Suspension", re.compile(r"AMORTIG|BASE|BALLESTA|RESORTE|SOPORTE|TERMINAL|ROTULA|BUJE|ESTABILI", re.I)),
    ("Direccion", re.compile(r"DIRECC|CREMALL|CAJA.*DIR|BOMBA.*DIR|TERMINAL.*DIR", re.I)),
    ("Motor", re.compile(r"MOTOR|PISTON|ANILLO|BIELA|CULATA|EMPAQUE|CORREA|CADENA|BOMBA.*AGUA|RADIADOR|TERMOST", re.I)),
    ("Transmision", re.compile(r"CAJA|CLUTCH|EMBRAG|CRUCETA|CARDAN|DIFEREN|TRANSMIS", re.I)),
    ("Electrico", re.compile(r"ALTERN|BATERI|BOMBILL|FAROL|LAMPAR|SENSOR|BOBINA|ARRANQUE|RELAY|FUSIBLE", re.I)),
    ("Carroceria", re.compile(r"GUARD|PARACH|CAPOT|PUERT|ESPEJO|GRILL|BOMPER|FENDER|GUARDAF", re.I)),
    ("Encendido", re.compile(r"BUJIA|CABLE|DISTRIB|INJECT|INYE", re.I)),
    ("Lubricantes y fluidos", re.compile(r"ACEITE|GRASA|REFRIG|LIQUIDO|ADITIV", re.I)),
]

CATEGORIA_OTROS = "Otros"


def categorizar_descripcion(descripcion: str) -> str:
    text = descripcion or ""
    for nombre, pattern in CATEGORIAS:
        if pattern.search(text):
            return nombre
    return CATEGORIA_OTROS


def sql_categoria_expr(alias: str = "p") -> str:
    """Expresion SQL CASE para categorizar en consultas agregadas."""
    parts = []
    for nombre, pattern in CATEGORIAS:
        # Convertir regex Python a ~ POSIX (patron simplificado)
        src = pattern.pattern.replace(".*", "%").replace("|", "|")
        parts.append(f"WHEN upper({alias}.descripcion) ~ '{src}' THEN '{nombre}'")
    return f"CASE {' '.join(parts)} ELSE '{CATEGORIA_OTROS}' END"
