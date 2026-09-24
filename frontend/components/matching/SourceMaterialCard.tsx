"use client";

import React, { useState } from "react";
import {
  Building2,
  Tag,
  Copy,
  Check,
  Wrench,
  Layers,
  FileText,
  Boxes,
  ShieldAlert,
  Search,
} from "lucide-react";
import { SourceMaterial } from "@/lib/types/matching";
import { toast } from "sonner";

interface SourceMaterialCardProps {
  source: SourceMaterial;
  onOpenSelector: () => void;
  onViewSpecs: () => void;
}

export default function SourceMaterialCard({
  source,
  onOpenSelector,
  onViewSpecs,
}: SourceMaterialCardProps) {
  const [copied, setCopied] = useState(false);

  const handleCopyCode = () => {
    navigator.clipboard.writeText(source.legacyCode);
    setCopied(true);
    toast.success(`Copied ${source.legacyCode} to clipboard`);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="rounded-[24px] border border-white/10 bg-[#121013]/90 backdrop-blur-xl p-5 sm:p-6 shadow-[0_20px_50px_rgba(0,0,0,0.4)] flex flex-col justify-between relative overflow-hidden">
      {/* Decorative gradient glow top-left */}
      <div className="absolute -top-16 -left-16 w-36 h-36 bg-[#A8DD73]/10 rounded-full blur-3xl pointer-events-none" />

      <div>
        {/* Top Header Badge Row */}
        <div className="flex flex-wrap items-center justify-between gap-2.5 pb-4 border-b border-white/5">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-1 rounded-md bg-[#A8DD73]/15 text-[#A8DD73] border border-[#A8DD73]/30 font-mono font-bold text-xs">
              {source.organization}
            </span>
            <span className="text-xs text-white/50 font-medium">
              {source.organizationName}
            </span>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={handleCopyCode}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/70 hover:text-white font-mono text-xs transition-colors"
              title="Click to copy legacy code"
            >
              <Tag className="w-3 h-3 text-[#A8DD73]" />
              <span>{source.legacyCode}</span>
              {copied ? (
                <Check className="w-3 h-3 text-[#A8DD73]" />
              ) : (
                <Copy className="w-3 h-3 text-white/40" />
              )}
            </button>
            <button
              onClick={onOpenSelector}
              className="p-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-white/60 hover:text-white transition-colors"
              title="Find another material"
            >
              <Search className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>

        {/* Legacy Description */}
        <div className="py-4">
          <span className="text-[10px] font-mono uppercase tracking-wider text-white/40 block mb-1">
            Legacy Procurement Description (CPSE Raw Text)
          </span>
          <p className="text-sm sm:text-base font-semibold text-white/95 leading-snug tracking-tight bg-white/[0.02] border border-white/5 p-3 rounded-xl">
            {source.description}
          </p>
        </div>

        {/* Structured Attribute Grid */}
        <div className="pt-2">
          <span className="text-[10px] font-mono uppercase tracking-wider text-[#A8DD73] block mb-2.5">
            Extracted Material Attributes
          </span>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5 text-xs">
            <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/5">
              <span className="text-[10px] text-white/40 block">Item Name</span>
              <span className="font-semibold text-white mt-0.5 truncate block" title={source.itemName}>
                {source.itemName}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/5">
              <span className="text-[10px] text-white/40 block">OEM Part Number</span>
              <span className="font-mono font-bold text-[#A8DD73] mt-0.5 truncate block" title={source.partNumber}>
                {source.partNumber}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/5">
              <span className="text-[10px] text-white/40 block">Manufacturer</span>
              <span className="font-semibold text-white mt-0.5 truncate block" title={source.manufacturer}>
                {source.manufacturer}
              </span>
            </div>

            <div className="p-2.5 rounded-xl bg-white/[0.02] border border-white/5">
              <span className="text-[10px] text-white/40 block">Unit of Measure</span>
              <span className="font-mono text-white/90 mt-0.5 block">
                {source.uom}
              </span>
            </div>

            <div className="col-span-2 p-2.5 rounded-xl bg-white/[0.02] border border-white/5">
              <span className="text-[10px] text-white/40 block">Equipment Compatibility</span>
              <span className="font-medium text-white/90 mt-0.5 truncate block" title={source.equipmentCompatibility}>
                {source.equipmentCompatibility}
              </span>
            </div>

            <div className="col-span-2 p-2.5 rounded-xl bg-white/[0.02] border border-white/5">
              <span className="text-[10px] text-white/40 block">Specification</span>
              <span className="font-medium text-white/90 mt-0.5 truncate block" title={source.specification}>
                {source.specification}
              </span>
            </div>
          </div>
        </div>
      </div>

      {/* Footer Info & Modal Trigger */}
      <div className="mt-4 pt-3 border-t border-white/5 flex flex-wrap items-center justify-between gap-2 text-xs">
        <div className="flex items-center gap-2">
          <span className="inline-block w-2 h-2 rounded-full bg-[#A8DD73]" />
          <span className="text-white/50 text-[11px]">
            Status: <strong className="text-white font-medium">Equivalency Ingestion Active</strong>
          </span>
        </div>

        <button
          onClick={onViewSpecs}
          className="inline-flex items-center gap-1.5 text-[11px] font-semibold text-[#A8DD73] hover:text-[#B8E77A] transition-colors"
        >
          <FileText className="w-3.5 h-3.5" />
          <span>Full Spec Audit</span>
        </button>
      </div>
    </div>
  );
}
