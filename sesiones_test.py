"""Pruebas visibles · usuarios y sesiones.

    uv run python -m pytest sesiones_test.py -q
"""

import sesiones

USUARIO = ("ana", "Ana Torres", "secreta", 3)


def test_crear_usuario(r):
    assert sesiones.crear_usuario(r, *USUARIO) is True
    datos = sesiones.obtener_usuario(r, "ana")
    assert datos["nombre"] == "Ana Torres"
    assert datos["privilegios"] == 3
    assert isinstance(datos["privilegios"], int), "los privilegios son un entero"


def test_no_se_puede_crear_dos_veces(r):
    sesiones.crear_usuario(r, *USUARIO)
    assert sesiones.crear_usuario(r, "ana", "Otra", "otra", 9) is False
    assert sesiones.obtener_usuario(r, "ana")["nombre"] == "Ana Torres", \
        "el usuario original no debe quedar sobrescrito"


def test_usuario_inexistente(r):
    assert sesiones.obtener_usuario(r, "nadie") is None


def test_actualizar_no_pisa_los_demas_campos(r):
    sesiones.crear_usuario(r, *USUARIO)
    assert sesiones.actualizar_usuario(r, "ana", nombre="Ana T.") is True
    datos = sesiones.obtener_usuario(r, "ana")
    assert datos["nombre"] == "Ana T."
    assert datos["privilegios"] == 3, "los privilegios siguen ahí"
    assert datos["password"] == "secreta"


def test_actualizar_usuario_inexistente(r):
    assert sesiones.actualizar_usuario(r, "nadie", nombre="X") is False


def test_login_con_credenciales_malas(r):
    sesiones.crear_usuario(r, *USUARIO)
    assert sesiones.login(r, "ana", "incorrecta") == (-1, None)
    assert sesiones.login(r, "nadie", "secreta") == (-1, None)


def test_login_correcto(r):
    sesiones.crear_usuario(r, *USUARIO)
    privilegios, token = sesiones.login(r, "ana", "secreta")
    assert privilegios == 3
    assert token and len(token) >= 16, "el token debe ser largo e impredecible"


def test_la_sesion_dura_un_mes(r):
    sesiones.crear_usuario(r, *USUARIO)
    _, token = sesiones.login(r, "ana", "secreta")
    restantes = sesiones.segundos_de_sesion(r, token)
    assert 29 * 86400 <= restantes <= 31 * 86400, f"duración inesperada: {restantes} s"


def test_login_por_token(r):
    sesiones.crear_usuario(r, *USUARIO)
    _, token = sesiones.login(r, "ana", "secreta")
    assert sesiones.login_por_token(r, token) == 3


def test_login_por_token_invalido(r):
    assert sesiones.login_por_token(r, "inventado") == -1
    assert sesiones.login_por_token(r, "") == -1


def test_un_login_nuevo_invalida_el_anterior(r):
    sesiones.crear_usuario(r, *USUARIO)
    _, primero = sesiones.login(r, "ana", "secreta")
    _, segundo = sesiones.login(r, "ana", "secreta")

    assert primero != segundo, "cada login genera un token nuevo"
    assert sesiones.login_por_token(r, primero) == -1, \
        "el token anterior no debe seguir sirviendo"
    assert sesiones.login_por_token(r, segundo) == 3


def test_logout(r):
    sesiones.crear_usuario(r, *USUARIO)
    _, token = sesiones.login(r, "ana", "secreta")
    assert sesiones.logout(r, token) is True
    assert sesiones.login_por_token(r, token) == -1
    assert sesiones.logout(r, token) is False, "ya no había sesión"


def test_borrar_usuario_cierra_su_sesion(r):
    sesiones.crear_usuario(r, *USUARIO)
    _, token = sesiones.login(r, "ana", "secreta")
    assert sesiones.borrar_usuario(r, "ana") is True
    assert sesiones.obtener_usuario(r, "ana") is None
    assert sesiones.login_por_token(r, token) == -1, \
        "el token de un usuario borrado no puede seguir valiendo"


def test_la_sesion_caducada_no_vale(r):
    """Se fuerza la caducidad en lugar de esperar un mes."""
    sesiones.crear_usuario(r, *USUARIO)
    _, token = sesiones.login(r, "ana", "secreta")
    r.delete(sesiones.clave_sesion(token))          # simula la expiración
    assert sesiones.login_por_token(r, token) == -1
