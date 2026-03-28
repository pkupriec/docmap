import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";

import type { BoundaryCollection, Location, LocationRank, MapViewport, ScreenPoint } from "./types";

type FocusCoordinate = {
  latitude: number;
  longitude: number;
};
type CoordinatePair = [number, number];

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

function pointInRing(lon: number, lat: number, ring: number[][]): boolean {
  let inside = false;
  for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
    const xi = ring[i][0];
    const yi = ring[i][1];
    const xj = ring[j][0];
    const yj = ring[j][1];
    const intersects = yi > lat !== yj > lat && lon < ((xj - xi) * (lat - yi)) / (yj - yi || Number.EPSILON) + xi;
    if (intersects) {
      inside = !inside;
    }
  }
  return inside;
}

function pointInPolygonGeometry(
  lon: number,
  lat: number,
  geometry: PolygonRecord["geometry"],
): boolean {
  if (geometry.type === "Polygon") {
    const rings = geometry.coordinates as number[][][];
    if (rings.length === 0 || !pointInRing(lon, lat, rings[0])) {
      return false;
    }
    for (let i = 1; i < rings.length; i += 1) {
      if (pointInRing(lon, lat, rings[i])) {
        return false;
      }
    }
    return true;
  }

  const polygons = geometry.coordinates as number[][][][];
  for (const rings of polygons) {
    if (rings.length === 0 || !pointInRing(lon, lat, rings[0])) {
      continue;
    }
    let insideHole = false;
    for (let i = 1; i < rings.length; i += 1) {
      if (pointInRing(lon, lat, rings[i])) {
        insideHole = true;
        break;
      }
    }
    if (!insideHole) {
      return true;
    }
  }
  return false;
}

type PolygonRecord = {
  type: "Feature";
  properties: {
    location_id: string;
    location_rank: LocationRank;
  };
  geometry: {
    type: "Polygon" | "MultiPolygon";
    coordinates: number[][][] | number[][][][];
  };
};

type PointRecord = {
  locationId: string;
  rank: LocationRank;
  longitude: number;
  latitude: number;
  documentCount: number;
  missingBoundary: boolean;
};

type Props = {
  locations: Location[];
  boundaries: BoundaryCollection;
  selectedLocationId: string | null;
  highlightedLocationIds: string[];
  onHoverLocation: (locationId: string | null) => void;
  onClickLocation: (locationId: string) => void;
  onEmptyMapClick: () => void;
  onViewportChange: (viewport: MapViewport) => void;
  onProjectorChange: (projector: ((longitude: number, latitude: number) => ScreenPoint) | null) => void;
  focusCoordinates: FocusCoordinate[];
};

const INITIAL_VIEW_STATE = {
  longitude: 12,
  latitude: 34,
  zoom: 1.4,
};

const CITY_POLYGON_ZOOM_THRESHOLD = 3.2;
const ALWAYS_POLYGON_RANKS: ReadonlySet<LocationRank> = new Set([
  "admin_region",
  "region",
  "country",
  "continent",
  "ocean",
]);
const POLYGON_PICK_PRIORITY: Record<LocationRank, number> = {
  ocean: 0,
  continent: 1,
  country: 2,
  admin_region: 3,
  region: 3,
  city: 4,
  unknown: 2,
};
const CLICK_RANK_PRIORITY: Record<LocationRank, number> = {
  unknown: 0,
  ocean: 1,
  continent: 2,
  country: 3,
  admin_region: 4,
  region: 4,
  city: 5,
};

function normalizeLocationRank(location: Location): LocationRank {
  const rawRank = (location.location_rank ?? "").toLowerCase();
  if (rawRank === "region") {
    return "admin_region";
  }
  if (
    rawRank === "city" ||
    rawRank === "admin_region" ||
    rawRank === "country" ||
    rawRank === "continent" ||
    rawRank === "ocean" ||
    rawRank === "unknown"
  ) {
    return rawRank;
  }

  const precision = (location.precision ?? "").toLowerCase();
  if (precision.includes("country")) {
    return "country";
  }
  if (precision.includes("region") || precision.includes("state") || precision.includes("province")) {
    return "admin_region";
  }
  return "city";
}

