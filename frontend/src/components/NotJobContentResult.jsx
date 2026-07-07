import { useNavigate } from "react-router-dom";
import { Search, ArrowLeft, ExternalLink,
         FileText, Link2, HelpCircle } from "lucide-react";

const EXAMPLE_URLS = [
  {
    label: "Naukri.com listing",
    url: "https://www.naukri.com/job-listings-software-engineer-123456",
    icon: "🔗"
  },
  {
    label: "LinkedIn job posting",
    url: "https://www.linkedin.com/jobs/view/software-engineer-1234567",
    icon: "🔗"
  },
  {
    label: "Company career portal",
    url: "https://careers.infosys.com/jobid/SE-2024-001",
    icon: "🏢"
  },
];

export default function NotJobContentResult({ result }) {
  const navigate = useNavigate();
  const entity = result.explanation_context?.detected_entity;
  const suggestions = result.suggestions || [];
  const detectedType = result.explanation_context?.detected_type;

  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--surface-page, var(--surface-base))",
      color: "var(--text-primary)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      justifyContent: "center",
      padding: "40px 24px",
    }}>
      <div style={{ maxWidth: "600px", width: "100%", textAlign: "center" }}>

        {/* Icon */}
        <div style={{
          width: "72px", height: "72px",
          background: "rgba(255,255,255,0.04)",
          border: "1px solid var(--border-default)",
          borderRadius: "var(--radius-2xl)",
          display: "flex", alignItems: "center", justifyContent: "center",
          margin: "0 auto 28px",
          boxShadow: "var(--shadow-md)",
        }}>
          <Search size={30} color="var(--text-tertiary)" />
        </div>

        {/* Heading */}
        <h1 style={{
          fontFamily: "var(--font-display)", fontWeight: 700,
          fontSize: "var(--text-2xl)", letterSpacing: "-0.03em",
          color: "var(--text-primary)", marginBottom: "14px",
        }}>
          This does not appear to be a job posting
        </h1>

        {/* Explanation */}
        <p style={{
          fontSize: "var(--text-base)", color: "var(--text-secondary)",
          lineHeight: "var(--leading-relaxed)", marginBottom: "8px",
        }}>
          {result.rejection_reason}
        </p>

        {entity && (
          <div style={{
            display: "inline-flex", alignItems: "center", gap: "6px",
            marginTop: "8px", marginBottom: "32px",
            padding: "5px 12px",
            background: "rgba(255,255,255,0.04)",
            border: "1px solid var(--border-subtle)",
            borderRadius: "var(--radius-full)",
            fontSize: "var(--text-sm)", color: "var(--text-tertiary)",
          }}>
            <HelpCircle size={12} />
            Detected as: <strong style={{ color: "var(--text-secondary)" }}>{entity}</strong>
          </div>
        )}

        {/* What to do instead */}
        <div style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border-default)",
          borderRadius: "var(--radius-2xl)",
          padding: "24px",
          marginBottom: "24px",
          textAlign: "left",
          boxShadow: "var(--shadow-md)",
        }}>
          <div style={{
            fontSize: "var(--text-xs)", fontWeight: 600,
            letterSpacing: "0.10em", textTransform: "uppercase",
            color: "var(--text-tertiary)", marginBottom: "16px",
          }}>
            What to submit instead
          </div>

          <div style={{ display: "flex", flexDirection: "column", gap: "10px" }}>
            <div style={{
              display: "flex", alignItems: "flex-start", gap: "12px",
              padding: "12px 14px",
              background: "var(--surface-2)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-lg)",
            }}>
              <Link2 size={15} color="var(--brand-400)" style={{ marginTop: "1px", flexShrink: 0 }} />
              <div>
                <div style={{
                  fontSize: "var(--text-sm)", fontWeight: 500,
                  color: "var(--text-primary)", marginBottom: "3px",
                }}>
                  The direct URL of a job listing
                </div>
                <div style={{
                  fontSize: "var(--text-xs)", color: "var(--text-tertiary)",
                  fontFamily: "var(--font-mono)",
                }}>
                  naukri.com/job-listings-... · linkedin.com/jobs/view/... · careers.company.com/...
                </div>
              </div>
            </div>

            <div style={{
              display: "flex", alignItems: "flex-start", gap: "12px",
              padding: "12px 14px",
              background: "var(--surface-2)",
              border: "1px solid var(--border-subtle)",
              borderRadius: "var(--radius-lg)",
            }}>
              <FileText size={15} color="var(--brand-400)" style={{ marginTop: "1px", flexShrink: 0 }} />
              <div>
                <div style={{
                  fontSize: "var(--text-sm)", fontWeight: 500,
                  color: "var(--text-primary)", marginBottom: "3px",
                }}>
                  The full job description text
                </div>
                <div style={{
                  fontSize: "var(--text-xs)", color: "var(--text-tertiary)",
                }}>
                  Copy and paste the complete job posting text into the Description tab
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Example URLs */}
        <div style={{
          background: "var(--surface-1)",
          border: "1px solid var(--border-default)",
          borderRadius: "var(--radius-2xl)",
          padding: "24px",
          marginBottom: "24px",
          textAlign: "left",
          boxShadow: "var(--shadow-md)",
        }}>
          <div style={{
            fontSize: "var(--text-xs)", fontWeight: 600,
            letterSpacing: "0.10em", textTransform: "uppercase",
            color: "var(--text-tertiary)", marginBottom: "16px",
          }}>
            Example valid URLs
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: "8px" }}>
            {EXAMPLE_URLS.map(({ label, url, icon }) => (
              <div key={url} style={{
                display: "flex", alignItems: "center", gap: "10px",
                padding: "8px 12px",
                background: "var(--surface-2)",
                border: "1px solid var(--border-subtle)",
                borderRadius: "var(--radius-lg)",
                fontSize: "var(--text-xs)",
              }}>
                <span>{icon}</span>
                <div>
                  <div style={{ color: "var(--text-secondary)", fontWeight: 500, marginBottom: "2px" }}>{label}</div>
                  <div style={{ color: "var(--text-disabled)", fontFamily: "var(--font-mono)", fontSize: "11px" }}>{url}</div>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Action buttons */}
        <div style={{ display: "flex", gap: "10px", justifyContent: "center" }}>
          <button
            onClick={() => navigate("/")}
            style={{
              display: "flex", alignItems: "center", gap: "8px",
              padding: "11px 22px",
              background: "linear-gradient(135deg, var(--brand-600), var(--brand-500))",
              border: "1px solid rgba(129,140,248,0.30)",
              borderRadius: "var(--radius-lg)",
              color: "white",
              fontFamily: "var(--font-display)",
              fontSize: "var(--text-sm)", fontWeight: 600,
              cursor: "pointer",
              boxShadow: "0 4px 20px rgba(99,102,241,0.22), var(--shadow-inset)",
              transition: "all var(--duration-fast) var(--ease-out-quart)",
            }}
            onMouseEnter={e => {
              e.currentTarget.style.transform = "translateY(-1px)";
              e.currentTarget.style.boxShadow = "0 8px 28px rgba(99,102,241,0.35), var(--shadow-inset)";
            }}
            onMouseLeave={e => {
              e.currentTarget.style.transform = "translateY(0)";
              e.currentTarget.style.boxShadow = "0 4px 20px rgba(99,102,241,0.22), var(--shadow-inset)";
            }}
          >
            <ArrowLeft size={15} />
            Try again with a job posting
          </button>
        </div>
      </div>
    </div>
  );
}
