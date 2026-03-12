import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchDocumentLocations, fetchLocationDocuments, fetchLocations, fetchSearch } from "./api";
import { MapView } from "./MapView";
import { PdfThumbnail } from "./PdfThumbnail";
import type {
  DocumentCard,
  DocumentLocation,
  Location,
  LocationDocumentsResponse,
  MapViewport,
  ScreenPoint,
  SearchResponse,
} from "./types";

type UiStatus = "loading" | "ready" | "error";

function isFiniteCoordinate(latitude: number, longitude: number): boolean {
  return (
    Number.isFinite(latitude) &&
    Number.isFinite(longitude) &&
    latitude >= -90 &&
    latitude <= 90 &&
    longitude >= -180 &&
    longitude <= 180
  );
}

function isInViewport(location: DocumentLocation, viewport: MapViewport | null): boolean {
  if (!viewport) {
    return false;
  }
  const { west, east, south, north } = viewport;
  const latInside = location.latitude >= south && location.latitude <= north;
  const lonInside =
    west <= east
      ? location.longitude >= west && location.longitude <= east
      : location.longitude >= west || location.longitude <= east;
  return latInside && lonInside;
}

function buildUmbrellaPath(source: ScreenPoint, anchorY: number, target: ScreenPoint): string {
  return `M ${source.x} ${source.y} L ${source.x} ${anchorY} L ${target.x} ${anchorY} L ${target.x} ${target.y}`;
}

