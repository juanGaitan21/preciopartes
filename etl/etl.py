"""
PrecioPartes ETL
================
Normaliza listas de precios de múltiples proveedores a un esquema único.

Esquema unificado (tabla: partes):
    id              SERIAL PK
    proveedor_id    FK -> proveedores
    referencia      TEXT    — código tal como viene en el archivo
    referencia_norm TEXT    — código normalizado (sin sufijo P, sin guiones, uppercase)
    equivalencia    TEXT    — código alternativo / equivalencia
    descripcion     TEXT
    vehiculo        TEXT
    marca_vehiculo  TEXT
    precio          NUMERIC
    precio_con_desc NUMERIC — precio después de aplicar descuento (si aplica)
    descuento_pct   NUMERIC — % de descuento si viene en la lista
    moneda          TEXT    default 'COP'
    fecha_lista     DATE    — fecha de la lista (del nombre del archivo o metadato)
    archivo_origen  TEXT    — nombre del archivo fuente
    sheet_origen    TEXT    — nombre de la hoja dentro del Excel
    creado_en       TIMESTAMP default now()

Proveedores soportados (auto-detectados por estructura):
    - TIPO_DH      : DH_4350_*.xls  (cols: VEHICULO, REFERENCIA, EQUIVALENCIA, DESCRIPCION, MARCA, PRECIO)
    - TIPO_CAJAS   : Lista_CAJAS_*.xls (multi-sheet por marca, cols: Cod.UR, Referencia, Descripción, Precio, Descuento)
    - TIPO_LISTA_E : ListaPrecio*.xlsx (cols: CODIGO, DESCRIPCION, MARCA, GRUPO, PRECIO — con filas de categoría intercaladas)
"""

import re
import logging
from pathlib import Path
from datetime import date, datetime
from typing import Optional

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

TIPO_DH = "DH"
TIPO_CAJAS = "CAJAS"
TIPO_LISTA_E = "LISTA_E"
TIPO_DESCONOCIDO = "DESCONOCIDO"


# ---------------------------------------------------------------------------
# Helpers de limpieza
# ---------------------------------------------------------------------------

def limpiar_precio(valor) -> Optional[float]:
    """
    Convierte cualquier representación de precio a float.
    Maneja: '$ 396.197', '396197', '396,197', 1426600.0, None, nan
    Retorna None si no se puede convertir.
    """
    if valor is None:
        return None
    s = str(valor).strip()
    if s.lower() in ("nan", "", "precio", "valor"):
        return None
    # Quitar símbolo de moneda y espacios
    s = re.sub(r"[$\s]", "", s)
    # Colombiano: punto como separador de miles, coma como decimal
    # Detectar: si hay punto Y coma → punto=miles, coma=decimal
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "." in s:
        # Si el punto separa exactamente 3 dígitos al final → es miles
        partes = s.split(".")
        if all(len(p) == 3 for p in partes[1:]):
            s = s.replace(".", "")
        # Si no, es decimal normal (ej: 1990.5)
    elif "," in s:
        s = s.replace(",", ".")
    try:
        val = float(s)
        return val if val > 0 else None
    except ValueError:
        logger.warning(f"No se pudo parsear precio: '{valor}' → '{s}'")
        return None


def normalizar_referencia(ref: str) -> str:
    """
    Normaliza un código de referencia OEM para comparación cruzada.
    Ejemplos:
        '96335952P'  → '96335952'   (quitar sufijo P de variante original)
        '56500-2S000' → '565002S000' (quitar guiones)
        ' 31112-07000 ' → '3111207000'
    """
    if not ref or ref.lower() == "nan":
        return ""
    r = str(ref).strip().upper()
    # Quitar sufijo P solo si viene al final de un código alfanumérico
    if r.endswith("P") and len(r) > 3 and r[-2].isdigit():
        r = r[:-1]
    # Quitar caracteres no alfanuméricos para comparación
    r = re.sub(r"[^A-Z0-9]", "", r)
    return r


def extraer_fecha_archivo(nombre: str) -> Optional[date]:
    """
    Intenta extraer fecha del nombre del archivo.
    Soporta: JUNIO_2026, 20260619, 26_junio, jun_2026
    """
    nombre_upper = nombre.upper()
    meses = {
        "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
        "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
        "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
        "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAY": 5, "JUN": 6,
        "JUL": 7, "AUG": 8, "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
    }
    # Formato YYYYMMDD
    m = re.search(r"(\d{4})(\d{2})(\d{2})", nombre)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    # Formato DIA_MES o MES_AÑO
    for mes_nombre, mes_num in meses.items():
        if mes_nombre in nombre_upper:
            year_m = re.search(r"(20\d{2})", nombre)
            year = int(year_m.group(1)) if year_m else datetime.now().year
            day_m = re.search(r"(\d{1,2})_?" + mes_nombre, nombre_upper)
            day = int(day_m.group(1)) if day_m else 1
            try:
                return date(year, mes_num, day)
            except ValueError:
                return date(year, mes_num, 1)
    return None


