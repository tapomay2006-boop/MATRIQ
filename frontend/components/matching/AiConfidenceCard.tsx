"use client";

import React from "react";
import { Sparkles, ShieldCheck, Gauge, Layers, Binary, Cpu } from "lucide-react";
import { CandidateMatch } from "@/lib/types/matching";
import { cn } from "@/lib/utils";

interface AiConfidenceCardProps {
  candidate: CandidateMatch;
}

export default function AiConfidenceCard({ candidate }: AiConfidenceCardProps) {
  const percentage = Math.round(candidate.confidence * 1000) / 10;
  const isHigh = candidate.confidence >= 0.85;
  const isMed = candidate.confidence >= 0.7 && candidate.confidence < 0.85;

  return (
    <div className="rounded-[24px] border border-white/10 bg-[#121013]/90 backdrop-blur-xl p-5 sm:p-6 shadow-[0_20px_50px_rgba(0,0,0,0.4)] flex flex-col justify-between relative overflow-hidden">
      {/* Glow background accent */}
      <div
        className={cn(
          "absolute -bottom-20 -right-20 w-44 h-44 rounded-full blur-3xl pointer-events-none transition-all",
          isHigh
            ? "bg-[#A8DD73]/15"
            : isMed
            ? "bg-amber-500/15"
            : "bg-rose-500/15"
        )}
      />

      <div>
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/5">
          <div className="flex items-center gap-2">
            <Gauge className="w-4 h-4 text-[#A8DD73]" />
            <h3 className="text-sm font-bold text-white tracking-tight">
              AI Confidence Assessment
            </h3>
          </div>
          <span className="text-[10px] font-mono uppercase tracking-wider text-white/40">
            Model: Siamese-CMRL
          </span>
        </div>

        {/* Large Score Display */}
        <div className="py-6 flex flex-col sm:flex-row items-center sm:items-start justify-between gap-4">
          <div>
            <div className="flex items-baseline gap-2">
              <span
                className={cn(
                  "text-5xl sm:text-6xl font-black font-mono tracking-tight",
                  isHigh
                    ? "text-[#A8DD73]"
                    : isMed
                    ? "text-amber-400"
                    : "text-rose-400"
                )}
              >
                {percentage}%
              </span>
              <span className="text-sm text-white/40 font-mono">confidence</span>
            </div>

            <div className="flex items-center gap-2 mt-2">
              <span
                className={cn(
                  "px-2.5 py-0.5 rounded-full text-xs font-bold uppercase tracking-wider font-mono",
                  isHigh
                    ? "bg-[#A8DD73]/20 text-[#A8DD73] border border-[#A8DD73]/40"
                    : isMed
                    ? "bg-amber-400/20 text-amber-300 border border-amber-400/30"
                    : "bg-rose-400/20 text-rose-300 border border-rose-400/30"
                )}
              >
                {candidate.confidenceTier} Confidence Match
              </span>
              {isHigh && (
                <span className="text-xs text-white/60 flex items-center gap-1">
                  <ShieldCheck className="w-3.5 h-3.5 text-[#A8DD73]" />
                  Auto-verification Recommended
                </span>
              )}
            </div>
          </div>

          {/* Threshold Visualizer */}
          <div className="w-full sm:w-48 bg-white/[0.02] border border-white/5 p-3 rounded-2xl">
            <div className="flex justify-between text-[10px] text-white/40 font-mono mb-1.5">
              <span>Thresholds</span>
              <span className="text-[#A8DD73]">≥85% High</span>
            </div>
            <div className="w-full bg-white/5 h-2 rounded-full overflow-hidden flex gap-0.5">
              <div className="h-full bg-rose-500/40 w-[69%]" title="Low (<70%)" />
              <div className="h-full bg-amber-500/40 w-[15%]" title="Medium (70-85%)" />
              <div className="h-full bg-[#A8DD73] w-[16%]" title="High (>85%)" />
            </div>
            <p className="text-[10px] text-white/50 mt-2 leading-tight">
              Scores above 85% qualify for streamlined national equivalency approval.
            </p>
          </div>
        </div>

        {/* Sub-Score Metrics Breakdown */}
        <div className="space-y-2.5 pt-2">
          <span className="text-[10px] font-mono uppercase tracking-wider text-white/40 block">
            Sub-Metric Decomposition
          </span>

          <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 text-xs">
            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
              <div className="flex items-center justify-between">
                <span className="text-white/50 text-[11px]">Semantic Cosine</span>
                <Layers className="w-3 h-3 text-[#A8DD73]" />
              </div>
              <div className="font-mono text-base font-bold text-white mt-1">
                {(candidate.semanticScore * 100).toFixed(1)}%
              </div>
              <span className="text-[10px] text-white/40">768-D dense vector</span>
            </div>

            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
              <div className="flex items-center justify-between">
                <span className="text-white/50 text-[11px]">Syntactic Overlap</span>
                <Binary className="w-3 h-3 text-sky-400" />
              </div>
              <div className="font-mono text-base font-bold text-white mt-1">
                {(candidate.syntacticScore * 100).toFixed(1)}%
              </div>
              <span className="text-[10px] text-white/40">P/N &amp; token correlation</span>
            </div>

            <div className="p-3 rounded-xl bg-white/[0.02] border border-white/5">
              <div className="flex items-center justify-between">
                <span className="text-white/50 text-[11px]">Entity Resolution</span>
                <Cpu className="w-3 h-3 text-amber-400" />
              </div>
              <div className="font-mono text-base font-bold text-white mt-1">
                {(candidate.attributeScore * 100).toFixed(1)}%
              </div>
              <span className="text-[10px] text-white/40">OEM &amp; spec alignment</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
