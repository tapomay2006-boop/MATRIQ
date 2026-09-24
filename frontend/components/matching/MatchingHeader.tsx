"use client";

import React from "react";
import Link from "next/link";
import { ArrowLeft, Cpu, Sparkles, Activity, Layers, Database } from "lucide-react";
import { SourceMaterial } from "@/lib/types/matching";

interface MatchingHeaderProps {
  currentSource: SourceMaterial;
  onOpenSelector: () => void;
  availableCount: number;
}

export default function MatchingHeader({
  currentSource,
  onOpenSelector,
  availableCount,
}: MatchingHeaderProps) {
  return (
    <div className="space-y-4 mb-8">
      {/* Breadcrumb & Top Navigation */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-2 text-xs text-white/50">
          <Link
            href="/"
            className="hover:text-white transition-colors inline-flex items-center gap-1.5"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            <span>National Platform</span>
          </Link>
          <span>/</span>
          <span className="text-white/80">AI Material Deduplication</span>
          <span>/</span>
          <span className="text-[#A8DD73] font-mono font-medium">
            {currentSource.legacyCode}
          </span>
        </div>

        {/* Switch Source Material Button */}
        <button
          onClick={onOpenSelector}
          className="inline-flex items-center gap-2 px-3.5 py-1.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 hover:border-[#A8DD73]/40 text-xs font-semibold text-white transition-all shadow-sm group"
        >
          <Database className="w-3.5 h-3.5 text-[#A8DD73] group-hover:scale-110 transition-transform" />
          <span>Switch CPSE Item</span>
          <span className="ml-1 px-1.5 py-0.5 rounded-full bg-[#A8DD73]/20 text-[#A8DD73] font-mono text-[10px] font-bold">
            {availableCount} items
          </span>
        </button>
      </div>

      {/* Main Title & AI Model Indicators */}
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4 pt-1">
        <div>
          <div className="flex flex-wrap items-center gap-2.5 mb-1.5">
            <h1
              className="text-3xl sm:text-4xl text-white tracking-tight"
              style={{
                fontFamily: "var(--font-heading)",
                fontWeight: 400,
                letterSpacing: "-0.02em",
              }}
            >
              NEMISYS AI{" "}
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Material Matching
              </span>
            </h1>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-[#A8DD73]/10 border border-[#A8DD73]/30 text-[#A8DD73] text-[11px] font-mono font-bold tracking-wider uppercase">
              <span className="w-1.5 h-1.5 rounded-full bg-[#A8DD73] animate-ping" />
              Siamese/CMRL v2.4
            </span>
          </div>
          <p className="text-xs sm:text-sm text-white/60 max-w-3xl leading-relaxed">
            Neural semantic cross-matching of heterogeneous CPSE legacy inventory items
            against the National Standardized Materials Directory.
          </p>
        </div>

        {/* Engine Telemetry Badges */}
        <div className="flex flex-wrap items-center gap-2">
          <div className="px-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/10 flex items-center gap-2 text-xs">
            <Cpu className="w-3.5 h-3.5 text-[#A8DD73]" />
            <span className="text-white/40">Latency:</span>
            <span className="font-mono text-white font-medium">38 ms</span>
          </div>

          <div className="px-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/10 flex items-center gap-2 text-xs">
            <Layers className="w-3.5 h-3.5 text-[#A8DD73]" />
            <span className="text-white/40">Embedding:</span>
            <span className="font-mono text-white font-medium">768-D Dense</span>
          </div>

          <div className="px-3 py-1.5 rounded-xl bg-white/[0.03] border border-white/10 flex items-center gap-2 text-xs">
            <Activity className="w-3.5 h-3.5 text-[#A8DD73]" />
            <span className="text-white/40">Review Threshold:</span>
            <span className="font-mono text-[#A8DD73] font-semibold">≥ 85%</span>
          </div>
        </div>
      </div>
    </div>
  );
}
