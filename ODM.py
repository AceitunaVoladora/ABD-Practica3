__author__ = 'Pablo Ramos Criado'
__students__ = 'Enrique Herranz Acosta y Marta Martín Moreno'


from geopy.geocoders import Nominatim
from geopy.exc import GeocoderTimedOut
import time
from typing import Generator, Any, Self
from geojson import Point
import pymongo
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
from bson.objectid import ObjectId
import yaml
from datetime import datetime
from bson import json_util

import redis
from bson.errors import InvalidId
from cache import CacheDocumentos

def getLocationPoint(address: str) -> Point:
    """ 
    Obtiene las coordenadas de una dirección en formato geojson.Point
    Utilizar la API de geopy para obtener las coordenadas de la direccion
    Cuidado, la API es publica tiene limite de peticiones, utilizar sleeps.

    Parameters
    ----------
        address : str
            direccion completa de la que obtener las coordenadas
    Returns
    -------
        geojson.Point
            coordenadas del punto de la direccion
    """
    location = None
    intentos = 0
    maxIntentos = 5
    while location is None and intentos < maxIntentos:
        intentos += 1
        try:
            time.sleep(1)
            # Es necesario proporcionar un user_agent para utilizar la API
            # Utilizar un nombre aleatorio para el user_agent
            location = Nominatim(user_agent="Kike_Y_Marta").geocode(address)
        except GeocoderTimedOut:
            # Puede lanzar una excepcion si se supera el tiempo de espera
            # Volver a intentarlo
            continue
    # Devolver un GeoJSON de tipo punto con la latitud y longitud almacenadas.
    # Si no se consiguieron coordenadas, lanzar ValueError: la funcion no puede
    # devolver un punto inventado ni None silenciosamente. Es lo que espera la
    # prueba test_get_location_point_timeout_failure.   

    if location is None:
        raise ValueError("No se pudieron obtener coordenadas")
    return Point((location.longitude, location.latitude))

class Model:
    """ 
    Clase de modelo abstracta
    Crear tantas clases que hereden de esta clase como  
    colecciones/modelos se deseen tener en la base de datos.

    Attributes
    ----------
        required_vars : set[str]
            conjunto de atributos requeridos por el modelo
        admissible_vars : set[str]
            conjunto de atributos admitidos por el modelo
        db : pymongo.collection.Collection
            conexion a la coleccion de la base de datos
    
    Methods
    -------
        __setattr__(name: str, value: str | dict) -> None
            Sobreescribe el metodo de asignacion de valores a los 
            atributos del objeto con el fin de controlar qué atributos 
            son modificados y cuando son modificados.
        __getattr__(name: str) -> Any
            Sobreescribe el metodo de acceso a atributos del objeto 
        save()  -> None
            Guarda el modelo en la base de datos
        delete() -> None
            Elimina el modelo de la base de datos
        find(filter: dict[str, str | dict]) -> ModelCursor
            Realiza una consulta de lectura en la BBDD.
            Devuelve un cursor de modelos ModelCursor
        aggregate(pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor
            Devuelve el resultado de una consulta aggregate.
        find_by_id(id: str) -> dict | None
            Busca un documento por su id utilizando la cache y lo devuelve.
            Si no se encuentra el documento, devuelve None.
        init_class(db_collection: pymongo.collection.Collection, required_vars: set[str], admissible_vars: set[str]) -> None
            Inicializa las variables de clase en la inicializacion del sistema.

    """
    _required_vars: set[str]
    _admissible_vars: set[str]
    _location_var: str | None = None
    _db: pymongo.collection.Collection
    _internal_vars: set[str] = frozenset(('_modified_vars', '_required_vars', '_admissible_vars', '_db', '_data', '_location_var','_cache'))
    _cache: CacheDocumentos | None = None

    def __init__(self, **kwargs: dict[str, str | dict | list]) -> None:
        """
        Inicializa el modelo con los valores proporcionados en kwargs
        Comprueba que los valores proporcionados en kwargs son admitidos
        por el modelo y que las atributos requeridos son proporcionadas.

        Parameters
        ----------
            kwargs : dict[str, str | dict]
                diccionario con los valores de las atributos del modelo
        """
        self._data: dict[str, str | dict | list] = {}
        self._modified_vars: set[str] = set() #Se inicializa para cuando haya que modificar algo luego
        
        # Realizar las comprabociones y gestiones necesarias
        # antes de la asignacion.

        # Asigna todos los valores en kwargs a las atributos con 
        # nombre las claves en kwargs
        # Utilizamos el atributo data para guardar los variables 
        # almacenadas en la base de datos en una solo atributo
        # Encapsular los datos en una sola variable facilita la 
        # gestion en metodos como save.

        info_dada = set(kwargs.keys())
        info_permitida= self._required_vars | self._admissible_vars

        #campos no admitidos
        info_desconocida = info_dada - info_permitida
        if info_desconocida:
            raise ValueError("Hay campos que no deberían estar")
        #campos obligatorios q faltan
        info_faltante = self._required_vars - info_dada
        if info_faltante:
            raise ValueError("Te faltan campos obligatorios")

        self._data.update(kwargs)

    def __setattr__(self, name: str, value: str | dict) -> None:
        """ Sobreescribe el metodo de asignacion de valores a los 
        atributos del objeto con el fin de controlar que atributos 
        son modificados y cuando son modificados.
        """
        if name in self._internal_vars:
            super().__setattr__(name, value)
            return
        if name not in self._required_vars and name not in self._admissible_vars:
            raise AttributeError("El campo modificado no está permitido")
        # Asigna el valor value a la variable name
        self._data[name] = value
        self._modified_vars.add(name) #Para marcar que la hemos  modificado

    def __getattr__(self, name: str) -> Any:
        """ Sobreescribe el metodo de acceso a atributos del objeto
        __getattr__ solo es llamado cuando no encuentra el atributo
        en el objeto 
        """
        if name in self._internal_vars:
            return super().__getattribute__(name)
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError
        
    def save(self) -> None:
        """
        Guarda el modelo en la base de datos
        Si el modelo no existe en la base de datos, se crea un nuevo
        documento con los valores del modelo. En caso contrario, se
        actualiza el documento existente con los nuevos valores del
        modelo.
        """

        if self._location_var and self._location_var in self._data: #Es decir, si el Modelo tiene un atributo de dirección
                    direccion = self._data[self._location_var]
                    campo_loc = self._location_var + "_loc"

                    #Obtendremos las coordenadas solo si es la primera vez que se guarda, o si la dirección ha sido modificada
                    if direccion and (not hasattr(self, "_id") or self._location_var in self._modified_vars):
                        self._data[campo_loc] = getLocationPoint(direccion) #Creamos un nuevo campo para las coordenadas
                        self._modified_vars.add(campo_loc) #Se añade a modificado porque se ha creado

        if not hasattr(self, "_id"): #Es decir, comprueba si aún no hay un identificador de Mongo
            resultado = self._db.insert_one(dict(self._data)) #Con dict() le paso una copia, para que no modifique mi _data metiendo un ObjectId
            super().__setattr__("_id", resultado.inserted_id)
            #La linea de encima asigna a la varialbe _id ese id que Mongo le ha puesto
            #Estamos llamando al método de la clase base para que ignores los "filtros" de la nuestra propia
            if self._cache is not None:
                self._cache.set(self._db.name, resultado.inserted_id, dict(self._data)) #Guardamos en la cach el documento que acabamos de insertar
        else:
            if self._modified_vars:
                cambios = {campo: self._data[campo]  for campo in self._modified_vars}
                #Esto crea un diccionario por cada campo modificado, con su valor nuevo
                self._db.update_one(
                    {"_id": self._id},
                    {"$set": cambios}
                )
            if self._cache is not None:
                self._cache.invalidar(self._db.name, self._id)
        self._modified_vars.clear() #Como ya ha sido guardado, se resetean las variables modificadas

        

    def delete(self) -> None:
        """
        Elimina el modelo de la base de datos
        """
        if hasattr(self, "_id"): #Solo borra si antes ha sido insertado
            self._db.delete_one({"_id": self._id})
            if self._cache is not None:
                self._cache.invalidar(self._db.name, self._id)
            object.__delattr__(self, "_id") #Le quita el id para que si se hace save, sepa que tiene que insertar,no actualizar
    
    @classmethod
    def find(cls, filter: dict[str, str | dict]) -> Any:
        """ 
        Utiliza el metodo find de pymongo para realizar una consulta
        de lectura en la BBDD.
        find debe devolver un cursor de modelos ModelCursor

        Parameters
        ----------
            filter : dict[str, str | dict]
                diccionario con el criterio de busqueda de la consulta
        Returns
        -------
            ModelCursor
                cursor de modelos
        """ 
        cursor = cls._db.find(filter) #cls ref. a propia clase, como self pero para la clase
        return ModelCursor(cls,cursor)

    @classmethod
    def aggregate(cls, pipeline: list[dict]) -> pymongo.command_cursor.CommandCursor:
        """ 
        Devuelve el resultado de una consulta aggregate. 
        No hay nada que hacer en esta funcion.
        Se utilizara para las consultas solicitadas
        en el segundo proyecto de la practica.

        Parameters
        ----------
            pipeline : list[dict]
                lista de etapas de la consulta aggregate 
        Returns
        -------
            pymongo.command_cursor.CommandCursor
                cursor de pymongo con el resultado de la consulta
        """ 
        return cls._db.aggregate(pipeline)
    
    @classmethod
    def find_by_id(cls, id: str) -> Self | None:
        """ 
        NO IMPLEMENTAR HASTA EL TERCER PROYECTO
        Busca un documento por su id utilizando la cache y lo devuelve.
        Si no se encuentra el documento, devuelve None.

        Parameters
        ----------
            id : str
                id del documento a buscar
        Returns
        -------
            Self | None
                Modelo del documento encontrado o None si no se encuentra
        """ 

        coleccion = cls._db.name
        document = cls._cache.get(coleccion, id) if cls._cache else None

        if document is None:
            try:
                document = cls._db.find_one({"_id": ObjectId(id)})
            except InvalidId:
                return None
            if document is None:
                return None
            if cls._cache:
                cls._cache.set(coleccion, id, document)

        document = dict(document)
        idAuxiliar = document.pop("_id", None)  
        object_Model = cls(**document)   
        object.__setattr__(object_Model, "_id", idAuxiliar) 
        return object_Model
        
        

    @classmethod
    def init_class(cls, db_collection: pymongo.collection.Collection, indexes:dict[str,str], required_vars: set[str], admissible_vars: set[str]) -> None:
        """ 
        Inicializa los atributos de clase en la inicializacion del sistema.
        Aqui se deben inicializar o asegurar los indices. Tambien se puede
        alguna otra inicialización/comprobaciones o cambios adicionales
        que estime el alumno.

        Parameters
        ----------
            db_collection : pymongo.collection.Collection
                Conexion a la collecion de la base de datos.
            indexes: Dict[str,str]
                Set de indices y tipo de indices para la coleccion
            required_vars : set[str]
                Set de atributos requeridos por el modelo
            admissible_vars : set[str] 
                Set de atributos admitidos por el modelo
        """
        cls._db = db_collection
        cls._required_vars = required_vars
        cls._admissible_vars = admissible_vars

        
        for campo, tipo in indexes.items():
            if tipo == "unique":
                cls._db.create_index([(campo, pymongo.ASCENDING)], unique=True)
            elif tipo == "asc":
                cls._db.create_index([(campo, pymongo.ASCENDING)])
            elif tipo == "geosphere":
                cls._location_var = campo
                cls._admissible_vars = cls._admissible_vars | {campo + "_loc"} #Se añade manualmente la direccion_loc, por si no se pone concretamente en el yml
                cls._db.create_index([(campo + "_loc", pymongo.GEOSPHERE)])

                #El campo que tiene _loc no existirá hasta el primer save, pero no da error colocarle un índice antes

        # Recorrer indexes y crear cada índice segun su tipo: 'unique', 'asc'
        # y 'geosphere'. Comparar el tipo por igualdad, no con el operador 'in'.
        # Ojo con el índice geoespacial: save() guarda el GeoJSON Point en
        # <campo>_loc, luego el índice 2dsphere va sobre <c ampo>_loc, mientras
        # que _location_var debe guardar el nombre del campo base.


