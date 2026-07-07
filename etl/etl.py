"""
PrecioPartes ETL — normaliza listas de precios de multiples proveedores.
"""

import logging
import re
from datetime import date, datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from limpieza import (
    consolidar_registros,
    construir_registro,
    limpiar_precio,
    limpiar_referencia,
    limpiar_texto,
    validar_lote,
)

logger = logging.getLogger(__name__)

TIPO_DH = "DH"
TIPO_CAJAS = "CAJAS"
TIPO_LISTA_E = "LISTA_E"
TIPO_TABULAR = "TABULAR"
TIPO_OBYCO = "OBYCO"
TIPO_DESCONOCIDO = "DESCONOCIDO"

EXTENSIONES_EXCEL = (".xls", ".xlsx", ".xlsm")


def extraer_fecha_archivo(nombre: str) -> Optional[date]:
    nombre_upper = nombre.upper()
    meses = {
        "ENERO": 1, "FEBRERO": 2, "MARZO": 3, "ABRIL": 4,
        "MAYO": 5, "JUNIO": 6, "JULIO": 7, "AGOSTO": 8,
        "SEPTIEMBRE": 9, "OCTUBRE": 10, "NOVIEMBRE": 11, "DICIEMBRE": 12,
    }
    m = re.search(r"(20\d{2})(\d{2})(\d{2})", nombre)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            pass
    for mes_nombre, mes_num in meses.items():
        if mes_nombre in nombre_upper:
            year_m = re.search(r"(20\d{2})", nombre)
            year = int(year_m.group(1)) if year_m else datetime.now().year
            day_m = re.search(r"(\d{1,2})[\s_\-]?" + mes_nombre, nombre_upper)
            day = int(day_m.group(1)) if day_m else 1
            try:
                return date(year, mes_num, day)
            except ValueError:
                return date(year, mes_num, 1)
    return None


def _nombre_compacto(path: Path) -> str:
    return re.sub(r"[\s_\-\+#]+", "", path.name.upper())


def _engine_excel(path: Path) -> str:
    return "xlrd" if path.suffix.lower() == ".xls" else "openpyxl"


def _texto_preview(df: pd.DataFrame, filas: int = 20) -> str:
    partes = []
    for v in df.iloc[:filas].values.flatten():
        if v is None or (isinstance(v, float) and pd.isna(v)):
            continue
        s = str(v).strip()
        if s and s.lower() not in ("nan", "none", "nat"):
            partes.append(s)
    return " ".join(partes).upper()


def _hojas_ignorar(path: Path) -> frozenset[str]:
    nombre = _nombre_compacto(path)
    if "VENDEDORES" in nombre:
        return frozenset({"HOJAS", "PEDIDO"})
    return frozenset()


def _buscar_fila_encabezado(df_raw: pd.DataFrame, marcadores: tuple = ("REFERENCIA", "PRECIO")) -> Optional[int]:
    patrones = [
        ("REFERENCIA", "PRECIO"),
        ("REFERENCIA", "VENTA"),
        ("REFERENCIA", "PRECIO VENTA"),
        ("CODIGO", "PRECIO"),
        ("CÓDIGO", "PRECIO"),
        ("CODIGO", "REFERENCIA"),
        ("VEHICULO", "REFERENCIA"),
        ("COD.UR", "REFERENCIA"),
        ("REFERENCIA", "NOMBRE"),
    ]
    for i, row in df_raw.iterrows():
        vals = " ".join(
            str(v).strip().upper()
            for v in row.values
            if v is not None and str(v).strip().lower() not in ("nan", "none", "")
        )
        if not vals:
            continue
        for a, b in patrones:
            if a in vals and b in vals:
                return int(i)
        if "V.MAYOR" in vals and ("CODIGO" in vals or "CÓDIGO" in vals):
            return int(i)
        if "ETIQUETAS DE FILA" in vals and "REFERENCIA" in vals:
            return int(i)
        if all(m in vals for m in marcadores):
            return int(i)
    return None


