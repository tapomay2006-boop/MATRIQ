"use client";

import React, { useState } from "react";
import { X, AlertTriangle, XCircle, ShieldAlert } from "lucide-react";
import { CandidateMatch, SourceMaterial } from "@/lib/types/matching";

interface RejectReasonModalProps {
  isOpen: boolean;
  onClose: () => void;
  source: SourceMaterial;
  candidate: CandidateMatch;
  onConfirmReject: (reason: string, comments: string) => void;
}

const REASONS = [
  "OEM Part Number Incompatibility",
  "Dimensional / Tolerance Conflict",
  "Different Equipment Model / Capacity",
  "Metallurgical / Specification Mismatch",
  "Commercial / Packaging UOM Inconsistency",
  "Duplicate / Obsolete Catalog Entry",
  "Other Architectural Deviation",
];

export default function RejectReasonModal({
  isOpen,
  onClose,
  source,
  candidate,
  onConfirmReject,
}: RejectReasonModalProps) {
  const [selectedReason, setSelectedReason] = useState(REASONS[0]);
  const [comments, setComments] = useState("");

  if (!isOpen) return null;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    onConfirmReject(selectedReason, comments);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="w-full max-w-lg rounded-[28px] border border-rose-500/30 bg-[#121013] p-6 shadow-[0_25px_70px_rgba(0,0,0,0.8)] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-full bg-rose-500/20 border border-rose-500/30 flex items-center justify-center">
              <XCircle className="w-4 h-4 text-rose-400" />
            </div>
            <div>
              <h3 className="text-base font-bold text-white tracking-tight">
                Reject Candidate Equivalency
              </h3>
              <p className="text-xs text-white/50">
                Reject <span className="font-mono text-rose-300">{candidate.nationalCode}</span> for{" "}
                <span className="font-mono text-white/80">{source.legacyCode}</span>
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4 mt-4">
          <div>
            <label className="text-xs font-semibold text-white/80 block mb-1.5">
              Reason for Rejection *
            </label>
            <div className="space-y-1.5 max-h-48 overflow-y-auto pr-1">
              {REASONS.map((reason) => (
                <label
                  key={reason}
                  className={`flex items-center gap-2.5 p-2.5 rounded-xl border text-xs cursor-pointer transition-colors ${
                    selectedReason === reason
                      ? "bg-rose-500/15 border-rose-500/40 text-white font-medium"
                      : "bg-white/[0.02] border-white/5 text-white/60 hover:text-white hover:bg-white/[0.04]"
                  }`}
                >
                  <input
                    type="radio"
                    name="rejectReason"
                    value={reason}
                    checked={selectedReason === reason}
                    onChange={() => setSelectedReason(reason)}
                    className="accent-rose-500 text-rose-500"
                  />
                  <span>{reason}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label className="text-xs font-semibold text-white/80 block mb-1.5">
              Technical Audit Notes (Optional)
            </label>
            <textarea
              rows={3}
              value={comments}
              onChange={(e) => setComments(e.target.value)}
              placeholder="Provide technical justification for the national audit log..."
              className="w-full bg-white/[0.04] border border-white/10 rounded-xl p-3 text-xs text-white placeholder-white/30 focus:outline-none focus:border-rose-400 transition-colors"
            />
          </div>

          <div className="pt-3 border-t border-white/10 flex items-center justify-end gap-2.5">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-white transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-4 py-2 rounded-full bg-rose-600 hover:bg-rose-500 text-white text-xs font-bold transition-all shadow-sm"
            >
              Confirm Rejection
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
