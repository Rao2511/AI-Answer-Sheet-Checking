"""
SQLite Database Layer for upGrad School of Technology Answer Sheet Grader.
Persists:
- Exam sessions & metadata
- Uploaded files (Answer Sheet PDFs, Question Paper, Rubric documents) as binary BLOBs
- AI-parsed rubrics and question paper text
- Student evaluation results, question-wise scores, transcriptions, and feedback
"""
import io
import os
import json
import sqlite3
import datetime
from typing import List, Optional, Tuple, Dict, Any

from core.models import ExamRubric, GradingSession, StudentGradingResult, GradedQuestion


# ─── Database Path Configuration ─────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "grader.db")


def _ensure_data_dir():
    """Creates the data directory if it does not already exist."""
    if not os.path.exists(DATA_DIR):
        os.makedirs(DATA_DIR, exist_ok=True)


def get_connection() -> sqlite3.Connection:
    """Returns a connection to the SQLite database with WAL mode enabled."""
    _ensure_data_dir()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode = WAL;")
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db():
    """Initializes the database schema and indexes."""
    with get_connection() as conn:
        cursor = conn.cursor()

        # 1. Exam sessions
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS exam_sessions (
                session_id TEXT PRIMARY KEY,
                exam_title TEXT NOT NULL,
                subject TEXT,
                total_marks REAL DEFAULT 100.0,
                instructions TEXT,
                question_paper_filename TEXT,
                question_paper_text TEXT,
                rubric_filename TEXT,
                rubric_json TEXT,
                status TEXT DEFAULT 'uploaded',
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )

        # 2. Uploaded documents (BLOB storage so documents survive restarts)
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS uploaded_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                file_type TEXT NOT NULL,
                filename TEXT NOT NULL,
                file_size INTEGER NOT NULL,
                file_data BLOB NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES exam_sessions(session_id) ON DELETE CASCADE
            );
            """
        )

        # 3. Student grading evaluations
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS student_evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                student_name_or_id TEXT NOT NULL,
                total_marks_awarded REAL NOT NULL,
                total_max_marks REAL NOT NULL,
                percentage REAL NOT NULL,
                needs_review INTEGER NOT NULL DEFAULT 0,
                results_json TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES exam_sessions(session_id) ON DELETE CASCADE,
                UNIQUE(session_id, student_name_or_id)
            );
            """
        )

        # Indexes for fast search & retrieval
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_files_session ON uploaded_files(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evals_session ON student_evaluations(session_id);")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sessions_created ON exam_sessions(created_at DESC);")
        conn.commit()


# ─── File Adapter Class ──────────────────────────────────────────────────────

class StoredFile:
    """
    A file-like object returned from the database that mimics Streamlit's UploadedFile.
    Allows components expecting an UploadedFile (.getvalue(), .name, .size, .read()) to work seamlessly.
    """
    def __init__(self, name: str, data: bytes):
        self.name = name
        self.size = len(data)
        self._data = data
        self._io = io.BytesIO(data)

    def getvalue(self) -> bytes:
        return self._data

    def read(self, *args, **kwargs) -> bytes:
        return self._io.read(*args, **kwargs)

    def seek(self, *args, **kwargs):
        return self._io.seek(*args, **kwargs)


# ─── Session CRUD Operations ─────────────────────────────────────────────────

