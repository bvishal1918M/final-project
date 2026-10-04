# LegalEase — AI-Powered Legal Document Generator

Generate employment contracts, NDAs, residential leases and freelance/service agreements from a short form.
Edit the result in the browser, add your company branding (logo, font, colour, footer) and export to
**PDF, DOCX or TXT**. Built with **FastAPI** and an optional **Claude** AI core.

> LegalEase produces drafts, not legal advice. Have a qualified lawyer review any document before signing.

## Quick start

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env                                    # optional: add ANTHROPIC_API_KEY
export $(grep -v '^#' .env | xargs)                     # or set the variable your own way
uvicorn app.main:app --reload
```

Open <http://localhost:8000> (interactive API docs: <http://localhost:8000/docs>).

Docker: `docker build -t legalease . && docker run -p 8000:8000 -e ANTHROPIC_API_KEY=... legalease`

## How it works

```
form input ─► validate & sanitise ─► deterministic template draft (facts) ─► [optional] AI polish ─► verified document
                                                                                      │
        editable preview in browser  ◄───────────────────────────────────────────────┘
                     │
                     └─► POST /api/export/{pdf|docx|txt}  (+ branding, logo)  ─► file download
```

* **Template mode (no key needed):** each document type has a clause builder in `app/doc_types.py`. Output is
  fully offline and deterministic.
* **AI mode (`ANTHROPIC_API_KEY` set):** Claude rewrites the clauses into polished, tailored prose. Facts always come
  from your form, never from the model. The rewrite is **rejected and the template draft is used instead** if the
  call fails, the JSON is malformed, the section count is unreasonable, the governing-law clause is missing, or any
  key party name / address / job title no longer appears in the text. Your input is sent as data, not instructions.
* **Editable preview:** change the title, preamble, key-terms table, any clause text, reorder / delete / add clauses
  and edit signatories. Exports use exactly what you see.
* **Branding:** logo (PNG/JPEG ≤ 2 MB), company name, font (serif / sans / mono), accent colour, footer text.
  Applied consistently to PDF and DOCX; TXT carries the company name and footer.

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | status, whether AI is enabled |
| GET | `/api/templates` | document types and their form fields |
| POST | `/api/generate` | `{document_type, data, use_ai}` → structured document JSON |
| POST | `/api/export/{pdf\|docx\|txt}` | `{document, branding}` → file download |

## Project layout

```
app/
  main.py        routes, rate limiting, security headers, static hosting
  doc_types.py   document registry: form fields + clause builders (add new document types here)
  generator.py   validation, template baseline, AI polish with fact verification
  exporters.py   TXT / DOCX (python-docx) / PDF (ReportLab) with branding
  security.py    input cleaning, logo validation/re-encoding, rate limiter
  schemas.py     Pydantic models
  static/        index.html, style.css, app.js (no build step)
tests/           test_core.py (no web framework needed), test_api.py (needs FastAPI)
```

## Adding a document type

In `app/doc_types.py` write a `build_xxx(d) -> LegalDocument` function, then add a `DocType(...)` entry to `REGISTRY`
with its form fields and "anchor" fields (values the AI must preserve). The form UI and API pick it up automatically.

## Data security

* No database, no files written, no user content logged. Everything is processed in memory per request.
* Input is length-limited and stripped of control characters; request bodies are capped at 4 MB.
* Logos are fully decoded and **re-encoded as PNG** (strips metadata, rejects non-images) before use.
* Strict Content-Security-Policy (no inline scripts), `X-Frame-Options: DENY`, `nosniff`, `no-store` caching.
* Per-IP rate limiting (default 30 API calls / minute, `LEGALEASE_RATE_LIMIT`). It is in-memory, so behind multiple
  workers use a shared limiter or your proxy's rate limiting.
* The browser UI builds DOM with `textContent`, so user text can't inject markup.
* When AI mode is on, form content is sent to the Anthropic API to draft your document. Leave the key unset to keep
  everything local. For production, serve over HTTPS and add authentication.

## Fonts and currencies

PDFs use DejaVu fonts when found (system folders or `app/fonts/`), giving full Unicode (₹, accents, many scripts).
Without them, PDFs fall back to built-in fonts and unsupported characters become `?`. The Docker image installs DejaVu.
Money is written with currency codes (e.g. `INR 25,000`), which render everywhere.

## Tests

```bash
python -m unittest discover -s tests -v        # core logic and exporters
pip install -r requirements-dev.txt && pytest  # adds HTTP-level tests
```
