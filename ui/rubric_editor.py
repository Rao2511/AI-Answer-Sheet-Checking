"""
Rubric editor interface to review and modify parsed rubrics.
"""
import streamlit as st
from core.models import ExamRubric, QuestionRubric, QuestionType, GradingCriterion

def render_rubric_editor():
    """Renders the parsed rubric for manual review and editing."""
    st.title("📋 Rubric Review & Editor")
    
    if not st.session_state.get('parsed_rubric'):
        st.warning("No rubric parsed yet. Please go to the Upload page and parse a rubric.")
        return
        
    st.markdown("Review and adjust the AI-parsed rubric before grading.")
    
    # Normally we would use st.session_state['parsed_rubric'] which is an ExamRubric object.
    # For demonstration/scaffolding, let's assume we have it or mock it.
    rubric = st.session_state['parsed_rubric']
    
    # Scaffold if it's just the boolean Mock from upload_page
    if isinstance(rubric, bool):
        rubric = ExamRubric(
            exam_title="Midterm Examination",
            subject="Physics",
            total_marks=100.0,
            instructions="Show all working.",
            questions=[
                QuestionRubric(
                    question_number="1",
                    question_type=QuestionType.SUBJECTIVE,
                    max_marks=10.0,
                    model_answer="Velocity = distance / time",
                    criteria=[GradingCriterion(step_description="Formula", allocated_marks=5.0)]
                )
            ]
        )
        st.session_state['parsed_rubric'] = rubric

    with st.container():
        st.subheader("Exam Details")
        col1, col2, col3 = st.columns(3)
        with col1:
            exam_title = st.text_input("Exam Title", value=rubric.exam_title)
        with col2:
            subject = st.text_input("Subject", value=rubric.subject or "")
        q_sum = sum(float(q.max_marks) for q in rubric.questions)
        with col3:
            total_marks = st.number_input(
                "Official Exam Total Marks",
                min_value=1.0,
                max_value=2000.0,
                value=float(rubric.total_marks if (rubric.total_marks and rubric.total_marks > 0) else q_sum),
                step=1.0,
                help=f"Detected question sum is {q_sum:.1f}. Set official total (e.g. 100) if students only answer a subset."
            )
            st.caption(f"Detected questions sum: **{q_sum:.1f}** marks")
            
        instructions = st.text_area("General Instructions", value=rubric.instructions or "")

        if getattr(rubric, "question_paper_text", None):
            with st.expander("📑 View Official Question Paper Reference", expanded=False):
                st.text_area(
                    "Official Question Paper Text",
                    value=rubric.question_paper_text,
                    height=200,
                    disabled=True,
                    help="Extracted question paper text used by the AI evaluator."
                )

    st.divider()
    st.subheader("Questions")
    
    updated_questions = []
    
    for i, q in enumerate(rubric.questions):
        with st.expander(f"Question {q.question_number} - {q.max_marks} marks", expanded=(i==0)):
            q_col1, q_col2, q_col3 = st.columns([1, 1, 1])
            with q_col1:
                q_num = st.text_input(f"Q. Number", value=q.question_number, key=f"qnum_{i}")
            with q_col2:
                q_type = st.selectbox(f"Type", [e.value for e in QuestionType], index=[e.value for e in QuestionType].index(q.question_type.value), key=f"qtype_{i}")
            with q_col3:
                q_marks = st.number_input(f"Max Marks", value=float(q.max_marks), key=f"qmarks_{i}")
                
            q_text = st.text_area("Question Text (optional)", value=q.question_text or "", key=f"qtext_{i}")
            model_ans = st.text_area("Model Answer", value=q.model_answer, key=f"mans_{i}")
            
            st.markdown("**Grading Criteria**")
            updated_criteria = []
            for j, c in enumerate(q.criteria):
                c_col1, c_col2 = st.columns([3, 1])
                with c_col1:
                    desc = st.text_input("Criterion Description", value=c.step_description, key=f"cdesc_{i}_{j}")
                with c_col2:
                    marks = st.number_input("Marks", value=float(c.allocated_marks), key=f"cmarks_{i}_{j}")
                updated_criteria.append(GradingCriterion(step_description=desc, allocated_marks=marks))
                
            updated_questions.append(QuestionRubric(
                question_number=q_num,
                question_type=QuestionType(q_type),
                question_text=q_text if q_text else None,
                max_marks=q_marks,
                model_answer=model_ans,
                criteria=updated_criteria
            ))
            
    if st.button("💾 Save Changes", type="primary"):
        rubric.exam_title = exam_title
        rubric.subject = subject
        rubric.total_marks = total_marks
        rubric.instructions = instructions if instructions else None
        rubric.questions = updated_questions
        st.session_state['parsed_rubric'] = rubric

        # Save changes to database
        from core.database import save_or_update_session
        current_sid = st.session_state.get("session_id", "default")
        save_or_update_session(
            session_id=current_sid,
            exam_title=exam_title,
            subject=subject,
            total_marks=total_marks,
            instructions=instructions if instructions else None,
            rubric=rubric,
            question_paper_text=getattr(rubric, "question_paper_text", None),
            status="parsed",
        )
        st.success("✅ Rubric updated and saved to database!")
