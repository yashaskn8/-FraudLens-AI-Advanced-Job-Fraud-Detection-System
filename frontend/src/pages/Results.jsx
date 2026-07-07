import { useLocation, useParams, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { ArrowLeft, Share2, Flag, CheckCircle,
         AlertTriangle, XCircle, Info, ExternalLink, Terminal } from "lucide-react";
import TrustScoreGauge from "../components/TrustScoreGauge";
import SignalBreakdown from "../components/SignalBreakdown";
import RedFlagsList from "../components/RedFlagsList";
import ExplainerPanel from "../components/ExplainerPanel";
import NotJobContentResult from "../components/NotJobContentResult";
import { getScan, reportJob } from "../api/client";

const VERDICT_CFG = {
  SAFE:         { color: "var(--safe-500)",     bg: "var(--safe-bg)",     border: "var(--safe-border)",     icon: CheckCircle,   label: "Analysis Complete — Safe" },
  SUSPICIOUS:   { color: "var(--suspicious-500)",bg:"var(--suspicious-bg)",border:"var(--suspicious-border)",icon: Info,          label: "Analysis Complete — Suspicious" },
  LIKELY_FRAUD: { color: "var(--fraud-500)",    bg: "var(--fraud-bg)",    border: "var(--fraud-border)",    icon: AlertTriangle, label: "Fraud Indicators Detected" },
  FRAUD:        { color: "var(--critical-500)", bg: "var(--critical-bg)", border: "var(--critical-border)", icon: XCircle,       label: "High Fraud Risk Detected" },
};

const card = {
  background: "var(--surface-1)",
  border: "1px solid var(--border-default)",
  borderRadius: "var(--radius-2xl)",
  padding: "28px",
  boxShadow: "var(--shadow-md)",
};

function TensorLog({ data }) {
  const [open, setOpen] = useState(false);
  return (
    <div style={{
      background: "#05050A", border: "1px solid var(--border-strong)",
      borderRadius: "var(--radius-xl)", marginBottom: "20px", overflow: "hidden",
      boxShadow: "var(--shadow-sm)"
    }}>
      <div 
        onClick={() => setOpen(!open)}
        style={{
          padding: "14px 20px", display: "flex", alignItems: "center", justifyContent: "space-between",
          cursor: "pointer", background: "var(--surface-1)", borderBottom: open ? "1px solid var(--border-strong)" : "none",
          transition: "background var(--duration-fast)"
        }}
        onMouseEnter={e => e.currentTarget.style.background = "var(--surface-2)"}
        onMouseLeave={e => e.currentTarget.style.background = "var(--surface-1)"}
      >
        <div style={{ display: "flex", alignItems: "center", gap: "10px", color: "var(--brand-400)", fontFamily: "var(--font-mono)", fontSize: "var(--text-xs)", fontWeight: 600 }}>
          <Terminal size={14} /> LIVE TENSOR LOG
        </div>
        <div style={{ fontSize: "10px", color: "var(--text-tertiary)", fontFamily: "var(--font-mono)", letterSpacing: "0.1em" }}>
          {open ? "[COLLAPSE]" : "[EXPAND]"}
        </div>
      </div>
      {open && (
        <div style={{
          padding: "20px", color: "var(--brand-400)", fontFamily: "var(--font-mono)",
          fontSize: "11px", whiteSpace: "pre-wrap", overflowX: "auto", maxHeight: "400px",
          background: "radial-gradient(circle at top left, rgba(99,102,241,0.05) 0%, transparent 80%)"
        }}>
          {JSON.stringify(data, null, 2)}
          <span className="terminal-cursor" style={{ marginLeft: "4px" }} />
        </div>
      )}
    </div>
  );
}

export default function Results() {
  const { state } = useLocation();
  const { scanId } = useParams();
  const navigate = useNavigate();
  const [result, setResult] = useState(state?.result || null);
  const [reported, setReported] = useState(false);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!result && scanId) getScan(scanId).then(setResult);
    const t = setTimeout(() => setVisible(true), 50);
    return () => clearTimeout(t);
  }, [scanId]);

  if (!result) return (
    <div style={{
      minHeight: "100vh", background: "var(--surface-base)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <div style={{
        width: "36px", height: "36px",
        border: "2px solid var(--border-brand)",
        borderTopColor: "var(--brand-500)",
        borderRadius: "50%",
        animation: "spin 0.8s linear infinite",
      }} />
      <style>{`@keyframes spin { to { transform:rotate(360deg); } }`}</style>
    </div>
  );

  // Handle non-job content rejection
  if (result.verdict === "NOT_JOB_CONTENT" || result.is_job_content === false) {
    return <NotJobContentResult result={result} />;
  }

  const cfg = VERDICT_CFG[result.verdict] || VERDICT_CFG.SUSPICIOUS;
  const VIcon = cfg.icon;

  return (
    <div style={{
      minHeight: "100vh", background: "var(--surface-base)",
      opacity: visible ? 1 : 0,
      transform: visible ? "translateY(0)" : "translateY(12px)",
      transition: "opacity 500ms var(--ease-out-quart), transform 500ms var(--ease-out-quart)",
    }}>
      <div style={{ maxWidth: "1000px", margin: "0 auto", padding: "32px 24px 80px" }}>

        {/* Back */}
        <button onClick={() => navigate("/")} style={{
          display: "inline-flex", alignItems: "center", gap: "6px",
          background: "none", border: "none", cursor: "pointer",
          fontSize: "var(--text-sm)", color: "var(--text-tertiary)",
          padding: "0", marginBottom: "28px",
          fontFamily: "var(--font-body)",
          transition: "color var(--duration-fast)",
        }}
        onMouseEnter={e => e.currentTarget.style.color = "var(--text-primary)"}
        onMouseLeave={e => e.currentTarget.style.color = "var(--text-tertiary)"}
        >
          <ArrowLeft size={15} /> Back to Scanner
        </button>

        {/* Verdict banner */}
        <div style={{
          background: cfg.bg,
          border: `1px solid ${cfg.border}`,
          borderRadius: "var(--radius-2xl)",
          padding: "20px 24px",
          display: "flex",
          alignItems: "center",
          justifyContent: "space-between",
          flexWrap: "wrap",
          gap: "16px",
          marginBottom: "20px",
          // Ensure it is always visible above the page background:
          boxShadow: `0 0 0 1px ${cfg.border}, var(--shadow-md)`,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <div style={{
              width: "48px", height: "48px",
              background: `${cfg.color}14`,
              border: `1px solid ${cfg.color}30`,
              borderRadius: "var(--radius-xl)",
              display: "flex", alignItems: "center", justifyContent: "center",
              flexShrink: 0,
            }}>
              <VIcon size={22} color={cfg.color} />
            </div>
            <div>
              <div style={{
                fontSize: "var(--text-xs)", fontWeight: 600,
                letterSpacing: "0.10em", textTransform: "uppercase",
                color: "var(--text-tertiary)", marginBottom: "4px",
              }}>
                {cfg.label}
              </div>
              <div style={{
                fontSize: "var(--text-sm)", color: "var(--text-secondary)",
                lineHeight: 1.4,
              }}>
                {result.recommendation?.slice(0, 100)}…
              </div>
            </div>
          </div>

          <div style={{ display: "flex", gap: "8px" }}>
            <button onClick={() => navigator.clipboard.writeText(window.location.href)}
              style={{
                display: "flex", alignItems: "center", gap: "6px",
                padding: "8px 14px",
                background: "rgba(255,255,255,0.04)",
                border: "1px solid var(--border-default)",
                borderRadius: "var(--radius-lg)",
                color: "var(--text-secondary)", cursor: "pointer",
                fontSize: "var(--text-sm)", fontFamily: "var(--font-body)",
              }}>
              <Share2 size={13} /> Share
            </button>
            {!reported ? (
              <button onClick={() => { reportJob(result.scan_id); setReported(true); }}
                style={{
                  display: "flex", alignItems: "center", gap: "6px",
                  padding: "8px 14px",
                  background: "var(--critical-bg)",
                  border: "1px solid var(--critical-border)",
                  borderRadius: "var(--radius-lg)",
                  color: "var(--critical-400)", cursor: "pointer",
                  fontSize: "var(--text-sm)", fontFamily: "var(--font-body)",
                }}>
                <Flag size={13} /> Report Fraud
              </button>
            ) : (
              <div style={{
                display: "flex", alignItems: "center", gap: "6px",
                padding: "8px 14px",
                background: "var(--safe-bg)",
                border: "1px solid var(--safe-border)",
                borderRadius: "var(--radius-lg)",
                color: "var(--safe-400)",
                fontSize: "var(--text-sm)",
              }}>
                <CheckCircle size={13} /> Reported
              </div>
            )}
          </div>
        </div>

        {/* Tensor Log Terminal */}
        <TensorLog data={result} />

        {/* Score + Signals grid */}
        <div style={{
          display: "grid",
          gridTemplateColumns: "260px 1fr",
          gap: "20px",
          marginBottom: "20px",
        }}>
          {/* Score card */}
          <div style={{
            ...card,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            gap: "8px",
          }}>
            <div style={{
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              letterSpacing: "0.10em",
              textTransform: "uppercase",
              color: "var(--text-tertiary)",
              marginBottom: "12px",
            }}>
              TRUST SCORE
            </div>
            <TrustScoreGauge
              score={result.trust_score}
              verdict={result.verdict}
              effectiveSignals={result.effective_signals}
              totalSignals={Object.keys(result.signal_scores || {}).length}
            />
          </div>

          {/* Signal breakdown card */}
          <div style={card}>
            <div style={{
              fontSize: "var(--text-xs)",
              fontWeight: 600,
              letterSpacing: "0.10em",
              textTransform: "uppercase",
              color: "var(--text-tertiary)",
              marginBottom: "20px",
            }}>
              SIGNAL BREAKDOWN
            </div>
            <SignalBreakdown
              scores={result.signal_scores}
              weights={result.signal_weights}
              configuredWeights={result.configured_weights}
              nlpDetails={result.nlp_details}
              companyDetails={result.company_details}
            />
          </div>
        </div>

        {/* Recommendation */}
        <div style={{
          ...card,
          background: cfg.bg,
          border: `1px solid ${cfg.border}`,
          marginBottom: "20px",
        }}>
          <div style={{
            fontSize: "var(--text-xs)", fontWeight: 600,
            letterSpacing: "0.10em", textTransform: "uppercase",
            color: "var(--text-tertiary)", marginBottom: "12px",
          }}>OUR RECOMMENDATION</div>
          <p style={{
            fontSize: "var(--text-sm)", color: cfg.color,
            lineHeight: "var(--leading-relaxed)",
          }}>{result.recommendation}</p>
        </div>

        {/* Red Flags */}
        {result.flags?.length > 0 && (
          <div style={{ marginBottom: "20px" }}>
            <RedFlagsList flags={result.flags} />
          </div>
        )}

        {/* Explanation */}
        {result.explanation && (
          <ExplainerPanel explanation={result.explanation}
                          modelTrained={result.model_trained} />
        )}
      </div>
    </div>
  );
}