def save_or_update_session(
    session_id: str,
    exam_title: str = "Examination",
    subject: Optional[str] = None,
    total_marks: float = 100.0,
    instructions: Optional[str] = None,
    rubric: Optional[ExamRubric] = None,
    question_paper_filename: Optional[str] = None,
    question_paper_text: Optional[str] = None,
    rubric_filename: Optional[str] = None,
    status: str = "uploaded",
) -> str:
    """
    Inserts or updates an exam session record in the database.
    """
    init_db()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rubric_json = rubric.model_dump_json() if rubric else None

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO exam_sessions (
                session_id, exam_title, subject, total_marks, instructions,
                question_paper_filename, question_paper_text, rubric_filename,
                rubric_json, status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id) DO UPDATE SET
                exam_title = excluded.exam_title,
                subject = COALESCE(excluded.subject, exam_sessions.subject),
                total_marks = excluded.total_marks,
                instructions = COALESCE(excluded.instructions, exam_sessions.instructions),
                question_paper_filename = COALESCE(excluded.question_paper_filename, exam_sessions.question_paper_filename),
                question_paper_text = COALESCE(excluded.question_paper_text, exam_sessions.question_paper_text),
                rubric_filename = COALESCE(excluded.rubric_filename, exam_sessions.rubric_filename),
                rubric_json = COALESCE(excluded.rubric_json, exam_sessions.rubric_json),
                status = excluded.status,
                updated_at = excluded.updated_at;
            """,
            (
                session_id,
                exam_title,
                subject,
                total_marks,
                instructions,
                question_paper_filename,
                question_paper_text,
                rubric_filename,
                rubric_json,
                status,
                now,
                now,
            ),
        )
        conn.commit()
    return session_id


def save_file(session_id: str, file_type: str, filename: str, file_bytes: bytes) -> int:
    """
    Saves an uploaded file (answer sheet, question paper, or rubric) to the database.
    Replaces existing file of the same type and name within the session.
    """
    init_db()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    with get_connection() as conn:
        cursor = conn.cursor()
        # Delete existing duplicate if present
        cursor.execute(
            "DELETE FROM uploaded_files WHERE session_id = ? AND file_type = ? AND filename = ?",
            (session_id, file_type, filename),
        )
        cursor.execute(
            """
            INSERT INTO uploaded_files (session_id, file_type, filename, file_size, file_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?);
            """,
            (session_id, file_type, filename, len(file_bytes), file_bytes, now),
        )
        conn.commit()
        return cursor.lastrowid


def save_uploaded_batch(
    session_id: str,
    answer_sheets: Optional[List[Any]] = None,
    question_paper_file: Optional[Any] = None,
    rubric_file: Optional[Any] = None,
):
    """
    Convenience method to save all uploaded files for an exam session at once.
    """
    init_db()
    if answer_sheets:
        for pdf in answer_sheets:
            try:
                data = pdf.getvalue()
                save_file(session_id, "answer_sheet", pdf.name, data)
            except Exception:
                pass

    if question_paper_file:
        try:
            data = question_paper_file.getvalue()
            save_file(session_id, "question_paper", question_paper_file.name, data)
        except Exception:
            pass

    if rubric_file:
        try:
            data = rubric_file.getvalue()
            save_file(session_id, "rubric", rubric_file.name, data)
        except Exception:
            pass


def get_files_for_session(session_id: str, file_type: Optional[str] = None) -> List[StoredFile]:
    """
    Retrieves stored files for a session as StoredFile objects.
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        if file_type:
            cursor.execute(
                "SELECT filename, file_data FROM uploaded_files WHERE session_id = ? AND file_type = ? ORDER BY id ASC",
                (session_id, file_type),
            )
        else:
            cursor.execute(
                "SELECT filename, file_data FROM uploaded_files WHERE session_id = ? ORDER BY id ASC",
                (session_id,),
            )
        rows = cursor.fetchall()
        return [StoredFile(row["filename"], row["file_data"]) for row in rows]


# ─── Grading Results Persistence ─────────────────────────────────────────────

