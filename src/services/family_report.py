"""Informe PDF completo de una ficha familiar."""

import mimetypes
import tempfile
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from app.personas_window import BASIC_FIELDS, BASIC_LABELS, FIELD_LABELS
from services.family_database import FamilyDatabase
from services.translation_pdf import _registrar_fuentes


class FamilyReport:
    BLANK = "____________________________"

    def __init__(self, database=None):
        self.database = database or FamilyDatabase()

    def create(self, person_id, path):
        person = self.database.get_person(person_id)
        if not person:
            raise ValueError("No se encontró la persona seleccionada.")
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        font, font_bold = _registrar_fuentes()
        styles = self._styles(font, font_bold)
        name = " ".join(value for value in (person.get("given_names"), person.get("surname")) if value).strip()
        name = name or person["folder_name"]
        document = SimpleDocTemplate(
            str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm, title=f"Informe familiar - {name}",
        )
        story = [
            Paragraph("Informe completo de datos", styles["title"]),
            Paragraph(f"Persona: <b>{escape(name)}</b><br/>Generado: {datetime.now():%d-%m-%Y %H:%M}", styles["meta"]),
            Paragraph("Los espacios en blanco indican información aún no registrada.", styles["notice"]),
        ]
        story.extend(self._section("Datos básicos", self._basic_rows(person), styles))
        for table, (title, fields) in FamilyDatabase.RELATED.items():
            if not self.database.tab_visible(person_id, table):
                continue
            story.append(Spacer(1, 8))
            rows = self.database.related(table, person_id)
            story.extend(self._related_section(title, fields, rows, styles))
        for tab in self.database.custom_tabs():
            if not self.database.tab_visible(person_id, f"custom:{tab['id']}"):
                continue
            story.append(Spacer(1, 8))
            rows = self.database.custom_entries(person_id, tab["id"])
            fields = self.database.custom_tab_fields(tab["id"])
            keys = tuple(field["field_key"] for field in fields)
            labels = {field["field_key"]: field["name"] for field in fields}
            story.extend(self._related_section(tab["name"], keys, rows, styles, labels))
        document.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        return path

    def temporary(self, person_id):
        folder = Path(tempfile.gettempdir()) / "Victor Document AI" / "informes"
        folder.mkdir(parents=True, exist_ok=True)
        person = self.database.get_person(person_id) or {}
        safe_name = "_".join((person.get("given_names") or person.get("folder_name") or "persona").split())
        return self.create(person_id, folder / f"informe_{safe_name}_{datetime.now():%Y%m%d_%H%M%S}.pdf")

    def create_query(self, question, result, path):
        """Guarda una consulta general sin exigir que se refiera a una persona."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        font, font_bold = _registrar_fuentes()
        styles = self._styles(font, font_bold)
        document = SimpleDocTemplate(
            str(path), pagesize=A4, leftMargin=16 * mm, rightMargin=16 * mm,
            topMargin=18 * mm, bottomMargin=18 * mm, title="Consulta de datos familiares",
        )
        story = [
            Paragraph("Resultado de consulta familiar", styles["title"]),
            Paragraph(f"Consulta: {escape(question)}<br/>Generado: {datetime.now():%d-%m-%Y %H:%M}", styles["meta"]),
        ]
        for line in result.splitlines():
            story.append(Paragraph(escape(line) if line.strip() else "&nbsp;", styles["value"]))
            story.append(Spacer(1, 2))
        document.build(story, onFirstPage=self._footer, onLaterPages=self._footer)
        return path

    def temporary_query(self, question, result):
        folder = Path(tempfile.gettempdir()) / "Victor Document AI" / "informes"
        folder.mkdir(parents=True, exist_ok=True)
        return self.create_query(question, result, folder / f"consulta_general_{datetime.now():%Y%m%d_%H%M%S}.pdf")

    @staticmethod
    def create_email_draft(pdf_path, recipient=""):
        pdf_path = Path(pdf_path)
        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = f"Información personal - {pdf_path.stem}"
        message.set_content("Adjunto encontrarás el informe solicitado con la información registrada.")
        mime_type, _ = mimetypes.guess_type(pdf_path.name)
        main, sub = (mime_type or "application/pdf").split("/", 1)
        message.add_attachment(pdf_path.read_bytes(), maintype=main, subtype=sub, filename=pdf_path.name)
        draft = Path(tempfile.gettempdir()) / "Victor Document AI" / "email"
        draft.mkdir(parents=True, exist_ok=True)
        output = draft / f"{pdf_path.stem}.eml"
        output.write_bytes(bytes(message))
        return output

    def _basic_rows(self, person):
        return [(BASIC_LABELS[field], person.get(field) or self.BLANK) for field in BASIC_FIELDS]

    def _related_section(self, title, fields, records, styles, labels=None):
        if not records:
            return self._section(title, [("Información", self.BLANK)], styles)
        content = [Paragraph(escape(title), styles["heading"])]
        for number, record in enumerate(records, start=1):
            if len(records) > 1:
                content.append(Paragraph(f"Registro {number}", styles["record"]))
            label_map = labels or {"concept": "Concepto", "detail": "Detalle", "note": "Nota"}
            rows = [(label_map.get(field, FIELD_LABELS.get(field, field)), record.get(field) or self.BLANK) for field in fields]
            content.append(self._table(rows, styles))
            content.append(Spacer(1, 5))
        return content

    def _section(self, title, rows, styles):
        return [Paragraph(escape(title), styles["heading"]), self._table(rows, styles)]

    @staticmethod
    def _table(rows, styles):
        values = [[Paragraph(escape(str(label)), styles["label"]), Paragraph(escape(str(value)), styles["value"])] for label, value in rows]
        table = Table(values, colWidths=(52 * mm, 118 * mm), repeatRows=0)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#EAF2F8")),
            ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B8C5D1")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ("RIGHTPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    @staticmethod
    def _styles(font, font_bold):
        base = getSampleStyleSheet()
        return {
            "title": ParagraphStyle("FamilyReportTitle", parent=base["Heading1"], fontName=font_bold, fontSize=18, leading=22, textColor=colors.HexColor("#17202A"), spaceAfter=7),
            "meta": ParagraphStyle("FamilyReportMeta", parent=base["Normal"], fontName=font, fontSize=9.5, leading=13, textColor=colors.HexColor("#4B5563"), spaceAfter=7),
            "notice": ParagraphStyle("FamilyReportNotice", parent=base["Normal"], fontName=font, fontSize=9, leading=12, textColor=colors.HexColor("#7B341E"), spaceAfter=9),
            "heading": ParagraphStyle("FamilyReportHeading", parent=base["Heading2"], fontName=font_bold, fontSize=12, leading=16, textColor=colors.HexColor("#1F4E79"), spaceBefore=6, spaceAfter=4),
            "record": ParagraphStyle("FamilyReportRecord", parent=base["Normal"], fontName=font_bold, fontSize=9, leading=12, spaceBefore=2, spaceAfter=3),
            "label": ParagraphStyle("FamilyReportLabel", parent=base["Normal"], fontName=font_bold, fontSize=8.7, leading=11),
            "value": ParagraphStyle("FamilyReportValue", parent=base["Normal"], fontName=font, fontSize=8.7, leading=11),
        }

    @staticmethod
    def _footer(canvas, document):
        canvas.saveState()
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#667085"))
        canvas.drawString(16 * mm, 10 * mm, "Victor Document AI - Información confidencial")
        canvas.drawRightString(A4[0] - 16 * mm, 10 * mm, f"Página {document.page}")
        canvas.restoreState()
