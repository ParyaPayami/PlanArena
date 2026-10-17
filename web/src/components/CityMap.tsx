import { useEffect, useMemo, useRef, useState } from "react";
import DeckGL, { type DeckGLRef } from "@deck.gl/react";
import { GeoJsonLayer } from "@deck.gl/layers";
import { FlyToInterpolator, LinearInterpolator, type MapViewState, type PickingInfo } from "@deck.gl/core";
import Map from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import type { CityData, Highlight } from "../store";
import type { LandUse } from "../types";

const DARK_STYLE = "https://basemaps.cartocdn.com/gl/dark-matter-nolabels-gl-style/style.json";
const FLOOR_M = 3.5;
const ASSUMED_COVERAGE = 0.6; // lot coverage used only to draw buildings for proposed FAR

export type MapMode = "select" | "box" | "lasso" | "block" | "paint";

export function hexToRgb(hex: string): [number, number, number] {
  const h = hex.replace("#", "");
  return [parseInt(h.slice(0, 2), 16), parseInt(h.slice(2, 4), 16), parseInt(h.slice(4, 6), 16)];
}

function pointInPolygon(x: number, y: number, poly: number[][]) {
  let inside = false;
  for (let i = 0, j = poly.length - 1; i < poly.length; j = i++) {
    const [xi, yi] = poly[i];
    const [xj, yj] = poly[j];
    if (yi > y !== yj > y && x < ((xj - xi) * (y - yi)) / (yj - yi + 1e-12) + xi) inside = !inside;
  }
  return inside;
}

interface Props {
  data: CityData;
  features?: GeoJSON.Feature[];
  landUses: LandUse[];
  use: Int16Array;
  far?: Float32Array;
  version: number;
  selected: Set<number>;
  selVersion: number;
  preview?: Map<number, number>;
  highlight?: Highlight;
  focus?: { lon: number; lat: number; zoom: number; id: number };
  view3d: boolean;
  mode: MapMode;
  initialViewState: MapViewState;
  onPick?: (i: number, additive: boolean) => void;
  onPaint?: (i: number) => void;
  onBox?: (idx: number[], additive: boolean) => void;
  onBlock?: (i: number, additive: boolean) => void;
  suggestionOverlay?: { top: number[]; p: number[] } | null;
}

