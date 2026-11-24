"""
Detailed Student Performance Reports Page.

Provides in-depth diagnostic reports for individual students:
- Score summary & letter grade
- Question-by-question breakdown with transcribed student text, model answers, AI feedback & deductions
- Single-click download for individual PDF Student Report Cards
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from core.report_generator import generate_student_report_card_pdf, get_letter_grade


def render_student_reports_page():
    """Renders the detailed student reports interface."""
    st.title("📑 Detailed Student Reports")

    session = st.session_state.get("grading_session")

    if not session or not session.student_results:
        st.warning("⚠️ No grading results available yet. Please upload answer sheets and complete grading first.")
        st.info("💡 You can run auto-grading on the **⚡ Grade** page.")
        return

    students = session.student_results
    total_students = len(students)

    st.markdown(
        f"Detailed question-by-question diagnostics and printable report cards for **{total_students}** student(s)."
    )

    st.divider()

    # ── 1. Select Student ──────────────────────────────────────────────
    student_labels = []
    for idx, s in enumerate(students):
        pct = s.percentage if s.percentage is not None else s.compute_percentage()
        grade = get_letter_grade(pct)
        name = s.student_name_or_id or f"Student {idx + 1}"
        student_labels.append(f"{name} — {s.total_marks_awarded:.1f}/{s.total_max_marks:.1f} ({pct:.1f}%, Grade {grade})")

    col_sel, col_dl1, col_dl2 = st.columns([2, 1, 1])
    with col_sel:
        selected_idx = st.selectbox(
            "Select Student to Inspect:",
            options=range(len(student_labels)),
            format_func=lambda i: student_labels[i],
            key="selected_student_report_idx",
        )

    student = students[selected_idx]
    student_name = student.student_name_or_id or f"Student {selected_idx + 1}"
    pct = student.percentage if student.percentage is not None else student.compute_percentage()
    grade = get_letter_grade(pct)
    is_pass = pct >= 50.0

    # Sort students by percentage to calculate rank
    sorted_students = sorted(
        students,
        key=lambda s: s.percentage if s.percentage is not None else s.compute_percentage(),
        reverse=True
    )
    rank = sorted_students.index(student) + 1

    # ── 2. Download Options ───────────────────────────────────────────
    pdf_bytes_map = st.session_state.get("pdf_bytes_map", {})
    matching_pdf = None
    for fn, b in pdf_bytes_map.items():
        if fn.replace(".pdf", "").replace("_", " ").lower() in student_name.lower():
            matching_pdf = b
            break
    if matching_pdf is None and selected_idx < len(pdf_bytes_map):
        matching_pdf = list(pdf_bytes_map.values())[selected_idx]

    with col_dl1:
        try:
            report_pdf_bytes = generate_student_report_card_pdf(student, session.exam_rubric)
            st.download_button(
                label="📑 Report Card (PDF)",
                data=report_pdf_bytes,
                file_name=f"{student_name.replace(' ', '_')}_Report_Card.pdf",
                mime="application/pdf",
                use_container_width=True,
                key=f"rep_card_dl_{selected_idx}",
            )
        except Exception as e:
            st.error(f"Error: {e}")

    with col_dl2:
        if matching_pdf:
            from core.pdf_annotator import annotate_graded_pdf
            try:
                ann_sheet_bytes = annotate_graded_pdf(matching_pdf, student)
                st.download_button(
                    label="📝 Graded Sheet (PDF)",
                    data=ann_sheet_bytes,
                    file_name=f"{student_name.replace(' ', '_')}_Graded_Sheet.pdf",
                    mime="application/pdf",
                    use_container_width=True,
                    key=f"ann_sheet_dl_{selected_idx}",
                )
            except Exception as e:
                st.error(f"Sheet error: {e}")
        else:
            st.caption("Sheet PDF not cached")

    # Bulk ZIP download option
    import io, zipfile
    from core.pdf_annotator import annotate_graded_pdf
    all_reports_zip = io.BytesIO()
    with zipfile.ZipFile(all_reports_zip, "w", zipfile.ZIP_DEFLATED) as zf:
        for idx_z, s_z in enumerate(students):
            s_clean = (s_z.student_name_or_id or f"Student_{idx_z+1}").replace(" ", "_")
            try:
                rc_bytes = generate_student_report_card_pdf(s_z, session.exam_rubric)
                zf.writestr(f"{s_clean}_Report_Card.pdf", rc_bytes)
            except Exception:
                pass
            m_bytes = None
            for fn, b in pdf_bytes_map.items():
                if fn.replace(".pdf", "").replace("_", " ").lower() in s_clean.lower():
                    m_bytes = b
                    break
            if m_bytes is None and idx_z < len(pdf_bytes_map):
                m_bytes = list(pdf_bytes_map.values())[idx_z]
            if m_bytes:
                try:
                    ann_b = annotate_graded_pdf(m_bytes, s_z)
                    zf.writestr(f"{s_clean}_Graded_Sheet.pdf", ann_b)
                except Exception:
                    pass

    st.download_button(
        label=f"📦 Download All Students' Sheet Reports (ZIP Bundle for {total_students} Students)",
        data=all_reports_zip.getvalue(),
        file_name="All_Student_Reports_Bundle.zip",
        mime="application/zip",
        use_container_width=True,
    )

    st.divider()

    # ── 3. Student Overview Card ──────────────────────────────────────
    st.markdown("### 🎓 Student Overview")
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("👤 Student", student_name)
    c2.metric("📝 Total Score", f"{student.total_marks_awarded:.1f} / {student.total_max_marks:.1f}")
    c3.metric("📊 Percentage", f"{pct:.1f}%")
    c4.metric("🏆 Letter Grade", grade)
    c5.metric("🏅 Class Rank", f"#{rank} of {total_students}")

    # Pass / Review Badges
    b_col1, b_col2 = st.columns([1, 4])
    with b_col1:
        if is_pass:
            st.success("✅ PASSED")
        else:
            st.error("⚠️ NEEDS IMPROVEMENT")

    flagged_qs = student.get_flagged_questions()
    if flagged_qs:
        st.warning(f"⚠️ **{len(flagged_qs)}** question(s) flagged for low confidence / unclear handwriting.")

    st.divider()

    # ── 4. Question Breakdown Diagnostics ─────────────────────────────
    st.markdown("### 🔍 Question-by-Question Diagnostic Report")

    # Build rubric lookup by question number
    rubric_lookup = {}
    if session.exam_rubric and session.exam_rubric.questions:
        for rq in session.exam_rubric.questions:
            rubric_lookup[str(rq.question_number)] = rq

    for q in student.results:
        is_full = q.marks_awarded == q.max_marks
        is_zero = q.marks_awarded == 0

        # Status badge
        if is_full:
            badge_icon = "🟢 Full Marks"
        elif is_zero:
            badge_icon = "🔴 Zero Marks"
        else:
            badge_icon = "🟡 Partial Credit"

        rubric_q = rubric_lookup.get(str(q.question_number))
        q_type = rubric_q.question_type.value.upper() if rubric_q else "SUBJECTIVE"

        with st.expander(
            f"**Q{q.question_number}** [{q_type}] — **{q.marks_awarded:.1f} / {q.max_marks:.1f} Marks**  ({badge_icon})",
            expanded=True
        ):
            # Metrics row
            qm1, qm2, qm3 = st.columns(3)
            qm1.metric("Score Awarded", f"{q.marks_awarded:.1f} / {q.max_marks:.1f}")
            qm2.metric("Evaluation Status", badge_icon)
            qm3.metric("AI Confidence", f"{int(q.confidence_score * 100)}%")

            st.markdown("---")

            # Student Answer vs Model Answer
            col_ans, col_model = st.columns(2)

            with col_ans:
                st.markdown("**✍️ Student's Transcribed Answer:**")
                clean_ans = q.transcription.strip() if q.transcription else "*No answer recorded on sheet.*"
                st.info(clean_ans)

            with col_model:
                st.markdown("**🎯 Expected / Model Answer (Rubric):**")
                model_text = rubric_q.model_answer if rubric_q and rubric_q.model_answer else "*Not specified in rubric.*"
                st.success(model_text)

            # AI Feedback & Deductions
            st.markdown("**💡 AI Step-by-Step Feedback:**")
            feedback_text = q.step_by_step_feedback if q.step_by_step_feedback else "Graded according to rubric criteria."
            st.markdown(f"> {feedback_text}")

            if q.deduction_reasons:
                st.markdown("**❌ Mark Deductions & Missing Points:**")
                for reason in q.deduction_reasons:
                    st.markdown(f"- 🔻 {reason}")

            # Criteria Breakdown if available
            if rubric_q and rubric_q.criteria:
                with st.expander("📋 Rubric Criteria Checklist", expanded=False):
                    for c_idx, c in enumerate(rubric_q.criteria, 1):
                        kw_info = f" (Keywords: {', '.join(c.keywords_or_formula)})" if c.keywords_or_formula else ""
                        st.markdown(f"**Step {c_idx}**: {c.step_description} — *{c.allocated_marks} marks*{kw_info}")

    st.divider()

    # ── 5. Comparison with Class Average ──────────────────────────────
    if total_students > 1:
        st.markdown("### 📊 Comparison with Class Averages")
        
        q_keys = []
        student_scores = []
        class_averages = []

        # Calculate class average per question
        for q in student.results:
            q_num = f"Q{q.question_number}"
            q_keys.append(q_num)
            student_scores.append(q.marks_awarded)

            # Calculate average for this question across all students
            all_scores_for_q = []
            for other_s in students:
                for oq in other_s.results:
                    if str(oq.question_number) == str(q.question_number):
                        all_scores_for_q.append(oq.marks_awarded)
            avg_for_q = sum(all_scores_for_q) / len(all_scores_for_q) if all_scores_for_q else 0.0
            class_averages.append(round(avg_for_q, 2))

        from core.theme_manager import get_theme
        t = get_theme()
        prim_col = "#e11d48"
        sec_col = "rgba(15, 23, 42, 0.45)"
        text_col = "#0f172a"
        grid_col = "rgba(0,0,0,0.06)"

        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=q_keys,
            y=student_scores,
            name=f"{student_name}",
            marker_color=prim_col,
            text=[f"{s:.1f}" for s in student_scores],
            textposition="outside"
        ))
        fig.add_trace(go.Bar(
            x=q_keys,
            y=class_averages,
            name="Class Average",
            marker_color=sec_col,
            opacity=0.65,
            text=[f"{a:.1f}" for a in class_averages],
            textposition="outside"
        ))
        fig.update_layout(
            barmode="group",
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Plus Jakarta Sans, Inter, sans-serif", color=text_col),
            xaxis=dict(gridcolor=grid_col),
            yaxis=dict(gridcolor=grid_col, title="Marks"),
            legend=dict(orientation="h", yanchor="bottom", y=-0.2, x=0.3)
        )
        st.plotly_chart(fig, use_container_width=True)
