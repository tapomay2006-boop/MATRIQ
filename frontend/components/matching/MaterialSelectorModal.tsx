"use client";

import React, { useState } from "react";
import { X, Search, Building2, Check, ArrowRight } from "lucide-react";
import { SourceMaterial } from "@/lib/types/matching";
import { cn } from "@/lib/utils";

interface MaterialSelectorModalProps {
  isOpen: boolean;
  onClose: () => void;
  materials: SourceMaterial[];
  selectedMaterialId: string;
  onSelect: (material: SourceMaterial) => void;
}

export default function MaterialSelectorModal({
  isOpen,
  onClose,
  materials,
  selectedMaterialId,
  onSelect,
}: MaterialSelectorModalProps) {
  const [search, setSearch] = useState("");

  if (!isOpen) return null;

  const filtered = materials.filter(
    (m) =>
      m.legacyCode.toLowerCase().includes(search.toLowerCase()) ||
      m.description.toLowerCase().includes(search.toLowerCase()) ||
      m.organization.toLowerCase().includes(search.toLowerCase()) ||
      m.itemName.toLowerCase().includes(search.toLowerCase())
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="w-full max-w-2xl rounded-[28px] border border-white/15 bg-[#121013] p-6 shadow-[0_25px_70px_rgba(0,0,0,0.8)] flex flex-col max-h-[85vh]">
        {/* Modal Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight">
              Select CPSE Source Material
            </h3>
            <p className="text-xs text-white/50 mt-0.5">
              Choose an ingested CPSE record to evaluate against the National Directory
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Search */}
        <div className="relative mt-4 mb-3">
          <Search className="w-4 h-4 text-white/40 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            placeholder="Search by legacy code, CPSE organization, or description..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full bg-white/[0.04] border border-white/10 rounded-xl pl-9 pr-4 py-2.5 text-xs text-white placeholder-white/40 focus:outline-none focus:border-[#A8DD73] transition-colors"
            autoFocus
          />
        </div>

        {/* List of items */}
        <div className="space-y-2.5 overflow-y-auto pr-1 flex-1 mt-2">
          {filtered.length === 0 ? (
            <div className="py-12 text-center text-white/40 text-xs">
              No CPSE materials match your search.
            </div>
          ) : (
            filtered.map((mat) => {
              const isSelected = mat.id === selectedMaterialId;

              return (
                <div
                  key={mat.id}
                  onClick={() => {
                    onSelect(mat);
                    onClose();
                  }}
                  className={cn(
                    "p-4 rounded-2xl border transition-all cursor-pointer flex items-center justify-between gap-4",
                    isSelected
                      ? "bg-[#A8DD73]/10 border-[#A8DD73]"
                      : "bg-white/[0.02] border-white/10 hover:border-white/20 hover:bg-white/[0.05]"
                  )}
                >
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded-md bg-[#A8DD73]/15 text-[#A8DD73] border border-[#A8DD73]/30 font-mono font-bold text-[11px]">
                        {mat.organization}
                      </span>
                      <span className="font-mono text-xs font-semibold text-white/90">
                        {mat.legacyCode}
                      </span>
                    </div>

                    <h4 className="text-xs font-semibold text-white">
                      {mat.itemName}
                    </h4>

                    <p className="text-[11px] text-white/50 line-clamp-1">
                      {mat.description}
                    </p>

                    <div className="flex items-center gap-2 pt-1 text-[10px] text-white/40">
                      <span>OEM: {mat.manufacturer}</span>
                      <span>•</span>
                      <span>P/N: {mat.partNumber}</span>
                      <span>•</span>
                      <span className="text-[#A8DD73]">
                        {mat.candidates.length} national candidate(s)
                      </span>
                    </div>
                  </div>

                  <div className="shrink-0">
                    {isSelected ? (
                      <div className="w-8 h-8 rounded-full bg-[#A8DD73] text-black flex items-center justify-center">
                        <Check className="w-4 h-4" />
                      </div>
                    ) : (
                      <div className="w-8 h-8 rounded-full bg-white/5 border border-white/10 flex items-center justify-center text-white/40 group-hover:text-white">
                        <ArrowRight className="w-4 h-4" />
                      </div>
                    )}
                  </div>
                </div>
              );
            })
          )}
        </div>

        {/* Modal Footer */}
        <div className="pt-4 mt-3 border-t border-white/10 flex justify-end">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-full bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-semibold text-white transition-colors"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
