import { useCallback, useEffect, useMemo, useState } from "react";

import { fetchDocumentLocations, fetchLocationDocuments, fetchLocations } from "./api";
import { MapView } from "./MapView";
import type { DocumentCard, DocumentLocation, Location } from "./types";

type UiStatus = "loading" | "ready" | "error";

export default function App() {
  const [status, setStatus] = useState<UiStatus>("loading");
  const [locations, setLocations] = useState<Location[]>([]);
  const [documents, setDocuments] = useState<DocumentCard[]>([]);
  const [hoverLocationId, setHoverLocationId] = useState<string | null>(null);
  const [pinnedLocationId, setPinnedLocationId] = useState<string | null>(null);
  const [hoveredDocumentId, setHoveredDocumentId] = useState<string | null>(null);
  const [highlightLinks, setHighlightLinks] = useState<DocumentLocation[]>([]);
  const [linksByDocumentId, setLinksByDocumentId] = useState<Record<string, DocumentLocation[]>>({});
  const [fallbackDepth, setFallbackDepth] = useState<number | null>(null);

  const selectedLocationId = pinnedLocationId ?? hoverLocationId;

  useEffect(() => {
    let cancelled = false;
    fetchLocations()
      .then((items) => {
        if (cancelled) {
          return;
        }
        setLocations(items);
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedLocationId) {
      setDocuments([]);
      setFallbackDepth(null);
      return;
    }
    let cancelled = false;
    fetchLocationDocuments(selectedLocationId)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setDocuments(payload.items);
        setFallbackDepth(payload.fallback_depth);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [selectedLocationId]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setPinnedLocationId(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  useEffect(() => {
    if (!hoveredDocumentId || !selectedLocationId) {
      setHighlightLinks([]);
      return;
    }
    const cached = linksByDocumentId[hoveredDocumentId];
    if (cached) {
      setHighlightLinks(cached);
      return;
    }
    let cancelled = false;
    fetchDocumentLocations(hoveredDocumentId)
      .then((items) => {
        if (cancelled) {
          return;
        }
        setLinksByDocumentId((state) => ({ ...state, [hoveredDocumentId]: items }));
        setHighlightLinks(items);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setHighlightLinks([]);
      });
    return () => {
      cancelled = true;
    };
  }, [hoveredDocumentId, linksByDocumentId, selectedLocationId]);

  const selectedLocation = useMemo(
    () => locations.find((item) => item.location_id === selectedLocationId) ?? null,
    [locations, selectedLocationId],
  );

  const onHoverLocation = useCallback(
    (locationId: string | null) => {
      if (pinnedLocationId) {
        return;
      }
      setHoverLocationId(locationId);
    },
    [pinnedLocationId],
  );

  const onClickLocation = useCallback((locationId: string | null) => {
    if (!locationId) {
      setPinnedLocationId(null);
      return;
    }
    setPinnedLocationId(locationId);
    setHoverLocationId(locationId);
  }, []);

  const onClear = useCallback(() => {
    setPinnedLocationId(null);
  }, []);

  return (
    <div className="layout">
      <aside className="left-panel">
        <h1>DocMap</h1>
        <p className="caption">Presentation Layer</p>
        <p>Locations: {locations.length}</p>
        <button type="button" onClick={onClear}>
          Clear
        </button>
      </aside>
      <main className="map-panel">
        <MapView
          locations={locations}
          selectedLocationId={selectedLocationId}
          links={highlightLinks}
          onHoverLocation={onHoverLocation}
          onClickLocation={onClickLocation}
        />
      </main>
      <aside className="right-panel">
        <h2>{selectedLocation ? selectedLocation.name : "Documents"}</h2>
        {fallbackDepth !== null && fallbackDepth > 0 ? (
          <p className="fallback-note">Fallback depth: {fallbackDepth}</p>
        ) : null}
        {status === "loading" && <p>Loading...</p>}
        {status === "error" && <p>Unable to load data.</p>}
        {status === "ready" && !selectedLocation && <p>Explore the map to discover SCP documents.</p>}
        {status === "ready" && selectedLocation && documents.length === 0 && <p>No linked documents.</p>}
        <div className="cards">
          {documents.map((doc) => (
            <article
              key={doc.document_id}
              className="doc-card"
              onMouseEnter={() => setHoveredDocumentId(doc.document_id)}
              onMouseLeave={() => setHoveredDocumentId(null)}
            >
              <header>{doc.scp_object_id ?? "SCP"}</header>
              <h3>{doc.title ?? "Untitled"}</h3>
              <p>{doc.preview_text ?? "No preview text available."}</p>
              <a href={doc.url} target="_blank" rel="noreferrer">
                Open source
              </a>
            </article>
          ))}
        </div>
      </aside>
    </div>
  );
}

