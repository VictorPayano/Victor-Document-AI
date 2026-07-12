from pathlib import Path

from services.analyzer import Analyzer
from services.document_manager import DocumentManager


class Pipeline:

    def __init__(self):

        self.analyzer = Analyzer()
        self.document_manager = DocumentManager()

    # ================================
    # Analizar
    # ================================

    def procesar(self, archivo: Path):

        print("PIPELINE:", archivo)

        resultado = self.analyzer.analizar(archivo)

        print(resultado)

        return resultado

    # ================================
    # Mover documento
    # ================================

    def aceptar(self, archivo: Path, destino: str, ruta_base: Path):

        print("PIPELINE ACEPTAR")
        print("Archivo:", archivo)
        print("Destino IA:", destino)
        print("Ruta base:", ruta_base)

        carpeta = ruta_base / destino

        print("Carpeta final:", carpeta)

        return self.document_manager.mover(
            archivo,
            carpeta
        )