"use client";

import { Suspense } from "react";
import { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { motion } from "framer-motion";
import { Mail, Lock, Eye, EyeOff, Sparkles, Loader2, ArrowRight } from "lucide-react";
import { signIn, getSession } from "next-auth/react";
import { loginSchema } from "@/lib/schemas/auth";

// ─────────────────────────────────────────────
// Inner form — uses useSearchParams so must be inside <Suspense>
// ─────────────────────────────────────────────
function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const callbackUrl = searchParams.get("callbackUrl") || "/";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [errors, setErrors] = useState({ email: "", password: "" });
  const [serverError, setServerError] = useState("");

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError("");

    const parsed = loginSchema.safeParse({ email, password });
    if (!parsed.success) {
      const fieldErrors = parsed.error.flatten().fieldErrors;
      setErrors({
        email: fieldErrors.email?.[0] ?? "",
        password: fieldErrors.password?.[0] ?? "",
      });
      return;
    }

    setErrors({ email: "", password: "" });
    setIsLoading(true);

    try {
      const result = await signIn("credentials", {
        email: parsed.data.email,
        password: parsed.data.password,
        redirect: false,
      });

      if (result?.error) {
        const msg =
          result.error === "CredentialsSignin"
            ? "Invalid email or password. Please verify your credentials."
            : result.error;
        setServerError(msg);
      } else {
        if (callbackUrl && callbackUrl !== "/" && callbackUrl !== "/dashboard") {
          router.push(callbackUrl);
        } else {
          const session = await getSession();
          const role = session?.user?.role;
          if (role === "national_admin") {
            router.push("/dashboard_national");
          } else {
            router.push("/dashboard_cpse");
          }
        }
        router.refresh();
      }
    } catch {
      setServerError("An unexpected error occurred. Please try again.");
    } finally {
      setIsLoading(false);
    }
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
        {/* Top Tag */}
        <span className="text-[10px] font-bold text-[#A8DD73] bg-[#A8DD73]/10 px-2.5 py-1 rounded-full border border-[#A8DD73]/25 inline-flex items-center gap-1.5 uppercase tracking-wider font-mono">
          <Sparkles className="w-3 h-3 text-[#B8E77A]" />
          <span>WELCOME BACK</span>
        </span>

        {/* Heading */}
        <h2
          className="text-2xl sm:text-3xl font-normal text-white m-0 mt-3 tracking-tight"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Sign In to MATRIQ
        </h2>
        <p className="text-xs sm:text-sm text-white/60 leading-normal m-0 mt-1">
          Access your material master intelligence workspace.
        </p>

        {/* Server Error */}
        {serverError && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300 font-medium"
          >
            {serverError}
          </motion.div>
        )}

        <form onSubmit={handleLogin} className="flex flex-col gap-3.5 mt-5" noValidate>
          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="login-email" className="text-[11px] font-semibold text-white/70 uppercase tracking-wide">
              Official Email
            </label>
            <div className="relative flex items-center">
              <Mail className="absolute left-3.5 w-4 h-4 text-white/40 pointer-events-none" />
              <input
                id="login-email"
                type="email"
                placeholder="officer@cpse.gov.in"
                autoComplete="email"
                value={email}
                disabled={isLoading}
                onChange={(e) => {
                  setEmail(e.target.value);
                  if (errors.email) setErrors((p) => ({ ...p, email: "" }));
                }}
                className={`w-full text-xs sm:text-sm text-white bg-white/[0.04] border rounded-xl pl-10 pr-4 h-[46px] outline-none transition-all disabled:opacity-50 placeholder:text-white/30 ${errors.email
                  ? "border-rose-500/50 focus:border-rose-400"
                  : "border-white/10 focus:border-[#A8DD73]/60 focus:bg-white/[0.06] focus:shadow-[0_0_15px_rgba(168,221,115,0.12)]"
                  }`}
              />
            </div>
            {errors.email && <div className="text-[10px] text-rose-400 font-medium px-1">{errors.email}</div>}
          </div>

          {/* Password */}
          <div className="flex flex-col gap-1.5">
            <div className="flex justify-between items-center">
              <label htmlFor="login-password" className="text-[11px] font-semibold text-white/70 uppercase tracking-wide">
                Password
              </label>
            </div>
            <div className="relative flex items-center">
              <Lock className="absolute left-3.5 w-4 h-4 text-white/40 pointer-events-none" />
              <input
                id="login-password"
                type={showPassword ? "text" : "password"}
                placeholder="••••••••••••"
                autoComplete="current-password"
                value={password}
                disabled={isLoading}
                onChange={(e) => {
                  setPassword(e.target.value);
                  if (errors.password) setErrors((p) => ({ ...p, password: "" }));
                }}
                className={`w-full text-xs sm:text-sm text-white bg-white/[0.04] border rounded-xl pl-10 pr-11 h-[46px] outline-none transition-all disabled:opacity-50 placeholder:text-white/30 ${errors.password
                  ? "border-rose-500/50 focus:border-rose-400"
                  : "border-white/10 focus:border-[#A8DD73]/60 focus:bg-white/[0.06] focus:shadow-[0_0_15px_rgba(168,221,115,0.12)]"
                  }`}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                aria-label={showPassword ? "Hide password" : "Show password"}
                className="absolute right-3.5 text-white/40 hover:text-white transition-colors"
              >
                {showPassword ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
              </button>
            </div>
            {errors.password && <div className="text-[10px] text-rose-400 font-medium px-1">{errors.password}</div>}
          </div>

          {/* Remember me */}
          <div className="flex items-center gap-2 select-none pt-1">
            <input
              id="remember"
              type="checkbox"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
              className="w-3.5 h-3.5 rounded border-white/20 bg-white/5 text-[#A8DD73] focus:ring-[#A8DD73]/40 cursor-pointer accent-[#A8DD73]"
            />
            <label htmlFor="remember" className="text-xs text-white/60 font-normal cursor-pointer select-none">
              Remember credentials on this device
            </label>
          </div>

          {/* Submit Button */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 text-xs sm:text-sm font-semibold h-[48px] bg-[#A8DD73] text-[#0A0809] hover:bg-[#B8E77A] rounded-xl transition-all shadow-[0_2px_14px_rgba(168,221,115,0.25)] hover:-translate-y-0.5 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0 cursor-pointer mt-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-[#0A0809]" />
                <span>Authenticating…</span>
              </>
            ) : (
              <>
                <span>Sign In to Platform</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="flex items-center my-5">
          <div className="flex-grow border-t border-white/10" />
          <span className="text-[10px] font-bold text-white/30 mx-3 uppercase tracking-wider font-mono">OR</span>
          <div className="flex-grow border-t border-white/10" />
        </div>

        {/* OAuth */}
        <button
          type="button"
          disabled={isLoading}
          onClick={() => signIn("google", { callbackUrl: "/dashboard" })}
          className="w-full flex items-center justify-center gap-2.5 h-[46px] bg-white/[0.04] border border-white/10 hover:border-white/20 hover:bg-white/[0.08] rounded-xl text-xs sm:text-sm font-medium text-white/90 transition-all cursor-pointer hover:-translate-y-0.5 disabled:opacity-50"
        >
          <svg className="w-4 h-4 shrink-0" viewBox="0 0 24 24">
            <path
              d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
              fill="#4285F4"
            />
            <path
              d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
              fill="#34A853"
            />
            <path
              d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.06H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.94l2.85-2.22.81-.63z"
              fill="#FBBC05"
            />
            <path
              d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.06l3.66 2.84c.87-2.6 3.3-4.52 6.16-4.52z"
              fill="#EA4335"
            />
          </svg>
          <span>Continue with Google</span>
        </button>
      </div>

      {/* Footer link to sign up */}
      <div className="text-center text-xs text-white/50 font-normal mt-6 pt-4 border-t border-white/10 shrink-0">
        <span>Need an authorized enterprise account? </span>
        <Link href="/auth/signup" className="text-[#A8DD73] hover:text-[#B8E77A] hover:underline font-semibold ml-1">
          Create Account
        </Link>
      </div>
    </motion.div>
  );
}

// ─────────────────────────────────────────────
// Page — wraps LoginForm in Suspense (required by useSearchParams)
// ─────────────────────────────────────────────
export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="p-8 bg-[#121013]/90 border border-white/10 rounded-[28px] shadow-[0_20px_60px_rgba(0,0,0,0.6)] backdrop-blur-2xl flex items-center justify-center min-h-[400px] w-full">
          <div className="flex flex-col items-center gap-3">
            <Loader2 className="w-6 h-6 text-[#A8DD73] animate-spin" />
            <p className="text-xs text-white/50 font-mono">Loading credentials…</p>
          </div>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
