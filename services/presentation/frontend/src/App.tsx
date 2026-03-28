import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import { fetchBoundaries, fetchDocumentLocations, fetchLocationDocuments, fetchLocations, fetchSearch } from "./api";
import { MapView } from "./MapView";
import { PdfThumbnail } from "./PdfThumbnail";
import type {
  BoundaryCollection,
  DocumentCard,
  DocumentLocation,
  Location,
  LocationDocumentsResponse,
  MapViewport,
  ScreenPoint,
  SearchResponse,
} from "./types";

type UiStatus = "loading" | "ready" | "error";
type ErrorContext = "startup" | "location_documents" | "search" | "unknown";
type ActiveMode =
  | "PDF Modal"
  | "Pinned Document"
  | "Document Hover"
  | "Search"
  | "Pinned Location"
  | "Hover Location"
  | "Idle";

const EMPTY_SEARCH_RESULTS: SearchResponse = { query: "", documents: [], locations: [] };
const LINK_DECLUTTER_LIMIT = 12;
const LOCATION_DOCUMENTS_PAGE_SIZE = 80;

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

function formatRank(rank: string | null | undefined): string {
  const normalized = String(rank ?? "unknown").toLowerCase();
  if (normalized === "admin_region" || normalized === "region") {
    return "Admin";
  }
  if (normalized === "country") {
    return "Country";
  }
  if (normalized === "continent") {
    return "Continent";
  }
  if (normalized === "ocean") {
    return "Ocean";
  }
  if (normalized === "city") {
    return "City";
  }
  return "Unknown";
}

function errorMessageFor(context: ErrorContext): string {
  if (context === "startup") {
    return "Unable to load locations and boundaries.";
  }
  if (context === "location_documents") {
    return "Unable to load linked documents for this location.";
  }
  if (context === "search") {
    return "Unable to load search results.";
  }
  return "Unable to load data.";
}

const EMPTY_BOUNDARIES: BoundaryCollection = {
  type: "FeatureCollection",
  features: [],
};

