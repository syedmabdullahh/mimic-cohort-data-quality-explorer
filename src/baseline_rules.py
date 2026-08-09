"""
Deterministic, non-AI baseline data-quality checks.

The Sofstica AI for Smarter Patient Care brief requires every submission to
"compare the AI method with a simple, relevant baseline or rule-based
approach." This module IS that baseline: fixed regex/range/null checks with
no learned parameters, no statistics fit on the data, and no confidence
scoring. The quality_scanner.py module extends this with statistical/ML
methods and is evaluated against this baseline in evaluate.py.

Each check returns a list of flagged issues in a common format:
{
    "table": str,
    "row_ref": dict,        # identifying columns for the flagged row
    "type": str,            # issue category
    "detail": str,          # human-readable explanation
    "source": "baseline",
}
"""

import pandas as pd


def _ref(row, id_cols):
    return {c: row.get(c) for c in id_cols if c in row}


def check_missing_required(df, table_name, required_cols, id_cols):
    issues = []
    for col in required_cols:
        if col not in df.columns:
            continue
        missing = df[df[col].isna()]
        for _, row in missing.iterrows():
            issues.append({
                "table": table_name,
                "row_ref": _ref(row, id_cols),
                "type": "missing_required_field",
                "detail": f"Required field '{col}' is null/blank.",
                "source": "baseline",
            })
    return issues


def check_exact_duplicates(df, table_name, id_cols):
    issues = []
    dup_mask = df.duplicated(keep="first")
    for _, row in df[dup_mask].iterrows():
        issues.append({
            "table": table_name,
            "row_ref": _ref(row, id_cols),
            "type": "duplicate_row",
            "detail": "Exact duplicate of another row (all columns identical).",
            "source": "baseline",
        })
    return issues


def check_temporal_order(df, table_name, start_col, end_col, id_cols):
    """Flags rows where end_col is chronologically before start_col."""
    issues = []
    if start_col not in df.columns or end_col not in df.columns:
        return issues
    bad = df[(df[start_col].notna()) & (df[end_col].notna()) & (df[end_col] < df[start_col])]
    for _, row in bad.iterrows():
        issues.append({
            "table": table_name,
            "row_ref": _ref(row, id_cols),
            "type": "temporal_misalignment",
            "detail": f"'{end_col}' ({row[end_col]}) is before '{start_col}' ({row[start_col]}).",
            "source": "baseline",
        })
    return issues


def check_static_range(df, table_name, col, lo, hi, id_cols):
    """Flags values outside a hard-coded, non-learned plausible range."""
    issues = []
    if col not in df.columns:
        return issues
    bad = df[(df[col].notna()) & ((df[col] < lo) | (df[col] > hi))]
    for _, row in bad.iterrows():
        issues.append({
            "table": table_name,
            "row_ref": _ref(row, id_cols),
            "type": "implausible_value",
            "detail": f"'{col}' = {row[col]} outside fixed range [{lo}, {hi}].",
            "source": "baseline",
        })
    return issues


def run_baseline(tables: dict) -> list:
    """Runs all deterministic baseline checks across the loaded tables."""
    issues = []

    if "admissions" in tables:
        df = tables["admissions"]
        issues += check_missing_required(df, "admissions", ["admission_type"], ["subject_id", "hadm_id"])
        issues += check_exact_duplicates(df, "admissions", ["subject_id", "hadm_id"])
        issues += check_temporal_order(df, "admissions", "admittime", "dischtime", ["subject_id", "hadm_id"])

    if "patients" in tables:
        df = tables["patients"]
        issues += check_static_range(df, "patients", "anchor_age", 0, 120, ["subject_id"])
        issues += check_exact_duplicates(df, "patients", ["subject_id"])

    if "transfers" in tables:
        df = tables["transfers"]
        issues += check_temporal_order(df, "transfers", "intime", "outtime", ["subject_id", "transfer_id"])

    if "labevents" in tables:
        df = tables["labevents"]
        # a single hard-coded sanity range for ANY numeric lab value (very
        # generous on purpose -- this is the "dumb" baseline)
        issues += check_static_range(df, "labevents", "valuenum", -1e6, 1e7, ["labevent_id"])

    return issues


def issues_to_df(issues: list) -> pd.DataFrame:
    if not issues:
        return pd.DataFrame(columns=["table", "row_ref", "type", "detail", "source"])
    return pd.DataFrame(issues)
