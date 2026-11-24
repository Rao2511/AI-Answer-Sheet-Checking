import os
import streamlit as st
from core.theme_manager import get_theme


# Navigation items with icons and page keys
NAV_ITEMS = [
    ("📤", "Upload Documents", "upload"),
    ("📋", "Rubric Review", "rubric_review"),
    ("⚡", "Auto-Grade Exam", "grade"),
    ("🔍", "Manual Review", "review"),
    ("📑", "Student Reports", "student_reports"),
    ("📊", "Class Analytics", "dashboard"),
    ("📥", "Export & Downloads", "downloads"),
]


def render_sidebar():
    """Renders the clean, modern sidebar with White & Red theme styling."""
    theme = get_theme()

    with st.sidebar:
        # ── Logo & App Title ───────────────────────────────────────────
        st.markdown(
            f"""
            <div style="padding: 16px 4px 8px 4px;">
                <div style="display: flex; align-items: center; gap: 12px; margin-bottom: 6px;">
                    <div style="
                        width: 44px; 
                        height: 44px; 
                        border-radius: 12px; 
                        background: {theme['accent_gradient']}; 
                        display: flex; 
                        align-items: center; 
                        justify-content: center;
                        font-size: 1.35rem;
                        box-shadow: 0 4px 16px rgba(225, 29, 72, 0.25);
                        color: white;
                    ">📝</div>
                    <div>
                        <div style="
                            font-size: 1.2rem;
                            font-weight: 800;
                            letter-spacing: -0.025em;
                            color: #0f172a;
                            line-height: 1.2;
                        ">AutoGrade <span style="color:#e11d48;">AI</span></div>
                        <div style="font-size: 0.73rem; color: #64748b; font-weight: 500;">
                            Answer Sheet Grader
                        </div>
                    </div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.divider()

        # ── ⚡ AI Provider Selector ─────────────────────────────────────
        st.markdown(
            "<p style='font-size:0.75rem; color:#64748b; font-weight:700; "
            "text-transform:uppercase; letter-spacing:0.06em; margin-bottom:6px;'>⚡ AI Provider</p>",
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

        # ── 🔑 Engine Configuration / API Key Input ─────────────────────
        if is_local:
            st.markdown(
                """
                <div style="
                    background: rgba(16, 185, 129, 0.08);
                    border: 1px solid rgba(16, 185, 129, 0.3);
                    border-radius: 8px;
                    padding: 8px 12px;
                    margin-top: 8px;
                    margin-bottom: 8px;
                ">
                    <div style="font-weight: 700; color: #047857; font-size: 0.78rem; display: flex; align-items: center; gap: 6px;">
                        <span>💻</span> 100% Offline AI (Zero API Keys)
                    </div>
                    <div style="font-size: 0.71rem; color: #475569; margin-top: 3px; line-height: 1.35;">
                        Runs directly on your Mac GPU (Metal accelerated) via local Ollama. Private, secure, and free.
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            ollama_endpoint = st.text_input(
                "Ollama Endpoint",
                value=st.session_state.get("ollama_endpoint", "http://localhost:11434"),
                placeholder="http://localhost:11434",
                help="Local or network Ollama API address (default: http://localhost:11434)",
                key="input_ollama_endpoint",
            )
            if ollama_endpoint != st.session_state.get("ollama_endpoint"):
                st.session_state["ollama_endpoint"] = ollama_endpoint
                st.session_state.pop("cached_models", None)
            st.session_state["api_key"] = "local"
            active_key = "local"

            # Setup Guide Expander
            with st.expander("🛠️ How to setup Local Offline AI", expanded=False):
                st.markdown(
                    """
                    <div style="font-size:0.75rem; color:#334155; line-height:1.4;">
                    <b>Quick 2-Step Terminal Setup:</b><br/>
                    1. Install Ollama:
                    <pre style="background:#f1f5f9; padding:4px 8px; border-radius:4px; font-size:0.72rem; margin:4px 0;">brew install ollama</pre>
                    2. Run Local Vision Model:
                    <pre style="background:#f1f5f9; padding:4px 8px; border-radius:4px; font-size:0.72rem; margin:4px 0;">ollama run qwen2.5-vl</pre>
                    <i>(Alternative models: <code>llama3.2-vision:11b</code>, <code>minicpm-v</code>)</i>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

        elif is_claude:
            st.markdown(
                "<p style='font-size:0.75rem; color:#64748b; font-weight:700; "
                "text-transform:uppercase; letter-spacing:0.06em; margin-top:8px; margin-bottom:4px;'>🔴 Anthropic Claude API Key</p>",
                unsafe_allow_html=True,
            )
            c_key_input = st.text_input(
                "Claude API Key",
                type="password",
                value=st.session_state.get("claude_api_key", ""),
                placeholder="Paste sk-ant-api03-... or sk-ant-usr-...",
                label_visibility="collapsed",
                key="input_claude_active_key",
            )
            if c_key_input != st.session_state.get("claude_api_key"):
                st.session_state["claude_api_key"] = c_key_input
                st.session_state.pop("cached_models", None)
            st.session_state["api_key"] = c_key_input
            active_key = c_key_input

            if active_key:
                st.markdown(
                    "<p style='color:#e11d48; font-size:0.74rem; font-weight:600; margin:2px 0 6px 0;'>"
                    "🔴 Anthropic Claude active</p>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<p style='color:#e11d48; font-size:0.74rem; margin:2px 0 6px 0;'>⚠️ Claude API Key required</p>",
                    unsafe_allow_html=True,
                )
        else:
            st.markdown(
                "<p style='font-size:0.75rem; color:#64748b; font-weight:700; "
                "text-transform:uppercase; letter-spacing:0.06em; margin-top:8px; margin-bottom:4px;'>🟢 Google Gemini API Key</p>",
                unsafe_allow_html=True,
            )
            g_key_input = st.text_input(
                "Gemini API Key",
                type="password",
                value=st.session_state.get("gemini_api_key", ""),
                placeholder="Paste AIzaSy...",
                label_visibility="collapsed",
                key="input_gemini_active_key",
            )
            if g_key_input != st.session_state.get("gemini_api_key"):
                st.session_state["gemini_api_key"] = g_key_input
                st.session_state.pop("cached_models", None)
            st.session_state["api_key"] = g_key_input
            active_key = g_key_input

            if active_key:
                st.markdown(
                    "<p style='color:#10b981; font-size:0.74rem; font-weight:600; margin:2px 0 6px 0;'>"
                    "🟢 Google Gemini active</p>",
                    unsafe_allow_html=True,
                )
            else:
                st.markdown(
                    "<p style='color:#e11d48; font-size:0.74rem; margin:2px 0 6px 0;'>⚠️ Gemini API Key required</p>",
                    unsafe_allow_html=True,
                )

        # ── ⚙️ Manage Both API Keys Expander ───────────────────────────
        with st.expander("🔑 Manage Saved API Keys", expanded=False):
            st.markdown(
                "<p style='font-size:0.75rem; color:#64748b; margin-bottom:6px;'>"
                "Save your cloud keys to easily switch between Claude and Gemini:</p>",
                unsafe_allow_html=True,
            )
            both_c = st.text_input(
                "Anthropic Key",
                value=st.session_state.get("claude_api_key", ""),
                type="password",
                key="exp_both_claude",
            )
            both_g = st.text_input(
                "Gemini Key",
                value=st.session_state.get("gemini_api_key", ""),
                type="password",
                key="exp_both_gemini",
            )
            if both_c != st.session_state.get("claude_api_key"):
                st.session_state["claude_api_key"] = both_c
                if is_claude:
                    st.session_state["api_key"] = both_c
            if both_g != st.session_state.get("gemini_api_key"):
                st.session_state["gemini_api_key"] = both_g
                if is_gemini:
                    st.session_state["api_key"] = both_g

        # ── 🤖 AI Model Selection ──────────────────────────────────────
        st.markdown(
            "<p style='font-size:0.75rem; color:#64748b; font-weight:700; "
            "text-transform:uppercase; letter-spacing:0.06em; margin-top:8px; margin-bottom:6px;'>🤖 AI Model</p>",
            unsafe_allow_html=True,
        )

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
            if is_local:
                test_label = "🔌 Test Local Ollama Connection"
            elif is_claude:
                test_label = "🔌 Test Claude Connection"
            else:
                test_label = "🔌 Test Gemini Connection"

            if st.button(test_label, use_container_width=True, key="btn_test_conn"):
                with st.spinner("Testing AI connection..."):
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

        # ── 🧭 Navigation ──────────────────────────────────────────────
        st.markdown(
            "<p style='font-size:0.75rem; color:#64748b; font-weight:700; "
            "text-transform:uppercase; letter-spacing:0.06em; margin-bottom:6px;'>🧭 Navigation</p>",
            unsafe_allow_html=True,
        )

        current_page = st.session_state.get("current_page", "upload")

        for icon, label, page_key in NAV_ITEMS:
            is_active = current_page == page_key
            btn_label = f"▸ {icon}  {label}" if is_active else f"{icon}   {label}"

            if st.button(
                btn_label,
                key=f"nav_{page_key}",
                use_container_width=True,
                type="primary" if is_active else "secondary",
            ):
                st.session_state["current_page"] = page_key
                st.rerun()

        st.divider()

        # ── 📊 Status Indicators ────────────────────────────────────────
        st.markdown(
            "<p style='font-size:0.75rem; color:#64748b; font-weight:700; "
            "text-transform:uppercase; letter-spacing:0.06em; margin-bottom:6px;'>📊 Live Status</p>",
            unsafe_allow_html=True,
        )

        pdfs = st.session_state.get("uploaded_pdfs", [])
        rubric = st.session_state.get("parsed_rubric")
        session = st.session_state.get("grading_session")

        _status_item("Answer Sheets", f"{len(pdfs)} loaded" if pdfs else "Pending", bool(pdfs))
        _status_item("Exam Rubric", "Ready ✓" if rubric else "Not parsed", bool(rubric))

        if session and session.student_results:
            _status_item(
                "Grading Status",
                f"{session.total_students} completed",
                True,
            )
        else:
            _status_item("Grading Status", "Not started", False)

        st.markdown("<div style='height: 20px;'></div>", unsafe_allow_html=True)


def _status_item(label: str, value: str, is_ok: bool):
    """Renders a single sleek status indicator line."""
    dot_color = "#e11d48" if is_ok else "#cbd5e1"
    val_color = "#0f172a" if is_ok else "#94a3b8"
    st.markdown(
        f"""
        <div style='display:flex; justify-content:space-between; align-items:center; 
                    padding:5px 0; font-size:0.82rem; border-bottom:1px solid #f1f5f9;'>
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