class ModelCursor:
    """ 
    Cursor para iterar sobre los documentos del resultado de una
    consulta. Los documentos deben ser devueltos en forma de objetos
    modelo.

    Attributes
    ----------
        model_class : Model
            Clase para crear los modelos de los documentos que se iteran.
        cursor : pymongo.cursor.Cursor
            Cursor de pymongo a iterar

    Methods
    -------
        __iter__() -> Generator
            Devuelve un iterador que recorre los elementos del cursor
            y devuelve los documentos en forma de objetos modelo.
    """

    def __init__(self, model_class: Model, cursor: pymongo.cursor.Cursor):
        """
        Inicializa el cursor con la clase de modelo y el cursor de pymongo

        Parameters
        ----------
            model_class : Model
                Clase para crear los modelos de los documentos que se iteran.
            cursor: pymongo.cursor.Cursor
                Cursor de pymongo a iterar
        """
        self.model = model_class
        self.cursor = cursor    
    
    def __iter__(self) -> Generator:
        """
        Devuelve un iterador que recorre los elementos del cursor
        y devuelve los documentos en forma de objetos modelo.
        Utilizar yield para generar el iterador
        Utilizar la funcion next para obtener el siguiente documento del cursor
        Utilizar alive para comprobar si existen mas documentos.
        """
        while self.cursor.alive: #Mientras haya elementos, aunque esto puede ser True sin que haya documentos
            try:
                document = next(self.cursor)
            except StopIteration:
                break
  
            idAuxiliar = document.pop("_id", None)  #_id no es considerado un campo permitido cuando justo después se cree la clase
            object_Model = self.model(**document)   #Convierte el documento en un objeto de la misma clase
            object.__setattr__(object_Model, "_id", idAuxiliar) #Le devolvemos el id
            yield object_Model                       #Es como un return, pero permite iterar lo que devuelve


