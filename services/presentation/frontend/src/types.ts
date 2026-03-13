export type LocationRank =
  | "city"
  | "admin_region"
  | "region"
  | "country"
  | "continent"
  | "ocean"
  | "unknown";

export type Location = {
  location_id: string;
  name: string;
  latitude: number;
  longitude: number;
  precision: string | null;
  location_rank: LocationRank | null;
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
  location_rank: LocationRank | null;
  evidence_quote: string | null;
  mention_count: number;
};

export type SearchResponse = {
  query: string;
  documents: DocumentCard[];
  locations: Location[];
};

export type BoundaryGeometry = {
  type: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
};

export type BoundaryFeature = {
  type: "Feature";
  properties: {
    location_id?: string;
    location_name?: string;
    location_rank?: string;
    country_name?: string | null;
    region_name?: string | null;
    match_strategy?: string;
  };
  geometry: BoundaryGeometry;
};

export type BoundaryCollection = {
  type: "FeatureCollection";
  features: BoundaryFeature[];
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
