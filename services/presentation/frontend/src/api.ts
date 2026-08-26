import type {
  BoundaryCollection,
  BoundariesRequestOptions,
  BakedManifest,
  BakedTileIndex,
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
  if (options?.ranks && options.ranks.length > 0) {
    params.set("ranks", options.ranks.join(","));
  }
  if (options?.chunk_ids && options.chunk_ids.length > 0) {
    params.set("chunk_ids", options.chunk_ids.join(","));
  }
  if (options?.viewport_bucket) {
    params.set("viewport_bucket", options.viewport_bucket);
  }
  if (options?.bbox) {
    params.set("bbox", options.bbox.join(","));
  }
  if (options?.selected_location_id) {
    params.set("selected_location_id", options.selected_location_id);
  }
  if (options?.highlighted_location_ids && options.highlighted_location_ids.length > 0) {
    params.set("highlighted_location_ids", options.highlighted_location_ids.join(","));
  }
  return getJson<BoundaryCollection>(`/api/map/boundaries?${params.toString()}`);
}

export function fetchBakedManifest(mode?: string): Promise<BakedManifest> {
  const params = new URLSearchParams();
  if (mode) {
    params.set("mode", mode);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return getJson<BakedManifest>(`/api/map/baked/manifest${suffix}`);
}

export function fetchBakedTileIndex(mode?: string): Promise<BakedTileIndex> {
  const params = new URLSearchParams();
  if (mode) {
    params.set("mode", mode);
  }
  const suffix = params.size > 0 ? `?${params.toString()}` : "";
  return getJson<BakedTileIndex>(`/api/map/baked/tile-index${suffix}`);
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
