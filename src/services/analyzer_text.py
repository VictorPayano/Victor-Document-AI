import re
import unicodedata
from datetime import date

from services.learning import LearningStore
from services.person_aliases import PersonAliasStore
from services.instance_choices import InstanceChoiceStore


class AnalyzerText:

    def __init__(self):
        self.aprendizaje = LearningStore()
        self.aliases_persona = PersonAliasStore()
        self.elecciones_instancia = InstanceChoiceStore()

    MESES = {
        "januari": 1, "january": 1, "enero": 1, "jan": 1, "ene": 1,
        "februari": 2, "february": 2, "febrero": 2, "feb": 2,
        "maart": 3, "march": 3, "marzo": 3, "mrt": 3, "mar": 3,
        "april": 4, "abril": 4, "apr": 4, "abr": 4,
        "mei": 5, "may": 5, "mayo": 5,
        "juni": 6, "june": 6, "junio": 6, "jun": 6,
        "juli": 7, "july": 7, "julio": 7, "jul": 7,
        "augustus": 8, "august": 8, "agosto": 8, "aug": 8, "ago": 8,
        "september": 9, "septiembre": 9, "sep": 9,
        "oktober": 10, "october": 10, "octubre": 10, "okt": 10, "oct": 10,
        "november": 11, "noviembre": 11, "nov": 11,
        "december": 12, "diciembre": 12, "dec": 12, "dic": 12,
    }

    PALABRAS_ENTIDAD = (
        "bank", "banco", "gemeente", "municipio", "verzekering", "seguro",
        "verzekeraar", "corporatie", "woning", "belasting", "tax", "ministerie",
        "ministerio", "dienst", "servicio", "stichting", "fundacion", "vereniging",
        "asociacion", "universiteit", "hospital", "ziekenhuis", "b.v.", "n.v.",
        "bv", "nv", "ltd", "llc", "inc",
    )

    def analizar(self, texto: str):

        persona_detectada = self._extraer_destinatario(texto)
        persona = self.aliases_persona.obtener(persona_detectada) or persona_detectada
        entidad = self._extraer_remitente(texto)
        fecha = self._extraer_fecha(self._normalizar(texto))

        campos_detectados = sum(valor is not None for valor in (persona, entidad, fecha))
        resultado = {
            "categoria": "Correspondencia" if campos_detectados else "Sin clasificar",
            "empresa": entidad or "Entidad no identificada",
            "persona": persona or "Destinatario no identificado",
            "fecha": fecha or "Sin fecha",
            "destino": "-",
            "confianza": 20 + campos_detectados * 25,
            "persona_detectada": persona_detectada or "",
        }
        resultado.update(self.elecciones_instancia.obtener(persona, entidad))

        destino_aprendido = (
            self.aprendizaje.obtener_destino(persona_detectada, entidad)
            or self.aprendizaje.obtener_destino(persona, entidad)
        )

        if destino_aprendido:
            resultado["destino"] = destino_aprendido
            resultado["confianza"] = max(resultado["confianza"], 85)
        elif persona and entidad and fecha:
            resultado["destino"] = "/".join((
                self._segmento_ruta(persona),
                self._segmento_ruta(entidad),
                fecha,
            ))
            resultado["confianza"] = 95

        return resultado

    def extraer_fecha(self, texto: str):

        return self._extraer_fecha(self._normalizar(texto))

    def extraer_destinatario(self, texto: str):

        return self._extraer_destinatario(texto)

    def aprender_destino(
        self,
        resultado,
        destino,
        persona_elegida=None,
        instancias_elegidas=None,
    ):

        persona_detectada = resultado.get("persona_detectada") or resultado.get("persona")
        persona_elegida = (persona_elegida or "").strip()
        if persona_elegida:
            self.aliases_persona.guardar(persona_detectada, persona_elegida)

        instancias_elegidas = instancias_elegidas or {}
        self.elecciones_instancia.guardar(
            persona_elegida or resultado.get("persona"),
            resultado.get("empresa"),
            instancias_elegidas.get("instancia_1"),
            instancias_elegidas.get("instancia_2"),
            instancias_elegidas.get("instancia_3"),
        )

        self.aprendizaje.guardar_destino(
            persona_detectada,
            resultado.get("empresa"),
            destino,
        )
        if persona_elegida:
            self.aprendizaje.guardar_destino(
                persona_elegida,
                resultado.get("empresa"),
                destino,
            )

    def _extraer_destinatario(self, texto: str):

        patrones = (
            r"(?im)^\s*(?:aan|t\.?\s*a\.?\s*v\.?|to|dear|geachte|beste|estimad[oa])\s*[: ,]*([^\n]{3,80})",
            r"(?im)^\s*(?:dhr\.?|mevr\.?|mr\.?|mrs\.?|sr\.?|sra\.?)\s+([^\n]{3,80})",
        )

        for patron in patrones:
            for coincidencia in re.finditer(patron, texto):
                candidata = self._limpiar_nombre(coincidencia.group(1))
                if self._es_posible_nombre(candidata):
                    return candidata

        lineas = [" ".join(linea.split()) for linea in texto.splitlines()]
        for indice, linea in enumerate(lineas[:50]):
            candidata = self._limpiar_nombre(linea)
            if not self._es_posible_nombre(candidata):
                continue

            contexto = " ".join(lineas[max(0, indice - 1):indice + 3])
            if re.search(r"\b\d{4}\s?[A-Za-z]{2}\b|\b\d{5}\b", contexto):
                return candidata

        return None

    def _extraer_remitente(self, texto: str):

        lineas = [" ".join(linea.split()) for linea in texto.splitlines()]

        for indice, linea in enumerate(lineas[:30]):
            if re.match(r"(?i)^\s*(?:afzender|sender|remitente|van|from)\s*:", linea):
                candidata = re.split(r":", linea, maxsplit=1)[-1].strip()
                if candidata:
                    return candidata
                if indice + 1 < len(lineas) and lineas[indice + 1]:
                    return lineas[indice + 1]

        for linea in lineas[:30]:
            candidata = " ".join(linea.split())
            normalizada = self._normalizar(candidata)
            if 3 <= len(candidata) <= 100 and any(
                palabra in normalizada for palabra in self.PALABRAS_ENTIDAD
            ):
                return candidata

        dominio = self._extraer_dominio(texto)
        if dominio:
            return dominio

        return None

    def _extraer_dominio(self, texto: str):

        coincidencia = re.search(
            r"(?i)(?:https?://|www\.|@)([a-z0-9][a-z0-9.-]+\.[a-z]{2,})",
            texto,
        )
        if not coincidencia:
            # Muchas cartas imprimen el dominio como "amsterdam.nl/ruta",
            # sin "www" ni "https". También es una pista válida del remitente.
            coincidencia = re.search(
                r"(?i)\b([a-z0-9][a-z0-9.-]+\.(?:nl|com|org|net|eu|gov))\b",
                texto,
            )
        if not coincidencia:
            return None

        partes = coincidencia.group(1).lower().split(".")
        if len(partes) < 2:
            return None

        nombre = partes[-2]
        if nombre in {"co", "com", "org", "gov"} and len(partes) >= 3:
            nombre = partes[-3]

        return " ".join(fragment.capitalize() for fragment in nombre.split("-"))

    def _extraer_fecha(self, texto: str):

        etiquetas_expedicion = (
            r"\bdatum van afgifte\b",
            r"\bafgiftedatum\b",
            r"\bdate of issue\b",
            r"\bissue date\b",
            r"\bfecha de expedicion\b",
            r"\bfecha de emision\b",
            r"\bdatum\b",
        )

        for etiqueta in etiquetas_expedicion:
            coincidencia = re.search(rf"{etiqueta}.{{0,50}}", texto, re.DOTALL)
            if coincidencia:
                fecha = self._buscar_fecha(coincidencia.group())
                if fecha:
                    return fecha

        return self._buscar_fecha(texto)

    def _buscar_fecha(self, texto: str):

        for patron, orden in (
            (r"\b(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})\b", "amd"),
            (r"\b(\d{1,2})[-/.](\d{1,2})[-/.](\d{4})\b", "dma"),
        ):
            coincidencia = re.search(patron, texto)
            if coincidencia:
                valores = tuple(map(int, coincidencia.groups()))
                ano, mes, dia = valores if orden == "amd" else (valores[2], valores[1], valores[0])
                fecha = self._fecha_valida(ano, mes, dia)
                if fecha:
                    return fecha

        meses = "|".join(map(re.escape, self.MESES))
        coincidencia = re.search(
            rf"\b(\d{{1,2}})\s+(?:de\s+)?({meses})\s+(?:de\s+)?(\d{{4}})\b",
            texto,
        )
        if coincidencia:
            dia, mes, ano = coincidencia.groups()
            return self._fecha_valida(int(ano), self.MESES[mes], int(dia))

        return None

    @staticmethod
    def _limpiar_nombre(valor: str):

        valor = re.sub(r"^(?:dhr\.?|mevr\.?|mr\.?|mrs\.?|sr\.?|sra\.?|heer|mevrouw)\s+", "", valor, flags=re.I)
        return re.sub(r"\s+", " ", valor).strip(" ,:;.-")

    def _es_posible_nombre(self, valor: str):

        if not 4 <= len(valor) <= 80 or any(caracter.isdigit() for caracter in valor):
            return False

        normalizada = self._normalizar(valor)
        if any(palabra in normalizada for palabra in self.PALABRAS_ENTIDAD):
            return False

        palabras = re.findall(r"[A-Za-zÀ-ÿ'’-]+", valor)
        if not 2 <= len(palabras) <= 6:
            return False

        conectores = {"de", "del", "de la", "van", "der", "den", "ten", "von"}
        return all(
            palabra.lower() in conectores or palabra[0].isupper() or palabra.isupper()
            for palabra in palabras
        )

    @staticmethod
    def _fecha_valida(ano: int, mes: int, dia: int):

        try:
            return date(ano, mes, dia).isoformat()
        except ValueError:
            return None

    @staticmethod
    def _normalizar(texto: str):

        texto = unicodedata.normalize("NFD", texto.lower())
        return "".join(caracter for caracter in texto if not unicodedata.combining(caracter))

    @staticmethod
    def _segmento_ruta(valor: str):

        return re.sub(r'[<>:"/\\|?*]', "-", valor).strip(". ")
