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

type BakedStatus = "waiting_viewport" | "loading" | "ready" | "error";

type PointRecord = {
  locationId: string;
  rank: LocationRank;
  longitude: number;
  latitude: number;
  documentCount: number;
};

type Props = {
  locations: Location[];
  explicitBoundaries: BoundaryCollection;
  bakedTileUrlTemplate: string | null;
  selectedLocationId: string | null;
  highlightedLocationIds: string[];
  onHoverLocation: (locationId: string | null) => void;
  onClickLocation: (locationId: string) => void;
  onEmptyMapClick: () => void;
  onViewportChange: (viewport: MapViewport) => void;
  onProjectorChange: (projector: ((longitude: number, latitude: number) => ScreenPoint) | null) => void;
  onBakedStatusChange: (status: BakedStatus) => void;
  focusCoordinates: FocusCoordinate[];
};

const INITIAL_VIEW_STATE = {
  longitude: 12,
  latitude: 34,
  zoom: 1.4,
};

const BAKED_SOURCE_ID = "baked-boundaries-source";
const BAKED_LAYER_FILL_ID = "baked-boundaries-fill";
const BAKED_LAYER_LINE_ID = "baked-boundaries-line";
const BAKED_LAYER_HIGHLIGHT_ID = "baked-boundaries-highlight";
const BAKED_LAYER_SELECTED_ID = "baked-boundaries-selected";

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