def initApp(definitions_path: str = "./models.yml", mongodb_uri="mongodb://localhost:27017/", db_name="abd", scope=globals(),redis_uri : str | None = None) -> None:
    """ 
    Declara las clases que heredan de Model para cada uno de los 
    modelos de las colecciones definidas en definitions_path.
    Inicializa las clases de los modelos proporcionando los indices y 
    atributos admitidos y requeridos para cada una de ellas y la conexión a la
    collecion de la base de datos.
    
    Parameters
    ----------
        definitions_path : str
            ruta al fichero de definiciones de modelos
        mongodb_uri : str
            uri de conexion a la base de datos
        db_name : str
            nombre de la base de datos
    """ 
    # Inicializar base de datos

    client = MongoClient(mongodb_uri)
    db = client[db_name]
    if redis_uri:
        cache = CacheDocumentos(redis.Redis.from_url(redis_uri))
    else:
        cache = None

    with open(definitions_path) as f:
        definitions = yaml.safe_load(f)

    # Declarar tantas clases modelo colecciones existan en la base de datos
    # Leer el fichero de definiciones de modelos para obtener las colecciones,
    # indices y los atributos admitidos y requeridos para cada una de ellas.
    # Ejemplo de declaracion de modelo para colecion llamada MiModelo

    for nombre, definicion in definitions.items():
        # Traducir las tres claves del YAML a un solo dict {campo: tipo}
        indexes = {}
        for campo in definicion.get("unique_indexes", []):
            indexes[campo] = "unique"
        for campo in definicion.get("regular_indexes", []):
            indexes[campo] = "asc"
        if "location_index" in definicion:
            indexes[definicion["location_index"]] = "geosphere"

        scope[nombre] = type(nombre, (Model,), {})
        scope[nombre]._cache = cache
        scope[nombre].init_class(
            db_collection=db[nombre],
            indexes=indexes,
            required_vars=set(definicion["required_vars"]),
            admissible_vars=set(definicion["admissible_vars"]),
        )

    # La clase se declara en tiempo de ejecucion y queda en scope, que no tiene
    # por que ser el espacio de nombres global: las pruebas le pasan su propio
    # diccionario. Por eso se inicializa a traves de scope y no por su nombre,
    # que ahi todavia no existe.