def _mapear_columnas(df: pd.DataFrame) -> dict:
    """Mapeo flexible de columnas Excel a campos internos."""
    col_map: dict = {}
    for col in df.columns:
        cu = str(col).strip().upper()
        if cu in ("NAN", "NONE", "NAT", ""):
            continue
        if ("VEHICULO" in cu or "VEHÍCULO" in cu) and "vehiculo" not in col_map:
            col_map["vehiculo"] = col
        elif "REFERENCIA" in cu and "referencia" not in col_map:
            col_map["referencia"] = col
        elif ("CODIGO" in cu or "CÓDIGO" in cu) and "codigo" not in col_map:
            col_map["codigo"] = col
        elif "COD.UR" in cu or cu == "COD UR":
            col_map["cod_ur"] = col
        elif "EQUIVALENCIA" in cu or "EQUIV" in cu:
            col_map["equivalencia"] = col
        elif "DESCRIPCI" in cu and "descripcion" not in col_map:
            col_map["descripcion"] = col
        elif "ETIQUETA" in cu and "FILA" in cu:
            col_map["descripcion"] = col
        elif "NOMBRE" in cu and "descripcion" not in col_map:
            col_map["descripcion"] = col
        elif cu == "MODELO" and "vehiculo" not in col_map:
            col_map["vehiculo"] = col
        elif "MARCA" in cu and "marca" not in col_map:
            col_map["marca"] = col
        elif "PRECIO VENTA" in cu:
            col_map["precio"] = col
        elif "V.MAYOR" in cu or "V MAYOR" in cu:
            col_map["precio"] = col
        elif "VENTA" in cu and "precio" not in col_map:
            col_map["precio"] = col
        elif "PRECIO" in cu and "precio" not in col_map:
            col_map["precio"] = col
        elif cu == "TOTAL":
            col_map["precio_total"] = col
        elif "DESCUENTO" in cu:
            col_map["descuento"] = col

    cols_upper = {str(c).strip().upper() for c in df.columns}
    tiene_v_mayor = any("V.MAYOR" in c or "V MAYOR" in c for c in cols_upper)

    if tiene_v_mayor and col_map.get("codigo"):
        col_map["equivalencia"] = col_map.get("referencia") or col_map.get("equivalencia")
        col_map["referencia"] = col_map["codigo"]

    if col_map.get("cod_ur") and not col_map.get("referencia"):
        col_map["referencia"] = col_map["cod_ur"]
    elif col_map.get("cod_ur") and col_map.get("referencia") and col_map["cod_ur"] != col_map["referencia"]:
        col_map.setdefault("equivalencia", col_map["cod_ur"])

    if not col_map.get("referencia") and col_map.get("codigo"):
        col_map["referencia"] = col_map["codigo"]

    return col_map


def _fila_es_categoria(row, col_map: dict) -> bool:
    ref_raw = row.get(col_map.get("referencia", ""), "")
    cod_raw = row.get(col_map.get("codigo", ""), "")
    ref = limpiar_referencia(ref_raw)
    cod = limpiar_texto(cod_raw)
    if str(ref_raw).strip() in ("=", "_") or str(cod_raw).strip() in ("=", "_"):
        return True
    if cod.startswith("01-") or cod.startswith("01 "):
        return True
    desc = limpiar_texto(row.get(col_map.get("descripcion", ""), ""))
    if desc and re.match(r"^\d{2}\s", desc) and limpiar_precio(row.get(col_map.get("precio"), None)) is None:
        return True
    precio_col = col_map.get("precio") or col_map.get("precio_total")
    if precio_col is None:
        return True
    if limpiar_precio(row.get(precio_col, None)) is None:
        return True
    return False


