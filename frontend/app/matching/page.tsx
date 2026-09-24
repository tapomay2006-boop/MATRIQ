"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function MatchingPage() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/dashboard_cpse");
  }, [router]);

  return null;
}
