import { useState, useEffect, useId } from "react";
import { BarChart3, Shield, AlertTriangle, CheckCircle, TrendingUp } from "lucide-react";
import useAnalytics from "../hooks/useAnalytics";
import MagicCard from "../components/MagicCard";

const card = {
  background: "var(--surface-1)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-2xl)",
  padding: "24px",
  boxShadow: "var(--shadow-md)",
  position: "relative",
  overflow: "hidden",
};

const VERDICT_CFG = {
  SAFE:         { color: "var(--safe-500)",     bg: "var(--safe-bg)" },
  SUSPICIOUS:   { color: "var(--suspicious-500)",bg: "var(--suspicious-bg)" },
  LIKELY_FRAUD: { color: "var(--fraud-500)",    bg: "var(--fraud-bg)" },
  FRAUD:        { color: "var(--critical-500)", bg: "var(--critical-bg)" },
};

function AnimatedRing({ percentage, label }) {
  const [animated, setAnimated] = useState(0);
  const uid = useId().replace(/:/g, "");

  useEffect(() => {
    const t = setTimeout(() => setAnimated(percentage), 250);
    return () => clearTimeout(t);
  }, [percentage]);

  const R = 54;
  const circ = 2 * Math.PI * R;
  const offset = circ - (animated / 100) * circ;

  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center" }}>
      <div style={{ position: "relative", width: 140, height: 140 }}>
        <svg width="140" height="140" viewBox="0 0 140 140" style={{ overflow: "visible", transform: "rotate(-90deg)" }}>
          <defs>
            <linearGradient id={`grad-${uid}`} x1="0%" y1="0%" x2="100%" y2="100%">
              <stop offset="0%" stopColor="var(--brand-400)" />
              <stop offset="100%" stopColor="var(--brand-600)" />
            </linearGradient>
            <filter id={`glow-${uid}`} x="-20%" y="-20%" width="140%" height="140%">
              <feGaussianBlur stdDeviation="3" result="blur" />
              <feMerge>
                <feMergeNode in="blur" />
                <feMergeNode in="SourceGraphic" />
              </feMerge>
            </filter>
          </defs>
          <circle cx="70" cy="70" r={R} fill="none" stroke="rgba(255,255,255,0.05)" strokeWidth="8" />
          <circle
            cx="70" cy="70" r={R} fill="none"
            stroke={`url(#grad-${uid})`}
            strokeWidth="8" strokeLinecap="round"
            strokeDasharray={circ} strokeDashoffset={offset}
            filter={`url(#glow-${uid})`}
            style={{ transition: "stroke-dashoffset 1.2s var(--ease-spring)" }}
          />
        </svg>
        <div style={{
          position: "absolute", inset: 0, display: "flex", flexDirection: "column",
          alignItems: "center", justifyContent: "center"
        }}>
          <span style={{
            fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "2rem",
            letterSpacing: "-0.04em", color: "var(--text-primary)"
          }}>
            {animated.toFixed(0)}%
          </span>
        </div>
      </div>
      <div style={{ marginTop: "16px", fontSize: "var(--text-sm)", color: "var(--text-secondary)", textAlign: "center", lineHeight: 1.4 }}>
        {label}
      </div>
    </div>
  );
}

