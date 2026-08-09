"""
FastAPI server providing API endpoints for the HTML/CSS/JS MIMIC-IV Explorer Frontend.

Run with:
    python server.py
    or
    uvicorn server:app --reload --port 8000
"""

import os
import sys
from typing import Optional, Dict, Any, List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import pandas as pd

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

app = FastAPI(
    title="MIMIC-IV Cohort & Data Quality Explorer API",
    description="Backend API for the HTML/CSS/JS frontend dashboard",
    version="1.0.0"
)

# Enable CORS for local web development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load data at startup
DATA_DIR, IS_SYNTHETIC = resolve_data_dir()
TABLES, LOAD_REPORT = load_tables(DATA_DIR)


class CohortQueryRequest(BaseModel):
    query: str


class ReviewItemUpdate(BaseModel):
    index: int
    status: str  # 'accepted', 'rejected', or 'pending'
    notes: Optional[str] = ""


@app.get("/api/info")
def get_info():
    """Returns metadata about the active dataset workspace."""
    patient_count = len(TABLES["patients"]) if "patients" in TABLES else 0
    return {
        "data_dir": DATA_DIR,
        "is_synthetic": IS_SYNTHETIC,
        "loaded_tables": list(TABLES.keys()),
        "summary": LOAD_REPORT.summary(),
        "total_patients": patient_count
    }


@app.post("/api/cohort/query")
def process_cohort_query(req: CohortQueryRequest):
    """Parses natural language query and filters patient bundle."""
    if "patients" not in TABLES:
        raise HTTPException(status_code=500, detail="Patients table not loaded.")
    
    cf, unmatched = parse_query(req.query)
    bundle = build_patient_bundle(TABLES)
    matches, clause_counts = apply_filter(bundle, cf)
    
    result_patients = []
    if matches:
        matched_df = TABLES["patients"][TABLES["patients"]["subject_id"].isin(matches)]
        result_patients = matched_df.to_dict(orient="records")
        
        # Format timestamps/dates for JSON
        for p in result_patients:
            for k, v in p.items():
                if pd.isna(v):
                    p[k] = None
                elif hasattr(v, "isoformat"):
                    p[k] = v.isoformat()

    return {
        "clauses": cf.explain(),
        "clause_counts": clause_counts,
        "unmatched": unmatched,
        "total_patients": len(bundle),
        "matched_count": len(matches),
        "patients": result_patients
    }


def sanitize_for_json(obj):
    """Recursively converts numpy numbers and pandas structures to python native types."""
    import numpy as np
    if isinstance(obj, dict):
        return {k: sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [sanitize_for_json(v) for v in obj]
    elif isinstance(obj, (np.integer, np.int64, np.int32)):
        return int(obj)
    elif isinstance(obj, (np.floating, np.float64, np.float32)):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return [sanitize_for_json(v) for v in obj.tolist()]
    elif pd.isna(obj):
        return None
    return obj


@app.get("/api/quality/baseline")
def get_baseline_quality():
    """Runs deterministic baseline rules and enriches with clinical impact."""
    raw_issues = run_baseline(TABLES)
    enriched = explain_all_issues(raw_issues)
    return sanitize_for_json({
        "count": len(enriched),
        "issues": enriched
    })


@app.get("/api/quality/ai")
def get_ai_quality(min_confidence: float = 0.0):
    """Runs AI/ML statistical quality scanner and enriches with clinical impact."""
    raw_issues = run_ai_scanner(TABLES)
    enriched = explain_all_issues(raw_issues)
    if min_confidence > 0:
        enriched = [i for i in enriched if i.get("confidence", 0) >= min_confidence]
    return sanitize_for_json({
        "count": len(raw_issues),
        "filtered_count": len(enriched),
        "issues": enriched
    })


@app.get("/api/quality/scores")
def get_quality_scores():
    """Computes overall and component quality scores."""
    b_issues = explain_all_issues(run_baseline(TABLES))
    a_issues = explain_all_issues(run_ai_scanner(TABLES))
    return sanitize_for_json(compute_quality_scores(TABLES, b_issues, a_issues))


@app.get("/api/executive/insights")
def get_executive_insights_endpoint():
    """Returns strategic Executive Insights, Risk Prioritizations, and Table Scores."""
    b_issues = explain_all_issues(run_baseline(TABLES))
    a_issues = explain_all_issues(run_ai_scanner(TABLES))
    all_issues = b_issues + a_issues
    q_scores = compute_quality_scores(TABLES, b_issues, a_issues)
    
    return sanitize_for_json(generate_executive_insights(TABLES, q_scores, all_issues))


@app.get("/api/quality/lab_distribution")
def get_lab_distribution(item_id: Optional[int] = None):
    """Returns lab value readings, median, and MAD for outlier inspection."""
    if "labevents" not in TABLES or TABLES["labevents"].empty:
        return {"items": [], "data": []}
        
    labevents = TABLES["labevents"]
    d_labitems = TABLES.get("d_labitems", None)
    
    item_counts = labevents["itemid"].value_counts()
    eligible_items = item_counts[item_counts >= 5].index.tolist()
    
    label_map = {}
    if d_labitems is not None and not d_labitems.empty:
        label_map = dict(zip(d_labitems["itemid"], d_labitems["label"]))
        
    items_list = [
        {"itemid": int(iid), "label": label_map.get(iid, f"Item {iid}"), "count": int(item_counts[iid])}
        for iid in eligible_items
    ]
    
    if not eligible_items:
        return {"items": [], "data": []}
        
    target_id = item_id if item_id in eligible_items else eligible_items[0]
    lab_vals = labevents[labevents["itemid"] == target_id]["valuenum"].dropna()
    
    med = float(lab_vals.median()) if not lab_vals.empty else 0.0
    mad = float((lab_vals - med).abs().median()) if not lab_vals.empty else 0.0
    
    return {
        "selected_itemid": int(target_id),
        "selected_label": label_map.get(target_id, f"Item {target_id}"),
        "median": round(med, 2),
        "mad": round(mad, 2),
        "items": items_list,
        "values": lab_vals.tolist()
    }


@app.get("/api/evaluation/metrics")
def get_evaluation_metrics():
    """Runs empirical evaluation comparing Baseline vs AI Scanner."""
    metrics, err = run_evaluation_metrics(DATA_DIR)
    if err:
        raise HTTPException(status_code=400, detail=err)
    return sanitize_for_json(metrics)


@app.get("/api/report/pdf")
def download_pdf_report():
    """Generates and returns downloadable PDF quality audit report."""
    b_issues = explain_all_issues(run_baseline(TABLES))
    a_issues = explain_all_issues(run_ai_scanner(TABLES))
    all_issues = b_issues + a_issues
    scores = compute_quality_scores(TABLES, b_issues, a_issues)
    
    pdf_path = generate_pdf_report(scores, all_issues)
    return FileResponse(
        path=pdf_path,
        filename="MIMIC_Data_Quality_Audit_Report.pdf",
        media_type="application/pdf"
    )


# Mount static directory for HTML/CSS/JS frontend
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("server:app", host="127.0.0.1", port=8000, reload=True)
