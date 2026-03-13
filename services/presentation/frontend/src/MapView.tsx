import { useEffect, useMemo, useRef, useState } from "react";
import maplibregl from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";

import type { BoundaryCollection, Location, LocationRank, MapViewport, ScreenPoint } from "./types";

type FocusCoordinate = {
  latitude: number;
  longitude: number;
};

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

type PolygonRecord = {
  location: Location;
  geometryType: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
};

type PointRecord = {
  location: Location;
  longitude: number;
  latitude: number;
  missingBoundary: boolean;
};

type Props = {
  locations: Location[];
  boundaries: BoundaryCollection;
  selectedLocationId: string | null;
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
  const [zoomLevel, setZoomLevel] = useState(INITIAL_VIEW_STATE.zoom);

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

    map.on("move", () => {
      setZoomLevel(map.getZoom());
      onViewportChange(getViewport(map));
    });

    map.on("click", () => {
      if (Date.now() - lastDeckClickTsRef.current < 90) {
        return;
      }
      onEmptyMapClick();
    });

    map.on("load", () => {
      setZoomLevel(map.getZoom());
      onViewportChange(getViewport(map));
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
      overlay.finalize();
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
      onProjectorChange(null);
    };
  }, [onEmptyMapClick, onProjectorChange, onViewportChange]);

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

  useEffect(() => {
    const map = mapRef.current;
    const overlay = overlayRef.current;
    if (!map || !overlay) {
      return;
    }

    const polygonRecords: PolygonRecord[] = [];
    const pointRecords: PointRecord[] = [];
    const rankedNameKey = (rank: string, name: string): string => `${rank}:${name}`;

    for (const location of locations) {
      const rank = normalizeLocationRank(location);
      const normalizedName = location.name.toLowerCase();
      const polygon =
        boundaryByLocationId.get(location.location_id) ??
        boundaryByRankedName.get(rankedNameKey(rank, normalizedName)) ??
        null;

      if (!polygon) {
        pointRecords.push({
          location,
          latitude: location.latitude,
          longitude: location.longitude,
          missingBoundary: true,
        });
        continue;
      }

      if (rank === "city") {
        const shouldFallbackToPoint = zoomLevel < CITY_POLYGON_ZOOM_THRESHOLD;
        if (shouldFallbackToPoint) {
          pointRecords.push({
            location,
            latitude: location.latitude,
            longitude: location.longitude,
            missingBoundary: false,
          });
        } else {
          polygonRecords.push({
            location,
            geometryType: polygon.geometryType,
            coordinates: polygon.coordinates,
          });
        }
        continue;
      }

      if (ALWAYS_POLYGON_RANKS.has(rank)) {
        polygonRecords.push({
          location,
          geometryType: polygon.geometryType,
          coordinates: polygon.coordinates,
        });
        continue;
      }

      pointRecords.push({
        location,
        latitude: location.latitude,
        longitude: location.longitude,
        missingBoundary: false,
      });
    }

    const layers = [
      new GeoJsonLayer<PolygonRecord>({
        id: "locations-polygons",
        data: polygonRecords.map((record) => ({
          type: "Feature",
          properties: {
            location_id: record.location.location_id,
            selected: record.location.location_id === selectedLocationId,
          },
          geometry: {
            type: record.geometryType,
            coordinates: record.coordinates,
          },
        })),
        pickable: true,
        stroked: true,
        filled: true,
        getFillColor: (feature) =>
          feature.properties.selected ? [220, 60, 40, 120] : [44, 122, 192, 90],
        getLineColor: (feature) =>
          feature.properties.selected ? [220, 60, 40, 210] : [38, 88, 132, 200],
        getLineWidth: 2,
        lineWidthUnits: "pixels",
        onHover: (info: PickingInfo<{ properties: { location_id: string } }>) => {
          const locationId = info.object ? info.object.properties.location_id : null;
          onHoverLocation(locationId);
        },
        onClick: (info: PickingInfo<{ properties: { location_id: string } }>) => {
          if (!info.object) {
            return;
          }
          lastDeckClickTsRef.current = Date.now();
          onClickLocation(info.object.properties.location_id);
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
        getRadius: (d) => Math.min(4 + d.location.document_count * 0.45, 16),
        getFillColor: (d) => {
          const rank = normalizeLocationRank(d.location);
          if (rank === "city") {
            return d.location.location_id === selectedLocationId ? [220, 60, 40, 230] : [35, 85, 190, 220];
          }
          if (d.missingBoundary) {
            return d.location.location_id === selectedLocationId ? [255, 0, 0, 255] : [255, 0, 0, 225];
          }
          return d.location.location_id === selectedLocationId ? [220, 60, 40, 230] : [35, 85, 190, 220];
        },
        onHover: (info: PickingInfo<PointRecord>) => {
          const locationId = info.object ? info.object.location.location_id : null;
          onHoverLocation(locationId);
        },
        onClick: (info: PickingInfo<PointRecord>) => {
          if (!info.object) {
            return;
          }
          lastDeckClickTsRef.current = Date.now();
          onClickLocation(info.object.location.location_id);
        },
      }),
    ];

    overlay.setProps({ layers });
  }, [
    locations,
    selectedLocationId,
    onHoverLocation,
    onClickLocation,
    boundaryByLocationId,
    boundaryByRankedName,
    zoomLevel,
  ]);

  return <div className="map-canvas" ref={containerRef} />;
}
