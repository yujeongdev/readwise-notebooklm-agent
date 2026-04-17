import json
import unittest
from unittest import mock

from readwise_notebooklm_agent.readwise_backend import BackendError, ReadwiseCliBackend, make_backend


class ReadwiseCliBackendTests(unittest.TestCase):
    def test_list_documents_invokes_official_cli_json(self):
        payload = {"results": [{"id": "doc", "title": "Doc"}], "nextPageCursor": None}
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout=json.dumps(payload), stderr="")
            docs = ReadwiseCliBackend().list_documents(
                updated_after="2026-01-01T00:00:00Z",
                location="new",
                category="article",
                tag=["robotics"],
                limit_pages=1,
                with_html=False,
                with_raw=False,
            )
        self.assertEqual(docs[0]["id"], "doc")
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[:3], ["readwise", "--json", "reader-list-documents"])
        self.assertIn("--updated-after", cmd)
        self.assertIn("--location", cmd)
        self.assertIn("--response-fields", cmd)

    def test_cli_backend_reports_non_json_output(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0, stdout="not-json", stderr="")
            with self.assertRaises(BackendError):
                ReadwiseCliBackend().get_document("doc")

    def test_auto_backend_prefers_cli_when_available(self):
        with mock.patch.object(ReadwiseCliBackend, "is_available", return_value=True):
            backend = make_backend("auto", token_loader=lambda: "token")
        self.assertIsInstance(backend, ReadwiseCliBackend)

    def test_auto_backend_falls_back_to_api(self):
        with mock.patch.object(ReadwiseCliBackend, "is_available", return_value=False):
            backend = make_backend("auto", token_loader=lambda: "token")
        self.assertEqual(backend.name, "api")


if __name__ == "__main__":
    unittest.main()
