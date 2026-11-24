import json
import time
from typing import List, Optional
from google import genai
from google.genai import types

from core.models import ExamRubric, StudentGradingResult, GradedQuestion
from core.ai_client import generate_content_with_fallback


def _build_grading_prompt(rubric: ExamRubric) -> str:
    """
    Builds the detailed system/grading prompt with specialized Handwriting Text Recognition (HTR) directives.
    """
    rubric_json = rubric.model_dump_json(indent=2)
    
    prompt = (
        "You are an expert AI Automated Handwriting Evaluator and Academic Grader.\n"
        "The attached images show a REAL STUDENT'S HANDWRITTEN EXAM ANSWER SHEET.\n\n"
        "### SPECIALIZED HANDWRITING RECOGNITION (HTR) DIRECTIVES:\n"
        "1. **Read Imperfect, Cursive, and Slanted Handwriting**: Student handwriting is written in blue/black pen or pencil. "
        "It may be cursive, connected, casual, faint, or slightly messy. Decipher every word and stroke carefully using word shapes, stroke trajectories, and context.\n"
        "2. **Search All Regions of Every Page**: Students write answer markers in varied styles: 'Q1', 'Ans 1', '1.', '(a)', 'i)', 'Question 1', "
        "circled numbers, or in left/top margins. Search thoroughly across all attached page images to locate every question attempt.\n"
        "3. **Transcribe Verbatim**: In the `transcription` field of each GradedQuestion, transcribe the exact words, sentences, or equations the student wrote. "
        "Do not leave transcription empty if student handwriting is present.\n"
        "4. **Math, Numerical & Scientific Work**: Inspect all intermediate steps, algebraic working, formulas, fractions, and units. "
        "Award partial credit generously for correct working and principles even if final calculations have arithmetic slips.\n"
        "5. **MCQs**: Identify circled, ticked, underlined, or written option letters (A, B, C, D).\n"
        "6. **Bounding Box**: For each answer, provide its 2D bounding box `box_2d` in `[ymin, xmin, ymax, xmax]` normalized to 0-1000 scale and specify the correct `page_number` (1-indexed).\n"
        "7. **Fair Grading & Partial Credit**: Award marks for every rubric criterion demonstrated by the student's handwritten response.\n\n"
        "### Official Exam Rubric (JSON):\n"
        f"{rubric_json}\n"
    )
    return prompt


def _chunk_pages(pages: List[bytes], chunk_size: int = 5) -> List[List[bytes]]:
    """
    Splits page images into chunks. Defaults to 5 pages per chunk so complete multi-page exams are evaluated together.
    """
    return [pages[i:i + chunk_size] for i in range(0, len(pages), chunk_size)]


def _merge_chunk_results(
    chunk_results: List[StudentGradingResult],
    rubric: Optional[ExamRubric] = None,
    exam_total_marks: Optional[float] = None,
) -> StudentGradingResult:
    """
    Merges results from multiple grading chunks into a single StudentGradingResult.
    Sets total_max_marks to the official exam total marks if specified or provided in rubric.
    """
    if not chunk_results:
        return StudentGradingResult(
            total_marks_awarded=0.0,
            total_max_marks=0.0,
            results=[]
        )

    # Initialize the merged result with the first chunk
    merged_result = chunk_results[0]
    
    # Merge subsequent chunks
    for result in chunk_results[1:]:
        if not merged_result.student_name_or_id and result.student_name_or_id:
            merged_result.student_name_or_id = result.student_name_or_id
            
        merged_result.results.extend(result.results)
        
    # Deduplicate questions if any (take the one with highest confidence)
    unique_results = {}
    for q in merged_result.results:
        if q.question_number not in unique_results or q.confidence_score > unique_results[q.question_number].confidence_score:
            unique_results[q.question_number] = q
    
    merged_result.results = list(unique_results.values())
    
    # Recalculate awarded total
    merged_result.total_marks_awarded = sum(q.marks_awarded for q in merged_result.results)
    
    # Set exam maximum marks:
    # 1. Custom explicit exam_total_marks if provided (> 0)
    # 2. rubric.total_marks if provided (> 0)
    # 3. Sum of all individual questions
    if exam_total_marks is not None and float(exam_total_marks) > 0:
        merged_result.total_max_marks = float(exam_total_marks)
    elif rubric is not None and hasattr(rubric, "total_marks") and float(rubric.total_marks) > 0:
        merged_result.total_max_marks = float(rubric.total_marks)
    else:
        merged_result.total_max_marks = sum(q.max_marks for q in merged_result.results)

    merged_result.compute_percentage()
    return merged_result


def grade_student_exam(
    page_images: List[bytes],
    rubric: ExamRubric,
    api_key: str,
    model_name: Optional[str] = None,
    workspace_id: Optional[str] = None,
    exam_total_marks: Optional[float] = None,
    provider: Optional[str] = None,
    endpoint: Optional[str] = None,
) -> StudentGradingResult:
    """
    Main grading function. Sends page images and rubric to Claude, Gemini, or Local Ollama for grading.
    Supports multi-provider fallback and exponential backoff retry.
    """
    try:
        prompt = _build_grading_prompt(rubric)
        
        # Evaluate up to 5 pages together for full multi-page exam context
        chunks = _chunk_pages(page_images, chunk_size=5)
        chunk_results = []
        
        for idx, chunk in enumerate(chunks):
            if idx > 0:
                time.sleep(1.0)  # Gentle pacing between chunks

            json_text = generate_content_with_fallback(
                api_key=api_key,
                prompt=prompt,
                response_schema=StudentGradingResult,
                images=chunk,
                preferred_model=model_name,
                provider=provider,
                workspace_id=workspace_id,
                endpoint=endpoint,
            )
            
            try:
                chunk_result = StudentGradingResult.model_validate_json(json_text)
            except Exception:
                from core.ai_client import repair_truncated_json
                repaired = repair_truncated_json(json_text, validator=StudentGradingResult.model_validate_json)
                chunk_result = StudentGradingResult.model_validate_json(repaired)
            chunk_results.append(chunk_result)
                
        return _merge_chunk_results(chunk_results, rubric=rubric, exam_total_marks=exam_total_marks)
        
    except Exception as e:
        raise RuntimeError(f"Error grading student exam: {e}")
