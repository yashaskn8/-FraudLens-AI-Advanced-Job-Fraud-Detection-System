import { useState, useCallback } from "react";
import { scanJob, getScan } from "../api/client";

export default function useScan() {
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);

  const scan = useCallback(async (payload) => {
    setLoading(true);
    setError(null);
    try {
      const data = await scanJob(payload);
      setResult(data);
      return data;
    } catch (err) {
      setError(err.response?.data?.detail || "Scan failed. Please try again.");
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchScan = useCallback(async (scanId) => {
    setLoading(true);
    try {
      const data = await getScan(scanId);
      setResult(data);
      return data;
    } catch (err) {
      setError("Could not fetch scan results.");
      throw err;
    } finally {
      setLoading(false);
    }
  }, []);

  return { loading, result, error, scan, fetchScan };
}
