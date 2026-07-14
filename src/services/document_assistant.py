from pathlib import Path

from openai import OpenAI

from services.translator import Translator


class DocumentAssistant(Translator):
    """Consultas de IA sobre el documento original, siempre para revisión humana."""

    INSTRUCCIONES = {
        "resumen": (
            "Resume este documento de forma clara y breve. Indica remitente, destinatario, "
            "fecha, asunto, importes, referencias y puntos importantes."
        ),
        "acciones": (
            "Explica qué solicita esta correspondencia y qué acciones debe tomar el destinatario. "
            "Destaca plazos, importes, datos que faltan y consecuencias. Si algo no está claro, indícalo."
        ),
        "respuesta": (
            "Prepara un borrador de respuesta educada al remitente. No inventes datos personales, "
            "números ni hechos: usa marcadores entre corchetes donde falte información."
        ),
        "traduccion": "Traduce fielmente el documento, sin resumir ni añadir comentarios.",
    }

    def consultar(self, archivo, tarea, idioma="español"):
        api_key = self._obtener_api_key()
        if not api_key:
            raise RuntimeError("No se encontró OPENAI_API_KEY en la configuración del proyecto.")

        archivo = Path(archivo)
        paginas = self._paginas(archivo)
        if len(paginas) > self.MAX_PAGINAS:
            raise RuntimeError(
                f"El documento tiene {len(paginas)} páginas. El máximo es {self.MAX_PAGINAS}."
            )

        instruccion = self.INSTRUCCIONES.get(tarea, self.INSTRUCCIONES["resumen"])
        contenido = [{
            "type": "input_text",
            "text": (
                f"{instruccion} Responde en {idioma}. Usa las imágenes originales como fuente "
                "de verdad. Conserva nombres, fechas, importes y referencias. No des asesoramiento "
                "legal definitivo; indica cuando sea necesaria una revisión profesional."
            ),
        }]
        for imagen, tipo in paginas:
            contenido.append({
                "type": "input_image",
                "image_url": self._data_url(imagen, tipo),
                "detail": "high",
            })

        respuesta = OpenAI(api_key=api_key).responses.create(
            model="gpt-4o",
            input=[{"role": "user", "content": contenido}],
        )
        return respuesta.output_text.strip()
