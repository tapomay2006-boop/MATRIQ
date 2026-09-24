"use client";

import React, { useState, useEffect, useMemo, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import {
  Package,
  Search,
  Building2,
  Filter,
  ArrowUpDown,
  ExternalLink,
  Edit3,
  Check,
  Copy,
  Loader2,
  RefreshCw,
  Plus,
  UploadCloud,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  X,
  Save,
  Tag,
  Wrench,
  Layers,
  Database,
  CheckCircle2,
  Clock,
} from "lucide-react";
import { toast } from "sonner";
import CpseLayout from "@/components/layout/CpseLayout";
import NationalLayout from "@/components/layout/NationalLayout";
import { apiClient } from "@/lib/api/client";
import { MaterialRecord } from "@/lib/types/material";
import { cn } from "@/lib/utils";

export default function MaterialsPage() {
  const { data: session } = useSession();
  const router = useRouter();

  // Role detection
  const userRole = session?.user?.role || "cpse_admin";
  const isNationalAdmin = userRole === "national_admin";
  const defaultCpseOrg = (session?.user as any)?.organization || "CCL";
  const userOrg = isNationalAdmin ? undefined : defaultCpseOrg;

  // Data state
  const [materials, setMaterials] = useState<MaterialRecord[]>([]);
  const [totalCount, setTotalCount] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);
  const [totalPages, setTotalPages] = useState(1);
  const [isLoading, setIsLoading] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [counts, setCounts] = useState<{ total: number; assigned: number; unassigned: number }>({
    total: 0,
    assigned: 0,
    unassigned: 0,
  });

  // Filter state
  const [searchQuery, setSearchQuery] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [selectedStatus, setSelectedStatus] = useState<"ALL" | "ASSIGNED" | "PENDING_REVIEW">("ALL");

  // Edit Modal State
  const [editingMaterial, setEditingMaterial] = useState<MaterialRecord | null>(null);
  const [editFormData, setEditFormData] = useState({
    description: "",
    part_number: "",
    manufacturer: "",
    category: "",
    uom: "",
    specification: "",
    equipment_compatibility: "",
  });
  const [isSavingEdit, setIsSavingEdit] = useState(false);

  // Copied feedback state
  const [copiedCode, setCopiedCode] = useState<string | null>(null);

  // Debounce search input
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(searchQuery.trim());
      setPage(1);
    }, 350);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  // Fetch materials from live PostgreSQL backend strictly scoped to user's CPSE
  const fetchMaterials = useCallback(async (isSilent = false) => {
    if (!isSilent) setIsLoading(true);
    else setIsRefreshing(true);

    try {
      const orgParam = userOrg;

      const [res, assignedRes, unassignedRes] = await Promise.all([
        apiClient.materials.list({
          organization: orgParam,
          status: selectedStatus === "ALL" ? undefined : selectedStatus,
          search: debouncedSearch || undefined,
          page,
          page_size: pageSize,
        }),
        apiClient.materials
          .list({
            organization: orgParam,
            status: "ASSIGNED",
            page_size: 1,
          })
          .catch(() => null),
        apiClient.materials
          .list({
            organization: orgParam,
            status: "PENDING_REVIEW",
            page_size: 1,
          })
          .catch(() => null),
      ]);

      setMaterials(res.items || []);
      setTotalCount(res.total || 0);
      setTotalPages(res.total_pages || Math.ceil((res.total || 0) / pageSize) || 1);

      const assignedTotal = assignedRes?.total ?? 0;
      const unassignedTotal = unassignedRes?.total ?? 0;
      const totalCombined = assignedTotal + unassignedTotal;

      setCounts({
        total: totalCombined || res.total || 0,
        assigned: assignedTotal,
        unassigned: unassignedTotal,
      });
    } catch (err) {
      console.error("Failed to load materials catalog:", err);
      toast.error("Failed to load catalog records from backend.");
    } finally {
      setIsLoading(false);
      setIsRefreshing(false);
    }
  }, [userOrg, selectedStatus, debouncedSearch, page, pageSize]);

  useEffect(() => {
    fetchMaterials();
  }, [fetchMaterials]);

  // Copy to clipboard helper
  const handleCopy = (code: string) => {
    navigator.clipboard.writeText(code);
    setCopiedCode(code);
    toast.success(`Copied ${code} to clipboard`);
    setTimeout(() => setCopiedCode(null), 1500);
  };

  // Open Edit Modal
  const handleOpenEdit = (material: MaterialRecord) => {
    setEditingMaterial(material);
    setEditFormData({
      description: material.description || "",
      part_number: material.part_number && material.part_number !== "N/A" ? material.part_number : "",
      manufacturer: material.manufacturer && material.manufacturer !== "N/A" ? material.manufacturer : "",
      category: material.category || "",
      uom: material.uom || "NOS",
      specification: material.specification || "",
      equipment_compatibility: material.equipment_compatibility || "",
    });
  };

  // Save Edit Changes via PUT /api/v1/materials/{id}
  const handleSaveEdit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!editingMaterial) return;

    setIsSavingEdit(true);
    try {
      const updated = await apiClient.materials.update(editingMaterial.id, {
        description: editFormData.description.trim(),
        part_number: editFormData.part_number.trim() || null as any,
        manufacturer: editFormData.manufacturer.trim() || null as any,
        category: editFormData.category.trim() || null as any,
        uom: editFormData.uom.trim() || null as any,
        specification: editFormData.specification.trim() || null as any,
        equipment_compatibility: editFormData.equipment_compatibility.trim() || null as any,
      });

      // Update state in place
      setMaterials((prev) =>
        prev.map((m) => (m.id === editingMaterial.id ? { ...m, ...updated } : m))
      );

      toast.success(`Material ${editingMaterial.legacy_code} updated successfully!`);
      setEditingMaterial(null);
    } catch (err: any) {
      console.error("Error updating material:", err);
      toast.error(err?.message || "Failed to save material updates to backend.");
    } finally {
      setIsSavingEdit(false);
    }
  };

  // Content Layout selection
  const LayoutComponent = isNationalAdmin ? NationalLayout : CpseLayout;

  return (
    <LayoutComponent>
      <main className="flex-1 flex flex-col px-4 sm:px-8 lg:px-10 py-6 sm:py-8 max-w-[1500px] w-full mx-auto space-y-6">
        {/* Page Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-4 border-b border-white/5">
          <div>
            <div className="inline-flex items-center gap-2 mb-2 px-3 py-1 rounded-full bg-[#A8DD73]/10 border border-[#A8DD73]/25">
              <Package className="w-3.5 h-3.5 text-[#A8DD73]" />
              <span className="text-xs font-semibold text-[#A8DD73]">
                {isNationalAdmin
                  ? "Sovereign Master Directory · All CPSE Records"
                  : `Enterprise Material Catalog · ${defaultCpseOrg} Node`}
              </span>
            </div>
            <h1
              className="text-3xl sm:text-4xl font-normal tracking-tight"
              style={{ fontFamily: "var(--font-heading)" }}
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
                {isNationalAdmin ? "Master Catalog" : `${defaultCpseOrg} Inventory`}
              </span>
            </h1>
            <p className="text-sm text-zinc-400 mt-1 max-w-2xl">
              {isNationalAdmin
                ? "Unified material records across all reporting Indian CPSE nodes with attribute governance."
                : `Live catalog explorer for ${defaultCpseOrg}. View and edit canonical attributes or upload new batches.`}
            </p>
          </div>

          <div className="flex items-center gap-3 shrink-0">
            <button
              onClick={() => fetchMaterials(true)}
              disabled={isRefreshing}
              className="flex items-center gap-2 px-3.5 py-2 rounded-xl bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-zinc-300 hover:text-white transition-colors cursor-pointer"
              title="Refresh catalog list"
            >
              <RefreshCw className={cn("w-3.5 h-3.5", isRefreshing && "animate-spin text-[#A8DD73]")} />
              <span>Refresh</span>
            </button>

            {!isNationalAdmin && (
              <Link
                href="/upload"
                className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#A8DD73] hover:bg-[#bbf082] text-black font-semibold text-xs transition-all shadow-md shadow-[#A8DD73]/20 shrink-0 no-underline"
              >
                <UploadCloud className="w-4 h-4" />
                <span>Upload Data</span>
              </Link>
            )}
          </div>
        </div>

        {/* Filter Controls Bar */}
        <div className="p-4 rounded-2xl bg-[#121013] border border-white/10 flex flex-col md:flex-row items-center justify-between gap-4">
          {/* Search Input */}
          <div className="relative w-full md:w-96">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-zinc-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search code, description, part #, make..."
              className="w-full pl-10 pr-8 py-2 rounded-xl bg-white/5 border border-white/10 focus:border-[#A8DD73] text-xs sm:text-sm text-white placeholder:text-zinc-500 focus:outline-none transition-colors"
            />
            {searchQuery && (
              <button
                onClick={() => setSearchQuery("")}
                className="absolute right-2.5 top-1/2 -translate-y-1/2 text-zinc-400 hover:text-white p-1"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            )}
          </div>

          {/* Org Filter & Status & Summary */}
          <div className="flex flex-wrap items-center gap-3 w-full md:w-auto justify-between md:justify-end">
            {/* Status Segmented Controls */}
            <div className="flex items-center gap-1 p-1 rounded-xl bg-white/[0.04] border border-white/10 text-xs">
              <button
                type="button"
                onClick={() => { setSelectedStatus("ALL"); setPage(1); }}
                className={cn(
                  "px-3 py-1.5 rounded-lg font-medium transition-all cursor-pointer",
                  selectedStatus === "ALL"
                    ? "bg-[#A8DD73] text-black font-semibold shadow-sm"
                    : "text-zinc-400 hover:text-white"
                )}
              >
                All ({counts.total})
              </button>
              <button
                type="button"
                onClick={() => { setSelectedStatus("ASSIGNED"); setPage(1); }}
                className={cn(
                  "px-3 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 cursor-pointer",
                  selectedStatus === "ASSIGNED"
                    ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/30 font-semibold"
                    : "text-zinc-400 hover:text-white"
                )}
              >
                <Sparkles className="w-3 h-3 text-emerald-400" />
                <span>Assigned ({counts.assigned})</span>
              </button>
              <button
                type="button"
                onClick={() => { setSelectedStatus("PENDING_REVIEW"); setPage(1); }}
                className={cn(
                  "px-3 py-1.5 rounded-lg font-medium transition-all flex items-center gap-1.5 cursor-pointer",
                  selectedStatus === "PENDING_REVIEW"
                    ? "bg-amber-500/20 text-amber-300 border border-amber-500/30 font-semibold"
                    : "text-zinc-400 hover:text-white"
                )}
              >
                <Clock className="w-3 h-3 text-amber-400" />
                <span>Unassigned ({counts.unassigned})</span>
              </button>
            </div>

            {/* CPSE Node Badge (Scoped to user's CPSE - other CPSEs cannot be selected) */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.04] border border-white/10 text-xs text-zinc-300">
              <Building2 className="w-3.5 h-3.5 text-[#A8DD73]" />
              <span className="font-semibold text-white">{defaultCpseOrg}</span>
              <span className="text-zinc-500">· Node Scoped</span>
            </div>

            {/* Total Count Badge */}
            <div className="text-xs text-zinc-400 font-mono pl-1">
              Count: <span className="font-bold text-white">{totalCount.toLocaleString()}</span>
            </div>
          </div>
        </div>

        {/* Data Table Container */}
        <div className="rounded-2xl border border-white/10 bg-[#121013] overflow-hidden shadow-xl">
          {isLoading ? (
            <div className="py-24 text-center space-y-3">
              <Loader2 className="w-8 h-8 animate-spin text-[#A8DD73] mx-auto" />
              <p className="text-xs text-zinc-400">Querying live material master records from database...</p>
            </div>
          ) : materials.length === 0 ? (
            <div className="py-20 text-center space-y-3 p-6">
              <Package className="w-10 h-10 text-zinc-600 mx-auto" />
              <h3 className="text-base font-semibold text-white">No Material Records Found</h3>
              <p className="text-xs text-zinc-400 max-w-md mx-auto">
                {searchQuery
                  ? `No items matching "${searchQuery}" in ${defaultCpseOrg} catalog.`
                  : `No materials currently registered in ${defaultCpseOrg} catalog.`}
              </p>
              {searchQuery && (
                <button
                  onClick={() => setSearchQuery("")}
                  className="mt-2 px-4 py-1.5 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-zinc-300 cursor-pointer"
                >
                  Clear Search
                </button>
              )}
            </div>
          ) : (
            <div className="overflow-x-auto no-scrollbar">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-white/10 bg-white/[0.02] text-zinc-400 font-medium">
                    <th className="py-3.5 px-4 font-mono uppercase tracking-wider text-[11px]">National ID</th>
                    <th className="py-3.5 px-3 font-mono uppercase tracking-wider text-[11px]">Legacy Code</th>
                    {isNationalAdmin && (
                      <th className="py-3.5 px-3 font-mono uppercase tracking-wider text-[11px]">CPSE</th>
                    )}
                    <th className="py-3.5 px-4 uppercase tracking-wider text-[11px]">Description</th>
                    <th className="py-3.5 px-3 font-mono uppercase tracking-wider text-[11px]">OEM Part #</th>
                    <th className="py-3.5 px-3 uppercase tracking-wider text-[11px]">Manufacturer</th>
                    <th className="py-3.5 px-3 uppercase tracking-wider text-[11px]">Category</th>
                    <th className="py-3.5 px-3 uppercase tracking-wider text-[11px]">Status</th>
                    <th className="py-3.5 px-3 uppercase tracking-wider text-[11px]">UOM</th>
                    <th className="py-3.5 px-4 text-right uppercase tracking-wider text-[11px]">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-white/5 font-sans">
                  {materials.map((item) => {
                    const hasPn = item.part_number && item.part_number !== "N/A" && item.part_number !== "NA";
                    const isCopied = copiedCode === item.legacy_code;

                    return (
                      <tr
                        key={item.id}
                        className="hover:bg-white/[0.03] transition-colors group"
                      >
                        {/* National ID */}
                        <td className="py-3.5 px-4 font-mono whitespace-nowrap">
                          {item.national_id ? (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-500/10 border border-emerald-500/25 text-emerald-400 font-bold text-[11px] shadow-sm">
                              <Sparkles className="w-3 h-3 text-emerald-400" />
                              {item.national_id}
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-amber-500/10 border border-amber-500/25 text-amber-300 font-medium text-[10px]">
                              <Clock className="w-3 h-3 text-amber-400" />
                              Unassigned
                            </span>
                          )}
                        </td>

                        {/* Legacy Code */}
                        <td className="py-3.5 px-3 font-mono font-bold text-white whitespace-nowrap">
                          <div className="flex items-center gap-1.5">
                            <span>{item.legacy_code}</span>
                            <button
                              onClick={() => handleCopy(item.legacy_code)}
                              className="text-zinc-500 hover:text-[#A8DD73] transition-colors p-0.5 cursor-pointer"
                              title="Copy item code"
                            >
                              {isCopied ? (
                                <Check className="w-3 h-3 text-[#A8DD73]" />
                              ) : (
                                <Copy className="w-3 h-3" />
                              )}
                            </button>
                          </div>
                        </td>

                        {/* CPSE Organization (National Admin View) */}
                        {isNationalAdmin && (
                          <td className="py-3.5 px-3 whitespace-nowrap">
                            <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-white/10 text-white border border-white/10">
                              {item.organization}
                            </span>
                          </td>
                        )}

                        {/* Description */}
                        <td className="py-3.5 px-4 text-zinc-200 max-w-xs sm:max-w-md truncate font-medium">
                          {item.description}
                        </td>

                        {/* OEM Part Number */}
                        <td className="py-3.5 px-3 font-mono whitespace-nowrap">
                          {hasPn ? (
                            <span className="text-[#A8DD73] font-semibold">
                              {item.part_number}
                            </span>
                          ) : (
                            <span className="text-zinc-600 font-normal italic">Unspecified</span>
                          )}
                        </td>

                        {/* Manufacturer / Make */}
                        <td className="py-3.5 px-3 text-zinc-300 whitespace-nowrap">
                          {item.manufacturer && item.manufacturer !== "N/A" ? (
                            <span>{item.manufacturer}</span>
                          ) : (
                            <span className="text-zinc-600 italic">Unspecified</span>
                          )}
                        </td>

                        {/* Category */}
                        <td className="py-3.5 px-3 text-zinc-400 whitespace-nowrap">
                          {item.category ? (
                            <span className="px-2 py-0.5 rounded bg-white/5 border border-white/5 text-[11px]">
                              {item.category}
                            </span>
                          ) : (
                            <span className="text-zinc-600 italic">—</span>
                          )}
                        </td>

                        {/* Status */}
                        <td className="py-3.5 px-3 whitespace-nowrap">
                          {item.national_id || item.status === "ASSIGNED" ? (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-emerald-400">
                              <CheckCircle2 className="w-3.5 h-3.5" />
                              Harmonized
                            </span>
                          ) : (
                            <span className="inline-flex items-center gap-1 text-[11px] font-semibold text-amber-400">
                              <Clock className="w-3.5 h-3.5" />
                              Pending Review
                            </span>
                          )}
                        </td>

                        {/* UOM */}
                        <td className="py-3.5 px-3 font-mono text-zinc-300 whitespace-nowrap">
                          {item.uom || "NOS"}
                        </td>

                        {/* Actions */}
                        <td className="py-3.5 px-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-2">
                            {/* Edit Button */}
                            <button
                              onClick={() => handleOpenEdit(item)}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-[#A8DD73]/20 hover:text-[#A8DD73] text-zinc-300 font-semibold text-[11px] transition-colors cursor-pointer border border-transparent hover:border-[#A8DD73]/30"
                              title="Edit material attributes"
                            >
                              <Edit3 className="w-3 h-3" />
                              <span>Edit</span>
                            </button>

                            {/* View Details Link */}
                            <Link
                              href={`/materials/${encodeURIComponent(item.id)}?code=${encodeURIComponent(
                                item.legacy_code
                              )}&org=${encodeURIComponent(item.organization)}&desc=${encodeURIComponent(
                                item.description
                              )}&partNumber=${encodeURIComponent(
                                item.part_number || ""
                              )}&manufacturer=${encodeURIComponent(
                                item.manufacturer || ""
                              )}&uom=${encodeURIComponent(item.uom || "")}&category=${encodeURIComponent(
                                item.category || ""
                              )}&specs=${encodeURIComponent(item.specification || "")}`}
                              className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/15 text-white font-semibold text-[11px] transition-colors cursor-pointer no-underline border border-white/10"
                              title="Open full canonical details"
                            >
                              <span>View</span>
                              <ExternalLink className="w-3 h-3" />
                            </Link>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination Controls */}
          {totalPages > 1 && (
            <div className="p-4 border-t border-white/5 flex items-center justify-between text-xs text-zinc-400">
              <div>
                Showing <span className="text-white font-semibold">{(page - 1) * pageSize + 1}</span> to{" "}
                <span className="text-white font-semibold">
                  {Math.min(page * pageSize, totalCount)}
                </span>{" "}
                of <span className="text-white font-semibold">{totalCount.toLocaleString()}</span> items
              </div>

              <div className="flex items-center gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page <= 1 || isLoading}
                  className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 text-white cursor-pointer transition-colors"
                  title="Previous page"
                >
                  <ChevronLeft className="w-4 h-4" />
                </button>
                <span className="font-mono text-white">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                  disabled={page >= totalPages || isLoading}
                  className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 disabled:opacity-30 text-white cursor-pointer transition-colors"
                  title="Next page"
                >
                  <ChevronRight className="w-4 h-4" />
                </button>
              </div>
            </div>
          )}
        </div>
      </main>

      {/* Edit Material Master Modal */}
      {editingMaterial && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-150">
          <div className="w-full max-w-xl rounded-2xl bg-[#121013] border border-white/15 shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-white/10 flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-xs font-mono font-bold text-[#A8DD73] px-2 py-0.5 rounded bg-[#A8DD73]/15 border border-[#A8DD73]/30">
                    {editingMaterial.organization}
                  </span>
                  <span className="text-xs font-mono text-zinc-400">
                    {editingMaterial.legacy_code}
                  </span>
                </div>
                <h3 className="text-base font-bold text-white mt-1">
                  Edit Material Attributes
                </h3>
              </div>

              <button
                onClick={() => setEditingMaterial(null)}
                className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Modal Form Content */}
            <form onSubmit={handleSaveEdit} className="p-6 space-y-4 overflow-y-auto flex-1">
              {/* Description */}
              <div className="space-y-1.5">
                <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-400 block">
                  Material Description *
                </label>
                <textarea
                  required
                  rows={3}
                  value={editFormData.description}
                  onChange={(e) =>
                    setEditFormData((prev) => ({ ...prev, description: e.target.value }))
                  }
                  className="w-full p-3 rounded-xl bg-white/5 border border-white/10 focus:border-[#A8DD73] text-xs sm:text-sm text-white focus:outline-none transition-colors"
                />
              </div>

              {/* Part Number & Manufacturer */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-400 block">
                    OEM Part Number
                  </label>
                  <input
                    type="text"
                    value={editFormData.part_number}
                    onChange={(e) =>
                      setEditFormData((prev) => ({ ...prev, part_number: e.target.value }))
                    }
                    placeholder="e.g. 6205-2RS"
                    className="w-full p-2.5 rounded-xl bg-white/5 border border-white/10 focus:border-[#A8DD73] text-xs sm:text-sm text-white focus:outline-none transition-colors font-mono"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-400 block">
                    Make / Manufacturer
                  </label>
                  <input
                    type="text"
                    value={editFormData.manufacturer}
                    onChange={(e) =>
                      setEditFormData((prev) => ({ ...prev, manufacturer: e.target.value }))
                    }
                    placeholder="e.g. SKF, BHEL"
                    className="w-full p-2.5 rounded-xl bg-white/5 border border-white/10 focus:border-[#A8DD73] text-xs sm:text-sm text-white focus:outline-none transition-colors"
                  />
                </div>
              </div>

              {/* Category & UOM */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="space-y-1.5">
                  <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-400 block">
                    Category / Material Family
                  </label>
                  <input
                    type="text"
                    value={editFormData.category}
                    onChange={(e) =>
                      setEditFormData((prev) => ({ ...prev, category: e.target.value }))
                    }
                    placeholder="e.g. BEARING, VALVE"
                    className="w-full p-2.5 rounded-xl bg-white/5 border border-white/10 focus:border-[#A8DD73] text-xs sm:text-sm text-white focus:outline-none transition-colors"
                  />
                </div>

                <div className="space-y-1.5">
                  <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-400 block">
                    Unit of Measurement (UOM)
                  </label>
                  <input
                    type="text"
                    value={editFormData.uom}
                    onChange={(e) =>
                      setEditFormData((prev) => ({ ...prev, uom: e.target.value }))
                    }
                    placeholder="e.g. NOS, SET, MTR, KGS"
                    className="w-full p-2.5 rounded-xl bg-white/5 border border-white/10 focus:border-[#A8DD73] text-xs sm:text-sm text-white focus:outline-none transition-colors font-mono"
                  />
                </div>
              </div>

              {/* Technical Specifications */}
              <div className="space-y-1.5">
                <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-400 block">
                  Specifications &amp; Dimensions
                </label>
                <textarea
                  rows={2}
                  value={editFormData.specification}
                  onChange={(e) =>
                    setEditFormData((prev) => ({ ...prev, specification: e.target.value }))
                  }
                  placeholder="Standard technical specs, dimensions, tolerances..."
                  className="w-full p-2.5 rounded-xl bg-white/5 border border-white/10 focus:border-[#A8DD73] text-xs text-zinc-200 focus:outline-none transition-colors"
                />
              </div>

              {/* Equipment Compatibility */}
              <div className="space-y-1.5">
                <label className="text-[11px] uppercase tracking-wider font-bold text-zinc-400 block">
                  Equipment Compatibility
                </label>
                <input
                  type="text"
                  value={editFormData.equipment_compatibility}
                  onChange={(e) =>
                    setEditFormData((prev) => ({ ...prev, equipment_compatibility: e.target.value }))
                  }
                  placeholder="Compatible machine models or plant systems..."
                  className="w-full p-2.5 rounded-xl bg-white/5 border border-white/10 focus:border-[#A8DD73] text-xs sm:text-sm text-white focus:outline-none transition-colors"
                />
              </div>

              {/* Footer Actions */}
              <div className="pt-4 border-t border-white/10 flex items-center justify-end gap-3">
                <button
                  type="button"
                  onClick={() => setEditingMaterial(null)}
                  className="px-4 py-2 rounded-xl bg-white/5 hover:bg-white/10 text-xs font-semibold text-zinc-300 hover:text-white transition-colors cursor-pointer"
                >
                  Cancel
                </button>

                <button
                  type="submit"
                  disabled={isSavingEdit}
                  className="flex items-center gap-2 px-5 py-2 rounded-xl bg-[#A8DD73] hover:bg-[#bbf082] disabled:opacity-50 text-black font-semibold text-xs transition-all shadow-md shadow-[#A8DD73]/20 cursor-pointer"
                >
                  {isSavingEdit ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <Save className="w-3.5 h-3.5" />
                  )}
                  <span>{isSavingEdit ? "Saving..." : "Save to Database"}</span>
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </LayoutComponent>
  );
}
