import { useState } from "react";
import { Flag, CheckCircle } from "lucide-react";
import { reportJob } from "../api/client";

export default function ReportButton({ scanId }) {
  const [reported, setReported] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleReport = async () => {
    setLoading(true);
    try {
      await reportJob(scanId, "User-flagged as fraudulent");
      setReported(true);
    } catch {
      // Ignore errors
    } finally {
      setLoading(false);
    }
  };

  if (reported) {
    return (
      <div className="flex items-center gap-1.5 bg-green-500/10 border border-green-500/20 rounded-xl px-3 py-2 text-sm text-green-400">
        <CheckCircle size={14} /> Reported — Thank you
      </div>
    );
  }

  return (
    <button
      onClick={handleReport}
      disabled={loading}
      className="flex items-center gap-1.5 bg-red-500/10 hover:bg-red-500/20 border border-red-500/20 rounded-xl px-3 py-2 text-sm text-red-400 transition-all disabled:opacity-50"
    >
      <Flag size={14} />
      {loading ? "Reporting..." : "Report as Fraud"}
    </button>
  );
}
