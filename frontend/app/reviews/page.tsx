"use client";

import React, { useState, useEffect, useMemo, Suspense } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  CheckSquare,
  Sparkles,
  Clock,
  ArrowRight,
  Database,
  ShieldCheck,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Search,
  FileSpreadsheet,
  Plus,
  Check,
  ExternalLink,
  ChevronRight,
  Layers,
  FileText,
} from "lucide-react";
import CpseLayout from "@/components/layout/CpseLayout";
import NationalLayout from "@/components/layout/NationalLayout";
import { useSession } from "next-auth/react";
import { toast } from "sonner";
import { aiClient } from "@/lib/api/ai-client";
import {
  BatchOut,
  BatchDetail,
  SessionSummaryOut,
  StandardizedAddResponse,
  RetrievalStatusOut,
  CheckedRowOut,
} from "@/lib/types/ai-extraction";

function ReviewsContent() {
  const { data: session } = useSession();
  const isCpseAdmin = session?.user?.role === "cpse_admin";
  const searchParams = useSearchParams();
  const initialSessionId = searchParams.get("sessionId");
  const initialBatchId = searchParams.get("batchId");

  // Live Backend Data
  const [batches, setBatches] = useState<BatchOut[]>([]);
  const [sessions, setSessions] = useState<SessionSummaryOut[]>([]);
  const [retrievalStatus, setRetrievalStatus] = useState<RetrievalStatusOut | null>(null);
  const [isAiOnline, setIsAiOnline] = useState<boolean | null>(null);

  // Loading States
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isCheckingSessionId, setIsCheckingSessionId] = useState<string | null>(null);
  const [isAddingBatchId, setIsAddingBatchId] = useState<string | null>(null);

  // Tab: "pending" (CHECKED batches), "sessions" (raw catalogs), "approved" (ADDED batches)
  const [activeTab, setActiveTab] = useState<"pending" | "sessions" | "approved">(
    initialSessionId ? "sessions" : "pending"
  );

  // Selected Batch for Inspection
  const [selectedBatchId, setSelectedBatchId] = useState<string | null>(initialBatchId);
  const [selectedBatch, setSelectedBatch] = useState<BatchDetail | null>(null);
  const [isLoadingBatchDetail, setIsLoadingBatchDetail] = useState(false);

  // Recent Action Confirmation
  const [recentAddResult, setRecentAddResult] = useState<StandardizedAddResponse | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  // Load all live data on mount
  useEffect(() => {
    loadAllData();
  }, []);

  // Handle URL query parameters
  useEffect(() => {
    if (initialBatchId) {
      setSelectedBatchId(initialBatchId);
      loadBatchDetail(initialBatchId);
    }
  }, [initialBatchId]);

  const loadAllData = async (showToast = false) => {
    setIsRefreshing(true);
    try {
      const [healthRes, batchesRes, sessionsRes, indexRes] = await Promise.allSettled([
        aiClient.checkHealth(),
        aiClient.listStandardizedBatches(50),
        aiClient.listSessions(50),
        aiClient.getIndexStatus(),
      ]);

      if (healthRes.status === "fulfilled") {
        setIsAiOnline(healthRes.value.status === "ok" || healthRes.value.status === "healthy");
      } else {
        setIsAiOnline(false);
      }

      let loadedBatches: BatchOut[] = [];
      if (batchesRes.status === "fulfilled") {
        loadedBatches = batchesRes.value;
        setBatches(loadedBatches);
      } else {
        setBatches([]);
      }

      if (sessionsRes.status === "fulfilled") {
        setSessions(sessionsRes.value);
      } else {
        setSessions([]);
      }

      if (indexRes.status === "fulfilled") {
        setRetrievalStatus(indexRes.value);
      }

      // Auto-select first pending batch if none selected
      if (!selectedBatchId && loadedBatches.length > 0) {
        const firstPending = loadedBatches.find((b) => b.status === "CHECKED") || loadedBatches[0];
        if (firstPending) {
          setSelectedBatchId(firstPending.id);
          loadBatchDetail(firstPending.id);
        }
      }

      if (showToast) {
        toast.success("Verification queue updated");
      }
    } catch {
      toast.error("Unable to reach verification service");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  };

  const loadBatchDetail = async (batchId: string) => {
    setIsLoadingBatchDetail(true);
    try {
      const detail = await aiClient.getStandardizedBatch(batchId);
      setSelectedBatch(detail);
      setSelectedBatchId(batchId);
    } catch {
      toast.error("Could not load batch details");
    } finally {
      setIsLoadingBatchDetail(false);
    }
  };

  /**
   * STEP 1: Run Vector Duplicate Check on a Session
   */
  const handleRunStandardizedCheck = async (sessionId: string) => {
    setIsCheckingSessionId(sessionId);
    setRecentAddResult(null);

    try {
      toast.info("Checking catalog for duplicates...", {
        description: "Scanning existing master database to isolate new materials.",
      });

      const res = await aiClient.checkStandardized({
        session_id: sessionId,
        requested_by: "reviewer@cpse.gov.in",
      });

      toast.success("Duplicate check complete", {
        description: `Found ${res.new_rows} new materials and flagged ${res.existing_rows + res.duplicate_rows_in_batch} existing items.`,
      });

      await loadAllData();
      if (res.batch_id) {
        setSelectedBatchId(res.batch_id);
        await loadBatchDetail(res.batch_id);
        setActiveTab("pending");
      }
    } catch (err) {
      const error = err as Error;
      toast.error("Duplicate check failed", {
        description: error?.message || "Please ensure the AI service is online.",
      });
    } finally {
      setIsCheckingSessionId(null);
    }
  };

  /**
   * STEP 2: Approve & Ingest Verified Materials into Master
   */
  const handleRunStandardizedAdd = async (batchId: string) => {
    setIsAddingBatchId(batchId);
    setRecentAddResult(null);

    try {
      toast.info("Ingesting approved materials...", {
        description: "Writing records and generating vector embeddings.",
      });

      const res = await aiClient.addStandardized({
        batch_id: batchId,
        requested_by: "reviewer@cpse.gov.in",
      });

      setRecentAddResult(res);

      toast.success("Materials successfully ingested!", {
        description: `${res.added} items added to National Master with issued National IDs.`,
      });

      await loadAllData();
      await loadBatchDetail(batchId);
    } catch (err) {
      const error = err as Error;
      toast.error("Approval failed", {
        description: error?.message || "Could not persist records.",
      });
    } finally {
      setIsAddingBatchId(null);
    }
  };

  // Aggregated KPIs
  const pendingBatches = useMemo(() => batches.filter((b) => b.status === "CHECKED"), [batches]);
  const approvedBatches = useMemo(() => batches.filter((b) => b.status === "ADDED"), [batches]);

  const kpiStats = useMemo(() => {
    const totalPendingItems = pendingBatches.reduce((acc, b) => acc + (b.new_rows || 0), 0);
    const totalApprovedItems =
      retrievalStatus?.indexed !== undefined
        ? retrievalStatus.indexed
        : approvedBatches.reduce((acc, b) => acc + (b.added_rows || 0), 0);

    const totalDuplicatesPrevented = batches.reduce(
      (acc, b) => acc + ((b.existing_rows || 0) + (b.duplicate_rows || 0)),
      0
    );

    return {
      pendingBatchesCount: pendingBatches.length,
      pendingItemsCount: totalPendingItems,
      approvedItemsCount: totalApprovedItems,
      duplicatesCount: totalDuplicatesPrevented,
    };
  }, [batches, pendingBatches, approvedBatches, retrievalStatus]);

  // Filtered Rows inside the selected batch
  const filteredBatchRows = useMemo(() => {
    if (!selectedBatch?.rows) return [];
    if (!searchQuery.trim()) return selectedBatch.rows;
    const q = searchQuery.toLowerCase().trim();
    return selectedBatch.rows.filter(
      (r) =>
        r.description.toLowerCase().includes(q) ||
        (r.category || "").toLowerCase().includes(q) ||
        (r.material_id || "").toLowerCase().includes(q) ||
        (r.matched_material_id || "").toLowerCase().includes(q)
    );
  }, [selectedBatch, searchQuery]);

  if (isCpseAdmin) {
    return (
      <CpseLayout>
        <main className="flex-1 flex flex-col items-center justify-center p-8 max-w-xl mx-auto text-center space-y-4 min-h-[60vh]">
          <div className="w-14 h-14 rounded-2xl bg-[#A8DD73]/10 border border-[#A8DD73]/25 flex items-center justify-center text-[#A8DD73]">
            <CheckSquare className="w-7 h-7" />
          </div>
          <h2 className="text-xl font-bold text-white">Harmonization Review Restricted to National Authority</h2>
          <p className="text-xs text-zinc-400 leading-relaxed max-w-md">
            Harmonization review and national master catalog standardization are managed by National Authority officers.
            CPSE enterprise admins manage their own material catalogs and upload new batch submissions.
          </p>
          <div className="flex items-center justify-center gap-3 pt-2">
            <Link
              href="/dashboard_cpse"
              className="px-4 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-xs font-semibold text-white transition-colors no-underline"
            >
              CPSE Dashboard
            </Link>
            <Link
              href="/materials"
              className="px-4 py-2 rounded-xl bg-[#A8DD73] hover:bg-[#bbf082] text-xs font-semibold text-black transition-all shadow-md shadow-[#A8DD73]/20 no-underline"
            >
              View Materials
            </Link>
          </div>
        </main>
      </CpseLayout>
    );
  }

  return (
    <NationalLayout>
      <main className="flex-1 flex flex-col px-4 sm:px-8 lg:px-10 py-6 sm:py-8 max-w-[1400px] w-full space-y-6 mx-auto">
        {/* Clean Header */}
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/5">
          <div>
            <div className="inline-flex items-center gap-2 mb-2 px-3 py-1 rounded-full bg-[#A8DD73]/10 border border-[#A8DD73]/25">
              <CheckSquare className="w-3.5 h-3.5 text-[#A8DD73]" />
              <span className="text-xs font-medium text-[#A8DD73]">
                Harmonization · Material Verification Queue
              </span>
            </div>
            <h1
              className="text-3xl sm:text-4xl font-normal tracking-tight"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              <span className="text-white">Reviewer </span>
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Verification Queue
              </span>
            </h1>
            <p className="text-sm text-zinc-400 mt-1 max-w-2xl">
              Verify extracted catalog items, resolve duplicate flags, and approve new materials into the National Master.
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <div className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/[0.03] border border-white/10 text-xs">
              <span
                className={`w-2 h-2 rounded-full ${
                  isAiOnline ? "bg-emerald-400 animate-pulse shadow-[0_0_8px_#10B981]" : "bg-red-400"
                }`}
              />
              <span className="text-zinc-300 font-mono text-[11px] font-medium">
                {isAiOnline ? "AI Vector Engine Ready" : "AI Service Offline"}
              </span>
            </div>

            <button
              onClick={() => loadAllData(true)}
              disabled={isRefreshing}
              className="inline-flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 hover:text-white border border-white/10 text-xs font-medium transition-all cursor-pointer"
              title="Refresh queue data"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${isRefreshing ? "animate-spin text-[#A8DD73]" : ""}`} />
              <span>Refresh</span>
            </button>
          </div>
        </div>

        {/* Success Alert Banner on Ingest */}
        {recentAddResult && (
          <div className="p-4 rounded-2xl bg-emerald-950/40 border border-emerald-500/40 text-emerald-200 flex items-center justify-between gap-4 animate-in fade-in duration-300">
            <div className="flex items-center gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-400 shrink-0" />
              <div>
                <p className="text-sm font-semibold text-white">
                  Successfully ingested {recentAddResult.added} materials into National Master!
                </p>
                {recentAddResult.national_ids.length > 0 && (
                  <p className="text-xs text-emerald-300 mt-0.5 font-mono">
                    Issued IDs: {recentAddResult.national_ids.slice(0, 3).join(", ")}
                    {recentAddResult.national_ids.length > 3 ? ` +${recentAddResult.national_ids.length - 3} more` : ""}
                  </p>
                )}
              </div>
            </div>
            <button
              onClick={() => setRecentAddResult(null)}
              className="text-xs text-emerald-300 hover:text-white px-3 py-1.5 rounded-lg bg-emerald-500/20 hover:bg-emerald-500/30 transition-all shrink-0 cursor-pointer"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Clean Segmented Tab Control */}
        <div className="flex items-center gap-2 p-1.5 rounded-2xl bg-[#121013] border border-white/10 w-fit">
          <button
            onClick={() => setActiveTab("pending")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === "pending"
                ? "bg-[#A8DD73] text-black shadow-md shadow-[#A8DD73]/20"
                : "text-zinc-400 hover:text-white hover:bg-white/[0.04]"
            }`}
          >
            <Clock className="w-3.5 h-3.5" />
            <span>Ready for Ingestion</span>
            <span
              className={`px-1.5 py-0.5 rounded-md text-[10px] font-mono font-bold ${
                activeTab === "pending" ? "bg-black/20 text-black" : "bg-white/10 text-zinc-300"
              }`}
            >
              {pendingBatches.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("sessions")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === "sessions"
                ? "bg-[#A8DD73] text-black shadow-md shadow-[#A8DD73]/20"
                : "text-zinc-400 hover:text-white hover:bg-white/[0.04]"
            }`}
          >
            <FileSpreadsheet className="w-3.5 h-3.5" />
            <span>Uploaded Catalogs</span>
            <span
              className={`px-1.5 py-0.5 rounded-md text-[10px] font-mono font-bold ${
                activeTab === "sessions" ? "bg-black/20 text-black" : "bg-white/10 text-zinc-300"
              }`}
            >
              {sessions.length}
            </span>
          </button>

          <button
            onClick={() => setActiveTab("approved")}
            className={`px-4 py-2 rounded-xl text-xs font-semibold transition-all flex items-center gap-2 cursor-pointer ${
              activeTab === "approved"
                ? "bg-[#A8DD73] text-black shadow-md shadow-[#A8DD73]/20"
                : "text-zinc-400 hover:text-white hover:bg-white/[0.04]"
            }`}
          >
            <CheckCircle2 className="w-3.5 h-3.5" />
            <span>Approved Batches</span>
            <span
              className={`px-1.5 py-0.5 rounded-md text-[10px] font-mono font-bold ${
                activeTab === "approved" ? "bg-black/20 text-black" : "bg-white/10 text-zinc-300"
              }`}
            >
              {approvedBatches.length}
            </span>
          </button>
        </div>

        {/* TAB 1: PENDING APPROVAL (POST /standardized/add) */}
        {activeTab === "pending" && (
          <div className="space-y-6">
            {pendingBatches.length === 0 ? (
              <div className="p-12 rounded-2xl bg-[#121013]/90 border border-white/10 text-center space-y-3">
                <CheckCircle2 className="w-9 h-9 text-[#A8DD73] mx-auto opacity-70" />
                <h3 className="text-base font-semibold text-white">Queue is clear!</h3>
                <p className="text-xs text-zinc-400 max-w-md mx-auto">
                  All checked items have been processed. Switch to &quot;Uploaded Catalogs&quot; to scan new inventory files for duplicates.
                </p>
                <button
                  onClick={() => setActiveTab("sessions")}
                  className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-white/[0.05] hover:bg-white/[0.1] text-zinc-200 text-xs font-medium border border-white/10 transition-all mt-2"
                >
                  <span>View Uploaded Catalogs</span>
                  <ArrowRight className="w-3.5 h-3.5" />
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
                {/* Batches Selector on Left */}
                <div className="lg:col-span-4 space-y-3">
                  <span className="text-xs font-semibold text-zinc-400 uppercase tracking-wider block px-1">
                    Select Batch to Review
                  </span>
                  <div className="space-y-2.5">
                    {pendingBatches.map((batch) => {
                      const isSelected = selectedBatchId === batch.id;
                      return (
                        <div
                          key={batch.id}
                          onClick={() => loadBatchDetail(batch.id)}
                          className={`p-4 rounded-xl border transition-all cursor-pointer ${
                            isSelected
                              ? "bg-[#A8DD73]/10 border-[#A8DD73]/50 shadow-md shadow-[#A8DD73]/10"
                              : "bg-[#121013]/90 border-white/10 hover:border-white/20"
                          }`}
                        >
                          <div className="flex items-center justify-between">
                            <span className="text-xs font-mono font-bold text-white">
                              Batch {batch.id.slice(0, 8)}
                            </span>
                            <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-amber-400/10 border border-amber-400/30 text-amber-400">
                              Ready to Ingest
                            </span>
                          </div>

                          <div className="flex items-center gap-4 mt-3 text-xs">
                            <div>
                              <span className="text-zinc-500 text-[11px] block">New Items</span>
                              <span className="font-semibold text-emerald-400 font-mono">
                                +{batch.new_rows}
                              </span>
                            </div>
                            <div>
                              <span className="text-zinc-500 text-[11px] block">Duplicates</span>
                              <span className="font-semibold text-zinc-400 font-mono">
                                {batch.existing_rows + batch.duplicate_rows}
                              </span>
                            </div>
                            <div>
                              <span className="text-zinc-500 text-[11px] block">Total</span>
                              <span className="font-semibold text-zinc-300 font-mono">
                                {batch.total_rows}
                              </span>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Batch Inspection Panel on Right */}
                <div className="lg:col-span-8">
                  {selectedBatch ? (
                    <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 space-y-5">
                      {/* Top Action Bar */}
                      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pb-4 border-b border-white/10">
                        <div>
                          <div className="flex items-center gap-2">
                            <h3 className="text-base font-semibold text-white">
                              Batch Inspection
                            </h3>
                            <span className="text-xs font-mono bg-white/10 px-2 py-0.5 rounded text-zinc-300">
                              {selectedBatch.id.slice(0, 8)}
                            </span>
                          </div>
                          <p className="text-xs text-zinc-400 mt-0.5">
                            {selectedBatch.new_rows} new materials will be added to the National Master.
                          </p>
                        </div>

                        <button
                          onClick={() => handleRunStandardizedAdd(selectedBatch.id)}
                          disabled={isAddingBatchId === selectedBatch.id || selectedBatch.new_rows === 0}
                          className="inline-flex items-center gap-2 px-5 py-2.5 rounded-xl bg-[#A8DD73] hover:bg-[#bbf082] text-black font-bold text-xs shadow-lg shadow-[#A8DD73]/25 transition-all shrink-0 disabled:opacity-50 disabled:cursor-not-allowed"
                        >
                          {isAddingBatchId === selectedBatch.id ? (
                            <>
                              <RefreshCw className="w-4 h-4 animate-spin" />
                              <span>Ingesting Materials...</span>
                            </>
                          ) : (
                            <>
                              <Check className="w-4 h-4" />
                              <span>Approve &amp; Ingest ({selectedBatch.new_rows} Items)</span>
                            </>
                          )}
                        </button>
                      </div>

                      {/* Search in Batch */}
                      <div className="flex items-center justify-between gap-3">
                        <div className="relative w-full max-w-sm">
                          <Search className="w-3.5 h-3.5 text-zinc-500 absolute left-3 top-1/2 -translate-y-1/2" />
                          <input
                            type="text"
                            placeholder="Filter items by name, category..."
                            value={searchQuery}
                            onChange={(e) => setSearchQuery(e.target.value)}
                            className="w-full pl-8 pr-3 py-1.5 rounded-xl bg-white/[0.04] border border-white/10 text-xs text-white placeholder:text-zinc-500 focus:outline-none focus:border-[#A8DD73]/50 transition-all"
                          />
                        </div>
                        <span className="text-xs text-zinc-400 shrink-0">
                          Showing {filteredBatchRows.length} items
                        </span>
                      </div>

                      {/* Clean Review Table */}
                      <div className="border border-white/10 rounded-xl overflow-hidden overflow-x-auto max-h-[460px] overflow-y-auto no-scrollbar">
                        <table className="w-full text-left text-xs border-collapse">
                          <thead className="bg-white/[0.04] text-zinc-400 text-[11px] sticky top-0 border-b border-white/10 backdrop-blur-md">
                            <tr>
                              <th className="py-2.5 px-3 font-semibold">#</th>
                              <th className="py-2.5 px-3 font-semibold">Material Description</th>
                              <th className="py-2.5 px-3 font-semibold">Category</th>
                              <th className="py-2.5 px-3 font-semibold">Status</th>
                              <th className="py-2.5 px-3 font-semibold">Notes / Match</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-white/5">
                            {filteredBatchRows.map((row) => {
                              const isNew = row.status === "NEW";
                              const isDup = row.status === "ALREADY_EXISTS" || row.status === "DUPLICATE_IN_BATCH";

                              return (
                                <tr key={row.row_number} className="hover:bg-white/[0.02] transition-colors">
                                  <td className="py-2.5 px-3 font-mono text-zinc-500">
                                    {row.row_number}
                                  </td>
                                  <td className="py-2.5 px-3 font-medium text-white max-w-xs">
                                    <div className="truncate">{row.description}</div>
                                    {row.material_id && (
                                      <span className="text-[10px] font-mono text-zinc-400">
                                        {row.material_id}
                                      </span>
                                    )}
                                  </td>
                                  <td className="py-2.5 px-3">
                                    <span className="px-2 py-0.5 rounded-md bg-white/[0.05] text-[10px] font-medium text-zinc-300">
                                      {row.category || "UNCLASSIFIED"}
                                    </span>
                                  </td>
                                  <td className="py-2.5 px-3">
                                    <span
                                      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[10px] font-bold tracking-wider uppercase border ${
                                        isNew
                                          ? "bg-emerald-400/10 border-emerald-400/30 text-emerald-400"
                                          : isDup
                                          ? "bg-amber-400/10 border-amber-400/30 text-amber-400"
                                          : "bg-red-400/10 border-red-400/30 text-red-400"
                                      }`}
                                    >
                                      {isNew ? "New Material" : isDup ? "Existing Duplicate" : row.status}
                                    </span>
                                  </td>
                                  <td className="py-2.5 px-3 text-zinc-400 max-w-xs truncate">
                                    {row.matched_material_id ? (
                                      <span className="text-[11px] text-amber-300/90 font-mono">
                                        Matches {row.matched_material_id}
                                      </span>
                                    ) : (
                                      <span className="text-[11px] text-zinc-400">
                                        {row.reason || "Ready to ingest"}
                                      </span>
                                    )}
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </div>
                    </div>
                  ) : (
                    <div className="p-12 rounded-2xl bg-[#121013]/90 border border-white/10 text-center text-zinc-400 text-xs">
                      Select a batch from the left to view materials.
                    </div>
                  )}
                </div>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: UPLOADED CATALOGS (POST /standardized/check) */}
        {activeTab === "sessions" && (
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 space-y-4">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pb-3 border-b border-white/10">
              <div>
                <h3 className="text-sm font-semibold text-white">
                  Uploaded Inventory Catalogs
                </h3>
                <p className="text-xs text-zinc-400 mt-0.5">
                  Scan any uploaded file for duplicate records before adding to the National Master.
                </p>
              </div>
            </div>

            {sessions.length === 0 ? (
              <div className="py-12 text-center space-y-2">
                <FileSpreadsheet className="w-8 h-8 text-zinc-600 mx-auto" />
                <p className="text-xs text-zinc-400">No uploaded catalogs found.</p>
              </div>
            ) : (
              <div className="divide-y divide-white/5 border border-white/10 rounded-xl overflow-hidden">
                {sessions.map((sess) => {
                  const isChecking = isCheckingSessionId === sess.session_id;

                  return (
                    <div
                      key={sess.session_id}
                      className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-white/[0.02] transition-colors"
                    >
                      <div className="space-y-1">
                        <div className="flex items-center gap-2">
                          <span className="text-xs font-semibold text-white">
                            {sess.original_filename || "Catalog Extracted Text"}
                          </span>
                          <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-white/[0.05] border border-white/10 text-zinc-300">
                            {sess.status}
                          </span>
                        </div>
                        <div className="text-xs text-zinc-400 flex items-center gap-3">
                          <span>{sess.total_records} Records</span>
                          <span>•</span>
                          <span className="font-mono text-zinc-500">{sess.session_id}</span>
                        </div>
                      </div>

                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={() => handleRunStandardizedCheck(sess.session_id)}
                          disabled={isChecking}
                          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#A8DD73] hover:bg-[#bbf082] text-black font-bold text-xs shadow-md shadow-[#A8DD73]/20 transition-all disabled:opacity-50"
                        >
                          {isChecking ? (
                            <>
                              <RefreshCw className="w-3.5 h-3.5 animate-spin" />
                              <span>Scanning...</span>
                            </>
                          ) : (
                            <>
                              <ShieldCheck className="w-3.5 h-3.5" />
                              <span>Check for Duplicates</span>
                            </>
                          )}
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {/* TAB 3: APPROVED BATCHES */}
        {activeTab === "approved" && (
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 space-y-4">
            <div className="pb-3 border-b border-white/10">
              <h3 className="text-sm font-semibold text-white">
                Approved &amp; Ingested Batches
              </h3>
              <p className="text-xs text-zinc-400 mt-0.5">
                Historical record of materials active in the National Master and vector database.
              </p>
            </div>

            {approvedBatches.length === 0 ? (
              <div className="py-12 text-center text-xs text-zinc-400">
                No approved batches yet. Items will appear here once approved from the &quot;Ready for Ingestion&quot; queue.
              </div>
            ) : (
              <div className="divide-y divide-white/5 border border-white/10 rounded-xl overflow-hidden">
                {approvedBatches.map((batch) => (
                  <div
                    key={batch.id}
                    onClick={() => loadBatchDetail(batch.id)}
                    className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4 hover:bg-white/[0.02] transition-colors cursor-pointer"
                  >
                    <div>
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-mono font-bold text-white">
                          Batch {batch.id.slice(0, 8)}
                        </span>
                        <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-400/10 border border-emerald-400/30 text-emerald-400">
                          Active in Master
                        </span>
                      </div>
                      <div className="text-xs text-zinc-400 mt-1 flex items-center gap-3">
                        <span className="text-emerald-400 font-semibold font-mono">
                          +{batch.added_rows} Added
                        </span>
                        <span>•</span>
                        <span>{batch.existing_rows + batch.duplicate_rows} Duplicates Filtered</span>
                      </div>
                    </div>

                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        loadBatchDetail(batch.id);
                        setActiveTab("pending");
                      }}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/[0.04] hover:bg-white/[0.08] text-zinc-300 text-xs font-medium border border-white/10 transition-all"
                    >
                      <span>View Items</span>
                      <ChevronRight className="w-3.5 h-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </main>
    </NationalLayout>
  );
}

export default function ReviewsPage() {
  return (
    <Suspense
      fallback={
        <NationalLayout>
          <div className="flex-1 flex items-center justify-center p-12">
            <RefreshCw className="w-8 h-8 animate-spin text-[#A8DD73]" />
          </div>
        </NationalLayout>
      }
    >
      <ReviewsContent />
    </Suspense>
  );
}
