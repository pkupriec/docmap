import type {
  BoundaryCollection,
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

export function fetchBoundaries(): Promise<BoundaryCollection> {
  return getJson<BoundaryCollection>("/api/map/boundaries");
}

export function fetchLocationDocuments(locationId: string): Promise<LocationDocumentsResponse> {
  return getJson<LocationDocumentsResponse>(`/api/map/location/${locationId}/documents`);
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
