"""
Report Generator Module.

Generates Excel and CSV reports for grading sessions.
"""
import io
import fitz
import pandas as pd
from typing import Tuple, Optional
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils.dataframe import dataframe_to_rows
from core.models import GradingSession, StudentGradingResult, ExamRubric

def generate_excel_report(session: GradingSession, filepath: str) -> None:
    """Generates a styled Excel report and saves it to a file."""
    excel_bytes, _ = generate_report_bytes(session)
    with open(filepath, "wb") as f:
        f.write(excel_bytes)

def generate_csv_report(session: GradingSession, filepath: str) -> None:
    """Generates a CSV report and saves it to a file."""
    _, csv_bytes = generate_report_bytes(session)
    with open(filepath, "wb") as f:
        f.write(csv_bytes)

def generate_report_bytes(session: GradingSession) -> Tuple[bytes, bytes]:
    """
    Generates Excel and CSV reports in memory.
    
    Returns:
        A tuple of (excel_bytes, csv_bytes).
    """
    # Create DataFrames
    summary_data = []
    question_data = []
    
    all_questions = set()
    
    for result in session.student_results:
        # Ensure percentage is computed
        pct = result.percentage
        if pct is None:
            pct = result.compute_percentage()
            
        pass_fail = "Pass" if pct >= 50.0 else "Fail"
        review_flag = "Yes" if result.has_flags() else "No"
        student_id = result.student_name_or_id or "Unknown"
        
        summary_data.append({
            "Student ID/Name": student_id,
            "Total Score": result.total_marks_awarded,
            "Max Score": result.total_max_marks,
            "Percentage": pct,
            "Pass/Fail": pass_fail,
            "Review Flag": review_flag
        })
        
        q_row = {"Student ID/Name": student_id}
        for q_res in result.results:
            q_key = f"Q{q_res.question_number}"
            all_questions.add(q_key)
            q_row[q_key] = f"{q_res.marks_awarded}/{q_res.max_marks}"
            q_row[f"{q_key}_raw"] = q_res.marks_awarded
            
        q_row["Total"] = result.total_marks_awarded
        question_data.append(q_row)

    df_summary = pd.DataFrame(summary_data)
    
    # Sort questions for breakdown
    q_keys = sorted(list(all_questions))
    breakdown_columns = ["Student ID/Name"] + q_keys + ["Total"]
    
    df_breakdown = pd.DataFrame(question_data)
    if not df_breakdown.empty:
        # Keep only the display columns
        df_breakdown_display = df_breakdown[breakdown_columns]
    else:
        df_breakdown_display = pd.DataFrame(columns=breakdown_columns)
        
    # Generate CSV
    csv_bytes = df_summary.to_csv(index=False).encode('utf-8')
    
    # Generate Excel
    wb = Workbook()
    
    # Sheet 1: Class Summary
    ws_summary = wb.active
    ws_summary.title = "Class Summary"
    for r in dataframe_to_rows(df_summary, index=False, header=True):
        ws_summary.append(r)
        
    # Styling variables
    header_fill = PatternFill(start_color="000080", end_color="000080", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True)
    fail_fill = PatternFill(start_color="FFC0CB", end_color="FFC0CB", fill_type="solid")
    review_fill = PatternFill(start_color="FFFF00", end_color="FFFF00", fill_type="solid")
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'), 
                         top=Side(style='thin'), bottom=Side(style='thin'))

    def apply_header_style(ws):
        for cell in ws[1]:
            cell.fill = header_fill
            cell.font = header_font
            cell.alignment = Alignment(horizontal="center")
            cell.border = thin_border
            
    def auto_width(ws):
        for column in ws.columns:
            max_length = 0
            column = [cell for cell in column]
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(cell.value)
                except:
                    pass
            adjusted_width = (max_length + 2)
            ws.column_dimensions[column[0].column_letter].width = adjusted_width

    apply_header_style(ws_summary)
    
    # Conditional formatting for summary
    for row in ws_summary.iter_rows(min_row=2, max_row=ws_summary.max_row, min_col=1, max_col=6):
        pass_fail_val = row[4].value
        review_val = row[5].value
        
        for cell in row:
            cell.border = thin_border
            if pass_fail_val == "Fail":
                cell.fill = fail_fill
            elif review_val == "Yes":
                cell.fill = review_fill

    auto_width(ws_summary)

    # Sheet 2: Question Breakdown
    ws_breakdown = wb.create_sheet(title="Question Breakdown")
    for r in dataframe_to_rows(df_breakdown_display, index=False, header=True):
        ws_breakdown.append(r)
        
    apply_header_style(ws_breakdown)
    for row in ws_breakdown.iter_rows(min_row=2, max_row=ws_breakdown.max_row, min_col=1, max_col=len(breakdown_columns)):
        for cell in row:
            cell.border = thin_border
            
    auto_width(ws_breakdown)

    # Sheet 3: Analytics
    ws_analytics = wb.create_sheet(title="Analytics")
    
    class_avg = session.get_class_average()
    scores = [r.total_marks_awarded for r in session.student_results]
    
    highest_score = max(scores) if scores else 0
    lowest_score = min(scores) if scores else 0
    
    if scores:
        std_dev = pd.Series(scores).std()
        if pd.isna(std_dev):
            std_dev = 0.0
    else:
        std_dev = 0.0
        
    pass_count = sum(1 for r in session.student_results if (r.percentage or 0) >= 50.0)
    pass_rate = (pass_count / len(scores) * 100) if scores else 0
    
    analytics_data = [
        ["Metric", "Value"],
        ["Class Average (%)", f"{class_avg}%"],
        ["Highest Score", highest_score],
        ["Lowest Score", lowest_score],
        ["Std Deviation", f"{std_dev:.2f}"],
        ["Pass Rate", f"{pass_rate:.1f}%"]
    ]
    
    # Per question averages
    if not df_breakdown.empty:
        analytics_data.append([])
        analytics_data.append(["Question", "Average Score"])
        for q in q_keys:
            raw_col = f"{q}_raw"
            if raw_col in df_breakdown.columns:
                avg = df_breakdown[raw_col].mean()
                analytics_data.append([q, f"{avg:.2f}"])
                
    for row in analytics_data:
        ws_analytics.append(row)
        
    # Style Analytics
    for row_idx, row in enumerate(ws_analytics.iter_rows(min_row=1, max_row=ws_analytics.max_row, min_col=1, max_col=2), 1):
        for cell in row:
            if cell.value in ["Metric", "Value", "Question", "Average Score"]:
                cell.fill = header_fill
                cell.font = header_font
            cell.border = thin_border
            
    auto_width(ws_analytics)

    # Save to bytes
    excel_io = io.BytesIO()
    wb.save(excel_io)
    excel_bytes = excel_io.getvalue()
    
    return excel_bytes, csv_bytes


