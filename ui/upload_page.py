"""
Upload page for answer sheets and rubric documents.
"""
import streamlit as st
from core.rubric_parser import parse_rubric_document


def render_upload_page():
    """Renders the Upload Examination Documents interface."""
    st.markdown(
        """
        <div style="margin-bottom: 24px; padding-bottom: 14px; border-bottom: 1px solid #f1f5f9;">
            <div style="font-size: 1.85rem; font-weight: 800; color: #0f172a; letter-spacing: -0.025em; line-height: 1.2;">
                📤 Upload Examination Documents
            </div>
            <div style="font-size: 0.92rem; color: #64748b; margin-top: 6px;">
                Upload scanned student answer sheets (.pdf), official question paper (.pdf / .docx), and examination grading rubric scheme (.docx / .pdf).
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    col1, col2, col3 = st.columns(3)

    # ── Column 1: Student Answer Sheets ───────────────────────────────
    with col1:
        st.markdown(
            """
            <div class="glass-card">
                <h3>📄 Answer Sheets</h3>
                <p style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">Upload PDF files — one per student</p>
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
                        f"background:rgba(235, 28, 36, 0.05); border-radius:10px; "
                        f"border-left:3px solid #eb1c24; color:#0f172a;'>"
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
                    if st.button("🔍 Test Transcription", key="btn_test_ocr", use_container_width=True):
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

    # ── Column 2: Question Paper ─────────────────────────────────────
    with col2:
        st.markdown(
            """
            <div class="glass-card">
                <h3>📑 Question Paper</h3>
                <p style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">Upload exam paper (.pdf or .docx)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        question_paper_file = st.file_uploader(
            "Drag and drop question paper here",
            type=["pdf", "docx"],
            key="qp_uploader",
            help="Upload official question paper. The AI extracts exact question wording, options, and constraints.",
        )
        if question_paper_file:
            st.session_state["question_paper_file"] = question_paper_file
            qp_size_kb = question_paper_file.size / 1024
            st.success(f"✅ Loaded **{question_paper_file.name}** ({qp_size_kb:.1f} KB)")

            with st.expander("👁️ Preview Question Paper Content", expanded=False):
                from core.rubric_parser import extract_text_from_file_bytes
                try:
                    qp_raw = extract_text_from_file_bytes(question_paper_file.getvalue(), question_paper_file.name)
                    st.session_state["question_paper_text"] = qp_raw
                    snippet = qp_raw[:1200] + ("\n... [content continues]" if len(qp_raw) > 1200 else "")
                    st.text_area("Extracted Question Paper Text", value=snippet, height=180, disabled=True)
                except Exception as qp_err:
                    st.warning(f"Could not extract preview: {qp_err}")
        else:
            st.markdown(
                """
                <div style="padding: 10px 12px; background: #f8fafc; border-radius: 8px; border: 1px dashed #cbd5e1; font-size: 0.78rem; color: #64748b; margin-top: 8px;">
                    💡 <strong>Evaluation Tip:</strong> Uploading the Question Paper gives the AI the exact questions, options, and sub-parts to evaluate student answers with highest accuracy.
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Column 3: Rubric Scheme ──────────────────────────────────────
    with col3:
        st.markdown(
            """
            <div class="glass-card">
                <h3>📋 Rubric Document</h3>
                <p style="color: #64748b; font-size: 0.85rem; margin-top: 4px;">Upload marking scheme (.docx or .pdf)</p>
            </div>
            """,
            unsafe_allow_html=True,
        )
        rubric_file = st.file_uploader(
            "Drag and drop rubric here",
            type=["docx", "pdf"],
            key="rubric_uploader",
            help="Marking scheme with model solutions and criteria. If omitted, AI will generate it from the Question Paper.",
        )
        if rubric_file:
            st.session_state["rubric_file"] = rubric_file
            size_kb = rubric_file.size / 1024
            st.success(f"✅ Loaded **{rubric_file.name}** ({size_kb:.1f} KB)")

        if st.session_state.get("parsed_rubric"):
            parsed = st.session_state["parsed_rubric"]
            q_sum = sum(float(q.max_marks) for q in parsed.questions)
            qp_indicator = " + Question Paper ✓" if getattr(parsed, "question_paper_text", None) else ""
            st.markdown(
                f"""
                <div style="background:#f8fafc; border:1px solid #e2e8f0; border-left:4px solid #eb1c24; padding:10px 14px; border-radius:6px; margin-top:10px;">
                    <div style="font-weight:700; color:#0f172a; font-size:0.88rem;">📋 Rubric Active: {parsed.exam_title or 'Exam'}{qp_indicator}</div>
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

    # Parse Rubric & Question Paper Button
    col_btn, _, _ = st.columns([1.5, 1, 2])
    with col_btn:
        if st.button("⚙️ Parse Rubric & Question Paper", type="primary", use_container_width=True):
            rubric_file = st.session_state.get("rubric_file")
            qp_file = st.session_state.get("question_paper_file")
            api_key = st.session_state.get("api_key", "")
            provider = st.session_state.get("ai_provider", "Anthropic Claude")
            endpoint = st.session_state.get("ollama_endpoint", "http://localhost:11434")
            ws_id = st.session_state.get("workspace_id", "")
            is_local = "Local" in provider or "Ollama" in provider or api_key == "local"

            if not rubric_file and not qp_file:
                st.error("❌ Please upload at least a Question Paper or a Rubric Document.")
            elif not is_local and not api_key:
                st.error("❌ Please enter your API Key in the sidebar.")
            else:
                with st.spinner("🔍 Analyzing examination documents & building evaluation rubric with AI..."):
                    try:
                        r_bytes = rubric_file.getvalue() if rubric_file else None
                        r_name = rubric_file.name if rubric_file else None
                        qp_bytes = qp_file.getvalue() if qp_file else None
                        qp_name = qp_file.name if qp_file else None
                        model_to_use = st.session_state.get("selected_model")

                        parsed_rubric = parse_rubric_document(
                            file_bytes=r_bytes,
                            filename=r_name,
                            api_key=api_key or "local",
                            model_name=model_to_use,
                            workspace_id=ws_id,
                            provider=provider,
                            endpoint=endpoint,
                            question_paper_bytes=qp_bytes,
                            question_paper_filename=qp_name,
                        )
                        st.session_state["parsed_rubric"] = parsed_rubric
                        st.success(
                            f"✅ Exam scheme parsed! Found **{len(parsed_rubric.questions)}** "
                            f"questions totalling **{parsed_rubric.total_marks}** marks."
                        )
                        # Auto navigate to rubric review
                        st.session_state["current_page"] = "rubric_review"
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error parsing documents: {str(e)}")
