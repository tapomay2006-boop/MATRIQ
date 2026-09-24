"use client";

import React from "react";
import {
  CheckCircle2,
  AlertTriangle,
  MinusCircle,
  HelpCircle,
  ArrowRight,
  Sparkles,
} from "lucide-react";
import { CandidateMatch, ComparisonAttribute, SourceMaterial } from "@/lib/types/matching";
import { cn } from "@/lib/utils";

interface ComparisonViewProps {
  source: SourceMaterial;
  candidate: CandidateMatch;
}

export default function ComparisonView({ source, candidate }: ComparisonViewProps) {
  const getStatusBadge = (status: ComparisonAttribute["status"]) => {
    switch (status) {
      case "MATCH":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-emerald-500/15 border border-emerald-500/30 text-emerald-400 font-mono text-[11px] font-bold">
            <CheckCircle2 className="w-3 h-3" />
            MATCH
          </span>
        );
      case "SIMILAR":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-sky-500/15 border border-sky-500/30 text-sky-400 font-mono text-[11px] font-bold">
            <Sparkles className="w-3 h-3" />
            SIMILAR
          </span>
        );
      case "CONFLICT":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-amber-500/15 border border-amber-500/30 text-amber-400 font-mono text-[11px] font-bold">
            <AlertTriangle className="w-3 h-3" />
            CONFLICT
          </span>
        );
      case "MISSING":
        return (
          <span className="inline-flex items-center gap-1 px-2.5 py-1 rounded-full bg-slate-500/15 border border-slate-500/30 text-slate-400 font-mono text-[11px] font-bold">
            <MinusCircle className="w-3 h-3" />
            MISSING
          </span>
        );
      default:
        return null;
    }
  };

  return (
    <div className="rounded-[24px] border border-white/10 bg-[#121013]/90 backdrop-blur-xl p-5 sm:p-6 shadow-[0_20px_50px_rgba(0,0,0,0.4)]">
      {/* Header with Title & Selected Material Code */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-5 border-b border-white/5">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              Side-by-Side Attribute Comparison
            </h2>
            <span className="px-2 py-0.5 rounded-full bg-[#A8DD73]/15 text-[#A8DD73] text-[10px] font-mono font-bold">
              Entity Alignment
            </span>
          </div>
          <p className="text-xs text-white/50 mt-0.5">
            Detailed granular parameter matching between CPSE legacy data and National Catalog
          </p>
        </div>

        <div className="flex items-center gap-2 text-xs">
          <div className="px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 font-mono text-white/70">
            {source.organization}: <span className="text-[#A8DD73]">{source.legacyCode}</span>
          </div>
          <ArrowRight className="w-3.5 h-3.5 text-white/30" />
          <div className="px-2.5 py-1 rounded-lg bg-white/5 border border-white/10 font-mono text-white/70">
            National: <span className="text-[#A8DD73]">{candidate.nationalCode}</span>
          </div>
        </div>
      </div>

      {/* Comparison Table */}
      <div className="overflow-x-auto mt-4">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            <tr className="border-b border-white/10 text-white/40 font-mono text-[11px] uppercase">
              <th className="pb-3 pr-4 font-semibold w-1/5">Attribute Field</th>
              <th className="pb-3 px-4 font-semibold w-2/5">
                {source.organization} Record ({source.legacyCode})
              </th>
              <th className="pb-3 px-4 font-semibold w-2/5">
                National Catalog ({candidate.nationalCode})
              </th>
              <th className="pb-3 pl-4 font-semibold text-right w-24">Status</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-white/5">
            {candidate.comparisons.map((comp) => {
              const isMatch = comp.status === "MATCH";
              const isConflict = comp.status === "CONFLICT";
              const isSimilar = comp.status === "SIMILAR";

              return (
                <tr
                  key={comp.field}
                  className={cn(
                    "hover:bg-white/[0.02] transition-colors",
                    isConflict && "bg-amber-500/[0.02]"
                  )}
                >
                  <td className="py-3.5 pr-4 align-top font-medium text-white/80">
                    <div className="font-semibold text-white/90">{comp.label}</div>
                    {comp.notes && (
                      <p className="text-[11px] text-white/40 mt-1 leading-normal font-normal">
                        {comp.notes}
                      </p>
                    )}
                  </td>

                  <td className="py-3.5 px-4 align-top">
                    <span
                      className={cn(
                        "inline-block text-white/90 font-mono text-xs",
                        comp.field === "partNumber" && "text-[#A8DD73] font-bold"
                      )}
                    >
                      {comp.sourceValue || "—"}
                    </span>
                  </td>

                  <td className="py-3.5 px-4 align-top">
                    <span
                      className={cn(
                        "inline-block font-mono text-xs",
                        isMatch
                          ? "text-white/90 font-semibold"
                          : isConflict
                          ? "text-amber-300 font-semibold"
                          : isSimilar
                          ? "text-sky-300 font-medium"
                          : "text-white/70"
                      )}
                    >
                      {comp.candidateValue || "—"}
                    </span>
                  </td>

                  <td className="py-3.5 pl-4 align-top text-right whitespace-nowrap">
                    {getStatusBadge(comp.status)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
