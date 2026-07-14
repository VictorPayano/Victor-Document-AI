import json
import unicodedata
from pathlib import Path


class LearningStore:

    def __init__(self, ruta=None):
        self.ruta = ruta or (
            Path(__file__).resolve().parents[2] / "data" / "learning.json"
        )
        self.destinos = self._cargar()

    def obtener_destino(self, persona, entidad):
        if not self._dato_valido(persona) or not self._dato_valido(entidad):
            return None

        clave = self._clave(persona, entidad)
        return self.destinos.get(clave)

    def guardar_destino(self, persona, entidad, destino):
        if not self._dato_valido(persona) or not self._dato_valido(entidad):
            return

        self.destinos[self._clave(persona, entidad)] = str(destino)
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(
            json.dumps(self.destinos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _cargar(self):
        if not self.ruta.exists():
            return {}

        try:
            return json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def _dato_valido(valor):
        return bool(valor) and "no identificado" not in valor.lower()

    def _clave(self, persona, entidad):
        return "|".join((self._normalizar(persona), self._normalizar(entidad)))

    @staticmethod
    def _normalizar(valor):
        valor = unicodedata.normalize("NFD", valor.lower())
        return "".join(caracter for caracter in valor if not unicodedata.combining(caracter))
