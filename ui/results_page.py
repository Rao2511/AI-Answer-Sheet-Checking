"""
Results and downloads hub — generates and serves annotated PDFs, Excel, and CSV reports.
"""
import io
import zipfile
import streamlit as st
from core.pdf_annotator import annotate_graded_pdf
from core.report_generator import generate_report_bytes


def render_results_page():
    """Renders the download hub for annotated PDFs and reports."""
    st.title("📥 Downloads & Results")

    session = st.session_state.get("grading_session")

    if not session or not session.student_results:
        st.warning("No grading results found. Please run the grading process first.")
        return

    st.markdown(
        f"**{session.total_students}** students graded · "
        f"**{session.get_class_average()}%** class average"
    )

    if st.button("📑 Open Detailed Student Reports & Report Cards", type="primary", use_container_width=True):
        st.session_state["current_page"] = "student_reports"
        st.rerun()

    st.divider()

    # ── Section 1: Grading Reports ─────────────────────────────────────────
    st.subheader("📊 Grading Reports")
    st.markdown("Download comprehensive score reports with styling and analytics.")

    try:
        excel_bytes, csv_bytes = generate_report_bytes(session)

        rep_col1, rep_col2 = st.columns(2)
        with rep_col1:
            st.download_button(
                label="📉 Download Excel Report (.xlsx)",
                data=excel_bytes,
                file_name="grading_report.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True,
            )
        with rep_col2:
            st.download_button(
                label="📄 Download CSV Report (.csv)",
                data=csv_bytes,
                file_name="grading_report.csv",
                mime="text/csv",
                use_container_width=True,
            )
        st.success("✅ Reports generated successfully!")
    except Exception as e:
        st.error(f"Error generating reports: {str(e)}")

    st.divider()

    # ── Section 2: Annotated PDFs ──────────────────────────────────────────
    st.subheader("📝 Annotated Answer Sheets")
    st.markdown(
        "Download graded PDFs with colored bounding boxes, score badges, "
        "and feedback annotations drawn on each answer."
    )

    pdf_bytes_map = st.session_state.get("pdf_bytes_map", {})

    if not pdf_bytes_map:
        st.warning(
            "Original PDF bytes not found. "
            "Please re-run grading to enable annotated PDF generation."
        )
        return

    if st.button("🖊️ Generate Annotated PDFs", type="primary", use_container_width=True):
        annotated_pdfs = {}
        progress = st.progress(0, text="Generating annotations...")

        for idx, result in enumerate(session.student_results):
            student_name = result.student_name_or_id or f"Student_{idx + 1}"
            progress.progress(
                (idx) / len(session.student_results),
                text=f"Annotating: {student_name}...",
            )

            # Find matching PDF bytes
            matching_pdf = None
            for filename, pdf_bytes in pdf_bytes_map.items():
                clean_name = filename.replace(".pdf", "").replace("_", " ")
                if clean_name == student_name or filename == f"{student_name}.pdf":
                    matching_pdf = pdf_bytes
                    break

            # Fallback: use by index
            if matching_pdf is None:
                pdf_keys = list(pdf_bytes_map.keys())
                if idx < len(pdf_keys):
                    matching_pdf = pdf_bytes_map[pdf_keys[idx]]

            if matching_pdf:
                try:
                    annotated = annotate_graded_pdf(matching_pdf, result)
                    annotated_pdfs[f"{student_name}_graded.pdf"] = annotated
                except Exception as e:
                    st.warning(f"⚠️ Could not annotate {student_name}: {str(e)}")
            else:
                st.warning(f"⚠️ No matching PDF found for {student_name}")

        progress.progress(1.0, text="✅ Annotations complete!")
        st.session_state["annotated_pdfs"] = annotated_pdfs
        st.success(f"✅ Generated {len(annotated_pdfs)} annotated PDFs!")

    # Show download buttons for annotated PDFs
    annotated_pdfs = st.session_state.get("annotated_pdfs", {})

    if annotated_pdfs:
        st.markdown("---")
        st.markdown("#### Individual Graded Answer Sheets")

        for filename, pdf_data in annotated_pdfs.items():
            st.download_button(
                label=f"📝 {filename}",
                data=pdf_data,
                file_name=filename,
                mime="application/pdf",
                key=f"dl_{filename}",
                use_container_width=True,
            )

    st.divider()

    # ── Section 3: Student Diagnostic Report Cards ─────────────────────────
    st.subheader("📑 Student Evaluation Report Cards")
    st.markdown("Download printable diagnostic report cards with student answers, marks breakdown, and AI feedback.")

    from core.report_generator import generate_student_report_card_pdf
    report_cards = {}
    for idx, s in enumerate(session.student_results):
        s_name = s.student_name_or_id or f"Student_{idx + 1}"
        clean_name = s_name.replace(" ", "_").replace("/", "_")
        try:
            rc_bytes = generate_student_report_card_pdf(s, session.exam_rubric)
            report_cards[f"{clean_name}_Report_Card.pdf"] = rc_bytes
        except Exception as e:
            st.warning(f"⚠️ Could not generate report card for {s_name}: {e}")

    if report_cards:
        rc_cols = st.columns(2)
        for idx, (fn, rc_data) in enumerate(report_cards.items()):
            with rc_cols[idx % 2]:
                st.download_button(
                    label=f"📑 {fn}",
                    data=rc_data,
                    file_name=fn,
                    mime="application/pdf",
                    key=f"dl_rc_page_{idx}",
                    use_container_width=True,
                )

    st.divider()

    # ── Section 4: All-in-One Comprehensive ZIP Bundle ───────────────────
    st.subheader("📦 All-in-One Complete ZIP Package")
    st.markdown("Download everything in a single archive: Excel report, CSV summary, all student report cards, and all annotated sheets.")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        # 1. Annotated Graded Sheets
        for filename, pdf_data in annotated_pdfs.items():
            zf.writestr(f"graded_sheets/{filename}", pdf_data)

        # 2. Report Cards
        for filename, rc_data in report_cards.items():
            zf.writestr(f"report_cards/{filename}", rc_data)

        # 3. Excel & CSV Reports
        try:
            excel_bytes, csv_bytes = generate_report_bytes(session)
            zf.writestr("grading_report.xlsx", excel_bytes)
            zf.writestr("grading_report.csv", csv_bytes)
        except Exception:
            pass

    st.download_button(
        label="🗜️ Download Complete Package (ZIP)",
        data=zip_buffer.getvalue(),
        file_name="complete_exam_grading_package.zip",
        mime="application/zip",
        use_container_width=True,
    )
