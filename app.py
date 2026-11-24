"""
Main Streamlit application entry point.
"""
import streamlit as st
import os

from ui.sidebar import render_sidebar
from ui.upload_page import render_upload_page
from ui.rubric_editor import render_rubric_editor
from ui.grading_page import render_grading_page
from ui.review_page import render_review_page
from ui.results_page import render_results_page
from ui.dashboard_page import render_dashboard_page
from ui.student_reports_page import render_student_reports_page

import uuid
from core.database import init_db
from core.theme_manager import generate_theme_css

def load_css():
    """Loads custom CSS styles and injects White & Red theme CSS variables."""
    theme_vars = generate_theme_css()
    st.markdown(theme_vars, unsafe_allow_html=True)

    css_path = os.path.join(os.path.dirname(__file__), 'assets', 'styles.css')
    try:
        with open(css_path, 'r') as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass # Ignore if css file doesn't exist yet

def init_session_state():
    """Initializes Streamlit session state variables."""
    if 'current_page' not in st.session_state:
        st.session_state['current_page'] = 'upload'
    if 'ai_provider' not in st.session_state:
        st.session_state['ai_provider'] = 'Anthropic Claude'

    if 'claude_api_key' not in st.session_state or not st.session_state['claude_api_key']:
        c_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not c_key and hasattr(st, "secrets"):
            try:
                c_key = st.secrets.get("ANTHROPIC_API_KEY", "")
            except Exception:
                pass
        st.session_state['claude_api_key'] = c_key

    if 'gemini_api_key' not in st.session_state or not st.session_state['gemini_api_key']:
        g_key = os.getenv("GEMINI_API_KEY", "")
        if not g_key and hasattr(st, "secrets"):
            try:
                g_key = st.secrets.get("GEMINI_API_KEY", "")
            except Exception:
                pass
        st.session_state['gemini_api_key'] = g_key

    if 'ollama_endpoint' not in st.session_state:
        st.session_state['ollama_endpoint'] = os.getenv("OLLAMA_ENDPOINT", "http://localhost:11434")

    # Active API key and selected model based on active provider
    if st.session_state['ai_provider'] == 'Local Offline (Ollama)':
        st.session_state['api_key'] = 'local'
        if 'selected_model' not in st.session_state or any(k in st.session_state.get('selected_model', '') for k in ['claude', 'gemini']):
            st.session_state['selected_model'] = 'qwen2.5-vl:7b'
    elif st.session_state['ai_provider'] == 'Google Gemini':
        st.session_state['api_key'] = st.session_state.get('gemini_api_key', '')
        if 'selected_model' not in st.session_state or 'claude' in st.session_state.get('selected_model', '') or 'qwen' in st.session_state.get('selected_model', ''):
            st.session_state['selected_model'] = 'gemini-2.5-flash'
    else:
        st.session_state['api_key'] = st.session_state.get('claude_api_key', '')
        if 'selected_model' not in st.session_state or 'gemini' in st.session_state.get('selected_model', '') or 'qwen' in st.session_state.get('selected_model', ''):
            st.session_state['selected_model'] = 'claude-sonnet-5-5'

    if 'session_id' not in st.session_state:
        st.session_state['session_id'] = str(uuid.uuid4())[:8]
    if 'uploaded_pdfs' not in st.session_state:
        st.session_state['uploaded_pdfs'] = []
    if 'rubric_file' not in st.session_state:
        st.session_state['rubric_file'] = None
    if 'question_paper_file' not in st.session_state:
        st.session_state['question_paper_file'] = None
    if 'question_paper_text' not in st.session_state:
        st.session_state['question_paper_text'] = None
    if 'parsed_rubric' not in st.session_state:
        st.session_state['parsed_rubric'] = None
    if 'grading_session' not in st.session_state:
        st.session_state['grading_session'] = None

def main():
    init_db()
    st.set_page_config(
        page_title='upGrad School of Technology — Answer Sheet Grader', 
        page_icon='🎓', 
        layout='wide',
        initial_sidebar_state="expanded"
    )
    
    load_css()
    init_session_state()
    render_sidebar()
    
    page = st.session_state['current_page']
    
    if page == 'upload':
        render_upload_page()
    elif page == 'rubric_review':
        render_rubric_editor()
    elif page == 'grade':
        render_grading_page()
    elif page == 'review':
        render_review_page()
    elif page == 'dashboard':
        render_dashboard_page()
    elif page == 'student_reports':
        render_student_reports_page()
    elif page == 'downloads':
        render_results_page()
    else:
        render_upload_page()

if __name__ == "__main__":
    main()
