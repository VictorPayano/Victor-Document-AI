from pathlib import Path


class AnalyzerFilename:

    def analizar(self, archivo: Path):

        nombre = archivo.stem.lower()

        resultado = {
            "categoria": "Sin clasificar",
            "empresa": "-",
            "persona": "-",
            "destino": "-",
            "confianza": 20,
        }

        if "ing" in nombre:
            resultado["categoria"] = "Banco"
            resultado["empresa"] = "ING"
            resultado["destino"] = "Victor/Banco/ING"
            resultado["confianza"] = 98

        elif "abn" in nombre:
            resultado["categoria"] = "Banco"
            resultado["empresa"] = "ABN AMRO"
            resultado["destino"] = "Victor/Banco/ABN AMRO"
            resultado["confianza"] = 98

        elif "rabobank" in nombre:
            resultado["categoria"] = "Banco"
            resultado["empresa"] = "Rabobank"
            resultado["destino"] = "Victor/Banco/Rabobank"
            resultado["confianza"] = 98

        return resultado