import json
from pathlib import Path


class AnalysisCache:

    def __init__(self, ruta=None):
        self.ruta = ruta or (
            Path(__file__).resolve().parents[2] / "data" / "analysis_dates.json"
        )
        self.datos = self._cargar()

    def obtener_fecha(self, archivo):
        dato = self._obtener_dato(archivo)
        return dato.get("fecha") if dato else None

    def obtener_persona(self, archivo):
        dato = self._obtener_dato(archivo)
        return dato.get("persona") if dato else None

    def guardar_fecha(self, archivo, fecha):
        self._guardar_dato(archivo, fecha=fecha)

    def guardar_persona(self, archivo, persona):
        self._guardar_dato(archivo, persona=persona)

    def _obtener_dato(self, archivo):
        archivo = Path(archivo)
        clave = str(archivo)
        dato = self.datos.get(clave)
        if not dato:
            return None

        try:
            estadisticas = archivo.stat()
        except OSError:
            return None

        if (
            dato.get("tamano") != estadisticas.st_size
            or dato.get("modificado") != estadisticas.st_mtime_ns
        ):
            return None

        return dato

    def _guardar_dato(self, archivo, **campos):
        archivo = Path(archivo)
        try:
            estadisticas = archivo.stat()
        except OSError:
            return

        datos = self.datos.get(str(archivo), {})
        datos.update(campos)
        datos.update({
            "tamano": estadisticas.st_size,
            "modificado": estadisticas.st_mtime_ns,
        })
        self.datos[str(archivo)] = datos
        self.ruta.parent.mkdir(parents=True, exist_ok=True)
        self.ruta.write_text(
            json.dumps(self.datos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _cargar(self):
        if not self.ruta.exists():
            return {}

        try:
            return json.loads(self.ruta.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
