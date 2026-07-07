"""
Limpieza, validacion y consistencia de datos — PrecioPartes ETL.
Toda fila pasa por aqui antes de insertarse en la base de datos.
"""

import logging
import math
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Filas de encabezado, totales o basura que no son repuestos
_REF_BASURA = frozenset({
    "REFERENCIA", "REF", "CODIGO", "CÓDIGO", "COD", "CODE",
    "N/A", "NA", "S/N", "SN", "TOTAL", "SUBTOTAL", "ITEM",
    "VEHICULO", "VEHÍCULO", "PRECIO", "DESCRIPCION", "DESCRIPCIÓN",
})
_DESC_BASURA = frozenset({
    "DESCRIPCION", "DESCRIPCIÓN", "DESC", "DESCRIPTION",
    "REFERENCIA", "PRECIO", "VEHICULO", "VEHÍCULO", "TOTAL",
})

PRECIO_MINIMO = 1            # COP — no descartar piezas baratas (tornillos, retenes, etc.)
PRECIO_MAXIMO = 500_000_000  # COP — tope de sanidad


def limpiar_texto(val) -> str:
    if val is None:
        return ""
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return ""
    s = str(val).strip()
    if s.lower() in ("nan", "none", "nat", "#n/a"):
        return ""
    return " ".join(s.split())


def limpiar_referencia(val) -> str:
    """Referencia tal como viene, corrigiendo floats de Excel (96335952.0)."""
    if val is None:
        return ""
    if isinstance(val, float):
        if math.isnan(val) or math.isinf(val):
            return ""
        if val == int(val):
            return str(int(val))
    if isinstance(val, int):
        return str(val)
    return limpiar_texto(val)


def normalizar_referencia(ref: str) -> str:
    """
    Codigo normalizado para comparacion cruzada entre proveedores.
    """
    if not ref:
        return ""
    r = str(ref).strip().upper()
    if r.endswith("P") and len(r) > 3 and r[-2].isdigit():
        r = r[:-1]
    r = re.sub(r"[^A-Z0-9]", "", r)
    return r


def limpiar_precio(valor) -> Optional[float]:
    """
    Convierte precio a float COP con 2 decimales.
    Maneja: numeros Excel, '$ 396.197', '396,197', etc.
    """
    if valor is None or isinstance(valor, bool):
        return None

    if isinstance(valor, (int, float)):
        try:
            v = float(valor)
            if math.isnan(v) or math.isinf(v) or v <= 0:
                return None
            return _validar_rango_precio(round(v, 2))
        except (TypeError, ValueError):
            return None

    s = str(valor).strip()
    if s.lower() in ("nan", "", "precio", "valor", "n/a", "#n/a", "-", "--"):
        return None
    if s.endswith("%"):
        return None

    s = re.sub(r"[$\s]", "", s)
    if not s or not re.search(r"\d", s):
        return None

    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        partes = s.split(".")
        if len(partes) > 1 and all(len(p) == 3 for p in partes[1:]):
            s = s.replace(".", "")
    elif "," in s:
        if "." not in s:
            parts = s.split(",")
            # Coma como miles: 396,197 o 1,234,567
            if all(len(p) == 3 for p in parts[1:]) and parts[0].isdigit() and all(p.isdigit() for p in parts[1:]):
                s = s.replace(",", "")
            else:
                s = s.replace(",", ".")
        else:
            s = s.replace(",", ".")

    try:
        v = float(s)
        if v <= 0:
            return None
        return _validar_rango_precio(round(v, 2))
    except ValueError:
        logger.debug("Precio no parseable: %r", valor)
        return None


def _validar_rango_precio(v: float) -> Optional[float]:
    if v < PRECIO_MINIMO or v > PRECIO_MAXIMO:
        logger.debug("Precio fuera de rango: %s", v)
        return None
    return v


def parsear_descuento_pct(valor) -> float:
    """
    Descuento en porcentaje (0-100).
    Acepta: 15, '15%', 0.15 (fraccion), '15,5'
    """
    if valor is None or isinstance(valor, bool):
        return 0.0

    if isinstance(valor, (int, float)):
        v = float(valor)
        if math.isnan(v) or math.isinf(v) or v <= 0:
            return 0.0
        if 0 < v < 1:
            v = v * 100
        return min(round(v, 2), 100.0)

    s = str(valor).strip().replace("%", "").replace(",", ".")
    if not s or s.lower() in ("nan", "n/a", "-", "0"):
        return 0.0
    try:
        v = float(s)
        if 0 < v < 1:
            v = v * 100
        if v <= 0:
            return 0.0
        return min(round(v, 2), 100.0)
    except ValueError:
        return 0.0


