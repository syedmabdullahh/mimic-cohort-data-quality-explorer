"""
Clinical Impact Explainer module.

Translates technical data-quality flags (z-score outliers, temporal mismatches,
duplicates, missing fields) into actionable clinical risk, research impact,
risk levels, and recommended mitigation actions for healthcare researchers.
"""

from typing import Dict, Any


IMPACT_RULES = {
    "missing_required_field": {
        "risk_level": "Medium",
        "clinical_impact": "Loss of critical clinical context (e.g. missing demographic, admission, or lab timestamps) preventing full longitudinal patient trajectory tracking.",
        "research_impact": "Introduces selection bias or missingness bias during multivariate analysis; forces listwise deletion or complex imputation.",
        "recommended_action": "Audit primary data pipeline ingestion; filter rows with missing key identifiers or apply verified domain-specific imputation."
    },
    "duplicate_row": {
        "risk_level": "High",
        "clinical_impact": "Artificial duplication of clinical encounters or medication administration records, risking double-counting of patient morbidity.",
        "research_impact": "Skews statistical variance, pseudoreplication in regression models, and artificially inflates cohort sample counts.",
        "recommended_action": "Deduplicate exact matching records preserving earliest entry timestamp; flag database primary key integrity."
    },
    "near_duplicate_admission": {
        "risk_level": "High",
        "clinical_impact": "Overlapping hospital encounter records for the same patient, causing confused readmission rates and resource utilization metrics.",
        "research_impact": "Distorts length-of-stay distributions, hospital mortality rates, and readmission risk prediction models.",
        "recommended_action": "Consolidate overlapping encounter records into a single continuous hospital episode; audit registration system logs."
    },
    "implausible_value": {
        "risk_level": "Critical",
        "clinical_impact": "Extreme physiological or lab measurement outliers (e.g., severe electrolyte anomaly or extreme blood pressure) that may reflect measurement error.",
        "research_impact": "Distorts mean/std statistics, heavily skews machine learning feature scaling, and leads to false extreme acuity cohort exclusions.",
        "recommended_action": "Inspect sensor/device calibration; cross-reference secondary lab orders or winnow extreme z-score outliers (z > 4.0)."
    },
    "temporal_misalignment": {
        "risk_level": "High",
        "clinical_impact": "Discharge time precedes admission time or event out-of-order within a single table encounter.",
        "research_impact": "Invalidates time-to-event survival modeling (e.g., Kaplan-Meier estimation, Cox proportional hazards).",
        "recommended_action": "Correct timestamp ordering using audit log metadata; drop negative duration records from survival cohorts."
    },
    "cross_table_temporal_inconsistency": {
        "risk_level": "High",
        "clinical_impact": "Transfer or ICU stay timestamps occurring outside the parent hospital admission timeframe.",
        "research_impact": "Invalidates longitudinal trajectory alignment between ward transfers and overall hospital stay duration.",
        "recommended_action": "Re-align transfer event windows against verified admission and discharge timestamps."
    },
    "categorical_normalization_issue": {
        "risk_level": "Low",
        "clinical_impact": "Inconsistent string formatting (e.g., 'WHITE' vs 'White ') causing fragmented categorical groupings.",
        "research_impact": "Fragmented cohort stratification leading to reduced statistical power in sub-group demographic analysis.",
        "recommended_action": "Apply automated string normalization (uppercase trimming) to harmonize categorical fields."
    }
}


def explain_issue(issue: Dict[str, Any]) -> Dict[str, Any]:
    """
    Enriches an issue dictionary (from baseline or AI scanner) with:
    - risk_level ("Critical", "High", "Medium", "Low")
    - clinical_impact
    - research_impact
    - recommended_action
    """
    issue_type = issue.get("type", "")
    rule = IMPACT_RULES.get(issue_type, {
        "risk_level": "Medium",
        "clinical_impact": f"Data quality anomaly detected in table '{issue.get('table', 'unknown')}'. Potential loss of clinical fidelity.",
        "research_impact": "May introduce noise or bias into downstream epidemiological analysis.",
        "recommended_action": "Perform manual chart review or dataset audit for flagged row reference."
    })

    enriched = dict(issue)
    enriched["risk_level"] = rule["risk_level"]
    enriched["clinical_impact"] = rule["clinical_impact"]
    enriched["research_impact"] = rule["research_impact"]
    enriched["recommended_action"] = rule["recommended_action"]
    return enriched


def explain_all_issues(issues: list) -> list:
    """Enriches a list of issue dictionaries."""
    return [explain_issue(iss) for iss in issues]