def save_student_evaluation(session_id: str, result: StudentGradingResult):
    """
    Saves or updates a single student's evaluation in the database.
    """
    init_db()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    student_name = result.student_name_or_id or "Unknown Student"
    needs_review = 1 if result.has_flags() else 0
    results_json = json.dumps([q.model_dump() for q in result.results])

    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO student_evaluations (
                session_id, student_name_or_id, total_marks_awarded, total_max_marks,
                percentage, needs_review, results_json, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(session_id, student_name_or_id) DO UPDATE SET
                total_marks_awarded = excluded.total_marks_awarded,
                total_max_marks = excluded.total_max_marks,
                percentage = excluded.percentage,
                needs_review = excluded.needs_review,
                results_json = excluded.results_json,
                updated_at = excluded.updated_at;
            """,
            (
                session_id,
                student_name,
                result.total_marks_awarded,
                result.total_max_marks,
                result.percentage or result.compute_percentage(),
                needs_review,
                results_json,
                now,
                now,
            ),
        )
        conn.commit()


def save_entire_grading_session(session: GradingSession):
    """
    Saves all student evaluations and updates the exam session status to 'graded'.
    """
    init_db()
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()

    # Update session status
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE exam_sessions SET
                status = 'graded',
                total_marks = ?,
                updated_at = ?
            WHERE session_id = ?;
            """,
            (session.exam_rubric.total_marks, now, session.session_id),
        )
        conn.commit()

    # Save each student
    for result in session.student_results:
        save_student_evaluation(session.session_id, result)


