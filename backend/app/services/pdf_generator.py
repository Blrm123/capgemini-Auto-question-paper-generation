"""
services/pdf_generator.py

PDF Generator Service for the Agentic Question Paper Generator.

Generates two professional A4 PDFs using ReportLab Platypus (flowable-based):
  1. Question Paper PDF — questions grouped by section (2M / 5M / 10M / 15M)
  2. Answer Key PDF    — model answers, key points, and marks breakdown

Stored in: generated_papers/
"""

import datetime
from pathlib import Path
from typing import Any, Optional
from PIL import Image as PILImage

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    HRFlowable,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
    Image as RLImage,
    KeepTogether,
)

from app.config import settings
from app.models.state import AnswerKeyItem, PaperMetadata, ValidatedQuestion
from app.services.logger import setup_logger

logger = setup_logger(__name__)


class NumberedCanvas(Canvas):
    """Deferred canvas that can render a consistent Page X of Y footer."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._saved_page_states: list[dict] = []

    def showPage(self) -> None:
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self) -> None:
        page_count = len(self._saved_page_states)
        for page_number, state in enumerate(self._saved_page_states, start=1):
            self.__dict__.update(state)
            self._draw_footer(page_number, page_count)
            Canvas.showPage(self)
        Canvas.save(self)

    def _draw_footer(self, page_number: int, page_count: int) -> None:
        page_width = self._pagesize[0]
        self.saveState()
        self.setStrokeColor(colors.HexColor("#777777"))
        self.setLineWidth(0.35)
        self.line(settings.pdf.MARGIN_LEFT, 33, page_width - settings.pdf.MARGIN_RIGHT, 33)
        self.setFont("Times-Roman", 10)
        self.setFillColor(colors.black)
        self.drawCentredString(page_width / 2, 19, f"Page {page_number} of {page_count}")
        footer_text = str(getattr(settings.pdf, "FOOTER_TEXT", "") or "").strip()
        if footer_text:
            self.setFont("Times-Roman", 8)
            self.drawRightString(page_width - settings.pdf.MARGIN_RIGHT, 19, footer_text)
        self.restoreState()

# ---------------------------------------------------------------------------
# Style definitions
# ---------------------------------------------------------------------------

def _build_styles() -> dict:
    """Build and return the paragraph style dictionary."""
    base = getSampleStyleSheet()

    styles = {
        "institution": ParagraphStyle(
            "institution",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=19,
            alignment=TA_CENTER,
            leading=22,
            spaceAfter=3,
        ),
        "subtitle": ParagraphStyle(
            "subtitle",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=9.5,
            leading=12,
            alignment=TA_CENTER,
            spaceAfter=2,
        ),
        "course_name": ParagraphStyle(
            "course_name",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=16,
            alignment=TA_CENTER,
            leading=19,
            spaceAfter=3,
        ),
        "header_info": ParagraphStyle(
            "header_info",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            leading=13,
            alignment=TA_CENTER,
            spaceAfter=0,
        ),
        "section_title": ParagraphStyle(
            "section_title",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=14,
            alignment=TA_LEFT,
            spaceBefore=20,
            spaceAfter=9,
            textColor=colors.black,
        ),
        "module_title": ParagraphStyle(
            "module_title",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=11,
            leading=14,
            alignment=TA_CENTER,
            spaceBefore=10,
            spaceAfter=6,
        ),
        "question": ParagraphStyle(
            "question",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=12,
            alignment=TA_LEFT,
            spaceAfter=0,
            leading=15,
        ),
        "answer_heading": ParagraphStyle(
            "answer_heading",
            parent=base["Normal"],
            fontName="Times-Bold",
            fontSize=11,
            alignment=TA_LEFT,
            spaceBefore=9,
            spaceAfter=4,
        ),
        "instruction": ParagraphStyle(
            "instruction",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=11,
            leading=14,
            alignment=TA_LEFT,
            leftIndent=22,
            firstLineIndent=-14,
            spaceAfter=2,
        ),
        "answer_body": ParagraphStyle(
            "answer_body",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            alignment=TA_LEFT,
            spaceAfter=4,
            leading=14,
        ),
        "key_point": ParagraphStyle(
            "key_point",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=11,
            alignment=TA_LEFT,
            leftIndent=14,
            spaceAfter=2,
            leading=13,
        ),
        "marks_breakdown": ParagraphStyle(
            "marks_breakdown",
            parent=base["Normal"],
            fontName="Times-Italic",
            fontSize=9,
            alignment=TA_LEFT,
            leftIndent=14,
            spaceAfter=6,
            textColor=colors.HexColor("#555555"),
        ),
        "footer": ParagraphStyle(
            "footer",
            parent=base["Normal"],
            fontName="Times-Roman",
            fontSize=10,
            alignment=TA_CENTER,
            textColor=colors.HexColor("#888888"),
        ),
    }
    return styles


# ---------------------------------------------------------------------------
# PDFGenerator class
# ---------------------------------------------------------------------------

class PDFGenerator:
    """
    Generates question paper and answer key PDFs.

    Usage:
        generator = PDFGenerator()
        paper_path = generator.generate_question_paper(questions, metadata)
        key_path   = generator.generate_answer_key(answer_key, metadata)
    """

    def __init__(self) -> None:
        settings.paths.ensure_directories()
        self.output_dir: Path = settings.paths.GENERATED_PAPERS_DIR
        self.styles = _build_styles()
        self.content_width = (
            settings.pdf.PAGE_WIDTH - settings.pdf.MARGIN_LEFT - settings.pdf.MARGIN_RIGHT
        )
        logger.info("PDFGenerator initialized.")

    @staticmethod
    def _draw_page_footer(canvas, doc) -> None:
        """Draw a stable footer outside the story on every page."""
        canvas.saveState()
        page_width = doc.pagesize[0]
        canvas.setStrokeColor(colors.HexColor("#A8A8A8"))
        canvas.setLineWidth(0.35)
        canvas.line(doc.leftMargin, 33, page_width - doc.rightMargin, 33)
        canvas.setFont("Helvetica", 8)
        canvas.setFillColor(colors.HexColor("#666666"))
        canvas.drawCentredString(page_width / 2, 20, f"Page {doc.page}")
        canvas.restoreState()

    def _new_document(self, filepath: Path) -> SimpleDocTemplate:
        """Create a document with identical printable geometry on every page."""
        return SimpleDocTemplate(
            str(filepath),
            pagesize=A4,
            leftMargin=settings.pdf.MARGIN_LEFT,
            rightMargin=settings.pdf.MARGIN_RIGHT,
            topMargin=settings.pdf.MARGIN_TOP,
            bottomMargin=settings.pdf.MARGIN_BOTTOM,
        )

    def _resolve_image_path(self, image_path: Optional[str]) -> Optional[Path]:
        """Robustly resolve image path string to an existing absolute Path object."""
        if not image_path:
            return None
        p = Path(image_path)
        if p.is_absolute() and p.is_file():
            return self._prepare_image_for_pdf(p)
        
        # 1. Try relative to BASE_DIR
        base_rel = settings.paths.BASE_DIR / p
        if base_rel.is_file():
            return self._prepare_image_for_pdf(base_rel)
            
        # 2. Try inside uploaded_documents/extracted_images
        extracted_dir = settings.paths.BASE_DIR / "uploaded_documents" / "extracted_images" / p.name
        if extracted_dir.is_file():
            return self._prepare_image_for_pdf(extracted_dir)
            
        return None

    def _prepare_image_for_pdf(self, img_path: Path) -> Optional[Path]:
        """Ensure image is in RGB format with a white background and valid dimensions."""
        try:
            with PILImage.open(img_path) as pil_img:
                w, h = pil_img.size
                # If image is full-page background mask or tiny stencil icon, skip rendering
                if w > 2000 or h > 2800 or w < 30 or h < 30:
                    logger.warning(f"Skipping page background mask / invalid image dimensions ({w}x{h}): {img_path}")
                    return None
                    
                extrema = pil_img.getextrema()
                if pil_img.mode == "L" and (extrema == (0, 0) or extrema == (255, 255)):
                    logger.warning(f"Skipping single-color stencil mask: {img_path}")
                    return None

                if pil_img.mode in ("RGBA", "LA") or (pil_img.mode == "P" and "transparency" in pil_img.info):
                    rgba = pil_img.convert("RGBA")
                    background = PILImage.new("RGB", rgba.size, (255, 255, 255))
                    background.paste(rgba, mask=rgba.split()[3])
                    clean_path = self.output_dir / f"clean_{img_path.name}"
                    background.save(clean_path, "PNG")
                    return clean_path
                elif pil_img.mode != "RGB":
                    clean_path = self.output_dir / f"clean_{img_path.name}"
                    pil_img.convert("RGB").save(clean_path, "PNG")
                    return clean_path
                else:
                    return img_path
        except Exception as e:
            logger.error(f"Error preparing image {img_path}: {e}")
            return None

    def _format_text(self, text: str) -> str:
        """Format math text, LaTeX symbols, matrices, and newlines to ReportLab HTML tags."""
        import re
        if not text:
            return ""

        # 0. Unescape literal escaped newlines (\n as 2 chars)
        text = text.replace(r'\n', '\n')

        # Pre-process LaTeX matrix blocks before replacing backslashes
        def _replace_matrix(m):
            matrix_content = m.group(1).strip()
            matrix_rows = matrix_content.split(r'\\')
            formatted_matrix_rows = []
            for r in matrix_rows:
                r_clean = r.strip()
                if not r_clean:
                    continue
                elems = [e.strip() for e in r_clean.split('&')]
                formatted_matrix_rows.append("[ &nbsp;" + "&nbsp;&nbsp;&nbsp;".join(elems) + "&nbsp; ]")
            return "<br/>&nbsp;&nbsp;&nbsp;&nbsp;" + "<br/>&nbsp;&nbsp;&nbsp;&nbsp;".join(formatted_matrix_rows) + "<br/>"

        text = re.sub(r'\\begin\{(?:bmatrix|pmatrix|matrix)\}(.*?)\\end\{(?:bmatrix|pmatrix|matrix)\}', _replace_matrix, text, flags=re.DOTALL)
        
        # Pre-process Unicode superscript and subscript characters
        # (fonts like Helvetica don't support them, causing black box artifacts)
        sup_map = {
            '⁰': '0', '¹': '1', '²': '2', '³': '3', '⁴': '4',
            '⁵': '5', '⁶': '6', '⁷': '7', '⁸': '8', '⁹': '9',
            '⁺': '+', '⁻': '-', '⁼': '=', '⁽': '(', '⁾': ')',
            'ⁿ': 'n'
        }
        sub_map = {
            '₀': '0', '₁': '1', '₂': '2', '₃': '3', '₄': '4',
            '₅': '5', '₆': '6', '₇': '7', '₈': '8', '₉': '9',
            '₊': '+', '₋': '-', '₌': '=', '₍': '(', '₎': ')'
        }
        
        rebuilt = []
        i = 0
        while i < len(text):
            if text[i] in sup_map:
                sup_chars = []
                while i < len(text) and text[i] in sup_map:
                    sup_chars.append(sup_map[text[i]])
                    i += 1
                rebuilt.append(f"<sup>{''.join(sup_chars)}</sup>")
            elif text[i] in sub_map:
                sub_chars = []
                while i < len(text) and text[i] in sub_map:
                    sub_chars.append(sub_map[text[i]])
                    i += 1
                rebuilt.append(f"<sub>{''.join(sub_chars)}</sub>")
            else:
                rebuilt.append(text[i])
                i += 1
        text = "".join(rebuilt)
        
        # 1. Handle exponents with curly brackets: base^{exponent} -> base<sup>exponent</sup>
        text = re.sub(
            r'([a-zA-Z0-9\-\+\(\)\*\/\\a-zA-Z]+)\^\{([^}]+)\}',
            r'\1<sup>\2</sup>',
            text
        )

        # 2. Handle simple exponents without curly brackets: base^exponent
        text = re.sub(
            r'([a-zA-Z0-9\-\+\(\)]+)\^([a-zA-Z0-9\-\+\(\)]+)',
            r'\1<sup>\2</sup>',
            text
        )

        # 3. Replace LaTeX fractions \frac{A}{B} -> <sup>A</sup>/<sub>B</sub>
        while True:
            new_text = re.sub(
                r'\\frac\s*\{([^}]+)\}\s*\{([^}]+)\}',
                r'<sup>\1</sup>/<sub>\2</sub>',
                text
            )
            if new_text == text:
                break
            text = new_text

        # 4. Square roots \sqrt{A} -> √A
        text = re.sub(r'\\sqrt\s*\{([^}]+)\}', r'√\1', text)

        # 5. Replace standard LaTeX symbols with Unicode equivalents
        latex_replacements = {
            r'\times': '×',
            r'\cdot': '·',
            r'\div': '÷',
            r'\pm': '±',
            r'\approx': '≈',
            r'\geq': '≥',
            r'\ge': '≥',
            r'\leq': '≤',
            r'\le': '≤',
            r'\neq': '≠',
            r'\infty': '∞',
            r'\pi': 'π',
            r'\theta': 'θ',
            r'\alpha': 'α',
            r'\beta': 'β',
            r'\gamma': 'γ',
            r'\delta': 'δ',
            r'\lambda': 'λ',
            r'\sigma': 'σ',
            r'\phi': 'φ',
            r'\omega': 'ω',
            r'\Delta': 'Δ',
            r'\Sigma': 'Σ',
            r'\mu': 'μ',
            r'\deg': '°',
            r'\in': '∈',
            r'\notin': '∉',
            r'\mathbb{N}': 'ℕ',
            r'\mathbb{R}': 'ℝ',
            r'\mathbb{Z}': 'ℤ',
            r'\mathbb{C}': 'ℂ',
            r'\cos': 'cos',
            r'\sin': 'sin',
            r'\tan': 'tan',
            r'\log': 'log',
            r'\ln': 'ln',
            r'\rightarrow': '→',
            r'\Rightarrow': '⇒',
        }
        
        for lat in sorted(latex_replacements.keys(), key=len, reverse=True):
            text = text.replace(lat, latex_replacements[lat])
            
        # 6. Strip $ characters used for math wrapping
        text = text.replace('$', '')
        
        # 7. Parse Markdown bold and italic
        text = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        text = re.sub(r'\*([^\*]+)\*', r'<i>\1</i>', text)
        
        # 8. Format Markdown bullet points nicely
        text = re.sub(r'(?m)^[-*]\s+', '&bull; ', text)
        
        # 9. Preserve explicit line breaks for multi-line text (e.g. matrix rows, lists)
        text = text.replace('\r\n', '\n').replace('\n', '<br/>')
        
        return text

    def _parse_markdown_tables_and_text(self, text: str, base_style: ParagraphStyle, prefix: str = "") -> list:
        """
        Parse text that may contain markdown tables or multi-line text into ReportLab Flowables.
        """
        import re
        if not text:
            return []
            
        flowables = []
        lines = text.strip().split('\n')
        
        i = 0
        paragraph_lines = []
        first_p = True
        
        def flush_paragraph():
            nonlocal paragraph_lines, first_p
            if paragraph_lines:
                p_text = "\n".join(paragraph_lines)
                formatted_p = self._format_text(p_text)
                if first_p and prefix:
                    formatted_p = f"{prefix}{formatted_p}"
                    first_p = False
                flowables.append(Paragraph(formatted_p, base_style))
                paragraph_lines = []
                
        while i < len(lines):
            line = lines[i]
            # Detect Markdown Table (contains | and adjacent divider row with -)
            if '|' in line and (i + 1 < len(lines) and '|' in lines[i+1] and '-' in lines[i+1]):
                flush_paragraph()
                
                table_rows = []
                while i < len(lines) and '|' in lines[i]:
                    # Skip divider rows like |---|---|
                    if re.match(r'^\s*\|?\s*:?-+:?\s*(\|?\s*:?-+:?\s*)+\|?\s*$', lines[i]):
                        i += 1
                        continue
                        
                    raw_cells = lines[i].split('|')
                    if raw_cells and not raw_cells[0].strip():
                        raw_cells = raw_cells[1:]
                    if raw_cells and not raw_cells[-1].strip():
                        raw_cells = raw_cells[:-1]
                        
                    cells = [self._format_text(c.strip()) for c in raw_cells]
                    if cells:
                        table_rows.append(cells)
                    i += 1
                    
                if table_rows:
                    cell_style = ParagraphStyle(
                        "tbl_cell",
                        parent=base_style,
                        fontSize=base_style.fontSize - 1,
                        leading=base_style.leading - 1,
                        alignment=TA_CENTER,
                    )
                    formatted_table_data = []
                    for row_idx, row in enumerate(table_rows):
                        row_cells = []
                        for cell_text in row:
                            if row_idx == 0:
                                p = Paragraph(f"<b>{cell_text}</b>", cell_style)
                            else:
                                p = Paragraph(cell_text, cell_style)
                            row_cells.append(p)
                        formatted_table_data.append(row_cells)
                        
                    rl_table = Table(formatted_table_data, hAlign='LEFT')
                    rl_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f0f4f8')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.HexColor('#1a1a2e')),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#cccccc')),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('LEFTPADDING', (0, 0), (-1, -1), 6),
                        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                    ]))
                    flowables.append(Spacer(1, 4))
                    flowables.append(rl_table)
                    flowables.append(Spacer(1, 6))
                continue
            else:
                paragraph_lines.append(line)
                i += 1
                
        flush_paragraph()
        return flowables

    # ------------------------------------------------------------------
    # Public methods
    # ------------------------------------------------------------------

    def generate_question_paper(
        self,
        validated_questions: list[ValidatedQuestion],
        paper_metadata: Optional[PaperMetadata] = None,
    ) -> str:
        """
        Generate a professional question paper PDF.

        Questions are grouped into sections by marks category:
          Section A — 2 Marks
          Section B — 5 Marks
          Section C — 10 Marks
          Section D — 15 Marks

        Args:
            validated_questions: List of ValidatedQuestion dicts from state.
            paper_metadata:      Optional header metadata for the PDF.

        Returns:
            Absolute path string of the generated PDF file.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"question_paper_{timestamp}.pdf"
        filepath = self.output_dir / filename

        doc = self._new_document(filepath)

        story = []
        story.extend(self._build_header(paper_metadata))
        story.extend(self._build_instructions(paper_metadata))
        story.extend(self._build_question_sections(validated_questions, paper_metadata))

        doc.build(story, canvasmaker=NumberedCanvas)
        logger.info(f"Question paper PDF generated: {filepath}")
        return str(filepath)

    def generate_answer_key(
        self,
        answer_key: list[AnswerKeyItem],
        paper_metadata: Optional[PaperMetadata] = None,
    ) -> str:
        """
        Generate a professional answer key PDF for examiners.

        Args:
            answer_key:     List of AnswerKeyItem dicts from state.
            paper_metadata: Optional header metadata for the PDF.

        Returns:
            Absolute path string of the generated PDF file.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"answer_key_{timestamp}.pdf"
        filepath = self.output_dir / filename

        doc = self._new_document(filepath)

        story = []
        story.extend(self._build_header(paper_metadata, is_answer_key=True))
        story.extend(self._build_answer_key_body(answer_key))

        doc.build(story, canvasmaker=NumberedCanvas)
        logger.info(f"Answer key PDF generated: {filepath}")
        return str(filepath)

    # ------------------------------------------------------------------
    # Header builder
    # ------------------------------------------------------------------

    def _build_header(
        self,
        metadata: Optional[PaperMetadata],
        is_answer_key: bool = False,
    ) -> list:
        """Render a compact header and collapse any metadata that was not supplied."""
        data = metadata or {}
        story = self._build_usn_and_course_code_row(data)
        institution_name = str(data.get("institution_name") or "").strip()
        subtitle = str(data.get("affiliation") or data.get("college_subtitle") or data.get("college_name") or "").strip()
        exam_title = self._exam_heading(data, is_answer_key)
        course_name = str(data.get("course_name") or "").strip()

        if institution_name:
            story.append(Paragraph(institution_name, self.styles["institution"]))
        if subtitle:
            story.append(Paragraph(subtitle, self.styles["subtitle"]))
        if exam_title:
            story.append(Paragraph(exam_title, self.styles["course_name"]))
        if course_name:
            story.append(Paragraph(course_name, self.styles["course_name"]))

        story.extend(self._build_duration_marks_row(data))

        if story:
            story.append(Spacer(1, 7))
        story.append(HRFlowable(width="100%", thickness=0.8, color=colors.black))
        story.append(Spacer(1, 7))
        return story

    def _build_usn_and_course_code_row(self, metadata: dict) -> list:
        """Render the reference-style top strip from optional metadata fields."""
        course_code = str(metadata.get("course_code") or "").strip()
        usn_boxes = metadata.get("usn_boxes") or metadata.get("usn_box_count")
        try:
            box_count = max(0, int(usn_boxes))
        except (TypeError, ValueError):
            box_count = 0
        left_cells = [Paragraph("<b>USN</b>", self.styles["header_info"])]
        left_cells.extend("" for _ in range(box_count))
        left_width = self.content_width * 0.5
        if box_count:
            usn_table = Table([left_cells], colWidths=[left_width / len(left_cells)] * len(left_cells))
            usn_table.setStyle(TableStyle([
                ("GRID", (0, 0), (-1, -1), 0.45, colors.black),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            left = usn_table
        else:
            left = ""
        top_row = Table([[left, Paragraph(f"<b>{course_code}</b>", self.styles["course_name"])]], colWidths=[left_width, left_width])
        top_row.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ]))
        return [top_row, HRFlowable(width="100%", thickness=1.2, color=colors.black), Spacer(1, 5)]

    @staticmethod
    def _exam_heading(metadata: dict, is_answer_key: bool) -> str:
        if is_answer_key:
            return "ANSWER KEY"
        fields = ("exam_type", "semester", "academic_year", "exam_session", "date")
        return " : ".join(str(metadata.get(field)).strip() for field in fields if metadata.get(field) is not None and str(metadata.get(field)).strip())

    def _build_duration_marks_row(self, metadata: dict) -> list:
        """Render only duration and maximum marks in their fixed reference positions."""
        duration = str(metadata.get("duration") or "").strip()
        maximum_marks = metadata.get("maximum_marks")
        left = Paragraph(f"Duration: <b>{duration}</b>" if duration else "", self.styles["header_info"])
        right_text = f"Max. Marks: <b>{maximum_marks}</b>" if maximum_marks is not None and str(maximum_marks).strip() else ""
        right = Paragraph(right_text, self.styles["header_info"])
        table = Table([[left, right]], colWidths=[self.content_width / 2, self.content_width / 2])
        table.setStyle(TableStyle([
            ("ALIGN", (0, 0), (0, 0), "LEFT"),
            ("ALIGN", (1, 0), (1, 0), "RIGHT"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
        ]))
        return [table]

    # ------------------------------------------------------------------
    # Exam instructions
    # ------------------------------------------------------------------

    def _build_instructions(self, metadata: Optional[PaperMetadata] = None) -> list:
        """Render only caller-supplied instructions, never invented exam content."""
        raw_instructions: Any = (metadata or {}).get("instructions")
        if isinstance(raw_instructions, str):
            instructions = [line.strip() for line in raw_instructions.splitlines() if line.strip()]
        elif isinstance(raw_instructions, (list, tuple)):
            instructions = [str(item).strip() for item in raw_instructions if str(item).strip()]
        else:
            instructions = list(settings.pdf.DEFAULT_INSTRUCTIONS)
        story = [Paragraph("<i><b>Instructions:</b></i>", self.styles["answer_heading"])]
        for index, instruction in enumerate(instructions, start=1):
            story.append(Paragraph(f"{index}. {self._format_text(instruction)}", self.styles["instruction"]))
        story.append(Spacer(1, 9))
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"))
        )
        story.append(Spacer(1, 5))
        return story

    # ------------------------------------------------------------------
    # Question sections builder
    # ------------------------------------------------------------------

    def _build_question_sections(
        self,
        validated_questions: list[ValidatedQuestion],
        metadata: Optional[PaperMetadata] = None,
    ) -> list:
        """
        Group questions into sections A/B/C/D by marks category
        and build the flowable list.
        """
        by_marks: dict[Any, list[ValidatedQuestion]] = {}
        for q in validated_questions:
            marks = q.get("marks")
            by_marks.setdefault(marks, []).append(q)

        story = []
        q_number = 1  # Global question counter across all sections

        ordered_groups = sorted(by_marks.items(), key=self._marks_sort_key)
        for part_index, (marks_value, qs) in enumerate(ordered_groups, start=1):
            section_label = self._part_label(part_index)
            column_labels = self._part_column_labels(qs)

            story.append(Paragraph(f"<u>{section_label}</u>", self.styles["section_title"]))
            story.append(Spacer(1, 2))
            story.append(self._render_question_column_headers(column_labels))
            show_modules = bool((metadata or {}).get("show_module_headings", False))
            current_module: Optional[str] = None

            for q in qs:
                module = str(q.get("unit") or "").strip()
                if show_modules and module and module != current_module:
                    story.append(Paragraph(module, self.styles["module_title"]))
                    current_module = module
                story.extend(self._render_question(q, q_number, column_labels))
                
                q_number += 1

            story.append(Spacer(1, 8))

        return story

    @staticmethod
    def _part_label(index: int) -> str:
        """Create a data-derived spreadsheet-style label for any part count."""
        letters = ""
        while index:
            index, remainder = divmod(index - 1, 26)
            letters = chr(65 + remainder) + letters
        return f"PART {letters}"

    @staticmethod
    def _marks_sort_key(group: tuple[Any, list[ValidatedQuestion]]) -> tuple[int, float | str]:
        """Retain the existing ascending mark-group order for any mark values."""
        marks = group[0]
        try:
            return (0, float(marks))
        except (TypeError, ValueError):
            return (1, str(marks or ""))

    @staticmethod
    def _question_columns(question: dict) -> list[tuple[str, str]]:
        columns = [("Marks", str(question.get("marks") or ""))]
        co_value = question.get("co") or question.get("course_outcome")
        if co_value is not None and str(co_value).strip():
            columns.append(("CO", str(co_value)))
        return columns

    def _part_column_labels(self, questions: list[ValidatedQuestion]) -> list[str]:
        labels = ["Marks"]
        available = {label for question in questions for label, _ in self._question_columns(question)}
        for label in ("CO",):
            if label in available:
                labels.append(label)
        return labels

    def _question_column_widths(self, right_count: int) -> list[float]:
        number_width = 35.0
        right_width = 40.0
        text_width = self.content_width - number_width - (right_width * right_count)
        return [number_width, text_width] + [right_width] * right_count

    def _render_question_column_headers(self, column_labels: list[str]) -> Table:
        headers = ["", ""] + column_labels
        table = Table(
            [[Paragraph(f"<b>{label}</b>", self.styles["header_info"]) for label in headers]],
            colWidths=self._question_column_widths(len(column_labels)),
        )
        table.setStyle(TableStyle([
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LINEBELOW", (0, 0), (-1, 0), 0.35, colors.HexColor("#999999")),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ]))
        return table

    def _render_question(
        self, question: ValidatedQuestion, sequence: int, column_labels: list[str]
    ) -> list:
        """Render one non-splitting question group with fixed right-side columns."""
        values = dict(self._question_columns(question))
        label = f"{sequence}."
        question_text = self._format_text(str(question.get("question") or ""))
        question_flowables = [Paragraph(question_text, self.styles["question"])]
        
        options = question.get("options")
        if options and isinstance(options, list) and len(options) == 4:
            # Render MCQ options in a 2x2 grid (A and B on line 1, C and D on line 2)
            opt_table_data = [
                [
                    Paragraph(self._format_text(str(options[0])), self.styles["question"]),
                    Paragraph(self._format_text(str(options[1])), self.styles["question"])
                ],
                [
                    Paragraph(self._format_text(str(options[2])), self.styles["question"]),
                    Paragraph(self._format_text(str(options[3])), self.styles["question"])
                ]
            ]
            
            # width constraint for the 2 cells (half of the question text width)
            text_col_width = self._question_column_widths(len(column_labels))[1]
            opt_col_width = (text_col_width - 15) / 2.0
            
            opt_table = Table(opt_table_data, colWidths=[opt_col_width, opt_col_width], hAlign="LEFT")
            opt_table.setStyle(TableStyle([
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]))
            question_flowables.append(Spacer(1, 4))
            question_flowables.append(opt_table)
            question_flowables.append(Spacer(1, 4))

        row = [
            Paragraph(f"<b>{label}</b>", self.styles["question"]),
            question_flowables,
            *[Paragraph(values.get(col, ""), self.styles["question"]) for col in column_labels],
        ]
        question_table = Table([row], colWidths=self._question_column_widths(len(column_labels)), hAlign="LEFT")
        question_table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("ALIGN", (2, 0), (-1, -1), "CENTER"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 2),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        block: list = [question_table]
        image = self._render_question_image(question.get("image_path"), label)
        if image:
            block.extend([Spacer(1, 4), image, Spacer(1, 4)])
        block.append(Spacer(1, 3))
        return [KeepTogether(block)]

    def _render_question_image(self, image_path: Optional[str], question_label: str) -> Optional[RLImage]:
        """Create a centered image that remains within the printable area."""
        resolved_image = self._resolve_image_path(image_path)
        if not resolved_image:
            if image_path:
                logger.warning(f"Image path specified but file not found: {image_path}")
            return None
        try:
            with PILImage.open(resolved_image) as source:
                image_width, image_height = source.size
            scale = min((self.content_width * 0.82) / image_width, 260.0 / image_height, 1.0)
            image = RLImage(str(resolved_image), width=image_width * scale, height=image_height * scale)
            image.hAlign = "CENTER"
            logger.info(f"Embedded image {resolved_image} for question {question_label}")
            return image
        except Exception as error:
            logger.error(f"Error rendering image {image_path} in PDF: {error}")
            return None

    # ------------------------------------------------------------------
    # Answer key body builder
    # ------------------------------------------------------------------

    def _build_answer_key_body(self, answer_key: list[AnswerKeyItem]) -> list:
        """Build the flowable list for the answer key document."""
        story = []
        story.append(
            Paragraph(
                "<b>MODEL ANSWERS AND MARKING SCHEME</b>",
                self.styles["section_title"],
            )
        )
        story.append(
            HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"))
        )
        story.append(Spacer(1, 8))

        for idx, item in enumerate(answer_key, start=1):
            q_prefix = f"<b>Q{idx}. ({item['marks']} Marks)</b>  "
            q_heading_flowables = self._parse_markdown_tables_and_text(
                item['question'],
                self.styles["answer_heading"],
                prefix=q_prefix,
            )
            story.extend(q_heading_flowables)

            # Embed image if available in Answer Key
            image_path = item.get("image_path")
            resolved_img = self._resolve_image_path(image_path)
            if resolved_img:
                try:
                    with PILImage.open(resolved_img) as pil_img:
                        img_w, img_h = pil_img.size
                    
                    max_width = 320.0
                    scale = max_width / img_w if img_w > max_width else 1.0
                    width = img_w * scale
                    height = img_h * scale
                    
                    story.append(Spacer(1, 4))
                    story.append(RLImage(str(resolved_img), width=width, height=height))
                    story.append(Spacer(1, 6))
                    logger.info(f"Embedded image {resolved_img} for Answer Key question Q{idx}")
                except Exception as img_err:
                    logger.error(f"Error rendering image {image_path} in Answer Key PDF: {img_err}")
            elif image_path:
                logger.warning(f"Answer Key: Image path specified but file not found: {image_path}")

            # --- Model answer ---
            story.append(Paragraph("<b>Model Answer:</b>", self.styles["answer_body"]))
            ma_flowables = self._parse_markdown_tables_and_text(
                item['model_answer'],
                self.styles["answer_body"],
            )
            story.extend(ma_flowables)

            # --- Key points ---
            story.append(Paragraph("<b>Key Points:</b>", self.styles["answer_body"]))
            for kp in item["key_points"]:
                kp_flowables = self._parse_markdown_tables_and_text(
                    kp,
                    self.styles["key_point"],
                    prefix="• ",
                )
                story.extend(kp_flowables)

            # --- Marks breakdown ---
            formatted_marks_breakdown = self._format_text(item['marks_breakdown'])
            story.append(
                Paragraph(
                    f"<i>Marks Breakdown: {formatted_marks_breakdown}</i>",
                    self.styles["marks_breakdown"],
                )
            )

            # Separator between answers
            story.append(Spacer(1, 4))
            story.append(
                HRFlowable(
                    width="100%",
                    thickness=0.3,
                    color=colors.HexColor("#dddddd"),
                )
            )

        return story

    # ------------------------------------------------------------------
    # Footer builder
    # ------------------------------------------------------------------

    def _build_footer(self) -> list:
        """Build the document footer flowables."""
        return [
            Spacer(1, 16),
            HRFlowable(
                width="100%",
                thickness=0.5,
                color=colors.HexColor("#cccccc"),
            ),
            Spacer(1, 4),
            Paragraph(settings.pdf.FOOTER_TEXT, self.styles["footer"]),
        ]
