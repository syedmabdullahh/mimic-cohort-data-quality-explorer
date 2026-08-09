"""
MIMIC-IV Cohort & Data Quality Explorer — Modern Clinical SaaS Suite
Sofstica Hackathon 2026 -- AI for Smarter Patient Care, Track 2

Research and educational prototype only. Not for clinical use. Do not use
for diagnosis, treatment, triage, or emergency decisions.

Run with:
    streamlit run app.py
"""

import os
import sys

import pandas as pd
import streamlit as st

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "scripts"))

from data_loader import load_tables, resolve_data_dir  # noqa: E402
from baseline_rules import run_baseline, issues_to_df as baseline_to_df  # noqa: E402
from quality_scanner import run_ai_scanner, issues_to_df as ai_to_df  # noqa: E402
from cohort_query import parse_query, build_patient_bundle, apply_filter  # noqa: E402
from run_evaluation import run_evaluation_metrics  # noqa: E402
from impact_explainer import explain_all_issues  # noqa: E402
from quality_score import compute_quality_scores  # noqa: E402
from report_generator import generate_pdf_report  # noqa: E402
from executive_insights import generate_executive_insights, prioritize_issues  # noqa: E402

# ---------------------------------------------------------------------------
# Page Configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="MIMIC-IV AI Clinical Analytics Suite",
    page_icon="🏥",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ---------------------------------------------------------------------------
