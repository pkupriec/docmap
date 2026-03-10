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
  scp_object_id: string | null;
  title: string | null;
  url: string;
  preview_text: string | null;
  evidence_quote: string | null;
  mention_count: number;
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

