"use client";

import Link from "next/link";
import Image from "next/image";
import MatriqLogo from "@/components/common/MatriqLogo";
import { Mail } from "lucide-react";

export default function Footer() {
  return (
    <footer
      className="relative w-full overflow-hidden border-t border-white/5 pt-16 pb-8"
      style={{ background: "#0A0809" }}
    >
      {/* Background ambient glow */}
      <div
        className="pointer-events-none absolute bottom-0 left-1/2 -translate-x-1/2 w-[800px] h-[250px] opacity-15 blur-[120px]"
        style={{
          background: "radial-gradient(circle, rgba(168,221,115,0.2) 0%, rgba(99,102,241,0.1) 60%, transparent 80%)",
        }}
      />

      <div className="relative mx-auto max-w-[1200px] px-6">
        <div className="grid grid-cols-1 gap-12 lg:grid-cols-12 lg:gap-8 pb-12">
          {/* Brand & Socials Section */}
          <div className="lg:col-span-5 flex flex-col justify-between">
            <div>
              {/* Brand Logo & Name */}
              <Link href="/" className="inline-flex items-center gap-3 group">
                <MatriqLogo size={36} />
                <span
                  className="text-xl font-bold text-white tracking-wider group-hover:text-[#A8DD73] transition-colors"
                  style={{ fontFamily: "var(--font-heading)" }}
                >
                  MATRIQ
                </span>
              </Link>

              {/* Tagline / Mission */}
              <p className="mt-4 text-sm leading-relaxed text-white/60 max-w-sm">
                AI-powered material master harmonization platform. Standardize legacy descriptions, eliminate duplicate
                catalogs, and optimize CPSE procurement with enterprise-grade intelligence.
              </p>
            </div>

            {/* Social Icons (X, LinkedIn, Instagram, YouTube) */}
            <div className="flex items-center gap-3 mt-6">
              {/* Twitter / X */}
              <a
                href="https://twitter.com"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Twitter / X"
                className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-white/70 hover:text-[#A8DD73] hover:border-[#A8DD73]/40 hover:bg-[#A8DD73]/5 transition-all duration-200"
              >
                <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                  <path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-5.214-6.817L4.99 21.75H1.68l7.73-8.835L1.254 2.25H8.08l4.713 6.231zm-1.161 17.52h1.833L7.084 4.126H5.117z" />
                </svg>
              </a>

              {/* LinkedIn */}
              <a
                href="https://linkedin.com"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="LinkedIn"
                className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-white/70 hover:text-[#A8DD73] hover:border-[#A8DD73]/40 hover:bg-[#A8DD73]/5 transition-all duration-200"
              >
                <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                  <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 10.9v8.37H9.2V10.9H6.46M7.83 6.45a1.64 1.64 0 1 0 0 3.28 1.64 1.64 0 0 0 0-3.28" />
                </svg>
              </a>

              {/* Instagram */}
              <a
                href="https://instagram.com"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="Instagram"
                className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-white/70 hover:text-[#A8DD73] hover:border-[#A8DD73]/40 hover:bg-[#A8DD73]/5 transition-all duration-200"
              >
                <svg className="w-4 h-4 fill-none stroke-current stroke-2" viewBox="0 0 24 24" strokeLinecap="round" strokeLinejoin="round">
                  <rect width="20" height="20" x="2" y="2" rx="5" ry="5" />
                  <path d="M16 11.37A4 4 0 1 1 12.63 8 4 4 0 0 1 16 11.37z" />
                  <line x1="17.5" x2="17.51" y1="6.5" y2="6.5" />
                </svg>
              </a>

              {/* YouTube */}
              <a
                href="https://youtube.com"
                target="_blank"
                rel="noopener noreferrer"
                aria-label="YouTube"
                className="w-10 h-10 rounded-xl bg-white/[0.04] border border-white/10 flex items-center justify-center text-white/70 hover:text-[#A8DD73] hover:border-[#A8DD73]/40 hover:bg-[#A8DD73]/5 transition-all duration-200"
              >
                <svg className="w-4 h-4 fill-current" viewBox="0 0 24 24">
                  <path d="M23.498 6.186a3.016 3.016 0 0 0-2.122-2.136C19.505 3.545 12 3.545 12 3.545s-7.505 0-9.377.505A3.017 3.017 0 0 0 .502 6.186C0 8.07 0 12 0 12s0 3.93.502 5.814a3.016 3.016 0 0 0 2.122 2.136c1.871.505 9.376.505 9.376.505s7.505 0 9.377-.505a3.015 3.015 0 0 0 2.122-2.136C24 15.93 24 12 24 12s0-3.93-.502-5.814zM9.545 15.568V8.432L15.818 12l-6.273 3.568z" />
                </svg>
              </a>
            </div>
          </div>

          {/* Links Columns */}
          <div className="lg:col-span-7 grid grid-cols-1 sm:grid-cols-3 gap-8">
            {/* NAVIGATE */}
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-widest text-white mb-5">
                NAVIGATE
              </h3>
              <ul className="space-y-3.5 text-sm">
                <li>
                  <Link href="/#home" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    Homepage
                  </Link>
                </li>
                <li>
                  <Link href="/#features" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    Features
                  </Link>
                </li>
                <li>
                  <Link href="/#how-it-works" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    How It Works
                  </Link>
                </li>
                <li>
                  <Link href="/#testimonials" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    Testimonials
                  </Link>
                </li>
                <li>
                  <Link href="/auth/login" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    Sign In
                  </Link>
                </li>
              </ul>
            </div>

            {/* SOLUTIONS */}
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-widest text-white mb-5">
                SOLUTIONS
              </h3>
              <ul className="space-y-3.5 text-sm">
                <li>
                  <Link href="/#features" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    Material Harmonizer
                  </Link>
                </li>
                <li>
                  <Link href="/#features" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    Duplicate Detection
                  </Link>
                </li>
                <li>
                  <Link href="/#features" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    Catalog Standardizer
                  </Link>
                </li>
                <li>
                  <Link href="/#how-it-works" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    AI Knowledge Graph
                  </Link>
                </li>
              </ul>
            </div>

            {/* SUPPORT */}
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-widest text-white mb-5">
                SUPPORT
              </h3>
              <ul className="space-y-3.5 text-sm">
                <li>
                  <Link href="/#faq" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    FAQs
                  </Link>
                </li>
                <li>
                  <a
                    href="mailto:support@apex.io"
                    className="inline-flex items-center gap-2 text-white/60 hover:text-[#A8DD73] transition-colors duration-150"
                  >
                    <Mail className="w-3.5 h-3.5 text-white/50" />
                    <span>Contact Us</span>
                  </a>
                </li>
                <li>
                  <Link href="/auth/signup" className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150">
                    Get Started
                  </Link>
                </li>
                <li>
                  <a
                    href="tel:+919064303017"
                    className="text-white/60 hover:text-[#A8DD73] transition-colors duration-150"
                  >
                    +919064303017
                  </a>
                </li>
              </ul>
            </div>
          </div>
        </div>

        {/* Bottom Bar Divider & Copyright */}
        <div className="border-t border-white/10 pt-6 flex flex-col sm:flex-row items-center justify-between gap-4 text-xs text-white/40">
          <p>© 2026 MATRIQ. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <Link href="/privacy" className="hover:text-[#A8DD73] transition-colors duration-150">
              Privacy Policy
            </Link>
            <Link href="/terms" className="hover:text-[#A8DD73] transition-colors duration-150">
              Terms &amp; Conditions
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
