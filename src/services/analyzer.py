from pathlib import Path

from services.extractor import Extractor
from services.analyzer_filename import AnalyzerFilename
from services.analyzer_text import AnalyzerText


class Analyzer:

    def __init__(self):

        self.extractor = Extractor()
        self.filename = AnalyzerFilename()
        self.text = AnalyzerText()

    # ================================
    # Analizar documento
    # ================================

    def analizar(self, archivo: Path):

        print("\n===================================")
        print("ANALYZER")
        print("Archivo:", archivo)
        print("===================================\n")

        texto = self.extractor.extraer(archivo)

        if texto.strip():

            print("Analizando contenido del documento...")

            resultado = self.text.analizar(texto)
            resultado["texto"] = texto
            return resultado

        print("No se encontro texto. Analizando nombre del archivo...")
        resultado = self.filename.analizar(archivo)
        resultado["texto"] = ""
        return resultado

    def aprender_destino(
        self,
        resultado,
        destino,
        persona_elegida=None,
        instancias_elegidas=None,
    ):

        self.text.aprender_destino(
            resultado,
            destino,
            persona_elegida,
            instancias_elegidas,
        )
