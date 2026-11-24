"""
PDF Annotation module using PyMuPDF.

This module provides functions to visually annotate graded answer sheets
with scores, bounding boxes, feedback, and summary banners.
"""
import io
import fitz
from core.models import StudentGradingResult, GradedQuestion

def annotate_graded_pdf(input_pdf_bytes: bytes, grading_result: StudentGradingResult) -> bytes:
    """
    Annotates a PDF document with grading results, drawing bounding boxes,
    scores, and feedback annotations.

    Args:
        input_pdf_bytes: The original PDF document as bytes.
        grading_result: The parsed grading result containing answers and scores.

    Returns:
        The annotated PDF as bytes.
    """
    doc = fitz.open(stream=input_pdf_bytes, filetype="pdf")

    # Group results by page
    results_by_page = {}
    for result in grading_result.results:
        page_idx = result.page_number - 1  # 0-indexed
        if page_idx not in results_by_page:
            results_by_page[page_idx] = []
        results_by_page[page_idx].append(result)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_rect = page.rect
        width = page_rect.width
        height = page_rect.height

        # Add summary banner on page 1 (index 0)
        if page_idx == 0:
            _add_summary_banner(page, width, grading_result)

        if page_idx in results_by_page:
            for ans_result in results_by_page[page_idx]:
                _annotate_answer(page, width, height, ans_result)

    output_stream = io.BytesIO()
    doc.save(output_stream)
    doc.close()
    return output_stream.getvalue()

def _add_summary_banner(page: fitz.Page, width: float, grading_result: StudentGradingResult) -> None:
    """Adds a branded summary banner at the top of the first page."""
    banner_height = 54
    banner_rect = fitz.Rect(0, 0, width, banner_height)
    
    # Ensure percentage is computed
    percentage = grading_result.percentage
    if percentage is None:
        percentage = grading_result.compute_percentage()
        
    pass_fail = "PASS" if percentage >= 50.0 else "NEEDS IMPROVEMENT"
    border_color = (0.92, 0.11, 0.14)  # upGrad Red #eb1c24
    bg_color = (0.98, 0.98, 0.99)
    
    page.draw_rect(banner_rect, color=border_color, fill=bg_color, width=1.2)
    page.draw_rect(fitz.Rect(0, 0, 6, banner_height), color=border_color, fill=border_color)
    
    page.insert_text(
        fitz.Point(18, 20),
        "UPGRAD SCHOOL OF TECHNOLOGY  |  OFFICIAL EVALUATION",
        fontsize=8.5,
        color=(0.5, 0.5, 0.6),
        fontname="helvetica-bold"
    )
    
    summary_text = (
        f"Score: {grading_result.total_marks_awarded:.1f} / {grading_result.total_max_marks:.1f}  "
        f"({percentage:.1f}%)  -  {pass_fail}"
    )
    score_color = (0.1, 0.55, 0.2) if percentage >= 50.0 else (0.85, 0.15, 0.15)
    page.insert_text(
        fitz.Point(18, 40),
        summary_text,
        fontsize=13,
        color=score_color,
        fontname="helvetica-bold"
    )

def _annotate_answer(page: fitz.Page, width: float, height: float, result: GradedQuestion) -> None:
    """Annotates a single graded question on the page."""
    # Convert normalized coords [ymin, xmin, ymax, xmax] to [x0, y0, x1, y1] points
    ymin_norm, xmin_norm, ymax_norm, xmax_norm = result.box_2d
    x0 = (xmin_norm / 1000.0) * width
    y0 = (ymin_norm / 1000.0) * height
    x1 = (xmax_norm / 1000.0) * width
    y1 = (ymax_norm / 1000.0) * height
    
    rect = fitz.Rect(x0, y0, x1, y1)
    
    # Determine color
    if result.marks_awarded == result.max_marks:
        color = (0.0, 0.7, 0.0) # Green
    elif result.marks_awarded == 0:
        color = (0.8, 0.0, 0.0) # Red
    else:
        color = (0.9, 0.5, 0.0) # Orange
        
    # Draw rectangle
    page.draw_rect(rect, color=color, width=2.0)
    
    # Score badge
    badge_text = f"Q{result.question_number}: {result.marks_awarded}/{result.max_marks}"
    badge_rect = fitz.Rect(x0, y0 - 15, x0 + 80, y0)
    page.draw_rect(badge_rect, color=color, fill=color)
    page.insert_text(
        fitz.Point(x0 + 5, y0 - 4),
        badge_text,
        fontsize=10,
        color=(1.0, 1.0, 1.0),
        fontname="helv-bo"
    )
    
    # Warning indicator for low confidence
    if result.confidence_score < 0.85:
        warn_point = fitz.Point(x1 + 5, y0 + 10)
        page.insert_text(
            warn_point,
            "⚠️",
            fontsize=14,
            color=(0.9, 0.8, 0.0) # Yellow-ish
        )
        
    # Sticky note annotation
    annot = page.add_text_annot(fitz.Point(x1 - 15, y0 + 5), result.step_by_step_feedback)
    annot.set_colors(stroke=color)
    annot.update()