export default function CityMap(props: Props) {
  const { data, landUses, use, far, version, selected, selVersion, preview, view3d, mode, highlight } = props;
  const colors = useMemo(() => landUses.map((u) => hexToRgb(u.color)), [landUses]);
  const [box, setBox] = useState<null | { x0: number; y0: number; x1: number; y1: number; c0: number[] }>(null);
  const [lasso, setLasso] = useState<null | { screen: number[][]; geo: number[][] }>(null);
  // Refs mirror the drag state so a fast drag (start and end before a re-render) still selects.
  const boxRef = useRef<null | { x0: number; y0: number; x1: number; y1: number }>(null);
  const lassoRef = useRef<number[][]>([]);
  const deckRef = useRef<DeckGLRef>(null);
  const [viewState, setViewState] = useState<MapViewState>(props.initialViewState);
  const features = props.features ?? data.features;
  const base = data.baseUse;

  useEffect(() => {
    setViewState((v) => ({
      ...v,
      pitch: view3d ? 55 : 0,
      transitionDuration: 600,
      transitionInterpolator: new LinearInterpolator(["pitch"]),
    }) as MapViewState);
  }, [view3d]);

  useEffect(() => {
    if (!props.focus) return;
    setViewState((v) => ({
      ...v,
      longitude: props.focus!.lon,
      latitude: props.focus!.lat,
      zoom: props.focus!.zoom,
      transitionDuration: 900,
      transitionInterpolator: new FlyToInterpolator(),
    }) as MapViewState);
  }, [props.focus?.id]);

  // Selection outline: thin when zoomed out so the new colours of painted parcels stay visible.
  const selW = viewState.zoom >= 15 ? 2.5 : viewState.zoom >= 13.5 ? 1.6 : 0.9;
  const changedAt = (i: number) => use[i] !== base[i] || (far !== undefined && !Number.isNaN(far[i]));

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
      if (props.suggestionOverlay) {
        const a = Math.round(60 + 195 * props.suggestionOverlay.p[i]);
        const t = colors[props.suggestionOverlay.top[i]];
        return [t[0], t[1], t[2], a];
      }
      const u = use[i];
      if (u < 0) return [90, 96, 110, 120];
      const c = colors[u];
      return [c[0], c[1], c[2], changedAt(i) ? 250 : preview || highlight ? 80 : 190];
    },
    getLineColor: (f: GeoJSON.Feature) => {
      const i = (f.properties as { i: number }).i;
      if (selected.has(i)) return [255, 255, 255, 255];
      if (highlight?.parcels.has(i)) return [highlight.color[0], highlight.color[1], highlight.color[2], 255];
      if (preview?.has(i)) return [255, 255, 255, 220];
      if (changedAt(i)) return [255, 240, 200, 230];
      return [10, 14, 24, 160];
    },
    getLineWidth: (f: GeoJSON.Feature) => {
      const i = (f.properties as { i: number }).i;
      if (selected.has(i)) return selW;
      if (highlight?.parcels.has(i)) return 2.2;
      if (preview?.has(i) || changedAt(i)) return 1.4;
      return 0.35;
    },
    getElevation: (f: GeoJSON.Feature) => {
      const p = f.properties as { i: number; h: number };
      const i = p.i;
      const u = preview?.get(i) ?? use[i];
      if (u >= 0 && !landUses[u].built) return 0.5;
      if (far && !Number.isNaN(far[i]) && preview?.get(i) === undefined)
        return Math.max(1, (far[i] / ASSUMED_COVERAGE) * FLOOR_M);
      if (u !== base[i] && (p.h || 0) < 3) return 20; // new building on a formerly unbuilt lot
      return Math.max(p.h || 0, 1);
    },
    material: { ambient: 0.35, diffuse: 0.55, shininess: 18, specularColor: [40, 44, 50] },
    updateTriggers: {
      getFillColor: [version, preview, props.suggestionOverlay, highlight?.key],
      getLineColor: [version, selVersion, preview, highlight?.key],
      getLineWidth: [version, selVersion, preview, highlight?.key, selW],
      getElevation: [version, preview],
    },
    transitions: { getFillColor: 220, getElevation: 400 },
  });

  const pickIndex = (info: PickingInfo) =>
    info.object ? ((info.object as GeoJSON.Feature).properties as { i: number }).i : null;
  const additiveOf = (ev: { srcEvent?: MouseEvent }) =>
    !!(ev.srcEvent && (ev.srcEvent.shiftKey || ev.srcEvent.metaKey || ev.srcEvent.ctrlKey));

  const onClick = (info: PickingInfo, ev: { srcEvent?: MouseEvent }) => {
    const i = pickIndex(info);
    if (i === null) {
      if (mode === "select") props.onPick?.(-1, false);
      return;
    }
    if (mode === "paint") props.onPaint?.(i);
    else if (mode === "block") props.onBlock?.(i, additiveOf(ev));
    else props.onPick?.(i, additiveOf(ev));
  };

  const selectInBounds = (test: (x: number, y: number) => boolean, additive: boolean) => {
    const out: number[] = [];
    for (const f of features) {
      const i = (f.properties as { i: number }).i;
      if (test(data.lon[i], data.lat[i])) out.push(i);
    }
    props.onBox?.(out, additive);
  };

  const dragModes = mode === "box" || mode === "lasso" || mode === "paint";
  const controller = dragModes ? { dragPan: false, touchRotate: false, dragRotate: false } : true;

  return (
    <div className="map-wrap">
      <DeckGL
        ref={deckRef}
        viewState={viewState}
        onViewStateChange={({ viewState: v }) => setViewState(v as MapViewState)}
        controller={controller}
        layers={[layer]}
        onClick={onClick as never}
        onDragStart={(info: PickingInfo, ev: { deltaX?: number; deltaY?: number }) => {
          if (mode === "box" && info.coordinate) {
            // A drag is recognised a few pixels after the press; anchor the box at the press point.
            const sx = info.x - (ev?.deltaX ?? 0);
            const sy = info.y - (ev?.deltaY ?? 0);
            boxRef.current = { x0: sx, y0: sy, x1: info.x, y1: info.y };
            setBox({ x0: sx, y0: sy, x1: info.x, y1: info.y, c0: info.coordinate });
          }
          if (mode === "lasso" && info.coordinate) {
            lassoRef.current = [info.coordinate];
            setLasso({ screen: [[info.x, info.y]], geo: [info.coordinate] });
          }
          if (mode === "paint") {
            const i = pickIndex(info);
            if (i !== null) props.onPaint?.(i);
          }
        }}
        onDrag={(info: PickingInfo) => {
          if (mode === "box" && boxRef.current) {
            boxRef.current = { ...boxRef.current, x1: info.x, y1: info.y };
            if (box) setBox({ ...box, x1: info.x, y1: info.y });
          }
          if (mode === "lasso" && info.coordinate) {
            lassoRef.current = [...lassoRef.current, info.coordinate];
            if (lasso) setLasso({ screen: [...lasso.screen, [info.x, info.y]], geo: [...lasso.geo, info.coordinate] });
          }
          if (mode === "paint") {
            const i = pickIndex(info);
            if (i !== null) props.onPaint?.(i);
          }
        }}
        onDragEnd={(info: PickingInfo, ev: { srcEvent?: MouseEvent }) => {
          const start = boxRef.current;
          if (mode === "box" && start) {
            // Test in screen space: the map is rotated, so a screen rectangle is not a lon/lat rectangle.
            const vp = deckRef.current?.deck?.getViewports()[0];
            // The rectangle the user saw: from the drag start to the farthest of the last drag and end positions.
            const ex = Math.abs(info.x - start.x0) >= Math.abs(start.x1 - start.x0) ? info.x : start.x1;
            const ey = Math.abs(info.y - start.y0) >= Math.abs(start.y1 - start.y0) ? info.y : start.y1;
            const [x0, x1] = [Math.min(start.x0, ex), Math.max(start.x0, ex)];
            const [y0, y1] = [Math.min(start.y0, ey), Math.max(start.y0, ey)];
            if (vp && x1 - x0 > 2 && y1 - y0 > 2)
              selectInBounds((x, y) => {
                const [sx, sy] = vp.project([x, y]);
                return sx >= x0 && sx <= x1 && sy >= y0 && sy <= y1;
              }, additiveOf(ev));
            boxRef.current = null;
            setBox(null);
          }
          if (mode === "lasso") {
            const geo = info.coordinate ? [...lassoRef.current, info.coordinate] : lassoRef.current;
            if (geo.length > 2) selectInBounds((x, y) => pointInPolygon(x, y, geo), additiveOf(ev));
            lassoRef.current = [];
            setLasso(null);
          }
        }}
        getCursor={({ isHovering }) =>
          mode === "paint" || mode === "box" || mode === "lasso" ? "crosshair" : isHovering ? "pointer" : "grab"
        }
        getTooltip={({ object }) => {
          if (!object || mode === "paint") return null;
          const i = ((object as GeoJSON.Feature).properties as { i: number }).i;
          const u = use[i];
          const label = u >= 0 ? landUses[u].label : "Unclassified";
          const was = base[i] !== u && base[i] >= 0 ? ` (was ${landUses[base[i]].label})` : "";
          const f = far && !Number.isNaN(far[i]) ? ` · FAR ${far[i].toFixed(1)}` : "";
          return { text: `${label}${was}${f}`, className: "deck-tooltip" };
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
      {lasso && (
        <svg className="lasso-svg">
          <polyline points={lasso.screen.map((p) => p.join(",")).join(" ")} />
        </svg>
      )}
      {highlight && (
        <div className="map-legend">
          <span className="swatch" style={{ background: `rgb(${highlight.color.join(",")})` }} /> {highlight.label} (
          {highlight.parcels.size.toLocaleString()})
        </div>
      )}
    </div>
  );
}
