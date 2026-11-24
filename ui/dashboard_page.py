"""
Analytics dashboard with rich Plotly charts and class insights.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np


from core.theme_manager import get_theme


def _get_chart_theme():
    """Returns clean layout and colors matching White & Red theme."""
    t = get_theme()
    template = {
        "layout": {
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "font": {"family": "Plus Jakarta Sans, Inter, sans-serif", "color": "#0f172a"},
            "xaxis": {"gridcolor": "rgba(0,0,0,0.06)", "zerolinecolor": "rgba(0,0,0,0.06)"},
            "yaxis": {"gridcolor": "rgba(0,0,0,0.06)", "zerolinecolor": "rgba(0,0,0,0.06)"},
            "margin": {"t": 40, "b": 40, "l": 40, "r": 20},
        }
    }
    return template, t["chart_colors"]


def render_dashboard_page():
    """Renders the analytics dashboard with interactive Plotly charts."""
    st.title("📊 Analytics Dashboard")

    chart_theme, chart_palette = _get_chart_theme()
    primary_chart_color = chart_palette[0] if chart_palette else "#6366f1"

    session = st.session_state.get("grading_session")

    # ── Build DataFrame ──────────────────────────────────────────────────
    if session and session.student_results:
        data = []
        for i, r in enumerate(session.student_results):
            pct = r.percentage if r.percentage is not None else r.compute_percentage()
            data.append({
                "Student": r.student_name_or_id or f"Student {i + 1}",
                "Score": r.total_marks_awarded,
                "Max": r.total_max_marks,
                "Percentage": pct,
            })
        df = pd.DataFrame(data)
        st.markdown(
            f"Showing results for **{len(df)} students** from exam "
            f"**{session.exam_rubric.exam_title}**"
        )
    else:
        st.info("📌 No grading data yet. Showing **sample data** for preview.")
        np.random.seed(42)
        scores = np.clip(np.random.normal(72, 15, 20), 15, 100).round(1)
        df = pd.DataFrame({
            "Student": [f"Student {i}" for i in range(1, 21)],
            "Score": scores,
            "Max": [100.0] * 20,
            "Percentage": scores,
        })

    # ── Row 1: Top Metrics ───────────────────────────────────────────────
    avg_pct = df["Percentage"].mean()
    highest = df["Percentage"].max()
    lowest = df["Percentage"].min()
    std_dev = df["Percentage"].std()
    pass_count = (df["Percentage"] >= 50).sum()
    pass_rate = (pass_count / len(df)) * 100

    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("👥 Students", len(df))
    m2.metric("📊 Average", f"{avg_pct:.1f}%")
    m3.metric("🏆 Highest", f"{highest:.1f}%")
    m4.metric("📉 Lowest", f"{lowest:.1f}%")
    m5.metric("✅ Pass Rate", f"{pass_rate:.0f}%")

    st.divider()

    # ── Row 2: Distribution + Pass/Fail ──────────────────────────────────
    chart1, chart2 = st.columns(2)

    with chart1:
        st.markdown("#### Score Distribution")
        fig_hist = go.Figure()
        fig_hist.add_trace(go.Histogram(
            x=df["Percentage"],
            nbinsx=10,
            marker=dict(
                color=primary_chart_color,
                opacity=0.85,
                line=dict(color=primary_chart_color, width=1),
            ),
            hovertemplate="Range: %{x}<br>Count: %{y}<extra></extra>",
        ))
        fig_hist.update_layout(
            **chart_theme["layout"],
            xaxis_title="Percentage (%)",
            yaxis_title="Number of Students",
            bargap=0.08,
            showlegend=False,
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    with chart2:
        st.markdown("#### Pass vs Fail")
        fail_count = len(df) - pass_count
        fig_pie = go.Figure()
        fig_pie.add_trace(go.Pie(
            labels=["Pass (≥50%)", "Fail (<50%)"],
            values=[pass_count, fail_count],
            marker=dict(colors=[primary_chart_color, "#f43f5e"]),
            hole=0.6,
            textinfo="percent+value",
            textfont=dict(size=13, color="white"),
            hovertemplate="%{label}: %{value} students (%{percent})<extra></extra>",
        ))
        fig_pie.update_layout(
            **chart_theme["layout"],
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=-0.15, x=0.25),
        )
        st.plotly_chart(fig_pie, use_container_width=True)

    st.divider()

    # ── Row 3: Student Rankings ──────────────────────────────────────────
    st.markdown("#### 🏅 Student Rankings")
    df_sorted = df.sort_values("Percentage", ascending=True)

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        y=df_sorted["Student"],
        x=df_sorted["Percentage"],
        orientation="h",
        marker=dict(
            color=df_sorted["Percentage"],
            colorscale=[[0, "#f43f5e"], [0.5, "#f59e0b"], [1, primary_chart_color]],
            line=dict(width=0),
        ),
        text=df_sorted["Percentage"].apply(lambda x: f"{x:.1f}%"),
        textposition="outside",
        hovertemplate="%{y}: %{x:.1f}%<extra></extra>",
    ))
    fig_bar.update_layout(
        **chart_theme["layout"],
        xaxis_title="Percentage (%)",
        height=max(400, len(df) * 35),
        showlegend=False,
    )
    # Add pass line
    fig_bar.add_vline(
        x=50, line_dash="dash", line_color="rgba(255,255,255,0.3)",
        annotation_text="Pass Line (50%)",
        annotation_position="top",
        annotation_font_color="#888",
    )
    st.plotly_chart(fig_bar, use_container_width=True)

    # ── Row 4: Question-wise Analysis (if real data) ─────────────────────
    if session and session.student_results:
        st.divider()
        st.markdown("#### 📝 Question-wise Performance")

        q_scores = {}
        for r in session.student_results:
            for q in r.results:
                key = f"Q{q.question_number}"
                if key not in q_scores:
                    q_scores[key] = {"awarded": [], "max": q.max_marks}
                q_scores[key]["awarded"].append(q.marks_awarded)

        if q_scores:
            q_df = pd.DataFrame([
                {
                    "Question": k,
                    "Average": np.mean(v["awarded"]),
                    "Max": v["max"],
                    "Avg %": (np.mean(v["awarded"]) / v["max"] * 100) if v["max"] > 0 else 0,
                }
                for k, v in sorted(q_scores.items())
            ])

            fig_q = go.Figure()
            fig_q.add_trace(go.Bar(
                x=q_df["Question"],
                y=q_df["Average"],
                name="Average Score",
                marker_color=primary_chart_color,
                text=q_df["Average"].apply(lambda x: f"{x:.1f}"),
                textposition="outside",
            ))
            fig_q.add_trace(go.Bar(
                x=q_df["Question"],
                y=q_df["Max"],
                name="Max Marks",
                marker_color="rgba(255,255,255,0.1)",
                marker_line=dict(color="rgba(255,255,255,0.3)", width=1),
            ))
            fig_q.update_layout(
                **chart_theme["layout"],
                barmode="overlay",
                yaxis_title="Marks",
                showlegend=True,
                legend=dict(orientation="h", yanchor="bottom", y=-0.15, x=0.3),
            )
            st.plotly_chart(fig_q, use_container_width=True)

    # ── Summary Stats Table ──────────────────────────────────────────────
    st.divider()
    st.markdown("#### 📋 Summary Statistics")
    stats_df = pd.DataFrame({
        "Metric": ["Total Students", "Class Average", "Std Deviation", "Highest Score", "Lowest Score", "Pass Rate"],
        "Value": [
            str(len(df)),
            f"{avg_pct:.1f}%",
            f"{std_dev:.1f}",
            f"{highest:.1f}%",
            f"{lowest:.1f}%",
            f"{pass_rate:.0f}% ({pass_count}/{len(df)})",
        ],
    })
    st.dataframe(stats_df, use_container_width=True, hide_index=True)
