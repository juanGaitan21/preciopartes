"""
Tests de limpieza y consistencia ETL (sin archivos Excel reales).
Ejecutar: python etl/test_limpieza.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from limpieza import (
    aplicar_descuento,
    construir_registro,
    consolidar_registros,
    limpiar_precio,
    limpiar_referencia,
    normalizar_referencia,
    parsear_descuento_pct,
    validar_lote,
)


def test_precios():
    assert limpiar_precio("$ 396.197") == 396197.0
    assert limpiar_precio("396,197") == 396197.0
    assert limpiar_precio(1426600.0) == 1426600.0
    assert limpiar_precio(96335952) == 96335952.0
    assert limpiar_precio("precio") is None
    assert limpiar_precio("15%") is None
    assert limpiar_precio(0) is None
    assert limpiar_precio(50) == 50.0
    print("  precios OK")


def test_referencias():
    assert limpiar_referencia(96335952.0) == "96335952"
    assert normalizar_referencia("56500-2S000") == "565002S000"
    assert normalizar_referencia("96335952P") == "96335952"
    assert normalizar_referencia(" 31112-07000 ") == "3111207000"
    print("  referencias OK")


def test_descuentos():
    assert parsear_descuento_pct(15) == 15.0
    assert parsear_descuento_pct("15%") == 15.0
    assert parsear_descuento_pct(0.15) == 15.0
    p, pd_, d = aplicar_descuento(100000, 15)
    assert pd_ == 85000.0
    assert d == 15.0
    print("  descuentos OK")


def test_registro_completo():
    reg = construir_registro(
        proveedor_nombre="Test",
        referencia_raw="ABC-123",
        descripcion_raw="Filtro aceite",
        precio_raw="$ 50.000",
    )
    assert reg is not None
    assert reg["referencia_norm"] == "ABC123"
    assert reg["precio"] == 50000.0
    assert reg["precio_con_desc"] == 50000.0

    basura = construir_registro(
        proveedor_nombre="Test",
        referencia_raw="REFERENCIA",
        descripcion_raw="DESCRIPCION",
        precio_raw=100000,
    )
    assert basura is None
    print("  registro completo OK")


def test_deduplicacion():
    # Exactamente iguales -> 1 fila
    regs = [
        {"referencia_norm": "ABC", "precio": 100, "precio_con_desc": 100, "descuento_pct": 0,
         "referencia": "A", "descripcion": "x", "vehiculo": "AVEO", "proveedor_nombre": "T"},
        {"referencia_norm": "ABC", "precio": 100, "precio_con_desc": 100, "descuento_pct": 0,
         "referencia": "A", "descripcion": "x", "vehiculo": "AVEO", "proveedor_nombre": "T"},
    ]
    out, dup = consolidar_registros(regs)
    assert len(out) == 1
    assert dup == 1

    # Misma ref, distinto vehiculo -> conservar ambas
    regs2 = [
        {"referencia_norm": "ABC", "precio": 100, "precio_con_desc": 100, "descuento_pct": 0,
         "referencia": "A", "descripcion": "x", "vehiculo": "AVEO", "proveedor_nombre": "T"},
        {"referencia_norm": "ABC", "precio": 90, "precio_con_desc": 90, "descuento_pct": 0,
         "referencia": "A", "descripcion": "x", "vehiculo": "CRUZE", "proveedor_nombre": "T"},
    ]
    out2, dup2 = consolidar_registros(regs2)
    assert len(out2) == 2
    assert dup2 == 0

    out3 = validar_lote(out2)
    assert len(out3) == 2
    print("  deduplicacion OK")


def main():
    print("\nPrecioPartes — Test limpieza ETL\n")
    test_precios()
    test_referencias()
    test_descuentos()
    test_registro_completo()
    test_deduplicacion()
    print("\nTodos los tests pasaron.\n")


if __name__ == "__main__":
    main()
