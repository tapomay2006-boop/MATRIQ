"use client";

import React, { useState, useRef, useEffect } from "react";
import { useSession, signOut } from "next-auth/react";
import { LogOut, User, ShieldCheck } from "lucide-react";

interface UserProfileMenuProps {
  role: "cpse_admin" | "national_admin";
  defaultName?: string;
}

export default function UserProfileMenu({ role, defaultName }: UserProfileMenuProps) {
  const { data: session } = useSession();
  const [imageFailed, setImageFailed] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  const effectiveRole = (session?.user as any)?.role || role;
  const isNational = effectiveRole === "national_admin";
  const roleLabel = isNational ? "National Admin" : "CPSE Admin";
  const fallbackName = defaultName || (isNational ? "National Director" : "CPSE Officer");

  const userName = session?.user?.name?.trim() || fallbackName;
  const userEmail = session?.user?.email || "";
  const imageUrl = session?.user?.image;

  // First letter of the user name when manually entered (or email initial if name empty)
  const initial = (
    session?.user?.name?.trim() ||
    session?.user?.email?.trim() ||
    (isNational ? "N" : "C")
  ).charAt(0).toUpperCase();

  // Color theming based on role
  const accentBorder = isNational ? "border-emerald-500/30" : "border-[#A8DD73]/30";
  const accentHoverBorder = isNational ? "hover:border-emerald-400" : "hover:border-[#A8DD73]";
  const accentBg = isNational ? "bg-emerald-500/15" : "bg-[#A8DD73]/15";
  const accentText = isNational ? "text-emerald-400" : "text-[#A8DD73]";
  const accentGlow = isNational
    ? "shadow-[0_0_14px_rgba(16,185,129,0.25)]"
    : "shadow-[0_0_14px_rgba(168,221,115,0.25)]";

  // Close dropdown on outside click
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setMenuOpen(false);
      }
    }
    if (menuOpen) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [menuOpen]);

  return (
    <div ref={dropdownRef} className="relative flex items-center gap-3 shrink-0">
      {/* User Name & Role details on larger screens */}
      <div className="text-right hidden sm:block select-none">
        <p className="text-xs font-semibold text-white m-0 leading-tight truncate max-w-[160px]">
          {userName}
        </p>
        <p className={`text-[10px] ${accentText} font-mono m-0 mt-0.5 leading-none font-medium`}>
          {roleLabel}
        </p>
      </div>

      {/* Profile Icon (Google profile photo when available, or first letter of user name when manual signup) */}
      <button
        type="button"
        onClick={() => setMenuOpen((prev) => !prev)}
        className={`relative group focus:outline-none cursor-pointer rounded-full transition-all duration-200 hover:scale-105 active:scale-95`}
        title={`${userName} • ${roleLabel}`}
        aria-label="User profile options"
      >
        {imageUrl && !imageFailed ? (
          <img
            src={imageUrl}
            alt={userName}
            referrerPolicy="no-referrer"
            onError={() => setImageFailed(true)}
            className={`w-9 h-9 sm:w-10 sm:h-10 rounded-full border-2 ${accentBorder} ${accentHoverBorder} object-cover shadow-sm transition-colors`}
          />
        ) : (
          <div
            className={`w-9 h-9 sm:w-10 sm:h-10 rounded-full ${accentBg} border-2 ${accentBorder} ${accentHoverBorder} ${accentGlow} flex items-center justify-center ${accentText} text-sm sm:text-base font-bold select-none transition-colors`}
          >
            {initial}
          </div>
        )}
      </button>

      {/* Profile Details Dropdown Card */}
      {menuOpen && (
        <div className="absolute right-0 top-[calc(100%+12px)] w-64 p-3 rounded-2xl bg-[#121013]/98 backdrop-blur-2xl border border-white/10 shadow-2xl z-50 animate-in fade-in slide-in-from-top-2 duration-150">
          <div className="flex items-center gap-3 p-2.5 rounded-xl bg-white/[0.03] border border-white/5 mb-2">
            {imageUrl && !imageFailed ? (
              <img
                src={imageUrl}
                alt={userName}
                referrerPolicy="no-referrer"
                className={`w-10 h-10 rounded-full border ${accentBorder} object-cover shrink-0`}
              />
            ) : (
              <div
                className={`w-10 h-10 rounded-full ${accentBg} border ${accentBorder} flex items-center justify-center ${accentText} font-bold text-base shrink-0`}
              >
                {initial}
              </div>
            )}
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-semibold text-white truncate leading-tight">
                {userName}
              </span>
              <span className="text-[11px] text-zinc-400 truncate leading-tight mt-0.5">
                {userEmail || "Signed in"}
              </span>
              <div className="mt-1">
                <span
                  className={`inline-block text-[9px] font-mono font-bold px-1.5 py-0.5 rounded-md ${accentBg} ${accentText} border ${accentBorder} uppercase tracking-wider`}
                >
                  {roleLabel}
                </span>
              </div>
            </div>
          </div>

          <div className="pt-1 flex flex-col gap-1">
            <button
              onClick={() => signOut({ callbackUrl: "/auth/login" })}
              className="w-full flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-medium text-rose-400 hover:bg-rose-500/15 border border-transparent hover:border-rose-500/25 transition-all cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" />
              <span>Sign Out</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

