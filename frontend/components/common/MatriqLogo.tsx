"use client";

import React from "react";
import { cn } from "@/lib/utils";

interface MatriqLogoProps {
  size?: number;
  className?: string;
}

export default function MatriqLogo({ size = 30, className }: MatriqLogoProps) {
  return (
    <div
      className={cn(
        "relative flex items-center justify-center shrink-0 rounded-xl bg-[#121013] border border-[#A8DD73]/30 shadow-[0_0_15px_rgba(168,221,115,0.25)] group-hover:border-[#A8DD73]/60 transition-all p-1",
        className
      )}
      style={{ width: size, height: size }}
      title="MATRIQ - National Material Intelligence & Harmonization Platform"
    >
      <svg
        viewBox="0 0 48 48"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        className="w-full h-full"
      >
        <defs>
          {/* Primary Lime Neon Gradient */}
          <linearGradient id="matriq-lime" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#E5ECCF" />
            <stop offset="45%" stopColor="#A8DD73" />
            <stop offset="100%" stopColor="#4ADE80" />
          </linearGradient>

          {/* Deep Contrast Facet Gradient */}
          <linearGradient id="matriq-dark" x1="0%" y1="0%" x2="100%" y2="100%">
            <stop offset="0%" stopColor="#2E4A1A" />
            <stop offset="100%" stopColor="#14240C" />
          </linearGradient>

          {/* Accent Glow Filter */}
          <filter id="matriq-glow" x="-20%" y="-20%" width="140%" height="140%">
            <feDropShadow
              dx="0"
              dy="0"
              stdDeviation="2"
              floodColor="#A8DD73"
              floodOpacity="0.4"
            />
          </filter>
        </defs>

        {/* Outer Hexagonal Matrix Lattice Frame */}
        <polygon
          points="24,3 43,14 43,34 24,45 5,34 5,14"
          stroke="url(#matriq-lime)"
          strokeWidth="2"
          strokeLinejoin="round"
          fill="none"
          opacity="0.35"
        />

        {/* Dynamic Stylized 'M' Isometric Crystal Polyhedra */}
        {/* Left 'M' Pillar */}
        <path
          d="M10 17 L20 22.5 L20 37 L10 31.5 Z"
          fill="url(#matriq-lime)"
          filter="url(#matriq-glow)"
          opacity="0.95"
        />

        {/* Right 'M' Pillar */}
        <path
          d="M38 17 L28 22.5 L28 37 L38 31.5 Z"
          fill="url(#matriq-lime)"
          filter="url(#matriq-glow)"
          opacity="0.95"
        />

        {/* Central 'M' Chevron Vertex (Harmonization Core) */}
        <path
          d="M24 11 L31 15 L24 26 L17 15 Z"
          fill="url(#matriq-lime)"
          opacity="0.85"
        />

        {/* Bottom Matrix Keystone Node */}
        <polygon
          points="24,28 28,34 24,39 20,34"
          fill="#FFFFFF"
          opacity="0.9"
        />

        {/* Intersecting Lattice Connection Lines */}
        <line
          x1="20"
          y1="22.5"
          x2="24"
          y2="26"
          stroke="#FFFFFF"
          strokeWidth="1.2"
          opacity="0.8"
        />
        <line
          x1="28"
          y1="22.5"
          x2="24"
          y2="26"
          stroke="#FFFFFF"
          strokeWidth="1.2"
          opacity="0.8"
        />
      </svg>
    </div>
  );
}
