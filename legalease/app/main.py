"""LegalEase FastAPI application.

Run:  uvicorn app.main:app --reload
Docs: http://localhost:8000/docs
"""
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from . import config
from .doc_types import REGISTRY
from .exporters import EXPORTERS
from .generator import ValidationError, generate_document
from .schemas import ExportRequest, GenerateRequest, LegalDocument
from .security import RateLimiter, process_logo

STATIC = Path(__file__).parent / "static"
limiter = RateLimiter(config.RATE_LIMIT_PER_MIN)

app = FastAPI(title="LegalEase", version="1.0.0",
              description="AI-powered legal document generator: employment contracts, NDAs, leases and more.")

CSP = ("default-src 'self'; img-src 'self' data: blob:; style-src 'self'; script-src 'self'; "
       "connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")


@app.middleware("http")
async def guard(request: Request, call_next):
    """Rate-limit API calls, cap body size, and attach security headers."""
    if request.url.path.startswith("/api/"):
        ip = request.client.host if request.client else "unknown"
        if not limiter.allow(ip):
            return JSONResponse({"detail": "Too many requests. Please wait a moment."}, status_code=429)
        if int(request.headers.get("content-length") or 0) > config.MAX_REQUEST_BYTES:
            return JSONResponse({"detail": "Request too large."}, status_code=413)
    response = await call_next(request)
    response.headers.update({
        "Content-Security-Policy": CSP, "X-Content-Type-Options": "nosniff", "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer", "Cache-Control": "no-store"})
    return response


@app.get("/api/health")
def health():
    return {"status": "ok", "ai_enabled": bool(config.ANTHROPIC_API_KEY), "model": config.AI_MODEL}


@app.get("/api/templates")
def templates():
    """Document types and the form fields the UI should render for each."""
    return [{"key": t.key, "label": t.label, "description": t.description, "fields": t.fields}
            for t in REGISTRY.values()]


@app.post("/api/generate", response_model=LegalDocument)
def generate(req: GenerateRequest):
    try:
        return generate_document(req.document_type, req.data, req.use_ai)
    except ValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc))


@app.post("/api/export/{fmt}")
def export(fmt: str, req: ExportRequest):
    """Render the (possibly user-edited) document with branding as pdf, docx or txt."""
    if fmt not in EXPORTERS:
        raise HTTPException(status_code=404, detail="Format must be one of: pdf, docx, txt.")
    try:
        logo = process_logo(req.branding.logo_data_url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    render, mime = EXPORTERS[fmt]
    payload = render(req.document, req.branding, logo)
    slug = re.sub(r"[^a-z0-9]+", "-", req.document.title.lower()).strip("-")[:60] or "document"
    return Response(payload, media_type=mime,
                    headers={"Content-Disposition": f'attachment; filename="{slug}.{fmt}"'})


@app.get("/")
def index():
    return FileResponse(STATIC / "index.html")


app.mount("/static", StaticFiles(directory=STATIC), name="static")
