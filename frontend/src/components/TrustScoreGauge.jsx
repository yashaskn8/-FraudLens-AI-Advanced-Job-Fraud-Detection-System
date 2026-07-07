import { useEffect, useState, useId } from "react";

const VERDICTS = {
  SAFE:         { label: "Safe",         c1: "#22c55e", c2: "#4ade80" },
  SUSPICIOUS:   { label: "Suspicious",   c1: "#d97706", c2: "#fbbf24" },
  LIKELY_FRAUD: { label: "Likely Fraud", c1: "#ea580c", c2: "#fb923c" },
  FRAUD:        { label: "Fraud",        c1: "#dc2626", c2: "#f87171" },
};

export default function TrustScoreGauge({ score, verdict, effectiveSignals, totalSignals }) {
  const uid = useId().replace(/:/g, "");   // unique IDs prevent gradient collisions
  const [animated, setAnimated] = useState(0);

  useEffect(() => {
    const t = setTimeout(() => setAnimated(score), 250);
    return () => clearTimeout(t);
  }, [score]);

  const cfg  = VERDICTS[verdict] || VERDICTS.SUSPICIOUS;
  const R    = 66;
  const circ = 2 * Math.PI * R;
  const arc  = circ * 0.75;
  const offset = arc - (animated / 100) * arc;

  return (
    <div style={{ display:"flex", flexDirection:"column", alignItems:"center" }}>
      <div style={{ position:"relative", width:200, height:200 }}>
        <svg width="200" height="200" viewBox="0 0 200 200"
             style={{ overflow:"visible" }}>
          <defs>
            {/* Gradient uses unique ID to prevent collision when multiple gauges render */}
            <linearGradient id={`grad-${uid}`} x1="0%" y1="0%" x2="100%" y2="0%">
              <stop offset="0%"   stopColor={cfg.c1} />
              <stop offset="100%" stopColor={cfg.c2} />
            </linearGradient>
            <filter id={`glow-${uid}`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="4" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>

          {/* Background track */}
          <circle
            cx="100" cy="100" r={R}
            fill="none"
            stroke="rgba(255,255,255,0.05)"
            strokeWidth="10"
            strokeDasharray={`${arc} ${circ - arc}`}
            strokeDashoffset={circ * 0.125}
            strokeLinecap="round"
            transform="rotate(135 100 100)"
          />

          {/* Subtle inner glow ring */}
          <circle
            cx="100" cy="100" r={R}
            fill="none"
            stroke={cfg.c1}
            strokeOpacity="0.08"
            strokeWidth="18"
            strokeDasharray={`${arc} ${circ - arc}`}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform="rotate(135 100 100)"
            style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.34,1.56,0.64,1)" }}
          />

          {/* Main progress arc */}
          <circle
            cx="100" cy="100" r={R}
            fill="none"
            stroke={`url(#grad-${uid})`}
            strokeWidth="10"
            strokeDasharray={`${arc} ${circ - arc}`}
            strokeDashoffset={offset}
            strokeLinecap="round"
            transform="rotate(135 100 100)"
            filter={`url(#glow-${uid})`}
            style={{ transition: "stroke-dashoffset 1.2s cubic-bezier(0.34,1.56,0.64,1)" }}
          />

          {/* Tick marks at 0, 25, 50, 75, 100 */}
          {[0, 25, 50, 75, 100].map(pct => {
            const angle = (135 + (pct / 100) * 270) * (Math.PI / 180);
            const r1 = R + 8; const r2 = R + 14;
            return (
              <line key={pct}
                x1={100 + r1 * Math.cos(angle)} y1={100 + r1 * Math.sin(angle)}
                x2={100 + r2 * Math.cos(angle)} y2={100 + r2 * Math.sin(angle)}
                stroke="rgba(255,255,255,0.18)"
                strokeWidth="1.5"
                strokeLinecap="round"
              />
            );
          })}
        </svg>

        {/* Score number */}
        <div style={{
          position: "absolute", inset: 0,
          display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center",
        }}>
          <span style={{
            fontFamily: "var(--font-display)",
            fontWeight: 700,
            fontSize: "2.8rem",
            lineHeight: 1,
            letterSpacing: "-0.05em",
            background: `linear-gradient(135deg, ${cfg.c1}, ${cfg.c2})`,
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            transition: "all 1.2s cubic-bezier(0.34,1.56,0.64,1)",
          }}>
            {animated}
          </span>
          <span style={{
            fontSize: "var(--text-xs)",
            color: "var(--text-tertiary)",
            fontWeight: 500,
            marginTop: "3px",
            letterSpacing: "0.04em",
          }}>
            / 100
          </span>
        </div>
      </div>

      {/* Verdict badge */}
      <div style={{
        marginTop: "14px",
        padding: "5px 16px",
        background: `${cfg.c1}18`,
        border: `1px solid ${cfg.c1}35`,
        borderRadius: "var(--radius-full)",
        fontSize: "var(--text-xs)",
        fontWeight: 700,
        letterSpacing: "0.10em",
        textTransform: "uppercase",
        color: cfg.c1,
      }}>
        {cfg.label}
      </div>

      {/* Signal count */}
      {effectiveSignals !== undefined && (
        <div style={{
          marginTop: "10px",
          fontSize: "var(--text-xs)",
          color: "var(--text-disabled)",
          textAlign: "center",
          lineHeight: 1.4,
        }}>
          Computed from{" "}
          <span style={{ color: "var(--text-tertiary)", fontWeight: 600 }}>
            {effectiveSignals}
          </span>
          {" "}of {totalSignals || 3} signals
        </div>
      )}
    </div>
  );
}