def detectar_tipo(path: Path, df_primera_hoja: pd.DataFrame) -> str:
    """Detecta formato: primero por nombre de archivo, luego por contenido."""
    compacto = _nombre_compacto(path)
    primeras_filas = _texto_preview(df_primera_hoja)

    if "OBYCO" in compacto or "ETIQUETAS DE FILA" in primeras_filas:
        return TIPO_OBYCO
    if any(k in compacto for k in ("CAJAS", "DIRECCION", "DRIECCION")):
        return TIPO_CAJAS
    if "DH4350" in compacto or (
        compacto.startswith("DH") and ("COREA" in compacto or "SOPORTES" in compacto)
    ):
        return TIPO_DH
    if "LISTAPORVEHICULO" in compacto:
        return TIPO_DH

    if "V.MAYOR" in primeras_filas or "V MAYOR" in primeras_filas:
        return TIPO_TABULAR
    if "TAIHO" in compacto or "VENTANAS" in compacto:
        return TIPO_TABULAR
    if "CODIGO" in primeras_filas and "REFERENCIA" in primeras_filas and "VENTA" in primeras_filas:
        return TIPO_TABULAR
    if "PRECIO VENTA" in primeras_filas:
        return TIPO_TABULAR
    if "COD.UR" in primeras_filas or "CODUR" in primeras_filas.replace(".", ""):
        return TIPO_CAJAS
    if "LISTAPRECIO" in compacto or "INDUFAROS" in compacto:
        return TIPO_LISTA_E
    if ("CODIGO" in primeras_filas or "CÓDIGO" in primeras_filas) and (
        "GRUPO" in primeras_filas or "MARCA" in primeras_filas
    ):
        return TIPO_LISTA_E

    if "REFERENCIA" in primeras_filas and (
        "PRECIO" in primeras_filas or "VENTA" in primeras_filas or "NOMBRE" in primeras_filas
    ):
        if "VEHICULO" in primeras_filas or "EQUIVALENCIA" in primeras_filas:
            return TIPO_DH
        return TIPO_TABULAR

    if ("DESCRIPCION" in primeras_filas or "DESCRIPCIÓN" in primeras_filas) and (
        "PRECIO" in primeras_filas or "VENTA" in primeras_filas
    ):
        return TIPO_TABULAR

    return TIPO_DESCONOCIDO


def detectar_proveedor_nombre(path: Path, tipo: Optional[str] = None) -> str:
    nombre = _nombre_compacto(path)

    reglas = [
        ("SOPORTES", "DH Soportes"),
        ("CAJAS", "Cajas de Dirección"),
        ("DIRECCION", "Cajas de Dirección"),
        ("DRIECCION", "Cajas de Dirección"),
        ("FLORIDA", "Florida Importaciones"),
        ("PUNTOCOREA", "Punto Corea"),
        ("OBYCO", "OBYCO"),
        ("INDUFAROS", "Indufaros"),
        ("TAIHO", "Taiho"),
        ("OCCIDENTE", "Autopartes de Occidente"),
        ("CONSOLIDADO", "Consolidado Mayor"),
        ("REDPARTES", "Redpartes OSRAM"),
        ("VENTANAS", "Redpartes OSRAM"),
        ("OSRAM", "Redpartes OSRAM"),
        ("LISTAPORVEHICULOJAPON", "Lista por Vehículo Japón"),
        ("LISTAPORVEHICULOKOREA", "Lista por Vehículo Korea"),
        ("DH4350COREA", "DH Repuestos Corea"),
        ("LISTAGENERAL", "Lista General UR"),
        ("VENDEDORES", "Lista Vendedores"),
    ]
    for clave, proveedor in reglas:
        if clave in nombre:
            return proveedor

    if "COREA" in nombre and "PUNTO" not in nombre:
        return "DH Repuestos Corea"
    if "LISTAPRECIO" in nombre:
        return "Lista Precio E"
    if tipo == TIPO_DH:
        return "DH Repuestos Corea"
    if tipo == TIPO_CAJAS:
        return "Cajas de Dirección"
    if tipo == TIPO_LISTA_E:
        return "Lista Precio E"

    stem = re.sub(r"[_\-#]+", " ", path.stem).strip()
    return stem[:80] if stem else "Proveedor desconocido"