def aplicar_descuento(precio: float, desc_pct: float) -> tuple[float, float, float]:
    """Retorna (precio, precio_con_desc, descuento_pct) consistentes."""
    desc_pct = max(0.0, min(desc_pct, 100.0))
    if desc_pct <= 0:
        return precio, precio, 0.0
    precio_con_desc = round(precio * (1 - desc_pct / 100), 2)
    if precio_con_desc <= 0:
        return precio, precio, 0.0
    if precio_con_desc > precio:
        return precio, precio, 0.0
    return precio, precio_con_desc, desc_pct


def es_fila_basura(referencia: str, descripcion: str, referencia_norm: str) -> bool:
    ref_u = referencia.upper().strip()
    desc_u = descripcion.upper().strip()

    if not referencia_norm or len(referencia_norm) < 2:
        return True
    if ref_u in _REF_BASURA or desc_u in _DESC_BASURA:
        return True
    if ref_u.startswith("TOTAL") or desc_u.startswith("TOTAL"):
        return True
    if not descripcion or len(descripcion) < 2:
        return True
    if re.fullmatch(r"[\d\s.\-]+", referencia) and len(referencia_norm) < 4:
        return True
    return False


def construir_registro(
    *,
    proveedor_nombre: str,
    referencia_raw,
    descripcion_raw,
    precio_raw,
    equivalencia_raw="",
    vehiculo_raw="",
    marca_vehiculo_raw="",
    descuento_raw=None,
    moneda: str = "COP",
    fecha_lista=None,
    archivo_origen: str = "",
    sheet_origen: str = "",
) -> Optional[dict]:
    """Construye y valida un registro unificado. Retorna None si la fila no es valida."""
    referencia = limpiar_referencia(referencia_raw)
    descripcion = limpiar_texto(descripcion_raw)
    # Si no hay descripcion, usar referencia (comun en algunas listas)
    if not descripcion or len(descripcion) < 2:
        descripcion = referencia
    referencia_norm = normalizar_referencia(referencia)

    if es_fila_basura(referencia, descripcion, referencia_norm):
        return None

    precio = limpiar_precio(precio_raw)
    if precio is None:
        return None

    desc_pct = parsear_descuento_pct(descuento_raw)
    precio, precio_con_desc, desc_pct = aplicar_descuento(precio, desc_pct)

    equivalencia = limpiar_referencia(equivalencia_raw)
    vehiculo = limpiar_texto(vehiculo_raw)
    marca = limpiar_texto(marca_vehiculo_raw) or vehiculo

    from display import normalizar_marca, extraer_vehiculo_display

    desc_para_display = descripcion
    marca_display = normalizar_marca(marca, desc_para_display)
    vehiculo_display = extraer_vehiculo_display(vehiculo, desc_para_display, marca)

    return {
        "proveedor_nombre": proveedor_nombre,
        "referencia": referencia,
        "referencia_norm": referencia_norm,
        "equivalencia": equivalencia,
        "descripcion": descripcion,
        "vehiculo": vehiculo_display or vehiculo,
        "marca_vehiculo": marca_display or marca,
        "precio": precio,
        "precio_con_desc": precio_con_desc,
        "descuento_pct": desc_pct,
        "moneda": moneda,
        "fecha_lista": fecha_lista,
        "archivo_origen": archivo_origen,
        "sheet_origen": sheet_origen,
    }


def consolidar_registros(registros: list[dict], archivo: str = "") -> tuple[list[dict], int]:
    """
    Elimina solo filas EXACTAMENTE iguales (misma ref + vehiculo + desc + precio).
    NO colapsa la misma referencia en distintos vehiculos — eso es normal en listas DH.
    """
    vistos: set[tuple] = set()
    unicos: list[dict] = []
    duplicados = 0

    for reg in registros:
        key = (
            reg["referencia_norm"],
            reg.get("vehiculo", "").upper().strip(),
            reg.get("descripcion", "").upper().strip(),
            reg["precio_con_desc"],
        )
        if key in vistos:
            duplicados += 1
            continue
        vistos.add(key)
        unicos.append(reg)

    if duplicados:
        logger.info("[%s] %d filas exactamente duplicadas omitidas", archivo, duplicados)

    return unicos, duplicados


def validar_lote(registros: list[dict]) -> list[dict]:
    """Validacion final: precios coherentes y campos obligatorios."""
    validos = []
    rechazados = 0

    for reg in registros:
        if not reg.get("referencia_norm") or not reg.get("descripcion"):
            rechazados += 1
            continue
        p = reg.get("precio")
        pd_ = reg.get("precio_con_desc")
        if p is None or pd_ is None or p <= 0 or pd_ <= 0:
            rechazados += 1
            continue
        if pd_ > p:
            reg["precio_con_desc"] = p
            reg["descuento_pct"] = 0.0
        reg["precio"] = round(float(reg["precio"]), 2)
        reg["precio_con_desc"] = round(float(reg["precio_con_desc"]), 2)
        reg["descuento_pct"] = round(float(reg.get("descuento_pct") or 0), 2)
        validos.append(reg)

    if rechazados:
        logger.warning("%d registros rechazados en validacion final", rechazados)

    return validos
