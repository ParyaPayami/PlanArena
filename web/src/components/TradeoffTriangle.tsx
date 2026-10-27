import { useRef } from "react";
import { PILLAR_COLOR } from "../format";

export type PillarWeights = { social: number; economic: number; environmental: number };

const W = 220, H = 196, PAD = 18;
// Corners: social (top), economic (bottom left), environmental (bottom right)
const C = {
  social: [W / 2, PAD],
  economic: [PAD, H - PAD],
  environmental: [W - PAD, H - PAD],
} as const;

function toPoint(w: PillarWeights): [number, number] {
  const t = w.social + w.economic + w.environmental || 1;
  const a = w.social / t, b = w.economic / t, c = w.environmental / t;
  return [a * C.social[0] + b * C.economic[0] + c * C.environmental[0], a * C.social[1] + b * C.economic[1] + c * C.environmental[1]];
}

/** Barycentric weights of a point, clamped into the triangle. */
function toWeights(x: number, y: number): PillarWeights {
  const [x1, y1] = C.social, [x2, y2] = C.economic, [x3, y3] = C.environmental;
  const det = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3);
  let a = ((y2 - y3) * (x - x3) + (x3 - x2) * (y - y3)) / det;
  let b = ((y3 - y1) * (x - x3) + (x1 - x3) * (y - y3)) / det;
  a = Math.max(0, a); b = Math.max(0, b);
  let c = Math.max(0, 1 - a - b);
  const t = a + b + c || 1;
  [a, b, c] = [a / t, b / t, c / t];
  const r = (v: number) => Math.round(v * 20) / 20; // steps of 5%
  return { social: r(a), economic: r(b), environmental: r(c) };
}

interface Props {
  weights: PillarWeights;
  disabled?: boolean;
  /** while dragging (throttled by the caller) */
  onDrag: (w: PillarWeights) => void;
  /** on release */
  onRelease: (w: PillarWeights) => void;
}

/** Drag the handle to trade the three pillars off against each other; the optimal plan follows. */
export default function TradeoffTriangle({ weights, disabled, onDrag, onRelease }: Props) {
  const ref = useRef<SVGSVGElement>(null);
  const dragging = useRef(false);
  const last = useRef<PillarWeights>(weights);
  const at = (ev: React.PointerEvent) => {
    const r = ref.current!.getBoundingClientRect();
    return toWeights(((ev.clientX - r.left) / r.width) * W, ((ev.clientY - r.top) / r.height) * H);
  };
  const [px, py] = toPoint(weights);
  const pct = (v: number) => `${Math.round(100 * v)}%`;
  const tot = weights.social + weights.economic + weights.environmental || 1;
  return (
    <div className={`tradeoff ${disabled ? "disabled" : ""}`}>
      <svg
        ref={ref}
        viewBox={`0 0 ${W} ${H}`}
        role="slider"
        aria-label="Trade-off between the social, economic and environmental pillars"
        aria-valuetext={`social ${pct(weights.social / tot)}, economic ${pct(weights.economic / tot)}, environmental ${pct(weights.environmental / tot)}`}
        onPointerDown={(ev) => {
          if (disabled) return;
          dragging.current = true;
          (ev.target as Element).setPointerCapture?.(ev.pointerId);
          last.current = at(ev);
          onDrag(last.current);
        }}
        onPointerMove={(ev) => {
          if (!dragging.current) return;
          const w = at(ev);
          if (w.social !== last.current.social || w.economic !== last.current.economic) {
            last.current = w;
            onDrag(w);
          }
        }}
        onPointerUp={() => {
          if (!dragging.current) return;
          dragging.current = false;
          onRelease(last.current);
        }}
      >
        <polygon
          points={[C.social, C.economic, C.environmental].map((p) => p.join(",")).join(" ")}
          className="tri"
        />
        <circle cx={toPoint({ social: 1, economic: 1, environmental: 1 })[0]} cy={toPoint({ social: 1, economic: 1, environmental: 1 })[1]} r={2.5} className="tri-centre" />
        <text x={C.social[0]} y={C.social[1] - 5} textAnchor="middle" fill={PILLAR_COLOR.social} className="tri-label">Social {pct(weights.social / tot)}</text>
        <text x={C.economic[0]} y={C.economic[1] + 13} textAnchor="start" fill={PILLAR_COLOR.economic} className="tri-label">Economic {pct(weights.economic / tot)}</text>
        <text x={C.environmental[0]} y={C.environmental[1] + 13} textAnchor="end" fill={PILLAR_COLOR.environmental} className="tri-label">Environmental {pct(weights.environmental / tot)}</text>
        <circle cx={px} cy={py} r={9} className="tri-handle" />
      </svg>
    </div>
  );
}
