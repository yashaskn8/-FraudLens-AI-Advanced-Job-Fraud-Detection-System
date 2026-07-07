import { useState, useEffect } from "react";
import { getAnalytics } from "../api/client";

export default function useAnalytics() {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const result = await getAnalytics();
        setData(result);
      } catch (err) {
        setError("Failed to load analytics data.");
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, []);

  return { data, loading, error };
}
