from pathlib import Path

ruta = Path(r"F:\Syncthing\AGIS\2019\CAK")   # Pon aquí una carpeta que tenga PDFs

print("Existe:", ruta.exists())

print("\nArchivos encontrados:\n")

for archivo in ruta.iterdir():
    print(archivo.name)

print("\nSolo PDFs:\n")

for pdf in ruta.glob("*.pdf"):
    print(pdf.name)