function normalizeLocationRank(location: Location): LocationRank {
  const rawRank = (location.location_rank ?? "").toLowerCase();
  const precision = (location.precision ?? "").toLowerCase();
  if (precision.includes("country")) {
    return "country";
  }
  if (precision.includes("region") || precision.includes("state") || precision.includes("province")) {
    return "admin_region";
  }
  if (precision.includes("city")) {
    return "city";
  }
  const adminLevelMatch = rawRank.match(/^admin_level_(\d+)$/);
  if (adminLevelMatch) {
    const adminLevel = Number(adminLevelMatch[1]);
    if (Number.isFinite(adminLevel)) {
      if (adminLevel <= 2) {
        return "country";
      }
      return "admin_region";
    }
  }
  if (rawRank === "region") {
    return "admin_region";
  }
  if (
    rawRank === "city" ||
    rawRank === "admin_region" ||
    rawRank === "country" ||
    rawRank === "continent" ||
    rawRank === "ocean" ||
    rawRank === "national_park" ||
    rawRank === "desert" ||
    rawRank === "unknown"
  ) {
    return rawRank;
  }
  return "unknown";
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

function _emptyFilter() {
  return ["==", ["get", "location_id"], "__none__"] as maplibregl.FilterSpecification;
}

function _inFilter(ids: string[]) {
  if (ids.length === 0) {
    return _emptyFilter();
  }
  return ["in", ["get", "location_id"], ["literal", ids]] as maplibregl.FilterSpecification;
}

function _selectedFilter(id: string | null) {
  if (!id) {
    return _emptyFilter();
  }
  return ["==", ["get", "location_id"], id] as maplibregl.FilterSpecification;
}

export function MapView({
  locations,
  explicitBoundaries,
  bakedTileUrlTemplate,
  selectedLocationId,
  highlightedLocationIds,
  onHoverLocation,
  onClickLocation,
  onEmptyMapClick,
  onViewportChange,
  onProjectorChange,
  onBakedStatusChange,
  focusCoordinates,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);
  const lastDeckClickTsRef = useRef(0);
  const lastBakedClickTsRef = useRef(0);
  const lastFocusKeyRef = useRef<string>("");
  const viewportFrameRef = useRef<number | null>(null);
  const pulseTimerRef = useRef<number | null>(null);
  const bakedSourceLoadedRef = useRef(false);
  const [pulsePhase, setPulsePhase] = useState(0);

  const pointRecords = useMemo<PointRecord[]>(
    () =>
      locations
        .filter((location) => isFiniteCoordinate(location.latitude, location.longitude))
        .map((location) => ({
          locationId: location.location_id,
          rank: normalizeLocationRank(location),
          latitude: location.latitude,
          longitude: location.longitude,
          documentCount: location.document_count,
        })),
    [locations],
  );

  const highlightedPoints = useMemo(
    () =>
      pointRecords
        .filter((item) => highlightedLocationIds.includes(item.locationId))
        .map((item) => ({
          longitude: item.longitude,
          latitude: item.latitude,
          locationId: item.locationId,
        })),
    [highlightedLocationIds, pointRecords],
  );

  const upsertBakedSource = useCallback((map: maplibregl.Map, template: string) => {
    if (map.getLayer(BAKED_LAYER_SELECTED_ID)) {
      map.removeLayer(BAKED_LAYER_SELECTED_ID);
    }
    if (map.getLayer(BAKED_LAYER_HIGHLIGHT_ID)) {
      map.removeLayer(BAKED_LAYER_HIGHLIGHT_ID);
    }
    if (map.getLayer(BAKED_LAYER_LINE_ID)) {
      map.removeLayer(BAKED_LAYER_LINE_ID);
    }
    if (map.getLayer(BAKED_LAYER_FILL_ID)) {
      map.removeLayer(BAKED_LAYER_FILL_ID);
    }
    if (map.getSource(BAKED_SOURCE_ID)) {
      map.removeSource(BAKED_SOURCE_ID);
    }

    map.addSource(BAKED_SOURCE_ID, {
      type: "vector",
      tiles: [template],
      minzoom: 0,
      maxzoom: 8,
    });
    map.addLayer({
      id: BAKED_LAYER_FILL_ID,
      type: "fill",
      source: BAKED_SOURCE_ID,
      "source-layer": "boundaries",
      paint: {
        "fill-color": "#2c7ac0",
        "fill-opacity": 0.22,
      },
    });
    map.addLayer({
      id: BAKED_LAYER_LINE_ID,
      type: "line",
      source: BAKED_SOURCE_ID,
      "source-layer": "boundaries",
      paint: {
        "line-color": "#2c608c",
        "line-width": 1.2,
        "line-opacity": 0.6,
      },
    });
    map.addLayer({
      id: BAKED_LAYER_HIGHLIGHT_ID,
      type: "fill",
      source: BAKED_SOURCE_ID,
      "source-layer": "boundaries",
      filter: _emptyFilter(),
      paint: {
        "fill-color": "#f5bf2f",
        "fill-opacity": 0.4,
      },
    });
    map.addLayer({
      id: BAKED_LAYER_SELECTED_ID,
      type: "fill",
      source: BAKED_SOURCE_ID,
      "source-layer": "boundaries",
      filter: _emptyFilter(),
      paint: {
        "fill-color": "#d8462d",
        "fill-opacity": 0.48,
      },
    });
  }, []);

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
    map.on("click", () => {
      const now = Date.now();
      if (now - lastDeckClickTsRef.current < 90 || now - lastBakedClickTsRef.current < 90) {
        return;
      }
      onEmptyMapClick();
    });

    map.on("load", () => {
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
    const map = mapRef.current;
    if (!map || !map.isStyleLoaded()) {
      return;
    }
    if (!bakedTileUrlTemplate) {
      onBakedStatusChange("error");
      return;
    }

    bakedSourceLoadedRef.current = false;
    onBakedStatusChange("loading");
    upsertBakedSource(map, bakedTileUrlTemplate);

    const onSourceData = (event: maplibregl.MapSourceDataEvent): void => {
      if (event.sourceId !== BAKED_SOURCE_ID || !event.isSourceLoaded || bakedSourceLoadedRef.current) {
        return;
      }
      bakedSourceLoadedRef.current = true;
      onBakedStatusChange("ready");
    };
    const onMouseMove = (event: maplibregl.MapMouseEvent & maplibregl.EventData): void => {
      const feature = event.features?.[0] as { properties?: Record<string, unknown> } | undefined;
      const locationId = String(feature?.properties?.location_id ?? "").trim();
      onHoverLocation(locationId || null);
    };
    const onMouseLeave = (): void => {
      onHoverLocation(null);
    };
    const onClick = (event: maplibregl.MapMouseEvent & maplibregl.EventData): void => {
      const feature = event.features?.[0] as { properties?: Record<string, unknown> } | undefined;
      const locationId = String(feature?.properties?.location_id ?? "").trim();
      if (!locationId) {
        return;
      }
      lastBakedClickTsRef.current = Date.now();
      onClickLocation(locationId);
    };

    map.on("sourcedata", onSourceData);
    map.on("mousemove", BAKED_LAYER_FILL_ID, onMouseMove);
    map.on("mouseleave", BAKED_LAYER_FILL_ID, onMouseLeave);
    map.on("click", BAKED_LAYER_FILL_ID, onClick);
    return () => {
      map.off("sourcedata", onSourceData);
      if (map.getLayer(BAKED_LAYER_FILL_ID)) {
        map.off("mousemove", BAKED_LAYER_FILL_ID, onMouseMove);
        map.off("mouseleave", BAKED_LAYER_FILL_ID, onMouseLeave);
        map.off("click", BAKED_LAYER_FILL_ID, onClick);
      }
    };
  }, [bakedTileUrlTemplate, onBakedStatusChange, onClickLocation, onHoverLocation, upsertBakedSource]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !map.getLayer(BAKED_LAYER_SELECTED_ID) || !map.getLayer(BAKED_LAYER_HIGHLIGHT_ID)) {
      return;
    }
    map.setFilter(BAKED_LAYER_SELECTED_ID, _selectedFilter(selectedLocationId));
    map.setFilter(BAKED_LAYER_HIGHLIGHT_ID, _inFilter(highlightedLocationIds));
  }, [highlightedLocationIds, selectedLocationId]);

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
    const validCoordinates = focusCoordinates.filter((item) => isFiniteCoordinate(item.latitude, item.longitude));
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

  useEffect(() => {
    const overlay = overlayRef.current;
    if (!overlay) {
      return;
    }
    const pulseFactor = 0.6 + Math.sin((pulsePhase / 60) * Math.PI * 2) * 0.4;
    const layers = [
      new GeoJsonLayer({
        id: "explicit-live-boundaries",
        data: explicitBoundaries.features,
        pickable: true,
        filled: false,
        stroked: true,
        lineWidthUnits: "pixels",
        getLineWidth: 3,
        getLineColor: [255, 255, 255, 245],
        visible: explicitBoundaries.features.length > 0,
        onHover: (info: PickingInfo<{ properties?: { location_id?: string } }>) => {
          const locationId = String(info.object?.properties?.location_id ?? "").trim();
          onHoverLocation(locationId || null);
        },
        onClick: (info: PickingInfo<{ properties?: { location_id?: string } }>) => {
          const locationId = String(info.object?.properties?.location_id ?? "").trim();
          if (!locationId) {
            return;
          }
          lastDeckClickTsRef.current = Date.now();
          onClickLocation(locationId);
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
        getFillColor: (d) =>
          d.locationId === selectedLocationId
            ? [216, 70, 45, 245]
            : d.rank === "city"
              ? [28, 92, 205, 215]
              : [96, 157, 214, 205],
        updateTriggers: {
          getFillColor: [selectedLocationId],
          getLineColor: [selectedLocationId],
        },
        onHover: (info: PickingInfo<PointRecord>) => {
          onHoverLocation(info.object?.locationId ?? null);
        },
        onClick: (info: PickingInfo<PointRecord>) => {
          if (!info.object) {
            return;
          }
          lastDeckClickTsRef.current = Date.now();
          onClickLocation(info.object.locationId);
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
    explicitBoundaries.features,
    highlightedPoints,
    onClickLocation,
    onHoverLocation,
    pointRecords,
    pulsePhase,
    selectedLocationId,
  ]);

  return <div className="map-canvas" ref={containerRef} />;
}