def _leer_hoja_con_encabezado(path: Path, sheet: str, engine: str) -> Optional[pd.DataFrame]:
    try:
        df_raw = pd.read_excel(path, sheet_name=sheet, engine=engine, header=None)
    except Exception as e:
        logger.error("Error leyendo hoja '%s' de %s: %s", sheet, path.name, e)
        return None

    header_row = _buscar_fila_encabezado(df_raw)
    if header_row is None:
        header_row = 0

    try:
        return pd.read_excel(path, sheet_name=sheet, engine=engine, header=header_row)
    except Exception as e:
        logger.error("Error re-leyendo hoja '%s' header=%s: %s", sheet, header_row, e)
        return None


def _parse_dh(path: Path, proveedor_nombre: str, fecha_lista: Optional[date]) -> list[dict]:
    engine = _engine_excel(path)
    xl = pd.ExcelFile(path, engine=engine)
    registros = []

    for sheet in xl.sheet_names:
        df = _leer_hoja_con_encabezado(path, sheet, engine)
        if df is None:
            continue

        col_map = _mapear_columnas(df)
        if not all(k in col_map for k in ("referencia", "descripcion", "precio")):
            logger.warning("[DH] Hoja '%s' sin columnas requeridas: %s", sheet, list(df.columns))
            continue

        for _, row in df.iterrows():
            reg = construir_registro(
                proveedor_nombre=proveedor_nombre,
                referencia_raw=row.get(col_map["referencia"], ""),
                descripcion_raw=row.get(col_map["descripcion"], ""),
                precio_raw=row.get(col_map["precio"], None),
                equivalencia_raw=row.get(col_map.get("equivalencia", ""), ""),
                vehiculo_raw=row.get(col_map.get("vehiculo", ""), ""),
                marca_vehiculo_raw=row.get(col_map.get("marca", ""), ""),
                fecha_lista=fecha_lista,
                archivo_origen=path.name,
                sheet_origen=sheet,
            )
            if reg:
                registros.append(reg)

    logger.info("[DH] %s: %d registros validos", path.name, len(registros))
    return registros


def _parse_cajas(path: Path, proveedor_nombre: str, fecha_lista: Optional[date]) -> list[dict]:
    engine = _engine_excel(path)
    xl = pd.ExcelFile(path, engine=engine)
    registros = []

    for sheet in xl.sheet_names:
        df = _leer_hoja_con_encabezado(path, sheet, engine)
        if df is None:
            continue

        col_map = _mapear_columnas(df)
        if "referencia" not in col_map or "precio" not in col_map:
            logger.warning("[CAJAS] Hoja '%s' faltan columnas: %s", sheet, col_map)
            continue

        for _, row in df.iterrows():
            reg = construir_registro(
                proveedor_nombre=proveedor_nombre,
                referencia_raw=row.get(col_map["referencia"], ""),
                descripcion_raw=row.get(col_map.get("descripcion", ""), ""),
                precio_raw=row.get(col_map["precio"], None),
                equivalencia_raw=row.get(col_map.get("equivalencia", ""), ""),
                vehiculo_raw=sheet,
                marca_vehiculo_raw=row.get(col_map.get("marca", ""), ""),
                descuento_raw=row.get(col_map.get("descuento"), None),
                fecha_lista=fecha_lista,
                archivo_origen=path.name,
                sheet_origen=sheet,
            )
            if reg:
                registros.append(reg)

    logger.info("[CAJAS] %s: %d registros validos", path.name, len(registros))
    return registros


