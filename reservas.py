"""EnVivo · fase 3 · reserva temporal de asientos.

Una reserva dura cinco minutos y, si nadie la confirma, **se libera sola**.
No debe haber ningún proceso de limpieza: la propia base de datos se encarga.

Las firmas y los valores de retorno **no deben cambiarse**.
"""

import redis

SEGUNDOS_POR_DEFECTO = 300


def clave(evento_id, asiento) -> str:
    """Clave de Redis. Formato: envivo:asiento:<evento>:<asiento>"""
    # TODO
    raise NotImplementedError


def reservar(r: redis.Redis, evento_id, asiento, usuario_id,
             segundos: int = SEGUNDOS_POR_DEFECTO) -> bool:
    """Reserva el asiento si está libre. Devuelve si se ha conseguido.

    Dos usuarios que lo intenten a la vez: **solo uno** puede conseguirlo.
    """
    # TODO
    raise NotImplementedError


def propietario(r: redis.Redis, evento_id, asiento) -> str | None:
    """Quién tiene reservado el asiento, o None si está libre."""
    # TODO
    raise NotImplementedError


def segundos_restantes(r: redis.Redis, evento_id, asiento) -> int:
    """Segundos que quedan. -1 si la reserva es firme, -2 si no hay reserva."""
    # TODO
    raise NotImplementedError


def liberar(r: redis.Redis, evento_id, asiento, usuario_id) -> bool:
    """Libera la reserva, **solo si es de ese usuario**.

    Devuelve True si la ha liberado y False si el asiento estaba libre o
    reservado por otro. Comprobar y borrar en dos comandos desde el cliente
    **no es correcto**: entre uno y otro la reserva puede caducar y pasar a
    otro usuario, y se le borraría la suya.
    """
    # TODO
    raise NotImplementedError


def confirmar(r: redis.Redis, evento_id, asiento, usuario_id) -> bool:
    """Convierte la reserva en firme: deja de caducar.

    Solo puede hacerlo el propietario. Devuelve si se ha confirmado.
    """
    # TODO
    raise NotImplementedError
