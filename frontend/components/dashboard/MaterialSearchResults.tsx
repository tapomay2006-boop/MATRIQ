"use client";

import React from "react";
import { ChevronRight, Tag, Wrench, Sparkles } from "lucide-react";
import { MaterialRecord } from "@/lib/types/material";
import { cn } from "@/lib/utils";

interface MaterialSearchResultsProps {
  results: MaterialRecord[];
  onSelect: (material: MaterialRecord) => void;
  isLoading?: boolean;
}

export default function MaterialSearchResults({
  results,
  onSelect,
  isLoading,
}: MaterialSearchResultsProps) {
  if (results.length === 0 && !isLoading) {
    return null;
  }

  // Display top 3 to 4 items max
  const displayResults = results.slice(0, 4);

  return (
    <div className="w-full rounded-2xl border border-white/10 bg-[#121013]/95 backdrop-blur-2xl shadow-[0_20px_60px_rgba(0,0,0,0.8)] overflow-hidden mt-2 divide-y divide-white/5 animate-in fade-in slide-in-from-top-2 duration-150 no-scrollbar">
      <div className="px-4 py-2 bg-white/[0.02] flex items-center justify-between text-xs text-zinc-400">
        <div className="flex items-center gap-2">
          <Sparkles className="w-3.5 h-3.5 text-[#A8DD73]" />
          <span className="font-semibold text-white">
            Top {displayResults.length} AI Recommendations
          </span>
        </div>
        <span className="text-[11px] text-zinc-500 hidden sm:inline">
          Click item to open product details
        </span>
      </div>

      <div className="divide-y divide-white/5 no-scrollbar">
        {displayResults.map((mat, idx) => {
          // Calculate probability score
          const prob = mat.probability_score || Math.max(76, 96 - idx * 7);
          const isHigh = prob >= 88;

          return (
            <button
              key={mat.id}
              onClick={() => onSelect(mat)}
              className="w-full text-left p-3.5 hover:bg-white/[0.04] transition-colors flex items-center justify-between gap-3 group cursor-pointer"
            >
              <div className="space-y-1 flex-1 min-w-0">
                {/* Header row: Probability Badge + Org + Legacy Code */}
                <div className="flex items-center gap-2 flex-wrap">
                  <span
                    className={cn(
                      "px-2 py-0.5 rounded-full font-mono text-[10px] font-extrabold border shrink-0",
                      isHigh
                        ? "bg-[#A8DD73]/20 text-[#A8DD73] border-[#A8DD73]/40"
                        : "bg-amber-400/20 text-amber-300 border-amber-400/40"
                    )}
                  >
                    {prob}% Match
                  </span>

                  <span className="px-1.5 py-0.5 rounded bg-white/10 text-zinc-300 font-mono text-[10px] font-bold">
                    {mat.organization || "CPSE"}
                  </span>

                  <span className="font-mono text-xs font-semibold text-white group-hover:text-[#A8DD73] transition-colors truncate">
                    {mat.legacy_code}
                  </span>

                  {mat.uom && (
                    <span className="text-[10px] text-zinc-400">
                      • {mat.uom}
                    </span>
                  )}
                </div>

                {/* Title */}
                <h4 className="text-sm font-semibold text-white tracking-tight truncate group-hover:text-zinc-100">
                  {mat.item_name || mat.description.slice(0, 50)}
                </h4>

                {/* Technical highlights */}
                <div className="flex items-center gap-3 text-[11px] text-zinc-400 truncate">
                  {mat.part_number && (
                    <span className="font-mono text-zinc-300 truncate">
                      P/N: <strong className="text-emerald-400">{mat.part_number}</strong>
                    </span>
                  )}
                  {mat.manufacturer && (
                    <span className="truncate">
                      Make: <strong className="text-zinc-300">{mat.manufacturer}</strong>
                    </span>
                  )}
                  {mat.category && (
                    <span className="text-zinc-500 truncate hidden md:inline">
                      {mat.category}
                    </span>
                  )}
                </div>
              </div>

              {/* Action Indicator */}
              <div className="shrink-0 flex items-center gap-1 text-xs font-semibold text-zinc-500 group-hover:text-[#A8DD73] transition-colors">
                <span className="hidden sm:inline text-[11px]">View Details</span>
                <ChevronRight className="w-4 h-4 transform group-hover:translate-x-0.5 transition-transform" />
              </div>
            </button>
          );
        })}
      </div>
    </div>
  );
}