def get_letter_grade(percentage: float) -> str:
    """Calculates letter grade from percentage."""
    if percentage >= 90:
        return "A+"
    elif percentage >= 80:
        return "A"
    elif percentage >= 70:
        return "B"
    elif percentage >= 60:
        return "C"
    elif percentage >= 50:
        return "D"
    else:
        return "F"


def generate_student_report_card_pdf(
    student: StudentGradingResult,
    rubric: Optional[ExamRubric] = None,
) -> bytes:
    """
    Generates a professional, multi-page PDF performance report card for an individual student.
    Includes score summary, letter grade, question breakdown, transcribed answer, feedback, and deductions.
    """
    doc = fitz.open()
    page_width = 595  # A4 width in points
    page_height = 842  # A4 height in points

    pct = student.percentage
    if pct is None:
        pct = student.compute_percentage()
    grade = get_letter_grade(pct)
    is_pass = pct >= 50.0

    exam_title = rubric.exam_title if rubric else "Examination Evaluation"
    subject = rubric.subject if rubric and rubric.subject else "General"

    page = doc.new_page(width=page_width, height=page_height)
    
    # ── Top Header Banner ──
    banner_height = 68
    header_color = (0.92, 0.11, 0.14)  # upGrad Crimson Red #eb1c24
    page.draw_rect(fitz.Rect(0, 0, page_width, banner_height), color=header_color, fill=header_color)
    page.insert_text(
        fitz.Point(30, 25),
        "UPGRAD SCHOOL OF TECHNOLOGY",
        fontsize=10,
        color=(1, 0.88, 0.88),
        fontname="helvetica-bold"
    )
    page.insert_text(
        fitz.Point(30, 44),
        "STUDENT EVALUATION REPORT CARD",
        fontsize=15,
        color=(1, 1, 1),
        fontname="helvetica-bold"
    )
    page.insert_text(
        fitz.Point(30, 58),
        f"{exam_title.upper()}  |  SUBJECT: {subject.upper()}",
        fontsize=8.5,
        color=(1, 0.9, 0.9),
        fontname="helv"
    )

    # ── Student Details Box ──
    y_cursor = 85
    student_name = student.student_name_or_id or "Student"
    
    info_box = fitz.Rect(30, y_cursor, page_width - 30, y_cursor + 75)
    page.draw_rect(info_box, color=(0.85, 0.88, 0.95), fill=(0.95, 0.97, 1), width=1)
    
    page.insert_text(fitz.Point(45, y_cursor + 28), f"Student Name: {student_name}", fontsize=13, fontname="helvetica-bold", color=(0.1, 0.1, 0.2))
    status_text = "STATUS: PASSED" if is_pass else "STATUS: NEEDS IMPROVEMENT"
    status_color = (0.1, 0.55, 0.2) if is_pass else (0.8, 0.15, 0.15)
    page.insert_text(fitz.Point(45, y_cursor + 52), status_text, fontsize=11, fontname="helvetica-bold", color=status_color)
    
    badge_x = page_width - 200
    page.insert_text(fitz.Point(badge_x, y_cursor + 28), f"Total Score: {student.total_marks_awarded:.1f} / {student.total_max_marks:.1f}", fontsize=12, fontname="helvetica-bold", color=(0.1, 0.2, 0.4))
    page.insert_text(fitz.Point(badge_x, y_cursor + 52), f"Percentage: {pct:.1f}%  (Grade: {grade})", fontsize=12, fontname="helvetica-bold", color=header_color)

    y_cursor += 95
    page.insert_text(fitz.Point(30, y_cursor), "QUESTION-BY-QUESTION EVALUATION BREAKDOWN", fontsize=12, fontname="helvetica-bold", color=(0.15, 0.2, 0.35))
    page.draw_line(fitz.Point(30, y_cursor + 5), fitz.Point(page_width - 30, y_cursor + 5), color=(0.7, 0.75, 0.85), width=1)
    y_cursor += 18

    # ── Render Each Question Card ──
    for q in student.results:
        if y_cursor > 700:
            page = doc.new_page(width=page_width, height=page_height)
            y_cursor = 40

        is_full = q.marks_awarded == q.max_marks
        is_zero = q.marks_awarded == 0
        q_color = (0.1, 0.6, 0.2) if is_full else ((0.8, 0.15, 0.15) if is_zero else (0.9, 0.5, 0.1))

        q_title = f"Question {q.question_number}  [{q.marks_awarded:.1f} / {q.max_marks:.1f} Marks]"
        page.insert_text(fitz.Point(35, y_cursor + 12), q_title, fontsize=11, fontname="helvetica-bold", color=q_color)
        
        conf_label = f"Confidence: {int(q.confidence_score * 100)}%"
        page.insert_text(fitz.Point(page_width - 150, y_cursor + 12), conf_label, fontsize=9, fontname="helv", color=(0.4, 0.4, 0.5))
        
        y_cursor += 22
        
        clean_transcript = q.transcription.replace("\n", " ") if q.transcription else "No answer recorded"
        if len(clean_transcript) > 120:
            clean_transcript = clean_transcript[:117] + "..."
        page.insert_text(fitz.Point(40, y_cursor + 8), "Student Answer:", fontsize=9, fontname="helvetica-bold", color=(0.2, 0.2, 0.3))
        page.insert_text(fitz.Point(125, y_cursor + 8), clean_transcript, fontsize=9, fontname="helv", color=(0.3, 0.3, 0.4))
        y_cursor += 16

        clean_feedback = q.step_by_step_feedback.replace("\n", " ") if q.step_by_step_feedback else "N/A"
        if len(clean_feedback) > 120:
            clean_feedback = clean_feedback[:117] + "..."
        page.insert_text(fitz.Point(40, y_cursor + 8), "AI Feedback:", fontsize=9, fontname="helvetica-bold", color=(0.2, 0.2, 0.3))
        page.insert_text(fitz.Point(125, y_cursor + 8), clean_feedback, fontsize=9, fontname="helv", color=(0.2, 0.3, 0.5))
        y_cursor += 16

        if q.deduction_reasons:
            deduct_str = ", ".join(q.deduction_reasons)
            if len(deduct_str) > 120:
                deduct_str = deduct_str[:117] + "..."
            page.insert_text(fitz.Point(40, y_cursor + 8), "Deductions:", fontsize=9, fontname="helvetica-bold", color=(0.7, 0.2, 0.2))
            page.insert_text(fitz.Point(125, y_cursor + 8), deduct_str, fontsize=9, fontname="helv", color=(0.6, 0.2, 0.2))
            y_cursor += 16

        page.draw_line(fitz.Point(35, y_cursor + 6), fitz.Point(page_width - 35, y_cursor + 6), color=(0.88, 0.9, 0.94), width=0.7)
        y_cursor += 16

    # ── Footer on all pages ──
    for p_idx in range(len(doc)):
        p = doc[p_idx]
        p.draw_line(fitz.Point(30, page_height - 35), fitz.Point(page_width - 30, page_height - 35), color=(0.8, 0.8, 0.85), width=0.5)
        p.insert_text(
            fitz.Point(30, page_height - 20),
            "upGrad School of Technology  |  Answer Sheet Grader  |  Verified by Faculty",
            fontsize=8,
            color=(0.5, 0.5, 0.6),
            fontname="helv"
        )
        p.insert_text(
            fitz.Point(page_width - 80, page_height - 20),
            f"Page {p_idx + 1} of {len(doc)}",
            fontsize=8,
            color=(0.5, 0.5, 0.6),
            fontname="helv"
        )

    pdf_bytes = doc.tobytes()
    doc.close()
    return pdf_bytes