function getViewport(map: maplibregl.Map): MapViewport {
  const bounds = map.getBounds();
  return {
    zoom: map.getZoom(),
    west: bounds.getWest(),
    east: bounds.getEast(),
    south: bounds.getSouth(),
    north: bounds.getNorth(),
  };
}

class ZoomLevelControl implements maplibregl.IControl {
  private map: maplibregl.Map | null = null;
  private container: HTMLDivElement | null = null;
  private label: HTMLButtonElement | null = null;

  private updateLabel = (): void => {
    if (!this.map || !this.label) {
      return;
    }
    this.label.textContent = `Zoom ${this.map.getZoom().toFixed(1)}`;
  };

  onAdd(map: maplibregl.Map): HTMLElement {
    this.map = map;
    const container = document.createElement("div");
    container.className = "maplibregl-ctrl maplibregl-ctrl-group";

    const label = document.createElement("button");
    label.type = "button";
    label.disabled = true;
    label.title = "Current zoom level";
    label.setAttribute("aria-label", "Current zoom level");
    label.style.width = "auto";
    label.style.minWidth = "84px";
    label.style.padding = "0 10px";
    label.style.font = "12px/29px sans-serif";
    label.style.color = "#111827";
    label.style.opacity = "1";
    label.style.cursor = "default";

    container.appendChild(label);
    this.container = container;
    this.label = label;
    this.updateLabel();
    map.on("zoom", this.updateLabel);
    return container;
  }

  onRemove(): void {
    if (this.map) {
      this.map.off("zoom", this.updateLabel);
    }
    this.container?.remove();
    this.map = null;
    this.container = null;
    this.label = null;
  }
}

