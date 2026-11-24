"""
Upload page for answer sheets and rubric documents.
"""
import streamlit as st
from core.rubric_parser import parse_rubric_document


def render_upload_page():
    """Renders the file upload interface."""
    st.title("📤 Upload Documents")
    st.markdown("Upload your students' answer sheets and the grading rubric document.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown(
            """
            <div class="glass-card">
                <h3>📄 Answer Sheets</h3>
                <p style="color: #aaa;">Upload PDF files — one per student</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        uploaded_pdfs = st.file_uploader(
            "Drag and drop student PDFs here",
            type=["pdf"],
            accept_multiple_files=True,
            key="pdf_uploader",
        )
        if uploaded_pdfs:
            st.session_state["uploaded_pdfs"] = uploaded_pdfs
            st.success(f"✅ Loaded **{len(uploaded_pdfs)}** answer sheet(s)")

            with st.expander("📁 View uploaded files", expanded=False):
                for pdf in uploaded_pdfs:
                    size_kb = pdf.size / 1024
                    st.markdown(
                        f"<div style='padding:8px 14px; margin:5px 0; "
                        f"background:rgba(225, 29, 72, 0.05); border-radius:10px; "
                        f"border-left:3px solid #e11d48; color:#0f172a;'>"
                        f"📄 <strong>{pdf.name}</strong> — {size_kb:.1f} KB</div>",
                        unsafe_allow_html=True,
                    )

            with st.expander("✍️ Inspect & Transcribe Handwriting (Preview)", expanded=False):
                from core.pdf_processor import render_pdf_pages
                from core.handwriting_ocr import transcribe_handwritten_sheet

                selected_preview_pdf = st.selectbox(
                    "Choose Answer Sheet to Inspect:",
                    options=[p.name for p in uploaded_pdfs],
                    key="inspect_pdf_sel",
                )
                target_pdf = next(p for p in uploaded_pdfs if p.name == selected_preview_pdf)

                rot_col, test_col = st.columns([1, 1])
                with rot_col:
                    rotation = st.selectbox(
                        "Orientation / Rotation:",
                        options=[0, 90, 180, 270],
                        format_func=lambda r: f"{r}° (Normal)" if r == 0 else f"{r}°",
                        key=f"rot_{selected_preview_pdf}",
                    )
                    st.session_state[f"rot_offset_{selected_preview_pdf}"] = rotation

                # Render enhanced preview
                preview_pages = render_pdf_pages(
                    target_pdf.getvalue(),
                    dpi=150,
                    enhance_handwriting=True,
                    rotation_offset=rotation,
                )
                if preview_pages:
                    st.image(
                        preview_pages[0].image_bytes,
                        caption=f"{selected_preview_pdf} — Page 1 (Enhanced for Handwriting)",
                        use_container_width=True,
                    )

                with test_col:
                    if st.button("🔍 Test Handwriting Transcription", key="btn_test_ocr", use_container_width=True):
                        api_key = st.session_state.get("api_key", "")
                        model_name = st.session_state.get("selected_model")
                        ws_id = st.session_state.get("workspace_id", "")
                        provider = st.session_state.get("ai_provider", "Anthropic Claude")
                        endpoint = st.session_state.get("ollama_endpoint", "http://localhost:11434")
                        is_local = "Local" in provider or "Ollama" in provider or api_key == "local"
                        if not is_local and not api_key:
                            st.warning("Please enter your API Key in the sidebar.")
                        else:
                            with st.spinner("🤖 Deciphering handwriting with AI..."):
                                raw_images = [p.image_bytes for p in preview_pages]
                                transcript = transcribe_handwritten_sheet(
                                    raw_images,
                                    api_key or "local",
                                    model_name=model_name,
                                    workspace_id=ws_id,
                                    provider=provider,
                                    endpoint=endpoint,
                                )
                                st.markdown("##### 📝 Transcribed Text:")
                                st.info(transcript)

    with col2:
        st.markdown(
            """
            <div class="glass-card">
                <h3>📋 Rubric Document</h3>
                <p style="color: #aaa;">Upload your marking scheme (.docx or .pdf)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        rubric_file = st.file_uploader(
            "Drag and drop rubric here",
            type=["docx", "pdf"],
            key="rubric_uploader",
        )
        if rubric_file:
            st.session_state["rubric_file"] = rubric_file
            size_kb = rubric_file.size / 1024
            st.success(f"✅ Loaded **{rubric_file.name}** ({size_kb:.1f} KB)")

        if st.session_state.get("parsed_rubric"):
            parsed = st.session_state["parsed_rubric"]
            q_sum = sum(float(q.max_marks) for q in parsed.questions)
            st.markdown(
                f"""
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-left:4px solid #e11d48; padding:10px 14px; border-radius:6px; margin-top:10px;">
                    <div style="font-weight:700; color:#0f172a; font-size:0.88rem;">📋 Rubric Active: {parsed.exam_title or 'Exam'}</div>
                    <div style="font-size:0.8rem; color:#64748b; margin-top:2px;">
                        <b>{len(parsed.questions)}</b> questions &bull; Detected questions sum: <b>{q_sum:.1f}</b> marks
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            custom_total = st.number_input(
                "Official Exam Total Marks (Scored Out Of):",
                min_value=1.0,
                max_value=2000.0,
                value=float(parsed.total_marks if (parsed.total_marks and parsed.total_marks > 0) else q_sum),
                step=1.0,
                key="upload_rubric_total_marks",
                help="If the exam has choice/optional questions (e.g. 200 marks detected, but exam is out of 100), specify 100 here.",
            )
            parsed.total_marks = custom_total
            st.session_state["parsed_rubric"].total_marks = custom_total

    st.divider()

    # Parse Rubric Button
    col_btn, _, _ = st.columns([1, 1, 2])
    with col_btn:
        if st.button("⚙️ Parse Rubric", type="primary", use_container_width=True):
            rubric_file = st.session_state.get("rubric_file")
            api_key = st.session_state.get("api_key", "")
            provider = st.session_state.get("ai_provider", "Anthropic Claude")
            endpoint = st.session_state.get("ollama_endpoint", "http://localhost:11434")
            ws_id = st.session_state.get("workspace_id", "")
            is_local = "Local" in provider or "Ollama" in provider or api_key == "local"

            if not rubric_file:
                st.error("❌ Please upload a rubric document first.")
            elif not is_local and not api_key:
                st.error("❌ Please enter your API Key in the sidebar.")
            else:
                with st.spinner("🔍 Analyzing rubric document with AI..."):
                    try:
                        file_bytes = rubric_file.getvalue()
                        model_to_use = st.session_state.get("selected_model")
                        parsed_rubric = parse_rubric_document(
                            file_bytes=file_bytes,
                            filename=rubric_file.name,
                            api_key=api_key or "local",
                            model_name=model_to_use,
                            workspace_id=ws_id,
                            provider=provider,
                            endpoint=endpoint,
                        )
                        st.session_state["parsed_rubric"] = parsed_rubric
                        st.success(
                            f"✅ Rubric parsed! Found **{len(parsed_rubric.questions)}** "
                            f"questions totalling **{parsed_rubric.total_marks}** marks."
                        )
                        # Auto navigate to rubric review
                        st.session_state["current_page"] = "rubric_review"
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error parsing rubric: {str(e)}")
