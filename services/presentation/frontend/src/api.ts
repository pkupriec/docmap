import type {
  BoundaryCollection,
  BoundariesRequestOptions,
  DocumentCard,
  DocumentLocation,
  Location,
  LocationDocumentsResponse,
  SearchResponse,
} from "./types";

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(path);
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchLocations(): Promise<Location[]> {
  return getJson<Location[]>("/api/map/locations");
}

export function fetchBoundaries(options?: BoundariesRequestOptions): Promise<BoundaryCollection> {
  const params = new URLSearchParams();
  params.set("lite", options?.lite ? "1" : "0");
  if (options?.rank_filter) {
    params.set("rank_filter", options.rank_filter);
  }
  if (options?.geometry_detail) {
    params.set("geometry_detail", options.geometry_detail);
  }
  return getJson<BoundaryCollection>(`/api/map/boundaries?${params.toString()}`);
}

export function fetchLocationDocuments(
  locationId: string,
  options?: { limit?: number; offset?: number },
): Promise<LocationDocumentsResponse> {
  const params = new URLSearchParams();
  if (typeof options?.limit === "number") {
    params.set("limit", String(options.limit));
  }
  if (typeof options?.offset === "number") {
    params.set("offset", String(options.offset));
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return getJson<LocationDocumentsResponse>(`/api/map/location/${locationId}/documents${suffix}`);
}

export function fetchDocument(documentId: string): Promise<DocumentCard> {
  return getJson<DocumentCard>(`/api/map/document/${documentId}`);
}

export function fetchDocumentLocations(documentId: string): Promise<DocumentLocation[]> {
  return getJson<DocumentLocation[]>(`/api/map/document/${documentId}/locations`);
}

export function fetchSearch(query: string, limit = 5): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, limit: String(Math.min(limit, 5)) });
  return getJson<SearchResponse>(`/api/search?${params.toString()}`);
}
