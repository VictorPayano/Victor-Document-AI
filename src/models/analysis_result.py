from dataclasses import dataclass

@dataclass
class AnalysisResult:

    categoria: str
    empresa: str
    persona: str
    destino: str
    confianza: int