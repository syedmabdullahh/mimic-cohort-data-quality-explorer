"""
Minimal unit tests covering the three core modules. Run with:
    python -m pytest tests/ -v
or:
    python tests/test_pipeline.py
"""

import os
import sys
import unittest
from datetime import datetime

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from baseline_rules import run_baseline  # noqa: E402
from quality_scanner import lab_value_outliers, near_duplicate_admissions  # noqa: E402
from cohort_query import parse_query, build_patient_bundle, apply_filter  # noqa: E402


class TestBaselineRules(unittest.TestCase):
    def test_flags_missing_required_field(self):
        admissions = pd.DataFrame([
            {"subject_id": 1, "hadm_id": 100, "admittime": pd.Timestamp("2110-01-01"),
             "dischtime": pd.Timestamp("2110-01-05"), "admission_type": None},
        ])
        tables = {"admissions": admissions}
        issues = run_baseline(tables)
        self.assertTrue(any(i["type"] == "missing_required_field" for i in issues))

    def test_flags_temporal_misalignment(self):
        admissions = pd.DataFrame([
            {"subject_id": 1, "hadm_id": 100, "admittime": pd.Timestamp("2110-01-10"),
             "dischtime": pd.Timestamp("2110-01-05"), "admission_type": "EW EMER."},
        ])
        tables = {"admissions": admissions}
        issues = run_baseline(tables)
        self.assertTrue(any(i["type"] == "temporal_misalignment" for i in issues))

    def test_does_not_flag_clean_data(self):
        admissions = pd.DataFrame([
            {"subject_id": 1, "hadm_id": 100, "admittime": pd.Timestamp("2110-01-01"),
             "dischtime": pd.Timestamp("2110-01-05"), "admission_type": "ELECTIVE"},
        ])
        tables = {"admissions": admissions}
        issues = run_baseline(tables)
        self.assertEqual(len(issues), 0)


class TestQualityScanner(unittest.TestCase):
    def test_lab_outlier_detection(self):
        rows = []
        for i in range(20):
            rows.append({"labevent_id": i, "subject_id": 1, "itemid": 999,
                         "valuenum": 100 + (i % 3)})
        rows.append({"labevent_id": 999, "subject_id": 1, "itemid": 999, "valuenum": 9999})
        labevents = pd.DataFrame(rows)
        d_labitems = pd.DataFrame([{"itemid": 999, "label": "Test Lab"}])
        issues = lab_value_outliers(labevents, d_labitems, min_group_size=5)
        flagged_ids = [i["row_ref"]["labevent_id"] for i in issues]
        self.assertIn(999, flagged_ids)

    def test_abstains_on_small_groups(self):
        # fewer than min_group_size rows -> should not flag anything (abstain)
        labevents = pd.DataFrame([
            {"labevent_id": 1, "subject_id": 1, "itemid": 5, "valuenum": 1000},
        ])
        issues = lab_value_outliers(labevents, pd.DataFrame(), min_group_size=8)
        self.assertEqual(len(issues), 0)

    def test_near_duplicate_admissions_detected(self):
        admissions = pd.DataFrame([
            {"subject_id": 1, "hadm_id": 100, "admittime": pd.Timestamp("2110-01-01 00:00"),
             "dischtime": pd.Timestamp("2110-01-05 00:00")},
            {"subject_id": 1, "hadm_id": 101, "admittime": pd.Timestamp("2110-01-01 02:00"),
             "dischtime": pd.Timestamp("2110-01-04 22:00")},
        ])
        issues = near_duplicate_admissions(admissions, overlap_threshold=0.5)
        self.assertEqual(len(issues), 1)


class TestCohortQuery(unittest.TestCase):
    def test_age_over_parses_correctly(self):
        cf, unmatched = parse_query("age over 65")
        self.assertEqual(len(cf.clauses), 1)
        self.assertEqual(unmatched, [])

    def test_unmatched_text_is_surfaced_not_dropped(self):
        cf, unmatched = parse_query("age over 65 who like pizza")
        self.assertTrue(len(unmatched) == 1 and "pizza" in unmatched[0])

    def test_filter_applies_correctly(self):
        tables = {
            "patients": pd.DataFrame([
                {"subject_id": 1, "anchor_age": 70, "gender": "F"},
                {"subject_id": 2, "anchor_age": 40, "gender": "M"},
            ]),
            "admissions": pd.DataFrame(),
            "diagnoses_icd": pd.DataFrame(),
            "d_icd_diagnoses": pd.DataFrame(),
        }
        cf, _ = parse_query("age over 65")
        bundle = build_patient_bundle(tables)
        matches, _ = apply_filter(bundle, cf)
        self.assertEqual(matches, [1])


if __name__ == "__main__":
    unittest.main()