def limpiar_texto(val) -> str:
    if val is None or str(val).lower() == "nan":
        return ""
    return " ".join(str(val).strip().split())  # colapsa espacios múltiples


# ---------------------------------------------------------------------------
# Detección de tipo de archivo
# ---------------------------------------------------------------------------

def detectar_tipo(path: Path, df_primera_hoja: pd.DataFrame) -> str:
    """
    Detecta el tipo de proveedor leyendo las columnas de la primera hoja.
    """
    cols = [str(c).strip().upper() for c in df_primera_hoja.columns]
    cols_str = " ".join(cols)

    # Revisa también primeras filas (algunos archivos tienen encabezado en fila 4+)
    primeras_filas = " ".join(
        df_primera_hoja.iloc[:8].astype(str).values.flatten().tolist()
    ).upper()

    if "VEHICULO" in cols_str and "REFERENCIA" in cols_str and "EQUIVALENCIA" in cols_str:
        return TIPO_DH

    if "COD.UR" in primeras_filas or "DESCRIPCIÓN" in primeras_filas and "PRECIO" in primeras_filas:
        return TIPO_CAJAS

    if "CODIGO" in cols_str or "CODIGO" in primeras_filas:
        return TIPO_LISTA_E

    # Fallback: revisar nombre del archivo
    nombre = path.name.upper()
    if "DH_" in nombre:
        return TIPO_DH
    if "CAJAS" in nombre or "DIRECCION" in nombre:
        return TIPO_CAJAS
    if "LISTA" in nombre or "PRECIO" in nombre:
        return TIPO_LISTA_E

    return TIPO_DESCONOCIDO


# ---------------------------------------------------------------------------
# Parsers por tipo
# ---------------------------------------------------------------------------

def _parse_dh(path: Path, proveedor_nombre: str, fecha_lista: Optional[date]) -> list[dict]:
    """
    Parser para archivos tipo DH_4350_*.
    Columnas: VEHICULO, REFERENCIA, EQUIVALENCIA, DESCRIPCION, MARCA, PRECIO, EMP, (extra)
    """
    engine = "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"
    xl = pd.ExcelFile(path, engine=engine)
    registros = []

    for sheet in xl.sheet_names:
        try:
            df = pd.read_excel(path, sheet_name=sheet, engine=engine, header=0)
        except Exception as e:
            logger.error(f"[DH] Error leyendo hoja '{sheet}' de {path.name}: {e}")
            continue

        # Mapear columnas flexiblemente (los archivos pueden tener distintos nombres)
        col_map = {}
        for col in df.columns:
            cu = str(col).strip().upper()
            if "VEHICULO" in cu or "VEHÍCULO" in cu:
                col_map["vehiculo"] = col
            elif "REFERENCIA" in cu:
                col_map["referencia"] = col
            elif "EQUIVALENCIA" in cu:
                col_map["equivalencia"] = col
            elif "DESCRIPCION" in cu or "DESCRIPCIÓN" in cu:
                col_map["descripcion"] = col
            elif "MARCA" in cu:
                col_map["marca"] = col
            elif "PRECIO" in cu:
                col_map["precio"] = col

        campos_requeridos = ["referencia", "descripcion", "precio"]
        if not all(c in col_map for c in campos_requeridos):
            logger.warning(f"[DH] Hoja '{sheet}' sin columnas requeridas. Cols: {list(df.columns)}")
            continue

        for idx, row in df.iterrows():
            ref_raw = limpiar_texto(row.get(col_map.get("referencia", ""), ""))
            desc = limpiar_texto(row.get(col_map.get("descripcion", ""), ""))
            precio = limpiar_precio(row.get(col_map.get("precio", ""), None))

            if not ref_raw or not desc or precio is None:
                continue

            registros.append({
                "proveedor_nombre": proveedor_nombre,
                "referencia": ref_raw,
                "referencia_norm": normalizar_referencia(ref_raw),
                "equivalencia": limpiar_texto(row.get(col_map.get("equivalencia", ""), "")),
                "descripcion": desc,
                "vehiculo": limpiar_texto(row.get(col_map.get("vehiculo", ""), "")),
                "marca_vehiculo": limpiar_texto(row.get(col_map.get("marca", ""), "")),
                "precio": precio,
                "precio_con_desc": precio,  # DH no tiene descuento
                "descuento_pct": 0.0,
                "moneda": "COP",
                "fecha_lista": fecha_lista,
                "archivo_origen": path.name,
                "sheet_origen": sheet,
            })

    logger.info(f"[DH] {path.name}: {len(registros)} registros válidos")
    return registros


