import json
import re
import unicodedata
from pathlib import Path


class InstanceChoiceStore:
    """Recuerda la ruta de instancias confirmada para persona y entidad."""

    def __init__(self, ruta=None):
        self.ruta = ruta or (
            Path(__file__).resolve().parents[2] / "data" / "instance_choices.json"
        )
        self.elecciones = self._cargar()

    def obtener(self, persona, entidad):
        clave = self._clave(persona, entidad)
        if not clave:
            return {}
        if clave in self.elecciones:
            return self.elecciones[clave]

        persona_normalizada, entidad_normalizada = clave.split("|", 1)
        palabras_entidad = set(entidad_normalizada.split())
        if not palabras_entidad:
            return {}
        prefijo_persona = f"{persona_normalizada}|"
        for clave_guardada, eleccion in self.elecciones.items():
            if not clave_guardada.startswith(prefijo_persona):
                continue
            entidad_guardada = clave_guardada.split("|", 1)[1]
            palabras_guardadas = set(entidad_guardada.split())
            # Acepta "Amsterdam" frente a "Gemeente Amsterdam", pero no
            # mezcla entidades distintas que solo comparten una palabra.
            if palabras_entidad <= palabras_guardadas or palabras_guardadas <= palabras_entidad:
                return eleccion
        return {}

    def guardar(self, persona, entidad, instancia_1, instancia_2="", instancia_3=""):
        clave = self._clave(persona, entidad)
        instancia_1 = (instancia_1 or "").strip()
        if not clave or not instancia_1:
            return False

        eleccion = {
            "instancia_1": instancia_1,
            "instancia_2": (instancia_2 or "").strip(),
            "instancia_3": (instancia_3 or "").strip(),
        }
        if self.elecciones.get(clave) == eleccion:
            return False

        self.elecciones[clave] = eleccion
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(
            json.dumps(self.elecciones, ensure_ascii=False, indent=2),
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
                if isinstance(clave, str)
                and isinstance(valor, dict)
                and isinstance(valor.get("instancia_1"), str)
            }
        except (OSError, json.JSONDecodeError):
            return {}

    def _clave(self, persona, entidad):
        persona = self._normalizar(persona)
        entidad = self._normalizar(entidad)
        if not persona or not entidad or "no identificado" in persona or "no identificada" in entidad:
            return ""
        return f"{persona}|{entidad}"

    @staticmethod
    def _normalizar(valor):
        if not valor:
            return ""
        valor = unicodedata.normalize("NFD", valor.lower())
        valor = "".join(caracter for caracter in valor if not unicodedata.combining(caracter))
        return " ".join(re.findall(r"[a-z0-9]+", valor))
