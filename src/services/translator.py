import base64
import mimetypes
import os
from pathlib import Path

import fitz
from openai import OpenAI


class Translator:

    MAX_PAGINAS = 20
    RUTA_ENV = Path(__file__).resolve().parents[2] / ".env"

    def traducir(self, archivo, idioma_destino):
        api_key = self._obtener_api_key()
        if not api_key:
            raise RuntimeError(
                "No se encontró OPENAI_API_KEY. Configúrala como variable de entorno."
            )

        archivo = Path(archivo)
        cliente = OpenAI(api_key=api_key)
        paginas = self._paginas(archivo)

        if len(paginas) > self.MAX_PAGINAS:
            raise RuntimeError(
                f"El documento tiene {len(paginas)} páginas. El máximo es {self.MAX_PAGINAS}."
            )

        traducciones = []
        for numero, imagen in enumerate(paginas, start=1):
            respuesta = cliente.responses.create(
                model="gpt-4o",
                input=[{
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                f"Traduce fielmente esta página al {idioma_destino}. "
                                "Usa la imagen original como fuente de verdad. Conserva "
                                "nombres propios, direcciones, importes, fechas, referencias "
                                "y estructura de párrafos. No resumas ni añadas comentarios. "
                                "Devuelve únicamente la traducción."
                            ),
                        },
                        {
                            "type": "input_image",
                            "image_url": self._data_url(*imagen),
                            "detail": "high",
                        },
                    ],
                }],
            )
            traducciones.append(f"--- Página {numero} ---\n{respuesta.output_text.strip()}")

        return "\n\n".join(traducciones)

    def _obtener_api_key(self):

        api_key = os.getenv("OPENAI_API_KEY")
        if api_key:
            return api_key

        if not self.RUTA_ENV.exists():
            return None

        try:
            for linea in self.RUTA_ENV.read_text(encoding="utf-8").splitlines():
                clave, separador, valor = linea.partition("=")
                if clave.strip() == "OPENAI_API_KEY" and separador:
                    return valor.strip().strip('"').strip("'") or None
        except OSError:
            return None

        return None

    def _paginas(self, archivo):
        if archivo.suffix.lower() == ".pdf":
            with fitz.open(archivo) as pdf:
                return [
                    (pagina.get_pixmap(dpi=160, alpha=False).tobytes("png"), "image/png")
                    for pagina in pdf
                ]

        tipo, _ = mimetypes.guess_type(archivo.name)
        return [(archivo.read_bytes(), tipo or "image/png")]

    @staticmethod
    def _data_url(imagen, tipo):
        contenido = base64.b64encode(imagen).decode("ascii")
        return f"data:{tipo};base64,{contenido}"
