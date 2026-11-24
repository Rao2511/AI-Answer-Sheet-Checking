"""
Manual review interface for flagged answers.
"""
import streamlit as st

def render_review_page():
    """Renders the manual review interface for low-confidence answers."""
    st.title("🔍 Manual Review")
    
    session = st.session_state.get('grading_session')
    
    if not session:
        st.warning("No grading session found. Please run the grading process first.")
        return
        
    st.markdown("Review answers flagged by the AI for low confidence.")
    
    # Mock data check
    if not session.student_results:
        st.info("No student results available. (Mock grading might be active)")
        return
        
    students_with_flags = [s for s in session.student_results if s.has_flags()]
    
    if not students_with_flags:
        st.success("🎉 No answers require manual review! All answers were graded with high confidence.")
        return
        
    st.markdown(f"**{len(students_with_flags)}** students require review.")
    
    for student in students_with_flags:
        st.subheader(f"Student: {student.student_name_or_id or 'Unknown'}")
        
        flagged_qs = student.get_flagged_questions()
        for q in flagged_qs:
            # Color code confidence
            color = "🔴" if q.confidence_score < 0.5 else "🟠"
            
            with st.expander(f"{color} Q{q.question_number} | Score: {q.marks_awarded}/{q.max_marks} | Confidence: {q.confidence_score:.2f}"):
                
                st.markdown("**AI Transcription:**")
                st.info(q.transcription)
                
                st.markdown("**AI Feedback:**")
                st.write(q.step_by_step_feedback)
                
                col1, col2 = st.columns([1, 2])
                with col1:
                    new_score = st.number_input(
                        "Override Score", 
                        min_value=0.0, 
                        max_value=float(q.max_marks), 
                        value=float(q.marks_awarded),
                        key=f"override_{student.student_name_or_id}_{q.question_number}"
                    )
                with col2:
                    st.write("") # spacing
                    st.write("")
                    if st.button("✅ Approve", key=f"approve_{student.student_name_or_id}_{q.question_number}"):
                        q.marks_awarded = new_score
                        q.confidence_score = 1.0 # Resolve flag
                        student.total_marks_awarded = sum(x.marks_awarded for x in student.results)
                        student.compute_percentage()

                        # Persist override to database
                        from core.database import update_question_override
                        update_question_override(
                            session_id=session.session_id,
                            student_name_or_id=student.student_name_or_id,
                            question_number=str(q.question_number),
                            new_marks=new_score,
                            confidence=1.0,
                        )
                        st.success("Saved & Updated in Database!")
                        st.rerun()
                        
    if st.button("Approve All Remaining", type="primary"):
        # Logic to approve all
        for student in students_with_flags:
            for q in student.get_flagged_questions():
                q.confidence_score = 1.0
            student.total_marks_awarded = sum(x.marks_awarded for x in student.results)
            student.compute_percentage()

        # Persist all updates to database
        from core.database import save_entire_grading_session
        save_entire_grading_session(session)
        st.success("All answers approved and saved to database!")
        st.rerun()
