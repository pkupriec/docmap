from __future__ import annotations

from pydantic import BaseModel


class LocationResponse(BaseModel):
    location_id: str
    name: str
    latitude: float
    longitude: float
    precision: str | None = None
    location_rank: str | None = None
    document_count: int
    parent_location_id: str | None = None


class DocumentCard(BaseModel):
    document_id: str
    scp_number: str
    canonical_scp_id: str
    scp_url: str
    location_display: str | None = None
    pdf_url: str | None = None


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
    location_rank: str | None = None
    evidence_quote: str | None = None
    mention_count: int


class DensityPoint(BaseModel):
    latitude: float
    longitude: float
    document_count: int


class SearchResponse(BaseModel):
    query: str
    documents: list[DocumentCard]
    locations: list[LocationResponse]
