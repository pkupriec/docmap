import { useCallback, useEffect, useMemo, useRef, useState } from "react";

import {
  fetchBakedManifest,
  fetchBoundaries,
  fetchDocumentLocations,
  fetchLocationDocuments,
  fetchLocations,
  fetchSearch,
} from "./api";
import { lazy, Suspense } from "react";
import type { ChangeEvent } from "react";
import { DocumentPanel } from "./DocumentPanel";
const MapView = lazy(() => import("./MapView").then((module) => ({ default: module.MapView })));
import type {
  BoundaryCollection,
  BoundaryFeature,
  BakedManifest,
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
type BoundariesStatus = "loading" | "ready" | "error";
type PrecisionMode = "full_precise" | "balanced_precise" | "simplified" | "primitive";
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
const PRECISION_MODE_OPTIONS: Array<{ value: PrecisionMode; label: string }> = [
  { value: "full_precise", label: "Full precise" },
  { value: "balanced_precise", label: "Balanced precise" },
  { value: "simplified", label: "Simplified" },
  { value: "primitive", label: "Primitive" },
];

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

function toPmtilesUrl(archiveUrl: string | null | undefined): string | null {
  if (!archiveUrl) return null;
  const absoluteUrl = new URL(archiveUrl, window.location.origin).toString();
  return `pmtiles://${absoluteUrl}`;
}

type BoundaryFeatureMap = Record<string, BoundaryFeature>;
const BOUNDARY_RENDER_RANK_PRIORITY: Record<string, number> = {
  ocean: 0,
  continent: 1,
  country: 2,
  admin_region: 3,
  region: 3,
  city: 4,
  national_park: 5,
  desert: 5,
  unknown: 90,
};

function getBoundaryFeatureKey(feature: BoundaryFeature, fallbackIndex: number): string {
  const locationId = String(feature.properties.location_id ?? "").trim();
  if (locationId) {
    return locationId;
  }
  return `feature:${fallbackIndex}:${feature.properties.location_rank ?? "unknown"}:${feature.properties.location_name ?? "unknown"}`;
}

function buildBoundaryFeatureMap(collection: BoundaryCollection): BoundaryFeatureMap {
  const next: BoundaryFeatureMap = {};
  collection.features.forEach((feature, index) => {
    next[getBoundaryFeatureKey(feature, index)] = feature;
  });
  return next;
}

function sortBoundaryFeatures(features: BoundaryFeature[]): BoundaryFeature[] {
  return [...features].sort((left, right) => {
    const rankA = String(left.properties.location_rank ?? "unknown");
    const rankB = String(right.properties.location_rank ?? "unknown");
    const priorityA = BOUNDARY_RENDER_RANK_PRIORITY[rankA] ?? 99;
    const priorityB = BOUNDARY_RENDER_RANK_PRIORITY[rankB] ?? 99;
    if (priorityA !== priorityB) {
      return priorityA - priorityB;
    }
    const idA = String(left.properties.location_id ?? "");
    const idB = String(right.properties.location_id ?? "");
    if (idA !== idB) {
      return idA.localeCompare(idB);
    }
    return String(left.properties.location_name ?? "").localeCompare(String(right.properties.location_name ?? ""));
  });
}

export default function App() {
  const runtimeWindow = globalThis as typeof globalThis & {
    __DOCMAP_TEST_HOOKS__?: {
      setViewport?: (viewport: MapViewport) => void;
      setPinnedLocationId?: (locationId: string | null) => void;
      setHighlightedLocationIds?: (locationIds: string[]) => void;
      clearHighlightedLocationIds?: () => void;
      setPrecisionMode?: (mode: PrecisionMode) => void;
      getBoundaryDebug?: () => Record<string, unknown>;
    };
    __DOCMAP_BOUNDARY_DEBUG__?: Record<string, unknown>;
  };
  const [status, setStatus] = useState<UiStatus>("loading");
  const [errorContext, setErrorContext] = useState<ErrorContext>("unknown");
  const [locations, setLocations] = useState<Location[]>([]);
  const [bakedManifest, setBakedManifest] = useState<BakedManifest | null>(null);
  const [sessionPrecisionMode, setSessionPrecisionMode] = useState<PrecisionMode | null>(null);
  const [explicitBoundaryFeatures, setExplicitBoundaryFeatures] = useState<BoundaryFeatureMap>({});
  const [boundariesStatus, setBoundariesStatus] = useState<BoundariesStatus>("loading");
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
  const [testHighlightedLocationIds, setTestHighlightedLocationIds] = useState<string[] | null>(null);

  const linksByDocumentIdRef = useRef<Record<string, DocumentLocation[]>>({});
  const locationDocumentsByLocationIdRef = useRef<Record<string, LocationDocumentsResponse>>({});
  const mapViewportRef = useRef<MapViewport | null>(null);
  const activeVisualizationDocumentIdRef = useRef<string | null>(null);
  const viewportRafRef = useRef<number | null>(null);
  const cardRefs = useRef<Record<string, HTMLElement | null>>({});
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const pdfModalRef = useRef<HTMLDivElement | null>(null);
  const startupTimestampRef = useRef<number>(performance.now());
  const firstMeaningfulRenderLoggedRef = useRef(false);
  const boundariesReadyLoggedRef = useRef(false);
  const explicitBoundaryRequestVersionRef = useRef(0);
  const explicitBoundaryCacheRef = useRef<Record<string, BoundaryFeatureMap>>({});
  const loadMoreRequestVersionRef = useRef(0);

  const selectedLocationId = pinnedLocationId ?? hoveredLocationId;
  const boundaryExplicitLocationId = pinnedLocationId;
  const searchActive = searchQuery.trim().length >= 3;
  const activeVisualizationDocumentId = pinnedDocumentId ?? hoveredDocumentId;

  const fetchLocationDocumentsCached = useCallback(
    async (locationId: string, signal?: AbortSignal): Promise<LocationDocumentsResponse> => {
      const cached = locationDocumentsByLocationIdRef.current[locationId];
      if (cached) {
        return cached;
      }

      const payload = await fetchLocationDocuments(locationId, {
        limit: LOCATION_DOCUMENTS_PAGE_SIZE,
        offset: 0,
      }, signal);
      locationDocumentsByLocationIdRef.current[locationId] = payload;
      return payload;
    },
    [],
  );

  const fetchDocumentLocationsCached = useCallback(
    async (documentId: string, signal?: AbortSignal): Promise<DocumentLocation[]> => {
      const cached = linksByDocumentIdRef.current[documentId];
      if (cached) {
        return cached;
      }

      const items = await fetchDocumentLocations(documentId, signal);
      const validItems = items.filter((item) => isFiniteCoordinate(item.latitude, item.longitude));
      linksByDocumentIdRef.current[documentId] = validItems;
      return validItems;
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
    const controller = new AbortController();
    startupTimestampRef.current = performance.now();
    boundariesReadyLoggedRef.current = false;
    setBoundariesStatus("loading");

    fetchLocations(controller.signal)
      .then((items) => {
        if (controller.signal.aborted) {
          return;
        }
        setLocations(items.filter((item) => isFiniteCoordinate(item.latitude, item.longitude)));
        setErrorContext("unknown");
        setStatus("ready");
        if (!firstMeaningfulRenderLoggedRef.current) {
          firstMeaningfulRenderLoggedRef.current = true;
          const elapsedMs = performance.now() - startupTimestampRef.current;
          console.info("presentation.performance.first_meaningful_render_ms", elapsedMs.toFixed(2));
        }
      })
      .catch(() => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorContext("startup");
        setStatus("error");
      });

    fetchBakedManifest(undefined, controller.signal)
      .then((manifest) => {
        if (controller.signal.aborted) return;
        setBakedManifest(manifest);
        if (manifest.mode) setSessionPrecisionMode(manifest.mode as PrecisionMode);
      })
      .catch(() => {
        if (!controller.signal.aborted) setBoundariesStatus("error");
      });

    return () => {
      controller.abort();
    };
  }, []);

  useEffect(() => {
    if (!sessionPrecisionMode || bakedManifest?.mode === sessionPrecisionMode) {
      return;
    }
    const controller = new AbortController();
    boundariesReadyLoggedRef.current = false;
    setBoundariesStatus("loading");
    fetchBakedManifest(sessionPrecisionMode, controller.signal)
      .then((manifest) => {
        if (controller.signal.aborted) {
          return;
        }
        setBakedManifest(manifest);
      })
      .catch(() => {
        if (controller.signal.aborted) {
          return;
        }
        setBoundariesStatus("error");
      });
    return () => {
      controller.abort();
    };
  }, [bakedManifest?.mode, sessionPrecisionMode]);

  useEffect(() => {
    loadMoreRequestVersionRef.current += 1;
    setIsLoadingMoreDocuments(false);
    if (!selectedLocationId || searchActive) {
      setLocationDocuments([]);
      setLocationDocumentsMeta(null);
      return;
    }
    const controller = new AbortController();
    fetchLocationDocumentsCached(selectedLocationId, controller.signal)
      .then((payload: LocationDocumentsResponse) => {
        if (controller.signal.aborted) {
          return;
        }
        setLocationDocuments(payload.items);
        setLocationDocumentsMeta(payload);
        setStatus("ready");
      })
      .catch(() => {
        if (controller.signal.aborted) {
          return;
        }
        setErrorContext("location_documents");
        setStatus("error");
      });
    return () => {
      controller.abort();
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
    const requestVersion = loadMoreRequestVersionRef.current + 1;
    loadMoreRequestVersionRef.current = requestVersion;
    fetchLocationDocuments(selectedLocationId, {
      limit: LOCATION_DOCUMENTS_PAGE_SIZE,
      offset: locationDocuments.length,
    })
      .then((payload) => {
        if (loadMoreRequestVersionRef.current !== requestVersion) return;
        setLocationDocuments((current) =>
          Array.from(new Map([...current, ...payload.items].map((item) => [item.document_id, item])).values()),
        );
        setLocationDocumentsMeta(payload);
      })
      .catch(() => {
        if (loadMoreRequestVersionRef.current !== requestVersion) return;
        setErrorContext("location_documents");
        setStatus("error");
      })
      .finally(() => {
        if (loadMoreRequestVersionRef.current === requestVersion) setIsLoadingMoreDocuments(false);
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
    const controller = new AbortController();
    const handle = window.setTimeout(() => {
      fetchSearch(searchQuery.trim(), 5, controller.signal)
        .then((payload) => {
          if (controller.signal.aborted) return;
          setSearchResults(payload);
          setStatus("ready");
        })
        .catch(() => {
          if (controller.signal.aborted) return;
          setErrorContext("search");
          setStatus("error");
        });
    }, 180);
    return () => {
      window.clearTimeout(handle);
      controller.abort();
    };
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

    const controller = new AbortController();
    const uniqueDocumentIds = Array.from(
      new Set(searchResults.documents.map((item) => item.document_id)),
    );

    Promise.all(uniqueDocumentIds.map((documentId) => fetchDocumentLocationsCached(documentId, controller.signal)))
      .then((allLinks) => {
        if (controller.signal.aborted) {
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
        if (controller.signal.aborted) {
          return;
        }
        setSearchDocumentCoordinates([]);
      });

    return () => {
      controller.abort();
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

    const controller = new AbortController();
    fetchDocumentLocationsCached(activeVisualizationDocumentId, controller.signal)
      .then(() => {
        if (controller.signal.aborted || activeVisualizationDocumentIdRef.current !== activeVisualizationDocumentId) {
          return;
        }
        updateVisibleLinksForActiveDocument(activeVisualizationDocumentId);
      })
      .catch(() => {
        if (controller.signal.aborted || activeVisualizationDocumentIdRef.current !== activeVisualizationDocumentId) {
          return;
        }
        setVisibleDocumentLinks([]);
        setOffscreenLinkCount(0);
      });

    return () => {
      controller.abort();
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

  useEffect(() => {
    if (!pdfModalDocumentId) {
      return;
    }

    const onPointerDown = (event: PointerEvent) => {
      const modal = pdfModalRef.current;
      if (!modal) {
        return;
      }
      const target = event.target;
      if (!(target instanceof Node) || modal.contains(target)) {
        return;
      }
      setPdfModalDocumentId(null);
    };

    window.addEventListener("pointerdown", onPointerDown, true);
    return () => window.removeEventListener("pointerdown", onPointerDown, true);
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

  const applyViewportChange = useCallback(
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

  const onViewportChange = useCallback(
    (viewport: MapViewport) => {
      applyViewportChange(viewport);
    },
    [applyViewportChange],
  );
  const onBakedStatusChange = useCallback(
    (nextStatus: "loading" | "ready" | "error") => {
      setBoundariesStatus(nextStatus);
      if (nextStatus === "ready" && !boundariesReadyLoggedRef.current) {
        boundariesReadyLoggedRef.current = true;
        const elapsedMs = performance.now() - startupTimestampRef.current;
        console.info("presentation.performance.boundaries_ready_ms", elapsedMs.toFixed(2));
      }
    },
    [],
  );
  const onPrecisionModeChange = useCallback(
    (event: ChangeEvent<HTMLSelectElement>) => {
      const nextMode = event.target.value as PrecisionMode;
      setSessionPrecisionMode(nextMode);
    },
    [],
  );

  const selectedLocation = useMemo(
    () => locations.find((item) => item.location_id === selectedLocationId) ?? null,
    [locations, selectedLocationId],
  );

  const highlightedLocationIds = useMemo(() => {
    if (testHighlightedLocationIds !== null) {
      return testHighlightedLocationIds;
    }
    return searchActive ? searchResults.locations.map((location) => location.location_id) : [];
  }, [searchActive, searchResults.locations, testHighlightedLocationIds]);

  const sortedHighlightedLocationIds = useMemo(
    () => Array.from(new Set(highlightedLocationIds)).sort(),
    [highlightedLocationIds],
  );

  const explicitBoundaryLocationIds = useMemo(() => {
    const ids = new Set<string>();
    if (boundaryExplicitLocationId) {
      ids.add(boundaryExplicitLocationId);
    }
    sortedHighlightedLocationIds.forEach((locationId) => ids.add(locationId));
    return Array.from(ids).sort();
  }, [boundaryExplicitLocationId, sortedHighlightedLocationIds]);

  const boundaries = useMemo<BoundaryCollection>(
    () => ({
      type: "FeatureCollection",
      features: sortBoundaryFeatures(Object.values(explicitBoundaryFeatures)),
    }),
    [explicitBoundaryFeatures],
  );

  useEffect(() => {
    if (explicitBoundaryLocationIds.length === 0) {
      setExplicitBoundaryFeatures({});
      return;
    }

    const requestKey = explicitBoundaryLocationIds.join(",");
    const cached = explicitBoundaryCacheRef.current[requestKey];
    if (cached) {
      setExplicitBoundaryFeatures(cached);
      return;
    }

    const requestVersion = explicitBoundaryRequestVersionRef.current + 1;
    explicitBoundaryRequestVersionRef.current = requestVersion;
    const controller = new AbortController();

    fetchBoundaries({
      selected_location_id: boundaryExplicitLocationId,
      highlighted_location_ids: sortedHighlightedLocationIds,
    }, controller.signal)
      .then((nextBoundaries) => {
        if (explicitBoundaryRequestVersionRef.current !== requestVersion) {
          return;
        }
        const nextFeatures = buildBoundaryFeatureMap(nextBoundaries);
        explicitBoundaryCacheRef.current[requestKey] = nextFeatures;
        setExplicitBoundaryFeatures(nextFeatures);
      })
      .catch(() => {
        if (controller.signal.aborted || explicitBoundaryRequestVersionRef.current !== requestVersion) {
          return;
        }
        console.warn("presentation.explicit_boundaries_unavailable");
      });
    return () => controller.abort();
  }, [boundaryExplicitLocationId, explicitBoundaryLocationIds, sortedHighlightedLocationIds]);

  useEffect(() => {
    runtimeWindow.__DOCMAP_BOUNDARY_DEBUG__ = {
      boundariesStatus,
      sessionPrecisionMode,
      defaultPrecisionMode: bakedManifest?.default_mode ?? null,
      bakedVersion: bakedManifest?.version ?? null,
      bakedArchiveUrl: bakedManifest?.archive_url ?? null,
      explicitBoundaryLocationIds,
      renderedBoundaryFeatureCount: boundaries.features.length,
    };
  }, [
    boundaries.features.length,
    boundariesStatus,
    bakedManifest?.default_mode,
    bakedManifest?.archive_url,
    bakedManifest?.version,
    explicitBoundaryLocationIds,
    runtimeWindow,
    sessionPrecisionMode,
  ]);

  useEffect(() => {
    runtimeWindow.__DOCMAP_TEST_HOOKS__ = {
      setViewport: (viewport) => {
        applyViewportChange(viewport);
      },
      setPinnedLocationId: (locationId) => {
        setPinnedLocationId(locationId);
        setHoveredLocationId(locationId);
      },
      setHighlightedLocationIds: (locationIds) => {
        setTestHighlightedLocationIds(Array.from(new Set(locationIds)).sort());
      },
      clearHighlightedLocationIds: () => {
        setTestHighlightedLocationIds([]);
      },
      setPrecisionMode: (mode) => {
        setSessionPrecisionMode(mode);
      },
      getBoundaryDebug: () => runtimeWindow.__DOCMAP_BOUNDARY_DEBUG__ ?? {},
    };
    return () => {
      delete runtimeWindow.__DOCMAP_TEST_HOOKS__;
      delete runtimeWindow.__DOCMAP_BOUNDARY_DEBUG__;
    };
  }, [applyViewportChange, runtimeWindow]);

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
              <label className="precision-control" htmlFor="precision-mode-select">
                Precision
                <select
                  id="precision-mode-select"
                  value={sessionPrecisionMode ?? bakedManifest?.mode ?? "balanced_precise"}
                  onChange={onPrecisionModeChange}
                >
                  {PRECISION_MODE_OPTIONS.map((option) => (
                    <option
                      key={option.value}
                      value={option.value}
                      disabled={Boolean(
                        bakedManifest?.available_modes.length &&
                          !bakedManifest.available_modes.includes(option.value),
                      )}
                    >
                      {option.label}
                    </option>
                  ))}
                </select>
              </label>
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
              <button
                type="button"
                title={`Precision: ${sessionPrecisionMode ?? bakedManifest?.mode ?? "balanced_precise"}`}
              >
                P
              </button>
            </div>
          )}
        </aside>

        <main className="map-panel">
          <Suspense fallback={<div className="map-loading">Loading map…</div>}>
          <MapView
            locations={locations}
            explicitBoundaries={boundaries}
            bakedArchiveUrl={toPmtilesUrl(bakedManifest?.archive_url)}
            bakedZoomMin={bakedManifest?.min_zoom ?? 0}
            bakedZoomMax={bakedManifest?.max_zoom ?? 8}
            selectedLocationId={selectedLocationId}
            highlightedLocationIds={highlightedLocationIds}
            onHoverLocation={onHoverLocation}
            onClickLocation={onClickLocation}
            onEmptyMapClick={onEmptyMapClick}
            onViewportChange={onViewportChange}
            onProjectorChange={onProjectorChange}
            onBakedStatusChange={onBakedStatusChange}
            focusCoordinates={searchFocusCoordinates}
          />
          </Suspense>

          <div className="map-legend" aria-label="Map legend">
            <h3>Legend</h3>
            <div className="legend-row"><span className="legend-dot city" /> City point</div>
            <div className="legend-row"><span className="legend-dot fallback" /> Boundary-unavailable point</div>
            <div className="legend-row"><span className="legend-polygon" /> Region/Country/Continent/Ocean polygon</div>
          </div>
        </main>

        <DocumentPanel
          searchInputRef={searchInputRef}
          searchQuery={searchQuery}
          onSearchQueryChange={setSearchQuery}
          activeMode={activeMode}
          selectedLocation={selectedLocation}
          searchActive={searchActive}
          searchResults={searchResults}
          panelTitle={panelTitle}
          locationDocumentsMeta={locationDocumentsMeta}
          status={status}
          errorContext={errorContext}
          boundariesStatus={boundariesStatus}
          documents={uniqueDisplayedDocuments}
          activeVisualizationDocumentId={activeVisualizationDocumentId}
          pinnedDocumentId={pinnedDocumentId}
          offscreenLinkCount={offscreenLinkCount}
          declutterLinks={declutterLinks}
          hiddenVisibleLinkCount={hiddenVisibleLinkCount}
          cardRefs={cardRefs}
          canLoadMore={canLoadMoreLocationDocuments}
          isLoadingMore={isLoadingMoreDocuments}
          onClickLocation={onClickLocation}
          onDeclutterChange={setDeclutterLinks}
          onHoverDocument={setHoveredDocumentId}
          onToggleDocument={(documentId) => {
            setPinnedDocumentId((current) => current === documentId ? null : documentId);
            setHoveredDocumentId(documentId);
            setPdfModalDocumentId((current) => current && current !== documentId ? null : current);
          }}
          onOpenPdf={(documentId) => {
            setPinnedDocumentId(documentId);
            setPdfModalDocumentId(documentId);
          }}
          onLoadMore={onLoadMoreLocationDocuments}
        />
      </div>

      {pdfModalDocumentId ? (
        <div
          className="pdf-modal-backdrop"
          style={{
            left: isLeftPanelCollapsed ? 50 : 240,
            right: 390,
          }}
        >
          <div ref={pdfModalRef} className="pdf-modal" role="dialog" aria-modal="true">
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
