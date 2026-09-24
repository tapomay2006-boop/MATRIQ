"use client";

import { useEffect, useRef, useState } from "react";
import Image from "next/image";
import { motion, useInView } from "framer-motion";
import {
  Sparkles,
  FileText,
  Sliders,
  Tag,
  Package,
  Link2,
  Gauge,
  ClipboardCheck,
} from "lucide-react";

export default function AgentEconomySection() {
  const containerRef = useRef<HTMLDivElement>(null);
  const cardRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(cardRef, { once: true, amount: 0.15 });

  // Mouse hover state for grid mask illumination
  const [mouse, setMouse] = useState({ x: -9999, y: -9999, active: false });
  const [activeStep, setActiveStep] = useState(0);

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    setMouse({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      active: true,
    });
  };

  const handleMouseLeave = () => {
    setMouse({ x: -9999, y: -9999, active: false });
  };

  // Pulse animation cycle for the timeline workflow at the bottom
  useEffect(() => {
    const interval = setInterval(() => {
      setActiveStep((prev) => (prev + 1) % 4);
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  return (
    <section
      id="how-it-works"
      ref={containerRef}
      className="w-full py-20 px-6 sm:px-8 relative overflow-hidden"
      style={{
        backgroundColor: "#0A0809",
        backgroundImage: `
          radial-gradient(circle at 50% 0%, rgba(184,231,122,0.06), transparent 45%),
          linear-gradient(to right, rgba(255, 255, 255, 0.03) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(255, 255, 255, 0.03) 1px, transparent 1px)
        `,
        backgroundSize: "100% 100%, 36px 36px, 36px 36px",
      }}
    >
      <div className="max-w-[1200px] mx-auto relative z-10">

        {/* Header section matching dark glass style */}
        <div className="flex flex-col items-center text-center mb-16">
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6 }}
            className="inline-flex items-center gap-2 rounded-full"
            style={{
              background: "rgba(255, 255, 255, 0.05)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
              border: "1px solid rgba(255, 255, 255, 0.18)",
              color: "rgba(255, 255, 255, 0.75)",
              fontFamily: "var(--font-body)",
              height: "38px",
              padding: "8px 18px",
              fontSize: "12.5px",
              fontWeight: 500,
              letterSpacing: "0.02em",
              marginBottom: "20px",
              boxShadow: "0 2px 10px rgba(0, 0, 0, 0.2)",
            }}
          >
            <Sparkles className="w-[14px] h-[14px] text-[#B8E77A]" />
            <span>How It Works</span>
          </motion.div>

          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.15 }}
            className="font-normal m-0 tracking-tight leading-[1.1]"
            style={{
              fontFamily: "var(--font-heading)",
              fontSize: "clamp(32px, 5.5vw, 64px)",
              letterSpacing: "-0.03em",
              color: "#FFFFFF",
              marginBottom: "20px",
            }}
          >
            How AI Helps You{" "}
            <span
              className="bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              Harmonize Material Data
            </span>
          </motion.h2>

          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.28 }}
            className="font-normal mx-auto m-0"
            style={{
              fontFamily: "var(--font-body)",
              fontSize: "17.5px",
              lineHeight: "28px",
              letterSpacing: "-0.01em",
              color: "rgba(255, 255, 255, 0.58)",
              maxWidth: "840px",
            }}
          >
            NEMISYS analyzes fragmented material records, extracts key attributes, finds equivalent materials, and guides transparent standardization across CPSEs.
          </motion.p>
        </div>

        {/* Masked cursor illumination layer bounds */}
        <div
          ref={cardRef}
          onMouseMove={handleMouseMove}
          onMouseLeave={handleMouseLeave}
          className="relative w-full overflow-x-auto pb-6 scrollbar-hide"
          style={{
            // @ts-ignore
            "--cx": `${mouse.x}px`,
            // @ts-ignore
            "--cy": `${mouse.y}px`,
          }}
        >
          {/* Hover-energized grid (masked by cursor) */}
          {mouse.active && (
            <div
              className="absolute inset-0 pointer-events-none z-[1] transition-opacity duration-300"
              style={{
                backgroundImage: `
                  linear-gradient(to right, rgba(184, 231, 122, 0.15) 1px, transparent 1px),
                  linear-gradient(to bottom, rgba(184, 231, 122, 0.15) 1px, transparent 1px)
                `,
                backgroundSize: "36px 36px",
                WebkitMaskImage: "radial-gradient(circle 180px at var(--cx) var(--cy), #000 0%, #000 40%, transparent 100%)",
                maskImage: "radial-gradient(circle 180px at var(--cx) var(--cy), #000 0%, #000 40%, transparent 100%)",
              }}
            />
          )}

          {/* Interactive Flow Grid Graph */}
          <div className="flex items-center justify-between relative w-[1060px] h-[420px] mx-auto z-10">

            {/* SVG flows animation layer */}
            <svg className="absolute inset-0 w-full h-full pointer-events-none z-0" width="1060" height="420" viewBox="0 0 1060 420">
              <defs>
                <linearGradient id="flowLeft" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="rgba(184, 231, 122, 0.15)"></stop>
                  <stop offset="100%" stopColor="#A8DD73"></stop>
                </linearGradient>
                <linearGradient id="flowRight" x1="0" y1="0" x2="1" y2="0">
                  <stop offset="0%" stopColor="#A8DD73"></stop>
                  <stop offset="100%" stopColor="rgba(184, 231, 122, 0.15)"></stop>
                </linearGradient>
              </defs>

              {/* Left connections */}
              <path className="fill-none stroke-[#A8DD73]/50 stroke-[2] opacity-80" strokeLinecap="round" strokeLinejoin="round" d="M 260 76 C 370 76, 400 175, 482 175"></path>
              <path className="fill-none stroke-[#A8DD73]/50 stroke-[2] opacity-80" strokeLinecap="round" strokeLinejoin="round" d="M 260 160 C 370 160, 400 195, 476 195"></path>
              <path className="fill-none stroke-[#A8DD73]/50 stroke-[2] opacity-80" strokeLinecap="round" strokeLinejoin="round" d="M 260 244 C 370 244, 400 215, 476 215"></path>
              <path className="fill-none stroke-[#A8DD73]/50 stroke-[2] opacity-80" strokeLinecap="round" strokeLinejoin="round" d="M 260 328 C 370 328, 400 235, 482 235"></path>

              {/* Right connections */}
              <path className="fill-none stroke-[#A8DD73]/50 stroke-[2] opacity-80" strokeLinecap="round" strokeLinejoin="round" d="M 578 175 C 660 175, 690 76, 800 76"></path>
              <path className="fill-none stroke-[#A8DD73]/50 stroke-[2] opacity-80" strokeLinecap="round" strokeLinejoin="round" d="M 584 195 C 660 195, 690 160, 800 160"></path>
              <path className="fill-none stroke-[#A8DD73]/50 stroke-[2] opacity-80" strokeLinecap="round" strokeLinejoin="round" d="M 584 215 C 660 215, 690 244, 800 244"></path>
              <path className="fill-none stroke-[#A8DD73]/50 stroke-[2] opacity-80" strokeLinecap="round" strokeLinejoin="round" d="M 578 235 C 660 235, 690 328, 800 328"></path>

              {/* Glowing Anchor Dots on Center Node */}
              <g fill="#A8DD73" filter="drop-shadow(0 0 6px rgba(168,221,115,0.8))">
                <circle cx="482" cy="175" r="2.5" />
                <circle cx="476" cy="195" r="2.5" />
                <circle cx="476" cy="215" r="2.5" />
                <circle cx="482" cy="235" r="2.5" />
                <circle cx="578" cy="175" r="2.5" />
                <circle cx="584" cy="195" r="2.5" />
                <circle cx="584" cy="215" r="2.5" />
                <circle cx="578" cy="235" r="2.5" />
              </g>

              {/* Flowing animated particles */}
              <g>
                <circle r="3.5" fill="#A8DD73" filter="drop-shadow(0 0 6px #A8DD73)">
                  <animateMotion dur="2.8s" repeatCount="indefinite" path="M 260 76 C 370 76, 400 175, 482 175" />
                </circle>
                <circle r="3.5" fill="#A8DD73" filter="drop-shadow(0 0 6px #A8DD73)">
                  <animateMotion dur="2.8s" begin="0.4s" repeatCount="indefinite" path="M 260 160 C 370 160, 400 195, 476 195" />
                </circle>
                <circle r="3.5" fill="#A8DD73" filter="drop-shadow(0 0 6px #A8DD73)">
                  <animateMotion dur="2.8s" begin="0.8s" repeatCount="indefinite" path="M 260 244 C 370 244, 400 215, 476 215" />
                </circle>
                <circle r="3.5" fill="#A8DD73" filter="drop-shadow(0 0 6px #A8DD73)">
                  <animateMotion dur="2.8s" begin="1.2s" repeatCount="indefinite" path="M 260 328 C 370 328, 400 235, 482 235" />
                </circle>

                <circle r="3.5" fill="#A8DD73" filter="drop-shadow(0 0 6px #A8DD73)">
                  <animateMotion dur="2.8s" begin="1.4s" repeatCount="indefinite" path="M 578 175 C 660 175, 690 76, 800 76" />
                </circle>
                <circle r="3.5" fill="#A8DD73" filter="drop-shadow(0 0 6px #A8DD73)">
                  <animateMotion dur="2.8s" begin="1.8s" repeatCount="indefinite" path="M 584 195 C 660 195, 690 160, 800 160" />
                </circle>
                <circle r="3.5" fill="#A8DD73" filter="drop-shadow(0 0 6px #A8DD73)">
                  <animateMotion dur="2.8s" begin="2.2s" repeatCount="indefinite" path="M 584 215 C 660 215, 690 244, 800 244" />
                </circle>
                <circle r="3.5" fill="#A8DD73" filter="drop-shadow(0 0 6px #A8DD73)">
                  <animateMotion dur="2.8s" begin="2.6s" repeatCount="indefinite" path="M 578 235 C 660 235, 690 328, 800 328" />
                </circle>
              </g>
            </svg>

            {/* Left Column: FRAGMENTED MATERIAL DATA */}
            <div className="flex flex-col gap-4 w-[260px] h-full justify-center relative">
              <div className="text-[10.5px] font-bold text-white/40 tracking-[0.14em] uppercase absolute top-1 w-full text-center font-mono">
                Fragmented Material Data
              </div>

              {/* Node 1: Legacy Descriptions */}
              <div className="group flex items-center gap-3 p-3 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md hover:border-[#B8E77A]/30 hover:shadow-[0_8px_24px_rgba(0,0,0,0.6)] hover:-translate-y-0.5 transition-all duration-300 z-10 w-full">
                <div className="w-[36px] h-[36px] bg-[#A8DD73]/15 rounded-xl flex items-center justify-center flex-shrink-0 text-[#A8DD73]">
                  <FileText className="w-4.5 h-4.5" />
                </div>
                <div>
                  <h4 className="text-[12.5px] font-semibold text-white leading-tight">Legacy Descriptions</h4>
                  <p className="text-[10.5px] text-white/50 mt-0.5 leading-snug">Unstructured & inconsistent text.</p>
                </div>
              </div>

              {/* Node 2: Material Specifications */}
              <div className="group flex items-center gap-3 p-3 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md hover:border-[#B8E77A]/30 hover:shadow-[0_8px_24px_rgba(0,0,0,0.6)] hover:-translate-y-0.5 transition-all duration-300 z-10 w-full">
                <div className="w-[36px] h-[36px] bg-[#A8DD73]/15 rounded-xl flex items-center justify-center flex-shrink-0 text-[#A8DD73]">
                  <Sliders className="w-4.5 h-4.5" />
                </div>
                <div>
                  <h4 className="text-[12.5px] font-semibold text-white leading-tight">Material Specifications</h4>
                  <p className="text-[10.5px] text-white/50 mt-0.5 leading-snug">Attributes, grades & dimensions.</p>
                </div>
              </div>

              {/* Node 3: Part Numbers & Codes */}
              <div className="group flex items-center gap-3 p-3 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md hover:border-[#B8E77A]/30 hover:shadow-[0_8px_24px_rgba(0,0,0,0.6)] hover:-translate-y-0.5 transition-all duration-300 z-10 w-full">
                <div className="w-[36px] h-[36px] bg-[#A8DD73]/15 rounded-xl flex items-center justify-center flex-shrink-0 text-[#A8DD73]">
                  <Tag className="w-4.5 h-4.5" />
                </div>
                <div>
                  <h4 className="text-[12.5px] font-semibold text-white leading-tight">Part Numbers & Codes</h4>
                  <p className="text-[10.5px] text-white/50 mt-0.5 leading-snug">Codes from disparate catalogs.</p>
                </div>
              </div>

              {/* Node 4: Units & Classifications */}
              <div className="group flex items-center gap-3 p-3 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md hover:border-[#B8E77A]/30 hover:shadow-[0_8px_24px_rgba(0,0,0,0.6)] hover:-translate-y-0.5 transition-all duration-300 z-10 w-full">
                <div className="w-[36px] h-[36px] bg-[#A8DD73]/15 rounded-xl flex items-center justify-center flex-shrink-0 text-[#A8DD73]">
                  <Package className="w-4.5 h-4.5" />
                </div>
                <div>
                  <h4 className="text-[12.5px] font-semibold text-white leading-tight">Units & Classifications</h4>
                  <p className="text-[10.5px] text-white/50 mt-0.5 leading-snug">UOMs, categories & details.</p>
                </div>
              </div>
            </div>

            {/* Center Component: Clean Circular Node */}
            <div className="flex flex-col items-center justify-center z-10 h-full w-[210px]">
              {/* Outer Circular Glass Ring */}
              <div className="relative w-28 h-28 flex items-center justify-center rounded-full border border-white/20 bg-white/[0.04] backdrop-blur-md shadow-[0_0_35px_rgba(168,221,115,0.18)]">
                {/* Slow Rotating Dashed Orbit */}
                <div className="absolute inset-0 rounded-full border border-dashed border-[#A8DD73]/40 animate-[spin_14s_linear_infinite]" />

                {/* Inner Glowing Circular Image Container */}
                <div className="relative w-20 h-20 rounded-full overflow-hidden flex items-center justify-center bg-radial from-[#A8DD73]/20 via-[#A8DD73]/10 to-transparent border border-[#A8DD73]/30 shadow-[inset_0_0_16px_rgba(168,221,115,0.25)]">
                  <Image
                    src="/logo.png"
                    alt="Center logo"
                    width={54}
                    height={54}
                    className="object-contain"
                  />
                </div>
              </div>
            </div>

            {/* Right Column: HARMONIZED RESULTS */}
            <div className="flex flex-col gap-4 w-[260px] h-full justify-center relative">
              <div className="text-[10.5px] font-bold text-white/40 tracking-[0.14em] uppercase absolute top-1 w-full text-center font-mono">
                Harmonized Results
              </div>

              {/* Node 1: Standardized Attributes */}
              <div className="group flex items-center gap-3 p-3 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md hover:border-[#B8E77A]/30 hover:shadow-[0_8px_24px_rgba(0,0,0,0.6)] hover:-translate-y-0.5 transition-all duration-300 z-10 w-full">
                <div className="w-[36px] h-[36px] bg-[#A8DD73]/15 rounded-xl flex items-center justify-center flex-shrink-0 text-[#A8DD73]">
                  <Sparkles className="w-4.5 h-4.5" />
                </div>
                <div>
                  <h4 className="text-[12.5px] font-semibold text-white leading-tight">Standardized Attributes</h4>
                  <p className="text-[10.5px] text-white/50 mt-0.5 leading-snug">Structured & unified data.</p>
                </div>
              </div>

              {/* Node 2: Equivalent Materials */}
              <div className="group flex items-center gap-3 p-3 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md hover:border-[#B8E77A]/30 hover:shadow-[0_8px_24px_rgba(0,0,0,0.6)] hover:-translate-y-0.5 transition-all duration-300 z-10 w-full">
                <div className="w-[36px] h-[36px] bg-[#A8DD73]/15 rounded-xl flex items-center justify-center flex-shrink-0 text-[#A8DD73]">
                  <Link2 className="w-4.5 h-4.5" />
                </div>
                <div>
                  <h4 className="text-[12.5px] font-semibold text-white leading-tight">Equivalent Materials</h4>
                  <p className="text-[10.5px] text-white/50 mt-0.5 leading-snug">Cross-CPSE catalog matches.</p>
                </div>
              </div>

              {/* Node 3: Match Confidence */}
              <div className="group flex items-center gap-3 p-3 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md hover:border-[#B8E77A]/30 hover:shadow-[0_8px_24px_rgba(0,0,0,0.6)] hover:-translate-y-0.5 transition-all duration-300 z-10 w-full">
                <div className="w-[36px] h-[36px] bg-[#A8DD73]/15 rounded-xl flex items-center justify-center flex-shrink-0 text-[#A8DD73]">
                  <Gauge className="w-4.5 h-4.5" />
                </div>
                <div>
                  <h4 className="text-[12.5px] font-semibold text-white leading-tight">Match Confidence</h4>
                  <p className="text-[10.5px] text-white/50 mt-0.5 leading-snug">Similarity & confidence scores.</p>
                </div>
              </div>

              {/* Node 4: Review-Ready Recommendations */}
              <div className="group flex items-center gap-3 p-3 bg-white/[0.04] border border-white/10 rounded-2xl backdrop-blur-md hover:border-[#B8E77A]/30 hover:shadow-[0_8px_24px_rgba(0,0,0,0.6)] hover:-translate-y-0.5 transition-all duration-300 z-10 w-full">
                <div className="w-[36px] h-[36px] bg-[#A8DD73]/15 rounded-xl flex items-center justify-center flex-shrink-0 text-[#A8DD73]">
                  <ClipboardCheck className="w-4.5 h-4.5" />
                </div>
                <div>
                  <h4 className="text-[12.5px] font-semibold text-white leading-tight">Review-Ready Results</h4>
                  <p className="text-[10.5px] text-white/50 mt-0.5 leading-snug">Technical committee approval.</p>
                </div>
              </div>
            </div>

          </div>
        </div>

      </div>

      <style jsx global>{`
        @keyframes popup-reveal {
          0%, 40% { opacity: 0; transform: translateY(5px); }
          50% { opacity: 1; transform: translateY(0); }
          90% { opacity: 1; transform: translateY(0); }
          100% { opacity: 0; transform: translateY(-10px); }
        }
        .animate-popup {
          animation: popup-reveal 3.5s ease-out infinite;
        }
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
        .scrollbar-hide {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}</style>
    </section>
  );
}
