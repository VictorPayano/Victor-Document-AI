import json
import re
from pathlib import Path


class InstanceStore:
    """Catálogo central de instancia, subinstancia y sub/subinstancia."""

    def __init__(self, ruta=None):
        self.ruta = ruta or (
            Path(__file__).resolve().parents[2] / "data" / "instances.json"
        )
        self.instancias = self._cargar()

    def listar(self):
        return self._nombres(self.instancias)

    def hijos(self, *niveles):
        nodos = self.instancias
        for nivel in (nivel.strip() for nivel in niveles if nivel and nivel.strip()):
            nodo = self._buscar(nodos, nivel)
            if nodo is None:
                return []
            nodos = nodo["hijos"]
        return self._nombres(nodos)

    def agregar(self, instancia):
        return self.agregar_ruta(instancia)

    def agregar_ruta(self, *niveles):
        niveles = [nivel.strip() for nivel in niveles if nivel and nivel.strip()]
        if not niveles:
            return False

        cambio = self._agregar_en_memoria(niveles)
        if cambio:
            self._guardar()
        return cambio

    def eliminar_ruta(self, *niveles):
        niveles = [nivel.strip() for nivel in niveles if nivel and nivel.strip()]
        if not niveles:
            return False

        nodos = self.instancias
        for nivel in niveles[:-1]:
            nodo = self._buscar(nodos, nivel)
            if nodo is None:
                return False
            nodos = nodo["hijos"]

        nodo = self._buscar(nodos, niveles[-1])
        if nodo is None:
            return False
        nodos.remove(nodo)
        self._guardar()
        return True

    def renombrar_ruta(self, *niveles, nuevo_nombre):
        niveles = [nivel.strip() for nivel in niveles if nivel and nivel.strip()]
        nuevo_nombre = nuevo_nombre.strip()
        if not niveles or not nuevo_nombre:
            raise ValueError("El nombre no puede estar vacío.")

        nodos = self.instancias
        for nivel in niveles[:-1]:
            padre = self._buscar(nodos, nivel)
            if padre is None:
                return False
            nodos = padre["hijos"]

        nodo = self._buscar(nodos, niveles[-1])
        if nodo is None:
            return False
        existente = self._buscar(nodos, nuevo_nombre)
        if existente is not None and existente is not nodo:
            raise ValueError("Ya existe una instancia con ese nombre en este nivel.")
        if nodo["nombre"] == nuevo_nombre:
            return False

        nodo["nombre"] = nuevo_nombre
        self._guardar()
        return True

    def importar_desde_personas(self, raiz_personas):
        """Copia la estructura existente una sola vez al catálogo central."""
        raiz_personas = Path(raiz_personas)
        cambio = False
        try:
            personas = [carpeta for carpeta in raiz_personas.iterdir() if carpeta.is_dir()]
        except OSError:
            return False

        for persona in personas:
            for instancia_1 in self._carpetas_no_anuales(persona):
                cambio |= self._agregar_en_memoria([instancia_1.name])
                for instancia_2 in self._carpetas_no_anuales(instancia_1):
                    cambio |= self._agregar_en_memoria(
                        [instancia_1.name, instancia_2.name]
                    )
                    for instancia_3 in self._carpetas_no_anuales(instancia_2):
                        cambio |= self._agregar_en_memoria(
                            [instancia_1.name, instancia_2.name, instancia_3.name]
                        )

        if cambio:
            self._guardar()
        return cambio

    @staticmethod
    def _carpetas_no_anuales(ruta):
        try:
            return [
                carpeta for carpeta in ruta.iterdir()
                if carpeta.is_dir() and not re.fullmatch(r"(?:19|20)\d{2}", carpeta.name)
            ]
        except OSError:
            return []

    def _agregar_en_memoria(self, niveles):
        nodos = self.instancias
        cambio = False
        for nivel in niveles:
            nodo = self._buscar(nodos, nivel)
            if nodo is None:
                nodo = {"nombre": nivel, "hijos": []}
                nodos.append(nodo)
                cambio = True
            nodos = nodo["hijos"]
        return cambio

    @staticmethod
    def _buscar(nodos, nombre):
        nombre_normalizado = nombre.casefold()
        return next(
            (nodo for nodo in nodos if nodo["nombre"].casefold() == nombre_normalizado),
            None,
        )

    @staticmethod
    def _nombres(nodos):
        return sorted((nodo["nombre"] for nodo in nodos), key=str.lower)

    def _guardar(self):
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(
            json.dumps({"instancias": self.instancias}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _cargar(self):
        if not self.ruta.exists():
            return []

        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return []

        # Compatibilidad con el antiguo catálogo plano: ["Banco", "DWI"].
        if isinstance(datos, list):
            return [
                {"nombre": nombre, "hijos": []}
                for nombre in datos if isinstance(nombre, str) and nombre.strip()
            ]

        if not isinstance(datos, dict) or not isinstance(datos.get("instancias"), list):
            return []
        return self._normalizar_nodos(datos["instancias"])

    def _normalizar_nodos(self, nodos):
        resultado = []
        for nodo in nodos:
            if not isinstance(nodo, dict) or not isinstance(nodo.get("nombre"), str):
                continue
            nombre = nodo["nombre"].strip()
            if not nombre:
                continue
            resultado.append({
                "nombre": nombre,
                "hijos": self._normalizar_nodos(nodo.get("hijos", [])),
            })
        return resultado
