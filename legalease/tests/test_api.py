"""HTTP-level tests. Skipped automatically if FastAPI isn't installed.
Run:  pip install -r requirements-dev.txt && pytest -q"""
import os, sys, unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
try:
    from fastapi.testclient import TestClient
    from app.main import app
    HAVE = True
except ImportError:
    HAVE = False
from tests.test_core import SAMPLES, logo_data_url


@unittest.skipUnless(HAVE, "fastapi not installed")
class Api(unittest.TestCase):
    def setUp(self): self.c = TestClient(app)

    def test_health_and_templates(self):
        self.assertEqual(self.c.get("/api/health").json()["status"], "ok")
        keys = {t["key"] for t in self.c.get("/api/templates").json()}
        self.assertEqual(keys, set(SAMPLES))

    def test_generate_then_export_all_formats(self):
        r = self.c.post("/api/generate", json={"document_type": "nda", "data": SAMPLES["nda"], "use_ai": False})
        self.assertEqual(r.status_code, 200)
        doc = r.json()
        for fmt, magic in (("pdf", b"%PDF"), ("docx", b"PK"), ("txt", b"")):
            r = self.c.post(f"/api/export/{fmt}", json={"document": doc, "branding": {"company_name": "X", "logo_data_url": logo_data_url(), "font": "sans"}})
            self.assertEqual(r.status_code, 200, fmt)
            self.assertTrue(r.content.startswith(magic))
            self.assertIn(f".{fmt}", r.headers["content-disposition"])

    def test_errors(self):
        self.assertEqual(self.c.post("/api/generate", json={"document_type": "nda", "data": {}, "use_ai": False}).status_code, 422)
        self.assertEqual(self.c.post("/api/export/exe", json={"document": {"title": "t"}}).status_code, 404)
        bad = self.c.post("/api/export/pdf", json={"document": {"title": "t"}, "branding": {"logo_data_url": "data:image/png;base64,AAAA"}})
        self.assertEqual(bad.status_code, 400)

    def test_security_headers(self):
        h = self.c.get("/api/health").headers
        self.assertIn("default-src 'self'", h["content-security-policy"])
        self.assertEqual(h["x-content-type-options"], "nosniff")


if __name__ == "__main__":
    unittest.main()
