import { useEffect, useMemo, useRef, useState } from "react";
import DeckGL, { type DeckGLRef } from "@deck.gl/react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { LinearInterpolator, type PickingInfo, type MapViewState } from "@deck.gl/core";
import Map from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { CityData } from "../store";
import type { LandUse } from "../types";

const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json";

export type MapMode = "select" | "box" | "paint";

export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

interface Props {
  data: CityData;
  features?: GeoJSON.Feature[];
  landUses: LandUse[];
  use: Int16Array;
  version: number;
  selected: Set<number>;
  selVersion: number;
  preview?: Map<number, number>;
  view3d: boolean;
  mode: MapMode;
  initialViewState: MapViewState;
  onPick?: (i: number, additive: boolean) => void;
  onPaint?: (i: number) => void;
  onBox?: (idx: number[], additive: boolean) => void;
  suggestionOverlay?: { top: number[]; p: number[] } | null;
}

export default function CityMap(props: Props) {
  const { data, landUses, use, version, selected, selVersion, preview, view3d, mode } = props;
  const colors = useMemo(() => landUses.map((u) => hexToRgb(u.color)), [landUses]);
  const [box, setBox] = useState<null | { x0: number; y0: number; x1: number; y1: number; c0: number[] }>(null);
  const dragging = useRef(false);
  const deckRef = useRef<DeckGLRef>(null);
  useEffect(() => {
    (window as unknown as { __deck?: unknown }).__deck = deckRef.current?.deck;
  });
  const [viewState, setViewState] = useState<MapViewState>(props.initialViewState);
  useEffect(() => {
    setViewState((v) => ({
      ...v,
      pitch: view3d ? 55 : 0,
      transitionDuration: 600,
      transitionInterpolator: new LinearInterpolator(["pitch"]),
    }) as MapViewState);
  }, [view3d]);
  const features = props.features ?? data.features;
  const base = data.baseUse;

  const layer = new GeoJsonLayer({
    id: "parcels",
    data: features as unknown as GeoJSON.FeatureCollection["features"],
    pickable: true,
    stroked: true,
    filled: true,
    extruded: view3d,
    wireframe: false,
    lineWidthUnits: "pixels",
    autoHighlight: true,
    highlightColor: [255, 255, 255, 70],
    getFillColor: (f: GeoJSON.Feature) => {
      const i = (f.properties as { i: number }).i;
      const pv = preview?.get(i);
      if (pv !== undefined) {
        const c = colors[pv];
        return [c[0], c[1], c[2], 245];
      }
      const u = use[i];
      if (u < 0) return [90, 96, 110, 120];
      const c = colors[u];
      const changed = u !== base[i];
      if (props.suggestionOverlay) {
        const a = Math.round(60 + 195 * props.suggestionOverlay.p[i]);
        const t = colors[props.suggestionOverlay.top[i]];
        return [t[0], t[1], t[2], a];
      }
      return [c[0], c[1], c[2], changed ? 250 : preview ? 70 : 190];
    },
    getLineColor: (f: GeoJSON.Feature) => {
      const i = (f.properties as { i: number }).i;
      if (selected.has(i)) return [255, 255, 255, 255];
      if (preview?.has(i)) return [255, 255, 255, 220];
      if (use[i] !== base[i]) return [255, 240, 200, 230];
      return [10, 14, 24, 160];
    },
    getLineWidth: (f: GeoJSON.Feature) => {
      const i = (f.properties as { i: number }).i;
      if (selected.has(i)) return 2.5;
      if (preview?.has(i) || use[i] !== base[i]) return 1.4;
      return 0.35;
    },
    getElevation: (f: GeoJSON.Feature) => {
      const i = (f.properties as { i: number; h: number }).i;
      const h = (f.properties as { h: number }).h || 0;
      const u = preview?.get(i) ?? use[i];
      if (u >= 0 && !landUses[u].built) return 0.5;
      if (u !== base[i] && h < 3) return 20; // new building on a formerly unbuilt lot
      return Math.max(h, 1);
    },
    material: { ambient: 0.45, diffuse: 0.6, shininess: 24, specularColor: [60, 64, 70] },
    updateTriggers: {
      getFillColor: [version, preview, props.suggestionOverlay],
      getLineColor: [version, selVersion, preview],
      getLineWidth: [version, selVersion, preview],
      getElevation: [version, preview],
    },
    transitions: { getFillColor: 220, getElevation: 400 },
  });

  const pickIndex = (info: PickingInfo) =>
    info.object ? ((info.object as GeoJSON.Feature).properties as { i: number }).i : null;

  const onClick = (info: PickingInfo, ev: { srcEvent?: MouseEvent }) => {
    const i = pickIndex(info);
    if (i === null) {
      if (mode === "select") props.onPick?.(-1, false);
      return;
    }
    if (mode === "paint") props.onPaint?.(i);
    else props.onPick?.(i, !!(ev.srcEvent && (ev.srcEvent.shiftKey || ev.srcEvent.metaKey || ev.srcEvent.ctrlKey)));
  };

  const boxSelect = (b: NonNullable<typeof box>, endCoord: number[], additive: boolean) => {
    const [lo0, la0] = b.c0;
    const [lo1, la1] = endCoord;
    const minLo = Math.min(lo0, lo1), maxLo = Math.max(lo0, lo1);
    const minLa = Math.min(la0, la1), maxLa = Math.max(la0, la1);
    const out: number[] = [];
    for (const f of features) {
      const i = (f.properties as { i: number }).i;
      const x = data.lon[i], y = data.lat[i];
      if (x >= minLo && x <= maxLo && y >= minLa && y <= maxLa) out.push(i);
    }
    props.onBox?.(out, additive);
  };

  const controller = mode === "select" ? true : { dragPan: false, touchRotate: false, dragRotate: false };

  return (
    <div className="map-wrap">
      <DeckGL
        ref={deckRef}
        viewState={viewState}
        onViewStateChange={({ viewState: v }) => setViewState(v as MapViewState)}
        controller={controller}
        layers={[layer]}
        onClick={onClick as never}
        onDragStart={(info: PickingInfo) => {
          dragging.current = true;
          if (mode === "box" && info.coordinate)
            setBox({ x0: info.x, y0: info.y, x1: info.x, y1: info.y, c0: info.coordinate });
          if (mode === "paint") {
            const i = pickIndex(info);
            if (i !== null) props.onPaint?.(i);
          }
        }}
        onDrag={(info: PickingInfo) => {
          if (mode === "box" && box) setBox({ ...box, x1: info.x, y1: info.y });
          if (mode === "paint") {
            const i = pickIndex(info);
            if (i !== null) props.onPaint?.(i);
          }
        }}
        onDragEnd={(info: PickingInfo, ev: { srcEvent?: MouseEvent }) => {
          dragging.current = false;
          if (mode === "box" && box && info.coordinate) {
            boxSelect(box, info.coordinate, !!ev.srcEvent?.shiftKey);
            setBox(null);
          }
        }}
        getCursor={({ isHovering }) => (mode === "paint" ? "crosshair" : mode === "box" ? "crosshair" : isHovering ? "pointer" : "grab")}
        getTooltip={({ object }) => {
          if (!object || mode === "paint") return null;
          const i = ((object as GeoJSON.Feature).properties as { i: number }).i;
          const u = use[i];
          const label = u >= 0 ? landUses[u].label : "Unclassified";
          const was = base[i] !== u && base[i] >= 0 ? ` (was ${landUses[base[i]].label})` : "";
          return { text: `${label}${was}`, className: "deck-tooltip" };
        }}
      >
        <Map mapStyle={DARK_STYLE} attributionControl={true} reuseMaps interactive={false} />
      </DeckGL>
      {box && (
        <div
          className="box-select"
          style={{
            left: Math.min(box.x0, box.x1),
            top: Math.min(box.y0, box.y1),
            width: Math.abs(box.x1 - box.x0),
            height: Math.abs(box.y1 - box.y0),
          }}
        />
      )}
    </div>
  );
}