def update_question_override(
    session_id: str,
    student_name_or_id: str,
    question_number: str,
    new_marks: float,
    confidence: float = 1.0,
):
    """
    Updates a specific question score after manual review.
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT results_json, total_max_marks FROM student_evaluations WHERE session_id = ? AND student_name_or_id = ?",
            (session_id, student_name_or_id),
        )
        row = cursor.fetchone()
        if not row:
            return

        questions_list = json.loads(row["results_json"])
        total_max = row["total_max_marks"]

        for q in questions_list:
            if str(q.get("question_number")) == str(question_number):
                q["marks_awarded"] = new_marks
                q["confidence_score"] = confidence

        total_awarded = sum(float(q.get("marks_awarded", 0)) for q in questions_list)
        pct = round((total_awarded / total_max * 100), 1) if total_max > 0 else 0.0
        flags = any(float(q.get("confidence_score", 1.0)) < 0.85 for q in questions_list)

        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute(
            """
            UPDATE student_evaluations SET
                results_json = ?,
                total_marks_awarded = ?,
                percentage = ?,
                needs_review = ?,
                updated_at = ?
            WHERE session_id = ? AND student_name_or_id = ?;
            """,
            (
                json.dumps(questions_list),
                total_awarded,
                pct,
                1 if flags else 0,
                now,
                session_id,
                student_name_or_id,
            ),
        )
        conn.commit()


# ─── Load & List Sessions ───────────────────────────────────────────────────

def list_all_sessions() -> List[Dict[str, Any]]:
    """
    Lists all saved exam sessions ordered by latest first, including student counts and averages.
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT 
                s.session_id,
                s.exam_title,
                s.subject,
                s.total_marks,
                s.status,
                s.created_at,
                s.updated_at,
                s.question_paper_filename,
                s.rubric_filename,
                COUNT(e.id) AS student_count,
                AVG(e.percentage) AS class_average,
                SUM(CASE WHEN e.needs_review = 1 THEN 1 ELSE 0 END) AS review_count,
                (SELECT COUNT(*) FROM uploaded_files f WHERE f.session_id = s.session_id AND f.file_type = 'answer_sheet') AS answer_sheet_count
            FROM exam_sessions s
            LEFT JOIN student_evaluations e ON s.session_id = e.session_id
            GROUP BY s.session_id
            ORDER BY s.updated_at DESC;
            """
        )
        rows = cursor.fetchall()
        sessions = []
        for r in rows:
            sessions.append({
                "session_id": r["session_id"],
                "exam_title": r["exam_title"],
                "subject": r["subject"] or "General",
                "total_marks": r["total_marks"],
                "status": r["status"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "question_paper_filename": r["question_paper_filename"],
                "rubric_filename": r["rubric_filename"],
                "student_count": r["student_count"],
                "class_average": round(r["class_average"], 1) if r["class_average"] is not None else None,
                "review_count": r["review_count"] or 0,
                "answer_sheet_count": r["answer_sheet_count"] or 0,
            })
        return sessions


def load_full_session(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Loads all data for a specific session:
    - Session metadata & ExamRubric
    - GradingSession object (with all student results)
    - Uploaded files (StoredFile objects)
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM exam_sessions WHERE session_id = ?", (session_id,))
        session_row = cursor.fetchone()
        if not session_row:
            return None

        # Reconstruct ExamRubric
        rubric = None
        if session_row["rubric_json"]:
            try:
                rubric = ExamRubric.model_validate_json(session_row["rubric_json"])
            except Exception:
                pass

        if not rubric:
            rubric = ExamRubric(
                exam_title=session_row["exam_title"],
                subject=session_row["subject"],
                total_marks=session_row["total_marks"],
                instructions=session_row["instructions"],
                questions=[],
                question_paper_text=session_row["question_paper_text"],
            )

        # Retrieve student evaluations
        cursor.execute(
            "SELECT * FROM student_evaluations WHERE session_id = ? ORDER BY student_name_or_id ASC",
            (session_id,),
        )
        eval_rows = cursor.fetchall()
        student_results: List[StudentGradingResult] = []

        for row in eval_rows:
            try:
                raw_qs = json.loads(row["results_json"])
                questions = [GradedQuestion.model_validate(q) for q in raw_qs]
                res = StudentGradingResult(
                    student_name_or_id=row["student_name_or_id"],
                    total_marks_awarded=row["total_marks_awarded"],
                    total_max_marks=row["total_max_marks"],
                    percentage=row["percentage"],
                    results=questions,
                )
                student_results.append(res)
            except Exception:
                pass

        # Construct GradingSession
        grading_session = GradingSession(
            session_id=session_id,
            exam_rubric=rubric,
            student_results=student_results,
            total_students=len(student_results),
            students_needing_review=sum(1 for s in student_results if s.has_flags()),
        )

        # Retrieve files
        answer_sheets = get_files_for_session(session_id, "answer_sheet")
        qp_files = get_files_for_session(session_id, "question_paper")
        rubric_files = get_files_for_session(session_id, "rubric")

        return {
            "session_id": session_id,
            "exam_title": session_row["exam_title"],
            "subject": session_row["subject"],
            "total_marks": session_row["total_marks"],
            "instructions": session_row["instructions"],
            "question_paper_text": session_row["question_paper_text"],
            "rubric": rubric,
            "grading_session": grading_session if student_results else None,
            "answer_sheets": answer_sheets,
            "question_paper_file": qp_files[0] if qp_files else None,
            "rubric_file": rubric_files[0] if rubric_files else None,
        }


def delete_session(session_id: str) -> bool:
    """
    Deletes an entire exam session and all associated files and student grades.
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM uploaded_files WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM student_evaluations WHERE session_id = ?", (session_id,))
        cursor.execute("DELETE FROM exam_sessions WHERE session_id = ?", (session_id,))
        conn.commit()
        return True


def get_database_stats() -> Dict[str, Any]:
    """
    Returns high-level statistics about the stored database for the sidebar indicator.
    """
    init_db()
    with get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM exam_sessions")
        total_sessions = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) FROM student_evaluations")
        total_evaluations = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*), COALESCE(SUM(file_size), 0) FROM uploaded_files")
        file_count, total_bytes = cursor.fetchone()

        db_size_mb = 0.0
        if os.path.exists(DB_PATH):
            db_size_mb = os.path.getsize(DB_PATH) / (1024 * 1024)

        return {
            "total_sessions": total_sessions,
            "total_evaluations": total_evaluations,
            "total_files": file_count,
            "storage_mb": round(db_size_mb + (total_bytes / (1024 * 1024)), 2),
        }
