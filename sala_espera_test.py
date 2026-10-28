"""Pruebas visibles · sala de espera virtual.

    uv run python -m pytest sala_espera_test.py -q
"""

import threading
import time

import redis

import sala_espera as sala


def test_entrar_y_contar(r):
    assert sala.entrar(r, "e1", 7, 10) is True
    assert sala.entrar(r, "e1", 9, 23.2) is True
    assert sala.en_espera(r, "e1") == 2


def test_un_usuario_no_ocupa_dos_puestos(r):
    sala.entrar(r, "e1", 7, 10)
    assert sala.entrar(r, "e1", 7, 50) is False, "ya estaba en la cola"
    assert sala.en_espera(r, "e1") == 1


def test_atiende_por_prioridad_descendente(r):
    sala.entrar(r, "e1", 7, 10)
    sala.entrar(r, "e1", 9, 23.2)
    sala.entrar(r, "e1", 5, 1)

    assert sala.atender_siguiente(r, "e1", timeout=1)[0] == "9"
    assert sala.atender_siguiente(r, "e1", timeout=1)[0] == "7"
    assert sala.atender_siguiente(r, "e1", timeout=1)[0] == "5"


def test_prioridad_absoluta(r):
    sala.entrar(r, "e1", 7, 999999)
    sala.entrar(r, "e1", 12, sala.PRIORIDAD_ABSOLUTA)
    assert sala.atender_siguiente(r, "e1", timeout=1)[0] == "12", \
        "la prioridad absoluta gana a cualquier valor concreto"


def test_atender_devuelve_tambien_la_prioridad(r):
    sala.entrar(r, "e1", 7, 23.5)
    usuario, prioridad = sala.atender_siguiente(r, "e1", timeout=1)
    assert usuario == "7"
    assert prioridad == 23.5


def test_atender_elimina_la_peticion(r):
    sala.entrar(r, "e1", 7, 10)
    sala.atender_siguiente(r, "e1", timeout=1)
    assert sala.en_espera(r, "e1") == 0


def test_posicion_en_la_cola(r):
    sala.entrar(r, "e1", 7, 10)
    sala.entrar(r, "e1", 9, 23.2)
    sala.entrar(r, "e1", 5, 1)

    assert sala.posicion(r, "e1", 9) == 1, "el de mayor prioridad va primero"
    assert sala.posicion(r, "e1", 7) == 2
    assert sala.posicion(r, "e1", 5) == 3
    assert sala.posicion(r, "e1", 404) is None


def test_sala_vacia_con_timeout(r):
    assert sala.atender_siguiente(r, "e1", timeout=1) is None


def test_el_operador_espera_a_que_llegue_una_peticion(r, uri):
    """El requisito central: no consultar en bucle, esperar.

    Hace falta una segunda conexión porque la del operador queda bloqueada:
    una conexión que está esperando en `BZPOPMAX` no puede enviar nada más.
    """
    recogido = {}

    def operador():
        recogido["peticion"] = sala.atender_siguiente(r, "e_espera", timeout=5)

    hilo = threading.Thread(target=operador)
    hilo.start()
    time.sleep(0.5)
    assert hilo.is_alive(), "el operador debe quedarse esperando, no volver con None"

    otro_cliente = redis.Redis.from_url(uri, decode_responses=True)
    try:
        sala.entrar(otro_cliente, "e_espera", 42, 5)
        hilo.join(timeout=3)
    finally:
        otro_cliente.close()

    assert recogido.get("peticion") is not None, "el operador no ha despertado"
    assert recogido["peticion"][0] == "42"


def test_salas_de_eventos_distintos_son_independientes(r):
    sala.entrar(r, "e1", 7, 10)
    sala.entrar(r, "e2", 9, 10)
    assert sala.en_espera(r, "e1") == 1
    assert sala.en_espera(r, "e2") == 1
