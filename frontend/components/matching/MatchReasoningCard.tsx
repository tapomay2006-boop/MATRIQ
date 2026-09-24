"use client";

import React from "react";
import { Sparkles, Plus, AlertCircle, Info, CheckCircle2 } from "lucide-react";
import { CandidateMatch, ReasoningFactor } from "@/lib/types/matching";
import { cn } from "@/lib/utils";

interface MatchReasoningCardProps {
  candidate: CandidateMatch;
}

export default function MatchReasoningCard({ candidate }: MatchReasoningCardProps) {
  const getFactorIcon = (type: ReasoningFactor["type"]) => {
    switch (type) {
      case "positive":
        return <Plus className="w-3.5 h-3.5 text-[#A8DD73]" />;
      case "warning":
        return <AlertCircle className="w-3.5 h-3.5 text-amber-400" />;
      case "neutral":
      default:
        return <Info className="w-3.5 h-3.5 text-sky-400" />;
    }
  };

  return (
    <div className="rounded-[24px] border border-white/10 bg-[#121013]/90 backdrop-blur-xl p-5 sm:p-6 shadow-[0_20px_50px_rgba(0,0,0,0.4)]">
      {/* Header */}
      <div className="flex items-center justify-between pb-4 border-b border-white/5">
        <div className="flex items-center gap-2">
          <Sparkles className="w-4 h-4 text-[#A8DD73]" />
          <h3 className="text-sm font-bold text-white tracking-tight">
            Explainable AI Rationale (XAI)
          </h3>
        </div>
        <span className="text-[10px] font-mono text-white/40">
          Transparent Factor Weighting
        </span>
      </div>

      {/* Factors List */}
      <div className="space-y-3 mt-4">
        {candidate.reasoning.map((factor, idx) => {
          const isPositive = factor.type === "positive";
          const isWarning = factor.type === "warning";
          const isNeutral = factor.type === "neutral";

          return (
            <div
              key={idx}
              className={cn(
                "p-3.5 rounded-xl border flex items-start justify-between gap-3 transition-colors",
                isPositive
                  ? "bg-[#A8DD73]/[0.03] border-[#A8DD73]/20"
                  : isWarning
                  ? "bg-amber-500/[0.04] border-amber-500/25"
                  : "bg-white/[0.02] border-white/5"
              )}
            >
              <div className="flex items-start gap-3">
                <div
                  className={cn(
                    "p-1.5 rounded-lg shrink-0 mt-0.5",
                    isPositive
                      ? "bg-[#A8DD73]/15"
                      : isWarning
                      ? "bg-amber-500/15"
                      : "bg-sky-500/15"
                  )}
                >
                  {getFactorIcon(factor.type)}
                </div>
                <div>
                  <h4 className="text-xs font-bold text-white tracking-tight">
                    {factor.title}
                  </h4>
                  <p className="text-xs text-white/60 mt-0.5 leading-relaxed">
                    {factor.detail}
                  </p>
                </div>
              </div>

              {factor.scoreImpact && (
                <span
                  className={cn(
                    "px-2 py-0.5 rounded-md font-mono text-[10px] font-bold shrink-0 self-center",
                    isPositive
                      ? "bg-[#A8DD73]/20 text-[#A8DD73]"
                      : isWarning
                      ? "bg-amber-500/20 text-amber-300"
                      : "bg-sky-500/20 text-sky-300"
                  )}
                >
                  {factor.scoreImpact}
                </span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