if __name__ == '__main__':
    """
    # Inicializar base de datos y modelos con initApp
    initApp()
    MODELOS = (Recinto, Artista, Asistente, Evento)

    Recinto._db.delete_many({})
    Artista._db.delete_many({})
    Asistente._db.delete_many({})
    Evento._db.delete_many({})
    # Hacer pruebas para comprobar que funciona correctamente el modelo
    
    # Crear modelo
    recinto = Recinto(nombre="Estadio Zapato",direccion="New York, NY",aforo=10000)
    luchork = Artista(nombre="LuchoRK",generos_musicales=["trap", "regeton"],pais_origen="España", anio_inicio_actividad=2022)
    luis = Asistente(nombre="Luis Ojeda",direccion="Bravo Murillo, Las Palmas de Gran Canaria",correo_electronico="luisojeda@gmail.com")
    # Asignar nuevo valor a variable admitida del objeto 
    recinto.aforo= 12000
    luchork.anio_inicio_actividad = 2021
    luis.correo_electronico = "luis.oojeda@gmail.com"
    # Asignar nuevo valor a variable no admitida del objeto 
    #recinto.comida = 2
    # Guardar
    recinto.save()
    luchork.save()
    luis.save()

    #Hacemos lo mismo con evento pero mas tarde para poder coger el id de artista y recinto
    evento_lucho = Evento(titulo="LuchoRK - Sordo de un pie", artistas = [luchork._id], recinto = recinto._id, fecha = datetime(2026, 3, 21), hora = "21:00",precio_por_zona={"Pista": 50.0, "Grada baja": 40.0, "Grada alta": 35.0},entradas_vendidas=8500)
    evento_lucho.fecha = datetime(2026, 4, 21)
    evento_lucho.save()
    # Asignar nuevo valor a variable admitida del objeto
    recinto.nombre="Estadio Farola"
    luchork.generos_musicales = ["trap", "regeton", "bolero"]
    luis.correo_electronico = "luis_ojeda@gmail.com"
    evento_lucho.hora = "20:30"
    # Guardar
    recinto.save()
    luchork.save()
    luis.save()
    evento_lucho.save()
    # Buscar nuevo documento con find
    consulta = next(iter(Recinto.find({"nombre": "Estadio Farola"}))) #next pide el primer resultado

    print("\nNombre:", consulta.nombre)
    print("Dirección:", consulta.direccion)
    print("Aforo:", consulta.aforo)
    print("Coordenadas:", consulta.direccion_loc)
    # Obtener primer documento
    consulta_total = Recinto.find({})
    primero = next(iter(consulta_total), None)

    if primero is not None:
        print("\nNombre:", primero.nombre)
        print("Dirección:", primero.direccion)
        print("Aforo:", primero.aforo)
        print("Coordenadas:", consulta.direccion_loc)

    # Modificar valor de variable admitida
    primero.aforo += 500
    # Guardar
    primero.save()

    consultaArtista = next(iter(Artista.find({"nombre": "LuchoRK"}))) 
    
    print("\nNombre:", consultaArtista.nombre)
    print("Generos musicales:", consultaArtista.generos_musicales)
    print("Pais de origen:", consultaArtista.pais_origen)
    print("Anio de inicio de actividad:", consultaArtista.anio_inicio_actividad)
    # Obtener primer documento
    consultaArtista_total = Artista.find({})
    primeroArtista = next(iter(consultaArtista_total), None)
    
    if primeroArtista is not None:
        print("\nNombre:", primeroArtista.nombre)
        print("Generos musicales:", primeroArtista.generos_musicales)
        print("Pais de origen:", primeroArtista.pais_origen)
        print("Anio de inicio de actividad:", primeroArtista.anio_inicio_actividad)

    # Modificar valor de variable admitida
    primeroArtista.anio_inicio_actividad = 2020
    # Guardar
    primeroArtista.save()

    consultaAsistente = next(iter(Asistente.find({"nombre": "Luis Ojeda"}))) 
    
    print("\nNombre:", consultaAsistente.nombre)
    print("Correo electronico:", consultaAsistente.correo_electronico)
    print("Direccion:", consultaAsistente.direccion)
    # Obtener primer documento
    consultaAsistente_total = Asistente.find({})
    primeroAsistente = next(iter(consultaAsistente_total), None)
    
    if primeroAsistente is not None:
        print("\nNombre:", primeroAsistente.nombre)
        print("Correo electronico:", primeroAsistente.correo_electronico)
        print("Direccion:", primeroAsistente.direccion)

    # Modificar valor de variable admitida
    primeroAsistente.direccion = "Primero de Mayo, Las Palmas de Gran Canaria"
    # Guardar
    primeroAsistente.save()

    consultaEvento = next(iter(Evento.find({"titulo": "LuchoRK - Sordo de un pie"}))) 
    
    print("\nTitulo:", consultaEvento.titulo)
    print("Artistas:", consultaEvento.artistas)
    print("Recinto:", consultaEvento.recinto)
    print("Fecha:", consultaEvento.fecha)
    print("Hora:", consultaEvento.hora)
    print("Precio por zona:", consultaEvento.precio_por_zona)
    print("Entradas vendidas:", consultaEvento.entradas_vendidas)
    # Obtener primer documento
    consultaEvento_total = Evento.find({})
    primeroEvento = next(iter(consultaEvento_total), None)
    
    if primeroEvento is not None:
        print("\nTitulo:", consultaEvento.titulo)
        print("Artistas:", consultaEvento.artistas)
        print("Recinto:", consultaEvento.recinto)
        print("Fecha:", consultaEvento.fecha)
        print("Hora:", consultaEvento.hora)
        print("Precio por zona:", consultaEvento.precio_por_zona)
        print("Entradas vendidas:", consultaEvento.entradas_vendidas)

    # Modificar valor de variable admitida
    primeroEvento.entradas_vendidas += 50
    # Guardar
    primeroEvento.save()

    for clase in MODELOS:
        documentos = list(clase._db.find({}))
        fichero = f"{clase._db.name}.json"
        with open(fichero, "w", encoding="utf-8") as f:
            f.write(json_util.dumps(documentos, indent=2, ensure_ascii=False))
        print(f"  {fichero:16} -> {len(documentos)} documentos")    """