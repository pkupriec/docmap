from __future__ import annotations

from pydantic import BaseModel


class LocationResponse(BaseModel):
    location_id: str
    name: str
    latitude: float
    longitude: float
    precision: str | None = None
    document_count: int
    parent_location_id: str | None = None


class DocumentCard(BaseModel):
    document_id: str
    scp_object_id: str | None = None
    title: str | None = None
    url: str
    preview_text: str | None = None
    evidence_quote: str | None = None
    mention_count: int


class LocationDocumentsResponse(BaseModel):
    requested_location_id: str
    resolved_location_id: str | None = None
    fallback_depth: int | None = None
    items: list[DocumentCard]


class DocumentLocationLink(BaseModel):
    document_id: str
    location_id: str
    name: str
    latitude: float
    longitude: float
    precision: str | None = None
    evidence_quote: str | None = None
    mention_count: int


class DensityPoint(BaseModel):
    latitude: float
    longitude: float
    document_count: int

