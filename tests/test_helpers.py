import datetime as dt
import json
import os
import tempfile
import unittest
import unittest.mock
from pathlib import Path
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
        groups = triage.load_domain_groups("examples/domains.robotics-sim2real.sample.json")
        score, reasons = triage.score_doc(doc, ["robotics", "sim2real"], groups)
        self.assertGreater(score, 10)
        self.assertTrue(any("robotics" in reason for reason in reasons))
        self.assertTrue(any("sim2real" in reason for reason in reasons))

    def test_load_domain_groups_from_custom_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "domains.json"
            path.write_text(json.dumps({"custom": {"weight": 9, "keywords": ["needle"]}}))
            groups = triage.load_domain_groups(str(path))
        self.assertIn("custom", groups)
        self.assertEqual(groups["custom"][1], 9)


    def test_missing_env_domain_file_does_not_break_defaults(self):
        old = os.environ.get("READWISE_NOTEBOOKLM_DOMAINS_FILE")
        os.environ["READWISE_NOTEBOOKLM_DOMAINS_FILE"] = "/tmp/does-not-exist-rna.json"
        try:
            score, reasons = triage.score_doc({"title": "AI research guide", "location": "new"}, [])
        finally:
            if old is None:
                os.environ.pop("READWISE_NOTEBOOKLM_DOMAINS_FILE", None)
            else:
                os.environ["READWISE_NOTEBOOKLM_DOMAINS_FILE"] = old
        self.assertGreater(score, 0)

    def test_make_nlm_command_preserves_custom_domain(self):
        cmd = triage.make_nlm_command(
            {"title": "Custom", "source_url": "https://example.com", "summary": "Example"},
            ["custom-domain: needle", "needs-browser-fallback"],
        )
        self.assertIn("--domain custom-domain", cmd)
        self.assertNotIn("--domain robotics", cmd)


    def test_invalid_domain_weight_reports_config_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "domains.json"
            path.write_text(json.dumps({"bad": {"weight": "high", "keywords": ["needle"]}}))
            with self.assertRaises(triage.DomainConfigError):
                triage.load_domain_groups(str(path))

    def test_archive_does_not_load_domain_config(self):
        old = os.environ.get("READWISE_NOTEBOOKLM_DOMAINS_FILE")
        os.environ["READWISE_NOTEBOOKLM_DOMAINS_FILE"] = "/tmp/does-not-exist-rna.json"
        calls = []
        try:
            with unittest.mock.patch.object(triage, "load_token", return_value="token"), \
                 unittest.mock.patch.object(triage, "update_docs", side_effect=lambda *args, **kwargs: calls.append((args, kwargs))):
                result = triage.main(["--archive", "doc-1", "--dry-run"])
        finally:
            if old is None:
                os.environ.pop("READWISE_NOTEBOOKLM_DOMAINS_FILE", None)
            else:
                os.environ["READWISE_NOTEBOOKLM_DOMAINS_FILE"] = old
        self.assertEqual(result, 0)
        self.assertEqual(len(calls), 1)

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
