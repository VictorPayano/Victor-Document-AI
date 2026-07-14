from pathlib import Path

import fitz
import pytesseract
from PIL import Image


class Extractor:

    def extraer(self, archivo: Path) -> str:

        texto = self._extraer_pdf(archivo)

        # Si el PDF ya contiene texto, no hacemos OCR
        if len(texto.strip()) > 50:
            print("✅ PDF editable detectado")
            return texto

        print("📄 PDF escaneado. Ejecutando OCR...")

        return self._extraer_ocr(archivo)

    # -------------------------------------------------

    def _extraer_pdf(self, archivo: Path) -> str:

        texto = ""

        pdf = fitz.open(archivo)

        for pagina in pdf:
            texto += pagina.get_text()

        pdf.close()

        return texto

    # -------------------------------------------------

    def _extraer_ocr(self, archivo: Path) -> str:

        texto = ""

        pdf = fitz.open(archivo)

        for pagina in pdf:

            pix = pagina.get_pixmap(dpi=300)

            imagen = Image.frombytes(
                "RGB",
                [pix.width, pix.height],
                pix.samples
            )

            texto += pytesseract.image_to_string(
                imagen,
                lang="nld+spa+eng"
            )

        pdf.close()

        return texto