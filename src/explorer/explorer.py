from pathlib import Path


class Explorer:

    def __init__(self):

        self.ruta_actual = None

    def abrir(self, ruta):
        """
        Abre una carpeta y devuelve todos sus elementos.
        Primero devuelve las carpetas y luego los archivos.
        """

        self.ruta_actual = Path(ruta)

        elementos = []

        if not self.ruta_actual.exists():
            return elementos

        # ==========================
        # Carpetas
        # ==========================

        carpetas = []

        for elemento in self.ruta_actual.iterdir():

            if elemento.is_dir():

                carpetas.append({
                    "nombre": elemento.name,
                    "ruta": elemento,
                    "tipo": "carpeta"
                })

        carpetas.sort(key=lambda x: x["nombre"].lower())

        elementos.extend(carpetas)

        # ==========================
        # Archivos
        # ==========================

        archivos = []

        for elemento in self.ruta_actual.iterdir():

            if elemento.is_file():

                archivos.append({
                    "nombre": elemento.name,
                    "ruta": elemento,
                    "tipo": "archivo"
                })

        archivos.sort(key=lambda x: x["nombre"].lower())

        elementos.extend(archivos)

        return elementos