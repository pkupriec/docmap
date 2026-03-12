import { useEffect, useMemo, useRef } from "react";
import maplibregl from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";

import boundariesRaw from "./assets/admin_boundaries.geojson?raw";
import type { Location, MapViewport, ScreenPoint } from "./types";

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

type BoundaryFeature = {
  properties: {
    location_name: string;
    location_rank?: string;
    country_name?: string;
    region_name?: string;
  };
  geometry: {
    type: string;
    coordinates: number[][][] | number[][][][];
  };
};

type BoundaryCollection = {
  features: BoundaryFeature[];
};

type PolygonRecord = {
  location: Location;
  geometryType: "Polygon" | "MultiPolygon";
  coordinates: number[][][] | number[][][][];
};

type PointRecord = {
  location: Location;
  longitude: number;
  latitude: number;
};

type Props = {
  locations: Location[];
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

const POLYGON_TO_POINT_ZOOM_THRESHOLD = 3.2;

function inferRank(location: Location): "country" | "region" | "city" {
  const precision = (location.precision ?? "").toLowerCase();
  if (precision.includes("country")) {
    return "country";
  }
  if (precision.includes("region") || precision.includes("state") || precision.includes("province")) {
    return "region";
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

export function MapView({
  locations,
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

  const boundaryCollection = useMemo(
    () => JSON.parse(boundariesRaw) as BoundaryCollection,
    [],
  );

  const boundaryByName = useMemo(() => {
    const next = new Map<string, { geometryType: "Polygon" | "MultiPolygon"; coordinates: number[][][] | number[][][][] }>();
    for (const feature of boundaryCollection.features) {
      const name = String(feature.properties.location_name).toLowerCase();
      if (feature.geometry.type === "Polygon" || feature.geometry.type === "MultiPolygon") {
        next.set(name, {
          geometryType: feature.geometry.type as "Polygon" | "MultiPolygon",
          coordinates: feature.geometry.coordinates as number[][][] | number[][][][],
        });
      }
    }
    return next;
  }, [boundaryCollection]);

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

    const overlay = new MapboxOverlay({ layers: [] });
    map.addControl(overlay);

    map.on("move", () => {
      onViewportChange(getViewport(map));
    });

    map.on("click", () => {
      if (Date.now() - lastDeckClickTsRef.current < 90) {
        return;
      }
      onEmptyMapClick();
    });

    map.on("load", () => {
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
      map.easeTo({ center: [unique[0].longitude, unique[0].latitude], zoom: Math.max(map.getZoom(), 4.5), duration: 500 });
      return;
    }

    const bounds = unique.reduce(
      (acc, item) => {
        acc.extend([item.longitude, item.latitude]);
        return acc;
      },
      new maplibregl.LngLatBounds([unique[0].longitude, unique[0].latitude], [unique[0].longitude, unique[0].latitude]),
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

    for (const location of locations) {
      const rank = inferRank(location);
      const polygon = rank === "city" ? null : boundaryByName.get(location.name.toLowerCase()) ?? null;
      if (!polygon) {
        pointRecords.push({
          location,
          latitude: location.latitude,
          longitude: location.longitude,
        });
        continue;
      }

      const shouldFallbackToPoint = map.getZoom() < POLYGON_TO_POINT_ZOOM_THRESHOLD;
      if (shouldFallbackToPoint) {
        pointRecords.push({
          location,
          latitude: location.latitude,
          longitude: location.longitude,
        });
      } else {
        polygonRecords.push({
          location,
          geometryType: polygon.geometryType,
          coordinates: polygon.coordinates,
        });
      }
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
        getFillColor: (d) =>
          d.location.location_id === selectedLocationId ? [220, 60, 40, 230] : [35, 85, 190, 220],
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
  }, [locations, selectedLocationId, onHoverLocation, onClickLocation, boundaryByName]);

  return <div className="map-canvas" ref={containerRef} />;
}
