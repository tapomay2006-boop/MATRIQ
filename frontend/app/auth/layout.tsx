"use client";

import { motion } from "framer-motion";
import Image from "next/image";
import Link from "next/link";
import MatriqLogo from "@/components/common/MatriqLogo";
import { Sparkles, ArrowLeft } from "lucide-react";
import { useRef, useState } from "react";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [mouse, setMouse] = useState({ x: -9999, y: -9999, active: false });

  const handleMouseMove = (e: React.MouseEvent<HTMLDivElement>) => {
    if (!containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    setMouse({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      active: true,
    });
  };

  const handleMouseLeave = () => {
    setMouse({ x: -9999, y: -9999, active: false });
  };

  return (
    <div
      ref={containerRef}
      onMouseMove={handleMouseMove}
      onMouseLeave={handleMouseLeave}
      className="min-h-screen relative overflow-hidden flex"
      style={{
        backgroundColor: "#0A0809",
        backgroundImage: `
          linear-gradient(to right, rgba(255, 255, 255, 0.04) 1px, transparent 1px),
          linear-gradient(to bottom, rgba(255, 255, 255, 0.04) 1px, transparent 1px)
        `,
        backgroundSize: "40px 40px",
        // @ts-ignore
        "--cx": `${mouse.x}px`,
        // @ts-ignore
        "--cy": `${mouse.y}px`,
      }}
    >
      {/* Masked Cursor Ambient Glow */}
      {mouse.active && (
        <div
          className="absolute inset-0 pointer-events-none z-[1] transition-opacity duration-300"
          style={{
            backgroundImage: `
              linear-gradient(to right, rgba(168, 221, 115, 0.12) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(168, 221, 115, 0.12) 1px, transparent 1px)
            `,
            backgroundSize: "40px 40px",
            WebkitMaskImage: "radial-gradient(circle 280px at var(--cx) var(--cy), #000 0%, #000 40%, transparent 100%)",
            maskImage: "radial-gradient(circle 280px at var(--cx) var(--cy), #000 0%, #000 40%, transparent 100%)",
          }}
        />
      )}

      {/* Background Soft Lime Glows */}
      <div className="absolute top-[-10%] left-[-5%] w-[45vw] h-[45vw] rounded-full pointer-events-none z-0 opacity-20 blur-[140px] bg-radial from-[#A8DD73]/30 via-[#7EBB4B]/10 to-transparent" />
      <div className="absolute bottom-[-10%] right-[-5%] w-[45vw] h-[45vw] rounded-full pointer-events-none z-0 opacity-15 blur-[150px] bg-radial from-[#A8DD73]/20 via-transparent to-transparent" />

      {/* Main Split Layout Grid */}
      <div className="flex-1 flex w-full relative z-10 min-h-screen">
        {/* LEFT PANEL: Branding & Mission (Hidden on Mobile) */}
        <motion.div
          initial={{ opacity: 0, x: -30 }}
          animate={{ opacity: 1, x: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          className="hidden lg:flex lg:w-[48%] xl:w-[45%] border-r border-white/10 flex-col justify-between p-10 xl:p-14 relative overflow-hidden backdrop-blur-sm"
          style={{
            background: "radial-gradient(circle at 10% 20%, rgba(168,221,115,0.06), transparent 50%), rgba(18, 16, 19, 0.6)",
          }}
        >
          {/* Top: Logo & Back Link */}
          <div className="flex items-center justify-between z-10">
            <Link href="/" className="inline-flex items-center gap-3 group">
              <MatriqLogo size={36} />
              <span
                className="text-xl font-bold text-white tracking-wider group-hover:text-[#A8DD73] transition-colors"
                style={{ fontFamily: "var(--font-heading)" }}
              >
                MATRIQ
              </span>
            </Link>

            <Link
              href="/"
              className="inline-flex items-center gap-1.5 text-xs text-white/60 hover:text-[#A8DD73] transition-colors py-1.5 px-3 rounded-full border border-white/10 bg-white/5 hover:border-[#A8DD73]/30"
            >
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Back to Home</span>
            </Link>
          </div>

          {/* Middle: Headline & Value Props - Exactly Centered */}
          <div className="flex-1 flex flex-col justify-center items-start max-w-[480px] my-auto py-12 z-10">
            <span className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full border border-[#A8DD73]/30 bg-[#A8DD73]/10 text-[#A8DD73] text-[10.5px] font-mono tracking-widest font-semibold uppercase mb-5 shadow-[0_0_12px_rgba(168,221,115,0.15)]">
              Ministry &amp; CPSE Standard
            </span>

            <h1
              className="tracking-tight text-white"
              style={{
                fontFamily: "var(--font-heading)",
                fontSize: "clamp(2.4rem, 4vw, 3.2rem)",
                lineHeight: 1.1,
              }}
            >
              Master Your{" "}
              <span
                className="bg-clip-text text-transparent italic block"
                style={{
                  backgroundImage:
                    "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                  fontFamily: "var(--font-serif)",
                  fontWeight: 400,
                }}
              >
                Material Catalogs.
              </span>
            </h1>

            <p className="mt-5 text-sm sm:text-[14.5px] text-white/60 leading-relaxed max-w-[440px]">
              Harmonize legacy item descriptions, identify equivalent materials across CPSE catalogs, and eliminate duplicate procurement with enterprise AI.
            </p>
          </div>

          {/* Bottom Footer Note */}
          <div className="pt-4 border-t border-white/10 flex items-center justify-center text-center text-[11px] text-white/40 z-10">
            <span>© 2026 MATRIQ. All rights reserved.</span>
          </div>
        </motion.div>

        {/* RIGHT PANEL: Authentication Form */}
        <div className="flex-1 flex flex-col justify-center items-center p-6 sm:p-10 lg:p-12 relative overflow-y-auto">
          {/* Mobile top bar */}
          <div className="lg:hidden w-full max-w-[460px] flex items-center justify-between mb-6">
            <Link href="/" className="inline-flex items-center gap-2">
              <MatriqLogo size={28} />
              <span className="font-bold text-white text-base tracking-wider" style={{ fontFamily: "var(--font-heading)" }}>
                MATRIQ
              </span>
            </Link>
            <Link href="/" className="text-xs text-white/60 hover:text-[#A8DD73] flex items-center gap-1">
              <ArrowLeft className="w-3.5 h-3.5" />
              <span>Home</span>
            </Link>
          </div>

          <div className="w-full max-w-[460px] relative z-10">
            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
