"""DOCX report generation for FinalReportBySections.

This module formats the step-2 consolidated report into a compact .docx file.

Structure:
- Title: report.doc_title (Document Title style)
- Sections with issues:
  - Heading 1: section.part
  - For each issue: a single-column table (4 rows) spanning page width:
      1) Код ошибки: <error_code>  [error code rendered with smaller font]
      2) Что некорректно: <what_is_incorrect>
      3) Как исправить: <how_to_fix>
      4) Риски, если не исправить: <risk_if_not_fixed>
- Document-wide issues LAST:
  - Heading 1: "Document Wide"
  - Same compact table per issue

Files are written under var/reports/YYYYMMDD/<timestamp>_<runid>_<ggid?>.docx
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re
from typing import Optional

from PromptBuilder.analysis_schemas import FinalReportBySections


_REPORTS_DIR = Path(__file__).resolve().parents[2] / "var" / "reports"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(text: str) -> str:
    """Make a safe filename from arbitrary text for Windows/Unix."""
    text = re.sub(r"[\r\n\t]+", " ", text)
    # Replace forbidden characters and collapse spaces
    text = re.sub(r"[<>:\\/\|\?\*\"]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "report"


def write_final_report_docx(
    report: FinalReportBySections,
    *,
    run_id: str,
    ggid: Optional[int] = None,
) -> Path:
    """Render the provided report to a .docx file and return its path."""

    ts = datetime.now()
    day_dir = _REPORTS_DIR / ts.strftime("%Y%m%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    safe_title = _sanitize_filename(report.doc_title)[:80]
    stamp = ts.strftime("%H%M%S_%f")
    parts = [stamp, run_id]
    if ggid is not None:
        parts.append(str(ggid))
    parts.append(safe_title)
    filename = "_".join(parts) + ".docx"
    out_path = day_dir / filename

    try:
        from docx import Document  # type: ignore[import-untyped]
        from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING  # type: ignore[import-untyped]
        from docx.shared import Pt  # type: ignore[import-untyped]
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "python-docx is required to generate DOCX reports. "
            "Please install it (e.g. add 'python-docx' to requirements)."
        ) from exc

    doc = Document()

    # Title (large as per the 'Title' style)
    title_par = doc.add_paragraph()
    title_par.add_run(report.doc_title)
    title_par.style = doc.styles["Title"]
    title_par.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Helpers
    def _compact_paragraph(p):
        pf = p.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
        pf.line_spacing = 1.0

    # Render an issue as two compact paragraphs (без строки с кодом ошибки).
    # Риск добавляется как комментарий Word к тексту 'Что некорректно' с префиксом (CODE).
    def _render_issue_block(code: str, what: str, how: str, risk: str | None = None) -> None:
        # Line 1: what is incorrect (attach comment here if risk exists)
        p1 = doc.add_paragraph()
        r1_label = p1.add_run("Что некорректно: ")
        r1_label.bold = True
        what_run = p1.add_run(what)
        _compact_paragraph(p1)
        if risk:
            try:
                doc.add_comment(what_run, text=f"({code}) {risk}", author="", initials="")
            except Exception:
                pass

        # Line 2: how to fix
        p2 = doc.add_paragraph()
        r2_label = p2.add_run("Как исправить: ")
        r2_label.bold = True
        p2.add_run(how)
        _compact_paragraph(p2)

        # Spacing after each issue
        _compact_paragraph(doc.add_paragraph())

    # Sections first
    for section in report.by_sections:
        if not section.issues:
            continue
        doc.add_heading(section.part, level=1)
        for issue in section.issues:
            _render_issue_block(
                code=issue.error_code,
                what=issue.what_is_incorrect,
                how=issue.how_to_fix,
                risk=getattr(issue, "risk_if_not_fixed", None),
            )

    # Document-wide issues last
    if report.document_wide:
        doc.add_heading("Document Wide", level=1)
        for issue in report.document_wide:
            _render_issue_block(
                code=issue.error_code,
                what=issue.what_is_incorrect,
                how=issue.how_to_fix,
                risk=getattr(issue, "risk_if_not_fixed", None),
            )

    doc.save(out_path)
    return out_path
