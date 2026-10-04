"""Pydantic models shared by the API, generator and exporters."""
import re
from typing import Optional
from pydantic import BaseModel, Field, field_validator


class Term(BaseModel):
    label: str = Field(max_length=200)
    value: str = Field(max_length=2000)


class Section(BaseModel):
    heading: str = Field(max_length=300)
    body: str = Field(max_length=20000)


class Signatory(BaseModel):
    name: str = Field(max_length=300)
    role: str = Field(max_length=200)


class LegalDocument(BaseModel):
    title: str = Field(max_length=300)
    document_type: str = Field("", max_length=60)
    preamble: str = Field("", max_length=5000)
    terms: list[Term] = Field(default_factory=list, max_length=60)
    sections: list[Section] = Field(default_factory=list, max_length=80)
    signatories: list[Signatory] = Field(default_factory=list, max_length=10)
    generated_by: str = Field("template", max_length=20)   # "template" | "ai"


class Branding(BaseModel):
    company_name: str = Field("", max_length=200)
    logo_data_url: Optional[str] = None          # data:image/png;base64,...
    font: str = "serif"                          # sans | serif | mono
    accent_color: str = "#1F3A5F"
    footer_text: str = Field("", max_length=300)

    @field_validator("font")
    @classmethod
    def _font(cls, v: str) -> str:
        return v if v in ("sans", "serif", "mono") else "serif"

    @field_validator("accent_color")
    @classmethod
    def _color(cls, v: str) -> str:
        return v if re.fullmatch(r"#[0-9a-fA-F]{6}", v or "") else "#1F3A5F"


class GenerateRequest(BaseModel):
    document_type: str = Field(max_length=60)
    data: dict[str, str]
    use_ai: bool = True


class ExportRequest(BaseModel):
    document: LegalDocument
    branding: Branding = Field(default_factory=Branding)
