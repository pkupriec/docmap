import type {
  BoundaryCollection,
  BoundariesRequestOptions,
  BakedManifest,
  DocumentCard,
  DocumentLocation,
  Location,
  LocationDocumentsResponse,
  SearchResponse,
} from "./types";

async function getJson<T>(path: string, signal?: AbortSignal): Promise<T> {
  const response = await fetch(path, { signal });
  if (!response.ok) {
    throw new Error(`Request failed: ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function fetchLocations(signal?: AbortSignal): Promise<Location[]> {
  return getJson<Location[]>("/api/map/locations", signal);
}

export function fetchBoundaries(options?: BoundariesRequestOptions, signal?: AbortSignal): Promise<BoundaryCollection> {
  const params = new URLSearchParams();
  if (options?.selected_location_id) {
    params.set("selected_location_id", options.selected_location_id);
  }
  if (options?.highlighted_location_ids && options.highlighted_location_ids.length > 0) {
    params.set("highlighted_location_ids", options.highlighted_location_ids.join(","));
  }
  return getJson<BoundaryCollection>(`/api/map/boundaries?${params.toString()}`, signal);
}

export function fetchBakedManifest(mode?: string, signal?: AbortSignal): Promise<BakedManifest> {
  const params = new URLSearchParams();
  if (mode) {
    params.set("mode", mode);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return getJson<BakedManifest>(`/api/map/baked/manifest${suffix}`, signal);
}

export function fetchLocationDocuments(
  locationId: string,
  options?: { limit?: number; offset?: number },
  signal?: AbortSignal,
): Promise<LocationDocumentsResponse> {
  const params = new URLSearchParams();
  if (typeof options?.limit === "number") {
    params.set("limit", String(options.limit));
  }
  if (typeof options?.offset === "number") {
    params.set("offset", String(options.offset));
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return getJson<LocationDocumentsResponse>(`/api/map/location/${locationId}/documents${suffix}`, signal);
}

export function fetchDocument(documentId: string): Promise<DocumentCard> {
  return getJson<DocumentCard>(`/api/map/document/${documentId}`);
}

export function fetchDocumentLocations(documentId: string, signal?: AbortSignal): Promise<DocumentLocation[]> {
  return getJson<DocumentLocation[]>(`/api/map/document/${documentId}/locations`, signal);
}

export function fetchSearch(query: string, limit = 5, signal?: AbortSignal): Promise<SearchResponse> {
  const params = new URLSearchParams({ q: query, limit: String(Math.min(limit, 5)) });
  return getJson<SearchResponse>(`/api/search?${params.toString()}`, signal);
}
