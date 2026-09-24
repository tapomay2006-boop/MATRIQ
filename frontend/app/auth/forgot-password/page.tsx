"use client";

import { useState } from "react";
import Link from "next/link";
import { motion } from "framer-motion";
import { Mail, Sparkles, ArrowLeft, ArrowRight } from "lucide-react";
import { toast } from "sonner";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!email.trim()) {
      setError("Email address is required");
      return;
    } else if (!/\S+@\S+\.\S+/.test(email)) {
      setError("Invalid email format");
      return;
    }

    setError("");
    setSubmitted(true);
    toast.success("✉️ Reset link sent successfully to: " + email);
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, ease: "easeOut" }}
      className="p-6 sm:p-8 bg-[#121013]/90 border border-white/10 rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.6)] backdrop-blur-2xl flex flex-col justify-between w-full"
      style={{
        background: "radial-gradient(circle at 50% 0%, rgba(168,221,115,0.06), transparent 70%), rgba(18,16,19,0.92)",
      }}
    >
      <div>
        {/* Card Header tag */}
        <span className="text-[10px] font-bold text-[#A8DD73] bg-[#A8DD73]/10 px-2.5 py-1 rounded-full border border-[#A8DD73]/25 inline-flex items-center gap-1.5 uppercase tracking-wider font-mono">
          <Sparkles className="w-3 h-3 text-[#B8E77A]" />
          <span>SECURITY &amp; ACCESS</span>
        </span>

        <h2
          className="text-2xl sm:text-3xl font-normal text-white m-0 mt-3 tracking-tight"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Recover Account Password
        </h2>
        <p className="text-xs sm:text-sm text-white/60 leading-normal m-0 mt-1">
          Enter your official email to receive a secure recovery token.
        </p>

        {submitted ? (
          <div className="mt-6 p-4 bg-[#A8DD73]/10 border border-[#A8DD73]/30 rounded-2xl flex flex-col gap-2">
            <span className="text-xs font-bold text-[#A8DD73]">Recovery Link Dispatched</span>
            <p className="text-xs text-white/70 leading-relaxed m-0">
              We have dispatched an authorization reset token to <span className="font-semibold text-white">{email}</span>. Please verify your enterprise inbox.
            </p>
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="flex flex-col gap-4 mt-5" noValidate>
            <div className="flex flex-col gap-1.5">
              <label htmlFor="reset-email" className="text-[11px] font-semibold text-white/70 uppercase tracking-wide">
                Official Email Address
              </label>
              <div className="relative flex items-center">
                <Mail className="absolute left-3.5 w-4 h-4 text-white/40 pointer-events-none" />
                <input
                  id="reset-email"
                  type="email"
                  placeholder="officer@cpse.gov.in"
                  value={email}
                  onChange={(e) => {
                    setEmail(e.target.value);
                    if (error) setError("");
                  }}
                  className={`w-full text-xs sm:text-sm text-white bg-white/[0.04] border rounded-xl pl-10 pr-4 h-[46px] outline-none transition-all placeholder:text-white/30 ${error
                      ? "border-rose-500/50 focus:border-rose-400"
                      : "border-white/10 focus:border-[#A8DD73]/60 focus:bg-white/[0.06] focus:shadow-[0_0_15px_rgba(168,221,115,0.12)]"
                    }`}
                />
              </div>
              {error && <div className="text-[10px] text-rose-400 font-medium px-1">{error}</div>}
            </div>

            <button
              type="submit"
              className="w-full flex items-center justify-center gap-2 text-xs sm:text-sm font-semibold h-[48px] bg-[#A8DD73] text-[#0A0809] hover:bg-[#B8E77A] rounded-xl transition-all shadow-[0_2px_14px_rgba(168,221,115,0.25)] hover:-translate-y-0.5 cursor-pointer mt-1"
            >
              <span>Send Recovery Link</span>
              <ArrowRight className="w-4 h-4" />
            </button>
          </form>
        )}
      </div>

      <div className="text-center text-xs text-white/50 font-normal mt-6 pt-4 border-t border-white/10 shrink-0">
        <Link href="/auth/login" className="inline-flex items-center gap-1.5 text-white/70 hover:text-[#A8DD73] transition-colors font-medium">
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Return to Sign In</span>
        </Link>
      </div>
    </motion.div>
  );
}
