export type LocationRank = "country" | "region" | "city";

export type Location = {
  location_id: string;
  name: string;
  latitude: number;
  longitude: number;
  precision: string | null;
  document_count: number;
  parent_location_id: string | null;
};

export type DocumentCard = {
  document_id: string;
  scp_number: string;
  canonical_scp_id: string;
  scp_url: string;
  location_display: string | null;
  pdf_url: string | null;
};

export type LocationDocumentsResponse = {
  requested_location_id: string;
  resolved_location_id: string | null;
  fallback_depth: number | null;
  items: DocumentCard[];
};

export type DocumentLocation = {
  document_id: string;
  location_id: string;
  name: string;
  latitude: number;
  longitude: number;
  precision: string | null;
  evidence_quote: string | null;
  mention_count: number;
};

export type SearchResponse = {
  query: string;
  documents: DocumentCard[];
  locations: Location[];
};

export type MapViewport = {
  zoom: number;
  west: number;
  east: number;
  south: number;
  north: number;
};

export type ScreenPoint = {
  x: number;
  y: number;
};