def _parse_lista_e(path: Path, proveedor_nombre: str, fecha_lista: Optional[date]) -> list[dict]:
    engine = _engine_excel(path)
    xl = pd.ExcelFile(path, engine=engine)
    registros = []

    # Algunos archivos traen la misma lista en 2 hojas (ej. Lista Completa + HYUNDAI-KIA KO).
    hojas = list(xl.sheet_names)
    if len(hojas) >= 2:
        tiene_completa = any(
            "COMPLETA" in s.upper() and "MARCA" in s.upper() for s in hojas
        )
        if tiene_completa:
            hojas = [
                s for s in hojas
                if not ("HYUNDAI" in s.upper() and "KIA" in s.upper())
            ]
            logger.info("[LISTA_E] %s: omitiendo hoja duplicada HYUNDAI-KIA KO", path.name)

    for sheet in hojas:
        df = _leer_hoja_con_encabezado(path, sheet, engine)
        if df is None:
            continue

        col_map = _mapear_columnas(df)
        if "referencia" not in col_map or "precio" not in col_map:
            logger.warning("[LISTA_E] Hoja '%s' faltan columnas: %s", sheet, col_map)
            continue

        for _, row in df.iterrows():
            precio_raw = row.get(col_map["precio"], None)
            ref_raw = row.get(col_map["referencia"], "")

            # Filas de categoria (titulo sin precio valido)
            if limpiar_precio(precio_raw) is None:
                continue

            marca = limpiar_texto(row.get(col_map.get("marca", ""), ""))
            reg = construir_registro(
                proveedor_nombre=proveedor_nombre,
                referencia_raw=ref_raw,
                descripcion_raw=row.get(col_map.get("descripcion", ""), ""),
                precio_raw=precio_raw,
                vehiculo_raw="",
                marca_vehiculo_raw=marca,
                fecha_lista=fecha_lista,
                archivo_origen=path.name,
                sheet_origen=sheet,
            )
            if reg:
                registros.append(reg)

    logger.info("[LISTA_E] %s: %d registros validos", path.name, len(registros))
    return registros


def _parse_tabular(path: Path, proveedor_nombre: str, fecha_lista: Optional[date]) -> list[dict]:
    """Formato tabular generico: consolidado, occidente, taiho, punto corea, vendedores, ventanas."""
    engine = _engine_excel(path)
    xl = pd.ExcelFile(path, engine=engine)
    ignorar = _hojas_ignorar(path)
    registros = []

    for sheet in xl.sheet_names:
        if sheet.strip().upper() in ignorar:
            continue

        df = _leer_hoja_con_encabezado(path, sheet, engine)
        if df is None or df.empty:
            continue

        col_map = _mapear_columnas(df)
        if "referencia" not in col_map or ("precio" not in col_map and "precio_total" not in col_map):
            logger.warning("[TABULAR] Hoja '%s' sin columnas clave: %s", sheet, col_map)
            continue

        precio_col = col_map.get("precio") or col_map.get("precio_total")

        for _, row in df.iterrows():
            if _fila_es_categoria(row, col_map):
                continue

            reg = construir_registro(
                proveedor_nombre=proveedor_nombre,
                referencia_raw=row.get(col_map["referencia"], ""),
                descripcion_raw=row.get(col_map.get("descripcion", ""), ""),
                precio_raw=row.get(precio_col, None),
                equivalencia_raw=row.get(col_map.get("equivalencia", ""), ""),
                vehiculo_raw=row.get(col_map.get("vehiculo", ""), "") or sheet,
                marca_vehiculo_raw=row.get(col_map.get("marca", ""), ""),
                descuento_raw=row.get(col_map.get("descuento"), None),
                fecha_lista=fecha_lista,
                archivo_origen=path.name,
                sheet_origen=sheet,
            )
            if reg:
                registros.append(reg)

    logger.info("[TABULAR] %s: %d registros validos", path.name, len(registros))

    if "TAIHO" in _nombre_compacto(path):
        registros.extend(_parse_taiho_sin_encabezado(path, engine, proveedor_nombre, fecha_lista))

    return registros


