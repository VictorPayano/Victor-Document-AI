from pathlib import Path
import shutil


class DocumentManager:

    def mover(self, origen: Path, destino: Path):

        destino.mkdir(parents=True, exist_ok=True)

        nuevo_archivo = destino / origen.name

        shutil.move(str(origen), str(nuevo_archivo))

        return nuevo_archivo