# Custom CSS Design System (Healthcare-Grade Dark Theme & Micro-Interactions)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@400;500;600;700;800&family=Plus+Jakarta+Sans:wght@400;500;600;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Plus Jakarta Sans', sans-serif;
    }
    
    h1, h2, h3, h4, h5, h6 {
        font-family: 'Outfit', sans-serif !important;
    }
    
    /* Top Hero Header Bar */
    .hero-header {
        background: linear-gradient(135deg, rgba(15, 23, 42, 0.95) 0%, rgba(30, 41, 59, 0.9) 100%);
        border: 1px solid rgba(56, 189, 248, 0.3);
        border-radius: 16px;
        padding: 28px;
        margin-bottom: 20px;
        box-shadow: 0 10px 30px -10px rgba(0, 0, 0, 0.5);
    }
    .hero-title {
        color: #f8fafc;
        font-size: 2.2rem;
        font-weight: 800;
        margin: 0;
        letter-spacing: -0.02em;
    }
    .hero-subtitle {
        color: #38bdf8;
        font-size: 1.05rem;
        font-weight: 500;
        margin-top: 4px;
    }
    .hero-badge {
        display: inline-block;
        background: rgba(56, 189, 248, 0.15);
        color: #38bdf8;
        border: 1px solid rgba(56, 189, 248, 0.3);
        padding: 4px 14px;
        border-radius: 20px;
        font-size: 0.82rem;
        font-weight: 700;
        margin-top: 10px;
    }

    /* Glassmorphism Safety Warning Banner */
    .safety-alert {
        background: rgba(254, 243, 199, 0.08);
        border-left: 4px solid #fbbf24;
        border: 1px solid rgba(251, 191, 36, 0.2);
        border-left-width: 4px;
        color: #fef3c7;
        border-radius: 10px;
        padding: 14px 20px;
        margin-bottom: 24px;
        font-size: 0.92rem;
    }

    /* Executive Score Cards */
    .exec-card {
        background: rgba(30, 41, 59, 0.7);
        border: 1px solid rgba(255, 255, 255, 0.08);
        border-radius: 14px;
        padding: 20px;
        text-align: center;
        box-shadow: 0 4px 15px rgba(0,0,0,0.2);
    }
    .exec-card.main {
        border-color: #38bdf8;
        background: rgba(56, 189, 248, 0.1);
    }

    /* Risk Pill Badges */
    .risk-pill {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.75rem;
        font-weight: 700;
        text-transform: uppercase;
    }
    .risk-critical { background: rgba(248, 113, 113, 0.2); color: #f87171; border: 1px solid #f87171; }
    .risk-high { background: rgba(251, 191, 36, 0.2); color: #fbbf24; border: 1px solid #fbbf24; }
    .risk-medium { background: rgba(56, 189, 248, 0.2); color: #38bdf8; border: 1px solid #38bdf8; }
    .risk-low { background: rgba(52, 211, 153, 0.2); color: #34d399; border: 1px solid #34d399; }
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Data Loading & Initialization
# ---------------------------------------------------------------------------
data_dir, is_synthetic = resolve_data_dir()

@st.cache_data
def _load(data_dir):
    tables, report = load_tables(data_dir)
    return tables, report.summary()

tables, load_summary = _load(data_dir)

if "patients" not in tables:
    st.error("Could not load the `patients` table. Please verify workspace data.")
    st.stop()

# Auto-compute issue states for seamless dashboard rendering
if "baseline_issues" not in st.session_state:
    st.session_state["baseline_issues"] = explain_all_issues(run_baseline(tables))
if "ai_issues" not in st.session_state:
    st.session_state["ai_issues"] = explain_all_issues(run_ai_scanner(tables))

baseline_issues = st.session_state["baseline_issues"]
ai_issues = st.session_state["ai_issues"]
all_issues = baseline_issues + ai_issues

quality_scores = compute_quality_scores(tables, baseline_issues, ai_issues)
exec_insights = generate_executive_insights(tables, quality_scores, all_issues)
prioritized = prioritize_issues(all_issues)

# ---------------------------------------------------------------------------
# Sidebar Navigation & Settings
# ---------------------------------------------------------------------------
with st.sidebar:
    st.image("https://img.icons8.com/isometric-folders/100/health-data.png", width=64)
    st.title("MIMIC Explorer")
    st.caption("AI CLINICAL SAITE v2.5")

    # One-Click Judge Demo Mode Trigger
    if st.button("⚡ 1-Click Judge Demo Mode", type="primary", width="stretch"):
        st.session_state["baseline_issues"] = explain_all_issues(run_baseline(tables))
        st.session_state["ai_issues"] = explain_all_issues(run_ai_scanner(tables))
        metrics, _ = run_evaluation_metrics(data_dir)
        if metrics:
            st.session_state["eval_metrics"] = metrics
        st.success("⚡ One-Click Demo Mode Complete! All engines populated.")
        st.rerun()

    st.markdown("---")
    st.markdown("### ⚙️ Lineage & Dataset")
    st.code(data_dir, language="text")
    
    if is_synthetic:
        st.warning("⚡ Status: SYNTHETIC Placeholder Data")
    else:
        st.success("✅ Status: Real MIMIC-IV Demo Loaded")

    if st.button("🔄 Reload Workspace Data", width="stretch"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")
    st.markdown("### 📄 Export Deliverable")
    if st.button("📥 Generate PDF Audit Report", width="stretch"):
        pdf_path = generate_pdf_report(quality_scores, all_issues)
        with open(pdf_path, "rb") as f:
            st.download_button(
                label="⬇️ Download PDF Audit Report",
                data=f.read(),
                file_name="MIMIC_Data_Quality_Audit_Report.pdf",
                mime="application/pdf",
                width="stretch"
            )

# ---------------------------------------------------------------------------
# Header Hero & Safety Notice
# ---------------------------------------------------------------------------
st.markdown(
    """
    <div class="hero-header">
        <div class="hero-title">🏥 MIMIC-IV Cohort & Data Quality Explorer</div>
        <div class="hero-subtitle">Sofstica Hackathon 2026 · AI for Smarter Patient Care · Track 2 Submission</div>
        <div class="hero-badge">Healthcare-Grade AI Quality Audit & Natural Language Cohort Engine</div>
    </div>
    <div class="safety-alert">
        <strong>⚠️ Research and educational prototype only. Not for clinical use.</strong>
        Do not use for diagnosis, treatment, triage, or emergency decisions. Data derived from MIMIC-IV Demo v2.2.
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# 6 Main Navigation Hub Tabs
# ---------------------------------------------------------------------------
nav_tab1, nav_tab2, nav_tab3, nav_tab4, nav_tab5, nav_tab6 = st.tabs([
    "📊 Executive Dashboard",
    "🔎 Cohort Explorer",
    "🛡️ AI Data Quality Center",
    "🏥 Clinical Impact Center",
    "📋 Human Review Workspace",
    "📈 Reports & Benchmarks"
])

# ---------------------------------------------------------------------------
# PAGE 1: EXECUTIVE DASHBOARD
# ---------------------------------------------------------------------------
with nav_tab1:
    st.subheader("Executive Intelligence Overview")
    st.caption("High-level dataset health metrics, risk distributions, and key clinical findings.")

    # Top KPI Metrics Cards
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Overall Trust Score", f"{quality_scores['overall_score']} / 100", delta="Dataset Health")
    kpi2.metric("Total Patients", exec_insights["dataset_summary"]["total_patients"])
    kpi3.metric("Total Issues Flagged", exec_insights["dataset_summary"]["total_issues_flagged"])
    kpi4.metric("High/Critical Risks", prioritized["high_count"], delta_color="inverse")
    kpi5.metric("Cohort Health Index", f"{exec_insights['dataset_summary']['cohort_score']} / 100")

    st.markdown("---")

    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        st.markdown("#### 🎯 Risk Level Distribution")
        risk_df = pd.DataFrame([
            {"Risk Category": "High / Critical", "Count": prioritized["high_count"]},
            {"Risk Category": "Medium Risk", "Count": prioritized["medium_count"]},
            {"Risk Category": "Low Risk", "Count": prioritized["low_count"]},
        ]).set_index("Risk Category")
        st.bar_chart(risk_df)

    with col_chart2:
        st.markdown("#### 📋 Quality Component Scores")
        component_df = pd.DataFrame([
            {"Sub-Score": "Missingness", "Score": quality_scores["missing_data_score"]},
            {"Sub-Score": "Uniqueness", "Score": quality_scores["duplicate_score"]},
            {"Sub-Score": "Temporal", "Score": quality_scores["temporal_score"]},
            {"Sub-Score": "Plausibility", "Score": quality_scores["outlier_score"]},
        ]).set_index("Sub-Score")
        st.bar_chart(component_df)

    st.markdown("---")
    st.markdown("#### 💡 Executive Key Findings & Strategic Recommendations")
    f_col, r_col = st.columns(2)
    with f_col:
        st.markdown("##### Key Dataset Findings")
        for finding in exec_insights["key_findings"]:
            st.info(f"• {finding}")
    with r_col:
        st.markdown("##### Strategic Governance Actions")
        for rec in exec_insights["recommendations"]:
            st.success(f"• {rec}")

# ---------------------------------------------------------------------------
# PAGE 2: COHORT EXPLORER
# ---------------------------------------------------------------------------
with nav_tab2:
    st.subheader("Natural Language Cohort Builder & Query Engine")
    st.caption("Transparent query builder mapping natural language into explicit inclusion logic.")

    example_query = "age over 65 and diagnosis of sepsis"
    query_text = st.text_input("Enter natural language cohort query target:", value=example_query)

    if query_text:
        cf, unmatched = parse_query(query_text)
        bundle = build_patient_bundle(tables)
        matches, clause_counts = apply_filter(bundle, cf)

        c_m1, c_m2, c_m3 = st.columns(3)
        c_m1.metric("Matched Cohort Patients", len(matches))
        c_m2.metric("Total Dataset Patients", len(bundle))
        c_m3.metric("Inclusion Percentage", f"{(len(matches)/len(bundle))*100:.1f}%" if bundle else "0%")

        st.markdown("#### 📜 Filter Clause Match Breakdown")
        if cf.clauses:
            explanations = cf.explain()
            chart_data = []
            for desc in explanations:
                cnt = clause_counts.get(desc, 0)
                st.write(f"- **{desc}** → matched **{cnt}** patient(s)")
                chart_data.append({"Filter Clause": desc, "Matched Patients": cnt})

            if chart_data:
                st.bar_chart(pd.DataFrame(chart_data).set_index("Filter Clause"))
        else:
            st.info("No recognized clauses. Try patterns like 'age over 65', 'gender female', 'diagnosis of sepsis'.")

        if unmatched:
            st.warning(f"⚠️ Could not interpret tokens: \"{unmatched[0]}\" (ignored from filter).")

        if matches:
            st.markdown("#### 👥 Matching Patient Cohort Table")
            result_df = tables["patients"][tables["patients"]["subject_id"].isin(matches)]
            st.dataframe(result_df, width="stretch", height=350)

# ---------------------------------------------------------------------------
# PAGE 3: AI DATA QUALITY CENTER
# ---------------------------------------------------------------------------
with nav_tab3:
    st.subheader("AI Quality Scanner & Anomaly Detector")
    st.caption("Statistical MAD Z-scores, near-duplicate overlap analysis, and cross-table temporal drift.")

    btn_col1, btn_col2 = st.columns(2)
    with btn_col1:
        if st.button("▶ Run Baseline Checks", width="stretch"):
            st.session_state["baseline_issues"] = explain_all_issues(run_baseline(tables))
            st.rerun()
    with btn_col2:
        if st.button("⚡ Run AI Quality Scanner", type="primary", width="stretch"):
            st.session_state["ai_issues"] = explain_all_issues(run_ai_scanner(tables))
            st.rerun()

    b_col, a_col = st.columns(2)
    with b_col:
        st.metric("Baseline Hardcoded Flags", len(baseline_issues))
        if baseline_issues:
            st.dataframe(baseline_to_df(baseline_issues), width="stretch", height=280)
    with a_col:
        st.metric("AI Statistical Flags", len(ai_issues))
        if ai_issues:
            ai_df = ai_to_df(ai_issues).sort_values("confidence", ascending=False)
            min_conf = st.slider("Confidence score filter threshold:", 0.0, 1.0, 0.4, 0.05)
            filtered_df = ai_df[ai_df["confidence"] >= min_conf]
            st.dataframe(filtered_df, width="stretch", height=280)

    # Interactive Lab Distribution Explainability Visual
    if "labevents" in tables and not tables["labevents"].empty and "d_labitems" in tables:
        st.markdown("---")
        st.markdown("#### 🔬 Visual Lab Value Explainability (Robust Z-score vs MAD)")
        labevents = tables["labevents"]
        d_labitems = tables["d_labitems"]
        
        item_counts = labevents["itemid"].value_counts()
        eligible_items = item_counts[item_counts >= 5].index.tolist()
        
        if eligible_items:
            item_labels = dict(zip(d_labitems["itemid"], d_labitems["label"]))
            selected_item = st.selectbox(
                "Select Lab Measurement to Inspect Distribution:",
                options=eligible_items,
                format_func=lambda x: f"{item_labels.get(x, f'Item {x}')} (ID: {x})"
            )
            
            lab_data = labevents[labevents["itemid"] == selected_item]["valuenum"].dropna()
            if not lab_data.empty:
                med = lab_data.median()
                mad = (lab_data - med).abs().median()
                
                lm1, lm2, lm3 = st.columns(3)
                lm1.metric("Median", f"{med:.2f}")
                lm2.metric("Median Abs Dev (MAD)", f"{mad:.2f}")
                lm3.metric("Total Readings", len(lab_data))
                
                st.area_chart(lab_data.reset_index(drop=True))

    if ai_issues:
        st.markdown("---")
        if st.button("📥 Route AI Flags to Human Review Queue", type="primary", width="stretch"):
            queue = st.session_state.get("review_queue", [])
            for issue in ai_issues:
                issue_dict = dict(issue)
                issue_dict["status"] = "pending"
                queue.append(issue_dict)
            st.session_state["review_queue"] = queue
            st.success(f"Routed {len(ai_issues)} flags to review queue.")

# ---------------------------------------------------------------------------
# PAGE 4: CLINICAL IMPACT CENTER
# ---------------------------------------------------------------------------
with nav_tab4:
    st.subheader("Clinical & Research Risk Explainer Center")
    st.caption("Actionable breakdown mapping data anomalies to patient safety and research bias risks.")

    if all_issues:
        for idx, iss in enumerate(all_current_issues := (baseline_issues + ai_issues)):
            r_level = iss.get("risk_level", "Medium")
            with st.expander(f"[{r_level.upper()} RISK] Table: {iss.get('table')} — Type: {iss.get('type')}"):
                st.markdown(f"**Anomaly Detail:** {iss.get('detail')}")
                st.markdown(f"**🏥 Clinical Impact:** {iss.get('clinical_impact')}")
                st.markdown(f"**🔬 Research Bias Risk:** {iss.get('research_impact')}")
                st.markdown(f"**🛠️ Recommended Action:** {iss.get('recommended_action')}")
                st.json(iss.get("row_ref", {}))

# ---------------------------------------------------------------------------
# PAGE 5: HUMAN REVIEW WORKSPACE
# ---------------------------------------------------------------------------
with nav_tab5:
    st.subheader("Human-in-the-Loop Reversible Audit Workspace")
    st.caption("Review flagged issues without mutating source files. Actions update audit state in real time.")

    queue = st.session_state.get("review_queue", [])
    if not queue:
        st.info("No items in review queue. Run AI Scanner in Tab 3 to populate flags.")
    else:
        for i, item in enumerate(queue):
            with st.expander(f"[{item['status'].upper()}] {item['type']} — {item['table']} (Confidence: {item.get('confidence', 'N/A')})"):
                st.write(item["detail"])
                st.markdown(f"**Clinical Impact:** {item.get('clinical_impact', 'N/A')}")
                st.markdown(f"**Recommended Action:** {item.get('recommended_action', 'N/A')}")
                st.json(item["row_ref"])
                
                notes = st.text_input("Reviewer Notes & Action Justification:", value=item.get("notes", ""), key=f"notes_{i}")
                queue[i]["notes"] = notes
                
                c1, c2, c3 = st.columns(3)
                if c1.button("✅ Accept Flag", key=f"accept_{i}"):
                    queue[i]["status"] = "accepted"
                    st.rerun()
                if c2.button("❌ Reject Flag", key=f"reject_{i}"):
                    queue[i]["status"] = "rejected"
                    st.rerun()
                if c3.button("🔄 Reset", key=f"reset_{i}"):
                    queue[i]["status"] = "pending"
                    st.rerun()
                    
        st.session_state["review_queue"] = queue

        statuses = pd.Series([q["status"] for q in queue]).value_counts()
        st.markdown("#### Queue Status Breakdown")
        st.bar_chart(statuses)

# ---------------------------------------------------------------------------
# PAGE 6: REPORTS & BENCHMARKS
# ---------------------------------------------------------------------------
with nav_tab6:
    st.subheader("📊 Empirical Evaluation & Audit Reports")
    st.caption("Performance benchmarks against ground-truth seeded issues (Track 2 requirement).")

    if st.button("🚀 Run Live Metric Evaluation", type="primary", width="stretch"):
        metrics, err = run_evaluation_metrics(data_dir)
        if err:
            st.error(err)
        else:
            st.session_state["eval_metrics"] = metrics
            st.rerun()

    eval_metrics = st.session_state.get("eval_metrics", None)
    if eval_metrics:
        b_score = eval_metrics["baseline_score"]
        a_score = eval_metrics["ai_score"]

        m1, m2, m3 = st.columns(3)
        m1.metric("Recall (Detection Rate)", f"{a_score['recall']:.1%}", delta=f"{(a_score['recall'] - b_score['recall']):.1%}")
        m2.metric("Precision Proxy", f"{a_score['precision_proxy']:.1%}", delta=f"{(a_score['precision_proxy'] - b_score['precision_proxy']):.1%}")
        m3.metric("F1 Score Proxy", f"{a_score['f1_proxy']:.1%}", delta=f"{(a_score['f1_proxy'] - b_score['f1_proxy']):.1%}")

        st.markdown("#### Complete Evaluation Matrix")
        summary_df = pd.DataFrame([
            {"Model": "Baseline (Deterministic)", **b_score},
            {"Model": "AI Scanner (Statistical/ML)", **a_score},
        ]).set_index("Model")
        st.dataframe(summary_df, width="stretch")

        st.markdown("#### Seeded Ground-Truth Issues Dataset")
        st.json(eval_metrics["seeds"])

st.divider()
st.caption("Data Lineage: Absolute data immutability preserved. Research prototype for Sofstica Hackathon 2026.")
