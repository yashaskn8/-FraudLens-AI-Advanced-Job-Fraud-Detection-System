import { useState } from "react";
import { AlertTriangle, ChevronDown, ChevronUp,
         ShieldAlert, AlertCircle, Info } from "lucide-react";

function severity(flag) {
  const f = flag.toLowerCase();
  if (/phishing|malware|virustotal|ip address|pay.*fee|deposit|known fraudulent/.test(f))
    return "critical";
  if (/days ago|new domain|gmail|generic email|not found|free hosting|shortener/.test(f))
    return "high";
  if (/redirect|suspicious|could not verify|short description/.test(f))
    return "medium";
  return "low";
}

const SEV = {
  critical: { color: "var(--critical-400)", bg: "var(--critical-bg)",
               border: "var(--critical-border)", icon: ShieldAlert,   label: "Critical" },
  high:     { color: "var(--fraud-400)",    bg: "var(--fraud-bg)",
               border: "var(--fraud-border)",    icon: AlertTriangle, label: "High"     },
  medium:   { color: "var(--suspicious-400)", bg: "var(--suspicious-bg)",
               border: "var(--suspicious-border)", icon: AlertCircle, label: "Warning"  },
  low:      { color: "var(--brand-400)",    bg: "rgba(99,102,241,0.06)",
               border: "rgba(99,102,241,0.15)",  icon: Info,          label: "Notice"   },
};

export default function RedFlagsList({ flags }) {
  const [expanded, setExpanded] = useState(true);
  const [showAll, setShowAll] = useState(false);
  const sortedFlags = [...flags].sort((a, b) => {
    const order = { critical:0, high:1, medium:2, low:3 };
    return order[severity(a)] - order[severity(b)];
  });
  const display = showAll ? sortedFlags : sortedFlags.slice(0, 5);

  const countBySev = sortedFlags.reduce((acc, f) => {
    const s = severity(f); acc[s] = (acc[s] || 0) + 1; return acc;
  }, {});

  return (
    <div style={{
      background: "var(--surface-1)",
      border: "1px solid var(--border-default)",
      borderRadius: "var(--radius-2xl)",
      overflow: "hidden",
    }}>
      {/* Header */}
      <button onClick={() => setExpanded(!expanded)} style={{
        width: "100%", padding: "20px 24px",
        display: "flex", alignItems: "center", gap: "12px",
        background: "none", border: "none", cursor: "pointer",
        borderBottom: expanded ? "1px solid var(--border-subtle)" : "none",
      }}>
        <AlertTriangle size={16} color="var(--fraud-400)" />
        <span style={{
          fontFamily: "var(--font-body)", fontWeight: 600,
          fontSize: "var(--text-sm)", color: "var(--text-primary)",
        }}>
          Red Flags Detected
        </span>

        {/* Severity counts */}
        <div style={{ display: "flex", gap: "6px", marginLeft: "4px" }}>
          {Object.entries(countBySev).map(([sev, count]) => (
            <span key={sev} style={{
              padding: "2px 7px",
              background: SEV[sev].bg,
              border: `1px solid ${SEV[sev].border}`,
              borderRadius: "var(--radius-full)",
              fontSize: "var(--text-xs)", fontWeight: 700,
              color: SEV[sev].color,
            }}>
              {count} {sev}
            </span>
          ))}
        </div>

        <div style={{ marginLeft: "auto", color: "var(--text-tertiary)" }}>
          {expanded ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
        </div>
      </button>

      {expanded && (
        <div style={{ padding: "16px 24px 20px" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {display.map((flag, i) => {
              const sev = severity(flag);
              const { color, bg, border, icon: Icon, label } = SEV[sev];
              return (
                <div key={i} style={{
                  display: "flex", alignItems: "flex-start", gap: "12px",
                  padding: "12px 14px",
                  background: bg, border: `1px solid ${border}`,
                  borderRadius: "var(--radius-lg)",
                  animation: `fadeIn 200ms ${i * 40}ms var(--ease-out-quart) both`,
                }}>
                  <div style={{
                    display: "flex", alignItems: "center", gap: "5px",
                    flexShrink: 0, paddingTop: "1px",
                  }}>
                    <Icon size={13} color={color} />
                    <span style={{
                      fontSize: "var(--text-xs)", fontWeight: 700,
                      color, letterSpacing: "0.05em",
                    }}>{label}</span>
                  </div>
                  <span style={{
                    fontSize: "var(--text-sm)", color: "var(--text-secondary)",
                    lineHeight: "var(--leading-normal)",
                  }}>{flag}</span>
                </div>
              );
            })}
          </div>

          {sortedFlags.length > 5 && (
            <button onClick={() => setShowAll(!showAll)} style={{
              marginTop: "12px",
              display: "flex", alignItems: "center", gap: "5px",
              background: "none", border: "none", cursor: "pointer",
              fontSize: "var(--text-xs)", color: "var(--text-tertiary)",
              fontFamily: "var(--font-body)", padding: 0,
            }}>
              {showAll
                ? <><ChevronUp size={12} /> Show fewer flags</>
                : <><ChevronDown size={12} /> Show {sortedFlags.length - 5} more flags</>
              }
            </button>
          )}
        </div>
      )}

      <style>{`
        @keyframes fadeIn {
          from { opacity:0; transform: translateX(-6px); }
          to   { opacity:1; transform: translateX(0); }
        }
      `}</style>
    </div>
  );
}
