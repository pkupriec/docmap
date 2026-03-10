import type {
  DocumentLocation,
  Location,
  LocationDocumentsResponse,
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

export function fetchLocationDocuments(locationId: string): Promise<LocationDocumentsResponse> {
  return getJson<LocationDocumentsResponse>(`/api/map/location/${locationId}/documents`);
}

export function fetchDocumentLocations(documentId: string): Promise<DocumentLocation[]> {
  return getJson<DocumentLocation[]>(`/api/map/document/${documentId}/locations`);
}

