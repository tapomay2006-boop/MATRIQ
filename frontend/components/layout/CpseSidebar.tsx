"use client";

import React from "react";
import Link from "next/link";
import Image from "next/image";
import MatriqLogo from "@/components/common/MatriqLogo";
import { usePathname } from "next/navigation";
import { useSession, signOut } from "next-auth/react";
import {
  LayoutDashboard,
  Package,
  UploadCloud,
  Sparkles,
  CheckSquare,
  BarChart3,
  LogOut,
  Building2,
  X,
} from "lucide-react";

interface CpseSidebarProps {
  onCloseMobile?: () => void;
}

export default function CpseSidebar({ onCloseMobile }: CpseSidebarProps) {
  const pathname = usePathname();
  const { data: session } = useSession();

  const navGroups = [
    {
      group: "OVERVIEW",
      items: [
        { name: "Dashboard", href: "/dashboard_cpse", icon: LayoutDashboard },
      ],
    },
    {
      group: "MATERIAL DATA",
      items: [
        { name: "Materials", href: "/materials", icon: Package },
        { name: "Upload & Ingest", href: "/upload", icon: UploadCloud },
      ],
    },
  ];

  const userName = session?.user?.name || "CPSE Officer";
  const userEmail = session?.user?.email || "officer@cpse.gov.in";
  const userInitial = (session?.user?.name?.trim() || session?.user?.email?.trim() || "C").charAt(0).toUpperCase();

  return (
    <aside className="w-64 sm:w-68 h-full bg-[#0E0C0F] border-r border-white/10 flex flex-col justify-between p-4 shrink-0 select-none z-30">
      {/* Top Section: Brand & Navigation */}
      <div className="flex flex-col gap-6 overflow-y-auto no-scrollbar pr-1">
        {/* Logo & Role Badge */}
        <div className="flex items-center justify-between pt-2 px-1">
          <Link href="/dashboard_cpse" className="flex items-center gap-2.5 no-underline group">
            <MatriqLogo size={32} />
            <span
              className="font-bold text-white text-lg tracking-wider group-hover:text-[#A8DD73] transition-colors"
              style={{ fontFamily: "var(--font-heading)" }}
            >
              MATRIQ
            </span>
            <span className="px-2 py-0.5 rounded-md text-[10px] font-mono font-bold bg-[#A8DD73]/15 text-[#A8DD73] border border-[#A8DD73]/30 uppercase tracking-wider ml-1">
              CPSE
            </span>
          </Link>

          {onCloseMobile && (
            <button
              onClick={onCloseMobile}
              className="lg:hidden p-1.5 rounded-lg bg-white/5 hover:bg-white/10 text-zinc-400 hover:text-white transition-colors cursor-pointer"
              title="Close sidebar"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Role Pill Banner */}
        <div className="px-3 py-2 rounded-xl bg-white/[0.03] border border-white/10 flex items-center gap-2">
          <div className="p-1 rounded-lg bg-[#A8DD73]/15 text-[#A8DD73]">
            <Building2 className="w-3.5 h-3.5" />
          </div>
          <div className="flex flex-col">
            <span className="text-[11px] font-semibold text-white">CPSE Admin Workspace</span>
            <span className="text-[9px] text-zinc-400">Enterprise Node · Active</span>
          </div>
        </div>

        {/* Nav Groups */}
        <nav className="flex flex-col gap-5">
          {navGroups.map((group) => (
            <div key={group.group} className="flex flex-col gap-1">
              <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-zinc-500 px-2 py-1">
                {group.group}
              </span>
              {group.items.map((item) => {
                const isActive =
                  pathname === item.href ||
                  (item.href !== "/dashboard_cpse" && pathname.startsWith(item.href));
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    onClick={onCloseMobile}
                    className={`flex items-center justify-between px-3 py-2.5 rounded-xl text-xs sm:text-[13px] font-medium transition-all no-underline ${isActive
                      ? "bg-[#A8DD73]/15 text-[#A8DD73] border border-[#A8DD73]/30 shadow-[0_0_15px_rgba(168,221,115,0.08)] font-semibold"
                      : "text-zinc-400 hover:text-white hover:bg-white/[0.05] border border-transparent"
                      }`}
                  >
                    <div className="flex items-center gap-2.5">
                      <Icon
                        className={`w-4 h-4 transition-colors ${isActive ? "text-[#A8DD73]" : "text-zinc-400 group-hover:text-white"
                          }`}
                      />
                      <span>{item.name}</span>
                    </div>
                    {isActive && (
                      <span className="w-1.5 h-1.5 rounded-full bg-[#A8DD73] shadow-[0_0_6px_#A8DD73]" />
                    )}
                  </Link>
                );
              })}
            </div>
          ))}
        </nav>
      </div>

      {/* Bottom Section: Profile & Logout */}
      <div className="pt-3 border-t border-white/10 flex flex-col gap-2">
        <div className="flex items-center justify-between p-2 rounded-xl bg-white/[0.02] border border-white/5">
          <div className="flex items-center gap-2.5 min-w-0">
            {session?.user?.image ? (
              <img
                src={session.user.image}
                alt={userName}
                referrerPolicy="no-referrer"
                className="w-8 h-8 rounded-full border border-white/20 object-cover shrink-0"
              />
            ) : (
              <div className="w-8 h-8 rounded-full bg-[#A8DD73]/20 border border-[#A8DD73]/30 flex items-center justify-center text-[#A8DD73] font-bold text-xs shrink-0">
                {userInitial}
              </div>
            )}
            <div className="flex flex-col min-w-0">
              <span className="text-xs font-semibold text-white truncate leading-tight">
                {userName}
              </span>
              <span className="text-[10px] text-zinc-500 truncate leading-tight mt-0.5">
                {userEmail}
              </span>
            </div>
          </div>

          <button
            onClick={() => signOut({ callbackUrl: "/auth/login" })}
            className="p-1.5 rounded-lg bg-white/5 hover:bg-rose-500/20 text-zinc-400 hover:text-rose-400 border border-transparent hover:border-rose-500/30 transition-all cursor-pointer shrink-0"
            title="Sign out of enterprise account"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </aside>
  );
}

