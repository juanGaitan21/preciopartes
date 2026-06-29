"""
Script de prueba del ETL con los archivos reales.
Ejecutar desde la raíz del proyecto:
    python etl/test_etl.py
"""
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s"
)

sys.path.insert(0, str(Path(__file__).parent))
from etl import procesar_archivo, TIPO_DH, TIPO_CAJAS, TIPO_LISTA_E

# ---- Ajustar estas rutas a tus archivos reales ----
ARCHIVOS = [
    ("DH_4350_COREA_JUNIO_2026.xls",       "DH Repuestos Corea",   TIPO_DH),
    ("DH_4350_SOPORTES_JUNIO_2026.xls",    "DH Soportes",          TIPO_DH),
    ("Lista_CAJAS_DE_DRIECCION_-_26_junio.xls", "Cajas de Dirección", TIPO_CAJAS),
    ("ListaPrecioE20260619___-1.xlsx",      "Lista Precio E",       TIPO_LISTA_E),
]

BASE = Path(__file__).parent.parent / "listas"  # carpeta donde guardas los Excels


def main():
    total_global = 0
    print("\n" + "="*60)
    print("  PrecioPartes — Test ETL")
    print("="*60)

    for nombre_archivo, proveedor, tipo in ARCHIVOS:
        path = BASE / nombre_archivo
        if not path.exists():
            print(f"\n⚠️  No encontrado: {path}")
            continue

        registros = procesar_archivo(path=path, proveedor_nombre=proveedor, tipo=tipo)
        total_global += len(registros)

        print(f"\n📄 {nombre_archivo}")
        print(f"   Proveedor : {proveedor}")
        print(f"   Tipo      : {tipo}")
        print(f"   Registros : {len(registros):,}")

        if registros:
            # Estadísticas
            precios = [r["precio"] for r in registros]
            print(f"   Precio min: ${min(precios):>12,.0f}")
            print(f"   Precio max: ${max(precios):>12,.0f}")
            print(f"   Con desc  : {sum(1 for r in registros if r['descuento_pct'] > 0)} registros")
            print(f"   Muestra   : {registros[0]['referencia']} | {registros[0]['descripcion'][:50]}")

    print(f"\n{'='*60}")
    print(f"  TOTAL REGISTROS VÁLIDOS: {total_global:,}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
