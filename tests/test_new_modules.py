"""
Unit tests for impact_explainer, quality_score, and report_generator modules.
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from impact_explainer import explain_issue, explain_all_issues
from quality_score import compute_quality_scores
from report_generator import generate_pdf_report


class TestNewModules(unittest.TestCase):

    def setUp(self):
        self.mock_issue = {
            "table": "labevents",
            "type": "implausible_value",
            "detail": "Outlier lab value (z=4.5)",
            "confidence": 0.85
        }
        self.mock_tables = {
            "patients": pd.DataFrame({"subject_id": [1, 2, 3]}),
            "admissions": pd.DataFrame({"hadm_id": [10, 20]})
        }

    def test_impact_explainer(self):
        enriched = explain_issue(self.mock_issue)
        self.assertEqual(enriched["risk_level"], "Critical")
        self.assertIn("physiological", enriched["clinical_impact"].lower())
        self.assertIn("distorts", enriched["research_impact"].lower())
        self.assertTrue(len(enriched["recommended_action"]) > 0)

        all_enriched = explain_all_issues([self.mock_issue])
        self.assertEqual(len(all_enriched), 1)

    def test_quality_score_engine(self):
        b_issues = [{"type": "missing_required_field", "table": "patients"}]
        a_issues = [self.mock_issue]
        scores = compute_quality_scores(self.mock_tables, b_issues, a_issues)

        self.assertIn("overall_score", scores)
        self.assertIn("missing_data_score", scores)
        self.assertIn("duplicate_score", scores)
        self.assertIn("temporal_score", scores)
        self.assertIn("outlier_score", scores)
        self.assertTrue(0 <= scores["overall_score"] <= 100)

    def test_pdf_report_generator(self):
        b_issues = [{"type": "missing_required_field", "table": "patients"}]
        a_issues = [explain_issue(self.mock_issue)]
        all_issues = b_issues + a_issues
        scores = compute_quality_scores(self.mock_tables, b_issues, a_issues)

        pdf_path = generate_pdf_report(scores, all_issues)
        self.assertTrue(os.path.exists(pdf_path))
        self.assertTrue(os.path.getsize(pdf_path) > 0)
        os.remove(pdf_path)


if __name__ == "__main__":
    unittest.main()
