"""
Official MIMIC-IV table schemas (subset used by this project).

Column names, types, and nullability are taken verbatim from the MIT-LCP
mimic-code repository's PostgreSQL build script:
  mimic-iv/buildmimic/postgres/create.sql
  https://github.com/MIT-LCP/mimic-code

Only the tables relevant to Track 2 (Cohort & Data Quality Explorer) are
included: patients, admissions, diagnoses_icd, d_icd_diagnoses, labevents,
d_labitems, prescriptions, transfers, icustays.
"""

from dataclasses import dataclass, field


@dataclass
class Column:
    name: str
    dtype: str          # "int", "float", "str", "datetime", "date"
    required: bool = False


@dataclass
class TableSchema:
    name: str
    columns: list = field(default_factory=list)
    primary_key: list = field(default_factory=list)

    @property
    def column_names(self):
        return [c.name for c in self.columns]

    @property
    def required_columns(self):
        return [c.name for c in self.columns if c.required]


PATIENTS = TableSchema(
    name="patients",
    primary_key=["subject_id"],
    columns=[
        Column("subject_id", "int", True),
        Column("gender", "str", True),
        Column("anchor_age", "int"),
        Column("anchor_year", "int", True),
        Column("anchor_year_group", "str", True),
        Column("dod", "date"),
    ],
)

ADMISSIONS = TableSchema(
    name="admissions",
    primary_key=["subject_id", "hadm_id"],
    columns=[
        Column("subject_id", "int", True),
        Column("hadm_id", "int", True),
        Column("admittime", "datetime", True),
        Column("dischtime", "datetime"),
        Column("deathtime", "datetime"),
        Column("admission_type", "str", True),
        Column("admit_provider_id", "str"),
        Column("admission_location", "str"),
        Column("discharge_location", "str"),
        Column("insurance", "str"),
        Column("language", "str"),
        Column("marital_status", "str"),
        Column("race", "str"),
        Column("edregtime", "datetime"),
        Column("edouttime", "datetime"),
        Column("hospital_expire_flag", "int"),
    ],
)

DIAGNOSES_ICD = TableSchema(
    name="diagnoses_icd",
    primary_key=["subject_id", "hadm_id", "seq_num"],
    columns=[
        Column("subject_id", "int", True),
        Column("hadm_id", "int", True),
        Column("seq_num", "int", True),
        Column("icd_code", "str"),
        Column("icd_version", "int"),
    ],
)

D_ICD_DIAGNOSES = TableSchema(
    name="d_icd_diagnoses",
    primary_key=["icd_code", "icd_version"],
    columns=[
        Column("icd_code", "str", True),
        Column("icd_version", "int", True),
        Column("long_title", "str"),
    ],
)

LABEVENTS = TableSchema(
    name="labevents",
    primary_key=["labevent_id"],
    columns=[
        Column("labevent_id", "int", True),
        Column("subject_id", "int", True),
        Column("hadm_id", "int"),
        Column("specimen_id", "int", True),
        Column("itemid", "int", True),
        Column("order_provider_id", "str"),
        Column("charttime", "datetime"),
        Column("storetime", "datetime"),
        Column("value", "str"),
        Column("valuenum", "float"),
        Column("valueuom", "str"),
        Column("ref_range_lower", "float"),
        Column("ref_range_upper", "float"),
        Column("flag", "str"),
        Column("priority", "str"),
        Column("comments", "str"),
    ],
)

D_LABITEMS = TableSchema(
    name="d_labitems",
    primary_key=["itemid"],
    columns=[
        Column("itemid", "int", True),
        Column("label", "str"),
        Column("fluid", "str"),
        Column("category", "str"),
    ],
)

PRESCRIPTIONS = TableSchema(
    name="prescriptions",
    primary_key=["subject_id", "hadm_id", "pharmacy_id"],
    columns=[
        Column("subject_id", "int", True),
        Column("hadm_id", "int", True),
        Column("pharmacy_id", "int", True),
        Column("poe_id", "str"),
        Column("poe_seq", "int"),
        Column("order_provider_id", "str"),
        Column("starttime", "datetime"),
        Column("stoptime", "datetime"),
        Column("drug_type", "str", True),
        Column("drug", "str", True),
        Column("formulary_drug_cd", "str"),
        Column("gsn", "str"),
        Column("ndc", "str"),
        Column("prod_strength", "str"),
        Column("form_rx", "str"),
        Column("dose_val_rx", "str"),
        Column("dose_unit_rx", "str"),
        Column("form_val_disp", "str"),
        Column("form_unit_disp", "str"),
        Column("doses_per_24_hrs", "float"),
        Column("route", "str"),
    ],
)

TRANSFERS = TableSchema(
    name="transfers",
    primary_key=["transfer_id"],
    columns=[
        Column("subject_id", "int", True),
        Column("hadm_id", "int"),
        Column("transfer_id", "int", True),
        Column("eventtype", "str"),
        Column("careunit", "str"),
        Column("intime", "datetime"),
        Column("outtime", "datetime"),
    ],
)

ICUSTAYS = TableSchema(
    name="icustays",
    primary_key=["stay_id"],
    columns=[
        Column("subject_id", "int", True),
        Column("hadm_id", "int", True),
        Column("stay_id", "int", True),
        Column("first_careunit", "str"),
        Column("last_careunit", "str"),
        Column("intime", "datetime"),
        Column("outtime", "datetime"),
        Column("los", "float"),
    ],
)

ALL_SCHEMAS = {
    "patients": PATIENTS,
    "admissions": ADMISSIONS,
    "diagnoses_icd": DIAGNOSES_ICD,
    "d_icd_diagnoses": D_ICD_DIAGNOSES,
    "labevents": LABEVENTS,
    "d_labitems": D_LABITEMS,
    "prescriptions": PRESCRIPTIONS,
    "transfers": TRANSFERS,
    "icustays": ICUSTAYS,
}

# Which folder each table lives in within a real MIMIC-IV Demo download
TABLE_MODULE = {
    "patients": "hosp",
    "admissions": "hosp",
    "diagnoses_icd": "hosp",
    "d_icd_diagnoses": "hosp",
    "labevents": "hosp",
    "d_labitems": "hosp",
    "prescriptions": "hosp",
    "transfers": "hosp",
    "icustays": "icu",
}

# Physiologically plausible reference ranges for a few common labs, used by
# the quality scanner to flag implausible values. Ranges are intentionally
# generous (wider than clinical reference ranges) since the goal is to catch
# data-entry errors, not clinical abnormalities.
LAB_PLAUSIBLE_RANGE = {
    "Hemoglobin": (2.0, 24.0),          # g/dL
    "Glucose": (10.0, 2000.0),          # mg/dL
    "Creatinine": (0.05, 30.0),         # mg/dL
    "Potassium": (1.0, 10.0),           # mEq/L
    "Sodium": (100.0, 190.0),           # mEq/L
    "White Blood Cells": (0.0, 200.0),  # K/uL
    "Platelet Count": (0.0, 2000.0),    # K/uL
    "Heart Rate": (0.0, 300.0),         # bpm (chartevents-style, kept for future use)
}
