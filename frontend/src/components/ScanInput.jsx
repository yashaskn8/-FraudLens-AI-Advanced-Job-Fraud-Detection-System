import { useState, useRef } from "react";
import { Link2, FileText, Layers, ChevronDown, Shield,
         AlertCircle, Building2, Mail, Briefcase } from "lucide-react";

const TABS = [
  { id: "url",  icon: Link2,    label: "URL"         },
  { id: "text", icon: FileText, label: "Description" },
  { id: "both", icon: Layers,   label: "Both"        },
];

const PLACEHOLDER_URLS = [
  "https://naukri.com/job-listings-senior-engineer",
  "https://careers.infosys.com/jobid/12345",
  "https://linkedin.com/jobs/view/software-engineer",
];

const INSTANT_REJECT_DOMAINS = new Set([
  "gemini.google.com", "chat.openai.com", "claude.ai",
  "google.com", "bing.com", "youtube.com", "facebook.com",
  "instagram.com", "twitter.com", "x.com", "reddit.com",
  "amazon.com", "amazon.in", "flipkart.com", "netflix.com",
  "wikipedia.org", "medium.com", "github.com",
]);

function isLikelyNonJobUrl(url) {
  try {
    const parsed = new URL(url.startsWith("http") ? url : "https://" + url);
    const hostname = parsed.hostname.replace("www.", "").toLowerCase();
    if (INSTANT_REJECT_DOMAINS.has(hostname)) return true;
    // LinkedIn with non-job paths
    if (hostname === "linkedin.com" && !parsed.pathname.includes("/jobs")) return true;
    return false;
  } catch {
    return false;
  }
}

/**
 * Validates that the URL input is actually a URL before submitting.
 * Returns null if valid, or an error message string if invalid.
 *
 * Accepts:
 *   https://careers.infosys.com/jobid/12345    ✓
 *   http://naukri.com/job-listings-engineer     ✓
 *   www.linkedin.com/jobs/view/123456           ✓  (auto-prefixed)
 *   linkedin.com/jobs/view/123456               ✓  (auto-prefixed)
 *
 * Rejects:
 *   h                                           ✗
 *   google                                      ✗
 *   software engineer                           ✗
 *   just some words                             ✗
 *   12345                                       ✗
 *   @username                                   ✗
 */
function validateUrlInput(input) {
  if (!input || !input.trim()) {
    return "Please enter a job posting URL or switch to the Description tab.";
  }

  const trimmed = input.trim();

  // Must contain at least one dot to be a domain
  if (!trimmed.includes(".")) {
    return "That doesn't look like a URL. Please enter a full job posting URL " +
           "such as https://naukri.com/job-listings-... or a company careers page.";
  }

  // Must not be just a single word or random text
  // A URL must have a domain structure: something.something
  const withProtocol = trimmed.startsWith("http")
    ? trimmed
    : "https://" + trimmed.replace(/^www\./, "");

  try {
    const parsed = new URL(withProtocol);

    // Hostname must have at least one dot (domain.tld)
    if (!parsed.hostname.includes(".")) {
      return "That doesn't look like a valid URL. Please enter a complete " +
             "job posting URL including the domain name.";
    }

    // Hostname must not be only digits (IP-like inputs from keyboard mashing)
    if (/^\d+\.\d+$/.test(parsed.hostname)) {
      return "That doesn't look like a valid job posting URL.";
    }

    // Hostname must be at least 4 characters (catches "h.c" etc.)
    if (parsed.hostname.replace("www.", "").length < 4) {
      return "That doesn't look like a valid URL. Please enter a complete " +
             "job posting URL from Naukri, LinkedIn, Indeed, or a company careers page.";
    }

    // Valid URL structure confirmed
    return null;

  } catch (e) {
    // URL constructor threw — not a parseable URL
    return "That doesn't look like a URL. Please enter a job posting URL " +
           "such as https://naukri.com/job-listings-... or a careers page link.";
  }
}

