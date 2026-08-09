"""
Generates SYNTHETIC placeholder data that matches the official MIMIC-IV
schema exactly (same tables, same columns, same dtypes).

This is NOT real patient data and NOT a substitute for the real MIMIC-IV
Clinical Database Demo v2.2. It exists so the prototype is runnable and
testable before the real, credentialed data is downloaded from PhysioNet
(https://physionet.org/content/mimic-iv-demo/2.2/), and so the data-quality
scanner has a ground-truth set of seeded issues to evaluate against
(precision/recall/F1 require known issues to check against).

To use REAL data instead: download the demo CSVs from PhysioNet and place
them in data/real/hosp/ and data/real/icu/ using the original filenames,
then set MIMIC_DATA_DIR=data/real when running the app (see README.md).

Usage:
    python scripts/generate_synthetic_data.py
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)

OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "synthetic")
HOSP_DIR = os.path.join(OUT_DIR, "hosp")
ICU_DIR = os.path.join(OUT_DIR, "icu")
os.makedirs(HOSP_DIR, exist_ok=True)
os.makedirs(ICU_DIR, exist_ok=True)

N_PATIENTS = 100

GENDERS = ["M", "F"]
RACES = ["WHITE", "BLACK/AFRICAN AMERICAN", "ASIAN", "HISPANIC/LATINO", "UNKNOWN", "OTHER"]
INSURANCE = ["Medicare", "Medicaid", "Private", "Other", "No charge"]
MARITAL = ["MARRIED", "SINGLE", "WIDOWED", "DIVORCED", None]
LANGUAGE = ["ENGLISH", "SPANISH", "CHINESE", None]
ADMIT_TYPES = ["EW EMER.", "OBSERVATION ADMIT", "URGENT", "ELECTIVE", "SURGICAL SAME DAY ADMISSION"]
ADMIT_LOC = ["EMERGENCY ROOM", "PHYSICIAN REFERRAL", "TRANSFER FROM HOSPITAL", "WALK-IN/SELF REFERRAL"]
DISCH_LOC = ["HOME", "HOME HEALTH CARE", "SKILLED NURSING FACILITY", "REHAB", "DIED"]
CAREUNITS = ["Medical Intensive Care Unit (MICU)", "Surgical Intensive Care Unit (SICU)",
             "Coronary Care Unit (CCU)", "Medicine", "Emergency Department"]

DIAGNOSES = [
    ("A419", 10, "Sepsis, unspecified organism"),
    ("I509", 10, "Heart failure, unspecified"),
    ("N179", 10, "Acute kidney failure, unspecified"),
    ("J189", 10, "Pneumonia, unspecified organism"),
    ("E119", 10, "Type 2 diabetes mellitus without complications"),
    ("I10", 10, "Essential (primary) hypertension"),
    ("K7200", 10, "Acute and subacute hepatic failure without coma"),
    ("J449", 10, "Chronic obstructive pulmonary disease, unspecified"),
]

LAB_ITEMS = [
    (51222, "Hemoglobin", "Blood", "Hematology", 12.0, 16.0, "g/dL"),
    (50931, "Glucose", "Blood", "Chemistry", 70.0, 100.0, "mg/dL"),
    (50912, "Creatinine", "Blood", "Chemistry", 0.5, 1.2, "mg/dL"),
    (50971, "Potassium", "Blood", "Chemistry", 3.5, 5.0, "mEq/L"),
    (50983, "Sodium", "Blood", "Chemistry", 135.0, 145.0, "mEq/L"),
    (51301, "White Blood Cells", "Blood", "Hematology", 4.0, 11.0, "K/uL"),
    (51265, "Platelet Count", "Blood", "Hematology", 150.0, 400.0, "K/uL"),
]

DRUGS = [
    ("Vancomycin", "IV", "MAIN", "500", "mg"),
    ("Metoprolol Tartrate", "PO", "MAIN", "25", "mg"),
    ("Insulin", "SC", "MAIN", "10", "units"),
    ("Furosemide", "IV", "MAIN", "40", "mg"),
    ("Acetaminophen", "PO", "MAIN", "650", "mg"),
]


def rand_dt(start_year=2110, end_year=2200):
    start = datetime(start_year, 1, 1)
    end = datetime(end_year, 12, 31)
    delta = end - start
    return start + timedelta(seconds=random.randint(0, int(delta.total_seconds())))


def write_csv(path, header, rows):
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header)
        w.writerows(rows)


def main():
    patients, admissions, diagnoses, labevents, prescriptions, transfers, icustays = (
        [], [], [], [], [], [], []
    )

    labevent_id = 1
    transfer_id = 1
    stay_id = 200000

    for i in range(1, N_PATIENTS + 1):
        subject_id = 10000000 + i
        anchor_age = random.randint(18, 95)
        anchor_year = random.randint(2110, 2190)
        dod = None
        if random.random() < 0.08:
            dod = rand_dt(anchor_year, anchor_year + 5).date().isoformat()

        patients.append([
            subject_id, random.choice(GENDERS), anchor_age, anchor_year,
            f"{anchor_year - anchor_year % 10}-{anchor_year - anchor_year % 10 + 9}", dod
        ])

        n_admissions = random.choice([1, 1, 1, 2, 2, 3])
        for a in range(n_admissions):
            hadm_id = 20000000 + subject_id * 10 + a
            admittime = rand_dt()
            los_days = random.randint(1, 14)
            dischtime = admittime + timedelta(days=los_days, hours=random.randint(0, 23))
            deathtime = None
            hospital_expire_flag = 0
            if dod and random.random() < 0.3:
                deathtime = dischtime
                hospital_expire_flag = 1

            admissions.append([
                subject_id, hadm_id, admittime.isoformat(sep=" "),
                dischtime.isoformat(sep=" "),
                deathtime.isoformat(sep=" ") if deathtime else "",
                random.choice(ADMIT_TYPES), f"P{random.randint(10000,99999)}",
                random.choice(ADMIT_LOC), random.choice(DISCH_LOC),
                random.choice(INSURANCE), random.choice(LANGUAGE) or "",
                random.choice(MARITAL) or "", random.choice(RACES),
                "", "", hospital_expire_flag
            ])

            # diagnoses
            n_dx = random.randint(1, 4)
            chosen = random.sample(DIAGNOSES, n_dx)
            for seq, (code, ver, title) in enumerate(chosen, start=1):
                diagnoses.append([subject_id, hadm_id, seq, code, ver])

            # labs
            for _ in range(random.randint(3, 10)):
                itemid, label, fluid, category, lo, hi, uom = random.choice(LAB_ITEMS)
                charttime = admittime + timedelta(hours=random.randint(0, los_days * 24))
                value = round(random.uniform(lo * 0.6, hi * 1.4), 2)
                flag = "abnormal" if (value < lo or value > hi) else ""
                labevents.append([
                    labevent_id, subject_id, hadm_id, labevent_id + 500000, itemid,
                    "", charttime.isoformat(sep=" "), charttime.isoformat(sep=" "),
                    str(value), value, uom, lo, hi, flag, random.choice(["ROUTINE", "STAT"]), ""
                ])
                labevent_id += 1

            # prescriptions
            for _ in range(random.randint(1, 5)):
                drug, route, drug_type, dose, unit = random.choice(DRUGS)
                starttime = admittime + timedelta(hours=random.randint(0, los_days * 24))
                stoptime = starttime + timedelta(hours=random.randint(4, 72))
                prescriptions.append([
                    subject_id, hadm_id, labevent_id + 900000, "", "", "",
                    starttime.isoformat(sep=" "), stoptime.isoformat(sep=" "),
                    drug_type, drug, "", "", "", "", "", dose, unit, dose, unit,
                    round(random.uniform(1, 4), 1), route
                ])

            # transfers
            n_transfers = random.randint(1, 3)
            t_time = admittime
            for t in range(n_transfers):
                out_time = t_time + timedelta(hours=random.randint(2, 48))
                transfers.append([
                    subject_id, hadm_id, transfer_id,
                    "admit" if t == 0 else "transfer",
                    random.choice(CAREUNITS), t_time.isoformat(sep=" "),
                    out_time.isoformat(sep=" ")
                ])
                transfer_id += 1
                t_time = out_time

            # icustays (only some admissions)
            if random.random() < 0.4:
                icu_in = admittime + timedelta(hours=random.randint(0, 12))
                icu_los = round(random.uniform(0.5, los_days), 2)
                icu_out = icu_in + timedelta(days=icu_los)
                stay_id += 1
                icustays.append([
                    subject_id, hadm_id, stay_id, random.choice(CAREUNITS),
                    random.choice(CAREUNITS), icu_in.isoformat(sep=" "),
                    icu_out.isoformat(sep=" "), icu_los
                ])

    # ---- Seed deliberate, documented data-quality issues for evaluation ----
    seeded_issues = []

    # 1. Duplicate admission rows (exact duplicate)
    dup = admissions[5][:]
    admissions.append(dup)
    seeded_issues.append({"type": "duplicate_row", "table": "admissions",
                           "subject_id": dup[0], "hadm_id": dup[1]})

    # 2. Temporal misalignment: dischtime before admittime
    bad_idx = 10
    row = admissions[bad_idx]
    admit = datetime.fromisoformat(row[2])
    row[3] = (admit - timedelta(days=2)).isoformat(sep=" ")
    seeded_issues.append({"type": "temporal_misalignment", "table": "admissions",
                           "subject_id": row[0], "hadm_id": row[1]})

    # 3. Missing required field: blank admission_type
    row2 = admissions[15]
    row2[5] = ""
    seeded_issues.append({"type": "missing_required_field", "table": "admissions",
                           "subject_id": row2[0], "hadm_id": row2[1], "field": "admission_type"})

    # 4. Implausible lab value (e.g. negative glucose)
    lab_bad = labevents[20]
    lab_bad[9] = -45.0
    lab_bad[8] = "-45.0"
    seeded_issues.append({"type": "implausible_value", "table": "labevents",
                           "labevent_id": lab_bad[0]})

    # 5. Implausible anchor_age (negative)
    pat_bad = patients[30]
    pat_bad[2] = -5
    seeded_issues.append({"type": "implausible_value", "table": "patients",
                           "subject_id": pat_bad[0], "field": "anchor_age"})

    # 6. Transfer with outtime before intime
    tr_bad = transfers[8]
    intime = datetime.fromisoformat(tr_bad[5])
    tr_bad[6] = (intime - timedelta(hours=5)).isoformat(sep=" ")
    seeded_issues.append({"type": "temporal_misalignment", "table": "transfers",
                           "transfer_id": tr_bad[2]})

    # 7. Near-duplicate (NOT exact-duplicate) overlapping admission -- same
    # subject, heavily overlapping stay windows, but different hadm_id and
    # slightly different metadata. Baseline's exact-duplicate check cannot
    # catch this by design; it requires the AI scanner's overlap logic.
    src = admissions[40]
    nd_subject, nd_hadm = src[0], src[1] + 5000
    admit_dt = datetime.fromisoformat(src[2])
    disch_dt = datetime.fromisoformat(src[3])
    near_dup_row = src[:]
    near_dup_row[1] = nd_hadm
    near_dup_row[2] = (admit_dt + timedelta(hours=2)).isoformat(sep=" ")   # slightly shifted admit
    near_dup_row[3] = (disch_dt - timedelta(hours=1)).isoformat(sep=" ")  # slightly shifted discharge
    admissions.append(near_dup_row)
    seeded_issues.append({"type": "duplicate_row", "table": "admissions",
                           "subject_id": nd_subject, "hadm_id": src[1],
                           "note": "near-duplicate overlapping admission, not byte-identical"})

    # 8. Cross-table temporal inconsistency: a transfer record that is
    # internally consistent (intime < outtime) but falls entirely outside
    # its parent admission's [admittime, dischtime] window -- only
    # detectable by joining transfers to admissions.
    ct_row = transfers[15]
    ct_subject, ct_hadm = ct_row[0], ct_row[1]
    parent_admit = next(a for a in admissions if a[0] == ct_subject and a[1] == ct_hadm)
    far_out_start = datetime.fromisoformat(parent_admit[3]) + timedelta(days=3)  # 3 days after discharge
    ct_row[5] = far_out_start.isoformat(sep=" ")
    ct_row[6] = (far_out_start + timedelta(hours=6)).isoformat(sep=" ")
    seeded_issues.append({"type": "temporal_misalignment", "table": "transfers",
                           "transfer_id": ct_row[2],
                           "note": "transfer window outside parent admission window"})

    # ---- Write tables ----
    write_csv(os.path.join(HOSP_DIR, "patients.csv"),
              ["subject_id", "gender", "anchor_age", "anchor_year", "anchor_year_group", "dod"],
              patients)
    write_csv(os.path.join(HOSP_DIR, "admissions.csv"),
              ["subject_id", "hadm_id", "admittime", "dischtime", "deathtime", "admission_type",
               "admit_provider_id", "admission_location", "discharge_location", "insurance",
               "language", "marital_status", "race", "edregtime", "edouttime", "hospital_expire_flag"],
              admissions)
    write_csv(os.path.join(HOSP_DIR, "diagnoses_icd.csv"),
              ["subject_id", "hadm_id", "seq_num", "icd_code", "icd_version"], diagnoses)
    write_csv(os.path.join(HOSP_DIR, "d_icd_diagnoses.csv"),
              ["icd_code", "icd_version", "long_title"],
              [[c, v, t] for c, v, t in DIAGNOSES])
    write_csv(os.path.join(HOSP_DIR, "labevents.csv"),
              ["labevent_id", "subject_id", "hadm_id", "specimen_id", "itemid", "order_provider_id",
               "charttime", "storetime", "value", "valuenum", "valueuom", "ref_range_lower",
               "ref_range_upper", "flag", "priority", "comments"], labevents)
    write_csv(os.path.join(HOSP_DIR, "d_labitems.csv"),
              ["itemid", "label", "fluid", "category"],
              [[itemid, label, fluid, category] for itemid, label, fluid, category, *_ in LAB_ITEMS])
    write_csv(os.path.join(HOSP_DIR, "prescriptions.csv"),
              ["subject_id", "hadm_id", "pharmacy_id", "poe_id", "poe_seq", "order_provider_id",
               "starttime", "stoptime", "drug_type", "drug", "formulary_drug_cd", "gsn", "ndc",
               "prod_strength", "form_rx", "dose_val_rx", "dose_unit_rx", "form_val_disp",
               "form_unit_disp", "doses_per_24_hrs", "route"], prescriptions)
    write_csv(os.path.join(HOSP_DIR, "transfers.csv"),
              ["subject_id", "hadm_id", "transfer_id", "eventtype", "careunit", "intime", "outtime"],
              transfers)
    write_csv(os.path.join(ICU_DIR, "icustays.csv"),
              ["subject_id", "hadm_id", "stay_id", "first_careunit", "last_careunit", "intime",
               "outtime", "los"], icustays)

    import json
    with open(os.path.join(OUT_DIR, "seeded_issues.json"), "w") as f:
        json.dump(seeded_issues, f, indent=2)

    print(f"Synthetic MIMIC-IV-shaped data written to {OUT_DIR}")
    print(f"  patients: {len(patients)} rows")
    print(f"  admissions: {len(admissions)} rows")
    print(f"  diagnoses_icd: {len(diagnoses)} rows")
    print(f"  labevents: {len(labevents)} rows")
    print(f"  prescriptions: {len(prescriptions)} rows")
    print(f"  transfers: {len(transfers)} rows")
    print(f"  icustays: {len(icustays)} rows")
    print(f"  seeded data-quality issues: {len(seeded_issues)} (see seeded_issues.json)")


if __name__ == "__main__":
    main()
