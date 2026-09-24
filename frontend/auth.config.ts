import type { NextAuthConfig } from "next-auth";

/**
 * Session Expiration Policy Constants (seconds)
 * ─────────────────────────────────────────────
 * Access Session:   30 minutes (1,800s)
 * Refresh Session:  7 days    (604,800s)
 * Idle Timeout:     30 minutes (1,800s)
 * Absolute Timeout: 7 days    (604,800s)
 */
export const ACCESS_SESSION_MAX_AGE = 30 * 60; // 30 minutes
export const REFRESH_SESSION_MAX_AGE = 7 * 24 * 60 * 60; // 7 days
export const IDLE_TIMEOUT_MS = 30 * 60 * 1000; // 30 minutes in ms
export const ABSOLUTE_TIMEOUT_MS = 7 * 24 * 60 * 60 * 1000; // 7 days in ms

/**
 * Edge-compatible Auth.js config.
 * ─────────────────────────────────────────────
 * This file contains NO database imports, NO bcrypt, NO Node.js-only modules.
 * It can safely run in the Next.js Edge runtime (used by proxy.ts).
 */
export const authConfig = {
  pages: {
    signIn: "/auth/login",
    error: "/auth/login",
  },

  session: {
    strategy: "jwt",
    maxAge: REFRESH_SESSION_MAX_AGE, // Refresh session / Absolute limit: 7 days
    updateAge: ACCESS_SESSION_MAX_AGE, // Access session / Token refresh interval: 30 minutes
  },

  callbacks: {
    /**
     * Called on every request by the proxy.
     * Returns true to allow access, false/redirect to block.
     */
    authorized({ auth, request }) {
      const { pathname } = request.nextUrl;
      const isExpired = auth?.error === "SessionExpired";
      const isAuthenticated = !!auth?.user && !isExpired;

      const PROTECTED_ROUTES: string[] = [];
      const AUTH_ROUTES = ["/auth/login", "/auth/signup", "/auth/sign-up"];

      const isProtectedRoute = PROTECTED_ROUTES.some(
        (r) => pathname === r || pathname.startsWith(r + "/")
      );
      if (isProtectedRoute && !isAuthenticated) return false;

      return true;
    },
  },

  providers: [],
} satisfies NextAuthConfig;
