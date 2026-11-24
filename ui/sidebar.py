import os
import streamlit as st
from core.theme_manager import get_theme


# Navigation items for Answer Sheet Grader
NAV_ITEMS = [
    ("📤", "Upload Documents", "upload"),
    ("📋", "Rubric Review", "rubric_review"),
    ("⚡", "Auto-Grade Exam", "grade"),
    ("🔍", "Manual Review", "review"),
    ("📑", "Student Reports", "student_reports"),
    ("📊", "Class Analytics", "dashboard"),
    ("📥", "Export & Downloads", "downloads"),
]


def get_upgrad_logo_base64() -> str:
    """Reads the upGrad School of Technology logo and returns it as base64."""
    logo_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "assets", "upgrad_logo.jpg")
    try:
        if os.path.exists(logo_path):
            import base64
            with open(logo_path, "rb") as f:
                return base64.b64encode(f.read()).decode("utf-8")
    except Exception:
        pass
    return ""


def render_sidebar():
    """Renders the upGrad School of Technology Answer Sheet Grader sidebar."""
    theme = get_theme()

    with st.sidebar:
        # ── 1. upGrad School of Technology Logo & Header ──────────────
        logo_b64 = get_upgrad_logo_base64()

        if logo_b64:
            st.markdown(
                f"""
                <div style="padding: 12px 4px 14px 4px; text-align: center;">
                    <img src="data:image/jpeg;base64,{logo_b64}" 
                         style="width: 175px; max-width: 100%; height: auto; display: block; margin: 0 auto;" 
                         alt="upGrad School of Technology" />
                    <div style="
                        font-size: 0.96rem; 
                        color: #0f172a; 
                        font-weight: 800; 
                        letter-spacing: -0.02em; 
                        margin-top: 10px;
                    ">Answer Sheet Grader</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                f"""
                <div style="padding: 14px 4px 10px 4px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div style="
                            width: 40px; 
                            height: 40px; 
                            border-radius: 10px; 
                            background: {theme['accent_primary']}; 
                            display: flex; 
                            align-items: center; 
                            justify-content: center;
                            font-size: 1.25rem;
                            color: white;
                            box-shadow: 0 4px 12px rgba(235, 28, 36, 0.25);
                        ">🎓</div>
                        <div>
                            <div style="font-size: 1.1rem; font-weight: 800; color: #0f172a; line-height: 1.15;">
                                upGrad <span style="color:#eb1c24;">SOT</span>
                            </div>
                            <div style="font-size: 0.72rem; color: #64748b; font-weight: 600;">
                                Answer Sheet Grader
                            </div>
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)

        # ── 2. Navigation Menu ─────────────────────────────────────────
        current_page = st.session_state.get("current_page", "upload")
        session = st.session_state.get("grading_session")

        for icon, label, page_key in NAV_ITEMS:
            is_active = current_page == page_key

            # Badge indicator
            badge = ""
            if page_key == "review" and session and session.students_needing_review > 0:
                badge = f"  [{session.students_needing_review}]"
            elif page_key == "student_reports" and session and session.total_students > 0:
                badge = f"  [{session.total_students}]"

            if is_active:
                btn_label = f"{icon}  {label}{badge}  ✦"
            else:
                btn_label = f"{icon}  {label}{badge}"

            if st.button(
                btn_label,
                key=f"nav_{page_key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["current_page"] = page_key
                st.rerun()

        st.divider()

        # ── 4. ⚡ AI Engine & Provider Configuration ───────────────────
        st.markdown(
            "<p style='font-size:0.72rem; color:#94a3b8; font-weight:700; "
            "text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;'>⚡ AI Evaluation Engine</p>",
            unsafe_allow_html=True,
        )

        from core.ai_client import (
            is_claude_key,
            get_available_models,
            CLAUDE_MODELS,
            GEMINI_DEFAULT_MODELS,
            test_api_connection,
        )

        # Initialize stored keys from env or secrets if not present
        if not st.session_state.get("claude_api_key"):
            c_env = os.getenv("ANTHROPIC_API_KEY", "")
            if not c_env and hasattr(st, "secrets"):
                try:
                    c_env = st.secrets.get("ANTHROPIC_API_KEY", "")
                except Exception:
                    pass
            st.session_state["claude_api_key"] = c_env

        if not st.session_state.get("gemini_api_key"):
            g_env = os.getenv("GEMINI_API_KEY", "")
            if not g_env and hasattr(st, "secrets"):
                try:
                    g_env = st.secrets.get("GEMINI_API_KEY", "")
                except Exception:
                    pass
            st.session_state["gemini_api_key"] = g_env

        raw_provider = st.session_state.get("ai_provider", "Anthropic Claude")
        provider_options = ["🔴 Anthropic Claude", "🟢 Google Gemini", "💻 Local ML (Ollama)"]
        if "Ollama" in raw_provider or "Local" in raw_provider:
            provider_idx = 2
        elif "Gemini" in raw_provider:
            provider_idx = 1
        else:
            provider_idx = 0

        selected_label = st.radio(
            "Select AI Provider",
            options=provider_options,
            index=provider_idx,
            horizontal=False,
            label_visibility="collapsed",
            key="radio_provider_selector",
        )
        if "Local" in selected_label or "Ollama" in selected_label:
            active_provider = "Local Offline (Ollama)"
            is_local = True
            is_claude = False
            is_gemini = False
        elif "Claude" in selected_label:
            active_provider = "Anthropic Claude"
            is_local = False
            is_claude = True
            is_gemini = False
        else:
            active_provider = "Google Gemini"
            is_local = False
            is_claude = False
            is_gemini = True

        # Handle provider switch
        if active_provider != st.session_state.get("ai_provider"):
            st.session_state["ai_provider"] = active_provider
            st.session_state.pop("cached_models", None)
            if is_local:
                st.session_state["api_key"] = "local"
                st.session_state["selected_model"] = "qwen2.5-vl:7b"
            elif is_claude:
                st.session_state["api_key"] = st.session_state.get("claude_api_key", "")
                st.session_state["selected_model"] = "claude-sonnet-5-5"
            else:
                st.session_state["api_key"] = st.session_state.get("gemini_api_key", "")
                st.session_state["selected_model"] = "gemini-2.5-flash"
            st.rerun()

        # Engine Settings
        if is_local:
            st.markdown(
                """
                <div style="
                    background: rgba(16, 185, 129, 0.08);
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 8px;
                    padding: 8px 12px;
                    margin-top: 6px;
                    margin-bottom: 6px;
                ">
                    <div style="font-weight: 700; color: #047857; font-size: 0.76rem; display: flex; align-items: center; gap: 6px;">
                        <span>💻</span> 100% Offline AI (Zero API Keys)
                    </div>
                    <div style="font-size: 0.70rem; color: #475569; margin-top: 3px; line-height: 1.35;">
                        Runs on Mac GPU via local Ollama. Private and secure.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            ollama_endpoint = st.text_input(
                "Ollama Endpoint",
                value=st.session_state.get("ollama_endpoint", "http://localhost:11434"),
                placeholder="http://localhost:11434",
                help="Local Ollama address (default: http://localhost:11434)",
                key="input_ollama_endpoint",
            )
            if ollama_endpoint != st.session_state.get("ollama_endpoint"):
                st.session_state["ollama_endpoint"] = ollama_endpoint
                st.session_state.pop("cached_models", None)
            st.session_state["api_key"] = "local"
            active_key = "local"

            with st.expander("🛠️ Setup Local AI Guide", expanded=False):
                st.markdown(
                    """
                    <div style="font-size:0.73rem; color:#334155; line-height:1.4;">
                    1. Install: <code>brew install ollama</code><br/>
                    2. Run: <code>ollama run qwen2.5-vl</code>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        elif is_claude:
            st.markdown(
                "<p style='font-size:0.72rem; color:#64748b; font-weight:700; "
                "text-transform:uppercase; letter-spacing:0.06em; margin-top:6px; margin-bottom:4px;'>🔴 Claude API Key</p>",
                unsafe_allow_html=True,
            )
            c_key_input = st.text_input(
                "Claude API Key",
                type="password",
                value=st.session_state.get("claude_api_key", ""),
                placeholder="sk-ant-...",
                label_visibility="collapsed",
                key="input_claude_active_key",
            )
            if c_key_input != st.session_state.get("claude_api_key"):
                st.session_state["claude_api_key"] = c_key_input
                st.session_state.pop("cached_models", None)
            st.session_state["api_key"] = c_key_input
            active_key = c_key_input

        else:
            st.markdown(
                "<p style='font-size:0.72rem; color:#64748b; font-weight:700; "
                "text-transform:uppercase; letter-spacing:0.06em; margin-top:6px; margin-bottom:4px;'>🟢 Gemini API Key</p>",
                unsafe_allow_html=True,
            )
            g_key_input = st.text_input(
                "Gemini API Key",
                type="password",
                value=st.session_state.get("gemini_api_key", ""),
                placeholder="AIzaSy...",
                label_visibility="collapsed",
                key="input_gemini_active_key",
            )
            if g_key_input != st.session_state.get("gemini_api_key"):
                st.session_state["gemini_api_key"] = g_key_input
                st.session_state.pop("cached_models", None)
            st.session_state["api_key"] = g_key_input
            active_key = g_key_input

        # Model Selection
        cached_m = st.session_state.get("cached_models")
        ws_id = os.getenv("ANTHROPIC_WORKSPACE_ID", "")
        current_endpoint = st.session_state.get("ollama_endpoint", "http://localhost:11434")

        if cached_m:
            model_options = cached_m
        else:
            if is_local:
                model_options = get_available_models("local", provider="Local Offline (Ollama)", endpoint=current_endpoint)
            elif is_claude:
                model_options = get_available_models(active_key, provider="Anthropic Claude", workspace_id=ws_id) if active_key else CLAUDE_MODELS
            else:
                model_options = get_available_models(active_key, provider="Google Gemini") if active_key else GEMINI_DEFAULT_MODELS

        default_model = model_options[0] if model_options else ("qwen2.5-vl:7b" if is_local else ("claude-sonnet-5-5" if is_claude else "gemini-2.5-flash"))
        current_model = st.session_state.get("selected_model")
        if not current_model or (is_local and not any(k in current_model for k in ["qwen", "llama", "llava", "minicpm", "deepseek"])) or (is_claude and "gemini" in current_model) or (is_gemini and "claude" in current_model):
            current_model = default_model

        selected_model = st.selectbox(
            "AI Model",
            options=model_options,
            index=model_options.index(current_model) if current_model in model_options else 0,
            label_visibility="collapsed",
        )
        st.session_state["selected_model"] = selected_model

        # Test Connection Button
        if is_local or active_key:
            test_label = "🔌 Test Local Connection" if is_local else ("🔌 Test Claude" if is_claude else "🔌 Test Gemini")
            if st.button(test_label, use_container_width=True, key="btn_test_conn"):
                with st.spinner("Testing connection..."):
                    ok, msg, discovered_models = test_api_connection(
                        api_key=active_key,
                        model_name=selected_model,
                        workspace_id=ws_id,
                        provider=active_provider,
                        endpoint=current_endpoint,
                    )
                    if ok:
                        st.success(f"✅ {msg}")
                        if discovered_models:
                            st.session_state["cached_models"] = discovered_models
                            st.rerun()
                    else:
                        st.error(f"❌ {msg}")

        st.divider()

        # ── 5. Live Status ─────────────────────────────────────────────
        st.markdown(
            "<p style='font-size:0.72rem; color:#94a3b8; font-weight:700; "
            "text-transform:uppercase; letter-spacing:0.08em; margin-bottom:6px;'>📊 Live Status</p>",
            unsafe_allow_html=True,
        )

        pdfs = st.session_state.get("uploaded_pdfs", [])
        qp_file = st.session_state.get("question_paper_file")
        rubric = st.session_state.get("parsed_rubric")

        from core.database import get_database_stats
        db_stats = get_database_stats()

        _status_item("Answer Sheets", f"{len(pdfs)} loaded" if pdfs else "Pending", bool(pdfs))
        _status_item("Question Paper", "Loaded ✓" if qp_file else "Optional", bool(qp_file))
        _status_item("Rubric Scheme", "Ready ✓" if rubric else "Not parsed", bool(rubric))
        if session and session.student_results:
            _status_item("Grading Status", f"{session.total_students} completed", True)
        else:
            _status_item("Grading Status", "Not started", False)
        _status_item("SQLite DB", f"{db_stats['total_sessions']} exams saved", True)

        active_sid = st.session_state.get("session_id", "default")
        st.markdown(
            f"<div style='font-size:0.71rem; color:#94a3b8; margin-top:10px; text-align:center;'>"
            f"Active Session: <code style='color:#eb1c24; font-weight:700;'>{active_sid[:8]}</code></div>",
            unsafe_allow_html=True,
        )

        st.markdown("<div style='height: 12px;'></div>", unsafe_allow_html=True)


def _status_item(label: str, value: str, is_ok: bool):
    """Renders a single sleek status indicator line."""
    dot_color = "#eb1c24" if is_ok else "#cbd5e1"
    val_color = "#0f172a" if is_ok else "#94a3b8"
    st.markdown(
        f"""
        <div style='display:flex; justify-content:space-between; align-items:center; 
                    padding:5px 0; font-size:0.80rem; border-bottom:1px solid #f1f5f9;'>
            <span style='display:flex; align-items:center; gap:7px; color:#334155;'>
                <span style='width:7px; height:7px; border-radius:50%; background:{dot_color}; 
                             box-shadow: 0 0 6px {dot_color if is_ok else "transparent"}; display:inline-block;'></span>
                {label}
            </span>
            <span style='color:{val_color}; font-weight:600;'>{value}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )
