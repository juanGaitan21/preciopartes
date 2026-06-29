"""Etiquetas legibles para el cliente final (marcas, vehiculos, descripciones)."""

import re

# Marcas exactas de listas Excel
_MARCA_EXACTA: dict[str, str] = {
    "HYUNDAI-KIA/KO": "Hyundai / Kia",
    "HYUNDAI-KIA": "Hyundai / Kia",
    "HYUNDAI/KIA": "Hyundai / Kia",
    "ISL-CARR*": "Carrocería",
    "ISL-ILUM*": "Iluminación",
    "ISL/MP": "Accesorios",
    "YULIM/KO": "Yulim",
    "HYUND": "Hyundai",
    "HYUNDAI": "Hyundai",
    "KIA": "Kia",
    "TOYOTA": "Toyota",
    "TY": "Toyota",
    "HY": "Hyundai",
    "KI": "Kia",
    "GM": "Chevrolet",
    "CHEVROLET": "Chevrolet",
    "RENAULT": "Renault",
    "NISSAN": "Nissan",
    "MAZDA": "Mazda",
    "FORD": "Ford",
    "SUZUKI": "Suzuki",
    "MITSUBISHI": "Mitsubishi",
    "HONDA": "Honda",
    "VOLKSWAGEN": "Volkswagen",
    "BMW": "BMW",
    "MERCEDES": "Mercedes-Benz",
    "MOTOR": "Motor (genérico)",
    "GATES": "Gates",
    "OEM": "OEM",
    "CTR": "CTR",
    "KBS": "KBS",
    "MAZDA GENUINO": "Mazda",
}

# Prefijos parciales (orden: mas especifico primero)
_MARCA_PREFIJOS: tuple[tuple[str, str], ...] = (
    ("HYUNDAI", "Hyundai"),
    ("CHEVROLET", "Chevrolet"),
    ("MITSUBISHI", "Mitsubishi"),
    ("MERCEDES", "Mercedes-Benz"),
    ("VOLKSWAGEN", "Volkswagen"),
    ("RENAULT", "Renault"),
    ("TOYOTA", "Toyota"),
    ("NISSAN", "Nissan"),
    ("MAZDA", "Mazda"),
    ("FORD", "Ford"),
    ("SUZUKI", "Suzuki"),
    ("HONDA", "Honda"),
    ("HYUND", "Hyundai"),
    ("KIA", "Kia"),
)

_MARCAS_EN_DESCRIPCION = (
    "HYUNDAI", "KIA", "TOYOTA", "RENAULT", "CHEVROLET", "NISSAN",
    "MAZDA", "FORD", "SUZUKI", "MITSUBISHI", "HONDA", "VOLKSWAGEN",
    "BMW", "MERCEDES", "PEUGEOT", "CITROEN", "FIAT", "JEEP", "DODGE",
)

_STOP_WORDS = frozenset({
    "DER", "IZQ", "DEL", "TRAS", "RH", "LH", "ORIGINAL", "OEM", "GENUINO",
    "L.", "R.", "DEL.", "TRAS.", "MOTOR", "SOPORTE", "SOPORTES", "BOMPER",
    "GUIA", "FILTRO", "CAJA", "AUX", "DIR", "MOT",
})

_ABBR_MARCA = {"TY": "Toyota", "HY": "Hyundai", "KI": "Kia", "GM": "Chevrolet"}


def normalizar_marca(marca: str, descripcion: str = "") -> str:
    """Convierte codigos de proveedor a nombre legible."""
    raw = (marca or "").strip()
    if not raw and descripcion:
        raw = _marca_desde_descripcion(descripcion)
    if not raw:
        return ""

    key = raw.upper().strip()
    if key in _MARCA_EXACTA:
        return _MARCA_EXACTA[key]

    for prefijo, nombre in _MARCA_PREFIJOS:
        if key.startswith(prefijo):
            return nombre

    if "/" in raw or "*" in raw:
        return raw.replace("/KO", "").replace("*", "").replace("/", " / ").strip()

    return raw.title() if raw.isupper() else raw


def _marca_desde_descripcion(descripcion: str) -> str:
    u = descripcion.upper()
    for marca in _MARCAS_EN_DESCRIPCION:
        if marca in u:
            return marca
    m = re.search(r"\b(TY|HY|KI|GM)\b", u)
    if m:
        return m.group(1)
    return ""


def extraer_vehiculo_display(vehiculo: str, descripcion: str, marca: str = "") -> str:
    """Mejor texto de vehiculo para mostrar al cliente."""
    v = (vehiculo or "").strip()
    if v and not _es_codigo_interno(v):
        return _titulo_vehiculo(v)

    from_desc = _vehiculo_desde_descripcion(descripcion)
    if from_desc:
        return from_desc

    if v:
        return _titulo_vehiculo(v)

    return ""


def _es_codigo_interno(texto: str) -> bool:
    u = texto.upper()
    return u.startswith("ISL") or u.endswith("*") or u in ("MOTOR", "OEM", "APK")


def _titulo_vehiculo(texto: str) -> str:
    if not texto:
        return ""
    parts = []
    for p in texto.split():
        if p.isdigit() or "/" in p:
            parts.append(p)
        elif p.isupper() and len(p) > 1:
            parts.append(p.title())
        else:
            parts.append(p)
    return " ".join(parts)


def _vehiculo_desde_descripcion(descripcion: str) -> str:
    u = descripcion.upper()

    # TY HIGHLANDER 2016/2020 DER, HY I25 DEL, etc.
    m = re.search(
        r"\b(TY|HY|KI|GM)\s+(.+?)\s+(?:DER|IZQ|DEL|TRAS|RH|LH)\b",
        u,
    )
    if m:
        marca = _ABBR_MARCA.get(m.group(1), m.group(1))
        model = _limpiar_modelo(m.group(2))
        return f"{marca} {model}".strip()

    # KIA PICANTO, HYUNDAI TUCSON, RENAULT KWID...
    for marca in _MARCAS_EN_DESCRIPCION:
        idx = u.find(marca)
        if idx < 0:
            continue
        resto = u[idx: idx + 45]
        tokens = resto.split()
        out = []
        for tok in tokens:
            if tok in _STOP_WORDS:
                break
            out.append(tok.title() if tok.isalpha() and tok not in _MARCAS_EN_DESCRIPCION else tok)
            if len(out) >= 5:
                break
        if len(out) >= 2:
            return " ".join(out)

    # Años sueltos con contexto: ... IONIQ HIBRIDO 19/
    m2 = re.search(r"([A-Z][A-Z0-9\s-]{2,20})\s+(\d{2}/|\d{4}/\d{4})", u)
    if m2:
        return _limpiar_modelo(m2.group(1) + " " + m2.group(2).strip())

    return ""


def _limpiar_modelo(texto: str) -> str:
    t = texto.strip()
    for stop in _STOP_WORDS:
        if re.search(rf"\b{re.escape(stop)}\b", t):
            t = re.split(rf"\b{re.escape(stop)}\b", t)[0]
            break
    parts = []
    for p in t.split():
        if p in _STOP_WORDS:
            break
        parts.append(p.title() if p.isalpha() and len(p) > 2 else p)
    return " ".join(parts)


def enriquecer_resultado(reg: dict) -> dict:
    """Agrega campos display para API / frontend."""
    desc = reg.get("descripcion") or ""
    marca_raw = reg.get("marca_vehiculo") or ""
    veh_raw = reg.get("vehiculo") or ""

    reg["marca_display"] = normalizar_marca(marca_raw, desc)
    reg["vehiculo_display"] = extraer_vehiculo_display(veh_raw, desc, marca_raw)
    return reg
