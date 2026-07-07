import { useState } from "react";
import { Info, ChevronDown, ChevronUp, AlertTriangle, CheckCircle, ShieldAlert } from "lucide-react";
import MagicCard from "./MagicCard";

const SIGNAL_META = {
  "URL Analysis": {
    icon: "🔗",
    desc: "Domain age, SSL certificate, WHOIS data, redirect chain, phishing database checks"
  },
  "NLP Classification": {
    icon: "🧠",
    desc: "Fraud language detection across the job description text"
  },
  "Company Verification": {
    icon: "🌍",
    desc: "National registry verification (MCA21, Companies House, SEC, ABN), email domain match, company website verification"
  },
};

const MODEL_SOURCE_BADGES = {
  bert_finetuned: {
    label: "Trained AI",
    bg: "background: rgba(34,197,94,0.1)", text: "color: #22c55e",
    border: "border: 1px solid rgba(34,197,94,0.2)",
    title: "Fine-tuned BERT model trained on EMSCAD dataset"
  },
  baseline_xgb: {
    label: "Baseline",
    bg: "background: rgba(56,189,248,0.1)", text: "color: #38bdf8",
    border: "border: 1px solid rgba(56,189,248,0.2)",
    title: "TF-IDF + XGBoost baseline — run train_models.py for full accuracy"
  },
  heuristic: {
    label: "Heuristic",
    bg: "background: rgba(234,179,8,0.1)", text: "color: #eab308",
    border: "border: 1px solid rgba(234,179,8,0.2)",
    title: "Structural analysis — training in progress automatically"
  },
};

function getTrafficLight(score) {
  // These thresholds align with what the backend trust scorer uses
  if (score >= 70) return { color: "#22c55e", bg: "rgba(34,197,94,0.1)", label: "SAFE", icon: CheckCircle };
  if (score >= 50) return { color: "#f59e0b", bg: "rgba(245,158,11,0.1)", label: "CAUTION", icon: AlertTriangle };
  if (score >= 30) return { color: "#f97316", bg: "rgba(249,115,22,0.1)", label: "WARNING", icon: AlertTriangle };
  return { color: "#ef4444", bg: "rgba(239,68,68,0.1)", label: "DANGER", icon: ShieldAlert };
}

