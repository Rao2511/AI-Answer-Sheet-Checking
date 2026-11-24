"""
Grading execution interface — connects to the actual Gemini grading engine.
"""
import streamlit as st
import uuid
from core.models import GradingSession
from core.pdf_processor import render_pdf_pages
from core.grading_engine import grade_student_exam


def render_grading_page():
    """Renders the grading execution interface with real AI grading."""
    st.title("⚡ Execute Auto-Grading")

    pdfs = st.session_state.get("uploaded_pdfs", [])
    rubric = st.session_state.get("parsed_rubric")
    api_key = st.session_state.get("api_key", "")
    provider = st.session_state.get("ai_provider", "Anthropic Claude")
    endpoint = st.session_state.get("ollama_endpoint", "http://localhost:11434")
    is_local = "Local" in provider or "Ollama" in provider or api_key == "local"

    if not pdfs:
        st.warning("📄 No answer sheets uploaded. Go to **Upload** page first.")
        return
    if not rubric or not hasattr(rubric, "questions"):
        st.warning("📋 No rubric parsed. Go to **Upload** page and parse your rubric first.")
        return
    if not is_local and not api_key:
        st.warning("🔑 Please enter your API Key in the sidebar.")
        return

    ws_id = st.session_state.get("workspace_id", "")
    num_students = len(pdfs)
    num_questions = len(rubric.questions)
    questions_sum = sum(float(q.max_marks) for q in rubric.questions)
    current_total = float(rubric.total_marks if (rubric.total_marks and rubric.total_marks > 0) else questions_sum)

    from core.ai_client import is_claude_key, is_local_provider
    if is_local:
        default_m = "qwen2.5-vl:7b"
    elif is_claude_key(api_key, provider):
        default_m = "claude-sonnet-5-5"
    else:
        default_m = "gemini-2.5-flash"
    selected_model_name = st.session_state.get("selected_model") or default_m

    # Summary metrics
    st.markdown("### 📊 Grading Summary")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("📄 Students", num_students)
    col2.metric("❓ Questions", num_questions)
    col3.metric("📝 Total Marks", f"{current_total:.1f}")
    col4.metric("📑 Question Paper", "Active ✓" if getattr(rubric, "question_paper_text", None) else "Optional")
    col5.metric("🤖 AI Model", selected_model_name)

    if getattr(rubric, "question_paper_text", None):
        st.info("📑 **Official Question Paper Active**: AI evaluator will cross-verify student answers directly against the original question paper prompts, options, and constraints.")

    st.markdown("#### 🎯 Exam Total Marks (Scored Out Of)")
    col_tm1, col_tm2 = st.columns([2, 1])
    with col_tm1:
        st.markdown(
            f"**Detected questions sum:** `{questions_sum:.1f}` marks across `{num_questions}` questions.<br>"
            "If this exam has optional/choice questions (e.g. questions sum to 200 marks, but the exam is out of 100 marks), "
            "specify the **Official Exam Total Marks** here:",
            unsafe_allow_html=True,
        )
    with col_tm2:
        configured_total = st.number_input(
            "Official Exam Total Marks",
            min_value=1.0,
            max_value=2000.0,
            value=float(current_total),
            step=1.0,
            key="input_exam_total_marks",
        )
        if configured_total != rubric.total_marks:
            rubric.total_marks = configured_total
            st.session_state["parsed_rubric"].total_marks = configured_total

    # Instant recalculation if a grading session is already loaded with a different total
    existing_session = st.session_state.get("grading_session")
    if existing_session and existing_session.student_results:
        first_student = existing_session.student_results[0]
        if abs(first_student.total_max_marks - configured_total) > 0.01:
            st.info(
                f"💡 Current graded results are scored out of **{first_student.total_max_marks}**. "
                f"Click below to instantly recalculate all student scores and percentages out of **{configured_total:.1f}** without re-grading!"
            )
            if st.button(f"🔄 Recalculate Existing Scores out of {configured_total:.1f} Marks", type="secondary", use_container_width=True):
                for s in existing_session.student_results:
                    s.total_max_marks = float(configured_total)
                    s.compute_percentage()
                existing_session.exam_rubric.total_marks = float(configured_total)
                st.session_state["grading_session"] = existing_session
                st.success(f"✅ Recalculated all student scores out of {configured_total:.1f} marks!")
                st.rerun()

    st.divider()

    # Show per-student file listing
    with st.expander("📁 Answer sheets to be graded"):
        for i, pdf in enumerate(pdfs, 1):
            st.markdown(f"**{i}.** {pdf.name} ({pdf.size / 1024:.1f} KB)")

    st.divider()

    # Grade button
    if st.button("🚀 Start Grading", type="primary", use_container_width=True):
        # Update rubric total
        rubric.total_marks = float(configured_total)
        # Initialize a fresh grading session
        current_sid = st.session_state.get("session_id") or str(uuid.uuid4())[:8]
        st.session_state["session_id"] = current_sid
        session = GradingSession(
            session_id=current_sid,
            exam_rubric=rubric,
        )

        progress_bar = st.progress(0, text="Preparing...")
        status_container = st.container()

        errors = []

        from core.database import save_student_evaluation, save_entire_grading_session

        for i, pdf in enumerate(pdfs):
            student_label = pdf.name.replace(".pdf", "").replace("_", " ")
            progress_text = f"Grading {i + 1}/{num_students}: **{student_label}**"
            progress_bar.progress((i) / num_students, text=progress_text)

            with status_container:
                status_msg = st.empty()
                status_msg.info(f"🔄 Processing **{student_label}**...")

            try:
                # Step 1: Render PDF pages with handwriting enhancement & user rotation
                pdf_bytes = pdf.getvalue()
                rot_offset = st.session_state.get(f"rot_offset_{pdf.name}", 0)
                pages = render_pdf_pages(
                    pdf_bytes,
                    dpi=180,
                    enhance_handwriting=True,
                    rotation_offset=rot_offset,
                )
                page_images = [p.image_bytes for p in pages]

                # Step 2: Grade with AI (Claude / Gemini / Local Ollama with retry and fallback)
                result = grade_student_exam(
                    page_images=page_images,
                    rubric=rubric,
                    api_key=api_key or "local",
                    model_name=selected_model_name,
                    workspace_id=ws_id,
                    exam_total_marks=configured_total,
                    provider=provider,
                    endpoint=endpoint,
                )

                # Set student name from filename if AI didn't detect one
                if not result.student_name_or_id:
                    result.student_name_or_id = student_label

                # Add to session & persist to database in real-time
                session.add_result(result)
                save_student_evaluation(current_sid, result)

                with status_container:
                    status_msg.success(
                        f"✅ **{student_label}** — "
                        f"{result.total_marks_awarded}/{result.total_max_marks} "
                        f"({result.percentage}%)"
                    )

            except Exception as e:
                error_msg = f"Error grading {student_label}: {str(e)}"
                errors.append(error_msg)
                with status_container:
                    status_msg.error(f"❌ {error_msg}")

        # Store session and results in state and database
        save_entire_grading_session(session)
        st.session_state["grading_session"] = session
        st.session_state["grading_errors"] = errors
        st.session_state["pdf_bytes_map"] = {
            pdf.name: pdf.getvalue() for pdf in pdfs
        }
        st.rerun()

    # ── Render Completed Grading Results & Download Student Sheet Reports ──
    session = st.session_state.get("grading_session")
    if session and session.student_results:
        st.divider()
        st.markdown("### 🎉 Grading Complete!")

        sum_col1, sum_col2, sum_col3, sum_col4 = st.columns(4)
        sum_col1.metric("✅ Graded", session.total_students)
        sum_col2.metric("⚠️ Need Review", session.students_needing_review)
        sum_col3.metric("📊 Class Average", f"{session.get_class_average()}%")
        errors = st.session_state.get("grading_errors", [])
        sum_col4.metric("❌ Errors", len(errors))

        if errors:
            with st.expander("⚠️ Errors encountered"):
                for err in errors:
                    st.error(err)

        st.markdown("#### ⚡ Quick Actions")
        qa_col1, qa_col2, qa_col3 = st.columns(3)
        with qa_col1:
            if st.button("📑 View Detailed Student Reports", use_container_width=True, type="primary"):
                st.session_state["current_page"] = "student_reports"
                st.rerun()
        with qa_col2:
            if st.button("📊 View Analytics Dashboard", use_container_width=True):
                st.session_state["current_page"] = "dashboard"
                st.rerun()
        with qa_col3:
            if st.button("📥 All Export & Downloads Hub", use_container_width=True):
                st.session_state["current_page"] = "downloads"
                st.rerun()

        # ── 📥 Dedicated Student Sheet Reports Download Section ────────────
        st.divider()
        st.markdown("### 📥 Download Student Sheet Reports")
        st.markdown("Download individual graded answer sheets and diagnostic evaluation reports:")

        import io
        import zipfile
        from core.pdf_annotator import annotate_graded_pdf
        from core.report_generator import generate_student_report_card_pdf

        pdf_bytes_map = st.session_state.get("pdf_bytes_map", {})

        # Bulk Download ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for idx, res in enumerate(session.student_results):
                s_name = res.student_name_or_id or f"Student_{idx + 1}"
                clean_name = s_name.replace(" ", "_").replace("/", "_")
                # Add Report Card PDF
                try:
                    rc_pdf = generate_student_report_card_pdf(res, session.exam_rubric)
                    zf.writestr(f"{clean_name}_Report_Card.pdf", rc_pdf)
                except Exception:
                    pass
                # Add Graded Answer Sheet PDF
                matching_pdf = None
                for fn, b in pdf_bytes_map.items():
                    if fn.replace(".pdf", "").replace("_", " ").lower() in s_name.lower():
                        matching_pdf = b
                        break
                if matching_pdf is None and idx < len(pdf_bytes_map):
                    matching_pdf = list(pdf_bytes_map.values())[idx]
                if matching_pdf:
                    try:
                        ann_pdf = annotate_graded_pdf(matching_pdf, res)
                        zf.writestr(f"{clean_name}_Graded_Sheet.pdf", ann_pdf)
                    except Exception:
                        pass

        col_zip, _ = st.columns([1, 1])
        with col_zip:
            st.download_button(
                label="📦 Download All Student Reports (ZIP Bundle)",
                data=zip_buffer.getvalue(),
                file_name="All_Students_Sheet_Reports.zip",
                mime="application/zip",
                use_container_width=True,
            )

        st.markdown("##### 📄 Individual Student Sheet Downloads:")
        for idx, res in enumerate(session.student_results):
            s_name = res.student_name_or_id or f"Student_{idx + 1}"
            pct = res.percentage if res.percentage is not None else res.compute_percentage()

            with st.container():
                st.markdown(
                    f"""
                    <div style="background:#ffffff; border:1px solid #e2e8f0; border-radius:8px; padding:10px 14px; margin-top:8px; margin-bottom:4px;">
                        <span style="font-weight:700; font-size:1.0rem; color:#0f172a;">👤 {s_name}</span>
                        <span style="margin-left:14px; font-weight:700; color:#e11d48; font-size:0.95rem;">
                            Score: {res.total_marks_awarded:.1f} / {res.total_max_marks:.1f} ({pct:.1f}%)
                        </span>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                btn_c1, btn_c2 = st.columns(2)

                # 1. Diagnostic Report Card PDF
                with btn_c1:
                    try:
                        rc_bytes = generate_student_report_card_pdf(res, session.exam_rubric)
                        st.download_button(
                            label=f"📑 Report Card ({s_name})",
                            data=rc_bytes,
                            file_name=f"{s_name.replace(' ', '_')}_Report_Card.pdf",
                            mime="application/pdf",
                            key=f"dl_grade_rc_{idx}",
                            use_container_width=True,
                        )
                    except Exception as e:
                        st.error(f"Report card error: {e}")

                # 2. Graded Answer Sheet PDF
                with btn_c2:
                    matching_pdf = None
                    for fn, b in pdf_bytes_map.items():
                        if fn.replace(".pdf", "").replace("_", " ").lower() in s_name.lower():
                            matching_pdf = b
                            break
                    if matching_pdf is None and idx < len(pdf_bytes_map):
                        matching_pdf = list(pdf_bytes_map.values())[idx]

                    if matching_pdf:
                        try:
                            ann_pdf_bytes = annotate_graded_pdf(matching_pdf, res)
                            st.download_button(
                                label=f"📝 Graded Sheet ({s_name})",
                                data=ann_pdf_bytes,
                                file_name=f"{s_name.replace(' ', '_')}_Graded_Sheet.pdf",
                                mime="application/pdf",
                                key=f"dl_grade_ann_{idx}",
                                use_container_width=True,
                            )
                        except Exception as e:
                            st.error(f"Annotation error: {e}")
                    else:
                        st.caption("Original sheet PDF not cached")