def _parse_cajas(path: Path, proveedor_nombre: str, fecha_lista: Optional[date]) -> list[dict]:
    """
    Parser para Lista_CAJAS_DE_DIRECCION_*.
    Multi-sheet (una por marca). Header en fila variable (buscar fila con 'Referencia').
    Precio: '$ 396.197' → 396197
    Tiene columna Descuento.
    """
    engine = "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"
    xl = pd.ExcelFile(path, engine=engine)
    registros = []

    for sheet in xl.sheet_names:
        try:
            df_raw = pd.read_excel(path, sheet_name=sheet, engine=engine, header=None)
        except Exception as e:
            logger.error(f"[CAJAS] Error leyendo hoja '{sheet}': {e}")
            continue

        # Buscar fila de encabezado
        header_row = None
        for i, row in df_raw.iterrows():
            vals_upper = [str(v).strip().upper() for v in row.values]
            if "REFERENCIA" in vals_upper or "DESCRIPCIÓN" in vals_upper or "DESCRIPCION" in vals_upper:
                header_row = i
                break

        if header_row is None:
            logger.warning(f"[CAJAS] Hoja '{sheet}': no se encontró fila de encabezado")
            continue

        try:
            df = pd.read_excel(path, sheet_name=sheet, engine=engine, header=header_row)
        except Exception as e:
            logger.error(f"[CAJAS] Error re-leyendo con header={header_row}: {e}")
            continue

        # Mapeo flexible de columnas
        col_map = {}
        for col in df.columns:
            cu = str(col).strip().upper()
            if "REFERENCIA" in cu:
                col_map["referencia"] = col
            elif "COD" in cu and "UR" in cu:
                col_map["cod_ur"] = col
            elif "DESCRIPCI" in cu:
                col_map["descripcion"] = col
            elif "EQUIVALENCIA" in cu or "EQUIV" in cu:
                col_map["equivalencia"] = col
            elif "MARCA" in cu:
                col_map["marca"] = col
            elif "PRECIO" in cu:
                col_map["precio"] = col
            elif "DESCUENTO" in cu:
                col_map["descuento"] = col

        if "referencia" not in col_map or "precio" not in col_map:
            logger.warning(f"[CAJAS] Hoja '{sheet}': faltan columnas clave. Map: {col_map}")
            continue

        for idx, row in df.iterrows():
            ref_raw = limpiar_texto(row.get(col_map.get("referencia", ""), ""))
            desc = limpiar_texto(row.get(col_map.get("descripcion", ""), ""))
            precio = limpiar_precio(row.get(col_map.get("precio", ""), None))

            if not ref_raw or not desc or precio is None:
                continue

            # Manejar descuento
            desc_pct = 0.0
            precio_con_desc = precio
            if "descuento" in col_map:
                d = limpiar_precio(row.get(col_map["descuento"], None))
                if d and 0 < d < 100:
                    desc_pct = d
                    precio_con_desc = round(precio * (1 - d / 100), 2)

            registros.append({
                "proveedor_nombre": proveedor_nombre,
                "referencia": ref_raw,
                "referencia_norm": normalizar_referencia(ref_raw),
                "equivalencia": limpiar_texto(row.get(col_map.get("equivalencia", ""), "")),
                "descripcion": desc,
                "vehiculo": sheet,  # La hoja es la marca del vehículo
                "marca_vehiculo": limpiar_texto(row.get(col_map.get("marca", ""), "")),
                "precio": precio,
                "precio_con_desc": precio_con_desc,
                "descuento_pct": desc_pct,
                "moneda": "COP",
                "fecha_lista": fecha_lista,
                "archivo_origen": path.name,
                "sheet_origen": sheet,
            })

    logger.info(f"[CAJAS] {path.name}: {len(registros)} registros válidos")
    return registros


