from pathlib import Path
from datetime import datetime
import json
import re
import shutil
import hashlib


class DocumentoDuplicadoError(FileExistsError):

    def __init__(self, existente):
        self.existente = Path(existente)
        super().__init__(f"Ya existe un documento idéntico: {self.existente.name}")


class DocumentManager:

    def mover(self, origen: Path, destino: Path, nombre=None):

        destino.mkdir(parents=True, exist_ok=True)

        nombre = self._normalizar_nombre(nombre or origen.name, origen.suffix)
        duplicado = self._buscar_duplicado(origen, destino)
        if duplicado is not None:
            raise DocumentoDuplicadoError(duplicado)
        nuevo_archivo = self._ruta_disponible(destino, nombre)

        shutil.move(str(origen), str(nuevo_archivo))
        self._registrar_ultimo_guardado(nuevo_archivo)

        return nuevo_archivo

    @staticmethod
    def _registrar_ultimo_guardado(archivo):
        ruta = Path(__file__).resolve().parents[2] / "data" / "last_saved.json"
        try:
            ruta.parent.mkdir(parents=True, exist_ok=True)
            ruta.write_text(
                json.dumps(
                    {
                        "nombre": archivo.name,
                        "ruta": str(archivo),
                        "guardado_en": datetime.now().isoformat(timespec="seconds"),
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
                encoding="utf-8",
            )
        except OSError:
            pass

    @classmethod
    def _buscar_duplicado(cls, origen, destino):
        try:
            tamano = origen.stat().st_size
            candidatos = (
                archivo for archivo in destino.iterdir()
                if archivo.is_file() and archivo.stat().st_size == tamano
            )
            huella_origen = None
            for candidato in candidatos:
                if huella_origen is None:
                    huella_origen = cls._huella(origen)
                if huella_origen == cls._huella(candidato):
                    return candidato
        except OSError:
            return None
        return None

    @staticmethod
    def _huella(archivo):
        digest = hashlib.sha256()
        with Path(archivo).open("rb") as contenido:
            for bloque in iter(lambda: contenido.read(1024 * 1024), b""):
                digest.update(bloque)
        return digest.digest()

    @staticmethod
    def _normalizar_nombre(nombre, extension):

        nombre = nombre.replace("\\", "/").split("/")[-1]
        nombre = re.sub(r'[<>:"/\\|?*]', "-", nombre).strip(". ")
        if not nombre:
            nombre = f"documento{extension}"
        if Path(nombre).suffix.lower() != extension.lower():
            nombre += extension
        return nombre

    @staticmethod
    def _ruta_disponible(destino, nombre):

        candidata = destino / nombre
        contador = 1
        while candidata.exists():
            candidata = destino / f"{Path(nombre).stem} ({contador}){Path(nombre).suffix}"
            contador += 1
        return candidata
