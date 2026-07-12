from pathlib import Path
import fitz  # PyMuPDF


class PDFReader:

    def extraer_texto(self, archivo: Path) -> str:
        """
        Extrae todo el texto de un PDF.
        Si no encuentra texto devuelve una cadena vacía.
        """

        texto = ""

        try:
            pdf = fitz.open(archivo)

            for pagina in pdf:
                texto += pagina.get_text()

            pdf.close()

        except Exception as e:
            print(f"Error leyendo PDF: {e}")

        return texto.strip()
    
if __name__ == "__main__":

    reader = PDFReader()

    texto = reader.extraer_texto(
        Path(r"D:\Entrada\Document (2).pdf")
    )

    print("============== TEXTO ==============")
    print(texto)