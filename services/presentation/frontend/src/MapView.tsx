import { useEffect, useMemo, useRef } from "react";
import maplibregl from "maplibre-gl";
import { Protocol } from "pmtiles";

import type { BoundaryCollection, Location, MapViewport, ScreenPoint } from "./types";

type FocusCoordinate = { latitude: number; longitude: number };
type BakedStatus = "loading" | "ready" | "error";

type Props = {
  locations: Location[];
  explicitBoundaries: BoundaryCollection;
  bakedArchiveUrl: string | null;
  bakedZoomMin: number;
  bakedZoomMax: number;
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

const INITIAL_VIEW = { longitude: 12, latitude: 34, zoom: 1.4 };
const BASE_STYLE: maplibregl.StyleSpecification = {
  version: 8,
  sources: {
    "openstreetmap-base": {
      type: "raster",
      tiles: ["https://tile.openstreetmap.org/{z}/{x}/{y}.png"],
      tileSize: 256,
      attribution: "© OpenStreetMap contributors",
    },
  },
  layers: [
    { id: "background", type: "background", paint: { "background-color": "#dce9ef" } },
    { id: "openstreetmap-base", type: "raster", source: "openstreetmap-base", paint: { "raster-opacity": 0.72 } },
  ],
};
const BAKED_SOURCE = "baked-boundaries";
const BAKED_LAYERS = {
  fill: "baked-boundaries-fill",
  line: "baked-boundaries-line",
  highlighted: "baked-boundaries-highlighted",
  selected: "baked-boundaries-selected",
} as const;
const EXPLICIT_SOURCE = "explicit-boundaries";
const EXPLICIT_LAYERS = { fill: "explicit-boundaries-fill", line: "explicit-boundaries-line" } as const;
const POINT_SOURCE = "location-points";
const POINT_LAYERS = {
  base: "location-points-base",
  highlighted: "location-points-highlighted",
  selected: "location-points-selected",
} as const;

const protocol = new Protocol();
maplibregl.addProtocol("pmtiles", protocol.tile);

function isFiniteCoordinate(latitude: number, longitude: number): boolean {
  return Number.isFinite(latitude) && Number.isFinite(longitude)
    && latitude >= -90 && latitude <= 90 && longitude >= -180 && longitude <= 180;
}

function getViewport(map: maplibregl.Map): MapViewport {
  const bounds = map.getBounds();
  return {
    zoom: map.getZoom(), west: bounds.getWest(), east: bounds.getEast(),
    south: bounds.getSouth(), north: bounds.getNorth(),
  };
}

function emptyFilter(): maplibregl.FilterSpecification {
  return ["==", ["get", "location_id"], "__none__"];
}

function idsFilter(ids: string[]): maplibregl.FilterSpecification {
  return ids.length > 0 ? ["in", ["get", "location_id"], ["literal", ids]] : emptyFilter();
}

function idFilter(id: string | null): maplibregl.FilterSpecification {
  return id ? ["==", ["get", "location_id"], id] : emptyFilter();
}

function removeBakedSource(map: maplibregl.Map): void {
  Object.values(BAKED_LAYERS).forEach((id) => {
    if (map.getLayer(id)) map.removeLayer(id);
  });
  if (map.getSource(BAKED_SOURCE)) map.removeSource(BAKED_SOURCE);
}

function addBakedSource(map: maplibregl.Map, archiveUrl: string, zoomMin: number, zoomMax: number): void {
  removeBakedSource(map);
  map.addSource(BAKED_SOURCE, { type: "vector", url: archiveUrl, minzoom: zoomMin, maxzoom: zoomMax });
  map.addLayer({
    id: BAKED_LAYERS.fill, type: "fill", source: BAKED_SOURCE, "source-layer": "boundaries",
    paint: { "fill-color": "#2c7ac0", "fill-opacity": 0.22 },
  });
  map.addLayer({
    id: BAKED_LAYERS.line, type: "line", source: BAKED_SOURCE, "source-layer": "boundaries",
    paint: { "line-color": "#2c608c", "line-width": 1.2, "line-opacity": 0.6 },
  });
  map.addLayer({
    id: BAKED_LAYERS.highlighted, type: "fill", source: BAKED_SOURCE, "source-layer": "boundaries",
    filter: emptyFilter(), paint: { "fill-color": "#f5bf2f", "fill-opacity": 0.4 },
  });
  map.addLayer({
    id: BAKED_LAYERS.selected, type: "fill", source: BAKED_SOURCE, "source-layer": "boundaries",
    filter: emptyFilter(), paint: { "fill-color": "#d8462d", "fill-opacity": 0.48 },
  });
}

function setGeoJsonSource(map: maplibregl.Map, id: string, data: GeoJSON.FeatureCollection): boolean {
  const source = map.getSource(id) as maplibregl.GeoJSONSource | undefined;
  if (source) {
    source.setData(data);
    return false;
  }
  map.addSource(id, { type: "geojson", data });
  return true;
}

function addExplicitLayers(map: maplibregl.Map): void {
  map.addLayer({
    id: EXPLICIT_LAYERS.fill, type: "fill", source: EXPLICIT_SOURCE,
    paint: { "fill-color": "#f7d354", "fill-opacity": 0.08 },
  });
  map.addLayer({
    id: EXPLICIT_LAYERS.line, type: "line", source: EXPLICIT_SOURCE,
    paint: { "line-color": "#ffffff", "line-width": 3, "line-opacity": 0.96 },
  });
}

function addPointLayers(map: maplibregl.Map): void {
  map.addLayer({
    id: POINT_LAYERS.base, type: "circle", source: POINT_SOURCE,
    paint: {
      "circle-radius": ["min", 16, ["+", 4, ["*", ["get", "document_count"], 0.42]]],
      "circle-color": ["case", ["==", ["get", "location_rank"], "city"], "#1c5ccd", "#609dd6"],
      "circle-opacity": 0.84, "circle-stroke-color": "rgba(20, 32, 53, 0.72)", "circle-stroke-width": 1.5,
    },
  });
  map.addLayer({
    id: POINT_LAYERS.highlighted, type: "circle", source: POINT_SOURCE, filter: emptyFilter(),
    paint: {
      "circle-radius": 14, "circle-opacity": 0, "circle-stroke-color": "#fad241",
      "circle-stroke-opacity": 0.9, "circle-stroke-width": 3,
    },
  });
  map.addLayer({
    id: POINT_LAYERS.selected, type: "circle", source: POINT_SOURCE, filter: emptyFilter(),
    paint: {
      "circle-radius": 9, "circle-color": "#d8462d", "circle-opacity": 0.96,
      "circle-stroke-color": "#ffffff", "circle-stroke-width": 2,
    },
  });
}

function makePointCollection(locations: Location[]): GeoJSON.FeatureCollection {
  return {
    type: "FeatureCollection",
    features: locations.filter((item) => isFiniteCoordinate(item.latitude, item.longitude)).map((item) => ({
      type: "Feature",
      properties: {
        location_id: item.location_id,
        location_rank: item.location_rank ?? "unknown",
        document_count: item.document_count,
      },
      geometry: { type: "Point", coordinates: [item.longitude, item.latitude] },
    })),
  };
}

class ZoomLevelControl implements maplibregl.IControl {
  private map: maplibregl.Map | null = null;
  private container: HTMLDivElement | null = null;
  private label: HTMLButtonElement | null = null;
  private update = (): void => {
    if (this.map && this.label) this.label.textContent = `Zoom ${this.map.getZoom().toFixed(1)}`;
  };

  onAdd(map: maplibregl.Map): HTMLElement {
    this.map = map;
    this.container = document.createElement("div");
    this.container.className = "maplibregl-ctrl maplibregl-ctrl-group";
    this.label = document.createElement("button");
    this.label.type = "button";
    this.label.disabled = true;
    this.label.title = "Current zoom level";
    this.label.setAttribute("aria-label", "Current zoom level");
    Object.assign(this.label.style, {
      width: "auto", minWidth: "84px", padding: "0 10px", font: "12px/29px sans-serif",
      color: "#111827", opacity: "1", cursor: "default",
    });
    this.container.appendChild(this.label);
    map.on("zoom", this.update);
    this.update();
    return this.container;
  }

  onRemove(): void {
    this.map?.off("zoom", this.update);
    this.container?.remove();
    this.map = null;
    this.container = null;
    this.label = null;
  }
}

export function MapView(props: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const propsRef = useRef(props);
  const viewportFrameRef = useRef<number | null>(null);
  const pulseTimerRef = useRef<number | null>(null);
  const hoveredIdRef = useRef<string | null>(null);
  const bakedGenerationRef = useRef(0);
  const lastFocusKeyRef = useRef("");
  const styleReadyRef = useRef(false);
  propsRef.current = props;

  const pointCollection = useMemo(() => makePointCollection(props.locations), [props.locations]);

  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;
    const map = new maplibregl.Map({
      container: containerRef.current,
      style: BASE_STYLE,
      center: [INITIAL_VIEW.longitude, INITIAL_VIEW.latitude], zoom: INITIAL_VIEW.zoom,
    });
    mapRef.current = map;
    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "top-right");
    map.addControl(new ZoomLevelControl(), "top-right");

    const syncSources = (): void => {
      const current = propsRef.current;
      if (setGeoJsonSource(map, EXPLICIT_SOURCE, current.explicitBoundaries as GeoJSON.FeatureCollection)) {
        addExplicitLayers(map);
      }
      if (setGeoJsonSource(map, POINT_SOURCE, makePointCollection(current.locations))) addPointLayers(map);
      map.setFilter(POINT_LAYERS.selected, idFilter(current.selectedLocationId));
      map.setFilter(POINT_LAYERS.highlighted, idsFilter(current.highlightedLocationIds));
      if (current.bakedArchiveUrl) {
        current.onBakedStatusChange("loading");
        addBakedSource(map, current.bakedArchiveUrl, current.bakedZoomMin, current.bakedZoomMax);
        map.setFilter(BAKED_LAYERS.selected, idFilter(current.selectedLocationId));
        map.setFilter(BAKED_LAYERS.highlighted, idsFilter(current.highlightedLocationIds));
      } else {
        removeBakedSource(map);
        current.onBakedStatusChange("error");
      }
    };
    const interactiveLayers = (): string[] => [
      EXPLICIT_LAYERS.fill, POINT_LAYERS.selected, POINT_LAYERS.base,
      BAKED_LAYERS.selected, BAKED_LAYERS.fill,
    ].filter((id) => Boolean(map.getLayer(id)));
    const pickedLocationId = (event: maplibregl.MapMouseEvent): string | null => {
      const layers = interactiveLayers();
      if (layers.length === 0) return null;
      const feature = map.queryRenderedFeatures(event.point, { layers })[0];
      const locationId = String(feature?.properties?.location_id ?? "").trim();
      return locationId || null;
    };
    const scheduleViewport = (): void => {
      if (viewportFrameRef.current !== null) return;
      viewportFrameRef.current = window.requestAnimationFrame(() => {
        viewportFrameRef.current = null;
        propsRef.current.onViewportChange(getViewport(map));
      });
    };
    const onMouseMove = (event: maplibregl.MapMouseEvent): void => {
      const locationId = pickedLocationId(event);
      if (locationId === hoveredIdRef.current) return;
      hoveredIdRef.current = locationId;
      map.getCanvas().style.cursor = locationId ? "pointer" : "";
      propsRef.current.onHoverLocation(locationId);
    };
    const onMouseOut = (): void => {
      hoveredIdRef.current = null;
      map.getCanvas().style.cursor = "";
      propsRef.current.onHoverLocation(null);
    };
    const onClick = (event: maplibregl.MapMouseEvent): void => {
      const locationId = pickedLocationId(event);
      if (locationId) propsRef.current.onClickLocation(locationId);
      else propsRef.current.onEmptyMapClick();
    };
    const onSourceData = (event: maplibregl.MapSourceDataEvent): void => {
      if (event.sourceId === BAKED_SOURCE && event.isSourceLoaded) propsRef.current.onBakedStatusChange("ready");
    };
    const onError = (event: { sourceId?: string }): void => {
      if (event.sourceId === BAKED_SOURCE) propsRef.current.onBakedStatusChange("error");
    };
    const onStyleLoad = (): void => {
      styleReadyRef.current = true;
      syncSources();
      propsRef.current.onViewportChange(getViewport(map));
      propsRef.current.onProjectorChange((longitude, latitude) => {
        if (!isFiniteCoordinate(latitude, longitude)) return { x: 0, y: 0 };
        const point = map.project([longitude, latitude]);
        const rect = map.getContainer().getBoundingClientRect();
        return { x: rect.left + point.x, y: rect.top + point.y };
      });
    };

    map.on("style.load", onStyleLoad);
    map.on("move", scheduleViewport);
    map.on("mousemove", onMouseMove);
    map.getCanvas().addEventListener("mouseout", onMouseOut);
    map.on("click", onClick);
    map.on("sourcedata", onSourceData);
    map.on("error", onError);

    return () => {
      if (viewportFrameRef.current !== null) window.cancelAnimationFrame(viewportFrameRef.current);
      if (pulseTimerRef.current !== null) window.clearInterval(pulseTimerRef.current);
      map.getCanvas().removeEventListener("mouseout", onMouseOut);
      map.remove();
      mapRef.current = null;
      styleReadyRef.current = false;
      propsRef.current.onProjectorChange(null);
    };
  }, []);

  useEffect(() => {
    const map = mapRef.current;
    if (map && styleReadyRef.current) setGeoJsonSource(map, POINT_SOURCE, pointCollection);
  }, [pointCollection]);

  useEffect(() => {
    const map = mapRef.current;
    if (map && styleReadyRef.current) {
      setGeoJsonSource(map, EXPLICIT_SOURCE, props.explicitBoundaries as GeoJSON.FeatureCollection);
    }
  }, [props.explicitBoundaries]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;
    const generation = bakedGenerationRef.current + 1;
    bakedGenerationRef.current = generation;
    props.onBakedStatusChange(props.bakedArchiveUrl ? "loading" : "error");
    const apply = (): void => {
      if (generation !== bakedGenerationRef.current || !styleReadyRef.current) return;
      if (!props.bakedArchiveUrl) {
        removeBakedSource(map);
        return;
      }
      addBakedSource(map, props.bakedArchiveUrl, props.bakedZoomMin, props.bakedZoomMax);
      map.setFilter(BAKED_LAYERS.selected, idFilter(props.selectedLocationId));
      map.setFilter(BAKED_LAYERS.highlighted, idsFilter(props.highlightedLocationIds));
    };
    if (styleReadyRef.current) apply();
    else map.once("style.load", apply);
    return () => {
      map.off("style.load", apply);
    };
  }, [props.bakedArchiveUrl, props.bakedZoomMax, props.bakedZoomMin]);

  useEffect(() => {
    const map = mapRef.current;
    if (!map || !styleReadyRef.current) return;
    if (map.getLayer(POINT_LAYERS.selected)) map.setFilter(POINT_LAYERS.selected, idFilter(props.selectedLocationId));
    if (map.getLayer(POINT_LAYERS.highlighted)) map.setFilter(POINT_LAYERS.highlighted, idsFilter(props.highlightedLocationIds));
    if (map.getLayer(BAKED_LAYERS.selected)) map.setFilter(BAKED_LAYERS.selected, idFilter(props.selectedLocationId));
    if (map.getLayer(BAKED_LAYERS.highlighted)) map.setFilter(BAKED_LAYERS.highlighted, idsFilter(props.highlightedLocationIds));
    if (pulseTimerRef.current !== null) window.clearInterval(pulseTimerRef.current);
    if (props.highlightedLocationIds.length === 0 || !map.getLayer(POINT_LAYERS.highlighted)) return;
    const started = performance.now();
    pulseTimerRef.current = window.setInterval(() => {
      if (!map.getLayer(POINT_LAYERS.highlighted)) return;
      const elapsed = performance.now() - started;
      map.setPaintProperty(POINT_LAYERS.highlighted, "circle-radius", 14 + Math.sin(elapsed / 130) * 4);
      if (elapsed > 1400 && pulseTimerRef.current !== null) {
        window.clearInterval(pulseTimerRef.current);
        pulseTimerRef.current = null;
      }
    }, 50);
  }, [props.highlightedLocationIds, props.selectedLocationId]);

  useEffect(() => {
    const map = mapRef.current;
    const valid = props.focusCoordinates.filter((item) => isFiniteCoordinate(item.latitude, item.longitude));
    if (!map || valid.length === 0) return;
    const unique = Array.from(new Map(valid.map((item) => [`${item.latitude.toFixed(6)}:${item.longitude.toFixed(6)}`, item])).values());
    const key = unique.map((item) => `${item.latitude.toFixed(4)}:${item.longitude.toFixed(4)}`).sort().join("|");
    if (key === lastFocusKeyRef.current) return;
    lastFocusKeyRef.current = key;
    if (unique.length === 1) {
      map.easeTo({ center: [unique[0].longitude, unique[0].latitude], zoom: Math.max(map.getZoom(), 4.5), duration: 500 });
      return;
    }
    const bounds = new maplibregl.LngLatBounds(
      [unique[0].longitude, unique[0].latitude], [unique[0].longitude, unique[0].latitude],
    );
    unique.slice(1).forEach((item) => bounds.extend([item.longitude, item.latitude]));
    map.fitBounds(bounds, { padding: 80, duration: 500, maxZoom: 6.5 });
  }, [props.focusCoordinates]);

  return <div className="map-canvas" ref={containerRef} />;
}
