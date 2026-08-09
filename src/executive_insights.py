"""
Executive Intelligence Engine module.

Provides high-level dataset summaries, key findings, top clinical risks,
table-level scores, risk prioritization groupings, and reviewer note tracking
to elevate the platform from raw issue detection to strategic issue understanding.
"""

from typing import Dict, Any, List


def prioritize_issues(issues: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Groups flagged issues into Risk Prioritization categories:
    - High Risk (Critical + High risk levels)
    - Medium Risk (Medium risk levels)
    - Low Risk (Low risk levels)
    """
    high_risk = []
    medium_risk = []
    low_risk = []

    for issue in issues:
        rlevel = issue.get("risk_level", "Medium").lower()
        if rlevel in ("critical", "high"):
            high_risk.append(issue)
        elif rlevel == "medium":
            medium_risk.append(issue)
        else:
            low_risk.append(issue)

    return {
        "high_risk": high_risk,
        "medium_risk": medium_risk,
        "low_risk": low_risk,
        "high_count": len(high_risk),
        "medium_count": len(medium_risk),
        "low_count": len(low_risk)
    }


def compute_table_scores(tables: Dict[str, Any], issues: List[Dict[str, Any]]) -> Dict[str, float]:
    """
    Computes quality scores per MIMIC-IV table (0 - 100).
    """
    table_scores = {}
    for t_name, df in tables.items():
        if not hasattr(df, "__len__"):
            continue
        t_issues = [i for i in issues if i.get("table") == t_name]
        t_rows = len(df) or 100
        # Deduct score proportional to issue severity and count
        penalty = sum(
            30.0 if i.get("risk_level") == "Critical" else
            20.0 if i.get("risk_level") == "High" else
            10.0 if i.get("risk_level") == "Medium" else 5.0
            for i in t_issues
        )
        score = max(0.0, round(100.0 - (penalty / (t_rows / 50.0 + 1)), 1))
        table_scores[t_name] = score
    return table_scores


def generate_executive_insights(
    tables: Dict[str, Any],
    quality_scores: Dict[str, Any],
    issues: List[Dict[str, Any]],
    cohort_info: Dict[str, Any] = None
) -> Dict[str, Any]:
    """
    Generates strategic Executive Insights including:
    - Dataset Summary
    - Key Findings
    - Top Risks
    - Actionable Recommendations
    """
    prioritized = prioritize_issues(issues)
    table_scores = compute_table_scores(tables, issues)

    # Key findings formulation
    key_findings = []
    if prioritized["high_count"] > 0:
        key_findings.append(
            f"Detected {prioritized['high_count']} High/Critical Risk anomalies (e.g. lab outliers or near-duplicate stays) that require immediate review before statistical modeling."
        )
    if quality_scores.get("missing_data_score", 100) < 85:
        key_findings.append("Missing required fields identified across key clinical identifier columns, risking listwise complete-case sample bias.")
    if quality_scores.get("temporal_score", 100) < 85:
        key_findings.append("Cross-table temporal misalignment found between transfer records and hospital admission bounds.")
    if not key_findings:
        key_findings.append("Dataset maintains high integrity across all evaluated baseline rules and statistical AI scans.")

    # Top risks formulation
    top_risks = []
    for iss in prioritized["high_risk"][:4]:
        top_risks.append({
            "table": iss.get("table"),
            "type": iss.get("type"),
            "clinical_impact": iss.get("clinical_impact"),
            "research_impact": iss.get("research_impact"),
            "recommended_action": iss.get("recommended_action")
        })

    # Strategic recommendations
    recommendations = [
        "Audit primary EHR ingestion pipelines for tables with Table Score < 80.0.",
        "Perform human reviewer validation in the Review Queue to resolve pending high-risk flags.",
        "Generate and archive the 1-Click PDF Audit Report for Institutional Review Board (IRB) compliance."
    ]

    total_patients = len(tables.get("patients", [])) if "patients" in tables else 0

    return {
        "dataset_summary": {
            "total_tables": len(tables),
            "total_patients": total_patients,
            "total_issues_flagged": len(issues),
            "overall_trust_score": quality_scores.get("overall_score", 100.0),
            "cohort_score": round(min(100.0, quality_scores.get("overall_score", 100.0) + 5.0), 1)
        },
        "table_scores": table_scores,
        "risk_prioritization": prioritized,
        "key_findings": key_findings,
        "top_risks": top_risks,
        "recommendations": recommendations
    }
