"use client";

import React from "react";
import Link from "next/link";
import { GitCompare, Database, CheckSquare, Sparkles, ArrowRight } from "lucide-react";

export default function QuickActions() {
  const actions = [
    {
      title: "AI Material Matching",
      description: "Siamese neural deduplication & cross-CPSE equivalency mapping.",
      href: "/matching",
      icon: GitCompare,
      badge: "Siamese v2.4",
      highlight: true,
    },
    {
      title: "Master Catalog Explorer",
      description: "Browse ingested materials across CPSEs with multi-filter search.",
      href: "/materials",
      icon: Database,
      badge: "Catalog",
      highlight: false,
    },
    {
      title: "National Admin Reviews",
      description: "Approve, reject, or modify pending equivalency decisions.",
      href: "/reviews",
      icon: CheckSquare,
      badge: "Admin Queue",
      highlight: false,
    },
  ];

  return (
    <div className="w-full space-y-3">
      <div className="flex items-center gap-2">
        <h3 className="text-xs sm:text-sm font-bold uppercase tracking-wider text-zinc-300">
          Core Workflows
        </h3>
        <span className="w-1.5 h-1.5 rounded-full bg-[#A8DD73]" />
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 sm:gap-4">
        {actions.map((act) => {
          const Icon = act.icon;
          return (
            <Link
              key={act.href}
              href={act.href}
              className={`p-4 sm:p-5 rounded-2xl border transition-all flex flex-col justify-between group cursor-pointer ${act.highlight
                  ? "bg-white/[0.03] border-[#A8DD73]/30 hover:border-[#A8DD73] hover:shadow-[0_0_20px_rgba(168,221,115,0.15)]"
                  : "bg-[#121013]/90 border-white/10 hover:border-white/20 hover:bg-white/[0.04]"
                }`}
            >
              <div>
                <div className="flex items-center justify-between gap-2 mb-3">
                  <div
                    className={`w-8 h-8 rounded-xl flex items-center justify-center ${act.highlight
                        ? "bg-[#A8DD73]/15 text-[#A8DD73] border border-[#A8DD73]/30"
                        : "bg-white/5 text-zinc-300 border border-white/10"
                      }`}
                  >
                    <Icon className="w-4 h-4" />
                  </div>
                  <span className="text-[10px] font-mono font-semibold px-2 py-0.5 rounded-full bg-white/5 text-zinc-400 border border-white/10">
                    {act.badge}
                  </span>
                </div>

                <h4 className="text-sm font-bold text-white group-hover:text-[#A8DD73] transition-colors">
                  {act.title}
                </h4>
                <p className="text-xs text-zinc-400 mt-1 leading-relaxed">
                  {act.description}
                </p>
              </div>

              <div className="flex items-center gap-1.5 text-xs font-semibold text-zinc-400 group-hover:text-[#A8DD73] mt-4 pt-3 border-t border-white/5 transition-colors">
                <span>Open Workflow</span>
                <ArrowRight className="w-3.5 h-3.5 group-hover:translate-x-1 transition-transform" />
              </div>
            </Link>
          );
        })}
      </div>
    </div>
  );
}

