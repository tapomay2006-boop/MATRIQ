/**
 * Centralized API Client for SIH 2026 Unified Material Intelligence Platform.
 * Communicates with backend/api-service via /api/v1/*.
 */

import type { ApiResponse, HealthStatus, ServicesHealthStatus } from "@/lib/types/common";
import type {
  MaterialRecord,
  PaginatedMaterialsResponse,
  MaterialQualityStats,
  MaterialIngestionResponse,
} from "@/lib/types/material";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export class ApiClientError extends Error {
  public status: number;
  public code?: string;
  public details?: Record<string, unknown>;

  constructor(message: string, status: number, code?: string, details?: Record<string, unknown>) {
    super(message);
    this.name = "ApiClientError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

interface RequestOptions extends Omit<RequestInit, "body"> {
  body?: unknown;
  params?: Record<string, string | number | boolean | undefined>;
}

async function request<T>(endpoint: string, options: RequestOptions = {}): Promise<T> {
  const { body, params, headers, ...customConfig } = options;

  let url = `${API_BASE_URL.replace(/\/$/, "")}/${endpoint.replace(/^\//, "")}`;

  if (params) {
    const queryParams = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
      if (value !== undefined) {
        queryParams.append(key, String(value));
      }
    });
    const queryString = queryParams.toString();
    if (queryString) {
      url += (url.includes("?") ? "&" : "?") + queryString;
    }
  }

  const reqHeaders: Record<string, string> = {
    Accept: "application/json",
    ...(body ? { "Content-Type": "application/json" } : {}),
    ...(headers as Record<string, string>),
  };

  const config: RequestInit = {
    ...customConfig,
    headers: reqHeaders,
    body: body ? JSON.stringify(body) : undefined,
  };

  try {
    const response = await fetch(url, config);

    if (!response.ok) {
      let errorData: { error?: { message?: string; code?: string; details?: Record<string, unknown> } } = {};
      try {
        errorData = await response.json();
      } catch {
        // Response was not JSON
      }

      const errorMessage =
        errorData?.error?.message ||
        `HTTP request failed with status ${response.status} (${response.statusText})`;

      throw new ApiClientError(
        errorMessage,
        response.status,
        errorData?.error?.code,
        errorData?.error?.details
      );
    }

    // Handle 204 No Content
    if (response.status === 204) {
      return {} as T;
    }

    return (await response.json()) as T;
  } catch (error) {
    if (error instanceof ApiClientError) {
      throw error;
    }
    throw new ApiClientError(
      (error as Error)?.message || "Network communication error with API service",
      0,
      "NETWORK_ERROR"
    );
  }
}

export const apiClient = {
  get: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: "GET" }),

  post: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: "POST", body }),

  put: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: "PUT", body }),

  patch: <T>(endpoint: string, body?: unknown, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: "PATCH", body }),

  delete: <T>(endpoint: string, options?: RequestOptions) =>
    request<T>(endpoint, { ...options, method: "DELETE" }),

  // ─────────────────────────────────────────────
  // Service Health Helpers
  // ─────────────────────────────────────────────
  checkLiveness: async (): Promise<HealthStatus> => {
    return request<HealthStatus>("api/v1/health");
  },

  checkServicesHealth: async (): Promise<ServicesHealthStatus> => {
    return request<ServicesHealthStatus>("api/v1/health/services");
  },

  // ─────────────────────────────────────────────
  // Materials Domain Endpoints
  // ─────────────────────────────────────────────
  materials: {
    list: async (params?: {
      organization?: string;
      national_id?: string;
      status?: string;
      search?: string;
      page?: number;
      page_size?: number;
      limit?: number;
      offset?: number;
    }): Promise<PaginatedMaterialsResponse> => {
      return request<PaginatedMaterialsResponse>("api/v1/materials", {
        method: "GET",
        params,
      });
    },

    getById: async (materialId: string): Promise<MaterialRecord> => {
      return request<MaterialRecord>(`api/v1/materials/${materialId}`, {
        method: "GET",
      });
    },

    update: async (
      materialId: string,
      data: Partial<{
        description: string;
        item_name: string;
        part_number: string;
        manufacturer: string;
        uom: string;
        category: string;
        specification: string;
        equipment_compatibility: string;
        material_type: string;
      }>
    ): Promise<MaterialRecord> => {
      return request<MaterialRecord>(`api/v1/materials/${materialId}`, {
        method: "PUT",
        body: data,
      });
    },

    getQuality: async (): Promise<MaterialQualityStats> => {
      return request<MaterialQualityStats>("api/v1/materials/quality", {
        method: "GET",
      });
    },

    getOrganizations: async (): Promise<string[]> => {
      return request<string[]>("api/v1/materials/organizations", {
        method: "GET",
      });
    },

    ingest: async (
      file: File,
      defaultOrganization?: string
    ): Promise<MaterialIngestionResponse> => {
      const formData = new FormData();
      formData.append("file", file);
      if (defaultOrganization && defaultOrganization.trim()) {
        formData.append("default_organization", defaultOrganization.trim());
      }

      return request<MaterialIngestionResponse>("api/v1/materials/ingest", {
        method: "POST",
        body: formData,
      });
    },
  },
};

export default apiClient;
