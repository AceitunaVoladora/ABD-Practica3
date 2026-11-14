"""EnVivo · fase 3 · sala de espera virtual.

Cola de prioridad: los valores grandes son peticiones de alta prioridad y los
pequeños de baja. El operador atiende siempre la de mayor prioridad y, si no
hay ninguna, **espera** hasta que llegue.

Las firmas y los valores de retorno **no deben cambiarse**.
"""

import redis

PRIORIDAD_ABSOLUTA = float("inf")


def clave(evento_id) -> str:
    """Clave de Redis. Formato: envivo:sala:<evento>"""
    return f"envivo:sala:{evento_id}"


def entrar(r: redis.Redis, evento_id, usuario_id, prioridad: float) -> bool:
    """Registra al usuario en la sala con esa prioridad.

    Devuelve True si es nuevo en la cola y False si ya estaba (en ese caso se
    le actualiza la prioridad). Un usuario **no puede ocupar dos puestos**.
    """
    return r.zadd(clave(evento_id), {str(usuario_id): prioridad}) == 1


def atender_siguiente(r: redis.Redis, evento_id, timeout: int = 0):
    """Toma y elimina la petición de mayor prioridad.

    Devuelve `(usuario_id, prioridad)`, o None si se agota el `timeout`.
    Con `timeout=0` espera indefinidamente. Obtener y eliminar deben ser una
    sola operación, o dos operadores podrían atender al mismo usuario.
    """

    resultado = r.bzpopmax(clave(evento_id), timeout)

    if resultado is None:
        return None

    _, usuario, prioridad = resultado

    return usuario, prioridad


def en_espera(r: redis.Redis, evento_id) -> int:
    """Cuántos usuarios hay en la sala."""
    return r.zcard(clave(evento_id))


def posicion(r: redis.Redis, evento_id, usuario_id) -> int | None:
    """Puesto en la cola **empezando en 1**, o None si el usuario no está.

    El puesto 1 es el que se va a atender antes.
    """
    puesto = r.zrevrank(clave(evento_id), str(usuario_id))

    if puesto is None:
        return None

    return puesto + 1
