"""Pruebas visibles · la caché integrada en el ODM.

    uv run python -m pytest odm_test.py -q

Necesitan tu `ODM.py` y tu `models.yml` en esta carpeta, y MongoDB levantado.
Todas siguen el mismo truco: borrar el documento de MongoDB a mano y mirar qué
devuelve `find_by_id`. Si lo sigue devolviendo, viene de la caché.
"""

import pytest


@pytest.fixture
def Modelo(odm):
    """La primera clase de modelo que declara tu models.yml."""
    for clase in odm.values():
        if hasattr(clase, "find_by_id") and hasattr(clase, "_db"):
            return clase
    pytest.fail("initApp no ha declarado ninguna clase de modelo")


def _guarda_uno(Modelo):
    objeto = Modelo(**{var: "x" for var in Modelo._required_vars})
    objeto.save()
    return objeto._id


def test_find_by_id_lee_de_la_cache(Modelo, r):
    oid = _guarda_uno(Modelo)
    r.flushdb()                       # se vacía la caché: el primer find_by_id va a Mongo

    assert Modelo.find_by_id(oid) is not None, "find_by_id no encuentra un documento que existe"
    Modelo._db.delete_one({"_id": oid})
    assert Modelo.find_by_id(oid) is not None, \
        "find_by_id ha ido a MongoDB: el documento ya no está allí y debería seguir en caché"


def test_save_cachea_al_insertar(Modelo):
    oid = _guarda_uno(Modelo)
    documento = Modelo._db.find_one({"_id": oid})
    Modelo._db.delete_one({"_id": oid})

    recuperado = Modelo.find_by_id(oid)
    assert recuperado is not None, "save no ha dejado en caché el documento que acaba de insertar"
    for campo, valor in documento.items():
        assert getattr(recuperado, campo) == valor, \
            f"lo cacheado al insertar no coincide con lo que hay en MongoDB en «{campo}»"


def test_save_invalida_al_actualizar(Modelo):
    oid = _guarda_uno(Modelo)
    campo = next(iter(Modelo._required_vars))

    objeto = Modelo.find_by_id(oid)
    setattr(objeto, campo, "valor_nuevo")
    objeto.save()

    Modelo._db.delete_one({"_id": oid})
    assert Modelo.find_by_id(oid) is None, \
        "save no ha invalidado la caché: find_by_id devuelve la versión anterior"


def test_delete_invalida(Modelo):
    oid = _guarda_uno(Modelo)
    campo = next(iter(Modelo._required_vars))

    objeto = Modelo.find_by_id(oid)
    documento = Modelo._db.find_one({"_id": oid})
    objeto.delete()

    # Se vuelve a meter en Mongo con otro valor: tiene que salir el nuevo.
    Modelo._db.insert_one({**documento, campo: "valor_nuevo"})
    assert getattr(Modelo.find_by_id(oid), campo) == "valor_nuevo", \
        "delete no ha invalidado la caché: find_by_id devuelve el documento borrado"
