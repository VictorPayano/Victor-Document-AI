import re


class AnalyzerText:

    def analizar(self, texto: str):

        texto = texto.lower()

        resultado = {
            "categoria": "Sin clasificar",
            "empresa": "-",
            "persona": "-",
            "destino": "-",
            "confianza": 20,
        }

        # =====================================
        # BANCOS
        # =====================================

        if re.search(r"\bing\b", texto):

            resultado["categoria"] = "Banco"
            resultado["empresa"] = "ING"
            resultado["destino"] = "Victor/Banco/ING"
            resultado["confianza"] = 98

        elif re.search(r"\babn\s+amro\b", texto):

            resultado["categoria"] = "Banco"
            resultado["empresa"] = "ABN AMRO"
            resultado["destino"] = "Victor/Banco/ABN AMRO"
            resultado["confianza"] = 98

        elif re.search(r"\brabobank\b", texto):

            resultado["categoria"] = "Banco"
            resultado["empresa"] = "Rabobank"
            resultado["destino"] = "Victor/Banco/Rabobank"
            resultado["confianza"] = 98

        # =====================================
        # NÓMINAS
        # =====================================

        elif "loon" in texto or "salaris" in texto:

            resultado["categoria"] = "Nómina"
            resultado["empresa"] = "Qualitair Aviation Holland B.V."
            resultado["destino"] = "Victor/Trabajo/Nóminas"
            resultado["confianza"] = 95

        return resultado