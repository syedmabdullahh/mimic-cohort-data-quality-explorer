"""
Loads MIMIC-IV-shaped CSV tables into pandas DataFrames, validates each
against the official schema (src/schema.py), and reports which columns are
present/missing so any downstream tool never silently assumes a column
exists.

Works identically whether pointed at the synthetic placeholder data
(data/synthetic) or a real MIMIC-IV Demo download (data/real), as long as
the real data preserves the original PhysioNet filenames.
"""

import os
import pandas as pd

from schema import ALL_SCHEMAS, TABLE_MODULE

DATETIME_COLS = {"admittime", "dischtime", "deathtime", "edregtime", "edouttime",
                  "charttime", "storetime", "starttime", "stoptime", "intime", "outtime"}
DATE_COLS = {"dod", "chartdate"}


class LoadReport:
    def __init__(self):
        self.tables_loaded = []
        self.tables_missing = []
        self.column_warnings = {}  # table -> list of missing required columns

    def summary(self):
        lines = []
        lines.append(f"Loaded {len(self.tables_loaded)} tables: {', '.join(self.tables_loaded) or 'none'}")
        if self.tables_missing:
            lines.append(f"Missing tables (files not found): {', '.join(self.tables_missing)}")
        for t, cols in self.column_warnings.items():
            lines.append(f"  {t}: missing required columns {cols}")
        return "\n".join(lines)


def load_tables(data_dir: str, table_names=None):
    """
    Loads the requested tables (default: all known tables) from data_dir.
    data_dir is expected to contain hosp/ and icu/ subfolders with the
    original PhysioNet CSV filenames (e.g. patients.csv, admissions.csv).

    Returns (dict of table_name -> DataFrame, LoadReport)
    """
    table_names = table_names or list(ALL_SCHEMAS.keys())
    tables = {}
    report = LoadReport()

    for name in table_names:
        schema = ALL_SCHEMAS[name]
        module = TABLE_MODULE[name]
        path = os.path.join(data_dir, module, f"{name}.csv")
        if not os.path.exists(path):
            report.tables_missing.append(name)
            continue

        df = pd.read_csv(path, dtype=str, keep_default_na=True, na_values=["", "NULL", "null"])

        # type coercion per schema, without dropping rows that fail to parse
        for col in schema.columns:
            if col.name not in df.columns:
                continue
            if col.dtype == "int":
                df[col.name] = pd.to_numeric(df[col.name], errors="coerce")
            elif col.dtype == "float":
                df[col.name] = pd.to_numeric(df[col.name], errors="coerce")
            elif col.dtype in ("datetime",):
                df[col.name] = pd.to_datetime(df[col.name], errors="coerce")
            elif col.dtype == "date":
                df[col.name] = pd.to_datetime(df[col.name], errors="coerce")

        missing_required = [c for c in schema.required_columns if c not in df.columns]
        if missing_required:
            report.column_warnings[name] = missing_required

        tables[name] = df
        report.tables_loaded.append(name)

    return tables, report


def resolve_data_dir(preferred_env_var="MIMIC_DATA_DIR", default_subdir="synthetic"):
    """
    Resolves which data directory to load from.
    - If MIMIC_DATA_DIR env var is set, use it (intended for real data, e.g. data/real).
    - Otherwise fall back to the bundled synthetic placeholder data.
    Returns (path, is_synthetic: bool)
    """
    base = os.path.join(os.path.dirname(__file__), "..", "data")
    env_dir = os.environ.get(preferred_env_var)
    if env_dir:
        return env_dir, ("synthetic" in env_dir)
    return os.path.join(base, default_subdir), True
