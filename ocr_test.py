from pathlib import Path

from src.services.extractor import Extractor

archivo = Path(r"D:\Entrada\Documentscan 5.pdf")

extractor = Extractor()

texto = extractor.extraer(archivo)

print("\n")
print("=" * 80)
print(texto)
print("=" * 80)