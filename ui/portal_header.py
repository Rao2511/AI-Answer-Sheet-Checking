"""
upGrad School of Technology Portal Header Component.
Renders the signature Admin Portal banner, date/campus metadata, and hero stats.
"""
import streamlit as st
import datetime


def render_portal_header(page_title: str = "Overview"):
    """
    Renders the upGrad School of Technology Admin Portal announcement banner
    and hero metrics header matching the portal design system.
    """
    now = datetime.datetime.now()
    date_str = now.strftime("%a %d %b").upper()
    time_str = now.strftime("%H:%M")
    full_meta = f"{date_str} · {time_str} IST · UPGRAD SOT · ADYPU + ONLINE + SSAHE"

    # ── 1. WHAT'S NEW Announcement Card ────────────────────────────────
    st.markdown(
        f"""
        <div style="
            background: #ffffff;
            border: 1px solid #e2e8f0;
            border-radius: 16px;
            padding: 16px 20px;
            margin-bottom: 22px;
            box-shadow: 0 1px 4px rgba(0, 0, 0, 0.03);
            display: flex;
            align-items: flex-start;
            gap: 16px;
        ">
            <div style="
                width: 36px;
                height: 36px;
                border-radius: 50%;
                background: #fee2e2;
                color: #eb1c24;
                display: flex;
                align-items: center;
                justify-content: center;
                font-size: 1.15rem;
                flex-shrink: 0;
                margin-top: 2px;
                font-weight: 700;
            ">✦</div>
            <div style="flex: 1;">
                <div style="
                    font-size: 0.72rem; 
                    font-weight: 800; 
                    color: #eb1c24; 
                    letter-spacing: 0.08em; 
                    text-transform: uppercase; 
                    margin-bottom: 3px;
                ">
                    WHAT'S NEW <span style="color: #94a3b8; font-weight: 500;">· {now.strftime('%d %b %Y')}</span>
                </div>
                <div style="
                    font-size: 1.05rem; 
                    font-weight: 700; 
                    color: #0f172a; 
                    line-height: 1.35; 
                    margin-bottom: 2px;
                ">
                    upGrad School of Technology AI Answer Sheet Grader is active
                </div>
                <div style="font-size: 0.85rem; color: #64748b; margin-bottom: 6px;">
                    • Multimodal OCR evaluates handwriting, equations & diagrams with automated rubric criteria matching.
                </div>
                <div style="font-size: 0.82rem; font-weight: 700; color: #eb1c24;">
                    Admin Portal · Semester Examination Evaluation
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 2. Page Title & Campus Metadata ────────────────────────────────
    st.markdown(
        f"""
        <div style="margin-bottom: 4px;">
            <div style="font-size: 1.3rem; font-weight: 800; color: #0f172a; letter-spacing: -0.02em;">
                {page_title}
            </div>
            <div style="
                font-size: 0.74rem; 
                color: #64748b; 
                font-weight: 700; 
                letter-spacing: 0.09em; 
                text-transform: uppercase; 
                font-family: 'JetBrains Mono', monospace; 
                margin-top: 10px;
                margin-bottom: 6px;
            ">
                {full_meta}
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # ── 3. Dynamic Hero Stat & Pills ───────────────────────────────────
    pdfs = st.session_state.get("uploaded_pdfs", [])
    rubric = st.session_state.get("parsed_rubric")
    session = st.session_state.get("grading_session")
    ai_provider = st.session_state.get("ai_provider", "Anthropic Claude")

    # Determine hero stats based on state
    if session and session.student_results:
        done_count = session.total_students
        review_count = session.students_needing_review
        avg_score = session.get_class_average()
        rubric_name = rubric.exam_title if rubric and rubric.exam_title else "Semester Exam"
        
        hero_stat = f"{done_count} done, {review_count} live"
        hero_sub = f"{review_count} answers flagged for review. {rubric_name}, Total: {rubric.total_marks if rubric else '100'} Marks."
        hero_desc = f"Faculty evaluation in progress. {done_count} student answer sheets evaluated with {ai_provider}. Diagnostic reports and PDF report cards ready."
        
        pill_blue = f"● {done_count} evaluated"
        pill_green = f"{avg_score}% class average"
        pill_red = f"{review_count} need review"
        pill_slate = f"{len(rubric.questions)} questions marked" if rubric else "Grading complete"

    elif pdfs:
        num_sheets = len(pdfs)
        rubric_name = rubric.exam_title if rubric and rubric.exam_title else "Answer Sheets Uploaded"
        total_m = f"{rubric.total_marks:.1f}" if rubric and rubric.total_marks else "Not set"
        
        hero_stat = f"{num_sheets} ready, 0 graded"
        hero_sub = f"{rubric_name}. Target Total: {total_m} Marks."
        hero_desc = f"{num_sheets} student answer sheets loaded and preprocessed with handwriting contrast enhancement. Ready for AI grading."
        
        pill_blue = f"● {num_sheets} uploaded"
        pill_green = f"Rubric: {'Ready ✓' if rubric else 'Pending upload'}"
        pill_red = f"Engine: {ai_provider.split()[0]}"
        pill_slate = f"upGrad SOT Evaluation"

    else:
        hero_stat = "0 done, ready"
        hero_sub = "Answer Sheet Grader · upGrad School of Technology"
        hero_desc = "Upload scanned student answer sheets (.pdf) and exam marking scheme (.docx / .pdf) to evaluate subjective and objective answers with AI."
        
        pill_blue = "● AI Engine Active"
        pill_green = "Faculty Portal"
        pill_red = "Semester Exams 2026"
        pill_slate = "15 of 15 syllabus marked"

    st.markdown(
        f"""
        <div style="margin-bottom: 24px;">
            <div style="
                font-size: 3.2rem; 
                font-weight: 900; 
                color: #eb1c24; 
                letter-spacing: -0.03em; 
                line-height: 1.1; 
                margin-bottom: 4px;
            ">
                {hero_stat}
            </div>
            <div style="
                font-size: 1.45rem; 
                font-weight: 700; 
                color: #0f172a; 
                letter-spacing: -0.02em; 
                margin-bottom: 6px;
            ">
                {hero_sub}
            </div>
            <div style="
                font-size: 0.92rem; 
                color: #475569; 
                line-height: 1.45; 
                margin-bottom: 14px;
            ">
                {hero_desc}
            </div>
            <div style="display: flex; flex-wrap: wrap; gap: 8px; align-items: center;">
                <span style="
                    display: inline-flex; align-items: center; gap: 6px; 
                    padding: 4px 12px; border-radius: 9999px; font-size: 0.78rem; 
                    font-weight: 700; background: #eff6ff; color: #2563eb; border: 1px solid #bfdbfe;
                ">{pill_blue}</span>
                <span style="
                    display: inline-flex; align-items: center; gap: 6px; 
                    padding: 4px 12px; border-radius: 9999px; font-size: 0.78rem; 
                    font-weight: 700; background: #f0fdf4; color: #16a34a; border: 1px solid #bbf7d0;
                ">{pill_green}</span>
                <span style="
                    display: inline-flex; align-items: center; gap: 6px; 
                    padding: 4px 12px; border-radius: 9999px; font-size: 0.78rem; 
                    font-weight: 700; background: #fef2f2; color: #dc2626; border: 1px solid #fecaca;
                ">{pill_red}</span>
                <span style="
                    display: inline-flex; align-items: center; gap: 6px; 
                    padding: 4px 12px; border-radius: 9999px; font-size: 0.78rem; 
                    font-weight: 700; background: #f1f5f9; color: #475569; border: 1px solid #e2e8f0;
                ">{pill_slate}</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
