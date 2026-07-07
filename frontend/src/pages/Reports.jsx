import { useState, useEffect } from "react";
import { Flag, ShieldAlert, ArrowRight, ExternalLink } from "lucide-react";
import { getHistory } from "../api/client";
import MagicCard from "../components/MagicCard";

const VERDICT_CFG = {
  SAFE:         { color: "var(--safe-500)",     bg: "var(--safe-bg)",     label: "Safe" },
  SUSPICIOUS:   { color: "var(--suspicious-500)",bg: "var(--suspicious-bg)",label: "Suspicious" },
  LIKELY_FRAUD: { color: "var(--fraud-500)",    bg: "var(--fraud-bg)",    label: "Likely Fraud" },
  FRAUD:        { color: "var(--critical-500)", bg: "var(--critical-bg)", label: "Fraud" },
};

export default function Reports() {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    getHistory()
      .then(data => setScans(data.scans || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div style={{
      minHeight: "100vh", paddingBottom: "100px",
      opacity: mounted ? 1 : 0, transition: "opacity 500ms ease"
    }}>
      
      {/* Hero Header */}
      <div style={{
        position: "relative", padding: "80px 24px 60px", marginBottom: "40px",
        overflow: "hidden", borderBottom: "1px solid var(--border-subtle)",
      }}>
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none", zIndex: 0,
          background: "radial-gradient(ellipse 70% 80% at 50% 0%, rgba(239, 68, 68, 0.08) 0%, transparent 70%)"
        }} />
        <div style={{
          position: "absolute", inset: 0, pointerEvents: "none", zIndex: 0,
          backgroundImage: "linear-gradient(rgba(255,255,255,0.02) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.02) 1px, transparent 1px)",
          backgroundSize: "40px 40px",
          maskImage: "radial-gradient(ellipse 60% 80% at 50% 0%, black 0%, transparent 80%)",
          WebkitMaskImage: "radial-gradient(ellipse 60% 80% at 50% 0%, black 0%, transparent 80%)",
        }} />
        <div style={{ maxWidth: "1000px", margin: "0 auto", position: "relative", zIndex: 1, textAlign: "center" }}>
          <div style={{
            display: "inline-flex", alignItems: "center", gap: "8px",
            background: "var(--critical-bg)", border: "1px solid var(--critical-border)",
            borderRadius: "var(--radius-full)", padding: "6px 16px", marginBottom: "24px",
          }}>
            <ShieldAlert size={14} color="var(--critical-400)" />
            <span style={{ fontSize: "var(--text-xs)", fontWeight: 600, color: "var(--critical-400)", letterSpacing: "0.08em", textTransform: "uppercase" }}>
              Community Fraud Log
            </span>
          </div>
          <h1 style={{
            fontFamily: "var(--font-display)", fontWeight: 700, fontSize: "clamp(2rem, 5vw, 3.5rem)",
            letterSpacing: "-0.04em", marginBottom: "16px", color: "var(--text-primary)"
          }}>
            Scan History & <span style={{ color: "var(--critical-400)" }}>Reports</span>
          </h1>
          <p style={{ fontSize: "var(--text-lg)", color: "var(--text-secondary)", maxWidth: "560px", margin: "0 auto", lineHeight: "var(--leading-relaxed)" }}>
            Review your past security audits and investigate previously flagged fraudulent job postings from the community.
          </p>
        </div>
      </div>

      <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "0 24px" }}>
        {loading ? (
          <div style={{ display: "flex", justifyContent: "center", padding: "80px 0" }}>
            <div style={{
              width: "36px", height: "36px", border: "2px solid var(--border-brand)",
              borderTopColor: "var(--brand-500)", borderRadius: "50%",
              animation: "spin 0.8s linear infinite"
            }} />
          </div>
        ) : scans.length > 0 ? (
          <div style={{
            display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(300px, 1fr))",
            gap: "24px"
          }}>
            {scans.map((scan, i) => {
              const cfg = VERDICT_CFG[scan.verdict] || VERDICT_CFG.SUSPICIOUS;
              return (
                <a key={scan.scan_id} href={`/results/${scan.scan_id}`} style={{textDecoration: "none", color: "inherit"}}>
                  <MagicCard style={{
                    display: "flex", flexDirection: "column",
                    background: "var(--surface-1)", border: "1px solid var(--border-default)",
                    borderRadius: "var(--radius-xl)", padding: "24px",
                    position: "relative", overflow: "hidden", height: "100%",
                    boxShadow: "var(--shadow-sm)", transition: "all 300ms var(--ease-out-expo)",
                    cursor: "pointer", animation: `fadeSlideDown 500ms ${i * 50}ms var(--ease-out-expo) both`
                  }}>
                    {/* Subtle top border gradient mapping to verdict */}
                    <div style={{ position: "absolute", top: 0, left: 0, right: 0, height: "3px", background: cfg.color }} />
                    
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: "20px" }}>
                      <div style={{
                        width: "48px", height: "48px", borderRadius: "50%",
                        display: "flex", alignItems: "center", justifyContent: "center",
                        border: `1px solid ${cfg.color}30`, background: cfg.bg,
                        fontFamily: "var(--font-mono)", fontWeight: 700, fontSize: "1.2rem",
                        color: cfg.color
                      }}>
                        {scan.trust_score}
                      </div>
                      <span style={{
                        display: "inline-block", padding: "4px 12px", borderRadius: "var(--radius-full)",
                        background: cfg.bg, border: `1px solid ${cfg.color}30`,
                        color: cfg.color, fontSize: "10px", fontWeight: 700, letterSpacing: "0.06em",
                        textTransform: "uppercase"
                      }}>
                        {cfg.label}
                      </span>
                    </div>

                    <div style={{ flex: 1, minHeight: 0 }}>
                      <h3 style={{
                        fontSize: "var(--text-base)", fontWeight: 600, color: "var(--text-primary)",
                        marginBottom: "6px", display: "-webkit-box", WebkitLineClamp: 2,
                        WebkitBoxOrient: "vertical", overflow: "hidden", lineHeight: 1.4
                      }}>
                        {scan.job_title || scan.url || "Untitled Analysis Target"}
                      </h3>
                      <div style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", marginBottom: "20px", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
                        {scan.company_name || "Unknown Company"}
                      </div>
                    </div>

                    <div style={{
                      display: "flex", alignItems: "center", justifyContent: "space-between",
                      paddingTop: "16px", borderTop: "1px solid var(--border-subtle)",
                      fontSize: "var(--text-xs)", color: "var(--text-tertiary)"
                    }}>
                      <span>{scan.scanned_at ? new Date(scan.scanned_at).toLocaleDateString() : ""}</span>
                      <div style={{ display: "flex", alignItems: "center", gap: "4px", color: "var(--text-secondary)", fontWeight: 500 }}>
                        View Report <ArrowRight size={12} />
                      </div>
                    </div>
                  </MagicCard>
                </a>
              );
            })}
          </div>
        ) : (
          <MagicCard style={{
            background: "var(--surface-1)", border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-2xl)", padding: "60px 24px", textAlign: "center"
          }}>
            <Flag size={32} color="var(--text-disabled)" style={{ margin: "0 auto 16px" }} />
            <h3 style={{ fontSize: "var(--text-lg)", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px" }}>
              No audits found
            </h3>
            <p style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", marginBottom: "24px" }}>
              Start scanning job descriptions to build your security history.
            </p>
            <a href="/" style={{
              display: "inline-flex", alignItems: "center", gap: "8px",
              background: "var(--text-primary)", color: "var(--surface-base)",
              padding: "10px 20px", borderRadius: "var(--radius-full)",
              fontSize: "var(--text-sm)", fontWeight: 600, textDecoration: "none",
              transition: "transform var(--duration-fast)",
              position: "relative", zIndex: 1
            }}>
              Open Scanner <ExternalLink size={14} />
            </a>
          </MagicCard>
        )}
      </div>
    </div>
  );
}
