"""
Unit tests for executive_insights module.
"""

import os
import sys
import unittest
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from impact_explainer import explain_issue
from quality_score import compute_quality_scores
from executive_insights import prioritize_issues, compute_table_scores, generate_executive_insights


class TestExecutiveInsights(unittest.TestCase):

    def setUp(self):
        self.mock_tables = {
            "patients": pd.DataFrame({"subject_id": [1, 2, 3, 4, 5]}),
            "admissions": pd.DataFrame({"hadm_id": [10, 20, 30]}),
            "transfers": pd.DataFrame({"transfer_id": [100, 200]})
        }
        self.mock_issues = [
            explain_issue({"table": "labevents", "type": "implausible_value", "detail": "Lab outlier"}),
            explain_issue({"table": "transfers", "type": "cross_table_temporal_inconsistency", "detail": "Time shift"}),
            explain_issue({"table": "patients", "type": "missing_required_field", "detail": "Missing age"})
        ]
        self.scores = compute_quality_scores(self.mock_tables, [], self.mock_issues)

    def test_prioritize_issues(self):
        prioritized = prioritize_issues(self.mock_issues)
        self.assertIn("high_risk", prioritized)
        self.assertIn("medium_risk", prioritized)
        self.assertIn("low_risk", prioritized)
        self.assertTrue(prioritized["high_count"] >= 1)

    def test_table_scores(self):
        t_scores = compute_table_scores(self.mock_tables, self.mock_issues)
        self.assertIn("patients", t_scores)
        self.assertIn("transfers", t_scores)
        self.assertTrue(0 <= t_scores["patients"] <= 100)

    def test_executive_insights(self):
        insights = generate_executive_insights(self.mock_tables, self.scores, self.mock_issues)
        self.assertIn("dataset_summary", insights)
        self.assertIn("key_findings", insights)
        self.assertIn("top_risks", insights)
        self.assertIn("recommendations", insights)
        self.assertTrue(len(insights["key_findings"]) > 0)


if __name__ == "__main__":
    unittest.main()
