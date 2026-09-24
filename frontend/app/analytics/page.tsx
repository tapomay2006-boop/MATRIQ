"use client";

import React from "react";
import Link from "next/link";
import { BarChart3, TrendingUp, PieChart, ShieldCheck } from "lucide-react";
import CpseLayout from "@/components/layout/CpseLayout";

export default function AnalyticsPage() {
  return (
    <CpseLayout>
      <main className="flex-1 flex flex-col px-4 sm:px-8 lg:px-10 py-6 sm:py-8 max-w-[1400px] w-full space-y-6">
        {/* Header */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-4 border-b border-white/5">
          <div>
            <div className="inline-flex items-center gap-2 mb-2 px-3 py-1 rounded-full bg-[#A8DD73]/10 border border-[#A8DD73]/25">
              <BarChart3 className="w-3.5 h-3.5 text-[#A8DD73]" />
              <span className="text-xs font-medium text-[#A8DD73]">
                Insights · Harmonization Reports
              </span>
            </div>
            <h1
              className="text-3xl sm:text-4xl font-normal tracking-tight"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              <span className="text-white">Harmonization </span>
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Analytics &amp; Reports
              </span>
            </h1>
            <p className="text-sm text-zinc-400 mt-1 max-w-2xl">
              CPSE-level catalog consolidation insights, duplicate elimination efficiency, and procurement alignment analytics.
            </p>
          </div>
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/10 text-xs text-zinc-400 shrink-0">
            <ShieldCheck className="w-4 h-4 text-[#A8DD73]" />
            <span>Quarterly Audit Ready</span>
          </div>
        </div>

        {/* Analytics Highlights */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 space-y-1">
            <span className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Consolidation Potential</span>
            <div className="text-2xl font-bold text-[#A8DD73]">24.8%</div>
            <p className="text-[11px] text-zinc-500">Estimated inventory duplicate reduction</p>
          </div>
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 space-y-1">
            <span className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Standardization Index</span>
            <div className="text-2xl font-bold text-white">89.4%</div>
            <p className="text-[11px] text-zinc-500">Master registry mapping coverage</p>
          </div>
          <div className="p-5 rounded-2xl bg-[#121013]/90 border border-white/10 space-y-1">
            <span className="text-xs text-zinc-400 uppercase tracking-wider font-semibold">Catalog Entities Audited</span>
            <div className="text-2xl font-bold text-sky-400">1,420</div>
            <p className="text-[11px] text-zinc-500">Active records in current namespace</p>
          </div>
        </div>

        {/* Report Download or Preview */}
        <div className="p-8 rounded-2xl bg-[#121013]/90 border border-white/10 text-center space-y-3">
          <TrendingUp className="w-8 h-8 text-[#A8DD73] mx-auto" />
          <h2 className="text-base font-semibold text-white">Automated Audit &amp; Reconciliation Report</h2>
          <p className="text-xs text-zinc-400 max-w-md mx-auto">
            Comprehensive breakdown of item noun standardization, OEM part cross-references, and legacy code deduplication.
          </p>
        </div>
      </main>
    </CpseLayout>
  );
}