def _parse_lista_e(path: Path, proveedor_nombre: str, fecha_lista: Optional[date]) -> list[dict]:
    """
    Parser para ListaPrecio*.xlsx.
    Columnas: CODIGO, DESCRIPCION, MARCA, GRUPO, PRECIO
    Filas de categoría intercaladas (sin precio numérico) → ignorar.
    No tiene columna VEHICULO → usar MARCA como vehiculo.
    """
    engine = "openpyxl" if path.suffix.lower() == ".xlsx" else "xlrd"
    xl = pd.ExcelFile(path, engine=engine)
    registros = []

    for sheet in xl.sheet_names:
        try:
            df_raw = pd.read_excel(path, sheet_name=sheet, engine=engine, header=None)
        except Exception as e:
            logger.error(f"[LISTA_E] Error leyendo hoja '{sheet}': {e}")
            continue

        # Buscar fila de encabezado (contiene CODIGO)
        header_row = None
        for i, row in df_raw.iterrows():
            vals_upper = [str(v).strip().upper() for v in row.values]
            if "CODIGO" in vals_upper or "CÓDIGO" in vals_upper:
                header_row = i
                break

        if header_row is None:
            logger.warning(f"[LISTA_E] Hoja '{sheet}': no se encontró encabezado con CODIGO")
            continue

        try:
            df = pd.read_excel(path, sheet_name=sheet, engine=engine, header=header_row)
        except Exception as e:
            logger.error(f"[LISTA_E] Error re-leyendo: {e}")
            continue

        # Mapeo flexible
        col_map = {}
        for col in df.columns:
            cu = str(col).strip().upper()
            if "CODIGO" in cu or "CÓDIGO" in cu:
                col_map["referencia"] = col
            elif "DESCRIPCION" in cu or "DESCRIPCIÓN" in cu:
                col_map["descripcion"] = col
            elif "MARCA" in cu:
                col_map["marca"] = col
            elif "GRUPO" in cu:
                col_map["grupo"] = col
            elif "PRECIO" in cu:
                col_map["precio"] = col

        if "referencia" not in col_map or "precio" not in col_map:
            logger.warning(f"[LISTA_E] Hoja '{sheet}': faltan columnas. Map: {col_map}")
            continue

        categoria_actual = ""
        for idx, row in df.iterrows():
            ref_raw = limpiar_texto(row.get(col_map.get("referencia", ""), ""))
            precio_raw = row.get(col_map.get("precio", ""), None)
            precio = limpiar_precio(precio_raw)

            # Si no hay precio numérico → es fila de categoría, guardar para contexto
            if precio is None:
                if ref_raw:
                    categoria_actual = ref_raw
                continue

            desc = limpiar_texto(row.get(col_map.get("descripcion", ""), ""))
            marca = limpiar_texto(row.get(col_map.get("marca", ""), ""))

            if not ref_raw or not desc:
                continue

            registros.append({
                "proveedor_nombre": proveedor_nombre,
                "referencia": ref_raw,
                "referencia_norm": normalizar_referencia(ref_raw),
                "equivalencia": "",
                "descripcion": desc,
                "vehiculo": marca,  # MARCA es el vehículo en este formato
                "marca_vehiculo": marca,
                "precio": precio,
                "precio_con_desc": precio,
                "descuento_pct": 0.0,
                "moneda": "COP",
                "fecha_lista": fecha_lista,
                "archivo_origen": path.name,
                "sheet_origen": sheet,
            })

    logger.info(f"[LISTA_E] {path.name}: {len(registros)} registros válidos")
    return registros


# ---------------------------------------------------------------------------
# Entry point principal
# ---------------------------------------------------------------------------

def procesar_archivo(
    path: Path,
    proveedor_nombre: str,
    tipo: Optional[str] = None,
) -> list[dict]:
    """
    Procesa un archivo Excel y retorna lista de dicts listos para insertar en DB.

    Args:
        path: Ruta al archivo .xls o .xlsx
        proveedor_nombre: Nombre del proveedor (ej: "DH Repuestos Corea")
        tipo: TIPO_DH | TIPO_CAJAS | TIPO_LISTA_E | None (auto-detectar)

    Returns:
        Lista de registros normalizados. Nunca lanza excepción — errores van al log.
    """
    if not path.exists():
        logger.error(f"Archivo no encontrado: {path}")
        return []

    fecha_lista = extraer_fecha_archivo(path.name)

    # Auto-detectar tipo si no viene explícito
    if tipo is None:
        engine = "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"
        try:
            df_preview = pd.read_excel(path, engine=engine, header=None, nrows=10)
            tipo = detectar_tipo(path, df_preview)
        except Exception as e:
            logger.error(f"Error leyendo preview de {path.name}: {e}")
            return []

    logger.info(f"Procesando {path.name} | tipo={tipo} | proveedor={proveedor_nombre} | fecha={fecha_lista}")

    parsers = {
        TIPO_DH: _parse_dh,
        TIPO_CAJAS: _parse_cajas,
        TIPO_LISTA_E: _parse_lista_e,
    }

    parser = parsers.get(tipo)
    if parser is None:
        logger.error(f"Tipo de archivo no soportado: {tipo} ({path.name})")
        return []

    try:
        return parser(path, proveedor_nombre, fecha_lista)
    except Exception as e:
        logger.exception(f"Error inesperado procesando {path.name}: {e}")
        return []
