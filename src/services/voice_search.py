from pathlib import Path

from openai import OpenAI

from services.translator import Translator


class VoiceSearch:
    """Transcribe órdenes de búsqueda pronunciadas por el usuario."""

    def transcribir(self, archivo_audio):
        api_key = Translator()._obtener_api_key()
        if not api_key:
            raise RuntimeError("No se encontró OPENAI_API_KEY para transcribir la voz.")

        with Path(archivo_audio).open("rb") as audio:
            respuesta = OpenAI(api_key=api_key).audio.transcriptions.create(
                model="gpt-4o-mini-transcribe",
                file=audio,
                language="es",
                prompt=(
                    "Orden de búsqueda de documentos en español u holandés. "
                    "Puede incluir nombres de personas, entidades holandesas, meses y años."
                ),
            )
        return respuesta.text.strip()
