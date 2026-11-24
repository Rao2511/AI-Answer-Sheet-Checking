import io
import os
from typing import Optional
from docx import Document
from google import genai
from google.genai import types

from core.models import ExamRubric
from core.pdf_processor import extract_text_from_pdf
from core.ai_client import generate_content_with_fallback


def _extract_text_from_docx(file_bytes: bytes) -> str:
    """
    Extracts all text from a Word (.docx) document, including paragraphs and tables.
    """
    try:
        doc = Document(io.BytesIO(file_bytes))
        full_text = []

        # Extract text from paragraphs
        for para in doc.paragraphs:
            if para.text.strip():
                full_text.append(para.text.strip())

        # Extract text from tables
        for table in doc.tables:
            for row in table.rows:
                row_data = []
                for cell in row.cells:
                    if cell.text.strip():
                        row_data.append(cell.text.strip())
                if row_data:
                    full_text.append(" | ".join(row_data))

        return "\n".join(full_text)
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from DOCX: {e}")


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    """
    Extracts all text from a PDF document.
    """
    try:
        return extract_text_from_pdf(file_bytes)
    except Exception as e:
        raise RuntimeError(f"Failed to extract text from PDF: {e}")


import re
from core.models import QuestionRubric, QuestionType, GradingCriterion
from core.ai_client import generate_content_with_fallback, repair_truncated_json, _safe_log


def _build_fallback_rubric(raw_text: str) -> ExamRubric:
    """
    Resilient fallback parser: extracts questions, marks, and sections from raw text
    using pattern matching if AI parsing encounters an unrecoverable failure.
    """
    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
    title = lines[0][:80] if lines else "Uploaded Examination"
    
    questions = []
    q_pattern = re.compile(
        r"^(?:Question|Q\.?|Que\.?)\s*(\d+[a-z]?|[a-z]|\d+)|^\s*(\d+)\.\s+",
        re.IGNORECASE
    )
    marks_pattern = re.compile(
        r"\[(\d+(?:\.\d+)?)\s*(?:marks?|pts?|m)\]|\((\d+(?:\.\d+)?)\s*(?:marks?|pts?|m)\)|(\d+(?:\.\d+)?)\s*(?:marks?|pts?)",
        re.IGNORECASE
    )

    for line in lines:
        match = q_pattern.search(line)
        if match:
            q_num = match.group(1) or match.group(2)
            marks_match = marks_pattern.search(line)
            marks = float(marks_match.group(1) or marks_match.group(2) or marks_match.group(3)) if marks_match else 5.0
            
            q_obj = QuestionRubric(
                question_number=str(q_num),
                question_type=QuestionType.SUBJECTIVE,
                question_text=line[:250],
                max_marks=marks,
                model_answer="Refer to rubric document.",
                criteria=[
                    GradingCriterion(
                        step_description="Correct reasoning and final answer",
                        allocated_marks=marks,
                        keywords_or_formula=[]
                    )
                ]
            )
            questions.append(q_obj)

    if not questions:
        questions.append(
            QuestionRubric(
                question_number="1",
                question_type=QuestionType.SUBJECTIVE,
                question_text="Exam Questions (Review Scheme in Editor)",
                max_marks=100.0,
                model_answer="Refer to document.",
                criteria=[
                    GradingCriterion(
                        step_description="Overall correctness and methodology",
                        allocated_marks=100.0,
                        keywords_or_formula=[]
                    )
                ]
            )
        )

    tot_marks = sum(q.max_marks for q in questions)
    return ExamRubric(
        exam_title=title,
        subject="General",
        total_marks=tot_marks,
        instructions="Extracted via fallback parser. Please review questions and marks in the Rubric Review tab.",
        questions=questions
    )


def _structure_rubric_with_ai(
    raw_text: str,
    api_key: str,
    model_name: Optional[str] = None,
    workspace_id: Optional[str] = None,
    provider: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> ExamRubric:
    """
    Converts raw text into a structured ExamRubric object using Claude, Gemini, or Local Ollama.
    Incorporates token-budget prompts and JSON repair.
    """
    try:
        # Limit raw text if extraordinarily long
        trimmed_text = raw_text[:35000] if len(raw_text) > 35000 else raw_text

        prompt = (
            "You are an expert academic evaluator. Extract the grading rubric from the following document into structured JSON.\n"
            "Requirements:\n"
            "1. Extract the 'exam_title', 'subject', 'total_marks', and all questions.\n"
            "2. For each question:\n"
            "   - 'question_number': string (e.g. '1', '2a', '3')\n"
            "   - 'question_type': exactly one of ['mcq', 'subjective', 'numerical', 'mathematical']\n"
            "   - 'max_marks': number (float)\n"
            "   - 'model_answer': brief correct solution or expected answer\n"
            "   - 'criteria': list of 1-4 concise grading steps (step_description, allocated_marks, keywords_or_formula)\n"
            "3. Keep all descriptions brief and concise to stay within output limits.\n"
            "4. Make sure total_marks matches the sum of question max_marks.\n\n"
            f"Document Text:\n{trimmed_text}"
        )

        from core.ai_client import is_claude_key, is_local_provider
        if is_local_provider(provider, api_key):
            default_pref = "qwen2.5-vl:7b"
        elif is_claude_key(api_key, provider):
            default_pref = "claude-sonnet-5-5"
        else:
            default_pref = "gemini-2.5-flash"

        json_text = generate_content_with_fallback(
            api_key=api_key,
            prompt=prompt,
            response_schema=ExamRubric,
            preferred_model=model_name or default_pref,
            provider=provider,
            workspace_id=workspace_id,
            endpoint=endpoint,
        )

        try:
            return ExamRubric.model_validate_json(json_text)
        except Exception:
            repaired = repair_truncated_json(json_text, validator=ExamRubric.model_validate_json)
            return ExamRubric.model_validate_json(repaired)

    except Exception as e:
        _safe_log(f"[RUBRIC_PARSER] AI structuring encountered an error: {e}. Trying fallback parser...")
        try:
            return _build_fallback_rubric(raw_text)
        except Exception as fb_err:
            raise RuntimeError(f"Failed to structure rubric with AI: {e}")


def parse_rubric_document(
    file_bytes: bytes,
    filename: str,
    api_key: str,
    model_name: Optional[str] = None,
    workspace_id: Optional[str] = None,
    provider: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> ExamRubric:
    """
    Main entry point to parse a rubric document and return a structured ExamRubric.
    Delegates to PDF or DOCX extractors based on the file extension.
    """
    ext = os.path.splitext(filename.lower())[1]
    
    if ext == '.pdf':
        raw_text = _extract_text_from_pdf(file_bytes)
    elif ext == '.docx':
        raw_text = _extract_text_from_docx(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: {ext}. Only .pdf and .docx are supported.")

    if not raw_text.strip():
        raise ValueError("No text could be extracted from the document.")

    return _structure_rubric_with_ai(
        raw_text,
        api_key,
        model_name=model_name,
        workspace_id=workspace_id,
        provider=provider,
        endpoint=endpoint,
    )
