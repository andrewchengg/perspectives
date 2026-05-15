"""
ASAM Level of Care Report Generator

Generates a professional PDF report from an ASAM evaluation result.
"""

import io
from datetime import datetime, timezone

from fpdf import FPDF


class ASAMReportPDF(FPDF):
    """Custom PDF class for ASAM reports."""

    def __init__(self):
        super().__init__()
        self.set_auto_page_break(auto=True, margin=20)

    def header(self):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(100, 100, 100)
        self.cell(0, 8, "Perspectives Health  |  ASAM Level of Care Report", ln=True, align="L")
        self.set_draw_color(59, 130, 246)
        self.set_line_width(0.5)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(6)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(150, 150, 150)
        self.cell(0, 10, f"Page {self.page_no()}/{{nb}}  |  Generated {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}", align="C")

    def section_title(self, title: str):
        self.ln(4)
        self.set_font("Helvetica", "B", 12)
        self.set_text_color(30, 30, 30)
        self.cell(0, 8, title, ln=True)
        self.set_draw_color(200, 200, 200)
        self.set_line_width(0.2)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def subsection_title(self, title: str):
        self.set_font("Helvetica", "B", 10)
        self.set_text_color(59, 130, 246)
        self.cell(0, 7, title, ln=True)

    def body_text(self, text: str):
        self.set_font("Helvetica", "", 9)
        self.set_text_color(50, 50, 50)
        self.multi_cell(0, 5, text)
        self.ln(2)

    def label_value(self, label: str, value: str):
        self.set_font("Helvetica", "B", 9)
        self.set_text_color(80, 80, 80)
        self.cell(45, 6, label + ":", align="L")
        self.set_font("Helvetica", "", 9)
        self.set_text_color(30, 30, 30)
        self.cell(0, 6, value, ln=True)

    def citation_block(self, source: str, text: str):
        self.set_x(15)
        self.set_draw_color(59, 130, 246)
        self.set_line_width(0.4)
        y_start = self.get_y()
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(100, 100, 100)
        self.multi_cell(175, 4, f'[{source}] "{text}"')
        y_end = self.get_y()
        self.line(14, y_start, 14, y_end)
        self.ln(2)

    def risk_badge(self, code: str, level: str):
        self.set_font("Helvetica", "B", 9)
        self.set_fill_color(235, 242, 255)
        self.set_text_color(59, 130, 246)
        self.cell(20, 6, f" {code} ", border=1, fill=True, align="C")
        self.set_text_color(80, 80, 80)
        self.set_font("Helvetica", "", 9)
        self.cell(5, 6, "")
        self.cell(0, 6, f"Minimum Level: {level}", ln=True)


