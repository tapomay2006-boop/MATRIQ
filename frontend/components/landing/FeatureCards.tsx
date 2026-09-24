"use client";

import Image from "next/image";
import { DottedMapCard } from "./DottedMapCard";

export default function FeatureCards() {
  return (
    <section
      id="features"
      className="w-full relative z-10 pt-20 pb-24 overflow-hidden"
      style={{
        backgroundColor: "#0A0809",
        backgroundImage:
          "radial-gradient(circle at 50% 0%, rgba(184,231,122,0.08), transparent 45%)",
      }}
    >
      <div
        className="w-full mx-auto px-6 xl:px-0 flex flex-col items-center text-center"
        style={{ maxWidth: "1200px" }}
      >
        {/* Tag / Pill Badge */}
        <div
          className="inline-flex items-center rounded-full transition-all duration-200"
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
            gap: "8px",
            marginBottom: "24px",
            boxShadow: "0 2px 10px rgba(0, 0, 0, 0.2)",
          }}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="#B8E77A"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            className="flex-shrink-0"
          >
            <path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275Z" />
          </svg>
          <span>AI-Powered Material Intelligence</span>
        </div>

        {/* Heading */}
        <h2
          className="font-normal m-0 animate-fade-in"
          style={{
            fontFamily: "var(--font-heading)",
            fontSize: "clamp(2.5rem, 5vw, 3.75rem)",
            fontWeight: 400,
            lineHeight: 1.15,
            letterSpacing: "-0.03em",
            color: "#FFFFFF",
            marginBottom: "20px",
          }}
        >
          Key{" "}
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Features
          </span>
        </h2>

        {/* Sub-heading */}
        <p
          className="font-normal mx-auto m-0"
          style={{
            fontFamily: "var(--font-body)",
            fontSize: "17.5px",
            fontWeight: 400,
            lineHeight: "28px",
            letterSpacing: "-0.01em",
            color: "rgba(255, 255, 255, 0.58)",
            maxWidth: "680px",
            marginTop: "0px",
            marginBottom: "60px",
            textShadow: "0 1px 2px rgba(0, 0, 0, 0.3)",
          }}
        >
          Discover the intelligent tools that standardize legacy descriptions, identify equivalent materials across CPSEs, and streamline procurement.
        </p>

        {/* Cards Grid */}
        <div className="grid grid-cols-1 md:grid-cols-6 gap-6 w-full text-left">
          {/* Row 1 - Card 1: AI Attribute Extraction */}
          <div
            className="md:col-span-2 flex flex-col p-7 sm:p-8 rounded-[24px] border border-white/10 hover:border-[#B8E77A]/30 hover:shadow-[0_12px_30px_-10px_rgba(0,0,0,0.6),0_0_20px_-5px_rgba(184,231,122,0.08)] transition-all duration-300 min-h-[380px] overflow-hidden justify-between group hover:-translate-y-1"
            style={{
              background:
                "radial-gradient(circle at 80% 10%, rgba(184,231,122,0.07), transparent 35%), rgba(255,255,255,0.04)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
            }}
          >
            <div className="relative w-full h-56 mb-4 rounded-2xl overflow-hidden flex items-center justify-center">
              <Image
                src="/Card1.png"
                alt="AI Attribute Extraction"
                fill
                priority={true}
                className="object-contain"
                sizes="(max-width: 768px) 100vw, 33vw"
              />
            </div>
            <div>
              <h3
                className="text-xl mb-2"
                style={{
                  color: "#FFFFFF",
                  fontWeight: 500,
                  fontFamily: "var(--font-body)",
                }}
              >
                AI Attribute Extraction
              </h3>
              <p
                className="text-[15px] leading-relaxed m-0"
                style={{
                  color: "rgba(255, 255, 255, 0.55)",
                  fontFamily: "var(--font-body)",
                }}
              >
                Turn unstructured material descriptions into standardized attributes, specifications, part numbers, and UOMs.
              </p>
            </div>
          </div>

          {/* Row 1 - Card 2: Semantic Material Search */}
          <div
            className="md:col-span-2 flex flex-col p-7 sm:p-8 rounded-[24px] border border-white/10 hover:border-[#B8E77A]/30 hover:shadow-[0_12px_30px_-10px_rgba(0,0,0,0.6),0_0_20px_-5px_rgba(184,231,122,0.08)] transition-all duration-300 min-h-[380px] overflow-hidden justify-between group hover:-translate-y-1"
            style={{
              background:
                "radial-gradient(circle at 80% 10%, rgba(184,231,122,0.07), transparent 35%), rgba(255,255,255,0.04)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
            }}
          >
            <div className="relative w-full h-56 mb-4 rounded-2xl overflow-hidden flex items-center justify-center">
              <Image
                src="/card2.png"
                alt="Semantic Material Search"
                fill
                className="object-contain"
                sizes="(max-width: 768px) 100vw, 33vw"
              />
            </div>
            <div>
              <h3
                className="text-xl mb-2"
                style={{
                  color: "#FFFFFF",
                  fontWeight: 500,
                  fontFamily: "var(--font-body)",
                }}
              >
                Semantic Material Search
              </h3>
              <p
                className="text-[15px] leading-relaxed m-0"
                style={{
                  color: "rgba(255, 255, 255, 0.55)",
                  fontFamily: "var(--font-body)",
                }}
              >
                Find the most relevant equivalent materials across CPSE catalogs using AI-powered vector retrieval.
              </p>
            </div>
          </div>

          {/* Row 1 - Card 3: Intelligent Match Verification (Hero technical feature) */}
          <div
            className="md:col-span-2 flex flex-col p-7 sm:p-8 rounded-[24px] border border-white/10 hover:border-[#B8E77A]/30 hover:shadow-[0_12px_30px_-10px_rgba(0,0,0,0.6),0_0_20px_-5px_rgba(184,231,122,0.08)] transition-all duration-300 min-h-[380px] overflow-hidden justify-between group hover:-translate-y-1"
            style={{
              background:
                "radial-gradient(circle at 80% 10%, rgba(184,231,122,0.07), transparent 35%), rgba(255,255,255,0.04)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
            }}
          >
            <div className="relative w-full h-56 mb-4 rounded-2xl overflow-hidden flex items-center justify-center">
              <Image
                src="/cards3.png"
                alt="Intelligent Match Verification"
                fill
                className="object-contain"
                sizes="(max-width: 768px) 100vw, 33vw"
              />
            </div>
            <div>
              <h3
                className="text-xl mb-2"
                style={{
                  color: "#FFFFFF",
                  fontWeight: 500,
                  fontFamily: "var(--font-body)",
                }}
              >
                Intelligent Match Verification
              </h3>
              <p
                className="text-[15px] leading-relaxed m-0"
                style={{
                  color: "rgba(255, 255, 255, 0.55)",
                  fontFamily: "var(--font-body)",
                }}
              >
                Compare critical specifications to distinguish true equivalents from similar but incompatible materials.
              </p>
            </div>
          </div>

          {/* Row 2 - Card 4: Expert Review & Approval */}
          <div
            className="md:col-span-3 flex flex-col p-7 sm:p-8 rounded-[24px] border border-white/10 hover:border-[#B8E77A]/30 hover:shadow-[0_12px_30px_-10px_rgba(0,0,0,0.6),0_0_20px_-5px_rgba(184,231,122,0.08)] transition-all duration-300 min-h-[380px] overflow-hidden justify-between group hover:-translate-y-1"
            style={{
              background:
                "radial-gradient(circle at 80% 10%, rgba(184,231,122,0.07), transparent 35%), rgba(255,255,255,0.04)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
            }}
          >
            <div className="relative w-full h-64 mb-4 rounded-2xl overflow-hidden flex items-center justify-center">
              <Image
                src="/card4.png"
                alt="Expert Review & Approval"
                fill
                priority={true}
                className="object-contain"
                sizes="(max-width: 768px) 100vw, 50vw"
              />
            </div>
            <div>
              <h3
                className="text-xl mb-2"
                style={{
                  color: "#FFFFFF",
                  fontWeight: 500,
                  fontFamily: "var(--font-body)",
                }}
              >
                Expert Review & Approval
              </h3>
              <p
                className="text-[15px] leading-relaxed m-0"
                style={{
                  color: "rgba(255, 255, 255, 0.55)",
                  fontFamily: "var(--font-body)",
                }}
              >
                Give technical committees a side-by-side comparison to approve, reject, or create a new material master.
              </p>
            </div>
          </div>

          {/* Row 2 - Card 5: Unified Material Master */}
          <div
            className="md:col-span-3 flex flex-col p-7 sm:p-8 rounded-[24px] border border-white/10 hover:border-[#B8E77A]/30 hover:shadow-[0_12px_30px_-10px_rgba(0,0,0,0.6),0_0_20px_-5px_rgba(184,231,122,0.08)] transition-all duration-300 min-h-[380px] overflow-hidden justify-between group hover:-translate-y-1"
            style={{
              background:
                "radial-gradient(circle at 80% 10%, rgba(184,231,122,0.07), transparent 35%), rgba(255,255,255,0.04)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
            }}
          >
            <div className="relative w-full h-56 mb-4 rounded-2xl overflow-hidden bg-transparent flex items-center justify-center">
              <DottedMapCard />
            </div>
            <div>
              <h3
                className="text-xl mb-2"
                style={{
                  color: "#FFFFFF",
                  fontWeight: 500,
                  fontFamily: "var(--font-body)",
                }}
              >
                Unified Material Master
              </h3>
              <p
                className="text-[15px] leading-relaxed m-0"
                style={{
                  color: "rgba(255, 255, 255, 0.55)",
                  fontFamily: "var(--font-body)",
                }}
              >
                Standardize material records across CPSEs while preserving legacy codes and traceability.
              </p>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
