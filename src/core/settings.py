from pathlib import Path
import json


class Settings:

    def __init__(self, ruta_config=None):

        self.origen = Path(r"D:\Entrada")
        self.destino = Path(r"D:\Documentos")
        self.ocr_idioma = "nld+spa+eng"
        self.impresora = ""
        self.ruta_config = ruta_config or (
            Path(__file__).resolve().parents[2] / "data" / "settings.json"
        )
        self._cargar()

    def set_origen(self, carpeta):

        self.origen = Path(carpeta)
        self._guardar()

    def set_destino(self, carpeta):

        self.destino = Path(carpeta)
        self._guardar()

    def set_ocr_idioma(self, idioma):

        self.ocr_idioma = idioma
        self._guardar()

    def set_impresora(self, impresora):

        self.impresora = impresora
        self._guardar()

    def _cargar(self):

        if not self.ruta_config.exists():
            return

        try:
            datos = json.loads(self.ruta_config.read_text(encoding="utf-8"))
            self.origen = Path(datos.get("origen", self.origen))
            self.destino = Path(datos.get("destino", self.destino))
            self.ocr_idioma = datos.get("ocr_idioma", self.ocr_idioma)
            self.impresora = datos.get("impresora", self.impresora)
        except (OSError, json.JSONDecodeError):
            pass

    def _guardar(self):

        self.ruta_config.parent.mkdir(parents=True, exist_ok=True)
        datos = {
            "origen": str(self.origen),
            "destino": str(self.destino),
            "ocr_idioma": self.ocr_idioma,
            "impresora": self.impresora,
        }
        self.ruta_config.write_text(
            json.dumps(datos, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
