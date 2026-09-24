"use client";

import React from "react";
import {
  Send,
  XCircle,
  FileText,
  CheckCircle2,
  AlertCircle,
  RotateCcw,
  Sparkles,
} from "lucide-react";
import { CandidateMatch, SourceMaterial } from "@/lib/types/matching";
import { cn } from "@/lib/utils";

interface ActionFooterProps {
  source: SourceMaterial;
  candidate: CandidateMatch;
  onSendForReview: () => void;
  onOpenRejectModal: () => void;
  onViewSpecs: () => void;
  onResetStatus: () => void;
  isSubmitting?: boolean;
}

export default function ActionFooter({
  source,
  candidate,
  onSendForReview,
  onOpenRejectModal,
  onViewSpecs,
  onResetStatus,
  isSubmitting = false,
}: ActionFooterProps) {
  const isSent = candidate.status === "sent_for_review";
  const isRejected = candidate.status === "rejected";
  const isApproved = candidate.status === "approved";

  return (
    <div className="sticky bottom-6 z-30 w-full mt-8">
      <div className="rounded-[24px] border border-white/15 bg-[#121013]/95 backdrop-blur-2xl p-4 sm:p-5 shadow-[0_25px_60px_rgba(0,0,0,0.8)] flex flex-col sm:flex-row items-center justify-between gap-4">
        {/* Left summary / Status indicator */}
        <div className="flex items-center gap-3 w-full sm:w-auto">
          {isSent ? (
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-amber-500/20 border border-amber-500/30 flex items-center justify-center">
                <Send className="w-4 h-4 text-amber-300" />
              </div>
              <div>
                <p className="text-xs font-bold text-white leading-tight">
                  Submitted for National Admin Review
                </p>
                <p className="text-[11px] text-white/50">
                  Target: <span className="font-mono text-amber-300">{candidate.nationalCode}</span> • Review Queue #REV-2026-9041
                </p>
              </div>
            </div>
          ) : isRejected ? (
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-rose-500/20 border border-rose-500/30 flex items-center justify-center">
                <XCircle className="w-4 h-4 text-rose-300" />
              </div>
              <div>
                <p className="text-xs font-bold text-white leading-tight">
                  Candidate Rejected
                </p>
                <p className="text-[11px] text-white/50">
                  Excluded from automated equivalency mapping
                </p>
              </div>
            </div>
          ) : (
            <div className="flex items-center gap-2.5">
              <div className="w-8 h-8 rounded-full bg-[#A8DD73]/20 border border-[#A8DD73]/30 flex items-center justify-center">
                <Sparkles className="w-4 h-4 text-[#A8DD73]" />
              </div>
              <div>
                <p className="text-xs font-bold text-white leading-tight">
                  Ready for Equivalency Action
                </p>
                <p className="text-[11px] text-white/50">
                  Pairing <span className="font-mono text-[#A8DD73]">{source.legacyCode}</span> with{" "}
                  <span className="font-mono text-white/90">{candidate.nationalCode}</span> (
                  {Math.round(candidate.confidence * 1000) / 10}%)
                </p>
              </div>
            </div>
          )}
        </div>

        {/* Right buttons */}
        <div className="flex flex-wrap items-center justify-end gap-2.5 w-full sm:w-auto">
          {/* Spec details */}
          <button
            onClick={onViewSpecs}
            className="px-4 py-2.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 text-xs font-semibold text-white/80 hover:text-white transition-all inline-flex items-center gap-1.5"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>View Specs</span>
          </button>

          {isSent || isRejected ? (
            <button
              onClick={onResetStatus}
              className="px-4 py-2.5 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-white/80 hover:text-white transition-all inline-flex items-center gap-1.5"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Reset Decision</span>
            </button>
          ) : (
            <>
              {/* Reject button */}
              <button
                onClick={onOpenRejectModal}
                className="px-4 py-2.5 rounded-full bg-rose-500/10 hover:bg-rose-500/20 border border-rose-500/30 hover:border-rose-500/50 text-xs font-semibold text-rose-300 transition-all inline-flex items-center gap-1.5"
              >
                <XCircle className="w-3.5 h-3.5" />
                <span>Reject Match</span>
              </button>

              {/* Send for Review Primary button */}
              <button
                onClick={onSendForReview}
                disabled={isSubmitting}
                className={cn(
                  "px-5 py-2.5 rounded-full bg-[#A8DD73] hover:bg-[#B8E77A] text-black font-bold text-xs transition-all inline-flex items-center gap-2 shadow-[0_0_25px_rgba(168,221,115,0.3)] hover:shadow-[0_0_35px_rgba(168,221,115,0.5)] cursor-pointer disabled:opacity-50"
                )}
              >
                <Send className="w-3.5 h-3.5" />
                <span>{isSubmitting ? "Submitting..." : "Send for Review"}</span>
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
