"use client";

import React, { useEffect } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import CpseDashboardPage from "@/app/dashboard_cpse/page";
import { Loader2 } from "lucide-react";

export default function DashboardPage() {
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "authenticated" && session?.user) {
      const role = session.user.role;
      if (role === "national_admin") {
        router.replace("/dashboard_national");
      }
    }
  }, [status, session, router]);

  if (status === "loading") {
    return (
      <div className="min-h-screen flex flex-col bg-[#0A0809] text-white items-center justify-center gap-3">
        <Loader2 className="w-7 h-7 text-[#A8DD73] animate-spin" />
        <p className="text-xs text-zinc-400 font-mono">Loading Material Intelligence Dashboard…</p>
      </div>
    );
  }

  // If National Admin, wait for redirect
  if (status === "authenticated" && session?.user?.role === "national_admin") {
    return (
      <div className="min-h-screen flex flex-col bg-[#0A0809] text-white items-center justify-center gap-3">
        <Loader2 className="w-7 h-7 text-emerald-400 animate-spin" />
        <p className="text-xs text-zinc-400 font-mono">Redirecting to National Governance Portal…</p>
      </div>
    );
  }

  // Render CPSE Admin Dashboard
  return <CpseDashboardPage />;
}
