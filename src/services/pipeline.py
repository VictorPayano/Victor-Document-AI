from pathlib import Path

from services.analyzer import Analyzer
from services.document_catalog import DocumentCatalog
from services.document_manager import DocumentManager


class Pipeline:

    def __init__(self):

        self.analyzer = Analyzer()
        self.document_manager = DocumentManager()
        self.document_catalog = DocumentCatalog()

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

    def aceptar(self, archivo: Path, destino: str, ruta_base: Path, nombre=None):

        print("PIPELINE ACEPTAR")
        print("Archivo:", archivo)
        print("Destino IA:", destino)
        print("Ruta base:", ruta_base)

        carpeta = ruta_base / destino

        print("Carpeta final:", carpeta)

        nuevo_archivo = self.document_manager.mover(
            archivo,
            carpeta,
            nombre
        )
        try:
            self.document_catalog.agregar_documento(
                nuevo_archivo,
                Path(ruta_base) / "Personas",
            )
        except Exception as error:
            # El documento ya está guardado; un fallo del índice nunca debe
            # impedir ni revertir el archivado en el NAS.
            print("No se pudo actualizar el catálogo local:", error)
        return nuevo_archivo

    def aprender_destino(
        self,
        resultado,
        destino,
        persona_elegida=None,
        instancias_elegidas=None,
    ):

        self.analyzer.aprender_destino(
            resultado,
            destino,
            persona_elegida,
            instancias_elegidas,
        )
