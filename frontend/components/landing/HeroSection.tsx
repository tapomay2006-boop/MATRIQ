"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import { Rocket, ArrowRight, Play } from "lucide-react";
import Navbar from "@/components/common/Navbar";
// import DigitalBadgesSection from "./DigitalBadgesSection";

export default function HeroSection() {
  const { data: session, status } = useSession();
  const router = useRouter();

  const handleGetStarted = () => {
    router.push("/auth/login");
  };

  return (
    <div
      id="home"
      className="grain-overlay relative min-h-screen flex flex-col overflow-hidden"
      style={{ background: "#0A0809" }}
    >
      {/* Background */}
      <div className="absolute inset-0 z-0">
        <Image
          src="/hero-section.png"
          alt=""
          fill
          priority
          className="object-cover object-center"
          sizes="100vw"
        />
        <div
          className="absolute inset-0"
          style={{
            background:
              "linear-gradient(to bottom, rgba(10,8,9,0.35) 0%, transparent 50%, #0A0809 100%)",
          }}
        />
      </div>

      {/* Navbar */}
      <Navbar />

      {/* Hero Content */}
      <section
        className="relative z-10 mx-auto flex w-full flex-col items-center text-center animate-hero px-6 xl:px-0 flex-1 justify-start"
        style={{
          maxWidth: "1300px",
          paddingTop: "16vh",
          paddingBottom: "12vh",
        }}
      >
        {/* Pill badge */}
        <div
          style={{
            background: "rgba(255, 255, 255, 0.05)",
            backdropFilter: "blur(12px)",
            WebkitBackdropFilter: "blur(12px)",
            border: "1px solid rgba(255, 255, 255, 0.25)",
            borderRadius: "999px",
            padding: "8px 26px",
            fontSize: "14.5px",
            fontWeight: 500,
            letterSpacing: "0.01em",
            color: "rgba(255, 255, 255, 0.68)",
            fontFamily: "var(--font-body)",
            marginBottom: "32px",
            boxShadow: "0 2px 10px rgba(0, 0, 0, 0.2)",
          }}
        >
          Smarter materials. Better procurement.
        </div>

        {/* Heading */}
        <h1
          style={{
            fontFamily: "var(--font-heading)",
            fontWeight: 400,
            fontSize: "clamp(3.4rem, 7.2vw, 6.2rem)",
            lineHeight: 1.06,
            letterSpacing: "-0.02em",
            marginBottom: "32px",
            maxWidth: "1050px",
          }}
        >
          <span className="text-white block">Unify your materials.</span>
          <span
            className="block bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(180deg, #E5ECCF 0%, #D4E0B0 35%, #C6DA93 65%, #A6C06B 100%)",
              WebkitBackgroundClip: "text",
              WebkitTextFillColor: "transparent",
            }}
          >
            Simplify your procurement.
          </span>
        </h1>

        {/* Description */}
        <p
          style={{
            fontFamily: "var(--font-body)",
            fontSize: "20px",
            lineHeight: 1.6,
            color: "rgba(255, 255, 255, 0.72)",
            fontWeight: 400,
            maxWidth: "900px",
            textWrap: "balance",
            marginBottom: "44px",
          }}
        >
          AI-powered material intelligence that standardizes legacy descriptions, finds equivalent materials across CPSEs, and enables faster, traceable procurement decisions.
        </p>

        {/* CTA Buttons */}
        <div className="flex items-center justify-center gap-5 flex-col sm:flex-row w-full sm:w-auto mt-2">
          {/* Explore Platform Button */}
          <Link
            href="/auth/login"
            className="group flex items-center justify-center gap-3.5 no-underline rounded-full font-semibold transition-all duration-300 ease-in-out hover:-translate-y-0.5 hover:shadow-xl"
            style={{
              fontFamily: "var(--font-body)",
              fontSize: "16.5px",
              color: "#14181B",
              backgroundColor: "#A8DD73",
              padding: "10px 28px 10px 12px",
              boxShadow: "0 6px 24px rgba(168, 221, 115, 0.38)",
              cursor: "pointer",
              border: "none",
            }}
          >
            <span
              className="flex items-center justify-center rounded-full"
              style={{
                width: "42px",
                height: "42px",
                backgroundColor: "#7CB342",
              }}
            >
              <Rocket size={20} className="text-white fill-white" />
            </span>
            <span className="font-semibold text-[16px] sm:text-[17px] tracking-tight text-neutral-900">
              Explore Platform
            </span>
            <ArrowRight
              size={20}
              strokeWidth={2.5}
              className="text-neutral-900 transition-transform duration-200 group-hover:translate-x-1 ml-0.5"
            />
          </Link>

          {/* Watch Demo Button */}
          <button
            onClick={() => {
              window.open("https://drive.google.com/file/d/19kOgPG5z3p8pzY_DOgrKQsx8J1STNUZP/view?usp=sharing", "_blank");
            }}
            className="group flex items-center justify-center gap-3.5 no-underline rounded-full font-medium transition-all duration-300 ease-in-out hover:-translate-y-0.5 hover:bg-white/10 hover:border-white/60"
            style={{
              fontFamily: "var(--font-body)",
              fontSize: "16.5px",
              color: "#FFFFFF",
              backgroundColor: "rgba(20, 24, 27, 0.55)",
              backdropFilter: "blur(12px)",
              WebkitBackdropFilter: "blur(12px)",
              border: "1.5px solid rgba(255, 255, 255, 0.35)",
              padding: "10px 30px 10px 12px",
              boxShadow: "0 4px 18px rgba(0, 0, 0, 0.35)",
              cursor: "pointer",
            }}
          >
            <span
              className="flex items-center justify-center rounded-full border border-white/60"
              style={{
                width: "42px",
                height: "42px",
                backgroundColor: "rgba(255, 255, 255, 0.12)",
              }}
            >
              <Play size={16} className="text-white fill-white translate-x-[1px]" />
            </span>
            <span className="text-[16px] sm:text-[17px] tracking-tight text-white font-medium">
              Watch Demo
            </span>
          </button>
        </div>
      </section>

      {/* Trusted By / Digital Badges Section
      <div className="w-full mt-auto">
        <DigitalBadgesSection />
      </div> */}
    </div>
  );
}
