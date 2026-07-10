from pathlib import Path


class Inventario:

    def __init__(self, ruta):

        self.ruta = Path(ruta)

    def analizar(self):

        print("\nAnalizando biblioteca...\n")

        contador = 0

        for archivo in self.ruta.rglob("*"):

            if archivo.is_file():

                contador += 1

                print(f"{contador:>3}  {archivo.name}")

                if contador == 10:
                    break

        print("\nFin de la prueba.")