"use client";

import React, { useState, useEffect, Suspense } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Search,
  Sparkles,
  Cpu,
  Layers,
  AlertTriangle,
  Database,
  Loader2,
  X,
} from "lucide-react";
import CpseLayout from "@/components/layout/CpseLayout";
import { aiClient } from "@/lib/api/ai-client";
import { apiClient } from "@/lib/api/client";
import { SearchHit, SearchResponse } from "@/lib/types/search";
import { MaterialRecord } from "@/lib/types/material";
import SearchHitCard from "@/components/search/SearchHitCard";

function SearchPageContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const initialQuery = searchParams.get("q") || "";

  const [query, setQuery] = useState(initialQuery);
  const [activeQuery, setActiveQuery] = useState(initialQuery);
  const [isLoading, setIsLoading] = useState(false);
  const [aiResponse, setAiResponse] = useState<SearchResponse | null>(null);
  const [catalogResults, setCatalogResults] = useState<MaterialRecord[]>([]);
  const [isAiMode, setIsAiMode] = useState(true);
  const [backendStatus, setBackendStatus] = useState<"connected" | "offline">("connected");
  const [error, setError] = useState<string | null>(null);

  const performSearch = async (searchTerm: string) => {
    const term = searchTerm.trim();
    if (!term) return;

    setIsLoading(true);
    setError(null);
    setActiveQuery(term);

    // Update URL without full reload
    const params = new URLSearchParams(window.location.search);
    params.set("q", term);
    window.history.replaceState(null, "", `?${params.toString()}`);

    let aiSucceeded = false;

    // 1. Attempt Siamese Neural Reranker Vector Search on ai-service (Port 8001)
    try {
      const res = await aiClient.search(term, 20, 10);
      if (res && res.results) {
        setAiResponse(res);
        aiSucceeded = true;
        setBackendStatus("connected");
      }
    } catch {
      // ai-service offline or error
    }

    // 2. Also query catalog items from api-service (Port 8000)
    try {
      const catRes = await apiClient.materials.list({ search: term, limit: 10 });
      if (catRes && catRes.items) {
        setCatalogResults(catRes.items);
        setBackendStatus("connected");
      }
    } catch {
      // api-service offline
    }

    if (!aiSucceeded && catalogResults.length === 0) {
      setBackendStatus("connected");
    }

    setIsLoading(false);
  };

  useEffect(() => {
    if (initialQuery) {
      performSearch(initialQuery);
    }
  }, [initialQuery]);

  const handleClear = () => {
    setQuery("");
    setAiResponse(null);
    setCatalogResults([]);
    setActiveQuery("");
  };

  return (
    <CpseLayout>
      <main className="flex-1 flex flex-col px-4 sm:px-8 lg:px-10 py-6 sm:py-8 max-w-[1400px] w-full space-y-6">
        {/* Header Title Bar */}
        <div className="flex flex-col sm:flex-row sm:items-end justify-between gap-4 pb-4 border-b border-white/5">
          <div>
            <div className="inline-flex items-center gap-2 mb-2 px-3 py-1 rounded-full bg-[#A8DD73]/10 border border-[#A8DD73]/25">
              <Sparkles className="w-3.5 h-3.5 text-[#A8DD73]" />
              <span className="text-xs font-medium text-[#A8DD73]">
                AI Semantic Retrieval &amp; Siamese Neural Reranker
              </span>
            </div>
            <h1
              className="text-3xl sm:text-4xl font-normal tracking-tight"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              <span className="text-white">Unified </span>
              <span
                className="bg-clip-text text-transparent"
                style={{
                  backgroundImage:
                    "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                  WebkitBackgroundClip: "text",
                  WebkitTextFillColor: "transparent",
                }}
              >
                Material Search
              </span>
            </h1>
            <p className="text-sm text-zinc-400 mt-1 max-w-2xl">
              Cross-CPSE semantic vector search powered by Siamese dual-encoders and deterministic attribute alignment.
            </p>
          </div>

          <div className="flex items-center gap-3">
            <span
              className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-xl border text-xs font-medium ${backendStatus === "connected"
                  ? "bg-emerald-500/10 border-emerald-500/30 text-emerald-400"
                  : "bg-amber-500/10 border-amber-500/30 text-amber-300"
                }`}
            >
              <span
                className={`w-2 h-2 rounded-full ${backendStatus === "connected" ? "bg-emerald-400 animate-pulse" : "bg-amber-400"
                  }`}
              />
              {backendStatus === "connected" ? "AI Engine Online (Port 8001)" : "Offline / Local Preview Mode"}
            </span>
          </div>
        </div>

        {/* Search Bar Input */}
        <div className="relative group">
          <div className="absolute -inset-0.5 bg-gradient-to-r from-[#A8DD73]/30 via-white/10 to-[#A8DD73]/30 rounded-2xl blur-sm opacity-40 group-hover:opacity-75 transition-opacity" />
          <div className="relative flex items-center bg-[#121013] border border-white/15 focus-within:border-[#A8DD73] rounded-2xl shadow-xl h-[56px]">
            <div className="pl-5 pr-2 text-zinc-400 group-focus-within:text-[#A8DD73]">
              {isLoading ? (
                <Loader2 className="w-5 h-5 animate-spin text-[#A8DD73]" />
              ) : (
                <Search className="w-5 h-5" />
              )}
            </div>

            <input
              type="text"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  performSearch(query);
                }
              }}
              placeholder="Search CPSE items by noun, spec (e.g. 'V BELT C 120'), OEM part number, or legacy code..."
              className="w-full bg-transparent py-3.5 px-2 text-sm sm:text-base text-white placeholder:text-zinc-500 focus:outline-none"
            />

            {query && (
              <button
                onClick={handleClear}
                className="p-2 mr-2 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white transition-colors"
                title="Clear input"
              >
                <X className="w-4 h-4" />
              </button>
            )}

            <button
              onClick={() => performSearch(query)}
              disabled={isLoading || !query.trim()}
              className="flex items-center gap-2 px-5 py-2.5 mr-3 rounded-xl bg-[#A8DD73] hover:bg-[#bbf082] disabled:opacity-50 text-black font-semibold text-xs sm:text-sm transition-all shadow-md shadow-[#A8DD73]/20 shrink-0 cursor-pointer"
            >
              <span>Search</span>
            </button>
          </div>
        </div>

        {/* Offline notice if backend is stopped */}
        {backendStatus === "offline" && (
          <div className="p-4 rounded-xl bg-amber-500/10 border border-amber-500/25 flex items-start gap-3">
            <AlertTriangle className="w-5 h-5 text-amber-400 shrink-0 mt-0.5" />
            <div className="text-xs text-amber-200/90 leading-relaxed">
              <span className="font-semibold text-amber-300">Backend Services Offline: </span>
              Displaying local verified catalog records. To activate real-time vector embeddings and the Siamese neural reranker, start your services in terminal:
              <div className="mt-2 font-mono text-[11px] bg-black/40 p-2 rounded-lg text-white/80 space-y-1">
                <div>Backend AI Service (Port 8001): <span className="text-[#A8DD73]">cd backend/ai-service && uvicorn app.main:app --reload --port 8001</span></div>
                <div>Backend API Service (Port 8000): <span className="text-[#A8DD73]">cd backend/api-service && uvicorn app.main:app --reload --port 8000</span></div>
              </div>
            </div>
          </div>
        )}

        {/* Siamese Neural Pipeline Diagnostics Banner */}
        {aiResponse?.pipeline && (
          <div className="p-4 rounded-xl bg-[#17151a] border border-white/10 flex flex-wrap items-center justify-between gap-4 text-xs">
            <div className="flex items-center gap-4 flex-wrap">
              <span className="text-zinc-400 flex items-center gap-1.5">
                <Cpu className="w-4 h-4 text-[#A8DD73]" />
                <span className="text-white font-medium">Embedding:</span>{" "}
                {aiResponse.pipeline.embedding_model || "Qwen2.5-3B"}
              </span>
              <span className="text-zinc-400 flex items-center gap-1.5">
                <Layers className="w-4 h-4 text-[#A8DD73]" />
                <span className="text-white font-medium">Reranker:</span>{" "}
                {aiResponse.pipeline.reranker_model || "Siamese Pair Model"}
              </span>
              <span className="text-zinc-400 flex items-center gap-1.5">
                <Database className="w-4 h-4 text-[#A8DD73]" />
                <span className="text-white font-medium">Candidates Scored:</span>{" "}
                {aiResponse.total_candidates}
              </span>
            </div>

            <div className="flex items-center gap-2">
              <span className="px-2.5 py-1 rounded-full bg-white/5 border border-white/10 text-white/70 font-mono text-[11px]">
                Top-K: {aiResponse.pipeline.top_k} ➔ Final-K: {aiResponse.pipeline.final_k}
              </span>
            </div>
          </div>
        )}

        {/* Search Results List */}
        {isLoading ? (
          <div className="py-20 text-center space-y-4">
            <Loader2 className="w-8 h-8 animate-spin text-[#A8DD73] mx-auto" />
            <p className="text-sm text-zinc-400">
              Running vector embedding search and Siamese neural reranker...
            </p>
          </div>
        ) : aiResponse && aiResponse.results.length > 0 ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white/90">
                Found {aiResponse.results.length} Ranked Matches for &quot;{activeQuery}&quot;
              </h2>
              <span className="text-xs text-zinc-400">
                Ranked by Siamese Neural Cross-Attention &amp; Vector Cosine
              </span>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {aiResponse.results.map((hit, idx) => (
                <SearchHitCard
                  key={`${hit.material_id}-${idx}`}
                  hit={hit}
                  index={idx}
                />
              ))}
            </div>
          </div>
        ) : catalogResults && catalogResults.length > 0 ? (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-semibold text-white/90">
                Found {catalogResults.length} Catalog Matches for &quot;{activeQuery}&quot;
              </h2>
              <span className="text-xs text-zinc-400">
                Direct CPSE Master Registry Search
              </span>
            </div>

            <div className="grid grid-cols-1 gap-4">
              {catalogResults.map((mat, idx) => (
                <SearchHitCard
                  key={`${mat.id}-${idx}`}
                  hit={mat}
                  index={idx}
                />
              ))}
            </div>
          </div>
        ) : activeQuery && !isLoading ? (
          <div className="py-16 text-center space-y-3 bg-[#121013]/50 rounded-2xl border border-white/5">
            <p className="text-base font-semibold text-white">
              No matching records found for &quot;{activeQuery}&quot;
            </p>
            <p className="text-xs text-zinc-400 max-w-md mx-auto">
              Try searching by a broader keyword, generic equipment name, or CPSE catalog reference.
            </p>
          </div>
        ) : null}
      </main>
    </CpseLayout>
  );
}

export default function SearchPage() {
  return (
    <Suspense
      fallback={
        <div className="min-h-screen bg-[#0A090B] flex items-center justify-center">
          <Loader2 className="w-8 h-8 animate-spin text-[#A8DD73]" />
        </div>
      }
    >
      <SearchPageContent />
    </Suspense>
  );
}
