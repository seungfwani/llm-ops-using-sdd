import axios, { AxiosInstance } from "axios";

// API base URL - use proxy in development, or env variable in production
const API_BASE = import.meta.env.VITE_API_BASE_URL || "/llm-ops/v1";

// Create axios instance with default config
export const apiClient: AxiosInstance = axios.create({
  baseURL: API_BASE,
  headers: {
    "Content-Type": "application/json",
  },
});

// Request interceptor to add auth headers
apiClient.interceptors.request.use(
  (config) => {
    // Get user info from localStorage or store
    const userId = localStorage.getItem("userId") || "test-user";
    const userRoles = localStorage.getItem("userRoles") || "llm-ops-user";

    // Add required headers
    config.headers["X-User-Id"] = userId;
    config.headers["X-User-Roles"] = userRoles;

    return config;
  },
  (error) => {
    return Promise.reject(error);
  }
);

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => {
    return response;
  },
  (error) => {
    // Handle common errors
    if (error.response?.status === 401) {
      console.error("Authentication failed. Please check your credentials.");
    } else if (error.response?.status === 403) {
      console.error("Access denied. You don't have permission to access this resource.");
    } else if (error.response?.status >= 500) {
      console.error("Server error. Please try again later.");
    }
    return Promise.reject(error);
  }
);

export default apiClient;

