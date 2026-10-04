"""Core tests (no web framework needed):  python -m unittest discover -s tests -v"""
import base64, io, os, sys, unittest
from unittest import mock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from PIL import Image

from app import config, generator
from app.doc_types import REGISTRY
from app.exporters import EXPORTERS
from app.schemas import Branding
from app.security import RateLimiter, clean_text, process_logo

SAMPLES = {
    "employment_contract": dict(effective_date="2026-10-05", employer_name="Nimbus Labs Pvt Ltd", employer_address="12 Anna Salai, Chennai",
        employee_name="Priya Raman", employee_address="45 Lake View Rd, Chennai", job_title="Backend Engineer",
        responsibilities="Build APIs; review code", start_date="2026-11-01", employment_type="Full-time", work_location="Chennai office",
        currency="INR", salary="1,200,000", pay_frequency="Monthly", probation_months="3", notice_days="30", annual_leave_days="18",
        non_solicit_months="12", governing_law="Tamil Nadu, India"),
    "nda": dict(effective_date="2026-10-02", nda_type="Mutual", disclosing_party="Asha Freelance", disclosing_address="Chennai",
        receiving_party="Zenith Corp", receiving_address="Bengaluru", purpose="evaluating a website redesign",
        confidential_scope="source code, pricing, client lists", term_years="2", survival_years="3", governing_law="Karnataka, India"),
    "lease_agreement": dict(effective_date="2026-10-02", landlord_name="R. Kumar", tenant_name="S. Meena", property_address="Flat 4B, Sea View Apts, ECR, Chennai",
        lease_start="2026-11-01", lease_end="2027-09-30", currency="INR", monthly_rent="25000", security_deposit="75000",
        rent_due_day="5", late_fee="500", pets="Allowed", governing_law="Tamil Nadu, India"),
    "service_agreement": dict(effective_date="2026-10-02", client_name="Orbit Retail", provider_name="Dev Patel", services="Design and build a Shopify storefront",
        start_date="2026-10-10", currency="USD", fee="4500", fee_basis="Fixed project fee", payment_days="15", governing_law="India"),
}


def logo_data_url(fmt="PNG"):
    im = Image.new("RGB", (300, 120), (31, 58, 95)); b = io.BytesIO(); im.save(b, fmt)
    return f"data:image/{fmt.lower()};base64," + base64.b64encode(b.getvalue()).decode()


class Core(unittest.TestCase):
    def test_every_type_generates_and_exports(self):
        logo = process_logo(logo_data_url())
        for key, data in SAMPLES.items():
            doc = generator.generate_document(key, data, use_ai=False)
            self.assertGreaterEqual(len(doc.sections), 9)
            self.assertTrue(doc.terms and doc.signatories)
            for fmt, (fn, _) in EXPORTERS.items():
                for font in ("sans", "serif", "mono"):
                    out = fn(doc, Branding(company_name="Nimbus Labs", font=font, footer_text="Confidential"), logo)
                    self.assertGreater(len(out), 500, (key, fmt, font))
                    if fmt == "pdf": self.assertTrue(out.startswith(b"%PDF"))
                    if fmt == "docx": self.assertTrue(out.startswith(b"PK"))

    def test_missing_and_invalid_fields(self):
        with self.assertRaises(generator.ValidationError): generator.generate_document("nda", {}, False)
        bad = dict(SAMPLES["nda"], term_years="abc")
        with self.assertRaises(generator.ValidationError): generator.generate_document("nda", bad, False)
        with self.assertRaises(generator.ValidationError): generator.generate_document("nope", {}, False)

    def test_facts_present(self):
        doc = generator.generate_document("employment_contract", SAMPLES["employment_contract"], False)
        text = doc.preamble + " ".join(s.body for s in doc.sections) + " ".join(t.value for t in doc.terms)
        for fact in ("Nimbus Labs Pvt Ltd", "Priya Raman", "INR 1,200,000", "1 November 2026", "Backend Engineer", "30 days"):
            self.assertIn(fact, text)

    def test_ai_accepts_valid_and_rejects_dropped_facts(self):
        base = generator.generate_document("nda", SAMPLES["nda"], False)
        good = '{"sections":' + __import__("json").dumps([s.model_dump() for s in base.sections]).replace("Receiving Party", "Recipient") + "}"
        with mock.patch.object(config, "ANTHROPIC_API_KEY", "k"), mock.patch.object(generator, "_call_claude", return_value="```json\n" + good + "\n```"):
            self.assertEqual(generator.generate_document("nda", SAMPLES["nda"]).generated_by, "ai")
        short = '{"sections":[{"heading":"Only","body":"One clause."}]}'
        for bad in (short, "not json at all"):
            with mock.patch.object(config, "ANTHROPIC_API_KEY", "k"), mock.patch.object(generator, "_call_claude", return_value=bad):
                self.assertEqual(generator.generate_document("nda", SAMPLES["nda"]).generated_by, "template")

    def test_ai_failure_falls_back(self):
        with mock.patch.object(config, "ANTHROPIC_API_KEY", "k"), mock.patch.object(generator, "_call_claude", side_effect=OSError("down")):
            self.assertEqual(generator.generate_document("nda", SAMPLES["nda"]).generated_by, "template")

    def test_logo_validation(self):
        self.assertIsNone(process_logo(None))
        self.assertEqual(process_logo(logo_data_url("JPEG"))[1:], (300, 120))
        for bad in ("data:image/png;base64,AAAA", "data:text/html;base64,PGI+", "http://x/y.png"):
            with self.assertRaises(ValueError): process_logo(bad)

    def test_sanitise_and_ratelimit(self):
        self.assertEqual(clean_text("a\x00b\n  c"), "ab c")
        rl = RateLimiter(2)
        self.assertTrue(rl.allow("a") and rl.allow("a")); self.assertFalse(rl.allow("a")); self.assertTrue(rl.allow("b"))

    def test_xml_special_chars_and_unicode(self):
        data = dict(SAMPLES["nda"], purpose="R&D <review> of “caf\u00e9” plans \u20b9 \u0b87")
        doc = generator.generate_document("nda", data, False)
        for fmt, (fn, _) in EXPORTERS.items():
            self.assertGreater(len(fn(doc, Branding())), 500)


if __name__ == "__main__":
    unittest.main()
