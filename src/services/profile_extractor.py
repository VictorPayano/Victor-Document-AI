"""Extracción estructurada de datos de una ficha familiar desde un documento."""

import json
import re
from pathlib import Path

from openai import OpenAI

from services.family_database import FamilyDatabase
from services.translator import Translator


class ProfileExtractor(Translator):
    MAX_PAGINAS_FICHA = 8

    def extract(self, file_path):
        api_key = self._obtener_api_key()
        if not api_key:
            raise RuntimeError("No se encontró OPENAI_API_KEY para leer el documento.")
        file_path = Path(file_path)
        pages = self._paginas(file_path)
        if not pages:
            raise RuntimeError("No se pudieron obtener páginas del documento.")

        schema = {
            "basic": {
                "given_names": "", "surname": "", "date_of_birth": "", "tax_number": "",
                "reference_notes": "", "address": "", "postcode": "", "city": "", "country": "", "note": "",
            },
            **{table: [dict.fromkeys(fields, "")] for table, (_, fields) in FamilyDatabase.RELATED.items()},
        }
        instruction = (
            "Extrae solamente datos visibles y claros de este documento para una ficha familiar. "
            "No inventes, no completes por suposición y deja vacío todo dato que no aparezca. "
            "Nunca extraigas ni devuelvas contraseñas, PIN, códigos secretos o CVV. "
            "Fechas en formato AAAA-MM-DD cuando sea posible. Para documentos de identidad, rellena "
            "basic y documents; para contratos, services; para seguros, insurances; para banco, bank_accounts. "
            "Devuelve ÚNICAMENTE JSON válido con esta estructura exacta, usando listas vacías cuando no haya datos:\n"
            + json.dumps(schema, ensure_ascii=False)
        )
        content = [{"type": "input_text", "text": instruction}]
        for image, mime_type in pages[:self.MAX_PAGINAS_FICHA]:
            content.append({
                "type": "input_image",
                "image_url": self._data_url(image, mime_type),
                "detail": "high",
            })
        response = OpenAI(api_key=api_key).responses.create(
            model="gpt-4o",
            input=[{"role": "user", "content": content}],
        )
        return self._parse(response.output_text)

    @staticmethod
    def _parse(text):
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", cleaned, flags=re.IGNORECASE)
        start, end = cleaned.find("{"), cleaned.rfind("}")
        if start < 0 or end < start:
            raise RuntimeError("La IA no devolvió datos estructurados. Inténtalo de nuevo.")
        try:
            data = json.loads(cleaned[start:end + 1])
        except json.JSONDecodeError as error:
            raise RuntimeError("La respuesta del documento no se pudo interpretar.") from error
        if not isinstance(data, dict):
            raise RuntimeError("La respuesta del documento no tiene el formato esperado.")
        return data
