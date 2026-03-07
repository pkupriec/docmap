from __future__ import annotations

from pydantic import BaseModel, Field


class LocationMentionPayload(BaseModel):
    mention_text: str
    normalized_location: str
    precision: str
    relation_type: str = "unspecified"
    confidence: float = Field(ge=0.0, le=1.0)
    evidence_quote: str


class ExtractionPayload(BaseModel):
    locations: list[LocationMentionPayload]
