from pathlib import Path


class Settings:

    def __init__(self):

        self.origen = Path(r"D:\Entrada")
        self.destino = Path(r"D:\Documentos")

    def set_origen(self, carpeta):

        self.origen = Path(carpeta)

    def set_destino(self, carpeta):

        self.destino = Path(carpeta)