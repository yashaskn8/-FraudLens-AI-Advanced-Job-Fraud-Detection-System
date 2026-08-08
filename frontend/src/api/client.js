import axios from "axios";

// Docker's nginx frontend proxies /api/ to the backend service. A relative
// default keeps browser requests on the frontend origin instead of exposing a
// container-only hostname such as http://backend:8000 to the browser.
const BASE_URL = import.meta.env.VITE_API_BASE_URL || "";

const api = axios.create({
  baseURL: BASE_URL,
  timeout: 60000,
  headers: { "Content-Type": "application/json" },
});

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("auth_token");
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

api.interceptors.response.use(
  (response) => response.data,
  (error) => {
    console.error("API Error:", error.response?.data || error.message);
    throw error;
  }
);

export const scanJob = (payload) => api.post("/api/v1/scan", payload);
export const getScan = (scanId) => api.get(`/api/v1/scan/${scanId}`);
export const getHistory = () => api.get("/api/v1/history");
export const reportJob = (scanId, reason) =>
  api.post("/api/v1/report", { scan_id: scanId, reason });
export const getAnalytics = () => api.get("/api/v1/analytics/dashboard");

export default api;
