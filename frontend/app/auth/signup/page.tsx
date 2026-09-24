"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { motion } from "framer-motion";
import {
  Mail,
  Lock,
  Eye,
  EyeOff,
  Sparkles,
  CircleUser,
  Loader2,
  ArrowRight,
  Building2,
  ShieldCheck,
  CheckCircle2,
} from "lucide-react";
import { signIn } from "next-auth/react";
import { signupSchema, UserRole } from "@/lib/schemas/auth";

export default function SignupPage() {
  const router = useRouter();

  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<UserRole | "">("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [serverError, setServerError] = useState("");
  const [errors, setErrors] = useState({
    name: "",
    email: "",
    role: "",
    password: "",
    confirmPassword: "",
  });

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();
    setServerError("");

    if (!role) {
      setErrors((p) => ({
        ...p,
        role: "Please select an authorized role (CPSE Admin or National Admin).",
      }));
      return;
    }

    // Client-side Zod validation
    const parsed = signupSchema.safeParse({ name, email, role, password, confirmPassword });
    if (!parsed.success) {
      const fieldErrors = parsed.error.flatten().fieldErrors;
      const formErrors = parsed.error.flatten().formErrors;
      setErrors({
        name: fieldErrors.name?.[0] ?? "",
        email: fieldErrors.email?.[0] ?? "",
        role: fieldErrors.role?.[0] ?? "",
        password: fieldErrors.password?.[0] ?? "",
        confirmPassword: fieldErrors.confirmPassword?.[0] ?? formErrors[0] ?? "",
      });
      return;
    }

    setErrors({ name: "", email: "", role: "", password: "", confirmPassword: "" });
    setIsLoading(true);

    try {
      // 1. Register user via API with selected role
      const res = await fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: parsed.data.name,
          email: parsed.data.email,
          role: parsed.data.role,
          password: parsed.data.password,
          confirmPassword: parsed.data.confirmPassword,
        }),
      });

      const data = await res.json();

      if (!res.ok) {
        if (data.fields) {
          setErrors({
            name: data.fields.name?.[0] ?? "",
            email: data.fields.email?.[0] ?? "",
            role: data.fields.role?.[0] ?? "",
            password: data.fields.password?.[0] ?? "",
            confirmPassword: data.fields.confirmPassword?.[0] ?? "",
          });
        } else {
          setServerError(data.error || "Registration failed. Please try again.");
        }
        return;
      }

      // 2. Auto-login after successful registration
      const signInResult = await signIn("credentials", {
        email: parsed.data.email,
        password: parsed.data.password,
        redirect: false,
      });

      if (signInResult?.error) {
        router.push("/auth/login?registered=true");
      } else {
        const targetDashboard = parsed.data.role === "national_admin" ? "/dashboard_national" : "/dashboard_cpse";
        router.push(targetDashboard);
        router.refresh();
      }
    } catch {
      setServerError("An unexpected error occurred during account creation.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleSignup = () => {
    if (!role) {
      setErrors((p) => ({
        ...p,
        role: "Please select an authorized role (CPSE Admin or National Admin) before continuing with Google.",
      }));
      return;
    }

    // Set cookie for server-side NextAuth signIn callback
    document.cookie = `pending_user_role=${role}; path=/; max-age=600; SameSite=Lax`;
    const targetDashboard = role === "national_admin" ? "/dashboard_national" : "/dashboard_cpse";
    signIn("google", { callbackUrl: targetDashboard });
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
        {/* Card Header Tag */}
        <span className="text-[10px] font-bold text-[#A8DD73] bg-[#A8DD73]/10 px-2.5 py-1 rounded-full border border-[#A8DD73]/25 inline-flex items-center gap-1.5 uppercase tracking-wider font-mono">
          <Sparkles className="w-3 h-3 text-[#B8E77A]" />
          <span>JOIN THE PLATFORM</span>
        </span>

        <h2
          className="text-2xl sm:text-3xl font-normal text-white m-0 mt-3 tracking-tight"
          style={{ fontFamily: "var(--font-heading)" }}
        >
          Create Enterprise Account
        </h2>
        <p className="text-xs sm:text-sm text-white/60 leading-normal m-0 mt-1">
          Join the NEMISYS material standardization workspace.
        </p>

        {/* Server error banner */}
        {serverError && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 p-3 bg-rose-500/10 border border-rose-500/30 rounded-xl text-xs text-rose-300 font-medium"
          >
            {serverError}
          </motion.div>
        )}

        {/* Form */}
        <form onSubmit={handleSignup} className="flex flex-col gap-3.5 mt-5" noValidate>
          {/* Role Selection (Mandatory) */}
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between">
              <label className="text-[11px] font-semibold text-white/70 uppercase tracking-wide">
                Enterprise Role <span className="text-[#A8DD73]">*</span>
              </label>
              <span className="text-[10px] text-white/40 font-mono">Mandatory selection</span>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
              {/* CPSE Admin Card */}
              <button
                type="button"
                onClick={() => {
                  setRole("cpse_admin");
                  if (errors.role) setErrors((p) => ({ ...p, role: "" }));
                }}
                className={`relative flex flex-col items-start text-left p-3 rounded-xl border transition-all cursor-pointer ${role === "cpse_admin"
                  ? "bg-[#A8DD73]/10 border-[#A8DD73] shadow-[0_0_15px_rgba(168,221,115,0.15)]"
                  : "bg-white/[0.03] border-white/10 hover:border-white/20 hover:bg-white/[0.05]"
                  }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <div
                    className={`p-1.5 rounded-lg ${role === "cpse_admin" ? "bg-[#A8DD73]/20 text-[#A8DD73]" : "bg-white/5 text-white/50"
                      }`}
                  >
                    <Building2 className="w-4 h-4" />
                  </div>
                  {role === "cpse_admin" && (
                    <CheckCircle2 className="w-4 h-4 text-[#A8DD73]" />
                  )}
                </div>
                <span className="text-xs font-semibold text-white">CPSE Admin</span>
                <span className="text-[10px] text-white/60 leading-tight mt-0.5">
                  Enterprise catalog, duplicate cleanup & harmonization
                </span>
              </button>

              {/* National Admin Card */}
              <button
                type="button"
                onClick={() => {
                  setRole("national_admin");
                  if (errors.role) setErrors((p) => ({ ...p, role: "" }));
                }}
                className={`relative flex flex-col items-start text-left p-3 rounded-xl border transition-all cursor-pointer ${role === "national_admin"
                  ? "bg-[#A8DD73]/10 border-[#A8DD73] shadow-[0_0_15px_rgba(168,221,115,0.15)]"
                  : "bg-white/[0.03] border-white/10 hover:border-white/20 hover:bg-white/[0.05]"
                  }`}
              >
                <div className="flex items-center justify-between w-full mb-1">
                  <div
                    className={`p-1.5 rounded-lg ${role === "national_admin" ? "bg-[#A8DD73]/20 text-[#A8DD73]" : "bg-white/5 text-white/50"
                      }`}
                  >
                    <ShieldCheck className="w-4 h-4" />
                  </div>
                  {role === "national_admin" && (
                    <CheckCircle2 className="w-4 h-4 text-[#A8DD73]" />
                  )}
                </div>
                <span className="text-xs font-semibold text-white">National Admin</span>
                <span className="text-[10px] text-white/60 leading-tight mt-0.5">
                  Master directory governance, cross-CPSE review & approval
                </span>
              </button>
            </div>
            {errors.role && (
              <div className="text-[10px] text-rose-400 font-medium px-1 mt-0.5">{errors.role}</div>
            )}
          </div>

          {/* Full Name */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signup-name" className="text-[11px] font-semibold text-white/70 uppercase tracking-wide">
              Full Name
            </label>
            <div className="relative flex items-center">
              <CircleUser className="absolute left-3.5 w-4 h-4 text-white/40 pointer-events-none" />
              <input
                id="signup-name"
                type="text"
                placeholder="e.g. Ramesh Kumar"
                autoComplete="name"
                value={name}
                disabled={isLoading}
                onChange={(e) => {
                  setName(e.target.value);
                  if (errors.name) setErrors((p) => ({ ...p, name: "" }));
                }}
                className={`w-full text-xs sm:text-sm text-white bg-white/[0.04] border rounded-xl pl-10 pr-4 h-[46px] outline-none transition-all disabled:opacity-50 placeholder:text-white/30 ${errors.name
                  ? "border-rose-500/50 focus:border-rose-400"
                  : "border-white/10 focus:border-[#A8DD73]/60 focus:bg-white/[0.06] focus:shadow-[0_0_15px_rgba(168,221,115,0.12)]"
                  }`}
              />
            </div>
            {errors.name && <div className="text-[10px] text-rose-400 font-medium px-1">{errors.name}</div>}
          </div>

          {/* Email */}
          <div className="flex flex-col gap-1.5">
            <label htmlFor="signup-email" className="text-[11px] font-semibold text-white/70 uppercase tracking-wide">
              Official Email
            </label>
            <div className="relative flex items-center">
              <Mail className="absolute left-3.5 w-4 h-4 text-white/40 pointer-events-none" />
              <input
                id="signup-email"
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

          {/* Password + Confirm in 2-col grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3.5">
            {/* Password */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="signup-password" className="text-[11px] font-semibold text-white/70 uppercase tracking-wide">
                Password
              </label>
              <div className="relative flex items-center">
                <Lock className="absolute left-3.5 w-4 h-4 text-white/40 pointer-events-none" />
                <input
                  id="signup-password"
                  type={showPassword ? "text" : "password"}
                  placeholder="Min 8 chars"
                  autoComplete="new-password"
                  value={password}
                  disabled={isLoading}
                  onChange={(e) => {
                    setPassword(e.target.value);
                    if (errors.password) setErrors((p) => ({ ...p, password: "" }));
                  }}
                  className={`w-full text-xs sm:text-sm text-white bg-white/[0.04] border rounded-xl pl-10 pr-10 h-[46px] outline-none transition-all disabled:opacity-50 placeholder:text-white/30 ${errors.password
                    ? "border-rose-500/50 focus:border-rose-400"
                    : "border-white/10 focus:border-[#A8DD73]/60 focus:bg-white/[0.06]"
                    }`}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                  className="absolute right-3 text-white/40 hover:text-white transition-colors"
                >
                  {showPassword ? <EyeOff className="w-3.5 h-3.5" /> : <Eye className="w-3.5 h-3.5" />}
                </button>
              </div>
              {errors.password && <div className="text-[10px] text-rose-400 font-medium px-1">{errors.password}</div>}
            </div>

            {/* Confirm Password */}
            <div className="flex flex-col gap-1.5">
              <label htmlFor="signup-confirm" className="text-[11px] font-semibold text-white/70 uppercase tracking-wide">
                Confirm
              </label>
              <div className="relative flex items-center">
                <Lock className="absolute left-3.5 w-4 h-4 text-white/40 pointer-events-none" />
                <input
                  id="signup-confirm"
                  type={showPassword ? "text" : "password"}
                  placeholder="Re-enter"
                  autoComplete="new-password"
                  value={confirmPassword}
                  disabled={isLoading}
                  onChange={(e) => {
                    setConfirmPassword(e.target.value);
                    if (errors.confirmPassword) setErrors((p) => ({ ...p, confirmPassword: "" }));
                  }}
                  className={`w-full text-xs sm:text-sm text-white bg-white/[0.04] border rounded-xl pl-10 pr-4 h-[46px] outline-none transition-all disabled:opacity-50 placeholder:text-white/30 ${errors.confirmPassword
                    ? "border-rose-500/50 focus:border-rose-400"
                    : "border-white/10 focus:border-[#A8DD73]/60 focus:bg-white/[0.06]"
                    }`}
                />
              </div>
              {errors.confirmPassword && (
                <div className="text-[10px] text-rose-400 font-medium px-1">{errors.confirmPassword}</div>
              )}
            </div>
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isLoading}
            className="w-full flex items-center justify-center gap-2 text-xs sm:text-sm font-semibold h-[48px] bg-[#A8DD73] text-[#0A0809] hover:bg-[#B8E77A] rounded-xl transition-all shadow-[0_2px_14px_rgba(168,221,115,0.25)] hover:-translate-y-0.5 disabled:opacity-60 disabled:cursor-not-allowed disabled:hover:translate-y-0 cursor-pointer mt-2"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-[#0A0809]" />
                <span>Registering Account…</span>
              </>
            ) : (
              <>
                <span>Complete Registration</span>
                <ArrowRight className="w-4 h-4" />
              </>
            )}
          </button>
        </form>

        {/* Divider */}
        <div className="flex items-center my-4">
          <div className="flex-grow border-t border-white/10" />
          <span className="text-[10px] font-bold text-white/30 mx-3 uppercase tracking-wider font-mono">OR</span>
          <div className="flex-grow border-t border-white/10" />
        </div>

        {/* OAuth */}
        <button
          type="button"
          disabled={isLoading}
          onClick={handleGoogleSignup}
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

      {/* Footer link to sign in */}
      <div className="text-center text-xs text-white/50 font-normal mt-5 pt-3 border-t border-white/10 shrink-0">
        <span>Already have an authorized account? </span>
        <Link href="/auth/login" className="text-[#A8DD73] hover:text-[#B8E77A] hover:underline font-semibold ml-1">
          Sign In
        </Link>
      </div>
    </motion.div>
  );
}
