import { useState, useEffect } from "react";
import { Clock } from "lucide-react";
import { getHistory } from "../api/client";

export default function ScanHistory() {
  const [scans, setScans] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHistory()
      .then((data) => setScans(data.scans || []))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const verdictColors = {
    SAFE: "#22C55E", SUSPICIOUS: "#EAB308", LIKELY_FRAUD: "#F97316", FRAUD: "#EF4444",
  };

  if (loading) return <div className="text-[color:var(--text-tertiary)] text-sm">Loading history...</div>;
  if (scans.length === 0) return <div className="text-[color:var(--text-tertiary)] text-sm">No scans yet.</div>;

  return (
    <div className="space-y-2">
      <div className="flex items-center gap-2 mb-3">
        <Clock size={14} className="text-[color:var(--text-secondary)]" />
        <span className="text-sm font-medium text-[color:var(--text-primary)]">Recent Scans</span>
      </div>
      {scans.slice(0, 10).map((scan) => (
        <a
          key={scan.scan_id}
          href={`/results/${scan.scan_id}`}
          className="flex items-center gap-3 bg-surface-base rounded-lg p-2.5 hover:bg-white/5 transition-colors"
        >
          <span
            className="text-sm font-bold w-8 text-center"
            style={{ color: verdictColors[scan.verdict] }}
          >
            {scan.trust_score}
          </span>
          <span className="text-sm text-[color:var(--text-primary)] truncate flex-1">
            {scan.job_title || scan.url || "Untitled"}
          </span>
        </a>
      ))}
    </div>
  );
}
