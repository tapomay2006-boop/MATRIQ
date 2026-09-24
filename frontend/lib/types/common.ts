/**
 * Standardized API Response and Health Check Types for SIH Platform.
 */

export interface ApiResponse<T = unknown> {
  success: boolean;
  data?: T;
  message?: string;
}

export interface ApiErrorDetail {
  code: string;
  message: string;
  details?: Record<string, unknown>;
}

export interface ApiErrorResponse {
  success: false;
  error: ApiErrorDetail;
}

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
  environment: string;
}

export interface ServiceDependencyStatus {
  status: "healthy" | "degraded" | "unavailable" | string;
  latency_ms?: number;
  message?: string;
}

export interface ServicesHealthStatus {
  status: "healthy" | "degraded" | "unhealthy" | string;
  service: string;
  version: string;
  environment: string;
  dependencies: Record<string, ServiceDependencyStatus>;
}

