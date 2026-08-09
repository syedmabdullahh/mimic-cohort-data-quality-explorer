"""
Quality Score Engine module.

Calculates a comprehensive composite Dataset Quality Score (0 - 100)
along with individual sub-scores for Missing Data, Duplicates,
Temporal Consistency, and Outliers based on flagged issues across MIMIC-IV tables.
"""

from typing import Dict, Any, List


def compute_quality_scores(tables: Dict[str, Any], baseline_issues: List[Dict[str, Any]], ai_issues: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Computes overall and sub-category data quality scores (0 to 100 scale).

    Sub-scores:
    1. missing_data_score: Deducts points based on missing required fields.
    2. duplicate_score: Deducts points for exact and near-duplicate records.
    3. temporal_score: Deducts points for within-table and cross-table time mismatches.
    4. outlier_score: Deducts points for implausible lab/vital outliers.
    5. overall_score: Weighted combination of the sub-scores.
    """
    all_issues = baseline_issues + ai_issues

    # Categorize issues
    missing_count = sum(1 for i in all_issues if i.get("type") == "missing_required_field")
    dup_count = sum(1 for i in all_issues if i.get("type") in ("duplicate_row", "near_duplicate_admission"))
    temporal_count = sum(1 for i in all_issues if i.get("type") in ("temporal_misalignment", "cross_table_temporal_inconsistency"))
    outlier_count = sum(1 for i in all_issues if i.get("type") == "implausible_value")
    norm_count = sum(1 for i in all_issues if i.get("type") == "categorical_normalization_issue")

    # Base dataset size scale (estimate total rows)
    total_rows = sum(len(df) for df in tables.values() if hasattr(df, "__len__")) or 1000

    # Sub-score calculations (100 max, scaling penalty by issue prevalence)
    # Penalty factor scales issue density against total records
    missing_score = max(0.0, round(100.0 - (missing_count * 15.0 / (total_rows / 100.0 + 1)), 1))
    duplicate_score = max(0.0, round(100.0 - (dup_count * 20.0 / (total_rows / 100.0 + 1)), 1))
    temporal_score = max(0.0, round(100.0 - (temporal_count * 18.0 / (total_rows / 100.0 + 1)), 1))
    outlier_score = max(0.0, round(100.0 - (outlier_count * 12.0 / (total_rows / 100.0 + 1)), 1))

    # Overall weighted score
    overall_score = round(
        0.25 * missing_score +
        0.25 * duplicate_score +
        0.25 * temporal_score +
        0.25 * outlier_score,
        1
    )

    # Risk level summary
    risk_counts = {"Critical": 0, "High": 0, "Medium": 0, "Low": 0}
    for iss in all_issues:
        itype = iss.get("type", "")
        if itype == "implausible_value":
            risk_counts["Critical"] += 1
        elif itype in ("duplicate_row", "near_duplicate_admission", "temporal_misalignment", "cross_table_temporal_inconsistency"):
            risk_counts["High"] += 1
        elif itype == "missing_required_field":
            risk_counts["Medium"] += 1
        else:
            risk_counts["Low"] += 1

    return {
        "overall_score": overall_score,
        "missing_data_score": missing_score,
        "duplicate_score": duplicate_score,
        "temporal_score": temporal_score,
        "outlier_score": outlier_score,
        "total_issues_count": len(all_issues),
        "issue_type_counts": {
            "missing_data": missing_count,
            "duplicates": dup_count,
            "temporal": temporal_count,
            "outliers": outlier_count,
            "normalization": norm_count,
        },
        "risk_counts": risk_counts
    }
