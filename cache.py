"""EnVivo · fase 3 · caché de documentos.

Hay que implementar la clase `CacheDocumentos`. Las firmas y los valores de
retorno **no deben cambiarse**: son el contrato con el que se corrige.
"""

import redis
from bson import json_util

TTL_POR_DEFECTO = 24 * 60 * 60      # 24 horas
MEMORIA_MAXIMA = "150mb"
POLITICA_DESALOJO = "volatile-ttl"            # TODO: la política que pide el enunciado


class CacheDocumentos:
    """Caché de documentos con caducidad renovada en cada acceso."""

    def __init__(self, cliente: redis.Redis, ttl: int = TTL_POR_DEFECTO):
        self._r = cliente
        self.ttl = ttl

    def configurar_limite(self, memoria: str = MEMORIA_MAXIMA,
                          politica: str = POLITICA_DESALOJO) -> None:
        """Fija el límite de memoria y la política de desalojo de la caché."""
        self.redis.config_set("maxmemory", memoria)
        self.redis.config_set("maxmemory-policy", politica)

    @staticmethod
    def clave(coleccion: str, id_documento) -> str:
        """Clave de Redis para un documento. Formato: envivo:cache:<col>:<id>"""
        return f"envivo:cache:{coleccion}:{id_documento}"

    def get(self, coleccion: str, id_documento) -> dict | None:
        """Devuelve el documento cacheado, o None si no está.

        Cada acceso debe **renovar la caducidad** a `self.ttl`.
        """
        valor = self.redis.getex(self.clave(coleccion, id_documento), ex = self.ttl)
        
        if valor is None:
            return None
        
        return json_util.loads(valor)

    def set(self, coleccion: str, id_documento, documento: dict) -> None:
        """Guarda el documento en la caché con su caducidad.

        `get` tiene que devolverlo igual, con los mismos tipos: las fechas como
        fechas y los ObjectId como ObjectId.
        """

        self.redis.set(self.clave(coleccion, id_documento), json_util.dumps(documento), ex = self.ttl)
        

    def invalidar(self, coleccion: str, id_documento) -> bool:
        """Saca el documento de la caché. Devuelve si estaba."""

        return self.redis.delete(self.clave(coleccion, id_documento)) == 1

    def caducidad(self, coleccion: str, id_documento) -> int:
        """Segundos restantes. -1 si no caduca, -2 si no existe."""
        return self.redis.ttl(self.clave(coleccion, id_documento))
