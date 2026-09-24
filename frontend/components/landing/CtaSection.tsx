"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowRight, Play, Sparkles } from "lucide-react";

export default function CtaSection() {
  const { data: session, status } = useSession();
  const router = useRouter();
  const cardRef = useRef<HTMLDivElement>(null);
  const isInView = useInView(cardRef, { once: true, amount: 0.2 });

  const handleGetStarted = () => {
    router.push("/auth/login");
  };

  // Interactive mouse tracking for illuminated grid
  const [mouse, setMouse] = useState({ x: -9999, y: -9999, active: false });
  const [curMouse, setCurMouse] = useState({ x: -9999, y: -9999 });

  const handlePointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!cardRef.current) return;
    const rect = cardRef.current.getBoundingClientRect();
    setMouse({
      x: e.clientX - rect.left,
      y: e.clientY - rect.top,
      active: true,
    });
  };

  const handlePointerLeave = () => {
    setMouse((prev) => ({ ...prev, active: false }));
  };

  // Smooth cursor follow interpolation loop
  useEffect(() => {
    if (!mouse.active) return;
    let frameId: number;

    const updateFollow = () => {
      setCurMouse((prev) => {
        const dx = mouse.x - prev.x;
        const dy = mouse.y - prev.y;
        if (Math.abs(dx) < 0.1 && Math.abs(dy) < 0.1) {
          return mouse;
        }
        return {
          x: prev.x + dx * 0.18,
          y: prev.y + dy * 0.18,
        };
      });
      frameId = requestAnimationFrame(updateFollow);
    };

    frameId = requestAnimationFrame(updateFollow);
    return () => cancelAnimationFrame(frameId);
  }, [mouse]);

  return (
    <section
      className="w-full py-10 sm:py-14 px-4 sm:px-6 xl:px-0 overflow-hidden"
      style={{
        backgroundColor: "#0A0809",
      }}
    >
      <div
        ref={cardRef}
        onPointerMove={handlePointerMove}
        onPointerLeave={handlePointerLeave}
        className="cta-card relative w-full max-w-[1060px] mx-auto rounded-[28px] sm:rounded-[32px] border border-[#A8DD73]/25 bg-[#0C100B]/95 overflow-hidden py-10 sm:py-14 px-6 sm:px-10 text-center transition-all duration-300 shadow-[0_0_50px_rgba(0,0,0,0.85),0_0_25px_rgba(168,221,115,0.06)]"
        style={{
          // @ts-ignore
          "--cx": `${curMouse.x}px`,
          // @ts-ignore
          "--cy": `${curMouse.y}px`,
          isolation: "isolate",
        }}
      >
        {/* Background Grid Pattern */}
        <div
          className="absolute inset-0 pointer-events-none z-0 opacity-40"
          style={{
            backgroundImage: `
              linear-gradient(to right, rgba(168, 221, 115, 0.10) 1px, transparent 1px),
              linear-gradient(to bottom, rgba(168, 221, 115, 0.10) 1px, transparent 1px)
            `,
            backgroundSize: "40px 40px",
          }}
        />

        {/* Hover-illuminated Grid Mask */}
        {mouse.active && (
          <div
            className="absolute inset-0 pointer-events-none z-[1] transition-opacity duration-300"
            style={{
              backgroundImage: `
                linear-gradient(to right, rgba(184, 231, 122, 0.28) 1.5px, transparent 1.5px),
                linear-gradient(to bottom, rgba(184, 231, 122, 0.28) 1.5px, transparent 1.5px)
              `,
              backgroundSize: "40px 40px",
              WebkitMaskImage:
                "radial-gradient(circle 200px at var(--cx) var(--cy), #000 0%, #000 35%, transparent 100%)",
              maskImage:
                "radial-gradient(circle 200px at var(--cx) var(--cy), #000 0%, #000 35%, transparent 100%)",
            }}
          />
        )}

        {/* Central Ambient Green Glow Spotlight (Soft & Subdued) */}
        <div
          className="absolute inset-0 pointer-events-none z-[1]"
          style={{
            background:
              "radial-gradient(circle 240px at 50% 55%, rgba(168, 221, 115, 0.08), transparent 70%)",
          }}
        />

        {/* Main Content */}
        <div className="relative z-10 flex flex-col items-center justify-center max-w-[780px] mx-auto">
          {/* Top Pill Badge */}
          <motion.div
            initial={{ opacity: 0, y: 15 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.5 }}
            className="inline-flex items-center gap-1.5 px-3.5 py-1 rounded-full border border-[#A8DD73]/35 bg-[#A8DD73]/10 text-[#A8DD73] text-[11px] font-mono tracking-[0.14em] font-semibold uppercase mb-4 sm:mb-5 shadow-[0_0_15px_rgba(168,221,115,0.15)] backdrop-blur-md"
          >
            <Sparkles className="w-3 h-3 text-[#B8E77A]" />
            <span>GET STARTED</span>
          </motion.div>

          {/* Heading with website-wide font-heading and signature gradient */}
          <motion.h2
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.1 }}
            className="font-normal tracking-tight text-white m-0 text-[32px] sm:text-[42px] md:text-[50px] lg:text-[56px] leading-[1.12]"
            style={{
              fontFamily: "var(--font-heading)",
              letterSpacing: "-0.03em",
              color: "#FFFFFF",
            }}
          >
            Automate your infrastructure{" "}
            <span
              className="block bg-clip-text text-transparent"
              style={{
                backgroundImage:
                  "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
                WebkitBackgroundClip: "text",
                WebkitTextFillColor: "transparent",
              }}
            >
              at the speed of thought
            </span>
          </motion.h2>

          {/* Subtitle */}
          <motion.p
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.2 }}
            className="text-white/60 font-normal text-sm sm:text-base md:text-[16.5px] leading-relaxed max-w-[640px] mt-3.5 mb-6 sm:mb-7 mx-auto"
            style={{
              fontFamily: "var(--font-body)",
            }}
          >
            Empower your entire organization to create, audit, and deploy at the speed of thought, while ensuring security remains at the forefront.
          </motion.p>

          {/* Action Buttons */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={isInView ? { opacity: 1, y: 0 } : {}}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="flex flex-col sm:flex-row items-center justify-center gap-3.5 sm:gap-4 w-full sm:w-auto"
          >
            {/* Primary Button with reduced, tight glow */}
            <Link
              href="/auth/login"
              className="inline-flex items-center justify-center gap-2 h-12 sm:h-13 px-7 sm:px-8 rounded-full bg-[#A8DD73] text-[#0A0809] hover:bg-[#B8E77A] font-semibold text-sm sm:text-[15px] transition-all duration-300 hover:-translate-y-0.5 shadow-[0_2px_12px_rgba(168,221,115,0.22)] cursor-pointer w-full sm:w-auto"
              style={{ fontFamily: "var(--font-body)" }}
            >
              <span>Request Early Access</span>
              <ArrowRight className="w-4 h-4 text-[#0A0809]" strokeWidth={2.5} />
            </Link>

            {/* Secondary Button */}
            <button
              onClick={() =>
                window.open(
                  "https://drive.google.com/file/d/19kOgPG5z3p8pzY_DOgrKQsx8J1STNUZP/view?usp=sharing",
                  "_blank"
                )
              }
              className="inline-flex items-center justify-center gap-2.5 h-12 sm:h-13 px-6 sm:px-7 rounded-full bg-[#0D120B]/80 text-[#A8DD73] hover:text-[#B8E77A] hover:bg-[#A8DD73]/15 font-semibold text-sm sm:text-[15px] transition-all duration-300 border border-[#A8DD73]/35 hover:border-[#A8DD73]/60 hover:-translate-y-0.5 cursor-pointer backdrop-blur-md shadow-[0_2px_8px_rgba(0,0,0,0.5)] w-full sm:w-auto"
              style={{ fontFamily: "var(--font-body)" }}
            >
              <Play className="w-3.5 h-3.5 fill-[#A8DD73] text-[#A8DD73]" />
              <span>Watch Technical Demo</span>
            </button>
          </motion.div>
        </div>
      </div>
    </section>
  );
}
