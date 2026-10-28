"""Pruebas visibles · reserva temporal de asientos.

    uv run python -m pytest reservas_test.py -q
"""

import time

import reservas


def test_reservar_un_asiento_libre(r):
    assert reservas.reservar(r, "e1", 12, 7) is True
    assert reservas.propietario(r, "e1", 12) == "7"


def test_no_se_puede_reservar_dos_veces(r):
    reservas.reservar(r, "e1", 12, 7)
    assert reservas.reservar(r, "e1", 12, 99) is False, \
        "el asiento ya estaba reservado"
    assert reservas.propietario(r, "e1", 12) == "7", "y sigue siendo del primero"


def test_asiento_libre_no_tiene_propietario(r):
    assert reservas.propietario(r, "e1", 99) is None
    assert reservas.segundos_restantes(r, "e1", 99) == -2


def test_la_reserva_caduca_sola(r):
    """El requisito central: nadie tiene que limpiar nada."""
    reservas.reservar(r, "e1", 12, 7, segundos=1)
    assert reservas.propietario(r, "e1", 12) == "7"

    time.sleep(1.3)

    assert reservas.propietario(r, "e1", 12) is None, \
        "la reserva tiene que liberarse por caducidad"
    assert reservas.reservar(r, "e1", 12, 99) is True, "y el asiento queda libre"


def test_solo_el_propietario_libera(r):
    reservas.reservar(r, "e1", 12, 7)
    assert reservas.liberar(r, "e1", 12, 99) is False, "un tercero no puede liberarla"
    assert reservas.propietario(r, "e1", 12) == "7"
    assert reservas.liberar(r, "e1", 12, 7) is True
    assert reservas.propietario(r, "e1", 12) is None


def test_confirmar_quita_la_caducidad(r):
    reservas.reservar(r, "e1", 12, 7, segundos=60)
    assert reservas.segundos_restantes(r, "e1", 12) > 0
    assert reservas.confirmar(r, "e1", 12, 7) is True
    assert reservas.segundos_restantes(r, "e1", 12) == -1, \
        "una reserva firme no caduca"


def test_solo_el_propietario_confirma(r):
    reservas.reservar(r, "e1", 12, 7, segundos=60)
    assert reservas.confirmar(r, "e1", 12, 99) is False
    assert reservas.segundos_restantes(r, "e1", 12) > 0, "sigue siendo temporal"


def test_asientos_distintos_son_independientes(r):
    assert reservas.reservar(r, "e1", 12, 7) is True
    assert reservas.reservar(r, "e1", 13, 99) is True
    assert reservas.reservar(r, "e2", 12, 99) is True, "otro evento, otro asiento"
