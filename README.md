# Práctica 3 · Caché, reservas y sesiones · EnVivo (fase 3)

Punto de partida de la práctica 3 de **Ampliación de Bases de Datos** (u-tad).
Aquí están los esqueletos de las cuatro piezas que se construyen sobre Redis
—la caché de documentos, la reserva de asientos, la sala de espera y las
sesiones— y las pruebas con las que puedes comprobarlas mientras las escribes.

El enunciado completo, con los requisitos de cada pieza y la rúbrica, está en
el campus virtual. Esto es solo el código.

## Cómo empezar

1. **Crea tu repositorio a partir de esta plantilla** con el botón
   *Use this template → Create a new repository*, y márcalo como **Private**.
   No hagas un *fork*: un fork de un repositorio público es público, y tu
   código quedaría a la vista de todos. Uno por grupo: quien lo crea añade a
   su compañero en *Settings → Collaborators*.
2. Clónalo en tu máquina:

   ```bash
   git clone https://github.com/<tu-usuario>/abd-p3-redis.git
   cd abd-p3-redis
   ```

3. Levanta Redis y MongoDB, desde la carpeta donde tengas el `compose.yaml` de
   la asignatura:

   ```bash
   docker compose up -d redis mongo
   ```

4. Instala las dependencias y comprueba que todo arranca:

   ```bash
   uv sync
   uv run python -m pytest -q
   ```

Al principio fallan todas: eso es lo normal, los cuatro módulos están por
implementar.

## Qué hay aquí

| Fichero | Qué es |
|---|---|
| `cache.py` | La clase `CacheDocumentos`, con los `TODO` |
| `reservas.py` | La reserva temporal de asientos, con los `TODO` |
| `sala_espera.py` | La sala de espera por prioridad, con los `TODO` |
| `sesiones.py` | Los usuarios y las sesiones, con los `TODO` |
| `pyproject.toml` | Las dependencias. No hace falta tocarlo |
| `cache_test.py`, `reservas_test.py`, `sala_espera_test.py`, `sesiones_test.py` | Las pruebas, una suite por pieza |
| `odm_test.py` | Las pruebas de la caché integrada en tu ODM |
| `conftest.py` | La conexión a Redis y MongoDB que usan las pruebas. **No lo edites** |

Falta el `ODM.py`, que es tuyo: ver más abajo.

## Qué se ve al ejecutar las pruebas

Cuando todo está bien, un punto por prueba:

```
.........................................                                [100%]
45 passed in 19.2s
```

Tardan unos segundos porque algunas esperan de verdad a que caduque una clave
o a que llegue una petición a la sala de espera. Mientras algo no esté bien,
cada `F` es una prueba que falla, y abajo sale el nombre de cada una con el
motivo.

Para trabajar sobre una sola pieza:

```bash
uv run python -m pytest cache_test.py -q
uv run python -m pytest reservas_test.py -v
uv run python -m pytest -x --tb=short      # para en el primer fallo
```

## Qué exige cada suite

| Suite | Qué tiene que funcionar |
|---|---|
| `cache_test.py` | Clave, `get`/`set`/`invalidar`, que `get` renueve la caducidad, que fechas y `ObjectId` vuelvan con su tipo, y el límite de memoria con una política que desaloje |
| `reservas_test.py` | Reservar un asiento libre y solo una vez, que la reserva caduque sola, y que solo el propietario pueda liberar o confirmar |
| `sala_espera_test.py` | Atender por prioridad, la prioridad absoluta, que atender elimine, la posición en la cola y que el operador espere a que llegue alguien |
| `sesiones_test.py` | El CRUD de usuarios, `login` y `login_por_token`, la duración de un mes, `logout` y que borrar un usuario cierre su sesión |
| `odm_test.py` | Que `find_by_id` lea de la caché sin ir a MongoDB, que `save` cachee al insertar e invalide al actualizar, y que `delete` invalide. Se saltan mientras no copies aquí tu `ODM.py` |

## Lo que estas pruebas no dicen

Pasarlas es **necesario, pero no suficiente**. En particular, no pueden
comprobar del todo que las operaciones que el enunciado pide atómicas lo sean.

## El ODM de las prácticas anteriores

La caché se engancha en tu ODM. Copia aquí tu `ODM.py` y tu `models.yml` —los de la
práctica 1, que ya usaste en la 2— y completa lo que pide el enunciado: `find_by_id`, que `save` cachee al
insertar, la invalidación en `save` y `delete`, y el parámetro `redis_uri` de
`initApp`. El
`pyproject.toml` ya trae las dependencias del ODM.

## Tres cosas que no hay que cambiar

- Los nombres de los ficheros: las pruebas hacen `from cache import
  CacheDocumentos`, `import reservas`, etc.
- Las firmas y los valores de retorno de las funciones: son el contrato con el
  que se corrige.
- Los nombres de las constantes, como `PRIORIDAD_ABSOLUTA`: las pruebas las
  usan.

Las pruebas trabajan sobre la **base de datos 15** de Redis y la vacían antes
de cada prueba, y las del ODM usan una base de MongoDB propia,
`envivo_pruebas_p3`, que se borra al terminar. Así que **no tocan tus datos**.

## La entrega

Tu repositorio es para trabajar. La entrega es la que dice el enunciado: un
**ZIP** con la carpeta del proyecto y estos seis ficheros —`cache.py`,
`reservas.py`, `sala_espera.py`, `sesiones.py`, `ODM.py` y `models.yml`—
nombrado `P3_G<grupo>_Nombre_Apellido-Nombre_Apellido.zip`.

## Si algo no arranca

El manual **Entorno de trabajo** de la asignatura tiene la tabla de errores
frecuentes. Los más habituales aquí:

- `redis.exceptions.ConnectionError` → Redis no está levantado:
  `docker compose up -d redis`.
- `ModuleNotFoundError: No module named 'cache'` → ejecutaste `pytest` a
  secas. Tiene que ser `python -m pytest`, desde la carpeta del proyecto.
- `NotImplementedError` → es el `raise` del esqueleto: esa función todavía
  está por hacer.