export default function App() {
  const [status, setStatus] = useState<UiStatus>("loading");
  const [errorContext, setErrorContext] = useState<ErrorContext>("unknown");
  const [locations, setLocations] = useState<Location[]>([]);
  const [boundaries, setBoundaries] = useState<BoundaryCollection>(EMPTY_BOUNDARIES);
  const [locationDocuments, setLocationDocuments] = useState<DocumentCard[]>([]);
  const [locationDocumentsMeta, setLocationDocumentsMeta] = useState<LocationDocumentsResponse | null>(null);
  const [isLoadingMoreDocuments, setIsLoadingMoreDocuments] = useState(false);
  const [hoveredLocationId, setHoveredLocationId] = useState<string | null>(null);
  const [pinnedLocationId, setPinnedLocationId] = useState<string | null>(null);
  const [hoveredDocumentId, setHoveredDocumentId] = useState<string | null>(null);
  const [pinnedDocumentId, setPinnedDocumentId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<SearchResponse>(EMPTY_SEARCH_RESULTS);
  const [visibleDocumentLinks, setVisibleDocumentLinks] = useState<DocumentLocation[]>([]);
  const [pdfModalDocumentId, setPdfModalDocumentId] = useState<string | null>(null);
  const [projector, setProjector] = useState<((longitude: number, latitude: number) => ScreenPoint) | null>(null);
  const [isLeftPanelCollapsed, setIsLeftPanelCollapsed] = useState(false);
  const [offscreenLinkCount, setOffscreenLinkCount] = useState(0);
  const [searchDocumentCoordinates, setSearchDocumentCoordinates] = useState<
    Array<{ latitude: number; longitude: number }>
  >([]);
  const [declutterLinks, setDeclutterLinks] = useState(true);

  const linksByDocumentIdRef = useRef<Record<string, DocumentLocation[]>>({});
  const pendingDocumentLocationsRef = useRef<Record<string, Promise<DocumentLocation[]>>>({});
  const locationDocumentsByLocationIdRef = useRef<Record<string, LocationDocumentsResponse>>({});
  const pendingLocationDocumentsRef = useRef<Record<string, Promise<LocationDocumentsResponse>>>({});
  const mapViewportRef = useRef<MapViewport | null>(null);
  const activeVisualizationDocumentIdRef = useRef<string | null>(null);
  const viewportRafRef = useRef<number | null>(null);
  const cardRefs = useRef<Record<string, HTMLElement | null>>({});
  const searchInputRef = useRef<HTMLInputElement | null>(null);

  const selectedLocationId = pinnedLocationId ?? hoveredLocationId;
  const searchActive = searchQuery.trim().length >= 3;
  const activeVisualizationDocumentId = pinnedDocumentId ?? hoveredDocumentId;

  const fetchLocationDocumentsCached = useCallback(
    async (locationId: string): Promise<LocationDocumentsResponse> => {
      const cached = locationDocumentsByLocationIdRef.current[locationId];
      if (cached) {
        return cached;
      }

      const pending = pendingLocationDocumentsRef.current[locationId];
      if (pending) {
        return pending;
      }

      const request = fetchLocationDocuments(locationId, {
        limit: LOCATION_DOCUMENTS_PAGE_SIZE,
        offset: 0,
      })
        .then((payload) => {
          locationDocumentsByLocationIdRef.current[locationId] = payload;
          return payload;
        })
        .finally(() => {
          delete pendingLocationDocumentsRef.current[locationId];
        });

      pendingLocationDocumentsRef.current[locationId] = request;
      return request;
    },
    [],
  );

  const fetchDocumentLocationsCached = useCallback(
    async (documentId: string): Promise<DocumentLocation[]> => {
      const cached = linksByDocumentIdRef.current[documentId];
      if (cached) {
        return cached;
      }

      const pending = pendingDocumentLocationsRef.current[documentId];
      if (pending) {
        return pending;
      }

      const request = fetchDocumentLocations(documentId)
        .then((items) => {
          const validItems = items.filter((item) =>
            isFiniteCoordinate(item.latitude, item.longitude),
          );
          linksByDocumentIdRef.current[documentId] = validItems;
          return validItems;
        })
        .finally(() => {
          delete pendingDocumentLocationsRef.current[documentId];
        });

      pendingDocumentLocationsRef.current[documentId] = request;
      return request;
    },
    [],
  );

  const updateVisibleLinksForActiveDocument = useCallback((documentId: string | null) => {
    if (!documentId) {
      setVisibleDocumentLinks([]);
      setOffscreenLinkCount(0);
      return;
    }

    const items = linksByDocumentIdRef.current[documentId];
    if (!items) {
      return;
    }

    const viewport = mapViewportRef.current;
    const visible = viewport ? items.filter((item) => isInViewport(item, viewport)) : [];
    setVisibleDocumentLinks(visible);
    setOffscreenLinkCount(items.length - visible.length);
  }, []);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchLocations(), fetchBoundaries()])
      .then(([items, nextBoundaries]) => {
        if (cancelled) {
          return;
        }
        setLocations(items.filter((item) => isFiniteCoordinate(item.latitude, item.longitude)));
        setBoundaries(nextBoundaries);
        setErrorContext("unknown");
        setStatus("ready");
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setErrorContext("startup");
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedLocationId || searchActive) {
      setLocationDocuments([]);
      setLocationDocumentsMeta(null);
      return;
    }
    let cancelled = false;
    fetchLocationDocumentsCached(selectedLocationId)
      .then((payload: LocationDocumentsResponse) => {
        if (cancelled) {
          return;
        }
        setLocationDocuments(payload.items);
        setLocationDocumentsMeta(payload);
      })
      .catch(() => {
        if (cancelled) {
          return;
        }
        setErrorContext("location_documents");
        setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, [fetchLocationDocumentsCached, searchActive, selectedLocationId]);

  const canLoadMoreLocationDocuments = useMemo(() => {
    if (searchActive) {
      return false;
    }
    if (!selectedLocationId || !locationDocumentsMeta) {
      return false;
    }
    return locationDocuments.length < locationDocumentsMeta.total_items;
  }, [locationDocuments.length, locationDocumentsMeta, searchActive, selectedLocationId]);

  const onLoadMoreLocationDocuments = useCallback(() => {
    if (!selectedLocationId || !locationDocumentsMeta || isLoadingMoreDocuments || searchActive) {
      return;
    }
    setIsLoadingMoreDocuments(true);
    fetchLocationDocuments(selectedLocationId, {
      limit: LOCATION_DOCUMENTS_PAGE_SIZE,
      offset: locationDocuments.length,
    })
      .then((payload) => {
        setLocationDocuments((current) =>
          Array.from(new Map([...current, ...payload.items].map((item) => [item.document_id, item])).values()),
        );
        setLocationDocumentsMeta(payload);
      })
      .catch(() => {
        setErrorContext("location_documents");
        setStatus("error");
      })
      .finally(() => {
        setIsLoadingMoreDocuments(false);
      });
  }, [
    isLoadingMoreDocuments,
    locationDocuments.length,
    locationDocumentsMeta,
    searchActive,
    selectedLocationId,
  ]);

  useEffect(() => {
    if (!searchActive) {
      setSearchResults(EMPTY_SEARCH_RESULTS);
      setSearchDocumentCoordinates([]);
      return;
    }
    const handle = window.setTimeout(() => {
      fetchSearch(searchQuery.trim(), 5)
        .then((payload) => {
          setSearchResults(payload);
        })
        .catch(() => {
          setErrorContext("search");
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

    Promise.all(uniqueDocumentIds.map((documentId) => fetchDocumentLocationsCached(documentId)))
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
  }, [
    fetchDocumentLocationsCached,
    searchActive,
    searchResults.documents,
    searchResults.locations.length,
  ]);

  useEffect(() => {
    activeVisualizationDocumentIdRef.current = activeVisualizationDocumentId;

    if (!activeVisualizationDocumentId) {
      updateVisibleLinksForActiveDocument(null);
      return;
    }

    updateVisibleLinksForActiveDocument(activeVisualizationDocumentId);

    let cancelled = false;
    fetchDocumentLocationsCached(activeVisualizationDocumentId)
      .then(() => {
        if (cancelled || activeVisualizationDocumentIdRef.current !== activeVisualizationDocumentId) {
          return;
        }
        updateVisibleLinksForActiveDocument(activeVisualizationDocumentId);
      })
      .catch(() => {
        if (cancelled || activeVisualizationDocumentIdRef.current !== activeVisualizationDocumentId) {
          return;
        }
        setVisibleDocumentLinks([]);
        setOffscreenLinkCount(0);
      });

    return () => {
      cancelled = true;
    };
  }, [
    activeVisualizationDocumentId,
    fetchDocumentLocationsCached,
    updateVisibleLinksForActiveDocument,
  ]);

  useEffect(
    () => () => {
      if (viewportRafRef.current !== null) {
        window.cancelAnimationFrame(viewportRafRef.current);
      }
    },
    [],
  );

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

  const searchFocusCoordinates = useMemo(() => {
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
  }, [searchActive, searchResults.locations, searchDocumentCoordinates]);

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

  const onViewportChange = useCallback(
    (viewport: MapViewport) => {
      mapViewportRef.current = viewport;
      if (!activeVisualizationDocumentIdRef.current) {
        return;
      }
      if (viewportRafRef.current !== null) {
        return;
      }
      viewportRafRef.current = window.requestAnimationFrame(() => {
        viewportRafRef.current = null;
        updateVisibleLinksForActiveDocument(activeVisualizationDocumentIdRef.current);
      });
    },
    [updateVisibleLinksForActiveDocument],
  );

  const selectedLocation = useMemo(
    () => locations.find((item) => item.location_id === selectedLocationId) ?? null,
    [locations, selectedLocationId],
  );

  const activeVisualizationDocument = useMemo(
    () => uniqueDisplayedDocuments.find((doc) => doc.document_id === activeVisualizationDocumentId) ?? null,
    [activeVisualizationDocumentId, uniqueDisplayedDocuments],
  );

  const highlightedLocationIds = useMemo(
    () => (searchActive ? searchResults.locations.map((location) => location.location_id) : []),
    [searchActive, searchResults.locations],
  );

  const visibleLinksToRender = useMemo(() => {
    if (!declutterLinks) {
      return visibleDocumentLinks;
    }
    return visibleDocumentLinks.slice(0, LINK_DECLUTTER_LIMIT);
  }, [declutterLinks, visibleDocumentLinks]);

  const hiddenVisibleLinkCount = Math.max(visibleDocumentLinks.length - visibleLinksToRender.length, 0);

  const linkPaths = useMemo(() => {
    if (!activeVisualizationDocumentId || !projector) {
      return [];
    }
    const card = cardRefs.current[activeVisualizationDocumentId];
    if (!card || visibleLinksToRender.length === 0) {
      return [];
    }

    const cardRect = card.getBoundingClientRect();
    const source = {
      x: cardRect.left + cardRect.width / 2,
      y: cardRect.top + cardRect.height / 2,
    };
    const anchorY = source.y + 28;
    const maxMention = Math.max(...visibleLinksToRender.map((link) => Math.max(link.mention_count, 1)), 1);

    return visibleLinksToRender.map((link) => {
      const target = projector(link.longitude, link.latitude);
      const emphasis = Math.max(link.mention_count, 1) / maxMention;
      return {
        d: buildUmbrellaPath(source, anchorY, target),
        opacity: 0.35 + emphasis * 0.5,
        width: 1.2 + emphasis * 1.8,
      };
    });
  }, [activeVisualizationDocumentId, projector, visibleLinksToRender]);

  const activeMode: ActiveMode = useMemo(() => {
    if (pdfModalDocumentId) {
      return "PDF Modal";
    }
    if (pinnedDocumentId) {
      return "Pinned Document";
    }
    if (hoveredDocumentId) {
      return "Document Hover";
    }
    if (searchActive) {
      return "Search";
    }
    if (pinnedLocationId) {
      return "Pinned Location";
    }
    if (hoveredLocationId) {
      return "Hover Location";
    }
    return "Idle";
  }, [hoveredDocumentId, hoveredLocationId, pdfModalDocumentId, pinnedDocumentId, pinnedLocationId, searchActive]);

  const panelTitle = searchActive
    ? `Search: ${searchResults.query || searchQuery.trim()}`
    : selectedLocation
      ? selectedLocation.name
      : "Documents";

  return (
    <div className="layout-root">
      <svg className="umbrella-overlay" aria-hidden="true">
        {linkPaths.map((item, index) => (
          <path
            key={`${index}-${item.d}`}
            d={item.d}
            className="umbrella-line"
            style={{ opacity: item.opacity, strokeWidth: item.width }}
          />
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
          ) : (
            <div className="left-panel-collapsed-actions">
              <button type="button" title="Focus search" onClick={() => searchInputRef.current?.focus()}>
                S
              </button>
              <button type="button" title="Clear selections" onClick={onClear}>
                C
              </button>
            </div>
          )}
        </aside>

        <main className="map-panel">
          <MapView
            locations={locations}
            boundaries={boundaries}
            selectedLocationId={selectedLocationId}
            highlightedLocationIds={highlightedLocationIds}
            onHoverLocation={onHoverLocation}
            onClickLocation={onClickLocation}
            onEmptyMapClick={onEmptyMapClick}
            onViewportChange={onViewportChange}
            onProjectorChange={onProjectorChange}
            focusCoordinates={searchFocusCoordinates}
          />

          <div className="map-legend" aria-label="Map legend">
            <h3>Legend</h3>
            <div className="legend-row"><span className="legend-dot city" /> City point</div>
            <div className="legend-row"><span className="legend-dot fallback" /> Missing boundary fallback</div>
            <div className="legend-row"><span className="legend-polygon" /> Region/Country/Continent/Ocean polygon</div>
          </div>
        </main>

        <aside className="right-panel">
          <div className="search-row">
            <input
              ref={searchInputRef}
              type="search"
              value={searchQuery}
              placeholder="Search SCP or location"
              onChange={(event) => setSearchQuery(event.target.value)}
            />
          </div>

          <div className="mode-summary-row">
            <span className="mode-pill">Mode: {activeMode}</span>
            {selectedLocation ? (
              <span className="selection-pill" title={selectedLocation.name}>
                {selectedLocation.name} · {selectedLocation.document_count} docs
              </span>
            ) : null}
          </div>

          {searchActive && status === "ready" ? (
            <p className="search-summary">
              Results: {searchResults.locations.length} locations, {searchResults.documents.length} documents
            </p>
          ) : null}

          <h2>{panelTitle}</h2>
          {locationDocumentsMeta && !searchActive ? (
            <p className="fallback-note">
              Scope: {formatRank(locationDocumentsMeta.scope_rank)} · {locationDocumentsMeta.total_items} docs from{" "}
              {locationDocumentsMeta.scope_location_count} locations
              {locationDocumentsMeta.fallback_depth && locationDocumentsMeta.fallback_depth > 0
                ? ` · alias depth ${locationDocumentsMeta.fallback_depth}`
                : ""}
            </p>
          ) : null}
          {status === "loading" && <p>Loading locations and boundaries...</p>}
          {status === "error" && <p>{errorMessageFor(errorContext)}</p>}

          {status === "ready" && searchActive ? (
            <div className="search-result-locations">
              {searchResults.locations.map((location) => (
                <button
                  key={location.location_id}
                  type="button"
                  className="search-location-chip"
                  onClick={() => onClickLocation(location.location_id)}
                >
                  <span className="chip-rank">{formatRank(location.location_rank)}</span>
                  <span>{location.name}</span>
                </button>
              ))}
            </div>
          ) : null}

          {status === "ready" && !searchActive && !selectedLocation && <p>Explore the map to discover SCP documents.</p>}
          {status === "ready" && uniqueDisplayedDocuments.length === 0 && (searchActive || selectedLocation) ? <p>No linked documents.</p> : null}

          {activeVisualizationDocumentId ? (
            <div className="link-controls">
              <label>
                <input
                  type="checkbox"
                  checked={declutterLinks}
                  onChange={(event) => setDeclutterLinks(event.target.checked)}
                />
                Declutter links (top {LINK_DECLUTTER_LIMIT})
              </label>
              {hiddenVisibleLinkCount > 0 ? <span>Hidden visible links: {hiddenVisibleLinkCount}</span> : null}
            </div>
          ) : null}

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
                <div className="card-meta-row">
                  <span className="card-meta-pill">PDF: {doc.pdf_url ? "Available" : "Missing"}</span>
                  {activeVisualizationDocument?.document_id === doc.document_id ? (
                    <span className="card-meta-pill emphasis">Active visualization</span>
                  ) : null}
                </div>

                <PdfThumbnail
                  pdfUrl={doc.pdf_url}
                  alt={`Preview for ${doc.scp_number}`}
                  onClick={() => {
                    setPinnedDocumentId(doc.document_id);
                    setPdfModalDocumentId(doc.document_id);
                  }}
                />

                {activeVisualizationDocumentId === doc.document_id ? (
                  <p className="offscreen-count badge">Offscreen linked locations: {offscreenLinkCount}</p>
                ) : null}
              </article>
            ))}
          </div>
          {canLoadMoreLocationDocuments ? (
            <div className="load-more-row">
              <button type="button" onClick={onLoadMoreLocationDocuments} disabled={isLoadingMoreDocuments}>
                {isLoadingMoreDocuments ? "Loading..." : "Load more"}
              </button>
            </div>
          ) : null}
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
