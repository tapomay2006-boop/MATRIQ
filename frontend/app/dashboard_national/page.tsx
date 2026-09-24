"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import NationalLayout from "@/components/layout/NationalLayout";
import {
  ShieldCheck,
  Landmark,
  Database,
  GitPullRequest,
  Building2,
  TrendingUp,
  Clock,
  ArrowDownUp,
  ArrowRight,
  CheckSquare,
  Package,
  Sparkles,
  AlertCircle,
  Loader2,
  CheckCircle2,
  RefreshCw,
  Search,
  UploadCloud,
  FileSpreadsheet,
  PackageSearch,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { MaterialQualityStats, MaterialRecord } from "@/lib/types/material";
import { useSession } from "next-auth/react";

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Pending";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "Pending";
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffMins = Math.floor(diffMs / (1000 * 60));
  if (diffMins < 1) return "Just now";
  if (diffMins < 60) return `${diffMins} min ago`;
  const diffHours = Math.floor(diffMins / 60);
  if (diffHours < 24) return `${diffHours} hr ago`;
  const diffDays = Math.floor(diffHours / 24);
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString("en-IN", { month: "short", day: "numeric" });
}

export default function NationalDashboardPage() {
  const { data: session } = useSession();
  const userRole = session?.user?.role || "national_admin";
  const isNationalAdmin = userRole === "national_admin";
  const userOrg = (session?.user as any)?.organization || "CCL";

  const [qualityStats, setQualityStats] = useState<MaterialQualityStats | null>(null);
  const [organizations, setOrganizations] = useState<string[]>([]);
  const [materials, setMaterials] = useState<MaterialRecord[]>([]);
  const [pendingMaterials, setPendingMaterials] = useState<MaterialRecord[]>([]);
  const [totalMaterialsCount, setTotalMaterialsCount] = useState<number>(0);
  const [pendingCount, setPendingCount] = useState<number>(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadDashboardData() {
    setLoading(true);
    setError(null);
    try {
      const [qualityRes, orgsRes, pendingRes, materialsRes] = await Promise.allSettled([
        apiClient.materials.getQuality(),
        apiClient.materials.getOrganizations(),
        apiClient.materials.list({ status: "PENDING_REVIEW", limit: 50, page_size: 50 }),
        apiClient.materials.list({ limit: 60, page_size: 60 }),
      ]);

      if (qualityRes.status === "fulfilled") {
        setQualityStats(qualityRes.value);
      }
      if (orgsRes.status === "fulfilled") {
        setOrganizations(orgsRes.value);
      }
      if (pendingRes.status === "fulfilled") {
        setPendingMaterials(pendingRes.value.items || []);
        setPendingCount(pendingRes.value.total || 0);
      }
      if (materialsRes.status === "fulfilled") {
        setMaterials(materialsRes.value.items || []);
        setTotalMaterialsCount(materialsRes.value.total || 0);
      } else {
        if (qualityRes.status === "rejected" && orgsRes.status === "rejected") {
          setError("Unable to connect to the material service. Please verify service availability.");
        }
      }
    } catch (err) {
      console.warn("Could not load National dashboard metrics:", err);
      setError("Failed to load dashboard data. Please try again.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadDashboardData();
  }, []);

  // Section 1 Metrics Calculation
  const totalRecords = qualityStats?.total_materials ?? totalMaterialsCount ?? 0;
  const assignedRecords = qualityStats?.assigned_count ?? Math.max(0, totalRecords - pendingCount);
  const orgCount = organizations.length;

  const missingTotal =
    (qualityStats?.missing_part_number || 0) +
    (qualityStats?.missing_manufacturer || 0) +
    (qualityStats?.missing_uom || 0) +
    (qualityStats?.missing_category || 0);

  const maxPossible = totalRecords * 4;
  const harmonizationIndex =
    maxPossible > 0
      ? Math.max(0, Math.round(((maxPossible - missingTotal) / maxPossible) * 100))
      : 0;

  const partNumberFidelity =
    totalRecords > 0
      ? Math.max(0, Math.round(((totalRecords - (qualityStats?.missing_part_number || 0)) / totalRecords) * 100))
      : 0;

  // Section 2 FIFO Queue Sorting: Only actual pending items, oldest submitted request appears first
  const fifoQueue = [...pendingMaterials].sort((a, b) => {
    const timeA = new Date(a.created_at || 0).getTime();
    const timeB = new Date(b.created_at || 0).getTime();
    return timeA - timeB;
  });

  const pendingQueueCount = pendingCount || fifoQueue.length || qualityStats?.unassigned_count || 0;

  const nationalQuickActions = [
    {
      label: "FIFO Review Queue",
      href: "/reviews",
      icon: CheckSquare,
      iconColor: "text-amber-400",
      badge: pendingQueueCount > 0 ? `${pendingQueueCount} Pending` : "Adjudication",
      badgeColor:
        pendingQueueCount > 0
          ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
          : "bg-white/5 text-zinc-400 border-white/10",
      description: "Adjudicate unassigned CPSE requests and issue National IDs (NMM-*)",
    },
    {
      label: "National Master Catalog",
      href: "/materials",
      icon: PackageSearch,
      iconColor: "text-[#A8DD73]",
      badge: totalRecords > 0 ? `${totalRecords} Items` : "All CPSEs",
      badgeColor: "bg-[#A8DD73]/10 text-[#A8DD73] border-[#A8DD73]/20",
      description: "Canonical master registry across all public enterprise nodes",
    },
    {
      label: "Neural Similarity Search",
      href: "/search",
      icon: Search,
      iconColor: "text-cyan-400",
      badge: "Dense Vectors",
      badgeColor: "bg-cyan-500/10 text-cyan-300 border-cyan-500/20",
      description: "Dense vector traversal & Siamese cross-encoder reranking",
    },
    {
      label: "CPSE Enterprise Nodes",
      href: "/dashboard_cpse",
      icon: Building2,
      iconColor: "text-blue-400",
      badge: `${orgCount} Nodes`,
      badgeColor: "bg-blue-500/10 text-blue-300 border-blue-500/20",
      description: "Inspect individual enterprise nodes (CCL, NTPC, BHEL, etc.)",
    },
  ];

  const cpseQuickActions = [
    {
      label: `Browse ${userOrg} Materials`,
      href: "/materials",
      icon: PackageSearch,
      iconColor: "text-[#A8DD73]",
      badge: `${userOrg} Node`,
      badgeColor: "bg-[#A8DD73]/10 text-[#A8DD73] border-[#A8DD73]/20",
      description: `View and audit registered inventory for ${userOrg}`,
    },
    {
      label: "Upload & Ingest",
      href: "/upload",
      icon: UploadCloud,
      iconColor: "text-emerald-400",
      badge: "Batch AI",
      badgeColor: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20",
      description: "Batch CSV / Excel ingestion with automated AI attribute extraction",
    },
    {
      label: "Find Equivalents",
      href: "/search",
      icon: Search,
      iconColor: "text-cyan-400",
      badge: "Pre-Procurement",
      badgeColor: "bg-cyan-500/10 text-cyan-300 border-cyan-500/20",
      description: "Search National Master to identify duplicate inventory before procurement",
    },
    {
      label: "Extraction Sessions",
      href: "/reviews?tab=sessions",
      icon: FileSpreadsheet,
      iconColor: "text-amber-400",
      badge: "Session Status",
      badgeColor: "bg-amber-500/10 text-amber-300 border-amber-500/20",
      description: "Track status of uploaded batches & pending harmonization reviews",
    },
  ];

  const activeQuickActions = isNationalAdmin ? nationalQuickActions : cpseQuickActions;

  return (
    <NationalLayout>
      <main className="flex-1 flex flex-col px-4 sm:px-8 lg:px-10 py-6 sm:py-8 max-w-[1400px] w-full space-y-7">
        {/* Header Section */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-4 border-b border-white/5">
          <div>
            {/* Pill Badge */}
            <div className="inline-flex items-center gap-2 mb-3 px-3 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/25 backdrop-blur-md">
              <Landmark className="w-3.5 h-3.5 text-emerald-400" />
              <span
                className="text-xs font-medium tracking-wide text-emerald-300"
                style={{ fontFamily: "var(--font-body)" }}
              >
                Central Registry · National Directory Governance
              </span>
            </div>

            {/* Heading following landing page style */}
            <h1
              className="tracking-tight"
              style={{
                fontFamily: "var(--font-heading)",
                fontWeight: 400,
                fontSize: "clamp(2.4rem, 4.5vw, 3.8rem)",
                lineHeight: 1.1,
                letterSpacing: "-0.02em",
                margin: 0,
              }}
            >
              <span className="text-white">Material </span>
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Intelligence Dashboard
              </span>
            </h1>

            <p
              className="mt-2.5 max-w-2xl text-zinc-400 text-sm sm:text-[15.5px] leading-relaxed"
              style={{ fontFamily: "var(--font-body)" }}
            >
              National-level material governance and harmonization oversight.
            </p>
          </div>

          <div className="hidden lg:flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-white/[0.02] border border-white/10 text-xs text-zinc-400 shrink-0">
            <ShieldCheck className="w-4 h-4 text-emerald-400" />
            <span>National Directory Authority Active</span>
          </div>
        </div>

        {/* Conceptual Workflow Ribbon (Reinforcing FIFO Review Pipeline) */}
        <div className="px-4 py-2.5 rounded-xl bg-white/[0.02] border border-white/5 flex items-center justify-between flex-wrap gap-2 text-xs text-zinc-400">
          <div className="flex items-center gap-2 flex-wrap font-mono text-[11px]">
            <span className="text-zinc-300 font-semibold uppercase tracking-wider">Workflow Pipeline:</span>
            <span className="text-zinc-400">CPSE Submission</span>
            <span className="text-zinc-600">→</span>
            <span className="text-zinc-400">AI Vector Matching</span>
            <span className="text-zinc-600">→</span>
            <span className="text-[#A8DD73] font-semibold bg-[#A8DD73]/10 px-2 py-0.5 rounded border border-[#A8DD73]/30 flex items-center gap-1">
              <ArrowDownUp className="w-3 h-3 text-[#A8DD73]" />
              FIFO Review Queue
            </span>
            <span className="text-zinc-600">→</span>
            <span className="text-emerald-400">National Master</span>
          </div>
          <span className="text-[11px] text-zinc-500 hidden md:inline font-mono">
            Sequential Adjudication Active
          </span>
        </div>

        {/* Section 1 — Overview Metrics (4-card row) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. Master Registry Items */}
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 flex flex-col justify-between hover:border-white/20 transition-colors">
            <div className="flex items-center justify-between text-zinc-400 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider">Master Registry Items</span>
              <Database className="w-4 h-4 text-[#A8DD73]" />
            </div>
            <div>
              {loading ? (
                <div className="h-8 w-24 bg-white/10 rounded animate-pulse" />
              ) : (
                <div className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                  {totalRecords > 0 ? totalRecords.toLocaleString() : "0"}
                </div>
              )}
              <p className="text-[11px] text-zinc-500 mt-1">Standardized national material records</p>
            </div>
          </div>

          {/* 2. Reporting CPSEs */}
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 flex flex-col justify-between hover:border-white/20 transition-colors">
            <div className="flex items-center justify-between text-zinc-400 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider">Reporting CPSEs</span>
              <Building2 className="w-4 h-4 text-sky-400" />
            </div>
            <div>
              {loading ? (
                <div className="h-8 w-16 bg-white/10 rounded animate-pulse" />
              ) : (
                <div className="text-2xl sm:text-3xl font-bold text-sky-400 tracking-tight">
                  {orgCount}
                </div>
              )}
              <p className="text-[11px] text-zinc-500 mt-1 truncate">
                {orgCount > 0 ? organizations.slice(0, 3).join(", ") + (orgCount > 3 ? ` +${orgCount - 3} more` : "") : "Active enterprise nodes"}
              </p>
            </div>
          </div>

          {/* 3. Pending Decision Queue */}
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 flex flex-col justify-between hover:border-white/20 transition-colors">
            <div className="flex items-center justify-between text-zinc-400 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider">Pending Decision Queue</span>
              <GitPullRequest className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              {loading ? (
                <div className="h-8 w-16 bg-white/10 rounded animate-pulse" />
              ) : (
                <div className="text-2xl sm:text-3xl font-bold text-amber-400 tracking-tight">
                  {pendingQueueCount}
                </div>
              )}
              <p className="text-[11px] text-zinc-500 mt-1">Awaiting National Admin review</p>
            </div>
          </div>

          {/* 4. Harmonization Index */}
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 flex flex-col justify-between hover:border-white/20 transition-colors">
            <div className="flex items-center justify-between text-zinc-400 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider">Harmonization Index</span>
              <TrendingUp className="w-4 h-4 text-[#A8DD73]" />
            </div>
            <div>
              {loading ? (
                <div className="h-8 w-20 bg-white/10 rounded animate-pulse" />
              ) : (
                <div className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                  {totalRecords > 0 ? `${harmonizationIndex}%` : "N/A"}
                </div>
              )}
              <p className="text-[11px] text-zinc-500 mt-1">Overall standardization completeness</p>
            </div>
          </div>
        </div>

        {/* Section 2 — Pending Review Queue (MOST IMPORTANT SECTION - FIFO Order) */}
        <div className="rounded-2xl bg-[#121013]/90 border border-white/10 overflow-hidden shadow-xl">
          {/* Table Header / Queue Banner */}
          <div className="p-5 sm:p-6 border-b border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white/[0.01]">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg sm:text-xl font-semibold text-white tracking-tight m-0">
                  Pending Review Queue
                </h2>
                <span className="px-2 py-0.5 rounded-full bg-amber-500/10 text-amber-400 text-xs font-mono font-medium border border-amber-500/20">
                  {pendingQueueCount} pending
                </span>
              </div>
              <p className="text-xs sm:text-sm text-zinc-400 mt-1 m-0">
                Review new material requests in first-in, first-out order.
              </p>
            </div>

            {/* FIFO Indicator Pill */}
            <div className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-[#A8DD73]/10 border border-[#A8DD73]/30 text-xs font-mono font-medium text-[#A8DD73] shrink-0">
              <ArrowDownUp className="w-3.5 h-3.5 text-[#A8DD73]" />
              <span>FIFO Queue • Oldest request first</span>
            </div>
          </div>

          {/* Queue Content State Handler */}
          {loading ? (
            /* Loading Skeleton */
            <div className="p-6 space-y-4">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex items-center justify-between gap-4 p-4 rounded-xl bg-white/[0.02] border border-white/5 animate-pulse">
                  <div className="h-4 w-12 bg-white/10 rounded" />
                  <div className="h-4 w-16 bg-white/10 rounded" />
                  <div className="h-4 w-48 bg-white/10 rounded flex-1" />
                  <div className="h-4 w-20 bg-white/10 rounded" />
                  <div className="h-7 w-20 bg-white/10 rounded-lg" />
                </div>
              ))}
            </div>
          ) : error && fifoQueue.length === 0 ? (
            /* Error State with Retry Button */
            <div className="p-10 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-amber-400 mx-auto" />
              <h3 className="text-sm font-semibold text-white">{error}</h3>
              <p className="text-xs text-zinc-400 max-w-md mx-auto">
                Could not retrieve queue items from the API service. Verify backend connectivity and retry.
              </p>
              <button
                onClick={loadDashboardData}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-xs text-white transition-colors cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry Connection</span>
              </button>
            </div>
          ) : fifoQueue.length === 0 ? (
            /* Empty State */
            <div className="p-10 text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/25 flex items-center justify-center text-emerald-400 mx-auto">
                <CheckCircle2 className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-semibold text-white">No pending requests in FIFO queue</h3>
              <p className="text-xs text-zinc-400 max-w-md mx-auto leading-relaxed">
                All CPSE material submissions have been reviewed and standardized into the National Master Registry.
              </p>
            </div>
          ) : (
            /* Desktop & Tablet Table */
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/5 bg-white/[0.015] text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
                    <th className="py-3 px-4 w-12 text-center">FIFO</th>
                    <th className="py-3 px-4">Request ID</th>
                    <th className="py-3 px-4">CPSE</th>
                    <th className="py-3 px-4">Material / Description</th>
                    <th className="py-3 px-4">Submitted At</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-xs">
                  {fifoQueue.map((item, index) => {
                    const relativeTime = formatRelativeTime(item.created_at);
                    const formattedDate = item.created_at
                      ? new Date(item.created_at).toLocaleString("en-IN")
                      : "Unrecorded";
                    const isFirst = index === 0;

                    return (
                      <tr
                        key={item.id || index}
                        className={`group hover:bg-white/[0.03] transition-colors ${isFirst ? "bg-[#A8DD73]/[0.02]" : ""
                          }`}
                      >
                        {/* FIFO Queue Position */}
                        <td className="py-3.5 px-4 text-center font-mono">
                          <span
                            className={`inline-flex items-center justify-center w-6 h-6 rounded-full text-[11px] font-bold ${isFirst
                              ? "bg-[#A8DD73]/20 text-[#A8DD73] border border-[#A8DD73]/40 shadow-[0_0_8px_rgba(168,221,115,0.2)]"
                              : "bg-white/5 text-zinc-400"
                              }`}
                          >
                            #{index + 1}
                          </span>
                        </td>

                        {/* Request ID */}
                        <td className="py-3.5 px-4 font-mono font-medium text-white whitespace-nowrap">
                          {item.legacy_code || `#${item.id.slice(0, 6)}`}
                        </td>

                        {/* CPSE Entity */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <span className="px-2 py-0.5 rounded-md bg-white/5 border border-white/10 text-zinc-300 font-mono text-[11px] font-semibold">
                            {item.organization || "CPSE"}
                          </span>
                        </td>

                        {/* Material / Description */}
                        <td className="py-3.5 px-4 max-w-xs md:max-w-md">
                          <div className="font-medium text-white group-hover:text-[#A8DD73] transition-colors truncate">
                            {item.item_name || item.description || "Material Spec Item"}
                          </div>
                          <div className="text-[11px] text-zinc-500 truncate mt-0.5">
                            {item.category ? `${item.category} · ` : ""}
                            {item.part_number ? `P/N: ${item.part_number}` : item.description}
                          </div>
                        </td>

                        {/* Submitted At (FIFO Timestamp) */}
                        <td className="py-3.5 px-4 whitespace-nowrap text-zinc-400" title={formattedDate}>
                          <div className="flex items-center gap-1.5 text-zinc-300">
                            <Clock className="w-3.5 h-3.5 text-zinc-500" />
                            <span>{relativeTime}</span>
                          </div>
                          {isFirst && (
                            <span className="text-[10px] text-[#A8DD73] font-mono block">
                              Next in queue
                            </span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-amber-500/10 text-amber-400 border border-amber-500/25">
                            <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
                            Pending
                          </span>
                        </td>

                        {/* Action: Review Route */}
                        <td className="py-3.5 px-4 text-right whitespace-nowrap">
                          <Link
                            href={`/reviews?id=${item.id}&code=${encodeURIComponent(
                              item.legacy_code || ""
                            )}&org=${encodeURIComponent(item.organization || "")}`}
                            className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-[#A8DD73] hover:bg-[#bbf082] text-black text-xs font-semibold transition-all shadow-sm shadow-[#A8DD73]/20 hover:shadow-[#A8DD73]/30 active:scale-95 no-underline cursor-pointer"
                            title="Open review workflow"
                          >
                            <span>Review</span>
                            <ArrowRight className="w-3 h-3" />
                          </Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Section 3 — Harmonization Overview */}
        <div className="p-5 sm:p-6 rounded-2xl bg-[#121013]/90 border border-white/10 space-y-4">
          <div>
            <h2 className="text-base sm:text-lg font-semibold text-white tracking-tight m-0">
              Harmonization Overview
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5 m-0">
              Global catalog attribute consistency and standardization fidelity.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-2">
            {/* Metric 1: Standardized Attribute Rate */}
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-300 font-medium">Standardized Attributes</span>
                <span className="font-mono font-bold text-[#A8DD73] text-sm">
                  {loading ? "..." : `${harmonizationIndex}%`}
                </span>
              </div>
              <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-gradient-to-r from-[#A8DD73] to-emerald-400 h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, harmonizationIndex))}%` }}
                />
              </div>
              <p className="text-[11px] text-zinc-500 m-0">
                Core fields completeness (UOM, OEM, P/N, Category)
              </p>
            </div>

            {/* Metric 2: Part Number Fidelity */}
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-300 font-medium">OEM Part Number Fidelity</span>
                <span className="font-mono font-bold text-sky-400 text-sm">
                  {loading ? "..." : `${partNumberFidelity}%`}
                </span>
              </div>
              <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-sky-400 h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, partNumberFidelity))}%` }}
                />
              </div>
              <p className="text-[11px] text-zinc-500 m-0">
                Resolved part numbers matching national standard
              </p>
            </div>

            {/* Metric 3: Pending Decisions */}
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 flex flex-col justify-between">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-300 font-medium">Pending Decision Items</span>
                <GitPullRequest className="w-4 h-4 text-amber-400" />
              </div>
              <div className="my-1">
                <div className="text-2xl font-bold font-mono text-amber-400">
                  {loading ? "..." : pendingQueueCount}
                </div>
              </div>
              <p className="text-[11px] text-zinc-500 m-0">
                Awaiting National Admin review in FIFO sequence
              </p>
            </div>
          </div>
        </div>

        {/* Section 4 — Quick Actions */}
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2.5">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-400">
                Quick Actions
              </span>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-md bg-emerald-500/10 text-emerald-300 border border-emerald-500/20 font-medium">
                {isNationalAdmin ? "National Sovereign Role" : `${userOrg} Enterprise Role`}
              </span>
            </div>
            <span className="text-[11px] text-zinc-500 font-mono hidden sm:inline">
              {isNationalAdmin
                ? "Sovereign review queue, cross-CPSE master & vector search"
                : "Enterprise catalog operations, batch ingestion & duplicate checks"}
            </span>
          </div>

          <div className="flex items-center gap-3 flex-wrap">
            {activeQuickActions.map((action) => {
              const ActionIcon = action.icon;
              return (
                <Link
                  key={action.href}
                  href={action.href}
                  title={action.description}
                  className="group inline-flex items-center gap-2.5 px-4 py-2.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.07] border border-white/10 hover:border-[#A8DD73]/40 text-xs font-medium text-white transition-all no-underline shadow-sm hover:shadow-[0_0_15px_rgba(168,221,115,0.08)]"
                >
                  <ActionIcon className={`w-4 h-4 ${action.iconColor} group-hover:scale-110 transition-transform`} />
                  <span>{action.label}</span>
                  <span
                    className={`text-[10px] font-mono px-2 py-0.5 rounded-md border ${action.badgeColor} transition-colors`}
                  >
                    {action.badge}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>
      </main>
    </NationalLayout>
  );
}