export default function SignalBreakdown({
  scores = {},
  weights = {},
  configuredWeights = {},
  nlpDetails = {},
  companyDetails = {},
}) {
  const [expanded, setExpanded] = useState(null);

  // Fallback defaults if API takes a split second to populate
  const safeScores = Object.keys(scores).length > 0 ? scores : { "URL Analysis": 100, "NLP Classification": 100, "Company Verification": 100 };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "16px" }}>
      {Object.entries(safeScores).map(([signal, score]) => {
        const hasScore = score !== null && score !== undefined;
        const displayScore = hasScore ? score : 50;
        
        // Traffic Light Logic (Red, Orange, Green)
        const traffic = getTrafficLight(displayScore);
        const { color, bg, label: statusLabel, icon: StatusIcon } = traffic;

        const meta = SIGNAL_META[signal] || { icon: "📊", desc: "Security analysis signal" };
        const effectiveWeight = weights[signal] || 0;
        const configuredWeight = configuredWeights[signal] || 0;
        const weightRedistributed = (
          hasScore && effectiveWeight > 0 && Math.abs(effectiveWeight - configuredWeight) > 0.5
        );

        const isNLP = signal === "NLP Classification";
        const modelSource = isNLP ? (nlpDetails?.model_source || "heuristic") : null;
        const sourceBadge = modelSource ? MODEL_SOURCE_BADGES[modelSource] : null;

        const isExpanded = expanded === signal;

        return (
          <MagicCard key={signal} style={{
            background: "var(--surface-1)", border: "1px solid var(--border-default)",
            borderRadius: "var(--radius-xl)", overflow: "hidden", transition: "all 300ms ease",
            boxShadow: isExpanded ? `0 0 20px ${bg}` : "var(--shadow-sm)"
          }}>
            <button
              onClick={() => setExpanded(isExpanded ? null : signal)}
              style={{
                width: "100%", textAlign: "left", padding: "20px 24px",
                background: "transparent", border: "none", cursor: "pointer",
                fontFamily: "var(--font-body)", display: "flex", flexDirection: "column", gap: "16px"
              }}
            >
              {/* Header Info */}
              <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", width: "100%" }}>
                <div style={{ display: "flex", alignItems: "center", gap: "12px", flexWrap: "wrap" }}>
                  <div style={{
                    width: "36px", height: "36px", background: "var(--surface-2)", borderRadius: "var(--radius-lg)",
                    border: "1px solid var(--border-subtle)", display: "flex", alignItems: "center", justifyContent: "center",
                    fontSize: "1.1rem"
                  }}>
                    {meta.icon}
                  </div>
                  <span style={{ fontSize: "var(--text-base)", fontWeight: 600, color: "var(--text-primary)" }}>
                    {signal}
                  </span>

                  {effectiveWeight > 0 && (
                    <span
                      title={weightRedistributed ? `Redistributed to ${effectiveWeight.toFixed(1)}%` : `Weight: ${effectiveWeight.toFixed(1)}%`}
                      style={{
                        fontSize: "11px", fontFamily: "var(--font-mono)",
                        padding: "3px 8px", borderRadius: "var(--radius-sm)",
                        background: weightRedistributed ? "rgba(99,102,241,0.15)" : "var(--surface-3)",
                        border: weightRedistributed ? "1px solid var(--border-brand)" : "1px solid transparent",
                        color: weightRedistributed ? "var(--brand-400)" : "var(--text-tertiary)",
                      }}
                    >
                      {effectiveWeight.toFixed(0)}%
                    </span>
                  )}

                  {sourceBadge && (
                    <span style={{
                      fontSize: "11px", fontWeight: 600, padding: "3px 8px", borderRadius: "var(--radius-sm)",
                      ...Object.fromEntries([sourceBadge.bg, sourceBadge.text, sourceBadge.border].map(s => s.split(":").map(x=>x.trim())))
                    }}>
                      {sourceBadge.label}
                    </span>
                  )}
                </div>

                {/* Score & Status */}
                <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
                  <div style={{
                    display: "flex", alignItems: "center", gap: "6px",
                    padding: "4px 10px", borderRadius: "var(--radius-full)",
                    background: bg, border: `1px solid ${color}30`,
                    color: color, fontSize: "11px", fontWeight: 700, letterSpacing: "0.06em",
                  }}>
                    <StatusIcon size={12} /> {statusLabel}
                  </div>
                  <span style={{ fontSize: "var(--text-lg)", fontWeight: 700, color: color, fontFamily: "var(--font-mono)" }}>
                    {displayScore}/100
                  </span>
                  {isExpanded ? <ChevronUp size={16} color="var(--text-disabled)" /> : <ChevronDown size={16} color="var(--text-disabled)" />}
                </div>
              </div>

              {/* Advanced Glowing Progress Track */}
              <div style={{ width: "100%", height: "8px", background: "rgba(255,255,255,0.04)", borderRadius: "var(--radius-full)", overflow: "hidden", position: "relative" }}>
                {/* Segmented Markers */}
                <div style={{ position: "absolute", inset: 0, backgroundImage: "linear-gradient(90deg, transparent 99%, rgba(0,0,0,0.5) 100%)", backgroundSize: "10% 100%", zIndex: 1 }} />
                
                {/* Glowing Fill */}
                <div style={{
                  height: "100%", width: `${displayScore}%`,
                  background: `linear-gradient(90deg, transparent, ${color})`,
                  borderRadius: "var(--radius-full)", position: "relative", zIndex: 0,
                  transition: "width 1.2s cubic-bezier(0.34,1.56,0.64,1)",
                }}>
                  {/* Outer Glow Bloom */}
                  <div style={{
                    position: "absolute", right: 0, top: "50%", transform: "translateY(-50%)",
                    width: "20px", height: "100%", background: color, filter: "blur(6px)", opacity: 0.8
                  }} />
                </div>
              </div>
            </button>

            {/* Expanded Content */}
            {isExpanded && (
              <div style={{
                padding: "0 24px 24px",
                display: "flex", flexDirection: "column", gap: "12px",
                animation: "fadeSlideDown 300ms var(--ease-out-quart) both"
              }}>
                <div style={{
                  padding: "16px", background: "rgba(0,0,0,0.2)", borderRadius: "var(--radius-lg)",
                  border: "1px solid var(--border-subtle)", borderLeft: `3px solid ${color}`
                }}>
                  <p style={{ fontSize: "var(--text-sm)", color: "var(--text-secondary)", lineHeight: 1.6 }}>{meta.desc}</p>
                  
                  {isExpanded && signal === "Company Verification" && companyDetails && (
                    <div style={{ marginTop: "12px", display: "flex", flexDirection: "column", gap: "8px" }}>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                        <span style={{ fontWeight: 600 }}>Detected Country:</span>
                        <span style={{ color: "var(--text-primary)" }}>
                          {companyDetails.detected_country_name} ({companyDetails.detected_country})
                        </span>
                      </div>
                      <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--text-secondary)" }}>
                        <span style={{ fontWeight: 600 }}>Registry Checked:</span>
                        <span style={{ color: "var(--brand-400)", fontFamily: "var(--font-mono)", fontSize: "12px" }}>
                          {companyDetails.registry_used}
                        </span>
                      </div>
                    </div>
                  )}

                  {isNLP && nlpDetails?.scam_phrases_found?.length > 0 && (
                    <div style={{ marginTop: "16px" }}>
                      <div style={{ fontSize: "12px", fontWeight: 600, color: "var(--text-primary)", marginBottom: "8px", textTransform: "uppercase", letterSpacing: "0.04em" }}>Red Flags Detected</div>
                      <div style={{ display: "flex", flexWrap: "wrap", gap: "8px" }}>
                        {nlpDetails.scam_phrases_found.slice(0, 5).map((p, i) => (
                          <span key={i} style={{
                            background: "rgba(239,68,68,0.1)", color: "#ef4444",
                            border: "1px solid rgba(239,68,68,0.2)", borderRadius: "var(--radius-sm)",
                            padding: "4px 8px", fontFamily: "var(--font-mono)", fontSize: "11px",
                          }}>"{p}"</span>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}
          </MagicCard>
        );
      })}
    </div>
  );
}