def _parse_taiho_sin_encabezado(
    path: Path, engine: str, proveedor_nombre: str, fecha_lista: Optional[date]
) -> list[dict]:
    """Hoja1 de Taiho viene sin fila de encabezado; reutiliza columnas de Sheet1."""
    extra: list[dict] = []
    try:
        df_header = pd.read_excel(path, sheet_name="Sheet1", engine=engine, header=None)
        header_row = _buscar_fila_encabezado(df_header)
        if header_row is None:
            return extra
        headers = [str(h).strip() for h in df_header.iloc[header_row].tolist()]
        df = pd.read_excel(path, sheet_name="Hoja1", engine=engine, header=None, names=headers)
    except Exception as e:
        logger.warning("[TAIHO] No se pudo leer Hoja1 de %s: %s", path.name, e)
        return extra

    col_map = _mapear_columnas(df)
    if "referencia" not in col_map or "precio" not in col_map:
        return extra

    for _, row in df.iterrows():
        if _fila_es_categoria(row, col_map):
            continue
        reg = construir_registro(
            proveedor_nombre=proveedor_nombre,
            referencia_raw=row.get(col_map["referencia"], ""),
            descripcion_raw=row.get(col_map.get("descripcion", ""), ""),
            precio_raw=row.get(col_map["precio"], None),
            equivalencia_raw=row.get(col_map.get("equivalencia", ""), ""),
            vehiculo_raw="",
            marca_vehiculo_raw=row.get(col_map.get("marca", ""), ""),
            fecha_lista=fecha_lista,
            archivo_origen=path.name,
            sheet_origen="Hoja1",
        )
        if reg:
            extra.append(reg)

    if extra:
        logger.info("[TAIHO] %s Hoja1: %d registros extra", path.name, len(extra))
    return extra


def _parse_obyco(path: Path, proveedor_nombre: str, fecha_lista: Optional[date]) -> list[dict]:
    """Lista pivot OBYCO: descripcion en etiqueta de fila, precio en Total."""
    engine = _engine_excel(path)
    xl = pd.ExcelFile(path, engine=engine)
    registros = []

    for sheet in xl.sheet_names:
        df_raw = pd.read_excel(path, sheet_name=sheet, engine=engine, header=None)
        header_row = _buscar_fila_encabezado(df_raw)
        if header_row is None:
            continue

        df = pd.read_excel(path, sheet_name=sheet, engine=engine, header=header_row)
        col_map = _mapear_columnas(df)
        if "referencia" not in col_map:
            continue

        precio_col = col_map.get("precio_total") or col_map.get("precio")
        if not precio_col:
            continue

        for _, row in df.iterrows():
            desc = limpiar_texto(row.get(col_map.get("descripcion", ""), ""))
            if not desc or desc.startswith("01-"):
                continue
            if limpiar_precio(row.get(precio_col, None)) is None:
                continue

            reg = construir_registro(
                proveedor_nombre=proveedor_nombre,
                referencia_raw=row.get(col_map["referencia"], ""),
                descripcion_raw=desc,
                precio_raw=row.get(precio_col, None),
                equivalencia_raw=row.get(col_map.get("codigo", ""), ""),
                vehiculo_raw=limpiar_texto(row.get(col_map.get("vehiculo", ""), "")),
                marca_vehiculo_raw=row.get(col_map.get("marca", ""), ""),
                fecha_lista=fecha_lista,
                archivo_origen=path.name,
                sheet_origen=sheet,
            )
            if reg:
                registros.append(reg)

    logger.info("[OBYCO] %s: %d registros validos", path.name, len(registros))
    return registros


def _finalizar_registros(registros: list[dict], archivo: str) -> tuple[list[dict], dict]:
    """Consolidacion y validacion final antes de persistir."""
    n_parseadas = len(registros)
    registros, n_dup = consolidar_registros(registros, archivo)
    n_pre_valid = len(registros)
    registros = validar_lote(registros)
    n_final = len(registros)

    stats = {
        "filas_validas_parseadas": n_parseadas,
        "duplicados_exactos": n_dup,
        "rechazados_validacion": n_pre_valid - n_final,
        "filas_cargadas": n_final,
        "filas_descartadas_total": n_parseadas - n_final,
    }
    logger.info("[%s] Estadisticas ETL: %s", archivo, stats)
    return registros, stats


