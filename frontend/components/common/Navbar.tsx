"use client";

import { useState, useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import Link from "next/link";
import MatriqLogo from "@/components/common/MatriqLogo";

const navLinks = [
  { href: "/#home", label: "Home" },
  { href: "/#features", label: "Features" },
  { href: "/#how-it-works", label: "How It Works" },
  { href: "/#reviews", label: "Reviews" },
  { href: "/#faqs", label: "FAQs" },
];

interface NavbarProps {
  userInfo?: {
    name?: string | null;
    email?: string | null;
    image?: string | null;
  };
  ctaText?: string;
  ctaHref?: string;
}

export default function Navbar({ userInfo, ctaText = "Get Started", ctaHref = "/auth/login" }: NavbarProps) {
  const [isScrolled, setIsScrolled] = useState(false);
  const { data: session, status } = useSession();
  const router = useRouter();

  const handleGetStarted = () => {
    router.push(ctaHref || "/auth/login");
  };

  useEffect(() => {
    const handleScroll = () => {
      if (window.scrollY > 10) {
        setIsScrolled(true);
      } else {
        setIsScrolled(false);
      }
    };
    window.addEventListener("scroll", handleScroll);
    handleScroll();
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      className={`fixed top-0 left-0 right-0 w-full z-40 transition-all duration-300 ${isScrolled
        ? "bg-[#0A0809]/85 backdrop-blur-md border-b border-white/10 shadow-lg"
        : "bg-transparent"
        }`}
      style={{ height: "72px" }}
    >
      <div
        className="mx-auto flex w-full h-full items-center justify-between px-4 sm:px-6 xl:px-0"
        style={{ maxWidth: "1200px" }}
      >
        {/* Logo */}
        <Link href="/" className="flex items-center gap-2.5 no-underline z-10 relative group">
          <MatriqLogo size={32} />
          <span
            className="font-bold text-white tracking-wider group-hover:text-[#A8DD73] transition-colors"
            style={{
              fontFamily: "var(--font-body)",
              fontSize: "18px",
              letterSpacing: "0.05em",
            }}
          >
            MATRIQ
          </span>
        </Link>

        {/* Center Desktop nav links */}
        <div className="absolute inset-0 hidden md:flex items-center justify-center pointer-events-none">
          <div className="flex items-center gap-8 pointer-events-auto">
            {navLinks.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="no-underline transition-opacity duration-150 text-[15px] text-white/75 hover:text-white"
                style={{
                  fontFamily: "var(--font-body)",
                }}
              >
                {link.label}
              </Link>
            ))}
          </div>
        </div>

        {/* Right side - User info or CTA */}
        <div className="flex items-center gap-3 z-10 relative">
          {userInfo || session?.user ? (
            <div className="flex items-center gap-3">
              <div className="text-right hidden sm:block">
                <p className="text-[13px] font-semibold text-white m-0 leading-none">
                  {userInfo?.name || session?.user?.name || "Officer"}
                </p>
                {(userInfo?.email || session?.user?.email) && (
                  <p className="text-[11px] text-white/50 m-0 mt-0.5 leading-none">
                    {userInfo?.email || session?.user?.email}
                  </p>
                )}
              </div>
              {userInfo?.image || session?.user?.image ? (
                <img
                  src={userInfo?.image || session?.user?.image || ""}
                  alt={userInfo?.name || session?.user?.name || "User"}
                  width={36}
                  height={36}
                  className="w-9 h-9 rounded-full border-2 border-white/20 object-cover"
                />
              ) : (
                <div className="w-9 h-9 rounded-full bg-white/10 border-2 border-white/20 flex items-center justify-center text-[#A8DD73] text-[14px] font-bold">
                  {(userInfo?.name || session?.user?.name)?.charAt(0).toUpperCase() ?? "A"}
                </div>
              )}
            </div>
          ) : (
            <Link
              href={ctaHref || "/auth/login"}
              className="no-underline text-[15px] font-semibold text-[#0A0809] bg-[#A8DD73] hover:bg-[#B8E77A] cursor-pointer transition-all duration-200 hover:-translate-y-0.5 inline-flex items-center justify-center"
              style={{
                fontFamily: "var(--font-body)",
                borderRadius: "999px",
                padding: "8px 22px",
                boxShadow: "0 2px 12px rgba(168,221,115,0.25)",
                border: "none",
              }}
            >
              {ctaText}
            </Link>
          )}
        </div>
      </div>
    </nav>
  );
}
