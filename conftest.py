"""Fixtures de la fase 3.

Las pruebas usan la **base de datos 15** de Redis y la vacían antes de cada
prueba, así que nunca tocan los datos de trabajo, que están en la 0.
"""

import os

import pytest
import redis

URI = os.environ.get("REDIS_URI", "redis://localhost:6379/15")


@pytest.fixture
def uri():
    """La URI de Redis, para las pruebas que necesitan una segunda conexión."""
    return URI


@pytest.fixture
def r():
    cliente = redis.Redis.from_url(URI, decode_responses=True)
    cliente.ping()                 # falla pronto si no hay Redis
    cliente.flushdb()
    yield cliente
    cliente.flushdb()
    cliente.close()


MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017/")
BD_MONGO = "envivo_pruebas_p3"


@pytest.fixture
def odm(r):
    """Inicializa tu ODM contra MongoDB y la base 15 de Redis.

    Usa el `ODM.py` y el `models.yml` de esta carpeta, y una base de MongoDB
    propia, `envivo_pruebas_p3`, que se borra al terminar. La geolocalización
    se simula para no llamar a la API pública de geopy en cada prueba.
    """
    from unittest.mock import MagicMock, patch

    if not os.path.exists("ODM.py"):
        pytest.skip("falta tu ODM.py: cópialo aquí junto con tu models.yml")
    import ODM

    definiciones = os.environ.get("MODELS_YML", "models.yml")
    ambito = {}
    with patch.object(ODM, "Nominatim") as fake, patch.object(ODM.time, "sleep"):
        fake.return_value.geocode.return_value = MagicMock(longitude=-3.7, latitude=40.4)
        ODM.initApp(definitions_path=definiciones, mongodb_uri=MONGO_URI,
                    db_name=BD_MONGO, scope=ambito, redis_uri=URI)
    yield ambito

    cliente = ODM.MongoClient(MONGO_URI)
    cliente.drop_database(BD_MONGO)
    cliente.close()
