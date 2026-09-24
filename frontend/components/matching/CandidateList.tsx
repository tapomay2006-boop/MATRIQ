"use client";

import React, { useState } from "react";
import {
  Sparkles,
  CheckCircle2,
  AlertTriangle,
  Search,
  Check,
  ChevronRight,
  ShieldCheck,
  Send,
  XCircle,
} from "lucide-react";
import { CandidateMatch } from "@/lib/types/matching";
import { cn } from "@/lib/utils";

interface CandidateListProps {
  candidates: CandidateMatch[];
  selectedCandidateId: string;
  onSelectCandidate: (candidateId: string) => void;
}

export default function CandidateList({
  candidates,
  selectedCandidateId,
  onSelectCandidate,
}: CandidateListProps) {
  const [filterQuery, setFilterQuery] = useState("");

  const filteredCandidates = candidates.filter(
    (c) =>
      c.nationalCode.toLowerCase().includes(filterQuery.toLowerCase()) ||
      c.itemName.toLowerCase().includes(filterQuery.toLowerCase()) ||
      c.manufacturer.toLowerCase().includes(filterQuery.toLowerCase()) ||
      c.partNumber.toLowerCase().includes(filterQuery.toLowerCase())
  );

  return (
    <div className="rounded-[24px] border border-white/10 bg-[#121013]/90 backdrop-blur-xl p-5 sm:p-6 shadow-[0_20px_50px_rgba(0,0,0,0.4)] flex flex-col h-full">
      {/* List Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-4 border-b border-white/5">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base sm:text-lg font-bold text-white tracking-tight">
              National Candidates
            </h2>
            <span className="px-2 py-0.5 rounded-full bg-[#A8DD73]/15 text-[#A8DD73] text-[11px] font-mono font-bold">
              {candidates.length} Ranked
            </span>
          </div>
          <p className="text-xs text-white/50 mt-0.5">
            Ranked by multi-modal Siamese neural similarity &amp; entity resolution
          </p>
        </div>

        {/* Filter input */}
        <div className="relative w-full sm:w-56">
          <Search className="w-3.5 h-3.5 text-white/40 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Filter candidates..."
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            className="w-full bg-white/[0.04] border border-white/10 rounded-xl pl-8 pr-3 py-1.5 text-xs text-white placeholder-white/40 focus:outline-none focus:border-[#A8DD73] transition-colors"
          />
        </div>
      </div>

      {/* Candidate Cards */}
      <div className="space-y-3 mt-4 flex-1 overflow-y-auto pr-1 max-h-[640px]">
        {filteredCandidates.length === 0 ? (
          <div className="py-12 text-center text-white/40 text-xs">
            No national candidates match your filter query.
          </div>
        ) : (
          filteredCandidates.map((candidate, idx) => {
            const isSelected = candidate.id === selectedCandidateId;
            const percentage = Math.round(candidate.confidence * 1000) / 10;
            const isHigh = candidate.confidence >= 0.85;
            const isMed = candidate.confidence >= 0.7 && candidate.confidence < 0.85;

            return (
              <div
                key={candidate.id}
                onClick={() => onSelectCandidate(candidate.id)}
                className={cn(
                  "p-4 rounded-2xl border transition-all cursor-pointer relative group",
                  isSelected
                    ? "bg-[#A8DD73]/[0.08] border-[#A8DD73] shadow-[0_0_25px_rgba(168,221,115,0.15)]"
                    : "bg-white/[0.02] border-white/10 hover:border-white/20 hover:bg-white/[0.04]"
                )}
              >
                {/* Top badge row */}
                <div className="flex items-center justify-between gap-2 mb-2">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-xs font-bold text-white/90">
                      {candidate.nationalCode}
                    </span>
                    {idx === 0 && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#A8DD73]/20 text-[#A8DD73] border border-[#A8DD73]/30 text-[10px] font-bold">
                        <Sparkles className="w-2.5 h-2.5" />
                        Recommended
                      </span>
                    )}
                    {candidate.status === "sent_for_review" && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-amber-500/20 text-amber-300 border border-amber-500/30 text-[10px] font-bold">
                        <Send className="w-2.5 h-2.5" />
                        In Review
                      </span>
                    )}
                    {candidate.status === "rejected" && (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-rose-500/20 text-rose-300 border border-rose-500/30 text-[10px] font-bold">
                        <XCircle className="w-2.5 h-2.5" />
                        Rejected
                      </span>
                    )}
                  </div>

                  {/* Confidence pill */}
                  <div
                    className={cn(
                      "px-2.5 py-1 rounded-full font-mono text-xs font-bold inline-flex items-center gap-1.5",
                      isHigh
                        ? "bg-[#A8DD73]/20 text-[#A8DD73] border border-[#A8DD73]/40"
                        : isMed
                        ? "bg-amber-400/20 text-amber-300 border border-amber-400/30"
                        : "bg-rose-400/20 text-rose-300 border border-rose-400/30"
                    )}
                  >
                    <span>{percentage}%</span>
                    <span className="text-[10px] uppercase tracking-wider font-semibold opacity-80">
                      {candidate.confidenceTier}
                    </span>
                  </div>
                </div>

                {/* Candidate title & description */}
                <h3 className="text-sm font-semibold text-white group-hover:text-[#A8DD73] transition-colors leading-tight">
                  {candidate.itemName}
                </h3>
                <p className="text-xs text-white/50 mt-1 line-clamp-2 leading-relaxed">
                  {candidate.description}
                </p>

                {/* Key metadata chips */}
                <div className="flex flex-wrap items-center gap-2 mt-3 pt-2.5 border-t border-white/5 text-[11px]">
                  <span className="text-white/40">
                    OEM: <strong className="text-white/80 font-medium">{candidate.manufacturer}</strong>
                  </span>
                  <span className="text-white/20">•</span>
                  <span className="text-white/40">
                    P/N: <strong className="font-mono text-white/80 font-medium">{candidate.partNumber}</strong>
                  </span>
                  <span className="text-white/20">•</span>
                  <span className="text-white/40">
                    UOM: <strong className="font-mono text-white/80 font-medium">{candidate.uom}</strong>
                  </span>
                </div>

                {/* Progress bar */}
                <div className="w-full bg-white/5 h-1.5 rounded-full mt-3 overflow-hidden">
                  <div
                    className={cn(
                      "h-full rounded-full transition-all duration-500",
                      isHigh ? "bg-[#A8DD73]" : isMed ? "bg-amber-400" : "bg-rose-400"
                    )}
                    style={{ width: `${percentage}%` }}
                  />
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
