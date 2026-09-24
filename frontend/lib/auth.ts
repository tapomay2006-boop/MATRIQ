import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import Google from "next-auth/providers/google";
import { randomUUID } from "crypto";
import {
  authConfig,
  IDLE_TIMEOUT_MS,
  ABSOLUTE_TIMEOUT_MS,
} from "@/auth.config";
import { loginSchema } from "@/lib/schemas/auth";

export const { handlers, auth, signIn, signOut } = NextAuth({
  ...authConfig,

  providers: [
    // Google OAuth Provider
    Google({
      clientId: process.env.GOOGLE_CLIENT_ID || "",
      clientSecret: process.env.GOOGLE_CLIENT_SECRET || "",
      allowDangerousEmailAccountLinking: true,
    }),

    // Credentials (Email + Password) Provider - Authenticates via PostgreSQL (api-service)
    Credentials({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },

      async authorize(credentials) {
        const parsed = loginSchema.safeParse(credentials);
        if (!parsed.success) return null;

        const { email, password } = parsed.data;
        const normalizedEmail = email.toLowerCase().trim();

        // 1. Authenticate with backend API (PostgreSQL backed)
        try {
          const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          const res = await fetch(`${backendUrl}/api/v1/users/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ email: normalizedEmail, password }),
          });

          if (res.ok) {
            const data = await res.json();
            return {
              id: String(data.id || normalizedEmail),
              name: data.full_name || normalizedEmail.split("@")[0],
              email: normalizedEmail,
              image: null,
              role: data.role || "cpse_admin",
            };
          }
        } catch {
          // Backend offline or unreachable in local dev
        }

        // 2. Development fallback authentication for testing (min length 6)
        if (password && password.length >= 6) {
          const isNational =
            normalizedEmail.includes("national") ||
            normalizedEmail.includes("director") ||
            normalizedEmail.includes("ministry");
          return {
            id: "usr_" + Buffer.from(normalizedEmail).toString("hex").slice(0, 12),
            name: isNational ? "National Director" : "CPSE Officer",
            email: normalizedEmail,
            image: null,
            role: isNational ? "national_admin" : "cpse_admin",
          };
        }

        return null;
      },
    }),
  ],

  callbacks: {
    ...authConfig.callbacks,

    async signIn({ user, account }) {
      if (!user.email) return false;

      if (account?.provider === "google") {
        try {
          const backendUrl = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
          const normalizedEmail = user.email.toLowerCase().trim();

          let assignedRole = (user as { role?: string }).role;
          if (!assignedRole) {
            try {
              const { cookies } = await import("next/headers");
              const cookieStore = await cookies();
              const pendingRole = cookieStore.get("pending_user_role")?.value;
              if (pendingRole === "cpse_admin" || pendingRole === "national_admin") {
                assignedRole = pendingRole;
              }
            } catch {
              // Ignore cookie read error
            }
            if (!assignedRole) {
              assignedRole = "cpse_admin";
            }
          }

          // Persist / Sync Google user to PostgreSQL backend via api-service
          const res = await fetch(`${backendUrl}/api/v1/users/oauth`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
              email: normalizedEmail,
              name: user.name || normalizedEmail.split("@")[0],
              image: user.image,
              role: assignedRole,
            }),
          });

          if (res.ok) {
            const dbUser = await res.json();
            if (dbUser?.id) user.id = String(dbUser.id);
            if (dbUser?.role) (user as { role?: string }).role = dbUser.role;
          }
        } catch (error) {
          console.warn("PostgreSQL user sync warning:", error);
        }
        return true;
      }
      return true;
    },

    async jwt({ token, user }) {
      const now = Date.now();

      // Initial Sign-in: Generate unique sessionId & initialize timers in JWT
      if (user) {
        const sessionId = randomUUID();
        const userRole = (user as { role?: string }).role || "cpse_admin";
        const userId = user.id || "usr_" + Buffer.from(user.email || "user").toString("hex").slice(0, 12);

        token.id = userId;
        token.role = userRole;
        if (user.name) token.name = user.name;
        if (user.email) token.email = user.email;
        if (user.image) token.picture = user.image;
        token.sessionId = sessionId;
        token.sessionCreatedAt = now; // Absolute timeout base (7 days)
        token.lastActiveAt = now;      // Idle timeout base (30 minutes)
        token.error = undefined;

        return token;
      }

      // ─────────────────────────────────────────────────────────
      // Subsequent Requests: Enforce Absolute and Idle Timeouts
      // ─────────────────────────────────────────────────────────
      if (token.error === "SessionExpired") {
        return token;
      }

      if (token.sessionCreatedAt) {
        const elapsedSinceCreated = now - (token.sessionCreatedAt as number);
        // Absolute Timeout: 7 days
        if (elapsedSinceCreated > ABSOLUTE_TIMEOUT_MS) {
          console.warn(`[Auth] Session ${token.sessionId} expired: Absolute timeout (7 days) exceeded.`);
          return {
            ...token,
            error: "SessionExpired",
          };
        }
      }

      if (token.lastActiveAt) {
        const elapsedSinceActive = now - (token.lastActiveAt as number);
        // Idle Timeout: 30 minutes
        if (elapsedSinceActive > IDLE_TIMEOUT_MS) {
          console.warn(`[Auth] Session ${token.sessionId} expired: Idle timeout (30 mins) exceeded.`);
          return {
            ...token,
            error: "SessionExpired",
          };
        }
      }

      // Refresh sliding idle window for active session
      token.lastActiveAt = now;

      return token;
    },

    async session({ session, token }) {
      if (token.error === "SessionExpired") {
        session.error = "SessionExpired";
        // Invalidate user on session so hooks perceive session as terminated
        // @ts-expect-error - allow clearing expired user
        session.user = null;
        return session;
      }

      if (token && session.user) {
        session.sessionId = token.sessionId as string;
        session.sessionCreatedAt = token.sessionCreatedAt as number;
        session.lastActiveAt = token.lastActiveAt as number;
        session.user.id = token.id as string;
        session.user.role = (token.role as string) || "cpse_admin";
        if (token.name) session.user.name = token.name as string;
        if (token.email) session.user.email = token.email as string;
        if (token.picture) session.user.image = token.picture as string;
      }

      return session;
    },
  },
});
