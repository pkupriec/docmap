import { useEffect, useRef } from "react";
import maplibregl from "maplibre-gl";
import { MapboxOverlay } from "@deck.gl/mapbox";
import { LineLayer, ScatterplotLayer } from "@deck.gl/layers";
import type { PickingInfo } from "@deck.gl/core";

import type { DocumentLocation, Location } from "./types";

type Props = {
  locations: Location[];
  selectedLocationId: string | null;
  links: DocumentLocation[];
  onHoverLocation: (locationId: string | null) => void;
  onClickLocation: (locationId: string | null) => void;
};

const INITIAL_VIEW_STATE = {
  longitude: 12,
  latitude: 34,
  zoom: 1.4,
};

export function MapView({
  locations,
  selectedLocationId,
  links,
  onHoverLocation,
  onClickLocation,
}: Props) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const overlayRef = useRef<MapboxOverlay | null>(null);

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
    mapRef.current = map;
    overlayRef.current = overlay;

    return () => {
      overlay.finalize();
      map.remove();
      mapRef.current = null;
      overlayRef.current = null;
    };
  }, []);

  useEffect(() => {
    if (!overlayRef.current) {
      return;
    }
    const selected = locations.find((location) => location.location_id === selectedLocationId) ?? null;
    const layers = [
      new ScatterplotLayer<Location>({
        id: "locations",
        data: locations,
        pickable: true,
        autoHighlight: true,
        radiusUnits: "pixels",
        radiusMinPixels: 3,
        radiusMaxPixels: 18,
        getPosition: (d) => [d.longitude, d.latitude],
        getRadius: (d) => Math.min(4 + d.document_count * 0.45, 16),
        getFillColor: (d) => (d.location_id === selectedLocationId ? [220, 60, 40, 230] : [35, 85, 190, 220]),
        onHover: (info: PickingInfo<Location>) => {
          const locationId = info.object ? info.object.location_id : null;
          onHoverLocation(locationId);
        },
        onClick: (info: PickingInfo<Location>) => {
          if (!info.object) {
            onClickLocation(null);
            return;
          }
          onClickLocation(info.object.location_id);
        },
      }),
      new LineLayer<DocumentLocation>({
        id: "document-links",
        data: selected ? links.filter((link) => link.location_id !== selected.location_id) : [],
        pickable: false,
        getSourcePosition: () => [selected?.longitude ?? 0, selected?.latitude ?? 0],
        getTargetPosition: (d) => [d.longitude, d.latitude],
        getColor: [250, 150, 30, 210],
        getWidth: 2,
      }),
    ];
    overlayRef.current.setProps({ layers });
  }, [locations, selectedLocationId, links, onHoverLocation, onClickLocation]);

  return <div className="map-canvas" ref={containerRef} />;
}

