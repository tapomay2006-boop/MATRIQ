"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  ExternalLink,
  Building2,
  CheckCircle2,
  AlertTriangle,
  Tag,
  Hash,
  Wrench,
} from "lucide-react";
import { SearchHit } from "@/lib/types/search";
import { MaterialRecord } from "@/lib/types/material";
import {
  getGoogleSearchUrl,
  getManufacturerUrl,
  buildMaterialGoogleQuery,
} from "@/lib/data/manufacturer-links";

interface SearchHitCardProps {
  hit: SearchHit | MaterialRecord;
  index: number;
}

export default function SearchHitCard({ hit, index }: SearchHitCardProps) {
  // Normalize fields between SearchHit and MaterialRecord
  const isSearchHit = "material_id" in hit;

  const materialId = isSearchHit ? hit.material_id : hit.id;
  const description = isSearchHit
    ? hit.description
    : hit.item_name || hit.description;
  const company = isSearchHit ? hit.company : hit.organization;
  const legacyCode = hit.legacy_code;
  const partNumber = hit.part_number && hit.part_number !== "NA" ? hit.part_number : "";
  const make = isSearchHit
    ? hit.make && hit.make !== "NA"
      ? hit.make
      : ""
    : hit.manufacturer && hit.manufacturer !== "NA"
      ? hit.manufacturer
      : "";
  const uom = hit.uom && hit.uom !== "NA" ? hit.uom : "";
  const matchLevel = isSearchHit
    ? hit.match_level
    : hit.probability_score && hit.probability_score >= 85
      ? "high"
      : "possible";

  const isHigh = matchLevel === "high";
  const isPossible = matchLevel === "possible";
  const identifierMatch = isSearchHit ? hit.identifier_match : false;
  const identifierToken = isSearchHit ? hit.identifier_token : null;

  const siameseScore = isSearchHit
    ? hit.siamese_score
    : hit.probability_score
      ? hit.probability_score / 100
      : null;
  const qdrantScore = isSearchHit ? hit.qdrant_score : null;

  // 1. Google Search Link calculation
  const googleQuery = buildMaterialGoogleQuery({
    description,
    make,
    manufacturer: make,
    company,
    part_number: partNumber,
  });
  const googleUrl = getGoogleSearchUrl({
    description,
    make,
    manufacturer: make,
    company,
    part_number: partNumber,
  });

  // 2. Manufacturer / Company redirect link calculation
  // Prefer specific make/brand, fallback to company entity if valid
  const manufacturerCandidate = make || company || "";
  const mfgInfo = getManufacturerUrl(manufacturerCandidate);

  return (
    <div className="p-5 rounded-2xl bg-[#121013] border border-white/10 hover:border-[#A8DD73]/40 transition-all shadow-md group relative flex flex-col lg:flex-row lg:items-center justify-between gap-6">
      {/* Left Details */}
      <div className="space-y-2 flex-1 min-w-0">
        <div className="flex items-center gap-2.5 flex-wrap">
          {/* Match Level Pill */}
          <span
            className={`inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${isHigh
                ? "bg-emerald-500/15 border border-emerald-500/30 text-emerald-400"
                : isPossible
                  ? "bg-amber-500/15 border border-amber-500/30 text-amber-300"
                  : "bg-white/10 border border-white/15 text-zinc-400"
              }`}
          >
            {isHigh ? (
              <CheckCircle2 className="w-3.5 h-3.5 text-emerald-400" />
            ) : (
              <AlertTriangle className="w-3.5 h-3.5 text-amber-300" />
            )}
            {matchLevel} Match
          </span>

          {identifierMatch && identifierToken && (
            <span className="px-2.5 py-1 rounded-full bg-[#A8DD73]/15 border border-[#A8DD73]/30 text-[#A8DD73] text-xs font-mono">
              Exact Identifier: {identifierToken}
            </span>
          )}

          <span className="text-xs text-zinc-500 font-mono">
            Rank #{index + 1}
          </span>
        </div>

        {/* Material Description Heading */}
        <h3 className="text-base font-semibold text-white group-hover:text-[#A8DD73] transition-colors leading-snug break-words">
          {description}
        </h3>

        {/* Technical Attributes Chips */}
        <div className="flex items-center gap-4 text-xs text-zinc-400 flex-wrap pt-1">
          {company && (
            <span className="flex items-center gap-1.5 text-zinc-300">
              <Building2 className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
              <span>{company}</span>
            </span>
          )}

          {legacyCode && (
            <span className="flex items-center gap-1.5 font-mono text-zinc-300">
              <Hash className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
              <span>{legacyCode}</span>
            </span>
          )}

          {partNumber && (
            <span className="flex items-center gap-1.5 font-mono text-[#A8DD73]">
              <Tag className="w-3.5 h-3.5 text-[#A8DD73] shrink-0" />
              <span>P/N: {partNumber}</span>
            </span>
          )}

          {make && (
            <span className="flex items-center gap-1.5 text-zinc-300">
              <Wrench className="w-3.5 h-3.5 text-zinc-500 shrink-0" />
              <span>Make: {make}</span>
            </span>
          )}

          {uom && (
            <span className="px-2 py-0.5 rounded bg-white/5 border border-white/10 text-[11px] font-mono text-zinc-300">
              UOM: {uom}
            </span>
          )}
        </div>
      </div>

      {/* Right Scores & Actions */}
      <div className="flex flex-row lg:flex-col items-start lg:items-end justify-between gap-4 shrink-0 border-t lg:border-t-0 pt-3 lg:pt-0 border-white/5">
        {/* Scores */}
        <div className="flex items-center gap-2">
          {siameseScore !== null && !isNaN(siameseScore) && (
            <div className="text-right">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">
                Siamese Score
              </span>
              <span className="font-mono text-sm font-bold text-white">
                {(siameseScore * 100).toFixed(1)}%
              </span>
            </div>
          )}
          {qdrantScore !== null && !isNaN(qdrantScore) && (
            <div className="text-right pl-3 border-l border-white/10">
              <span className="text-[10px] text-zinc-500 uppercase tracking-wider block">
                Vector Cosine
              </span>
              <span className="font-mono text-sm font-bold text-zinc-400">
                {(qdrantScore * 100).toFixed(1)}%
              </span>
            </div>
          )}
        </div>

        {/* Action Buttons Group */}
        <div className="flex flex-col items-start lg:items-end gap-2.5 w-full sm:w-auto">
          {/* Primary Action: Review in Matching */}
          <Link
            href={`/matching?materialId=${materialId}&code=${encodeURIComponent(
              legacyCode || ""
            )}&org=${encodeURIComponent(company || "")}&desc=${encodeURIComponent(
              description || ""
            )}&partNumber=${encodeURIComponent(partNumber || "")}`}
            className="flex items-center gap-1.5 px-4 py-2 rounded-xl bg-white/10 hover:bg-[#A8DD73] text-white hover:text-black font-semibold text-xs transition-all cursor-pointer no-underline shadow-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#A8DD73]"
          >
            <span>Review in Matching</span>
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>

          {/* Secondary Actions: Search on Google & Manufacturer */}
          <div className="flex items-center gap-1 sm:gap-2 flex-wrap">
            {/* 1. Google Search Action */}
            {googleUrl && (
              <a
                href={googleUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-[#A8DD73] hover:bg-[#A8DD73]/10 transition-colors cursor-pointer no-underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#A8DD73]"
                title={`Search "${googleQuery}" on Google (opens in new tab)`}
                aria-label={`Search "${googleQuery}" on Google in new tab`}
              >
                <ExternalLink className="w-3.5 h-3.5 shrink-0 text-zinc-500 group-hover:text-[#A8DD73] transition-colors" />
                <span>Search on Google</span>
              </a>
            )}

            {/* 2. Manufacturer / Company Action */}
            {mfgInfo && (
              <a
                href={mfgInfo.url}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs text-zinc-400 hover:text-[#A8DD73] hover:bg-[#A8DD73]/10 transition-colors cursor-pointer no-underline focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-[#A8DD73]"
                title={
                  mfgInfo.isOfficial
                    ? `Visit official ${mfgInfo.name} website: ${mfgInfo.url}`
                    : `Search ${mfgInfo.name} official site on Google`
                }
                aria-label={
                  mfgInfo.isOfficial
                    ? `Visit official ${mfgInfo.name} website`
                    : `Search ${mfgInfo.name} official site on Google`
                }
              >
                <Building2 className="w-3.5 h-3.5 shrink-0 text-zinc-500 group-hover:text-[#A8DD73] transition-colors" />
                <span>Manufacturer</span>
              </a>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

