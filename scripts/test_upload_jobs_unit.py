"""Tests unitarios del modulo upload_jobs (sin DB ni pandas)."""

import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.upload_jobs import _build_job_response


def test_build_job_response_with_decimal():
    job = {
        "id": "test-job",
        "estado": "processing",
        "total_archivos": 1,
        "mensaje": "",
        "creado_en": None,
        "iniciado_en": None,
        "finalizado_en": None,
    }
    files = [
        {
            "archivo_nombre": "lista.xls",
            "orden": 0,
            "estado": "completed",
            "lista_id": 5,
            "registros_cargados": Decimal("12345"),
            "resultado": {"lista_id": 5, "registros_cargados": Decimal("12345")},
            "error": None,
        },
        {
            "archivo_nombre": "otro.xls",
            "orden": 1,
            "estado": "processing",
            "lista_id": None,
            "registros_cargados": Decimal("0"),
            "resultado": '{"fase": "leyendo_excel", "detalle": "Leyendo..."}',
            "error": None,
        },
    ]

    resp = _build_job_response(job, files)

    assert resp["job_id"] == "test-job"
    assert resp["total_registros"] == 12345
    assert isinstance(resp["total_registros"], int)
    assert resp["archivos"][0]["registros_cargados"] == 12345
    assert resp["archivos"][1]["fase"] == "leyendo_excel"
    assert resp["progreso_pct"] == 100.0

    import json
    json.dumps(resp)
    print("OK: _build_job_response serializa correctamente con Decimal")


if __name__ == "__main__":
    test_build_job_response_with_decimal()