export default function App() {
  const [status, setStatus] = useState<UiStatus>("loading");
  const [locations, setLocations] = useState<Location[]>([]);
  const [locationDocuments, setLocationDocuments] = useState<DocumentCard[]>([]);
  const [hoveredLocationId, setHoveredLocationId] = useState<string | null>(null);
  const [pinnedLocationId, setPinnedLocationId] = useState<string | null>(null);
  const [hoveredDocumentId, setHoveredDocumentId] = useState<string | null>(null);
  const [pinnedDocumentId, setPinnedDocumentId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResponse>({ query: "", documents: [], locations: [] });
  const [visibleDocumentLinks, setVisibleDocumentLinks] = useState<DocumentLocation[]>([]);
  const [pdfModalDocumentId, setPdfModalDocumentId] = useState<string | null>(null);
  const [fallbackDepth, setFallbackDepth] = useState<number | null>(null);
  const [mapViewport, setMapViewport] = useState<MapViewport | null>(null);
  const [projector, setProjector] = useState<((longitude: number, latitude: number) => ScreenPoint) | null>(null);
  const [isLeftPanelCollapsed, setIsLeftPanelCollapsed] = useState(false);
  const [offscreenLinkCount, setOffscreenLinkCount] = useState(0);
  const [searchDocumentCoordinates, setSearchDocumentCoordinates] = useState<
    Array<{ latitude: number; longitude: number }>
  >([]);

  const linksByDocumentIdRef = useRef<Record<string, DocumentLocation[]>>({});
  const cardRefs = useRef<Record<string, HTMLElement | null>>({});

  const selectedLocationId = pinnedLocationId ?? hoveredLocationId;
  const searchActive = searchQuery.trim().length >= 3;

  useEffect(() => {
    let cancelled = false;
    fetchLocations()
      .then((items) => {
        if (cancelled) {
          return;
        }
        setLocations(items.filter((item) => isFiniteCoordinate(item.latitude, item.longitude)));
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
    if (!selectedLocationId || searchActive) {
      setLocationDocuments([]);
      setFallbackDepth(null);
      return;
    }
    let cancelled = false;
    fetchLocationDocuments(selectedLocationId)
      .then((payload: LocationDocumentsResponse) => {
        if (cancelled) {
          return;
        }
        setLocationDocuments(payload.items);
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
  }, [selectedLocationId, searchActive]);

  useEffect(() => {
    if (!searchActive) {
      setSearchResults({ query: "", documents: [], locations: [] });
      setSearchDocumentCoordinates([]);
      return;
    }
    const handle = window.setTimeout(() => {
      fetchSearch(searchQuery.trim(), 5)
        .then((payload) => {
          setSearchResults(payload);
        })
        .catch(() => {
          setStatus("error");
        });
    }, 180);
    return () => window.clearTimeout(handle);
  }, [searchActive, searchQuery]);

  const displayedDocuments = searchActive ? searchResults.documents : locationDocuments;
  const uniqueDisplayedDocuments = useMemo(
    () =>
      Array.from(
        new Map(displayedDocuments.map((item) => [item.document_id, item])).values(),
      ),
    [displayedDocuments],
  );
  const activeVisualizationDocumentId = pinnedDocumentId ?? hoveredDocumentId;

  useEffect(() => {
    if (!searchActive || searchResults.documents.length === 0) {
      setSearchDocumentCoordinates([]);
      return;
    }
    if (searchResults.locations.length > 0) {
      setSearchDocumentCoordinates([]);
      return;
    }

    let cancelled = false;
    const uniqueDocumentIds = Array.from(
      new Set(searchResults.documents.map((item) => item.document_id)),
    );

    Promise.all(uniqueDocumentIds.map((documentId) => fetchDocumentLocations(documentId)))
      .then((allLinks) => {
        if (cancelled) {
          return;
        }
        const byKey = new Map<string, { latitude: number; longitude: number }>();
        for (const links of allLinks) {
          for (const link of links) {
            if (!isFiniteCoordinate(link.latitude, link.longitude)) {
              continue;
            }
            const key = `${link.latitude.toFixed(6)}:${link.longitude.toFixed(6)}`;
            if (!byKey.has(key)) {
              byKey.set(key, { latitude: link.latitude, longitude: link.longitude });
            }
          }
        }
        setSearchDocumentCoordinates(Array.from(byKey.values()));
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setSearchDocumentCoordinates([]);
      });

    return () => {
      cancelled = true;
    };
  }, [searchActive, searchResults.documents, searchResults.locations.length]);

  useEffect(() => {
    if (!activeVisualizationDocumentId) {
      setVisibleDocumentLinks([]);
      setOffscreenLinkCount(0);
      return;
    }

    const cached = linksByDocumentIdRef.current[activeVisualizationDocumentId];
    if (cached) {
      const visible = cached.filter((item) => isInViewport(item, mapViewport));
      setVisibleDocumentLinks(visible);
      setOffscreenLinkCount(cached.length - visible.length);
      return;
    }

    let cancelled = false;
    fetchDocumentLocations(activeVisualizationDocumentId)
      .then((items) => {
        if (cancelled) {
          return;
        }
        const validItems = items.filter((item) =>
          isFiniteCoordinate(item.latitude, item.longitude),
        );
        linksByDocumentIdRef.current[activeVisualizationDocumentId] = validItems;
        const visible = validItems.filter((item) => isInViewport(item, mapViewport));
        setVisibleDocumentLinks(visible);
        setOffscreenLinkCount(validItems.length - visible.length);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setVisibleDocumentLinks([]);
        setOffscreenLinkCount(0);
      });

    return () => {
      cancelled = true;
    };
  }, [activeVisualizationDocumentId, mapViewport]);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape") {
        return;
      }
      if (pdfModalDocumentId) {
        setPdfModalDocumentId(null);
      }
      setPinnedDocumentId(null);
      setPinnedLocationId(null);
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [pdfModalDocumentId]);

  const searchFocusCoordinates = useMemo(
    () => {
      if (!searchActive) {
        return [];
      }
      if (searchResults.locations.length > 0) {
        return searchResults.locations
          .filter((item) => isFiniteCoordinate(item.latitude, item.longitude))
          .map((item) => ({
            latitude: item.latitude,
            longitude: item.longitude,
          }));
      }
      return searchDocumentCoordinates;
    },
    [searchActive, searchResults.locations, searchDocumentCoordinates],
  );

  const onHoverLocation = useCallback(
    (locationId: string | null) => {
      if (pinnedLocationId) {
        return;
      }
      setHoveredLocationId(locationId);
    },
    [pinnedLocationId],
  );

  const onClickLocation = useCallback((locationId: string) => {
    setPinnedLocationId(locationId);
    setHoveredLocationId(locationId);
  }, []);

  const onClear = useCallback(() => {
    setPinnedLocationId(null);
    setPinnedDocumentId(null);
    setPdfModalDocumentId(null);
  }, []);

  const onEmptyMapClick = useCallback(() => {
    setPinnedDocumentId(null);
    setPinnedLocationId(null);
  }, []);

  const onProjectorChange = useCallback(
    (next: ((longitude: number, latitude: number) => ScreenPoint) | null) => {
      setProjector(() => next);
    },
    [],
  );

  const selectedLocation = useMemo(
    () => locations.find((item) => item.location_id === selectedLocationId) ?? null,
    [locations, selectedLocationId],
  );

  const linkPaths = useMemo(() => {
    if (!activeVisualizationDocumentId || !projector) {
      return [];
    }
    const card = cardRefs.current[activeVisualizationDocumentId];
    if (!card || visibleDocumentLinks.length === 0) {
      return [];
    }

    const cardRect = card.getBoundingClientRect();
    const source = {
      x: cardRect.left + cardRect.width / 2,
      y: cardRect.top + cardRect.height / 2,
    };
    const anchorY = source.y + 28;

    return visibleDocumentLinks.map((link) => {
      const target = projector(link.longitude, link.latitude);
      return buildUmbrellaPath(source, anchorY, target);
    });
  }, [activeVisualizationDocumentId, projector, visibleDocumentLinks]);

  const panelTitle = searchActive
    ? `Search: ${searchResults.query || searchQuery.trim()}`
    : selectedLocation
      ? selectedLocation.name
      : "Documents";

  return (
    <div className="layout-root">
      <svg className="umbrella-overlay" aria-hidden="true">
        {linkPaths.map((path, index) => (
          <path key={`${index}-${path}`} d={path} className="umbrella-line" />
        ))}
      </svg>

      <div className={`layout ${isLeftPanelCollapsed ? "left-collapsed" : ""}`}>
        <aside className="left-panel">
          <button
            type="button"
            className="collapse-toggle"
            onClick={() => setIsLeftPanelCollapsed((state) => !state)}
            aria-label={isLeftPanelCollapsed ? "Expand controls" : "Collapse controls"}
          >
            {isLeftPanelCollapsed ? ">" : "<"}
          </button>
          {!isLeftPanelCollapsed ? (
            <>
              <h1>DocMap</h1>
              <p className="caption">Presentation Layer</p>
              <p>Locations: {locations.length}</p>
              <button type="button" onClick={onClear}>
                Clear
              </button>
            </>
          ) : null}
        </aside>

        <main className="map-panel">
          <MapView
            locations={locations}
            selectedLocationId={selectedLocationId}
            onHoverLocation={onHoverLocation}
            onClickLocation={onClickLocation}
            onEmptyMapClick={onEmptyMapClick}
            onViewportChange={setMapViewport}
            onProjectorChange={onProjectorChange}
            focusCoordinates={searchFocusCoordinates}
          />
        </main>

        <aside className="right-panel">
          <div className="search-row">
            <input
              type="search"
              value={searchQuery}
              placeholder="Search SCP or location"
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <h2>{panelTitle}</h2>
          {fallbackDepth !== null && fallbackDepth > 0 && !searchActive ? (
            <p className="fallback-note">Fallback depth: {fallbackDepth}</p>
          ) : null}
          {status === "loading" && <p>Loading...</p>}
          {status === "error" && <p>Unable to load data.</p>}

          {status === "ready" && searchActive ? (
            <div className="search-result-locations">
              {searchResults.locations.map((location) => (
                <button
                  key={location.location_id}
                  type="button"
                  className="search-location-chip"
                  onClick={() => onClickLocation(location.location_id)}
                >
                  {location.name}
                </button>
              ))}
            </div>
          ) : null}

          {status === "ready" && !searchActive && !selectedLocation && <p>Explore the map to discover SCP documents.</p>}
          {status === "ready" && uniqueDisplayedDocuments.length === 0 && (searchActive || selectedLocation) ? <p>No linked documents.</p> : null}

          <div className="cards">
            {uniqueDisplayedDocuments.map((doc) => (
              <article
                key={doc.document_id}
                className={`doc-card ${pinnedDocumentId === doc.document_id ? "doc-card-pinned" : ""}`}
                ref={(element) => {
                  cardRefs.current[doc.document_id] = element;
                }}
                onMouseEnter={() => setHoveredDocumentId(doc.document_id)}
                onMouseLeave={() => setHoveredDocumentId((current) => (current === doc.document_id ? null : current))}
                onClick={() => {
                  setPinnedDocumentId((current) => {
                    if (current === doc.document_id) {
                      return null;
                    }
                    return doc.document_id;
                  });
                  setHoveredDocumentId(doc.document_id);
                  setPdfModalDocumentId((current) => (current && current !== doc.document_id ? null : current));
                }}
              >
                <header>
                  <a href={doc.scp_url} target="_blank" rel="noreferrer" onClick={(event) => event.stopPropagation()}>
                    {doc.scp_number}
                  </a>
                </header>
                <p className="card-location">{doc.location_display ?? "Unknown location"}</p>

                <PdfThumbnail
                  pdfUrl={doc.pdf_url}
                  alt={`Preview for ${doc.scp_number}`}
                  onClick={() => {
                    setPinnedDocumentId(doc.document_id);
                    setPdfModalDocumentId(doc.document_id);
                  }}
                />

                {activeVisualizationDocumentId === doc.document_id ? (
                  <p className="offscreen-count">Offscreen linked locations: {offscreenLinkCount}</p>
                ) : null}
              </article>
            ))}
          </div>
        </aside>
      </div>

      {pdfModalDocumentId ? (
        <div
          className="pdf-modal-backdrop"
          role="button"
          tabIndex={-1}
          onClick={(event) => {
            if (event.target === event.currentTarget) {
              setPdfModalDocumentId(null);
            }
          }}
        >
          <div className="pdf-modal" role="dialog" aria-modal="true">
            <button type="button" className="pdf-close" onClick={() => setPdfModalDocumentId(null)}>
              Close
            </button>
            <iframe
              title="Document PDF"
              src={`/api/map/document/${pdfModalDocumentId}/pdf`}
              className="pdf-frame"
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
