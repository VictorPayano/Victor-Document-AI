from pathlib import Path
from models.persona import Persona


class Descubrimiento:

    def __init__(self, ruta):

        self.ruta = Path(ruta)

    def detectar_personas(self):

        personas = []

        if not self.ruta.exists():
            return personas

        for carpeta in sorted(self.ruta.iterdir()):

            if not carpeta.is_dir():
                continue

            persona = Persona()

            persona.nombre = carpeta.name

            persona.ruta = str(carpeta)

            persona.total_documentos = self.contar_documentos(carpeta)

            personas.append(persona)

        return personas

    def contar_documentos(self, carpeta):

        contador = 0

        for archivo in carpeta.rglob("*"):

            if archivo.is_file():

                contador += 1

        return contador