export function MapView({
  locations,
  boundaries,
  selectedLocationId,
  highlightedLocationIds,
  onHoverLocation,
  onClickLocation,
  onEmptyMapClick,
  onViewportChange,
  onProjectorChange,
  focusCoordinates,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const lastDeckClickTsRef = useRef(0);
  const lastFocusKeyRef = useRef<string>("");
  const viewportFrameRef = useRef<number | null>(null);
  const pulseTimerRef = useRef<number | null>(null);
  const [cityPolygonMode, setCityPolygonMode] = useState(
    INITIAL_VIEW_STATE.zoom >= CITY_POLYGON_ZOOM_THRESHOLD,
  );
  const [pulsePhase, setPulsePhase] = useState(0);

  const { boundaryByLocationId, boundaryByRankedName } = useMemo(() => {
    const byLocationId = new Map<
      string,
      { geometryType: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] }
    >();
    const byRankedName = new Map<
      string,
      { geometryType: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] }
    >();
    const rankedNameKey = (rank: string, name: string): string => `${rank}:${name}`;

    for (const feature of boundaries.features) {
      if (feature.geometry.type !== "Polygon" && feature.geometry.type !== "MultiPolygon") {
        continue;
      }
      const geometry = {
        geometryType: feature.geometry.type as "Polygon" | "MultiPolygon",
        coordinates: feature.geometry.coordinates as number[][][] | number[][][][],
      };
      const rank = String(feature.properties.location_rank ?? "unknown").toLowerCase();
      const normalizedRank = rank === "region" ? "admin_region" : rank;
      const normalizedName = String(feature.properties.location_name ?? "").toLowerCase();
      const locationId = String(feature.properties.location_id ?? "").trim();

      if (locationId) {
        byLocationId.set(locationId, geometry);
      }
      if (normalizedName) {
        byRankedName.set(rankedNameKey(normalizedRank, normalizedName), geometry);
      }
    }

    return {
      boundaryByLocationId: byLocationId,
      boundaryByRankedName: byRankedName,
    };
  }, [boundaries]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) {
      return;
    }
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: "https://demotiles.maplibre.org/style.json",
      center: [INITIAL_VIEW_STATE.longitude, INITIAL_VIEW_STATE.latitude],
      zoom: INITIAL_VIEW_STATE.zoom,
      attributionControl: true,
    });
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new ZoomLevelControl(), "top-right");

    const overlay = new MapboxOverlay({ layers: [] });
    map.addControl(overlay);

    const emitViewport = (): void => {
      onViewportChange(getViewport(map));
    };

    const scheduleViewportChange = (): void => {
      if (viewportFrameRef.current !== null) {
        return;
      }
      viewportFrameRef.current = window.requestAnimationFrame(() => {
        viewportFrameRef.current = null;
        emitViewport();
      });
    };

    map.on("move", scheduleViewportChange);
    map.on("zoom", () => {
      const nextMode = map.getZoom() >= CITY_POLYGON_ZOOM_THRESHOLD;
      setCityPolygonMode((current) => (current === nextMode ? current : nextMode));
    });

    map.on("click", () => {
      if (Date.now() - lastDeckClickTsRef.current < 90) {
        return;
      }
      onEmptyMapClick();
    });

    map.on("load", () => {
      setCityPolygonMode(map.getZoom() >= CITY_POLYGON_ZOOM_THRESHOLD);
      emitViewport();
      onProjectorChange((longitude, latitude) => {
        if (!isFiniteCoordinate(latitude, longitude)) {
          return { x: 0, y: 0 };
        }
        let point: maplibregl.Point;
        try {
          point = map.project([longitude, latitude]);
        } catch {
          return { x: 0, y: 0 };
        }
        const rect = map.getContainer().getBoundingClientRect();
        return {
          x: rect.left + point.x,
          y: rect.top + point.y,
        };
      });
    });

    mapRef.current = map;
    overlayRef.current = overlay;

    return () => {
      if (viewportFrameRef.current !== null) {
        window.cancelAnimationFrame(viewportFrameRef.current);
        viewportFrameRef.current = null;
      }
      if (pulseTimerRef.current !== null) {
        window.clearInterval(pulseTimerRef.current);
        pulseTimerRef.current = null;
      }
      overlay.finalize();
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
      onProjectorChange(null);
    };
  }, [onEmptyMapClick, onProjectorChange, onViewportChange]);

  useEffect(() => {
    if (highlightedLocationIds.length === 0) {
      return;
    }
    setPulsePhase(0);
    if (pulseTimerRef.current !== null) {
      window.clearInterval(pulseTimerRef.current);
    }
    pulseTimerRef.current = window.setInterval(() => {
      setPulsePhase((phase) => (phase + 1) % 60);
    }, 50);

    const stopHandle = window.setTimeout(() => {
      if (pulseTimerRef.current !== null) {
        window.clearInterval(pulseTimerRef.current);
        pulseTimerRef.current = null;
      }
      setPulsePhase(0);
    }, 1400);

    return () => {
      window.clearTimeout(stopHandle);
    };
  }, [highlightedLocationIds]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || focusCoordinates.length === 0) {
      return;
    }
    const validCoordinates = focusCoordinates.filter((item) =>
      isFiniteCoordinate(item.latitude, item.longitude),
    );
    if (validCoordinates.length === 0) {
      return;
    }

    const unique = Array.from(
      new Map(
        validCoordinates.map((item) => [
          `${item.latitude.toFixed(6)}:${item.longitude.toFixed(6)}`,
          item,
        ]),
      ).values(),
    );
    const key = unique
      .map((item) => `${item.latitude.toFixed(4)}:${item.longitude.toFixed(4)}`)
      .sort()
      .join("|");

    if (key === lastFocusKeyRef.current) {
      return;
    }
    lastFocusKeyRef.current = key;

    if (unique.length === 1) {
      map.easeTo({
        center: [unique[0].longitude, unique[0].latitude],
        zoom: Math.max(map.getZoom(), 4.5),
        duration: 500,
      });
      return;
    }

    const bounds = unique.reduce(
      (acc, item) => {
        acc.extend([item.longitude, item.latitude]);
        return acc;
      },
      new maplibregl.LngLatBounds(
        [unique[0].longitude, unique[0].latitude],
        [unique[0].longitude, unique[0].latitude],
      ),
    );
    map.fitBounds(bounds, { padding: 80, duration: 500, maxZoom: 6.5 });
  }, [focusCoordinates]);

  const highlightedSet = useMemo(() => new Set(highlightedLocationIds), [highlightedLocationIds]);
  const locationMetaById = useMemo(() => {
    const map = new Map<string, { rank: LocationRank; documentCount: number }>();
    for (const location of locations) {
      map.set(location.location_id, {
        rank: normalizeLocationRank(location),
        documentCount: location.document_count,
      });
    }
    return map;
  }, [locations]);

  const pickPreferredLocationId = useCallback(
    (primaryLocationId: string, x: number | null | undefined, y: number | null | undefined): string => {
      const candidateIds = new Set<string>([primaryLocationId]);
      const overlay = overlayRef.current as unknown as {
        pickMultipleObjects?: (opts: { x: number; y: number; radius?: number; depth?: number }) => Array<{
          object?: unknown;
        }>;
      } | null;
      if (overlay?.pickMultipleObjects && typeof x === "number" && typeof y === "number") {
        const picks = overlay.pickMultipleObjects({
          x,
          y,
          radius: 20,
          depth: 64,
        });
        for (const pick of picks) {
          const object = pick.object as
            | { locationId?: string; properties?: { location_id?: string } }
            | undefined;
          const pickedId = object?.locationId ?? object?.properties?.location_id;
          if (pickedId) {
            candidateIds.add(pickedId);
          }
        }
      }

      let bestId = primaryLocationId;
      let bestScore = Number.NEGATIVE_INFINITY;
      for (const candidateId of candidateIds) {
        const meta = locationMetaById.get(candidateId);
        if (!meta) {
          continue;
        }
        const rankPriority = CLICK_RANK_PRIORITY[meta.rank] ?? 0;
        const hasDocuments = meta.documentCount > 0 ? 1 : 0;
        const score = hasDocuments * 10000 + rankPriority * 100 + Math.min(meta.documentCount, 99);
        if (score > bestScore) {
          bestScore = score;
          bestId = candidateId;
        }
      }
      return bestId;
    },
    [locationMetaById],
  );

  const { polygonRecords, pointRecords, highlightedPoints } = useMemo(() => {
    const nextPolygons: PolygonRecord[] = [];
    const nextPoints: PointRecord[] = [];
    const nextHighlights: Array<{ longitude: number; latitude: number; locationId: string }> = [];
    const rankedNameKey = (rank: string, name: string): string => `${rank}:${name}`;

    for (const location of locations) {
      const rank = normalizeLocationRank(location);
      const normalizedName = location.name.toLowerCase();
      const polygon =
        boundaryByLocationId.get(location.location_id) ??
        boundaryByRankedName.get(rankedNameKey(rank, normalizedName)) ??
        null;

      if (highlightedSet.has(location.location_id)) {
        nextHighlights.push({
          locationId: location.location_id,
          latitude: location.latitude,
          longitude: location.longitude,
        });
      }

      if (!polygon) {
        nextPoints.push({
          locationId: location.location_id,
          rank,
          latitude: location.latitude,
          longitude: location.longitude,
          documentCount: location.document_count,
          missingBoundary: true,
        });
        continue;
      }

      if (rank === "city") {
        if (!cityPolygonMode) {
          nextPoints.push({
            locationId: location.location_id,
            rank,
            latitude: location.latitude,
            longitude: location.longitude,
            documentCount: location.document_count,
            missingBoundary: false,
          });
        } else {
          nextPolygons.push({
            type: "Feature",
            properties: {
              location_id: location.location_id,
              location_rank: rank,
            },
            geometry: {
              type: polygon.geometryType,
              coordinates: polygon.coordinates,
            },
          });
        }
        continue;
      }

      if (ALWAYS_POLYGON_RANKS.has(rank)) {
        nextPolygons.push({
          type: "Feature",
          properties: {
            location_id: location.location_id,
            location_rank: rank,
          },
          geometry: {
            type: polygon.geometryType,
            coordinates: polygon.coordinates,
          },
        });
        continue;
      }

      nextPoints.push({
        locationId: location.location_id,
        rank,
        latitude: location.latitude,
        longitude: location.longitude,
        documentCount: location.document_count,
        missingBoundary: false,
      });
    }

    nextPolygons.sort((a, b) => {
      const rankA = a.properties.location_rank;
      const rankB = b.properties.location_rank;
      const priorityA = POLYGON_PICK_PRIORITY[rankA] ?? 0;
      const priorityB = POLYGON_PICK_PRIORITY[rankB] ?? 0;
      return priorityA - priorityB;
    });

    return {
      polygonRecords: nextPolygons,
      pointRecords: nextPoints,
      highlightedPoints: nextHighlights,
    };
  }, [boundaryByLocationId, boundaryByRankedName, cityPolygonMode, highlightedSet, locations]);

  const selectLocationForClick = useCallback(
    (
      primaryLocationId: string,
      x: number | null | undefined,
      y: number | null | undefined,
      coordinate: CoordinatePair | null | undefined,
    ): string => {
      const primaryMeta = locationMetaById.get(primaryLocationId);
      const primaryRankPriority = primaryMeta ? CLICK_RANK_PRIORITY[primaryMeta.rank] ?? 0 : 0;
      const preferredByPicks = pickPreferredLocationId(primaryLocationId, x, y);

      if (primaryRankPriority > CLICK_RANK_PRIORITY.continent || !coordinate) {
        return preferredByPicks;
      }

      const [lon, lat] = coordinate;
      if (!Number.isFinite(lon) || !Number.isFinite(lat)) {
        return preferredByPicks;
      }

      const polygonCandidates: string[] = [];
      for (const polygon of polygonRecords) {
        const locationId = polygon.properties.location_id;
        const meta = locationMetaById.get(locationId);
        if (!meta) {
          continue;
        }
        const rankPriority = CLICK_RANK_PRIORITY[meta.rank] ?? 0;
        if (rankPriority <= CLICK_RANK_PRIORITY.continent) {
          continue;
        }
        if (pointInPolygonGeometry(lon, lat, polygon.geometry)) {
          polygonCandidates.push(locationId);
        }
      }

      if (polygonCandidates.length === 0) {
        return preferredByPicks;
      }

      let bestId = preferredByPicks;
      let bestScore = Number.NEGATIVE_INFINITY;
      for (const candidateId of polygonCandidates) {
        const meta = locationMetaById.get(candidateId);
        if (!meta) {
          continue;
        }
        const rankPriority = CLICK_RANK_PRIORITY[meta.rank] ?? 0;
        const hasDocuments = meta.documentCount > 0 ? 1 : 0;
        const score = hasDocuments * 10000 + rankPriority * 100 + Math.min(meta.documentCount, 99);
        if (score > bestScore) {
          bestScore = score;
          bestId = candidateId;
        }
      }
      return bestId;
    },
    [locationMetaById, pickPreferredLocationId, polygonRecords],
  );

  useEffect(() => {
    const overlay = overlayRef.current;
    if (!mapRef.current || !overlay) {
      return;
    }

    const pulseFactor = 0.6 + Math.sin((pulsePhase / 60) * Math.PI * 2) * 0.4;

    const layers = [
      new GeoJsonLayer<PolygonRecord>({
        id: "locations-polygons",
        data: polygonRecords,
        pickable: true,
        stroked: true,
        filled: true,
        getFillColor: (feature) =>
          feature.properties.location_id === selectedLocationId
            ? [216, 70, 45, 170]
            : [44, 122, 192, 72],
        getLineColor: (feature) =>
          feature.properties.location_id === selectedLocationId
            ? [255, 255, 255, 245]
            : [44, 96, 140, 160],
        getLineWidth: (feature) => (feature.properties.location_id === selectedLocationId ? 3 : 1.5),
        lineWidthUnits: "pixels",
        updateTriggers: {
          getFillColor: [selectedLocationId],
          getLineColor: [selectedLocationId],
          getLineWidth: [selectedLocationId],
        },
        onHover: (info: PickingInfo<{ properties: { location_id: string } }>) => {
          const locationId = info.object ? info.object.properties.location_id : null;
          onHoverLocation(locationId);
        },
        onClick: (info: PickingInfo<{ properties: { location_id: string } }>) => {
          if (!info.object) {
            return;
          }
          lastDeckClickTsRef.current = Date.now();
          const coordinate = Array.isArray(info.coordinate)
            ? ([Number(info.coordinate[0]), Number(info.coordinate[1])] as CoordinatePair)
            : null;
          onClickLocation(
            selectLocationForClick(info.object.properties.location_id, info.x, info.y, coordinate),
          );
        },
      }),
      new ScatterplotLayer<PointRecord>({
        id: "locations-points",
        data: pointRecords,
        pickable: true,
        autoHighlight: true,
        radiusUnits: "pixels",
        radiusMinPixels: 3,
        radiusMaxPixels: 18,
        getPosition: (d) => [d.longitude, d.latitude],
        getRadius: (d) => Math.min(4 + d.documentCount * 0.42, 16),
        getLineColor: (d) =>
          d.locationId === selectedLocationId ? [255, 255, 255, 250] : [20, 32, 53, 120],
        lineWidthMinPixels: 1.5,
        stroked: true,
        getFillColor: (d) => {
          if (d.rank === "city") {
            return d.locationId === selectedLocationId ? [216, 70, 45, 245] : [28, 92, 205, 215];
          }
          if (d.missingBoundary) {
            return d.locationId === selectedLocationId ? [255, 40, 20, 255] : [230, 40, 30, 228];
          }
          return d.locationId === selectedLocationId ? [216, 70, 45, 245] : [44, 122, 192, 205];
        },
        updateTriggers: {
          getFillColor: [selectedLocationId],
          getLineColor: [selectedLocationId],
        },
        onHover: (info: PickingInfo<PointRecord>) => {
          const locationId = info.object ? info.object.locationId : null;
          onHoverLocation(locationId);
        },
        onClick: (info: PickingInfo<PointRecord>) => {
          if (!info.object) {
            return;
          }
          lastDeckClickTsRef.current = Date.now();
          const coordinate = Array.isArray(info.coordinate)
            ? ([Number(info.coordinate[0]), Number(info.coordinate[1])] as CoordinatePair)
            : null;
          onClickLocation(selectLocationForClick(info.object.locationId, info.x, info.y, coordinate));
        },
      }),
      new ScatterplotLayer<{ longitude: number; latitude: number; locationId: string }>({
        id: "highlight-points",
        data: highlightedPoints,
        pickable: false,
        radiusUnits: "pixels",
        stroked: true,
        filled: false,
        lineWidthUnits: "pixels",
        lineWidthMinPixels: 2,
        getPosition: (d) => [d.longitude, d.latitude],
        getRadius: 10 + pulseFactor * 8,
        getLineColor: [250, 210, 65, 220],
        visible: highlightedPoints.length > 0,
        updateTriggers: {
          getRadius: [pulseFactor],
        },
      }),
    ];

    overlay.setProps({ layers });
  }, [
    highlightedPoints,
    onClickLocation,
    onHoverLocation,
    pickPreferredLocationId,
    pointRecords,
    polygonRecords,
    selectLocationForClick,
    pulsePhase,
    selectedLocationId,
  ]);

  return <div className="map-canvas" ref={containerRef} />;
}

