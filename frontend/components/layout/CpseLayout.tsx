"use client";

import React, { useState } from "react";
import CpseSidebar from "./CpseSidebar";
import UserProfileMenu from "./UserProfileMenu";
import MaterialSearch from "@/components/dashboard/MaterialSearch";
import { Menu } from "lucide-react";

interface CpseLayoutProps {
  children: React.ReactNode;
}

export default function CpseLayout({ children }: CpseLayoutProps) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex flex-col min-h-screen bg-[#0A0809] text-white font-sans selection:bg-[#A8DD73] selection:text-black">
      {/* Full-width Top Header Bar - Search Bar covers sidebar width on left, spans wide across, and stops beside profile icon */}
      <header className="sticky top-0 z-40 w-full h-[72px] sm:h-[76px] bg-[#0E0C0F]/95 backdrop-blur-md border-b border-white/10 px-4 sm:px-6 flex items-center justify-between gap-4 sm:gap-6">
        {/* Mobile menu toggle button */}
        <div className="lg:hidden flex items-center shrink-0">
          <button
            onClick={() => setMobileOpen(true)}
            className="p-2 rounded-xl bg-white/5 border border-white/10 text-white hover:bg-white/10 transition-colors cursor-pointer"
            title="Open navigation menu"
          >
            <Menu className="w-5 h-5 text-[#A8DD73]" />
          </button>
        </div>

        {/* Wide Search Bar - Spanning across the left sidebar width area all the way to profile icon */}
        <div className="flex-1 min-w-0 w-full">
          <MaterialSearch />
        </div>

        {/* User Profile Icon on the right side of the search bar */}
        <UserProfileMenu role="cpse_admin" defaultName="CPSE Officer" />
      </header>

      {/* Body Area below Header: Sidebar on Left, Content on Right */}
      <div className="flex-1 flex min-w-0">
        {/* Desktop Sticky Sidebar */}
        <div className="hidden lg:block sticky top-[72px] sm:top-[76px] h-[calc(100vh-72px)] sm:h-[calc(100vh-76px)] shrink-0">
          <CpseSidebar />
        </div>

        {/* Mobile Sidebar Slide-over Drawer */}
        {mobileOpen && (
          <div className="lg:hidden fixed inset-0 z-50 flex animate-in fade-in duration-200">
            <div
              className="fixed inset-0 bg-black/70 backdrop-blur-sm"
              onClick={() => setMobileOpen(false)}
            />
            <div className="relative z-10 flex">
              <CpseSidebar onCloseMobile={() => setMobileOpen(false)} />
            </div>
          </div>
        )}

        {/* Content Children */}
        <div className="flex-1 min-w-0 flex flex-col">
          {children}
        </div>
      </div>
    </div>
  );
}

