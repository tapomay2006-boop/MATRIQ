"use client";

import React, { useEffect, useState } from "react";
import {
  Database,
  Building2,
  CheckCircle2,
  AlertTriangle,
  RefreshCw,
  Layers,
  Sparkles,
} from "lucide-react";
import { apiClient } from "@/lib/api/client";
import { MaterialQualityStats } from "@/lib/types/material";

export default function DashboardMetrics() {
  const [stats, setStats] = useState<MaterialQualityStats | null>(null);
  const [orgsCount, setOrgsCount] = useState<number | null>(null);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [isOffline, setIsOffline] = useState<boolean>(false);

  const fetchMetrics = async () => {
    setIsLoading(true);
    setIsOffline(false);
    try {
      // Fetch both quality statistics and organizations concurrently
      const [qualityData, orgsList] = await Promise.allSettled([
        apiClient.materials.getQuality(),
        apiClient.materials.getOrganizations(),
      ]);

      if (qualityData.status === "fulfilled") {
        setStats(qualityData.value);
      } else {
        // Fallback quality stats if empty
        setStats({
          total_materials: 0,
          organizations: 0,
          missing_uom: 0,
          missing_manufacturer: 0,
          missing_part_number: 0,
          missing_category: 0,
        });
      }

      if (orgsList.status === "fulfilled") {
        setOrgsCount(orgsList.value.length);
      } else if (qualityData.status === "fulfilled") {
        setOrgsCount(qualityData.value.organizations);
      } else {
        setOrgsCount(0);
      }
    } catch {
      setIsOffline(true);
      setStats({
        total_materials: 0,
        organizations: 0,
        missing_uom: 0,
        missing_manufacturer: 0,
        missing_part_number: 0,
        missing_category: 0,
      });
      setOrgsCount(0);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
  }, []);

  // Compute attribute completeness rate deterministically
  const total = stats?.total_materials || 0;
  const missingTotal =
    (stats?.missing_part_number || 0) +
    (stats?.missing_manufacturer || 0) +
    (stats?.missing_uom || 0) +
    (stats?.missing_category || 0);

  const maxPossibleAttributes = total * 4;
  const completenessRate =
    maxPossibleAttributes > 0
      ? Math.max(0, Math.round(((maxPossibleAttributes - missingTotal) / maxPossibleAttributes) * 100))
      : 100;

  const requiringReviewCount =
    (stats?.missing_part_number || 0) + (stats?.missing_manufacturer || 0);

  return (
    <div className="w-full space-y-3">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-zinc-300">
            Catalog Intelligence Overview
          </h3>
          <span className="w-1.5 h-1.5 rounded-full bg-[#A8DD73]" />
        </div>

        <button
          onClick={fetchMetrics}
          disabled={isLoading}
          className="inline-flex items-center gap-1.5 text-xs text-zinc-400 hover:text-white transition-colors cursor-pointer disabled:opacity-40"
          title="Refresh metrics from API"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? "animate-spin text-[#A8DD73]" : ""}`} />
          <span className="hidden sm:inline">Sync Data</span>
        </button>
      </div>

      {/* 4 Metric Cards */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 sm:gap-4">
        {/* Metric 1: Total Materials */}
        <div className="p-4 sm:p-5 rounded-2xl bg-[#121013]/90 border border-white/10 hover:border-white/20 transition-all shadow-lg">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">Total Materials</span>
            <div className="w-7 h-7 rounded-lg bg-[#A8DD73]/10 border border-[#A8DD73]/20 flex items-center justify-center text-[#A8DD73]">
              <Database className="w-3.5 h-3.5" />
            </div>
          </div>
          {isLoading ? (
            <div className="h-7 w-16 bg-white/5 rounded animate-pulse" />
          ) : (
            <div className="flex items-baseline gap-2">
              <span className="text-2xl sm:text-3xl font-extrabold font-mono text-white tracking-tight">
                {total.toLocaleString()}
              </span>
              <span className="text-[11px] text-zinc-500 font-mono">items</span>
            </div>
          )}
          <p className="text-[11px] text-zinc-500 mt-1.5 truncate">
            Standardized catalog records
          </p>
        </div>

        {/* Metric 2: CPSE Organizations */}
        <div className="p-4 sm:p-5 rounded-2xl bg-[#121013]/90 border border-white/10 hover:border-white/20 transition-all shadow-lg">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">CPSE Entities</span>
            <div className="w-7 h-7 rounded-lg bg-sky-500/10 border border-sky-500/20 flex items-center justify-center text-sky-400">
              <Building2 className="w-3.5 h-3.5" />
            </div>
          </div>
          {isLoading ? (
            <div className="h-7 w-12 bg-white/5 rounded animate-pulse" />
          ) : (
            <div className="flex items-baseline gap-2">
              <span className="text-2xl sm:text-3xl font-extrabold font-mono text-white tracking-tight">
                {(orgsCount !== null ? orgsCount : stats?.organizations || 0).toLocaleString()}
              </span>
              <span className="text-[11px] text-zinc-500 font-mono">orgs</span>
            </div>
          )}
          <p className="text-[11px] text-zinc-500 mt-1.5 truncate">
            Integrated public enterprises
          </p>
        </div>

        {/* Metric 3: Attribute Completeness Rate */}
        <div className="p-4 sm:p-5 rounded-2xl bg-[#121013]/90 border border-white/10 hover:border-white/20 transition-all shadow-lg">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">Completeness</span>
            <div className="w-7 h-7 rounded-lg bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <CheckCircle2 className="w-3.5 h-3.5" />
            </div>
          </div>
          {isLoading ? (
            <div className="h-7 w-16 bg-white/5 rounded animate-pulse" />
          ) : (
            <div className="flex items-baseline gap-2">
              <span className="text-2xl sm:text-3xl font-extrabold font-mono text-[#A8DD73] tracking-tight">
                {completenessRate}%
              </span>
              <span className="text-[11px] text-zinc-500 font-mono">quality</span>
            </div>
          )}
          <p className="text-[11px] text-zinc-500 mt-1.5 truncate">
            Canonical attribute completeness
          </p>
        </div>

        {/* Metric 4: Records Requiring Review */}
        <div className="p-4 sm:p-5 rounded-2xl bg-[#121013]/90 border border-white/10 hover:border-white/20 transition-all shadow-lg">
          <div className="flex items-center justify-between text-zinc-400 mb-2">
            <span className="text-xs font-medium">Review Queue</span>
            <div className="w-7 h-7 rounded-lg bg-amber-500/10 border border-amber-500/20 flex items-center justify-center text-amber-400">
              <AlertTriangle className="w-3.5 h-3.5" />
            </div>
          </div>
          {isLoading ? (
            <div className="h-7 w-14 bg-white/5 rounded animate-pulse" />
          ) : (
            <div className="flex items-baseline gap-2">
              <span className="text-2xl sm:text-3xl font-extrabold font-mono text-white tracking-tight">
                {requiringReviewCount.toLocaleString()}
              </span>
              <span className="text-[11px] text-zinc-500 font-mono">flags</span>
            </div>
          )}
          <p className="text-[11px] text-zinc-500 mt-1.5 truncate">
            Missing OEM P/N or make attributes
          </p>
        </div>
      </div>
    </div>
  );
}

