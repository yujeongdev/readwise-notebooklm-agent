import datetime as dt
import unittest
from unittest import mock

from readwise_notebooklm_agent import triage
from readwise_notebooklm_agent import deepdive


class TriageScoringTests(unittest.TestCase):
    def test_scores_robotics_sim2real_document(self):
        doc = {
            "title": "Building a robotics simulator with MuJoCo and Isaac",
            "summary": "Robot simulation and sim-to-real workflow",
            "source_url": "https://example.com/robotics",
            "location": "new",
            "category": "article",
        }
        score, reasons = triage.score_doc(doc, ["robotics", "sim2real"])
        self.assertGreater(score, 10)
        self.assertTrue(any("robotics" in reason for reason in reasons))
        self.assertTrue(any("sim2real" in reason for reason in reasons))

    def test_kst_days_ago_uses_utc_suffix(self):
        value = triage.kst_days_ago_iso(7)
        self.assertTrue(value.endswith("Z"))


class DeepDiveTests(unittest.TestCase):
    def test_classifies_arxiv_as_paper(self):
        self.assertEqual(deepdive.classify_source("https://arxiv.org/pdf/2512.05107", "auto"), "paper")

    def test_slugify_keeps_meaningful_prefix(self):
        self.assertIn("robot", deepdive.slugify("Robot Learning / Sim2Real", 40).lower())


if __name__ == "__main__":
    unittest.main()
