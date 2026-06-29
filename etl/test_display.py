"""Tests display helpers."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from display import enriquecer_resultado, normalizar_marca, extraer_vehiculo_display


def test_marca_lista_e():
    assert normalizar_marca("HYUNDAI-KIA/KO") == "Hyundai / Kia"
    assert normalizar_marca("ISL-CARR*") == "Carrocería"
    assert normalizar_marca("ISL-ILUM*") == "Iluminación"


def test_marca_dh():
    assert normalizar_marca("HYUND") == "Hyundai"
    assert normalizar_marca("KIA") == "Kia"


def test_vehiculo_desde_descripcion():
    desc = "SOPORTE GUIA BOMPER TRAS TY HIGHLANDER 2016/2020 DER"
    assert "Toyota" in extraer_vehiculo_display("", desc)
    assert "HIGHLANDER" in extraer_vehiculo_display("", desc).upper()

    desc2 = "FILTRO GASOLINA KIA PICANTO I/II /ION (ORIGINAL)"
    v = extraer_vehiculo_display("", desc2)
    assert "KIA" in v.upper() or "Picanto" in v


def test_enriquecer():
    r = enriquecer_resultado({
        "marca_vehiculo": "HYUNDAI-KIA/KO",
        "vehiculo": "",
        "descripcion": "SOPORTE BOMPER HY I25 DER DEL",
    })
    assert r["marca_display"] == "Hyundai / Kia"
    assert r["vehiculo_display"]


def main():
    test_marca_lista_e()
    test_marca_dh()
    test_vehiculo_desde_descripcion()
    test_enriquecer()
    print("display OK")


if __name__ == "__main__":
    main()
