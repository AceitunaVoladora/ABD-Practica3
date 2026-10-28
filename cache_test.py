"""Pruebas visibles · caché de documentos.

    uv run python -m pytest cache_test.py -q
"""

import pytest

from cache import CacheDocumentos


@pytest.fixture
def cache(r):
    return CacheDocumentos(r, ttl=100)


def test_la_clave_lleva_coleccion_e_id():
    clave = CacheDocumentos.clave("evento", "abc123")
    assert "evento" in clave and "abc123" in clave
    assert clave.startswith("envivo:")


def test_get_de_algo_no_cacheado_devuelve_none(cache):
    assert cache.get("evento", "no_existe") is None


def test_set_y_get(cache):
    documento = {"titulo": "Rosalía", "aforo": 15500}
    cache.set("evento", "e1", documento)
    assert cache.get("evento", "e1") == documento


def test_set_fija_la_caducidad(cache):
    cache.set("evento", "e1", {"a": 1})
    assert cache.caducidad("evento", "e1") == 100


def test_get_renueva_la_caducidad(cache, r):
    """El requisito central: cada acceso reinicia el plazo."""
    cache.set("evento", "e1", {"a": 1})
    r.expire(CacheDocumentos.clave("evento", "e1"), 20)   # se envejece a mano
    assert cache.caducidad("evento", "e1") == 20

    cache.get("evento", "e1")

    assert cache.caducidad("evento", "e1") == 100, \
        "leer de la caché tiene que renovar la caducidad"


def test_invalidar(cache):
    cache.set("evento", "e1", {"a": 1})
    assert cache.invalidar("evento", "e1") is True
    assert cache.get("evento", "e1") is None
    assert cache.invalidar("evento", "e1") is False


def test_caducidad_de_lo_que_no_existe(cache):
    assert cache.caducidad("evento", "fantasma") == -2


def test_conserva_fechas_y_objectid(cache):
    """Lo que sale de la caché tiene que ser igual a lo que entró, con sus tipos."""
    from datetime import datetime

    from bson import ObjectId

    documento = {"_id": ObjectId(), "fecha": datetime(2026, 3, 14, 21, 0),
                 "artistas": [ObjectId(), ObjectId()], "recinto": ObjectId()}
    cache.set("evento", "e1", documento)
    recuperado = cache.get("evento", "e1")
    assert recuperado is not None
    assert recuperado == documento, \
        "las fechas y los ObjectId tienen que volver de la caché con su tipo, no como texto"


def test_configurar_limite(cache, r):
    cache.configurar_limite()
    try:
        assert int(r.config_get("maxmemory")["maxmemory"]) == 150 * 1024 * 1024
        assert r.config_get("maxmemory-policy")["maxmemory-policy"] != "noeviction", \
            "la política de desalojo sigue siendo la de por omisión"
    finally:
        r.config_set("maxmemory", 0)              # se deja como estaba
        r.config_set("maxmemory-policy", "noeviction")