def procesar_archivo_detallado(
    path: Path,
    proveedor_nombre: str = "",
    tipo: Optional[str] = None,
) -> dict:
    resultado = {
        "registros": [],
        "archivo": path.name,
        "tipo_detectado": None,
        "proveedor_detectado": None,
        "formato_reconocido": False,
        "codigo_error": None,
        "mensaje": "",
        "filas_descartadas": 0,
        "estadisticas": {},
    }

    if not path.exists():
        resultado["codigo_error"] = "ARCHIVO_NO_ENCONTRADO"
        resultado["mensaje"] = "No se pudo leer el archivo."
        return resultado

    fecha_lista = extraer_fecha_archivo(path.name)
    tipo_explicito = tipo is not None

    if tipo is None:
        engine = _engine_excel(path)
        try:
            xl = pd.ExcelFile(path, engine=engine)
            sheet = xl.sheet_names[0]
            for candidata in xl.sheet_names:
                if candidata.strip().upper() not in _hojas_ignorar(path):
                    sheet = candidata
                    break
            df_preview = pd.read_excel(path, sheet_name=sheet, engine=engine, header=None, nrows=25)
            tipo = detectar_tipo(path, df_preview)
        except Exception as e:
            logger.error("Error leyendo preview de %s: %s", path.name, e)
            resultado["codigo_error"] = "ARCHIVO_ILEGIBLE"
            resultado["mensaje"] = (
                f"No se pudo abrir '{path.name}'. Verifica que sea un Excel valido (.xls / .xlsx)."
            )
            return resultado

    resultado["tipo_detectado"] = tipo

    if tipo == TIPO_DESCONOCIDO and not tipo_explicito:
        resultado["codigo_error"] = "FORMATO_DESCONOCIDO"
        resultado["mensaje"] = (
            f"Formato no reconocido: '{path.name}'. "
            "Copia este archivo a la carpeta listas/ y avisa al administrador para agregar reglas ETL."
        )
        return resultado

    if not proveedor_nombre or proveedor_nombre.startswith("proveedor_"):
        proveedor_nombre = detectar_proveedor_nombre(path, tipo)
    resultado["proveedor_detectado"] = proveedor_nombre

    parsers = {
        TIPO_DH: _parse_dh,
        TIPO_CAJAS: _parse_cajas,
        TIPO_LISTA_E: _parse_lista_e,
        TIPO_TABULAR: _parse_tabular,
        TIPO_OBYCO: _parse_obyco,
    }
    parser = parsers.get(tipo)
    if parser is None:
        resultado["codigo_error"] = "FORMATO_DESCONOCIDO"
        resultado["mensaje"] = (
            f"Tipo '{tipo}' no soportado en '{path.name}'. "
            "Copia el archivo a listas/ y solicita nuevas reglas ETL."
        )
        return resultado

    resultado["formato_reconocido"] = True
    logger.info(
        "Procesando %s | tipo=%s | proveedor=%s | fecha=%s",
        path.name, tipo, proveedor_nombre, fecha_lista,
    )

    try:
        raw = parser(path, proveedor_nombre, fecha_lista)
        registros, stats = _finalizar_registros(raw, path.name)
        resultado["filas_descartadas"] = stats["filas_descartadas_total"]
        resultado["estadisticas"] = stats
    except Exception as e:
        logger.exception("Error procesando %s: %s", path.name, e)
        resultado["codigo_error"] = "ERROR_PROCESAMIENTO"
        resultado["mensaje"] = f"Error procesando '{path.name}': {e}"
        return resultado

    if not registros:
        resultado["codigo_error"] = "SIN_REGISTROS"
        resultado["mensaje"] = (
            f"Formato detectado '{tipo}' pero '{path.name}' no produjo registros validos. "
            "Puede ser variante nueva: copia a listas/ y solicita ajuste de reglas."
        )
        return resultado

    resultado["registros"] = registros
    resultado["mensaje"] = (
        f"{len(registros):,} repuestos ({proveedor_nombre}, formato {tipo})"
    )
    return resultado


def procesar_archivo(
    path: Path,
    proveedor_nombre: str,
    tipo: Optional[str] = None,
) -> list[dict]:
    return procesar_archivo_detallado(path, proveedor_nombre, tipo)["registros"]


# Re-export para compatibilidad
from limpieza import limpiar_precio, normalizar_referencia  # noqa: E402
