import json
import re
import unicodedata
from pathlib import Path


class PersonAliasStore:
    """Equivalencias entre el nombre detectado por OCR y la carpeta de persona."""

    def __init__(self, ruta=None):
        self.ruta = ruta or (
            Path(__file__).resolve().parents[2] / "data" / "person_aliases.json"
        )
        self.aliases = self._cargar()

    def obtener(self, nombre_detectado):
        clave = self.normalizar(nombre_detectado)
        return self.aliases.get(clave) if clave else None

    def guardar(self, nombre_detectado, persona):
        clave = self.normalizar(nombre_detectado)
        persona = (persona or "").strip()
        if not clave or not persona or "no identificado" in persona.lower():
            return False
        if self.aliases.get(clave) == persona:
            return False

        self.aliases[clave] = persona
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(
            json.dumps(self.aliases, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return True

    def _cargar(self):
        if not self.ruta.exists():
            return {}
        try:
            datos = json.loads(self.ruta.read_text(encoding="utf-8"))
            return {
                clave: valor for clave, valor in datos.items()
                if isinstance(clave, str) and isinstance(valor, str)
            }
        except (OSError, json.JSONDecodeError):
            return {}

    @staticmethod
    def normalizar(valor):
        if not valor:
            return ""
        valor = unicodedata.normalize("NFD", valor.lower())
        valor = "".join(caracter for caracter in valor if not unicodedata.combining(caracter))
        return " ".join(re.findall(r"[a-z0-9]+", valor))