export default function Dashboard() {
  const { data, loading } = useAnalytics();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
  }, []);

  if (loading) {
    return (
      <div style={{ minHeight: "100vh", display: "flex", alignItems: "center", justifyContent: "center" }}>
        <div style={{
          width: "36px", height: "36px", border: "2px solid var(--border-brand)",
          borderTopColor: "var(--brand-500)", borderRadius: "50%",
          animation: "spin 0.8s linear infinite"
        }} />
      </div>
    );
  }

  const stats = data || {
    total_scans: 0, fraud_detected: 0, safe_count: 0,
    average_trust_score: 0, detection_rate: 0, recent_scans: [],
    verdict_distribution: { SAFE: 0, SUSPICIOUS: 0, LIKELY_FRAUD: 0, FRAUD: 0 },
  };

  const STAT_CARDS = [
    { label: "Total Scans", value: stats.total_scans, icon: BarChart3, color: "var(--brand-400)", bg: "rgba(99,102,241,0.1)" },
    { label: "Fraud Detected", value: stats.fraud_detected, icon: AlertTriangle, color: "var(--critical-400)", bg: "var(--critical-bg)" },
    { label: "Safe Postings", value: stats.safe_count, icon: CheckCircle, color: "var(--safe-400)", bg: "var(--safe-bg)" },
    { label: "Avg Trust Score", value: Math.round(stats.average_trust_score), icon: TrendingUp, color: "var(--brand-400)", bg: "rgba(99,102,241,0.1)" },
  ];

  return (
    <div style={{
      minHeight: "100vh", paddingBottom: "80px",
      opacity: mounted ? 1 : 0, transition: "opacity 500ms ease"
    }}>
      
      {/* Heavy Graphic Header */}
      <div style={{
        position: "relative", padding: "80px 24px 60px", marginBottom: "32px",
        overflow: "hidden", borderBottom: "1px solid var(--border-subtle)",
      }}>
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none", zIndex: 0,
          background: "radial-gradient(ellipse 70% 80% at 50% 0%, rgba(99,102,241,0.08) 0%, transparent 70%)"
        }} />
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none", zIndex: 0,
          backgroundImage: "linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
          maskImage: "radial-gradient(ellipse 60% 80% at 50% 0%, black 0%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse 60% 80% at 50% 0%, black 0%, transparent 80%)",
        }} />
        <div style={{ maxWidth: "1100px", margin: "0 auto", position: "relative", zIndex: 1 }}>
          <h1 style={{
            fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "clamp(2rem, 5vw, 3rem)",
            letterSpacing: "-0.04em", marginBottom: "12px",
          }}>
            Platform <span style={{ color: "var(--brand-400)" }}>Analytics</span>
          </h1>
          <p style={{ fontSize: "var(--text-lg)", color: "var(--text-secondary)", maxWidth: "500px", lineHeight: "var(--leading-relaxed)" }}>
            High-level telemetry of the TrustHire detection engine across all inbound scans.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: "1100px", margin: "0 auto", padding: "0 24px" }}>
        
        {/* Metric Cards Top Row */}
        <div style={{
          display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(240px, 1fr))",
          gap: "20px", marginBottom: "20px"
        }}>
          {STAT_CARDS.map(({ label, value, icon: Icon, color, bg }, i) => (
            <MagicCard key={label} style={{
              ...card, padding: "24px",
              animation: `fadeSlideDown 600ms ${i * 75}ms var(--ease-out-expo) both`
            }}>
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "20px" }}>
                <span style={{ fontSize: "var(--text-sm)", fontWeight: 500, color: "var(--text-tertiary)" }}>{label}</span>
                <div style={{
                  width: "36px", height: "36px", borderRadius: "var(--radius-lg)",
                  background: bg, display: "flex", alignItems: "center", justifyContent: "center"
                }}>
                  <Icon size={16} color={color} />
                </div>
              </div>
              <div style={{
                fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "2.5rem",
                letterSpacing: "-0.04em", color: "var(--text-primary)", lineHeight: 1
              }}>
                {value}
              </div>
            </MagicCard>
          ))}
        </div>

        {/* Dense Analytics Row */}
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 340px", gap: "20px", marginBottom: "20px"
        }}>
          {/* Verdict Distribution */}
          <MagicCard style={{ ...card, animation: "fadeSlideDown 600ms 300ms var(--ease-out-expo) both" }}>
            <h2 style={{ fontSize: "var(--text-base)", fontWeight: 600, marginBottom: "28px" }}>Verdict Distribution</h2>
            <div style={{ display: "flex", flexDirection: "column", gap: "20px" }}>
              {Object.entries(stats.verdict_distribution || {}).map(([verdict, count]) => {
                const total = Math.max(stats.total_scans, 1);
                const pct = (count / total) * 100;
                const vCfg = VERDICT_CFG[verdict] || VERDICT_CFG.SUSPICIOUS;
                return (
                  <div key={verdict}>
                    <div style={{ display: "flex", justifyContent: "space-between", marginBottom: "8px", fontSize: "var(--text-sm)" }}>
                      <span style={{ color: "var(--text-secondary)", fontWeight: 500 }}>{verdict.replace("_", " ")}</span>
                      <span style={{ color: "var(--text-primary)", fontFamily: "var(--font-mono)" }}>{count} <span style={{ color: "var(--text-tertiary)" }}>({pct.toFixed(1)}%)</span></span>
                    </div>
                    <div style={{ height: "6px", background: "rgba(255,255,255,0.04)", borderRadius: "var(--radius-full)", overflow: "hidden" }}>
                      <div style={{
                        height: "100%", borderRadius: "var(--radius-full)", background: vCfg.color,
                        width: `${pct}%`, transition: "width 1s var(--ease-out-quart)",
                        boxShadow: `0 0 10px ${vCfg.color}40`
                      }} />
                    </div>
                  </div>
                );
              })}
            </div>
          </MagicCard>

          {/* Detection Ring */}
          <MagicCard style={{ ...card, display: "flex", alignItems: "center", justifyContent: "center", animation: "fadeSlideDown 600ms 400ms var(--ease-out-expo) both" }}>
            <AnimatedRing percentage={stats.detection_rate} label="of scanned jobs flagged as potential fraud" />
          </MagicCard>
        </div>

        {/* Recent Scans Table */}
        <MagicCard style={{ ...card, animation: "fadeSlideDown 600ms 500ms var(--ease-out-expo) both" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "24px" }}>
            <h2 style={{ fontSize: "var(--text-base)", fontWeight: 600 }}>Recent Activity</h2>
          </div>
          
          {stats.recent_scans?.length > 0 ? (
            <div style={{ margin: "0 -24px" }}>
              <div style={{
                display: "grid", gridTemplateColumns: "3fr 2fr 100px 140px 120px", gap: "16px",
                padding: "0 24px 12px", borderBottom: "1px solid var(--border-default)",
                fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--text-tertiary)",
                letterSpacing: "0.06em", textTransform: "uppercase"
              }}>
                <div>Job Title</div>
                <div>Company</div>
                <div style={{ textAlign: "center" }}>Score</div>
                <div style={{ textAlign: "center" }}>Verdict</div>
                <div style={{ textAlign: "right" }}>Date</div>
              </div>
              
              <div style={{ display: "flex", flexDirection: "column" }}>
                {stats.recent_scans.map((scan) => {
                  const vCfg = VERDICT_CFG[scan.verdict] || VERDICT_CFG.SUSPICIOUS;
                  return (
                    <a key={scan.scan_id} href={`/results/${scan.scan_id}`} style={{
                      display: "grid", gridTemplateColumns: "3fr 2fr 100px 140px 120px", gap: "16px",
                      padding: "16px 24px", borderBottom: "1px solid var(--border-subtle)",
                      alignItems: "center", textDecoration: "none", transition: "background var(--duration-fast)",
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = "var(--surface-2)"}
                    onMouseLeave={e => e.currentTarget.style.background = "transparent"}>
                      <div style={{ color: "var(--text-primary)", fontSize: "var(--text-sm)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", fontWeight: 500 }}>
                        {scan.job_title || "—"}
                      </div>
                      <div style={{ color: "var(--text-secondary)", fontSize: "var(--text-sm)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {scan.company_name || "—"}
                      </div>
                      <div style={{ color: vCfg.color, fontSize: "var(--text-sm)", fontFamily: "var(--font-mono)", fontWeight: 700, textAlign: "center" }}>
                        {scan.trust_score}
                      </div>
                      <div style={{ textAlign: "center" }}>
                        <span style={{
                          display: "inline-block", padding: "4px 12px", borderRadius: "var(--radius-full)",
                          background: vCfg.bg, border: `1px solid ${vCfg.color}30`,
                          color: vCfg.color, fontSize: "10px", fontWeight: 700, letterSpacing: "0.06em"
                        }}>
                          {scan.verdict}
                        </span>
                      </div>
                      <div style={{ color: "var(--text-tertiary)", fontSize: "var(--text-xs)", textAlign: "right" }}>
                        {scan.scanned_at ? new Date(scan.scanned_at).toLocaleDateString() : "—"}
                      </div>
                    </a>
                  );
                })}
              </div>
            </div>
          ) : (
            <div style={{ padding: "40px 0", textAlign: "center", color: "var(--text-tertiary)", fontSize: "var(--text-sm)" }}>
              No telemetry available yet.
            </div>
          )}
        </MagicCard>
      </div>
      <style>{`
        @media (max-width: 900px) {
          div[style*="grid-template-columns: 1fr 340px"] { grid-template-columns: 1fr !important; }
        }
      `}</style>
    </div>
  );
}
