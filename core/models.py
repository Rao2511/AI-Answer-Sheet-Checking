"""
Pydantic data models for the Answer Sheet Auto-Grading System.

Defines structured schemas for:
- Exam rubrics (questions, criteria, marks)
- Grading results (transcriptions, scores, bounding boxes)
- Student results aggregation
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


# ─── Enums ────────────────────────────────────────────────────────────────────

class QuestionType(str, Enum):
    """Type of question on the answer sheet."""
    MCQ = "mcq"
    SUBJECTIVE = "subjective"
    NUMERICAL = "numerical"
    MATHEMATICAL = "mathematical"


class ReviewStatus(str, Enum):
    """Review status for a graded answer."""
    AUTO_APPROVED = "auto_approved"
    NEEDS_REVIEW = "needs_review"
    MANUALLY_REVIEWED = "manually_reviewed"


# ─── Rubric Models ───────────────────────────────────────────────────────────

class GradingCriterion(BaseModel):
    """A single grading criterion within a question's rubric."""
    step_description: str = Field(
        description="Description of the expected step, concept, or keyword"
    )
    allocated_marks: float = Field(
        description="Marks allocated for this specific criterion/step"
    )
    keywords_or_formula: Optional[List[str]] = Field(
        default=None,
        description="Key terms, formulas, or phrases that indicate this criterion is met"
    )


class QuestionRubric(BaseModel):
    """Rubric definition for a single question."""
    question_number: str = Field(
        description="Question identifier (e.g., '1', '2a', '3.ii')"
    )
    question_type: QuestionType = Field(
        description="Type of question: mcq, subjective, numerical, or mathematical"
    )
    question_text: Optional[str] = Field(
        default=None,
        description="The question text itself, if available"
    )
    max_marks: float = Field(
        description="Maximum marks for this question"
    )
    model_answer: str = Field(
        description="The expected correct answer or model solution"
    )
    criteria: List[GradingCriterion] = Field(
        default_factory=list,
        description="Detailed grading criteria for step-by-step marking"
    )


class ExamRubric(BaseModel):
    """Complete rubric for an entire exam."""
    exam_title: str = Field(
        description="Title or name of the examination"
    )
    subject: Optional[str] = Field(
        default=None,
        description="Subject name (e.g., 'Physics', 'Mathematics')"
    )
    total_marks: float = Field(
        description="Total maximum marks for the entire exam"
    )
    instructions: Optional[str] = Field(
        default=None,
        description="Any special grading instructions"
    )
    questions: List[QuestionRubric] = Field(
        description="List of all question rubrics"
    )


# ─── Grading Result Models ───────────────────────────────────────────────────

class GradedQuestion(BaseModel):
    """Result of grading a single question for a student."""
    question_number: str = Field(
        description="Question identifier matching the rubric"
    )
    transcription: str = Field(
        description="AI-transcribed text of the student's handwritten answer"
    )
    marks_awarded: float = Field(
        description="Marks awarded for this answer"
    )
    max_marks: float = Field(
        description="Maximum possible marks (from rubric)"
    )
    is_correct: bool = Field(
        description="Whether the answer is fully correct"
    )
    step_by_step_feedback: str = Field(
        description="Detailed feedback explaining marks awarded/deducted"
    )
    deduction_reasons: List[str] = Field(
        default_factory=list,
        description="Specific reasons for any mark deductions"
    )
    confidence_score: float = Field(
        ge=0.0, le=1.0,
        description="AI confidence in the grading (0.0 to 1.0). Below 0.85 = flag for review"
    )
    box_2d: List[int] = Field(
        description="Bounding box [ymin, xmin, ymax, xmax] normalized to 0-1000 scale"
    )
    page_number: int = Field(
        description="Page number where this answer appears (1-indexed)"
    )


class StudentGradingResult(BaseModel):
    """Complete grading result for a single student's answer sheet."""
    student_name_or_id: Optional[str] = Field(
        default=None,
        description="Student's name or roll number (extracted from sheet or filename)"
    )
    total_marks_awarded: float = Field(
        description="Sum of all marks awarded"
    )
    total_max_marks: float = Field(
        description="Sum of all max marks"
    )
    percentage: Optional[float] = Field(
        default=None,
        description="Percentage score"
    )
    results: List[GradedQuestion] = Field(
        description="Per-question grading results"
    )

    def compute_percentage(self) -> float:
        """Calculate and set percentage."""
        if self.total_max_marks > 0:
            self.percentage = round(
                (self.total_marks_awarded / self.total_max_marks) * 100, 1
            )
        else:
            self.percentage = 0.0
        return self.percentage

    def get_flagged_questions(self) -> List[GradedQuestion]:
        """Get questions that need manual review (confidence < 0.85)."""
        return [q for q in self.results if q.confidence_score < 0.85]

    def has_flags(self) -> bool:
        """Check if any questions need manual review."""
        return len(self.get_flagged_questions()) > 0


# ─── Page Data Models ────────────────────────────────────────────────────────

class PageData(BaseModel):
    """Rendered page data from a PDF."""
    page_number: int = Field(description="1-indexed page number")
    width_pts: float = Field(description="Page width in PDF points")
    height_pts: float = Field(description="Page height in PDF points")
    image_bytes: bytes = Field(description="PNG image bytes of the rendered page")

    class Config:
        # Allow bytes field
        arbitrary_types_allowed = True


# ─── Session / Batch Models ──────────────────────────────────────────────────

class GradingSession(BaseModel):
    """Represents a complete grading session with multiple students."""
    session_id: str = Field(description="Unique session identifier")
    exam_rubric: ExamRubric = Field(description="The rubric used for grading")
    student_results: List[StudentGradingResult] = Field(
        default_factory=list,
        description="All student grading results"
    )
    total_students: int = Field(default=0, description="Total number of students graded")
    students_needing_review: int = Field(
        default=0, description="Count of students with flagged answers"
    )

    def add_result(self, result: StudentGradingResult):
        """Add a student result and update counts."""
        result.compute_percentage()
        self.student_results.append(result)
        self.total_students = len(self.student_results)
        self.students_needing_review = sum(
            1 for r in self.student_results if r.has_flags()
        )

    def get_class_average(self) -> float:
        """Calculate the class average percentage."""
        if not self.student_results:
            return 0.0
        percentages = [r.percentage or 0.0 for r in self.student_results]
        return round(sum(percentages) / len(percentages), 1)
