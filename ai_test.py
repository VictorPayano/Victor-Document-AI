import json
import os

from dotenv import load_dotenv
from openai import OpenAI

# ============================
# Cargar variables de entorno
# ============================

load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")

if not api_key:
    raise RuntimeError("No se encontró OPENAI_API_KEY en el archivo .env")

client = OpenAI(api_key=api_key)

from pathlib import Path
from src.services.extractor import Extractor

archivo = Path(r"D:\Entrada\Document (2).pdf")   # <-- cambia aquí el documento

extractor = Extractor()

texto = extractor.extraer(archivo)

prompt = f"""
Eres un experto en clasificación documental.

Analiza el siguiente documento.

Devuelve EXCLUSIVAMENTE un JSON válido.

Los campos son:

categoria
tipo_documento
empresa
persona
fecha_documento
resumen
confianza

Documento:

{texto}
"""

respuesta = client.chat.completions.create(
    model="gpt-5.5",
    messages=[
        {
            "role": "system",
            "content": "Responde únicamente con JSON válido."
        },
        {
            "role": "user",
            "content": prompt
        }
    ],
    response_format={"type": "json_object"}
)


resultado = json.loads(respuesta.choices[0].message.content)

print("\n==============================")
print("RESPUESTA DE LA IA")
print("==============================\n")

print(json.dumps(resultado, indent=4, ensure_ascii=False))