def generate_asam_report(patient_data: dict, asam_data: dict) -> bytes:
    """Generate a PDF report from ASAM evaluation data.

    Args:
        patient_data: Patient extraction dict (patient, assessment, progress_notes)
        asam_data: ASAM evaluation result dict (dimensions, recommended_level, etc.)

    Returns:
        PDF bytes
    """
    pdf = ASAMReportPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    p = patient_data.get("patient", {})

    # ── Title ──
    pdf.set_font("Helvetica", "B", 18)
    pdf.set_text_color(20, 20, 20)
    pdf.cell(0, 12, "ASAM Level of Care Evaluation", ln=True)
    pdf.ln(2)

    # ── Patient Info ──
    pdf.section_title("Patient Information")
    pdf.label_value("Name", f"{p.get('first_name', '')} {p.get('last_name', '')}")
    pdf.label_value("Date of Birth", str(p.get("date_of_birth", "")))
    pdf.label_value("Gender", p.get("gender", ""))
    pdf.label_value("Admission Date", str(p.get("admission_date", "")))
    if p.get("diagnoses"):
        dx_str = ", ".join(d.get("code", "") for d in p["diagnoses"] if d.get("code"))
        if dx_str:
            pdf.label_value("Diagnoses", dx_str)
    pdf.ln(2)

    # ── Recommendation ──
    pdf.section_title("Level of Care Recommendation")
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(59, 130, 246)
    level = asam_data.get("recommended_level", "--")
    level_name = asam_data.get("recommended_level_name", "")
    pdf.cell(0, 10, f"Level {level}  —  {level_name}", ln=True)
    pdf.ln(2)

    if asam_data.get("level_rationale"):
        pdf.body_text(asam_data["level_rationale"])

    # ── Dimensions ──
    pdf.section_title("Dimensional Assessment")

    for dim in asam_data.get("dimensions", []):
        dim_num = dim.get("dimension_number", "")
        dim_name = dim.get("dimension_name", "")
        pdf.subsection_title(f"Dimension {dim_num}: {dim_name}")
        pdf.ln(1)

        if dim.get("key_factors"):
            pdf.set_font("Helvetica", "I", 8)
            pdf.set_text_color(120, 120, 120)
            pdf.multi_cell(0, 4, "Key factors: " + ", ".join(dim["key_factors"]))
            pdf.ln(2)

        for sub in dim.get("subdimensions", []):
            # Subdimension name + risk badge
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(0, 6, sub.get("name", ""), ln=True)
            pdf.risk_badge(sub.get("risk_rating_code", ""), sub.get("minimum_level", ""))
            pdf.ln(1)

            # Rationale
            rationale = sub.get("rationale", "")
            if rationale:
                pdf.body_text(rationale)

            # Citations
            for cit in sub.get("citations", [])[:3]:
                pdf.citation_block(cit.get("source", ""), cit.get("text", "")[:200])

        pdf.ln(3)

    # ── LOC Determination Steps ──
    steps = asam_data.get("loc_determination_steps", [])
    if steps:
        pdf.section_title("Level of Care Determination Steps")
        for step in steps:
            pdf.set_font("Helvetica", "B", 9)
            pdf.set_text_color(50, 50, 50)
            pdf.cell(20, 6, f"Step {step.get('step', '')}:")
            pdf.set_font("Helvetica", "", 9)
            desc = step.get("description", "")
            result = step.get("result", "")
            pdf.multi_cell(0, 6, f"{desc}")
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(59, 130, 246)
            pdf.cell(20, 6, "")
            pdf.cell(0, 6, f"Result: {result}", ln=True)
            pdf.set_text_color(50, 50, 50)
            pdf.ln(2)

    # ── Clinical Summary ──
    summary = asam_data.get("clinical_summary", "")
    if summary:
        pdf.section_title("Clinical Summary")
        pdf.body_text(summary)

    # ── QA Validation ──
    qa = asam_data.get("qa_validation", {})
    if qa:
        pdf.section_title("QA Validation")
        llm_val = qa.get("llm_validation", {})
        quality = llm_val.get("overall_quality", "unknown")
        cite_issues = len(qa.get("citation_issues", []))
        loc_issues = len(qa.get("loc_consistency_issues", []))
        pdf.label_value("Overall Quality", quality.upper())
        pdf.label_value("Citation Issues", str(cite_issues))
        pdf.label_value("LOC Consistency Issues", str(loc_issues))
        if llm_val.get("issues_summary"):
            pdf.ln(2)
            pdf.body_text(llm_val["issues_summary"])

    # ── Disclaimer ──
    pdf.ln(6)
    pdf.set_font("Helvetica", "I", 7)
    pdf.set_text_color(150, 150, 150)
    pdf.multi_cell(0, 4,
        "DISCLAIMER: This report was generated by an AI-assisted clinical decision support tool. "
        "It is intended to assist qualified clinicians and does not constitute a definitive clinical recommendation. "
        "All findings should be reviewed and validated by a licensed professional before use in treatment planning. "
        "Based on ASAM Criteria, Fourth Edition."
    )

    return pdf.output()
