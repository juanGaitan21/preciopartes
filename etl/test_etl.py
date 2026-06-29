"""
Script de prueba del ETL con archivos reales en listas/.
Ejecutar desde la raiz del proyecto:
    python etl/test_etl.py
"""
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s | %(name)s | %(message)s",
)

sys.path.insert(0, str(Path(__file__).parent))
from etl import procesar_archivo_detallado

BASE = Path(__file__).parent.parent / "listas"


def main():
    archivos = sorted(
        list(BASE.glob("*.xls")) + list(BASE.glob("*.xlsx"))
    )

    print("\n" + "=" * 60)
    print("  PrecioPartes — Test ETL (autodetect)")
    print("=" * 60)

    if not archivos:
        print(f"\nNo hay Excel en {BASE}")
        print("Copia tus listas a esa carpeta y vuelve a ejecutar.\n")
        return

    total = 0
    for path in archivos:
        det = procesar_archivo_detallado(path)
        print(f"\n  {path.name}")
        print(f"     Tipo      : {det.get('tipo_detectado')}")
        print(f"     Proveedor : {det.get('proveedor_detectado')}")
        if det["codigo_error"]:
            print(f"     ERROR     : {det['mensaje']}")
            continue
        n = len(det["registros"])
        total += n
        desc = det.get("filas_descartadas", 0)
        print(f"     Registros : {n:,}  (descartados en limpieza: {desc})")
        if n:
            r = det["registros"][0]
            print(f"     Muestra   : {r['referencia']} | {r['descripcion'][:40]}")

    print(f"\n{'=' * 60}")
    print(f"  TOTAL VALIDOS: {total:,}")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
