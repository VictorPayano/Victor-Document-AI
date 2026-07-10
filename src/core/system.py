from pathlib import Path


class Sistema:

    VERSION = "0.1"

    # Ruta de tu biblioteca
    BIBLIOTECA = Path(
        r"\\VictorNas\DriveData\Dropbox\00 PERSONALES 14-04-2015\00 - My PaperPort Documents 27-03-2012 (Gastd)"
    )

    @staticmethod
    def mostrar_banner():

        print("=" * 60)
        print("          Victor Document AI")
        print(f"               Version {Sistema.VERSION}")
        print("=" * 60)

    @staticmethod
    def comprobar_biblioteca():

        if Sistema.BIBLIOTECA.exists():
            print("✅ Biblioteca encontrada")
            return True

        print("❌ Biblioteca NO encontrada")
        return False