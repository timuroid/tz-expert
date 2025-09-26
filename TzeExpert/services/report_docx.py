"""DOCX report generation for SectionPlanOutput (Step 2 v3).

Builds a compact .docx report from the SectionPlanOutput and step-1 parsed results.

Formatting:
- Title: plan.doc_title (Title style)
- Optional: Proposed New Sections (bullet list)
- Sections (in plan order):
  - Heading 1: section.part
  - For each instance id in final_instance_ids:
    - Line 1: "Что некорректно: " + text (comment attached with "(ID) risk" if risk present)
    - Line 2: "Как исправить: " + fix
    - Compact spacing between lines and items
"""
from __future__ import annotations

from pathlib import Path
from datetime import datetime
import re
from typing import Optional, Dict, List

from PromptBuilder.section_plan import SectionPlanOutput, SectionRow
from TzeExpert.schemas import Step1Run


_REPORTS_DIR = Path(__file__).resolve().parents[2] / "var" / "reports"
_REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def _sanitize_filename(text: str) -> str:
    text = re.sub(r"[\r\n\t]+", " ", text)
    text = re.sub(r"[<>:\\\\/\|\?\*\"]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text or "report"


def _build_instance_index(step1_runs: List[Step1Run]) -> Dict[str, Dict[str, str]]:
    idx: Dict[str, Dict[str, str]] = {}
    for run in step1_runs:
        for err in run.parsed.errors:
            for inst in err.instances:
                # normalize to strings
                idx[str(inst.id)] = {
                    "what": str(getattr(inst, "what_is_incorrect", "")),
                    "fix": str(getattr(inst, "fix", "")),
                    "risks": str(getattr(inst, "risks", "")),
                }
    return idx


def write_section_plan_docx(
    plan: SectionPlanOutput,
    *,
    step1_runs: List[Step1Run],
    run_id: str,
    ggid: Optional[int] = None,
) -> Path:
    ts = datetime.now()
    day_dir = _REPORTS_DIR / ts.strftime("%Y%m%d")
    day_dir.mkdir(parents=True, exist_ok=True)

    safe_title = _sanitize_filename(plan.doc_title)[:80]
    stamp = ts.strftime("%H%M%S_%f")
    parts = [stamp, run_id]
    if ggid is not None:
        parts.append(str(ggid))
    parts.append(safe_title)
    filename = "_".join(parts) + ".docx"
    out_path = day_dir / filename

    try:
        from docx import Document  # type: ignore
        from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_LINE_SPACING  # type: ignore
        from docx.shared import Pt  # type: ignore
    except Exception as exc:  # pragma: no cover
        raise RuntimeError(
            "python-docx is required to generate DOCX reports. "
            "Please install it (e.g. add 'python-docx' to requirements)."
        ) from exc

    doc = Document()

    def _compact_paragraph(p):
        pf = p.paragraph_format
        pf.space_before = Pt(0)
        pf.space_after = Pt(0)
        pf.line_spacing_rule = WD_LINE_SPACING.SINGLE
        pf.line_spacing = 1.0

    # Title
    title_par = doc.add_paragraph()
    title_par.add_run(plan.doc_title)
    title_par.style = doc.styles["Title"]
    title_par.alignment = WD_ALIGN_PARAGRAPH.CENTER

    # Proposed new sections (optional) — disabled in header per new format
    if False and plan.proposed_new_sections:
        doc.add_heading("Предлагаемые новые разделы", level=1)
        for ns in plan.proposed_new_sections:
            p = doc.add_paragraph(style=None)
            p.add_run(f"{ns.name} — {ns.suggested_position}" + (f" {ns.position_ref}" if ns.position_ref else "") + f". {ns.reason}")
            _compact_paragraph(p)

    # Build index from step1
    inst_index = _build_instance_index(step1_runs)

    # Sections in order
    for row in plan.sections:
        # Skip sections without any final_instance_ids
        if not getattr(row, "final_instance_ids", None):
            continue
        doc.add_heading(row.part, level=1)
        for iid in row.final_instance_ids:
            data = inst_index.get(str(iid))
            if not data:
                # mention unplaced/missing quietly
                p = doc.add_paragraph()
                p.add_run(f"Не удалось найти инстанс {iid} по результатам шага 1")
                _compact_paragraph(p)
                continue

            # Line 1: what (with risk as comment if present)
            p1 = doc.add_paragraph()
            r1_label = p1.add_run("Что некорректно: ")
            r1_label.bold = True
            what_run = p1.add_run(data.get("what", ""))
            _compact_paragraph(p1)
            risk = data.get("risks") or None
            if risk:
                try:
                    # Attach a comment containing (ID) risk
                    doc.add_comment(what_run, text=f"({iid}) {risk}", author="", initials="")
                except Exception:
                    pass

            # Line 2: fix
            p2 = doc.add_paragraph()
            r2_label = p2.add_run("Как исправить: ")
            r2_label.bold = True
            p2.add_run(data.get("fix", ""))
            _compact_paragraph(p2)

            # spacer
            _compact_paragraph(doc.add_paragraph())

    # Notes and unplaced (optional)
    if plan.unplaced_instances:
        doc.add_heading("Непривязанные инстансы", level=1)
        p = doc.add_paragraph(", ".join(plan.unplaced_instances))
        _compact_paragraph(p)
    if plan.notes:
        p = doc.add_paragraph(plan.notes)
        _compact_paragraph(p)

    doc.save(out_path)
    return out_path
