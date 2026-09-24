"use client";

import React, { use, useState, useEffect, Suspense } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowLeft, Copy, Check, Sparkles, Building2, Tag, Wrench, Package, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import CpseLayout from "@/components/layout/CpseLayout";
import { apiClient } from "@/lib/api/client";
import { MaterialRecord } from "@/lib/types/material";
import { cn } from "@/lib/utils";

interface MaterialDetailContentProps {
  id: string;
}

function MaterialDetailContent({ id }: MaterialDetailContentProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [copied, setCopied] = useState(false);
  const [copiedPN, setCopiedPN] = useState(false);
  const [liveRecord, setLiveRecord] = useState<MaterialRecord | null>(null);

  // Read URL search params
  const codeParam = searchParams.get("code");
  const orgParam = searchParams.get("org");
  const descParam = searchParams.get("desc");
  const nameParam = searchParams.get("name");
  const partNumberParam = searchParams.get("partNumber");
  const manufacturerParam = searchParams.get("manufacturer");
  const categoryParam = searchParams.get("category");
  const uomParam = searchParams.get("uom");
  const specsParam = searchParams.get("specs");
  const equipParam = searchParams.get("equip");
  const gradeParam = searchParams.get("grade");
  const scoreParam = searchParams.get("score");

  // Fetch from live database if not fully populated via URL params
  useEffect(() => {
    if (!descParam && id) {
      apiClient.materials
        .getById(id)
        .then((rec) => setLiveRecord(rec))
        .catch(() => {
          if (codeParam) {
            apiClient.materials
              .list({ search: codeParam, limit: 1 })
              .then((res) => {
                if (res.items && res.items.length > 0) setLiveRecord(res.items[0]);
              })
              .catch(() => {});
          }
        });
    }
  }, [id, descParam, codeParam]);

  // Resolved canonical fields
  const description = descParam || liveRecord?.description || "Industrial Material Item";
  const legacyCode = codeParam || liveRecord?.legacy_code || id;
  const organization = orgParam || liveRecord?.organization || "CPSE";
  const partNumber = partNumberParam || liveRecord?.part_number || "Standard Part";
  const manufacturer = manufacturerParam || liveRecord?.manufacturer || "Standard Registry Entity";
  const category = categoryParam || liveRecord?.category || "Industrial Supplies & Equipment";
  const uom = uomParam || liveRecord?.uom || "NOS";
  const equipmentCompatibility = equipParam || liveRecord?.equipment_compatibility || "General Industrial Machinery";
  const materialType = gradeParam || liveRecord?.material_type || "Standard Commercial Grade";
  const specification = specsParam || liveRecord?.specification || "Standard Technical Specifications";
  const probabilityScore = scoreParam ? parseInt(scoreParam, 10) : 96;

  const isHighMatch = probabilityScore >= 88;

  const handleCopySpecs = () => {
    const text = `Material: ${description}
Code: ${legacyCode}
OEM Part Number: ${partNumber}
Manufacturer: ${manufacturer}
Category: ${category}
UOM: ${uom}
Equipment Compatibility: ${equipmentCompatibility}
Material Grade: ${materialType}
Specifications: ${specification}`;

    navigator.clipboard.writeText(text);
    setCopied(true);
    toast.success("Specifications copied to clipboard!");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleCopyPN = () => {
    if (!partNumber || partNumber === "Standard Part") return;
    navigator.clipboard.writeText(partNumber);
    setCopiedPN(true);
    toast.success(`Part number ${partNumber} copied!`);
    setTimeout(() => setCopiedPN(false), 1500);
  };

  return (
    <main className="flex-1 flex flex-col px-4 sm:px-8 lg:px-12 py-6 sm:py-8 max-w-5xl w-full mx-auto space-y-6">
      {/* Navigation Breadcrumb */}
      <div className="flex items-center justify-between gap-4">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center gap-2 text-xs font-semibold text-zinc-400 hover:text-white transition-colors cursor-pointer"
        >
          <ArrowLeft className="w-4 h-4" />
          <span>Back</span>
        </button>

        <div className="flex items-center gap-2">
          <span
            className={cn(
              "px-3 py-1 rounded-full font-mono text-xs font-bold border",
              isHighMatch
                ? "bg-[#A8DD73]/20 text-[#A8DD73] border-[#A8DD73]/40"
                : "bg-amber-400/20 text-amber-300 border-amber-400/40"
            )}
          >
            {probabilityScore}% Match Probability
          </span>
          <span className="px-2.5 py-1 rounded-lg bg-white/10 text-white font-mono text-xs font-bold">
            {organization}
          </span>
        </div>
      </div>

      {/* Main Product Header Card */}
      <div className="p-6 sm:p-8 rounded-2xl border border-white/10 bg-[#121013] shadow-xl space-y-4">
        <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4">
          <div className="space-y-2 flex-1">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-semibold text-zinc-400">
                Item Code:
              </span>
              <span className="font-mono text-xs font-bold text-white bg-white/5 px-2 py-0.5 rounded border border-white/10">
                {legacyCode}
              </span>
            </div>

            <h1 className="text-xl sm:text-2xl lg:text-3xl font-bold text-white tracking-tight leading-snug">
              {description}
            </h1>
          </div>

          <button
            onClick={handleCopySpecs}
            className="inline-flex items-center gap-2 px-4 py-2.5 rounded-xl bg-[#A8DD73] hover:bg-[#bbf082] text-black font-semibold text-xs transition-all shadow-md shadow-[#A8DD73]/20 shrink-0 cursor-pointer"
          >
            {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
            <span>{copied ? "Copied" : "Copy Specifications"}</span>
          </button>
        </div>
      </div>

      {/* 8 Canonical Product Specifications Grid */}
      <div className="p-6 sm:p-8 rounded-2xl border border-white/10 bg-[#121013] shadow-xl space-y-6">
        <h2 className="text-sm uppercase tracking-wider font-bold text-zinc-400">
          Canonical Specifications (8 Standard Attributes)
        </h2>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-xs">
          {/* 1. Description */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 sm:col-span-2">
            <span className="text-[11px] text-zinc-500 uppercase font-bold tracking-wider block">
              Item Description
            </span>
            <p className="font-medium text-white text-sm mt-1.5 leading-relaxed">
              {description}
            </p>
          </div>

          {/* 2. OEM Part Number */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <div className="flex items-center justify-between">
              <span className="text-[11px] text-zinc-500 uppercase font-bold tracking-wider block">
                OEM Part Number
              </span>
              {partNumber && partNumber !== "Standard Part" && (
                <button
                  onClick={handleCopyPN}
                  className="text-[10px] text-zinc-400 hover:text-emerald-400 transition-colors inline-flex items-center gap-1 cursor-pointer"
                  title="Copy part number"
                >
                  {copiedPN ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />}
                  <span>{copiedPN ? "Copied" : "Copy"}</span>
                </button>
              )}
            </div>
            <p className="font-mono font-bold text-emerald-400 text-sm mt-1.5">
              {partNumber}
            </p>
          </div>

          {/* 3. Make / Manufacturer */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <span className="text-[11px] text-zinc-500 uppercase font-bold tracking-wider block">
              Make / Manufacturer
            </span>
            <p className="font-medium text-white text-sm mt-1.5">
              {manufacturer}
            </p>
          </div>

          {/* 4. Category / Material Family */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <span className="text-[11px] text-zinc-500 uppercase font-bold tracking-wider block">
              Category / Material Family
            </span>
            <p className="font-medium text-zinc-200 text-sm mt-1.5">
              {category}
            </p>
          </div>

          {/* 5. Unit of Measurement */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <span className="text-[11px] text-zinc-500 uppercase font-bold tracking-wider block">
              Unit of Measurement (UOM)
            </span>
            <p className="font-mono font-medium text-zinc-200 text-sm mt-1.5">
              {uom}
            </p>
          </div>

          {/* 6. Equipment Compatibility */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <span className="text-[11px] text-zinc-500 uppercase font-bold tracking-wider block">
              Equipment Compatibility
            </span>
            <p className="font-medium text-zinc-200 text-sm mt-1.5">
              {equipmentCompatibility}
            </p>
          </div>

          {/* 7. Material Grade / Metallurgy */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5">
            <span className="text-[11px] text-zinc-500 uppercase font-bold tracking-wider block">
              Material Grade / Metallurgy
            </span>
            <p className="font-medium text-zinc-200 text-sm mt-1.5">
              {materialType}
            </p>
          </div>

          {/* 8. Technical Specifications */}
          <div className="p-4 rounded-xl bg-white/[0.02] border border-white/5 sm:col-span-2">
            <span className="text-[11px] text-zinc-500 uppercase font-bold tracking-wider block">
              Technical Specifications &amp; Dimensions
            </span>
            <p className="text-zinc-300 text-sm mt-1.5 leading-relaxed">
              {specification}
            </p>
          </div>
        </div>
      </div>
    </main>
  );
}

export default function MaterialDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const resolvedParams = use(params);

  return (
    <CpseLayout>
      <Suspense
        fallback={
          <div className="flex-1 flex items-center justify-center p-12 text-zinc-400">
            <span>Loading product details...</span>
          </div>
        }
      >
        <MaterialDetailContent id={resolvedParams.id} />
      </Suspense>
    </CpseLayout>
  );
}
