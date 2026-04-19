"""Streamlit UI for generating and downloading daily jobs PDFs."""

from __future__ import annotations

from datetime import datetime
import inspect
from typing import Any

import streamlit as st

from job_pdf_automation import run_pipeline


ROLE_OPTIONS = [
    "Data Analyst",
    "Data Scientist",
    "ML Engineer",
    "Business Analyst",
    "Management Trainee MBA",
]
ALL_ROLES_OPTION = "All roles"


def apply_modern_styles() -> None:
    """Inject custom CSS for a modern app look."""
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;700&family=DM+Sans:wght@400;500;700&display=swap');

        :root {
            --bg-a: #0b1220;
            --bg-b: #0f172a;
            --card: rgba(15, 23, 42, 0.78);
            --text-main: #e2e8f0;
            --text-muted: #cbd5e1;
            --brand: #38bdf8;
            --brand-strong: #0284c7;
            --line: rgba(148, 163, 184, 0.24);
        }

        .stApp {
            background:
                radial-gradient(circle at 12% 8%, rgba(56, 189, 248, 0.18), transparent 34%),
                radial-gradient(circle at 88% 12%, rgba(2, 132, 199, 0.15), transparent 32%),
                linear-gradient(135deg, var(--bg-a), var(--bg-b));
            color: var(--text-main);
            font-family: 'DM Sans', sans-serif;
        }

        .block-container {
            max-width: 980px;
            padding-top: 2rem;
            padding-bottom: 2rem;
            animation: fadeSlide 0.55s ease-out;
        }

        @keyframes fadeSlide {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }

        h1, h2, h3 {
            font-family: 'Space Grotesk', sans-serif;
            letter-spacing: -0.02em;
            color: var(--text-main);
        }

        .hero {
            background: linear-gradient(135deg, rgba(15, 23, 42, 0.9), rgba(2, 6, 23, 0.85));
            border: 1px solid var(--line);
            border-radius: 20px;
            padding: 1.3rem 1.2rem;
            backdrop-filter: blur(4px);
            box-shadow: 0 14px 30px rgba(2, 6, 23, 0.35);
            margin-bottom: 1rem;
        }

        .hero p {
            color: var(--text-main);
            margin: 0.4rem 0 0 0;
            font-size: 0.98rem;
        }

        .metric-card {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0.8rem 0.95rem;
            margin-bottom: 0.65rem;
            box-shadow: 0 8px 20px rgba(18, 35, 38, 0.06);
        }

        .metric-label {
            color: var(--text-main);
            font-size: 0.8rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            margin-bottom: 0.18rem;
        }

        .metric-value {
            color: var(--text-main);
            font-size: 1.2rem;
            font-weight: 700;
            font-family: 'Space Grotesk', sans-serif;
            line-height: 1.2;
        }

        .report-item {
            background: var(--card);
            border: 1px solid var(--line);
            border-radius: 14px;
            padding: 0.72rem 0.78rem;
            margin-bottom: 0.6rem;
        }

        .controls-wrap {
            background: rgba(15, 23, 42, 0.72);
            border: 1px solid var(--line);
            border-radius: 16px;
            padding: 0.85rem 0.95rem 0.35rem 0.95rem;
            margin-bottom: 0.8rem;
            box-shadow: 0 12px 22px rgba(2, 6, 23, 0.35);
        }

        .controls-wrap h3,
        .controls-wrap label,
        .controls-wrap p,
        .controls-wrap span {
            color: #ffffff !important;
        }

        .controls-wrap [data-testid="stWidgetLabel"] {
            color: #ffffff !important;
        }

        .controls-wrap [data-testid="stCheckbox"] span,
        .controls-wrap [data-testid="stMultiSelect"] span,
        .controls-wrap [data-testid="stSelectbox"] span {
            color: #ffffff !important;
        }

        .controls-wrap [data-baseweb="select"] > div {
            background-color: #1e293b !important;
            color: var(--text-main) !important;
            border-color: rgba(148, 163, 184, 0.35) !important;
        }

        .controls-wrap [data-baseweb="select"] * {
            color: var(--text-main) !important;
        }

        .controls-wrap input,
        .controls-wrap textarea {
            color: var(--text-main) !important;
            background-color: #1e293b !important;
        }

        .controls-wrap [data-testid="stCheckbox"] label,
        .controls-wrap [data-testid="stMultiSelect"] label,
        .controls-wrap [data-testid="stSelectbox"] label {
            color: var(--text-main) !important;
        }

        .controls-wrap [role="radiogroup"],
        .controls-wrap [data-baseweb="tag"] {
            color: var(--text-main) !important;
            background-color: rgba(30, 41, 59, 0.9) !important;
        }

        .report-name {
            color: var(--text-main);
            font-weight: 600;
            margin-bottom: 0.25rem;
        }

        .report-meta {
            color: var(--text-main);
            font-size: 0.84rem;
        }

        .stMarkdown, .stCaption, .stInfo, .stSuccess, .stWarning, .stError {
            color: var(--text-main) !important;
        }

        .stButton > button, .stDownloadButton > button {
            border-radius: 12px;
            border: 1px solid rgba(56, 189, 248, 0.65);
            background: linear-gradient(180deg, var(--brand), var(--brand-strong));
            color: #eaf6ff;
            font-weight: 600;
            transition: transform 0.18s ease, box-shadow 0.18s ease;
        }

        .stButton > button:hover, .stDownloadButton > button:hover {
            transform: translateY(-1px);
            box-shadow: 0 10px 20px rgba(2, 132, 199, 0.4);
        }

        @media (max-width: 768px) {
            .hero { padding: 1rem; }
            .metric-value { font-size: 1.1rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_metric_card(label: str, value: Any) -> None:
    """Render a small metric card."""
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def run_pipeline_compatible(**kwargs):
    """Call run_pipeline with only supported keyword args for deployment compatibility."""
    accepted = inspect.signature(run_pipeline).parameters
    filtered_kwargs = {key: value for key, value in kwargs.items() if key in accepted}
    return run_pipeline(**filtered_kwargs)


st.set_page_config(page_title="Daily Job PDF Automation", page_icon="PDF", layout="centered")
apply_modern_styles()

st.markdown(
    """
    <div class="hero">
        <h1 style="margin:0;">Daily Job Opportunities</h1>
        <p>
            Fetch fresh jobs with live progress and filter by role and experience.
            Results appear below with links and fetch time.
        </p>
    </div>
    """,
    unsafe_allow_html=True,
)

if "latest_result" not in st.session_state:
    st.session_state["latest_result"] = None

st.markdown('<div class="controls-wrap">', unsafe_allow_html=True)
st.markdown("### Fetch Controls")

ctrl_col1, ctrl_col2 = st.columns(2)
with ctrl_col1:
    use_mock = st.checkbox("Use mock data", value=False, help="Use sample jobs instead of live scraping.")
    experience_level = st.selectbox(
        "Experience",
        options=["Fresher", "0 to 2 years", "More experience"],
        index=1,
        help="Filter jobs by required experience level.",
    )

with ctrl_col2:
    selected_role_options = st.multiselect(
        "Roles",
        options=[ALL_ROLES_OPTION] + ROLE_OPTIONS,
        default=[ALL_ROLES_OPTION],
        help="Select specific roles, or keep 'All roles' selected.",
    )

if not selected_role_options or ALL_ROLES_OPTION in selected_role_options:
    selected_roles = ROLE_OPTIONS
else:
    selected_roles = selected_role_options

trigger_generate = st.button("Fetch Jobs", type="primary", use_container_width=True)
st.markdown('</div>', unsafe_allow_html=True)

if trigger_generate:
    progress_placeholder = st.empty()
    progress_bar = progress_placeholder.progress(0, text="0% - Starting fetch...")

    def on_progress(completed: int, total: int, status_message: str) -> None:
        percent = int((completed / total) * 100) if total else 0
        progress_bar.progress(percent, text=f"{percent}% - {status_message}")

    with st.spinner("Fetching jobs..."):
        st.session_state["latest_result"] = run_pipeline_compatible(
            use_mock=use_mock,
            experience_level=experience_level,
            role_queries=selected_roles,
            generate_pdf=False,
            allow_mock_fallback=False,
            progress_callback=on_progress,
        )

    progress_bar.progress(100, text="100% - Fetch complete")

result = st.session_state.get("latest_result")

if result:
    fetched_at_text = result["fetched_at"].strftime("%Y-%m-%d %H:%M:%S")
    jobs = result["jobs"]

    st.success("Job fetching completed.")
    c1, c2, c3 = st.columns(3)
    with c1:
        render_metric_card("Fetched At", fetched_at_text)
    with c2:
        render_metric_card("Experience", result["experience_level"])
    with c3:
        render_metric_card("Total Included", result["total_included"])

    st.caption(f"Total jobs fetched before filtering: {result['total_fetched']}")
    st.caption(f"Roles used: {', '.join(result['role_queries'])}")

    st.markdown("### Fetched Job List")

    if not jobs:
        if result.get("used_mock_data"):
            st.warning("No live jobs found; showing mock data.")
        else:
            st.warning(
                "No live jobs were fetched for your filters in this run. "
                "Try changing roles/location filters, or enable 'Use mock data' for testing."
            )
    else:
        for job in jobs:
            st.markdown(
                f"""
                <div class="report-item">
                    <div class="report-name">{job.title}</div>
                    <div class="report-meta">
                        {job.company} | {job.location} | {job.experience} | {job.source}<br>
                        Fetched at: {fetched_at_text}<br>
                        <a href="{job.apply_link}" target="_blank">Open job link</a>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )
else:
    st.info("Use Fetch Controls above to start fetching jobs.")
