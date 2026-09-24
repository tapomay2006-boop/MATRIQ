"use client";

import React, { useState } from "react";
import { X, Copy, Check, FileJson, Layers, Tag } from "lucide-react";
import { CandidateMatch, SourceMaterial } from "@/lib/types/matching";
import { toast } from "sonner";

interface MaterialSpecsModalProps {
  isOpen: boolean;
  onClose: () => void;
  source: SourceMaterial;
  candidate: CandidateMatch;
}

export default function MaterialSpecsModal({
  isOpen,
  onClose,
  source,
  candidate,
}: MaterialSpecsModalProps) {
  const [activeTab, setActiveTab] = useState<"spec" | "json">("spec");
  const [copied, setCopied] = useState(false);

  if (!isOpen) return null;

  const jsonPayload = {
    source_material: {
      organization: source.organization,
      organization_name: source.organizationName,
      legacy_code: source.legacyCode,
      description: source.description,
      item_name: source.itemName,
      part_number: source.partNumber,
      manufacturer: source.manufacturer,
      uom: source.uom,
      equipment_compatibility: source.equipmentCompatibility,
      material_type: source.materialType,
      category: source.category,
      specification: source.specification,
    },
    national_candidate: {
      national_code: candidate.nationalCode,
      item_name: candidate.itemName,
      description: candidate.description,
      manufacturer: candidate.manufacturer,
      part_number: candidate.partNumber,
      category: candidate.category,
      uom: candidate.uom,
      equipment_compatibility: candidate.equipmentCompatibility,
      specification: candidate.specification,
      confidence_score: candidate.confidence,
      semantic_similarity: candidate.semanticScore,
      syntactic_similarity: candidate.syntacticScore,
      status: candidate.status,
    },
  };

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(jsonPayload, null, 2));
    setCopied(true);
    toast.success("Payload copied to clipboard");
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/80 backdrop-blur-md animate-in fade-in duration-200">
      <div className="w-full max-w-3xl rounded-[28px] border border-white/15 bg-[#121013] p-6 shadow-[0_25px_70px_rgba(0,0,0,0.8)] flex flex-col max-h-[85vh]">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-white/10">
          <div>
            <h3 className="text-lg font-bold text-white tracking-tight">
              Material Technical Specification Audit
            </h3>
            <p className="text-xs text-white/50 mt-0.5">
              Deep attribute inspection for {source.legacyCode} vs {candidate.nationalCode}
            </p>
          </div>
          <button
            onClick={onClose}
            className="p-2 rounded-full bg-white/5 hover:bg-white/10 text-white/60 hover:text-white transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Tab switchers */}
        <div className="flex items-center justify-between mt-4 mb-3">
          <div className="flex items-center gap-2 p-1 bg-white/5 rounded-full border border-white/10">
            <button
              onClick={() => setActiveTab("spec")}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
                activeTab === "spec"
                  ? "bg-[#A8DD73] text-black shadow-sm"
                  : "text-white/60 hover:text-white"
              }`}
            >
              Structured Comparison
            </button>
            <button
              onClick={() => setActiveTab("json")}
              className={`px-3 py-1 rounded-full text-xs font-semibold transition-all ${
                activeTab === "json"
                  ? "bg-[#A8DD73] text-black shadow-sm"
                  : "text-white/60 hover:text-white"
              }`}
            >
              JSON Contract
            </button>
          </div>

          {activeTab === "json" && (
            <button
              onClick={handleCopyJson}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg bg-white/5 hover:bg-white/10 border border-white/10 text-xs font-mono text-white/80 hover:text-white transition-colors"
            >
              {copied ? (
                <Check className="w-3.5 h-3.5 text-[#A8DD73]" />
              ) : (
                <Copy className="w-3.5 h-3.5" />
              )}
              <span>{copied ? "Copied" : "Copy JSON"}</span>
            </button>
          )}
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto pr-1 mt-2">
          {activeTab === "spec" ? (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Source CPSE panel */}
              <div className="p-4 rounded-2xl bg-white/[0.02] border border-white/10 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-white/5">
                  <span className="font-mono text-xs font-bold text-[#A8DD73]">
                    {source.organization} Source
                  </span>
                  <span className="font-mono text-xs text-white/60">
                    {source.legacyCode}
                  </span>
                </div>
                <div className="space-y-2 text-xs">
                  <div>
                    <span className="text-white/40 block text-[10px]">Description</span>
                    <p className="text-white/90 font-medium">{source.description}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Item Name</span>
                    <p className="text-white/90">{source.itemName}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Part Number</span>
                    <p className="font-mono text-[#A8DD73]">{source.partNumber}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Manufacturer</span>
                    <p className="text-white/90">{source.manufacturer}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">UOM</span>
                    <p className="font-mono text-white/90">{source.uom}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Equipment Compatibility</span>
                    <p className="text-white/90">{source.equipmentCompatibility}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Specification</span>
                    <p className="text-white/90">{source.specification}</p>
                  </div>
                </div>
              </div>

              {/* Candidate panel */}
              <div className="p-4 rounded-2xl bg-white/[0.02] border border-[#A8DD73]/30 space-y-3">
                <div className="flex items-center justify-between pb-2 border-b border-white/5">
                  <span className="font-mono text-xs font-bold text-white">
                    National Catalog
                  </span>
                  <span className="font-mono text-xs text-[#A8DD73]">
                    {candidate.nationalCode}
                  </span>
                </div>
                <div className="space-y-2 text-xs">
                  <div>
                    <span className="text-white/40 block text-[10px]">Standardized Description</span>
                    <p className="text-white/90 font-medium">{candidate.description}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Item Name</span>
                    <p className="text-white/90">{candidate.itemName}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Part Number</span>
                    <p className="font-mono text-[#A8DD73]">{candidate.partNumber}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Manufacturer</span>
                    <p className="text-white/90">{candidate.manufacturer}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">UOM</span>
                    <p className="font-mono text-white/90">{candidate.uom}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Equipment Compatibility</span>
                    <p className="text-white/90">{candidate.equipmentCompatibility}</p>
                  </div>
                  <div>
                    <span className="text-white/40 block text-[10px]">Specification</span>
                    <p className="text-white/90">{candidate.specification}</p>
                  </div>
                </div>
              </div>
            </div>
          ) : (
            <pre className="p-4 rounded-2xl bg-black/60 border border-white/10 font-mono text-xs text-white/80 overflow-x-auto">
              {JSON.stringify(jsonPayload, null, 2)}
            </pre>
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
