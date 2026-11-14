"""EnVivo · fase 3 · usuarios y sesiones.

De cada usuario se guarda: nombre completo, nombre de usuario, contraseña
(puede estar en plano), privilegios (entero positivo) y el token de sesión si
tiene una activa. Las sesiones duran **un mes** y al caducar desaparecen solas.

Las firmas y los valores de retorno **no deben cambiarse**.
"""

import redis
import secrets

DURACION_SESION = 30 * 24 * 60 * 60      # un mes
SIN_ACCESO = -1


def clave_usuario(usuario: str) -> str:
    """Formato: envivo:usuario:<usuario>"""
    return f"envivo:usuario:{usuario}"


def clave_sesion(token: str) -> str:
    """Formato: envivo:sesion:<token>"""
    return f"envivo:sesion:{token}"


# ── Gestión de usuarios (CRUD) ──────────────────────────────────────────────

def crear_usuario(r: redis.Redis, usuario: str, nombre: str,
                  password: str, privilegios: int) -> bool:
    """Crea el usuario si no existe. Devuelve si se ha creado."""


    script = """
    if redis.call('EXISTS', KEYS[1]) == 1 then
        return 0
    end

    redis.call('HSET', KEYS[1],
        'usuario', ARGV[1],
        'nombre', ARGV[2],
        'password', ARGV[3],
        'privilegios', ARGV[4]
    )

    return 1
    """

    resultado = r.eval(
        script,
        1,
        clave_usuario(usuario),
        usuario,
        nombre,
        password,
        privilegios
    )

    return resultado == 1


def obtener_usuario(r: redis.Redis, usuario: str) -> dict | None:
    """Todos los campos del usuario, o None si no existe.

    `privilegios` debe venir como **entero**, no como cadena.
    """
    
    datos = r.hgetall(clave_usuario(usuario))

    if not datos:
        return None

    token = datos.get("token")

    if token and not r.exists(clave_sesion(token)): #Si hay un token guardado, pero ya no está activo
        #Quitamos en redis y en la copia local el campo token
        r.hdel(clave_usuario(usuario), "token")
        datos.pop("token")

    #Devolvemos privilegios como un int
    datos["privilegios"] = int(datos["privilegios"])

    return datos


def actualizar_usuario(r: redis.Redis, usuario: str, **campos) -> bool:
    """Modifica los campos indicados y **solo** esos.

    Devuelve False si el usuario no existe.
    """

    if not r.exists(clave_usuario(usuario)):
        return False

    campos_permitidos = {"nombre", "password", "privilegios"}

    if not set(campos).issubset(campos_permitidos):
        raise ValueError("Hay campos que no se pueden modificar")


    if "privilegios" in campos:
        if int(campos["privilegios"]) <= 0:
            raise ValueError("Los privilegios deben ser positivos")

    r.hset(clave_usuario(usuario), mapping=campos)

    return True


def borrar_usuario(r: redis.Redis, usuario: str) -> bool:
    """Borra el usuario. Si tenía sesión abierta, debe quedar cerrada."""

    script = """
    local token = redis.call('HGET', KEYS[1], 'token')

    if redis.call('EXISTS', KEYS[1]) == 0 then
        return 0
    end

    if token then
        redis.call('DEL', 'envivo:sesion:' .. token)
    end

    redis.call('DEL', KEYS[1])
    return 1
    """

    resultado = r.eval(script, 1, clave_usuario(usuario))

    return resultado == 1


# ── Sesiones ────────────────────────────────────────────────────────────────

def login(r: redis.Redis, usuario: str, password: str) -> tuple[int, str | None]:
    """Comprueba las credenciales y abre una sesión.

    Devuelve `(privilegios, token)` si son correctas y `(-1, None)` si no.
    Un login nuevo debe invalidar la sesión anterior del mismo usuario.
    """

    token = secrets.token_urlsafe(32) #El token debe ser impredecible

    script = """
    local password_guardada = redis.call('HGET', KEYS[1], 'password')

    if not password_guardada or password_guardada ~= ARGV[1] then
        return -1
    end

    local privilegios = redis.call('HGET', KEYS[1], 'privilegios')
    local token_anterior = redis.call('HGET', KEYS[1], 'token')

    -- Invalidamos la sesión anterior.
    if token_anterior then
        redis.call('DEL', 'envivo:sesion:' .. token_anterior)
    end

    -- Creamos la nueva sesión.
    redis.call('HSET', KEYS[2],
        'usuario', ARGV[4],
        'privilegios', privilegios
    )

    -- Le asignamos una duración de un mes.
    redis.call('EXPIRE', KEYS[2], ARGV[3])

    -- Guardamos el nuevo token en el usuario.
    redis.call('HSET', KEYS[1], 'token', ARGV[2])

    return tonumber(privilegios)
    """

    resultado = r.eval(
        script,
        2,
        clave_usuario(usuario),
        clave_sesion(token),
        password,
        token,
        DURACION_SESION,
        usuario
    )

    if resultado == SIN_ACCESO:
        return SIN_ACCESO, None

    return int(resultado), token


def login_por_token(r: redis.Redis, token: str) -> int:
    """Privilegios asociados al token, o -1 si no vale.

    Un token cuya sesión ha caducado devuelve -1, igual que uno inventado.
    """
    if not token:
        return SIN_ACCESO

    script = """
    if redis.call('EXISTS', KEYS[1]) == 0 then
        return -1
    end

    local usuario = redis.call('HGET', KEYS[1], 'usuario')

    if not usuario then
        return -1
    end

    local clave_usuario = 'envivo:usuario:' .. usuario

    -- El token debe seguir siendo el token actual del usuario.
    if redis.call('HGET', clave_usuario, 'token') ~= ARGV[1] then
        return -1
    end

    local privilegios = redis.call('HGET', KEYS[1], 'privilegios')

    return tonumber(privilegios)
    """

    resultado = r.eval(script, 1, clave_sesion(token), token)

    return int(resultado)


def logout(r: redis.Redis, token: str) -> bool:
    """Cierra la sesión. Devuelve si había una sesión que cerrar."""

    if not token:
        return False

    script = """
    if redis.call('EXISTS', KEYS[1]) == 0 then
        return 0
    end

    local usuario = redis.call('HGET', KEYS[1], 'usuario')

    if usuario then
        local clave_usuario = 'envivo:usuario:' .. usuario

        -- Solo quitamos el token si sigue siendo el actual.
        if redis.call('HGET', clave_usuario, 'token') == ARGV[1] then
            redis.call('HDEL', clave_usuario, 'token')
        end
    end

    redis.call('DEL', KEYS[1])
    return 1
    """

    resultado = r.eval(script, 1, clave_sesion(token), token)

    return resultado == 1


def segundos_de_sesion(r: redis.Redis, token: str) -> int:
    """Segundos que le quedan a la sesión. -2 si no existe."""

    return r.ttl(clave_sesion(token))
