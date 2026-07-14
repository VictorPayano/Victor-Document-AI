from xml.sax.saxutils import escape
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer


def guardar_traduccion_pdf(ruta, nombre_documento, idioma, traduccion):

    fuente, fuente_negrita = _registrar_fuentes()

    documento = SimpleDocTemplate(
        str(ruta),
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Traducción - {nombre_documento}",
    )

    estilos = getSampleStyleSheet()
    titulo = ParagraphStyle(
        "TituloTraduccion",
        parent=estilos["Heading1"],
        fontName=fuente_negrita,
        fontSize=16,
        leading=20,
        textColor=colors.HexColor("#1F2937"),
        spaceAfter=10,
    )
    metadatos = ParagraphStyle(
        "MetadatosTraduccion",
        parent=estilos["Normal"],
        fontName=fuente,
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4B5563"),
        spaceAfter=14,
    )
    cuerpo = ParagraphStyle(
        "CuerpoTraduccion",
        parent=estilos["BodyText"],
        fontName=fuente,
        fontSize=10.5,
        leading=15,
        textColor=colors.HexColor("#111827"),
        spaceAfter=9,
    )

    contenido = [
        Paragraph(f"Traducción al {escape(idioma)}", titulo),
        Paragraph(f"Documento original: {escape(nombre_documento)}", metadatos),
    ]

    for parrafo in traduccion.splitlines():
        if parrafo.strip():
            contenido.append(Paragraph(escape(parrafo), cuerpo))
        else:
            contenido.append(Spacer(1, 5))

    documento.build(contenido)


def _registrar_fuentes():

    fuentes = Path(r"C:\Windows\Fonts")
    regular = fuentes / "arial.ttf"
    negrita = fuentes / "arialbd.ttf"

    if regular.exists() and negrita.exists():
        if "VictorArial" not in pdfmetrics.getRegisteredFontNames():
            pdfmetrics.registerFont(TTFont("VictorArial", str(regular)))
            pdfmetrics.registerFont(TTFont("VictorArialBold", str(negrita)))
        return "VictorArial", "VictorArialBold"

    return "Helvetica", "Helvetica-Bold"