export default function ScanInput({ onScan }) {
  const [mode, setMode] = useState("url");
  const [url, setUrl] = useState("");
  const [description, setDescription] = useState("");
  const [jobTitle, setJobTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [recruiterEmail, setRecruiterEmail] = useState("");
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [focused, setFocused] = useState(null);
  const [urlError, setUrlError] = useState("");
  const [placeholderIdx] = useState(() => Math.floor(Math.random() * PLACEHOLDER_URLS.length));

  const handleScan = () => {
    setUrlError("");
    
    // If URL mode is active, validate the URL before submitting
    if (mode === "url" || mode === "both") {
      if (url && url.trim()) {
        const errorMsg = validateUrlInput(url);
        if (errorMsg) {
          setUrlError(errorMsg);
          return;   // Stop here — do not call onScan, do not hit the backend
        }
      }
    }

    // If description mode is active with no URL, check description has content
    if ((mode === "text") && (!description || description.trim().length < 20)) {
      setUrlError("Please paste the full job description text (at least 20 characters) " +
               "for accurate analysis.");
      return;
    }

    // If both mode and neither field has content
    if (mode === "both" && (!url || !url.trim()) && (!description || description.trim().length < 5)) {
      setUrlError("Please provide a job URL, a job description, or both.");
      return;
    }

    if (url && isLikelyNonJobUrl(url)) {
      setUrlError(
        "That URL does not look like a job posting. " +
        "Please submit a URL from a job board (Naukri, LinkedIn Jobs, Indeed) " +
        "or a company careers page."
      );
      return;
    }

    onScan({ url, description, jobTitle, companyName, recruiterEmail });
  };

  const inputStyle = (name) => ({
    width: "100%",
    background: focused === name ? "var(--surface-3)" : "var(--surface-2)",
    border: `1px solid ${focused === name ? "var(--border-brand)" : "var(--border-subtle)"}`,
    borderRadius: "var(--radius-lg)",
    padding: "11px 14px",
    color: "var(--text-primary)",
    fontSize: "var(--text-sm)",
    fontFamily: "var(--font-body)",
    outline: "none",
    transition: "all var(--duration-fast) var(--ease-out-quart)",
    boxShadow: focused === name ? "var(--shadow-brand)" : "none",
    resize: "none",
  });

  const labelStyle = {
    display: "block",
    fontSize: "var(--text-xs)",
    fontWeight: 600,
    color: "var(--text-tertiary)",
    letterSpacing: "0.06em",
    textTransform: "uppercase",
    marginBottom: "6px",
  };

  return (
    <div style={{
      background: "var(--surface-1)",
      border: "1px solid var(--border-default)",
      borderRadius: "var(--radius-2xl)",
      padding: "24px",
      maxWidth: "680px",
      margin: "0 auto",
      textAlign: "left",
    }}>

      {/* Mode tabs */}
      <div style={{
        display: "flex", gap: "4px",
        background: "var(--surface-base)",
        borderRadius: "var(--radius-lg)",
        padding: "4px",
        marginBottom: "20px",
        border: "1px solid var(--border-subtle)",
      }}>
        {TABS.map(({ id, icon: Icon, label }) => {
          const active = mode === id;
          return (
            <button key={id} onClick={() => setMode(id)} style={{
              flex: 1, display: "flex", alignItems: "center",
              justifyContent: "center", gap: "6px",
              padding: "8px",
              borderRadius: "var(--radius-md)",
              border: "none", cursor: "pointer",
              fontFamily: "var(--font-body)",
              fontSize: "var(--text-sm)", fontWeight: active ? 600 : 400,
              color: active ? "var(--text-primary)" : "var(--text-tertiary)",
              background: active
                ? "linear-gradient(135deg, rgba(99,102,241,0.18), rgba(129,140,248,0.08))"
                : "transparent",
              outline: active ? "1px solid var(--border-brand)" : "none",
              transition: "all var(--duration-fast) var(--ease-out-quart)",
            }}>
              <Icon size={13} />
              {label}
            </button>
          );
        })}
      </div>

      {/* URL input */}
      {(mode === "url" || mode === "both") && (
        <div style={{ marginBottom: "14px" }}>
          <label style={labelStyle}>Job Posting URL</label>
          <div style={{ position: "relative" }}>
            <input
              type="url" value={url}
              onChange={e => setUrl(e.target.value)}
              onFocus={() => setFocused("url")}
              onBlur={() => setFocused(null)}
              placeholder={PLACEHOLDER_URLS[placeholderIdx]}
              style={{ ...inputStyle("url"), paddingLeft: "38px" }}
            />
            <Link2 size={14} style={{
              position: "absolute", left: "12px", top: "50%",
              transform: "translateY(-50%)",
              color: focused === "url" ? "var(--brand-400)" : "var(--text-disabled)",
              transition: "color var(--duration-fast)",
            }} />
          </div>
        </div>
      )}

      {/* Description input */}
      {(mode === "text" || mode === "both") && (
        <div style={{ marginBottom: "14px" }}>
          <label style={labelStyle}>Job Description</label>
          <textarea
            value={description}
            onChange={e => setDescription(e.target.value)}
            onFocus={() => setFocused("desc")}
            onBlur={() => setFocused(null)}
            placeholder="Paste the full job description here for deepest analysis…"
            rows={5}
            style={inputStyle("desc")}
          />
          <div style={{
            display: "flex", justifyContent: "flex-end",
            marginTop: "4px",
            fontSize: "var(--text-xs)", color: "var(--text-disabled)",
          }}>
            {description.length} chars
          </div>
        </div>
      )}

      {/* Advanced fields toggle */}
      <button
        onClick={() => setShowAdvanced(!showAdvanced)}
        style={{
          display: "flex", alignItems: "center", gap: "6px",
          background: "none", border: "none", cursor: "pointer",
          fontSize: "var(--text-xs)", color: "var(--text-tertiary)",
          padding: "4px 0", marginBottom: showAdvanced ? "14px" : "0",
          fontFamily: "var(--font-body)",
        }}
      >
        <ChevronDown size={12} style={{
          transform: showAdvanced ? "rotate(180deg)" : "rotate(0deg)",
          transition: "transform var(--duration-fast)",
        }} />
        {showAdvanced ? "Hide" : "Add"} optional details — improves accuracy
      </button>

      {showAdvanced && (
        <div style={{
          display: "grid", gridTemplateColumns: "1fr 1fr", gap: "12px",
          marginBottom: "14px",
          animation: "fadeIn 200ms var(--ease-out-quart)",
        }}>
          {[
            { key: "jobTitle", val: jobTitle, set: setJobTitle,
              label: "Job Title", icon: Briefcase, ph: "e.g. Senior Data Analyst" },
            { key: "company", val: companyName, set: setCompanyName,
              label: "Company Name", icon: Building2, ph: "e.g. Infosys Limited" },
            { key: "email", val: recruiterEmail, set: setRecruiterEmail,
              label: "Recruiter Email", icon: Mail, ph: "e.g. hr@company.com" },
          ].map(({ key, val, set, label, icon: Icon, ph }) => (
            <div key={key} style={{ gridColumn: key === "email" ? "span 2" : "span 1" }}>
              <label style={labelStyle}>{label}</label>
              <div style={{ position: "relative" }}>
                <input
                  type="text" value={val}
                  onChange={e => set(e.target.value)}
                  onFocus={() => setFocused(key)}
                  onBlur={() => setFocused(null)}
                  placeholder={ph}
                  style={{ ...inputStyle(key), paddingLeft: "34px" }}
                />
                <Icon size={13} style={{
                  position: "absolute", left: "11px", top: "50%",
                  transform: "translateY(-50%)",
                  color: focused === key ? "var(--brand-400)" : "var(--text-disabled)",
                  transition: "color var(--duration-fast)",
                }} />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Client-side URL validation error */}
      {urlError && (
        <div style={{
          marginBottom: "10px", padding: "10px 14px",
          background: "rgba(239,68,68,0.08)",
          border: "1px solid rgba(239,68,68,0.20)",
          borderRadius: "var(--radius-lg)",
          fontSize: "var(--text-sm)", color: "#f87171",
          display: "flex", alignItems: "flex-start", gap: "8px",
          animation: "fadeIn 200ms var(--ease-out-quart)",
        }}>
          <AlertCircle size={14} style={{ marginTop: "2px", flexShrink: 0 }} />
          {urlError}
        </div>
      )}

      {/* Submit */}
      <button
        onClick={handleScan}
        style={{
          width: "100%", marginTop: "8px",
          padding: "13px 24px",
          background: "linear-gradient(135deg, var(--brand-600), var(--brand-500))",
          border: "1px solid rgba(129,140,248,0.30)",
          borderRadius: "var(--radius-lg)",
          color: "white",
          fontFamily: "var(--font-display)",
          fontSize: "var(--text-base)", fontWeight: 600,
          letterSpacing: "-0.01em",
          cursor: "pointer",
          display: "flex", alignItems: "center",
          justifyContent: "center", gap: "8px",
          boxShadow: "0 4px 20px rgba(99,102,241,0.25), var(--shadow-inset)",
          transition: "all var(--duration-fast) var(--ease-out-quart)",
        }}
        onMouseEnter={e => {
          e.currentTarget.style.transform = "translateY(-1px)";
          e.currentTarget.style.boxShadow = "0 8px 28px rgba(99,102,241,0.35), var(--shadow-inset)";
        }}
        onMouseLeave={e => {
          e.currentTarget.style.transform = "translateY(0)";
          e.currentTarget.style.boxShadow = "0 4px 20px rgba(99,102,241,0.25), var(--shadow-inset)";
        }}
        onMouseDown={e => e.currentTarget.style.transform = "translateY(0) scale(0.99)"}
        onMouseUp={e => e.currentTarget.style.transform = "translateY(-1px)"}
      >
        <Shield size={16} />
        Analyse This Job Posting
      </button>

      <style>{`
        @keyframes fadeIn {
          from { opacity: 0; transform: translateY(-8px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        input::placeholder, textarea::placeholder {
          color: var(--text-disabled);
          font-family: var(--font-body);
        }
      `}</style>
    </div>
  );
}
