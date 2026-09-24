/**
 * Dedicated API Client for AI Service (Phase 1 Extraction & Vector Intelligence)
 * Communicates with backend/ai-service at http://localhost:8001/api/v1
 */

import {
  AiServiceHealth,
  ExtractionJobOut,
  SessionOut,
  SessionSummaryOut,
  StandardizedCheckResponse,
  StandardizedAddResponse,
  BatchOut,
  BatchDetail,
  RetrievalStatusOut,
  ExtractedRecordItem,
} from "@/lib/types/ai-extraction";
import { SearchResponse } from "@/lib/types/search";

const AI_BASE_URL =
  process.env.NEXT_PUBLIC_AI_SERVICE_URL || "http://localhost:8001";

class AiServiceError extends Error {
  public status: number;
  public details?: unknown;

  constructor(message: string, status: number, details?: unknown) {
    super(message);
    this.name = "AiServiceError";
    this.status = status;
    this.details = details;
  }
}

export const aiClient = {
  getBaseUrl: () => AI_BASE_URL,

  /**
   * Check liveness and configuration of the AI service.
   */
  checkHealth: async (): Promise<AiServiceHealth> => {
    try {
      let res = await fetch(`${AI_BASE_URL}/api/v1/health`, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) {
        // Fallback to root /health
        res = await fetch(`${AI_BASE_URL}/health`, {
          method: "GET",
          headers: { Accept: "application/json" },
          signal: AbortSignal.timeout(3000),
        });
      }
      if (!res.ok) {
        throw new AiServiceError(`Health check failed (${res.status})`, res.status);
      }
      return await res.json();
    } catch (err: unknown) {
      const error = err as Error;
      throw new AiServiceError(error?.message || "AI Service unavailable", 0);
    }
  },

  /**
   * Check extraction engine info (model, active LoRA weights, session count).
   */
  getExtractionInfo: async (): Promise<Record<string, unknown>> => {
    try {
      const res = await fetch(`${AI_BASE_URL}/api/v1/extract/info`, {
        method: "GET",
        headers: { Accept: "application/json" },
        signal: AbortSignal.timeout(3000),
      });
      if (!res.ok) throw new Error("Failed to fetch extraction info");
      return await res.json();
    } catch {
      return { enabled: false, service: "offline" };
    }
  },

  /**
   * Upload and trigger batch CSV/Excel attribute extraction.
   * If the server returns 202 (asynchronous job), this automatically polls
   * the job status until completed and returns the full SessionOut result.
   */
  uploadCsv: async (
    file: File,
    options: {
      textColumn?: string;
      maxRows?: number;
      wait?: number;
      onProgress?: (current: number, total: number, message: string) => void;
    } = {}
  ): Promise<SessionOut> => {
    const formData = new FormData();
    formData.append("file", file);

    if (options.textColumn) {
      formData.append("text_column", options.textColumn);
    }
    if (options.maxRows) {
      formData.append("max_rows", String(options.maxRows));
    }

    const waitParam = options.wait !== undefined ? `?wait=${options.wait}` : "?wait=5";

    const res = await fetch(`${AI_BASE_URL}/api/v1/extract/csv${waitParam}`, {
      method: "POST",
      body: formData,
    });

    if (!res.ok) {
      let errDetail = "CSV Extraction upload failed";
      try {
        const errorJson = await res.json();
        errDetail = errorJson?.detail || errDetail;
      } catch {
        // ignore non-json
      }
      throw new AiServiceError(errDetail, res.status);
    }

    const initial = await res.json();

    // If completed within inline wait window
    if (initial.records && Array.isArray(initial.records)) {
      return initial as SessionOut;
    }

    // If deferred as background job (HTTP 202)
    const jobId = initial.id || initial.job_id;
    if (!jobId) {
      throw new AiServiceError("No job ID received from extraction service", 500);
    }

    // Poll until complete
    const timeoutMs = 300000; // 5 minutes max for batch
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      await new Promise((r) => setTimeout(r, 1500));
      const jobRes = await fetch(`${AI_BASE_URL}/api/v1/jobs/${jobId}`, {
        headers: { Accept: "application/json" },
      });

      if (!jobRes.ok) continue;
      const job = await jobRes.json();

      if (options.onProgress && job.progress_total) {
        options.onProgress(
          job.progress_current || 0,
          job.progress_total || 0,
          job.progress_message || `Extracting row ${job.progress_current || 0}/${job.progress_total || 0}`
        );
      }

      if (job.terminal || job.status === "SUCCEEDED" || job.status === "FAILED" || job.status === "CANCELLED") {
        if (job.status === "SUCCEEDED" && job.result) {
          return job.result as SessionOut;
        }
        throw new AiServiceError(
          job.error || `Batch extraction ended with status: ${job.status}`,
          job.error_status || 500
        );
      }
    }

    throw new AiServiceError("Batch extraction timed out after 5 minutes.", 408);
  },

  /**
   * Single string interactive extraction.
   * If the model outruns the wait parameter, it polls the background job until complete.
   */
  extractSingleText: async (
    text: string,
    wait: number = 30
  ): Promise<{ session_id: string; record: ExtractedRecordItem }> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/extract/text?wait=${wait}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({ text }),
    });

    if (!res.ok) {
      let detail = "Single text extraction failed";
      try {
        const errJson = await res.json();
        detail = errJson?.detail || detail;
      } catch {
        // ignore
      }
      throw new AiServiceError(detail, res.status);
    }

    const initial = await res.json();

    // If completed inline
    if (initial.record) {
      return initial as { session_id: string; record: ExtractedRecordItem };
    }

    // If deferred as background job
    const jobId = initial.id || initial.job_id;
    if (!jobId) {
      throw new AiServiceError("No job ID received for text extraction", 500);
    }

    const timeoutMs = 120000; // 2 minutes
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      await new Promise((r) => setTimeout(r, 1200));
      const jobRes = await fetch(`${AI_BASE_URL}/api/v1/jobs/${jobId}`, {
        headers: { Accept: "application/json" },
      });

      if (!jobRes.ok) continue;
      const job = await jobRes.json();

      if (job.terminal || job.status === "SUCCEEDED" || job.status === "FAILED" || job.status === "CANCELLED") {
        if (job.status === "SUCCEEDED" && job.result) {
          return job.result as { session_id: string; record: ExtractedRecordItem };
        }
        throw new AiServiceError(
          job.error || `Text extraction ended with status: ${job.status}`,
          job.error_status || 500
        );
      }
    }

    throw new AiServiceError("Text extraction timed out.", 408);
  },

  /**
   * Poll progress of an extraction job.
   */
  pollJobStatus: async (jobId: string): Promise<ExtractionJobOut> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/jobs/${jobId}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw new AiServiceError(`Job ${jobId} query failed`, res.status);
    }

    return await res.json();
  },

  /**
   * List recent extraction sessions.
   */
  listSessions: async (limit: number = 20): Promise<SessionSummaryOut[]> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/extract/sessions?limit=${limit}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw new AiServiceError("Failed to fetch sessions", res.status);
    }

    return await res.json();
  },

  /**
   * Get full session records with predicted and current review states.
   */
  getSessionDetails: async (sessionId: string): Promise<SessionOut> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/extract/sessions/${sessionId}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw new AiServiceError(`Session ${sessionId} not found`, res.status);
    }

    return await res.json();
  },

  /**
   * Update one record in human-in-the-loop review.
   */
  updateRecord: async (
    sessionId: string,
    recordId: string,
    payload: Record<string, unknown>
  ): Promise<{ success: boolean; record: ExtractedRecordItem }> => {
    const res = await fetch(
      `${AI_BASE_URL}/api/v1/extract/records/${sessionId}/${recordId}`,
      {
        method: "PUT",
        headers: {
          "Content-Type": "application/json",
          Accept: "application/json",
        },
        body: JSON.stringify(payload),
      }
    );

    if (!res.ok) {
      throw new AiServiceError(`Record update failed`, res.status);
    }

    return await res.json();
  },

  /**
   * Trigger vector duplicate check against Qdrant/Postgres master (POST /api/v1/standardized/check).
   * Accepts session_id string or full check payload. Handles background job polling if deferred.
   */
  checkStandardized: async (
    input: string | {
      session_id?: string;
      rows?: Record<string, unknown>[];
      records?: Record<string, unknown>[];
      default_company?: string;
      requested_by?: string;
    }
  ): Promise<StandardizedCheckResponse> => {
    const payload = typeof input === "string" ? { session_id: input } : input;
    const res = await fetch(`${AI_BASE_URL}/api/v1/standardized/check?wait=30`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let detail = "Standardized duplicate check failed";
      try {
        const errJson = await res.json();
        detail = errJson?.detail || detail;
      } catch {
        // ignore
      }
      throw new AiServiceError(detail, res.status);
    }

    const data = await res.json();

    // If completed inline
    if (data.batch_id && Array.isArray(data.rows)) {
      return {
        ...data,
        total_checked: data.total_rows,
        new_count: data.new_rows,
        duplicate_count: data.existing_rows + data.duplicate_rows_in_batch,
      };
    }

    // If deferred as background job (HTTP 202)
    const jobId = data.id || data.job_id;
    if (!jobId) {
      throw new AiServiceError("No job ID received for standardized check", 500);
    }

    const timeoutMs = 120000;
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      await new Promise((r) => setTimeout(r, 1200));
      const jobRes = await fetch(`${AI_BASE_URL}/api/v1/jobs/${jobId}`, {
        headers: { Accept: "application/json" },
      });

      if (!jobRes.ok) continue;
      const job = await jobRes.json();

      if (job.terminal || job.status === "SUCCEEDED" || job.status === "FAILED" || job.status === "CANCELLED") {
        if (job.status === "SUCCEEDED" && job.result) {
          const result = job.result;
          return {
            ...result,
            total_checked: result.total_rows,
            new_count: result.new_rows,
            duplicate_count: result.existing_rows + result.duplicate_rows_in_batch,
          };
        }
        throw new AiServiceError(
          job.error || `Standardized check ended with status: ${job.status}`,
          job.error_status || 500
        );
      }
    }

    throw new AiServiceError("Standardized check timed out.", 408);
  },

  /**
   * Add verified new material rows to the vector database and master catalog (POST /api/v1/standardized/add).
   * Atomically writes to PostgreSQL and upserts Qdrant vectors.
   */
  addStandardized: async (
    input: string | {
      batch_id?: string;
      rows?: Record<string, unknown>[];
      records?: Record<string, unknown>[];
      default_company?: string;
      requested_by?: string;
    }
  ): Promise<StandardizedAddResponse> => {
    const payload = typeof input === "string" ? { batch_id: input } : input;
    const res = await fetch(`${AI_BASE_URL}/api/v1/standardized/add?wait=30`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify(payload),
    });

    if (!res.ok) {
      let detail = "Adding standardized material failed";
      try {
        const errJson = await res.json();
        detail = errJson?.detail || detail;
      } catch {
        // ignore
      }
      throw new AiServiceError(detail, res.status);
    }

    const data = await res.json();

    // If completed inline
    if (data.batch_id && (data.added !== undefined || data.materials)) {
      return data as StandardizedAddResponse;
    }

    // If deferred as background job (HTTP 202)
    const jobId = data.id || data.job_id;
    if (!jobId) {
      throw new AiServiceError("No job ID received for standardized add", 500);
    }

    const timeoutMs = 120000;
    const startTime = Date.now();

    while (Date.now() - startTime < timeoutMs) {
      await new Promise((r) => setTimeout(r, 1200));
      const jobRes = await fetch(`${AI_BASE_URL}/api/v1/jobs/${jobId}`, {
        headers: { Accept: "application/json" },
      });

      if (!jobRes.ok) continue;
      const job = await jobRes.json();

      if (job.terminal || job.status === "SUCCEEDED" || job.status === "FAILED" || job.status === "CANCELLED") {
        if (job.status === "SUCCEEDED" && job.result) {
          return job.result as StandardizedAddResponse;
        }
        throw new AiServiceError(
          job.error || `Standardized add ended with status: ${job.status}`,
          job.error_status || 500
        );
      }
    }

    throw new AiServiceError("Standardized add timed out.", 408);
  },

  /**
   * List recent standardization batches (GET /api/v1/standardized/batches).
   */
  listStandardizedBatches: async (limit: number = 50): Promise<BatchOut[]> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/standardized/batches?limit=${limit}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw new AiServiceError("Failed to fetch standardized batches", res.status);
    }

    return await res.json();
  },

  /**
   * Fetch single batch with all row verdicts and staged new materials (GET /api/v1/standardized/batches/{batch_id}).
   */
  getStandardizedBatch: async (batchId: string): Promise<BatchDetail> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/standardized/batches/${batchId}`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw new AiServiceError(`Batch ${batchId} not found`, res.status);
    }

    return await res.json();
  },

  /**
   * Get vector index coverage and store connectivity (GET /api/v1/retrieval/status).
   */
  getIndexStatus: async (): Promise<RetrievalStatusOut> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/retrieval/status`, {
      method: "GET",
      headers: { Accept: "application/json" },
    });

    if (!res.ok) {
      throw new AiServiceError("Failed to fetch retrieval status", res.status);
    }

    return await res.json();
  },

  /**
   * Run semantic vector retrieval and Siamese neural reranker search (POST /search).
   */
  search: async (
    query: string,
    topK: number = 20,
    finalK: number = 5
  ): Promise<SearchResponse> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/search`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Accept: "application/json",
      },
      body: JSON.stringify({
        query: query.trim(),
        top_k: topK,
        final_k: finalK,
      }),
    });

    if (!res.ok) {
      let detail = "AI Siamese search failed";
      try {
        const errJson = await res.json();
        detail = errJson?.detail || detail;
      } catch {
        // ignore
      }
      throw new AiServiceError(detail, res.status);
    }

    return await res.json();
  },

  /**
   * Get search and reranker model operational status.
   */
  getSearchModelInfo: async (): Promise<Record<string, unknown>> => {
    try {
      const res = await fetch(`${AI_BASE_URL}/api/v1/search/model/info`, {
        headers: { Accept: "application/json" },
      });
      if (!res.ok) throw new Error("Failed to fetch model info");
      return await res.json();
    } catch {
      return { degraded: true, error: "AI service offline" };
    }
  },

  /**
   * Fetch standardized materials from AI service master catalog (GET /api/v1/materials).
   */
  getMaterials: async (params?: {
    cpse?: string;
    category?: string;
    query?: string;
    limit?: number;
    offset?: number;
  }): Promise<{ items: any[]; total: number; unindexed: number; has_more: boolean }> => {
    const queryParams = new URLSearchParams();
    if (params?.cpse) queryParams.set("cpse", params.cpse);
    if (params?.category) queryParams.set("category", params.category);
    if (params?.query) queryParams.set("query", params.query);
    if (params?.limit) queryParams.set("limit", params.limit.toString());
    if (params?.offset) queryParams.set("offset", params.offset.toString());

    const url = `${AI_BASE_URL}/api/v1/materials?${queryParams.toString()}`;
    const res = await fetch(url, { headers: { Accept: "application/json" } });
    if (!res.ok) throw new Error("Failed to fetch materials from AI service");
    return await res.json();
  },

  /**
   * Fetch extraction sessions for ingestion/review analytics (GET /api/v1/extract/sessions).
   */
  getSessions: async (): Promise<any[]> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/extract/sessions`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error("Failed to fetch extraction sessions");
    return await res.json();
  },

  /**
   * Fetch background AI jobs (GET /api/v1/jobs).
   */
  getJobs: async (limit: number = 20): Promise<any[]> => {
    const res = await fetch(`${AI_BASE_URL}/api/v1/jobs?limit=${limit}`, {
      headers: { Accept: "application/json" },
    });
    if (!res.ok) throw new Error("Failed to fetch jobs");
    return await res.json();
  },
};

export default aiClient;

