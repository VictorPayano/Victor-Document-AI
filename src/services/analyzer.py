from pathlib import Path

from services.pdf_reader import PDFReader
from services.analyzer_filename import AnalyzerFilename
from services.analyzer_text import AnalyzerText


class Analyzer:

    def __init__(self):

        self.pdf_reader = PDFReader()
        self.filename = AnalyzerFilename()
        self.text = AnalyzerText()

    def analizar(self, archivo: Path):

        texto = self.pdf_reader.extraer_texto(archivo)

        print("\n========== TEXTO EXTRAÍDO ==========\n")
        print(texto[:3000])
        print("\n====================================\n")

        if texto:

            print("📄 Analizando contenido del PDF...")

            return self.text.analizar(texto)

        print("📁 Analizando nombre del archivo...")

        return self.filename.analizar(archivo)