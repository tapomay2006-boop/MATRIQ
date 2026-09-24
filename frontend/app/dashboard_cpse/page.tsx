"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import CpseLayout from "@/components/layout/CpseLayout";
import {
  Building2,
  Cpu,
  Layers,
  Database,
  Clock,
  ShieldCheck,
  CheckCircle2,
  Sparkles,
  ArrowRight,
  UploadCloud,
  CheckSquare,
  PackageSearch,
  RefreshCw,
  AlertCircle,
  ChevronDown,
  Search,
  FileSpreadsheet,
  Landmark,
  Package,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { aiClient } from "@/lib/api/ai-client";
import { MaterialRecord, MaterialQualityStats } from "@/lib/types/material";
import { useSession } from "next-auth/react";

function formatRelativeTime(dateString?: string): string {
  if (!dateString) return "Recently";
  const date = new Date(dateString);
  if (isNaN(date.getTime())) return "Recently";
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

export default function CpseDashboardPage() {
  const { data: session } = useSession();
  const userRole = session?.user?.role || "cpse_admin";
  const isNationalAdmin = userRole === "national_admin";
  const defaultCpseOrg = (session?.user as any)?.organization || "CCL";
  const [selectedOrg, setSelectedOrg] = useState<string>(isNationalAdmin ? "CCL" : defaultCpseOrg);
  const [availableOrgs, setAvailableOrgs] = useState<string[]>(["CCL", "NTPC", "BHEL", "SAIL", "ONGC", "IOCL"]);
  const [materials, setMaterials] = useState<MaterialRecord[]>([]);
  const [totalCount, setTotalCount] = useState<number>(0);
  const [reviewCount, setReviewCount] = useState<number>(0);
  const [retrievalStats, setRetrievalStats] = useState<{
    materials: number;
    indexed: number;
    store: string;
    store_reachable: boolean;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function loadCpseData(orgName: string) {
    setLoading(true);
    setError(null);
    try {
      const [
        orgsRes,
        apiMaterialsRes,
        aiMaterialsRes,
        indexStatusRes,
        sessionsRes,
      ] = await Promise.allSettled([
        apiClient.materials.getOrganizations(),
        apiClient.materials.list({ organization: orgName, limit: 50, page_size: 50 }),
        aiClient.getMaterials({ cpse: orgName, limit: 50 }),
        aiClient.getIndexStatus(),
        aiClient.getSessions(),
      ]);

      if (orgsRes.status === "fulfilled" && orgsRes.value.length > 0) {
        setAvailableOrgs(orgsRes.value);
        if (!orgsRes.value.map((o) => o.toLowerCase()).includes(orgName.toLowerCase())) {
          setSelectedOrg(orgsRes.value[0]);
        }
      }

      if (indexStatusRes.status === "fulfilled") {
        setRetrievalStats(indexStatusRes.value);
      }

      let pendingSessions = 0;
      if (sessionsRes.status === "fulfilled" && Array.isArray(sessionsRes.value)) {
        pendingSessions = sessionsRes.value.filter(
          (s: any) => s.status === "PENDING_REVIEW" || s.status === "PROCESSING"
        ).length;
      }

      let loadedItems: MaterialRecord[] = [];

      // 1. Prioritize api-service materials if populated
      if (
        apiMaterialsRes.status === "fulfilled" &&
        apiMaterialsRes.value.items &&
        apiMaterialsRes.value.items.length > 0
      ) {
        loadedItems = apiMaterialsRes.value.items;
        setMaterials(loadedItems);
        setTotalCount(apiMaterialsRes.value.total || loadedItems.length);
        const pendingInItems = loadedItems.filter(
          (m) => m.status === "PENDING_REVIEW" || !m.national_id
        ).length;
        setReviewCount(Math.max(pendingSessions, pendingInItems));
      }
      // 2. Otherwise load live items from AI service master catalog
      else if (
        aiMaterialsRes.status === "fulfilled" &&
        aiMaterialsRes.value.items &&
        aiMaterialsRes.value.items.length > 0
      ) {
        loadedItems = aiMaterialsRes.value.items.map((m: any, idx: number) => ({
          id: m.material_id || `mat-${idx}`,
          organization: m.cpse_code || m.company || orgName,
          legacy_code: m.legacy_code || m.material_id,
          national_id: m.national_id || null,
          status: m.status || (m.national_id ? "ASSIGNED" : "PENDING_REVIEW"),
          description: m.description,
          uom: m.uom || "NOS",
          item_name:
            m.description.length > 40 ? `${m.description.slice(0, 40)}...` : m.description,
          part_number: m.part_number,
          manufacturer: m.make,
          category: m.category,
          specification: m.specifications,
          source_file: "ai_master_catalog",
          source_row: m.source_row || idx + 1,
          created_at: m.created_at || new Date().toISOString(),
          updated_at: m.created_at || new Date().toISOString(),
        }));
        setMaterials(loadedItems);
        setTotalCount(aiMaterialsRes.value.total || loadedItems.length);
      }
      // 3. Fallback: check if any items exist across all CPSEs in AI service
      else {
        try {
          const allAi = await aiClient.getMaterials({ limit: 50 });
          if (allAi && allAi.items && allAi.items.length > 0) {
            loadedItems = allAi.items.map((m: any, idx: number) => ({
              id: m.material_id || `mat-${idx}`,
              organization: m.cpse_code || m.company || orgName,
              legacy_code: m.legacy_code || m.material_id,
              national_id: m.national_id || null,
              status: m.status || (m.national_id ? "ASSIGNED" : "PENDING_REVIEW"),
              description: m.description,
              uom: m.uom || "NOS",
              item_name:
                m.description.length > 40 ? `${m.description.slice(0, 40)}...` : m.description,
              part_number: m.part_number,
              manufacturer: m.make,
              category: m.category,
              specification: m.specifications,
              source_file: "ai_master_catalog",
              source_row: m.source_row || idx + 1,
              created_at: m.created_at || new Date().toISOString(),
              updated_at: m.created_at || new Date().toISOString(),
            }));
            setMaterials(loadedItems);
            setTotalCount(allAi.total || loadedItems.length);
          } else {
            setMaterials([]);
            setTotalCount(0);
          }
        } catch {
          setMaterials([]);
          setTotalCount(0);
        }
      }
    } catch (err) {
      console.warn("Could not load CPSE dashboard data:", err);
      setError("Unable to load enterprise catalog data. Please verify service availability.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadCpseData(selectedOrg);
  }, [selectedOrg]);

  // Scoped Metrics Calculations for Current CPSE
  const itemsCount = totalCount > 0 ? totalCount : (retrievalStats?.materials || materials.length);

  // Duplicate candidates: detect items sharing identical name/description or missing critical part numbers
  const duplicateCandidates = materials.filter((m, idx, arr) => {
    return (
      arr.findIndex(
        (x) =>
          x.id !== m.id &&
          ((x.item_name && m.item_name && x.item_name.toLowerCase() === m.item_name.toLowerCase()) ||
            (x.description && m.description && x.description.toLowerCase() === m.description.toLowerCase()) ||
            (x.part_number && m.part_number && x.part_number.toLowerCase() === m.part_number.toLowerCase()))
      ) !== -1
    );
  }).length;

  // Harmonization Progress: Completeness of critical attributes (UOM, Part Number, Manufacturer, Category)
  const totalPossibleAttributes = Math.max(1, materials.length * 4);
  const presentAttributes = materials.reduce((acc, item) => {
    let count = 0;
    if (item.uom && item.uom.trim()) count++;
    if (item.part_number && item.part_number.trim()) count++;
    if (item.manufacturer && item.manufacturer.trim()) count++;
    if (item.category && item.category.trim() && item.category !== "UNCLASSIFIED") count++;
    return acc + count;
  }, 0);

  const harmonizationProgress =
    materials.length > 0
      ? Math.max(0, Math.min(100, Math.round((presentAttributes / totalPossibleAttributes) * 100)))
      : (retrievalStats && retrievalStats.indexed > 0 ? 100 : 0);

  // Submissions in Review: items or sessions pending standardization / adjudication
  const submissionsInReview =
    reviewCount > 0
      ? reviewCount
      : materials.filter((m) => !m.part_number || !m.manufacturer).length;

  // Harmonization Section Progress Indicators
  const aiMatchedPercent =
    materials.length > 0
      ? Math.round(
          (materials.filter(
            (m) => m.category && m.category.trim()
          ).length /
            materials.length) *
            100
        )
      : (retrievalStats && retrievalStats.indexed > 0 ? 100 : 0);

  const standardizedPercent =
    materials.length > 0
      ? Math.round(
          (materials.filter((m) => m.part_number && m.manufacturer).length /
            materials.length) *
            100
        )
      : (retrievalStats && retrievalStats.indexed > 0 ? 100 : 0);

  const submittedForReviewPercent =
    retrievalStats && retrievalStats.materials > 0
      ? Math.round((retrievalStats.indexed / retrievalStats.materials) * 100)
      : (materials.length > 0 ? 100 : 0);

  const cpseQuickActions = [
    {
      label: `Browse ${selectedOrg} Materials`,
      href: "/materials",
      icon: PackageSearch,
      iconColor: "text-[#A8DD73]",
      badge: materials.length > 0 ? `${materials.length} Items` : `${selectedOrg} Node`,
      badgeColor: "bg-[#A8DD73]/10 text-[#A8DD73] border-[#A8DD73]/20",
      description: `View and audit registered inventory for ${selectedOrg}`,
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
      badge: reviewCount > 0 ? `${reviewCount} In Review` : "Pipeline Active",
      badgeColor:
        reviewCount > 0
          ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
          : "bg-white/5 text-zinc-400 border-white/10",
      description: "Track status of uploaded batches & pending harmonization reviews",
    },
  ];

  const nationalQuickActions = [
    {
      label: "FIFO Review Queue",
      href: "/reviews",
      icon: CheckSquare,
      iconColor: "text-amber-400",
      badge: reviewCount > 0 ? `${reviewCount} Pending` : "Adjudication",
      badgeColor:
        reviewCount > 0
          ? "bg-amber-500/15 text-amber-300 border-amber-500/30"
          : "bg-white/5 text-zinc-400 border-white/10",
      description: "Adjudicate unassigned CPSE requests and issue National IDs (NMM-*)",
    },
    {
      label: "National Master Catalog",
      href: "/materials",
      icon: PackageSearch,
      iconColor: "text-[#A8DD73]",
      badge: "All 7 CPSEs",
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
      description: "Traverse semantic vector embeddings & Siamese cross-encoder reranker",
    },
    {
      label: "Sovereign Governance Hub",
      href: "/dashboard_national",
      icon: Landmark,
      iconColor: "text-purple-400",
      badge: "Executive",
      badgeColor: "bg-purple-500/10 text-purple-300 border-purple-500/20",
      description: "National deduplication metrics and multi-CPSE compliance overview",
    },
  ];

  const activeQuickActions = isNationalAdmin ? nationalQuickActions : cpseQuickActions;

  return (
    <CpseLayout>
      <main className="flex-1 flex flex-col px-4 sm:px-8 lg:px-10 py-6 sm:py-8 max-w-[1400px] w-full space-y-7">
        {/* Header Section */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-4 border-b border-white/5">
          <div>
            {/* Pill Badge */}
            <div className="flex items-center gap-2 mb-3 flex-wrap">
              <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-[#A8DD73]/10 border border-[#A8DD73]/25 backdrop-blur-md">
                <Building2 className="w-3.5 h-3.5 text-[#A8DD73]" />
                <span
                  className="text-xs font-medium tracking-wide text-[#A8DD73]"
                  style={{ fontFamily: "var(--font-body)" }}
                >
                  CPSE Enterprise Workspace
                </span>
              </div>
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
              CPSE-level material management and harmonization with the National Master Registry.
            </p>
          </div>

          <div className="hidden lg:flex items-center gap-2 px-3.5 py-2 rounded-2xl bg-white/[0.02] border border-white/10 text-xs text-zinc-400 shrink-0">
            <ShieldCheck className="w-4 h-4 text-[#A8DD73]" />
            <span>CPSE Enterprise Node Connected</span>
          </div>
        </div>

        {/* Conceptual Workflow Ribbon */}
        <div className="px-4 py-2.5 rounded-xl bg-white/[0.02] border border-white/5 flex items-center justify-between flex-wrap gap-2 text-xs text-zinc-400">
          <div className="flex items-center gap-2 flex-wrap font-mono text-[11px]">
            <span className="text-zinc-300 font-semibold uppercase tracking-wider">Enterprise Lifecycle:</span>
            <span className="text-white">Manage Materials</span>
            <span className="text-zinc-600">→</span>
            <span className="text-amber-400 font-medium">Detect Duplicates</span>
            <span className="text-zinc-600">→</span>
            <span className="text-[#A8DD73] font-medium">AI Harmonization</span>
            <span className="text-zinc-600">→</span>
            <span className="text-sky-400 font-medium">Submit to National Admin</span>
            <span className="text-zinc-600">→</span>
            <span className="text-emerald-400 font-medium">Track Status</span>
          </div>
          <span className="text-[11px] text-zinc-500 hidden md:inline font-mono">
            {selectedOrg} Local Scope
          </span>
        </div>

        {/* Section 2 — Overview Metrics (4-card row scoped to CPSE) */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {/* 1. CPSE Catalog Items */}
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 flex flex-col justify-between hover:border-white/20 transition-colors">
            <div className="flex items-center justify-between text-zinc-400 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider">CPSE Catalog Items</span>
              <Database className="w-4 h-4 text-[#A8DD73]" />
            </div>
            <div>
              {loading ? (
                <div className="h-8 w-24 bg-white/10 rounded animate-pulse" />
              ) : (
                <div className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                  {itemsCount > 0 ? itemsCount.toLocaleString() : "0"}
                </div>
              )}
              <p className="text-[11px] text-zinc-500 mt-1">{selectedOrg} inventory records registered</p>
            </div>
          </div>

          {/* 2. Duplicate Candidates */}
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 flex flex-col justify-between hover:border-white/20 transition-colors">
            <div className="flex items-center justify-between text-zinc-400 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider">Duplicate Candidates</span>
              <Layers className="w-4 h-4 text-amber-400" />
            </div>
            <div>
              {loading ? (
                <div className="h-8 w-16 bg-white/10 rounded animate-pulse" />
              ) : (
                <div className="text-2xl sm:text-3xl font-bold text-amber-400 tracking-tight">
                  {duplicateCandidates}
                </div>
              )}
              <p className="text-[11px] text-zinc-500 mt-1">Identified across local inventory lines</p>
            </div>
          </div>

          {/* 3. Harmonization Progress */}
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 flex flex-col justify-between hover:border-white/20 transition-colors">
            <div className="flex items-center justify-between text-zinc-400 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider">Harmonization Progress</span>
              <Cpu className="w-4 h-4 text-[#A8DD73]" />
            </div>
            <div>
              {loading ? (
                <div className="h-8 w-20 bg-white/10 rounded animate-pulse" />
              ) : (
                <div className="text-2xl sm:text-3xl font-bold text-white tracking-tight">
                  {itemsCount > 0 ? `${harmonizationProgress}%` : "N/A"}
                </div>
              )}
              <p className="text-[11px] text-zinc-500 mt-1">Normalized attributes completeness</p>
            </div>
          </div>

          {/* 4. Submissions in Review */}
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 flex flex-col justify-between hover:border-white/20 transition-colors">
            <div className="flex items-center justify-between text-zinc-400 mb-3">
              <span className="text-xs font-semibold uppercase tracking-wider">Submissions in Review</span>
              <Clock className="w-4 h-4 text-sky-400" />
            </div>
            <div>
              {loading ? (
                <div className="h-8 w-16 bg-white/10 rounded animate-pulse" />
              ) : (
                <div className="text-2xl sm:text-3xl font-bold text-sky-400 tracking-tight">
                  {submissionsInReview}
                </div>
              )}
              <p className="text-[11px] text-zinc-500 mt-1">Submitted to National Admin for review</p>
            </div>
          </div>
        </div>

        {/* Section 3 — Material Harmonization Section (Compact Progress Indicators) */}
        <div className="p-5 sm:p-6 rounded-2xl bg-[#121013]/90 border border-white/10 space-y-4">
          <div>
            <h2 className="text-base sm:text-lg font-semibold text-white tracking-tight m-0">
              Material Harmonization
            </h2>
            <p className="text-xs text-zinc-400 mt-0.5 m-0">
              Cross-attribute normalization and national registry alignment progress.
            </p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-5 pt-2">
            {/* 1. AI Matched */}
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-300 font-medium">AI Matched</span>
                <span className="font-mono font-bold text-[#A8DD73] text-sm">
                  {loading ? "..." : `${aiMatchedPercent}%`}
                </span>
              </div>
              <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-gradient-to-r from-[#A8DD73] to-emerald-400 h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, aiMatchedPercent))}%` }}
                />
              </div>
              <p className="text-[11px] text-zinc-500 m-0">
                Neural vector category and specification alignment
              </p>
            </div>

            {/* 2. Standardized */}
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-300 font-medium">Standardized</span>
                <span className="font-mono font-bold text-emerald-400 text-sm">
                  {loading ? "..." : `${standardizedPercent}%`}
                </span>
              </div>
              <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-emerald-400 h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, standardizedPercent))}%` }}
                />
              </div>
              <p className="text-[11px] text-zinc-500 m-0">
                Part number and OEM manufacturer verified
              </p>
            </div>

            {/* 3. Submitted for Review */}
            <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 space-y-2">
              <div className="flex items-center justify-between text-xs">
                <span className="text-zinc-300 font-medium">Submitted for Review</span>
                <span className="font-mono font-bold text-sky-400 text-sm">
                  {loading ? "..." : `${submittedForReviewPercent}%`}
                </span>
              </div>
              <div className="w-full bg-white/10 h-2 rounded-full overflow-hidden">
                <div
                  className="bg-sky-400 h-full rounded-full transition-all duration-500"
                  style={{ width: `${Math.min(100, Math.max(0, submittedForReviewPercent))}%` }}
                />
              </div>
              <p className="text-[11px] text-zinc-500 m-0">
                Forwarded to National Admin review queue
              </p>
            </div>
          </div>
        </div>

        {/* Section 4 — Recent Material Activity */}
        <div className="rounded-2xl bg-[#121013]/90 border border-white/10 overflow-hidden shadow-xl">
          <div className="p-5 sm:p-6 border-b border-white/10 flex flex-col sm:flex-row sm:items-center justify-between gap-4 bg-white/[0.01]">
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg sm:text-xl font-semibold text-white tracking-tight m-0">
                  Recent Material Activity
                </h2>
                <span className="px-2 py-0.5 rounded-full bg-white/5 text-zinc-300 text-xs font-mono font-medium border border-white/10">
                  {selectedOrg} Catalog
                </span>
              </div>
              <p className="text-xs sm:text-sm text-zinc-400 mt-1 m-0">
                Recently ingested, normalized, or submitted material records.
              </p>
            </div>

            <Link
              href="/materials"
              className="text-xs font-semibold text-[#A8DD73] hover:text-[#bbf082] transition-colors flex items-center gap-1 no-underline shrink-0"
            >
              <span>View full catalog</span>
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>

          {/* Activity Content Handler */}
          {loading ? (
            <div className="p-6 space-y-3">
              {[1, 2, 3, 4].map((i) => (
                <div key={i} className="flex items-center justify-between gap-4 p-3.5 rounded-xl bg-white/[0.02] border border-white/5 animate-pulse">
                  <div className="h-4 w-44 bg-white/10 rounded" />
                  <div className="h-4 w-24 bg-white/10 rounded" />
                  <div className="h-4 w-20 bg-white/10 rounded" />
                  <div className="h-4 w-16 bg-white/10 rounded" />
                </div>
              ))}
            </div>
          ) : error && materials.length === 0 ? (
            <div className="p-10 text-center space-y-3">
              <AlertCircle className="w-8 h-8 text-amber-400 mx-auto" />
              <h3 className="text-sm font-semibold text-white">{error}</h3>
              <p className="text-xs text-zinc-400 max-w-md mx-auto">
                Unable to retrieve recent material activity for {selectedOrg}.
              </p>
              <button
                onClick={() => loadCpseData(selectedOrg)}
                className="inline-flex items-center gap-1.5 px-3.5 py-2 rounded-xl bg-white/10 hover:bg-white/15 text-xs text-white transition-colors cursor-pointer"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                <span>Retry</span>
              </button>
            </div>
          ) : materials.length === 0 ? (
            <div className="p-10 text-center space-y-3">
              <div className="w-10 h-10 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-zinc-400 mx-auto">
                <Database className="w-5 h-5" />
              </div>
              <h3 className="text-sm font-semibold text-white">No material records found for {selectedOrg}</h3>
              <p className="text-xs text-zinc-400 max-w-md mx-auto leading-relaxed">
                Upload your initial CSV or JSON catalog batch to begin automated duplicate detection and AI harmonization.
              </p>
              <Link
                href="/upload"
                className="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-[#A8DD73] text-black font-semibold text-xs transition-all shadow-md shadow-[#A8DD73]/20 no-underline mt-2"
              >
                <UploadCloud className="w-4 h-4" />
                <span>Upload First Batch</span>
              </Link>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse">
                <thead>
                  <tr className="border-b border-white/5 bg-white/[0.015] text-[11px] font-mono text-zinc-400 uppercase tracking-wider">
                    <th className="py-3 px-4">Material</th>
                    <th className="py-3 px-4">Action</th>
                    <th className="py-3 px-4">Status</th>
                    <th className="py-3 px-4 text-right">Time</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 text-xs">
                  {materials.slice(0, 8).map((item, index) => {
                    const relativeTime = formatRelativeTime(item.created_at || item.updated_at);
                    const isStandardized = Boolean(item.part_number && item.manufacturer && item.category);
                    const isAiMatched = Boolean(item.category && !isStandardized);

                    let actionLabel = "Ingested";
                    let statusBadge = (
                      <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-white/5 text-zinc-300 border border-white/10">
                        <CheckCircle2 className="w-3.5 h-3.5 text-zinc-400" />
                        Cataloged
                      </span>
                    );

                    if (isStandardized) {
                      actionLabel = "Standardized";
                      statusBadge = (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/25">
                          <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
                          Standardized
                        </span>
                      );
                    } else if (isAiMatched) {
                      actionLabel = "AI Matched";
                      statusBadge = (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-[#A8DD73]/10 text-[#A8DD73] border border-[#A8DD73]/25">
                          <Sparkles className="w-3.5 h-3.5 text-[#A8DD73]" />
                          AI Matched
                        </span>
                      );
                    } else {
                      actionLabel = "Submitted for Review";
                      statusBadge = (
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium bg-sky-500/10 text-sky-400 border border-sky-500/25">
                          <Clock className="w-3.5 h-3.5 text-sky-400" />
                          Under Review
                        </span>
                      );
                    }

                    return (
                      <tr key={item.id || index} className="group hover:bg-white/[0.03] transition-colors">
                        {/* Material Column */}
                        <td className="py-3.5 px-4 max-w-sm">
                          <Link
                            href={`/materials/${encodeURIComponent(item.id)}?code=${encodeURIComponent(item.legacy_code)}&desc=${encodeURIComponent(item.description)}&partNumber=${encodeURIComponent(item.part_number || "")}&manufacturer=${encodeURIComponent(item.manufacturer || "")}&category=${encodeURIComponent(item.category || "")}&uom=${encodeURIComponent(item.uom || "")}&org=${encodeURIComponent(item.organization || selectedOrg)}`}
                            className="font-medium text-white group-hover:text-[#A8DD73] transition-colors truncate block no-underline"
                          >
                            {item.item_name || item.description}
                          </Link>
                          <div className="text-[11px] font-mono text-zinc-500 truncate mt-0.5">
                            {item.legacy_code} {item.part_number ? `· P/N: ${item.part_number}` : ""}
                          </div>
                        </td>

                        {/* Action Column */}
                        <td className="py-3.5 px-4 whitespace-nowrap text-zinc-300 font-medium">
                          {actionLabel}
                        </td>

                        {/* Status Column */}
                        <td className="py-3.5 px-4 whitespace-nowrap">
                          {statusBadge}
                        </td>

                        {/* Time Column */}
                        <td className="py-3.5 px-4 text-right whitespace-nowrap text-zinc-400 font-mono text-[11px]">
                          {relativeTime}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Section 5 — Quick Actions */}
        <div className="space-y-3 pt-2">
          <div className="flex items-center justify-between gap-3 flex-wrap">
            <div className="flex items-center gap-2.5">
              <span className="text-xs font-mono font-semibold uppercase tracking-wider text-zinc-400">
                Quick Actions
              </span>
              <span className="text-[10px] font-mono uppercase px-2 py-0.5 rounded-md bg-[#A8DD73]/10 text-[#A8DD73] border border-[#A8DD73]/20 font-medium">
                {isNationalAdmin ? "National Sovereign Role" : `${selectedOrg} Enterprise Role`}
              </span>
            </div>
            <span className="text-[11px] text-zinc-500 font-mono hidden sm:inline">
              {isNationalAdmin
                ? "Sovereign adjudication, global directory & neural matching"
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
    </CpseLayout>
  );
}
